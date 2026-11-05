"""Validador INDEPENDIENTE del motor: revisa la parrilla cliente por cliente contra las restricciones
(leyendo umbrales, cupos, campanas y reglas desde la configuracion) y calcula las metricas.
Uso: python -m nba.validar <parrilla.csv> --clientes <clientes.csv> [--config config]"""
import argparse
import sys
from collections import Counter

import pandas as pd

from nba import config as cfgmod

# nombre estructural -> restriccion del PDF del reto
ESTRUCTURALES = {"UMBRAL_PRODUCTO": "R08", "UMBRAL_CANAL": "R11", "CANAL_NO_PERMITIDO": "R12",
                 "VARIOS_CANALES": "R13", "TOPE_PRODUCTOS": "R14", "TOPE_SEMANAL": "R15",
                 "CUPO_EXCEDIDO": "R16", "CAMPANA_INACTIVA": "R-vigencia", "PRODUCTO_REPETIDO": "R14b"}


def _aplica(r, c):
    """Alcance de una regla de elegibilidad (implementacion propia del validador)."""
    return (r.alcance_nivel == "global" or (r.alcance_nivel == "campana" and c.id in r.alcance_valores)
            or (r.alcance_nivel == "producto" and c.producto in r.alcance_valores)
            or (r.alcance_nivel == "objetivo" and c.objetivo in r.alcance_valores))


def _num(x):
    return None if x is None or (isinstance(x, float) and x != x) else x


def _regla_se_cumple(fila, r, producto):
    """True si la condicion de exclusion de la regla se cumple para esta fila (implementacion escalar)."""
    x = _num(fila.get(r.atributo))
    valor = producto if r.valor == "$producto" else r.valor
    if r.operador in ("contiene", "no_contiene"):
        items = str(x).split("|") if x is not None else []
        res = str(valor) in items
        return res if r.operador == "contiene" else not res
    if x is None:
        return False
    if r.operador in ("en", "no_en"):
        if isinstance(x, float) and x.is_integer():
            x = int(x)
        lista = [str(int(float(v))) if str(v).replace(".", "", 1).lstrip("-").isdigit() else str(v) for v in valor]
        res = str(x) in lista
        return res if r.operador == "en" else not res
    v = valor
    if isinstance(x, (int, float)):
        v = float(valor)
    return {"==": x == v, "!=": x != v, "<": x < v, "<=": x <= v, ">": x > v, ">=": x >= v}[r.operador]


def validar(parrilla: pd.DataFrame, clientes: pd.DataFrame, cfg) -> dict:
    viol = Counter()
    ejemplos = {}
    camps = {c.id: c for c in cfg.campanas}
    canales = {c.id: c for c in cfg.canales}
    reglas = [r for r in cfg.reglas if r.activa]
    f = cfg.fecha_corrida
    base = clientes.set_index("id_cliente")
    p = parrilla[parrilla.estado == "asignado"]
    if parrilla.id_cliente.duplicated().any():
        viol["CLIENTE_DUPLICADO"] += int(parrilla.id_cliente.duplicated().sum())
    if len(parrilla) != len(clientes):
        viol["FILAS_PARRILLA"] += abs(len(parrilla) - len(clientes))

    def marca(cod, cid):
        viol[cod] += 1
        ejemplos.setdefault(cod, cid)

    filas = base.loc[p.id_cliente].to_dict("records")
    valor = 0.0
    usos = Counter()
    asignados_camp = {}
    for t, fila in zip(p.itertuples(index=False), filas):
        cid = t.id_cliente
        if t.canal not in canales:
            marca("CANAL_NO_PERMITIDO", cid); continue
        ch = canales[t.canal]
        usos[t.canal] += 1
        ps = [c for c in (t.campana_1, t.campana_2) if isinstance(c, str) and c]
        asignados_camp[cid] = ps
        if not ps or len(set(ps)) != len(ps):
            marca("PRODUCTO_REPETIDO", cid)
        if len(ps) > ch.max_productos:
            marca("TOPE_PRODUCTOS", cid)
        if _num(fila[cfg.politica_contacto.columna_contactos_semana]) is None or \
                fila[cfg.politica_contacto.columna_contactos_semana] + 1 > cfg.politica_contacto.max_contactos_semana:
            marca("TOPE_SEMANAL", cid)
        if fila[ch.columna_score] < cfg.asignacion.umbral_score_canal:
            marca("UMBRAL_CANAL", cid)
        for r in reglas:
            if r.tipo == "canal" and (r.alcance_nivel == "global" or t.canal in r.alcance_valores):
                if _regla_se_cumple(fila, r, None):
                    marca(r.id, cid)
        for cp in ps:
            if cp not in camps:
                marca("CAMPANA_INACTIVA", cid); continue
            c = camps[cp]
            if not (c.activa and (c.vigencia_inicio is None or c.vigencia_inicio <= f)
                    and (c.vigencia_fin is None or f <= c.vigencia_fin)):
                marca("CAMPANA_INACTIVA", cid)
            if t.canal not in c.canales_permitidos:
                marca("CANAL_NO_PERMITIDO", cid)
            if fila[c.columna_score] < cfg.priorizacion.umbral_score_producto:
                marca("UMBRAL_PRODUCTO", cid)
            for r in reglas:
                if r.tipo == "elegibilidad" and _aplica(r, c):
                    if _regla_se_cumple(fila, r, c.producto):
                        marca(r.id, cid)
            valor += fila[c.columna_score] * fila[ch.columna_score] * c.valor_negocio
    for ch in canales.values():
        if usos[ch.id] > ch.cupo:
            viol["CUPO_EXCEDIDO"] += usos[ch.id] - ch.cupo
            ejemplos.setdefault("CUPO_EXCEDIDO", ch.id)

    return {"violaciones_total": int(sum(viol.values())), "violaciones": dict(viol), "ejemplos": ejemplos,
            "valor_esperado": round(float(valor), 2), "clientes_con_accion": int(len(p)),
            "productos_asignados": int(sum(len(v) for v in asignados_camp.values())),
            "uso_canales": dict(usos), "jerarquia_pct": jerarquia(asignados_camp, base, cfg)}


def jerarquia(asignados, base, cfg):
    """% de clientes con accion que recibieron su producto elegible de mayor jerarquia.
    Elegible = pasa reglas de elegibilidad y umbral de producto (sin mirar canal ni cupo)."""
    niv = cfg.nivel_jerarquia()
    orden = sorted([c for c in cfg.campanas_vigentes()], key=lambda c: -niv[c.id])
    reglas = [r for r in cfg.reglas if r.activa and r.tipo == "elegibilidad"]
    filas = base.loc[list(asignados)].to_dict("records")
    ok = 0
    for fila, ps in zip(filas, asignados.values()):
        for c in orden:
            if fila[c.columna_score] < cfg.priorizacion.umbral_score_producto:
                continue
            if any(_regla_se_cumple(fila, r, c.producto) for r in reglas if _aplica(r, c)):
                continue
            ok += c.id in ps
            break
    return round(100 * ok / max(1, len(asignados)), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parrilla")
    ap.add_argument("--clientes", default="data/oficial/clientes.csv")
    ap.add_argument("--config", default="config")
    a = ap.parse_args()
    cfg = cfgmod.cargar(a.config)
    r = validar(pd.read_csv(a.parrilla, dtype=str, keep_default_na=False).replace("", pd.NA).fillna(""),
                pd.read_csv(a.clientes, dtype={"canales_contactados_mes": str, "productos_ofertados_mes": str}), cfg)
    for k, v in r.items():
        print(f"{k}: {v}")
    sys.exit(1 if r["violaciones_total"] else 0)


if __name__ == "__main__":
    main()
