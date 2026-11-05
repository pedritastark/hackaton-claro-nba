"""Explicabilidad: un registro estructurado por cliente (fuente unica) del que salen
la frase de la parrilla, explicaciones.jsonl y el resumen agregado para la consola."""
import json
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd


class Explicador:
    def __init__(self, df, cfg, el, cand, asg):
        self.df, self.cfg, self.el, self.cand, self.asg = df, cfg, el, cand, asg
        self.ids = df["id_cliente"].to_numpy()
        self._cols = {}
        self.reglas = {r.id: r for r in cfg.reglas}
        self.camps, self.canales = cand.campanas, cand.canales
        self.sombra = asg.info.get("precio_sombra", {})
        C = len(self.canales)
        self.usado = np.array([(asg.canal == j).sum() for j in range(C)])
        self.cupo = np.array([ch.cupo for ch in self.canales])
        self.por_orden = cfg.asignacion.criterio_canal == "orden_preferencia"
        if self.por_orden:     # "mejor" canal = el primero de la lista de preferencia que tenga opcion
            ids = [ch.id for ch in self.canales]
            pref = cfg.asignacion.orden_preferencia
            rank = np.array([pref.index(i) if i in pref else len(pref) for i in ids], dtype=float)
            self.j_best = np.where(cand.n_paq > 0, -rank[None, :], -np.inf).argmax(1)
            self.v_best = np.where(cand.n_paq.sum(axis=1) > 0, cand.v_util[np.arange(len(df)), self.j_best], -np.inf)
        else:
            vu = np.where(cand.n_paq > 0, cand.v_util, -np.inf)
            self.j_best, self.v_best = vu.argmax(1), vu.max(1)
        pr = cfg.priorizacion
        self.ponderado = pr.alpha != 0 or pr.peso_modelo != 1 or pr.peso_valor != 1
        self.palabra = "utilidad ponderada" if self.ponderado else "valor"
        self.max_sem = cfg.politica_contacto.max_contactos_semana
        self.col_sem = cfg.politica_contacto.columna_contactos_semana

    # ---------- utilidades
    def _val(self, atributo, i):
        if atributo not in self._cols:
            self._cols[atributo] = self.df[atributo].to_numpy()
        v = self._cols[atributo][i]
        return "(sin dato)" if (isinstance(v, float) and v != v) else v

    def _motivo(self, codigo, i, k=None, j=None):
        """k: indice de campana, j: indice de canal (para umbrales)."""
        if codigo == "UMBRAL_PRODUCTO":
            return {"codigo": codigo, "texto": f"Probabilidad de compra de {self.camps[k].nombre} "
                    f"{self.cand.sp[i, k]:.2f} menor al minimo {self.cfg.priorizacion.umbral_score_producto:.2f}"}
        if codigo == "UMBRAL_CANAL":
            return {"codigo": codigo, "texto": f"Probabilidad de respuesta por {self.canales[j].id} "
                    f"{self.cand.sc[i, j]:.2f} menor al minimo {self.cfg.asignacion.umbral_score_canal:.2f}"}
        r = self.reglas[codigo]
        if isinstance(r.valor, list):
            vtxt = ", ".join(map(str, r.valor))
        else:
            vtxt = "el producto evaluado" if r.valor == "$producto" else str(r.valor)
        return {"codigo": codigo, "texto": f"{r.nombre}. La regla excluye cuando {r.atributo} {self._OP[r.operador]} {vtxt}; "
                f"este cliente tiene {r.atributo} = {self._val(r.atributo, i)}"}

    _OP = {"==": "es igual a", "!=": "es distinto de", "<": "es menor que", "<=": "es menor o igual a", ">": "es mayor que",
           ">=": "es mayor o igual a", "en": "es uno de", "no_en": "no es uno de", "contiene": "incluye",
           "no_contiene": "no incluye"}
    _ETIQ = {"UMBRAL_PRODUCTO": "probabilidad de compra baja", "UMBRAL_CANAL": "probabilidad de respuesta baja",
             "TOPE_PRODUCTOS": "tope de productos del canal", "CANAL_NO_PERMITIDO": "canal no permitido para el producto",
             "TOPE_SEMANAL": "tope semanal", "SIN_PRODUCTO": "ningun producto aplica", "ELEGIBLE_SIN_CONTACTO": "sin contacto"}

    def etiqueta(self, codigo):
        if codigo in self._ETIQ:
            return self._ETIQ[codigo]
        r = self.reglas.get(codigo)
        return f"{codigo} {r.nombre}" if r else codigo

    def _etiquetas(self, motivos):
        return "; ".join(self.etiqueta(m["codigo"]) for m in motivos)

    def _codigos(self, texto):
        return [c for c in texto.split(";") if c]

    # ---------- registro por cliente
    def registro(self, i) -> dict:
        el, cand, asg = self.el, self.cand, self.asg
        j = int(asg.canal[i])
        reg = {"id_cliente": str(self.ids[i]), "estado": "asignado" if j >= 0 else "sin_accion",
               "canal": self.canales[j].id if j >= 0 else None, "productos": [], "valor_esperado": 0.0,
               "descartados": [], "canales": [], "cupo": None, "motivo_sin_accion": None}
        elegidos = set()
        if j >= 0:
            for s in range(asg.paq.shape[1]):
                k = int(asg.paq[i, s])
                if k < 0:
                    continue
                c = self.camps[k]
                ve = float(cand.sp[i, k] * cand.sc[i, j] * c.valor_negocio)
                reg["productos"].append({"campana": c.id, "nombre": c.nombre, "prob_compra": round(float(cand.sp[i, k]), 4),
                                         "prob_canal": round(float(cand.sc[i, j]), 4), "valor_negocio": c.valor_negocio,
                                         "valor_esperado": round(ve, 4)})
                reg["valor_esperado"] += ve
                elegidos.add(k)
            reg["valor_esperado"] = round(reg["valor_esperado"], 4)

        for jj, ch in enumerate(self.canales):
            e = {"canal": ch.id, "valor": None, "resultado": None, "motivos": []}
            if not el.semana_ok[i]:
                e["resultado"] = "no_habilitado"
                e["motivos"] = [{"codigo": "TOPE_SEMANAL", "texto": self._texto_semana(i)}]
            elif not el.canal_ok[ch.id][i]:
                e["resultado"] = "no_habilitado"
                e["motivos"] = [self._motivo(cd, i, j=jj) for cd in self._codigos(el.canal_why[ch.id][i])]
            elif cand.n_paq[i, jj] == 0:
                e["resultado"] = "no_habilitado"
                e["motivos"] = [{"codigo": "SIN_PRODUCTO", "texto": "Ningun producto elegible del cliente se ofrece por este canal"}]
            else:
                e["valor"] = round(float(cand.v_util[i, jj]), 4)
                e["resultado"] = "elegido" if jj == j else "alternativa"
            reg["canales"].append(e)

        for k, c in enumerate(self.camps):
            if k in elegidos:
                continue
            codes = self._codigos(el.prod_why[c.id][i])
            if codes:
                mot = [self._motivo(cd, i, k=k) for cd in codes]
            elif j >= 0 and self.canales[j].id not in c.canales_permitidos:
                mot = [{"codigo": "CANAL_NO_PERMITIDO", "texto": f"{c.nombre} no se ofrece por {self.canales[j].id} "
                        f"(canales permitidos: {', '.join(c.canales_permitidos)})"}]
            elif j >= 0:
                mot = [{"codigo": "TOPE_PRODUCTOS", "texto": f"El canal {self.canales[j].id} admite {self.canales[j].max_productos} "
                        f"producto(s) por contacto y este aportaba menos valor"}]
            else:
                mot = [{"codigo": "ELEGIBLE_SIN_CONTACTO", "texto": "Elegible, pero el cliente no recibio contacto (ver motivo)"}]
            reg["descartados"].append({"campana": c.id, "nombre": c.nombre, "motivos": mot})

        hay_opcion = cand.n_paq[i].sum() > 0
        if j >= 0:
            jb = int(self.j_best[i])
            if jb != j and (self.por_orden or self.v_best[i] > cand.v_util[i, j] + 1e-12) and self.usado[jb] >= self.cupo[jb]:
                ced = max(0.0, float(self.v_best[i] - cand.v_util[i, j]))
                reg["cupo"] = {"tipo": "canal_alternativo", "canal_ideal": self.canales[jb].id,
                               "valor_ideal": round(float(self.v_best[i]), 4), "valor_asignado": round(float(cand.v_util[i, j]), 4),
                               "valor_cedido": round(ced, 4)}
        else:
            if not el.semana_ok[i]:
                reg["motivo_sin_accion"] = {"categoria": "tope_semanal", "texto": self._texto_semana(i)}
            elif not any(el.prod_ok[c.id][i] for c in self.camps):
                reg["motivo_sin_accion"] = {"categoria": "sin_campana_elegible", "texto": "Ninguna campana es elegible"}
            elif not hay_opcion:
                reg["motivo_sin_accion"] = {"categoria": "sin_canal_habilitado", "texto": "Ningun canal habilitado para sus productos elegibles"}
            else:
                jb = int(self.j_best[i])
                ch = self.canales[jb].id
                reg["cupo"] = {"tipo": "sin_cupo", "canal": ch, "valor": round(float(self.v_best[i]), 4),
                               "precio_cupo": round(float(self.sombra[ch]), 4) if ch in self.sombra else None}
                reg["motivo_sin_accion"] = {"categoria": "sin_cupo", "texto": "Sin cupo en sus canales habilitados"}
        return reg

    def _texto_semana(self, i):
        return (f"El cliente lleva {int(self._val(self.col_sem, i))} contactos esta semana; "
                f"el tope es {self.max_sem}")

    def categorias(self):
        """Etiqueta vectorizada por cliente, para buscar ejemplos de cada situacion."""
        el, cand, asg = self.el, self.cand, self.asg
        N = len(self.ids)
        cat = np.full(N, "", dtype=object)
        asignado = asg.canal >= 0
        idx = np.arange(N)
        vj = cand.v_util[idx, np.where(asignado, asg.canal, 0)]
        mejor = np.ones(N, bool) if self.por_orden else (self.v_best > vj + 1e-12)
        desplazado = (asignado & (self.j_best != asg.canal) & mejor
                      & (self.usado[self.j_best] >= self.cupo[self.j_best]))
        cat[asignado] = "Asignado"
        cat[desplazado] = "Asignado en canal alternativo (cupo del ideal agotado)"
        sin = ~asignado
        hay_prod = np.any([el.prod_ok[c.id] for c in self.camps], axis=0)
        hay_op = cand.n_paq.sum(axis=1) > 0
        cat[sin & ~el.semana_ok] = "Sin accion: tope semanal"
        cat[sin & el.semana_ok & ~hay_prod] = "Sin accion: sin campana elegible"
        cat[sin & el.semana_ok & hay_prod & ~hay_op] = "Sin accion: sin canal habilitado"
        cat[sin & el.semana_ok & hay_prod & hay_op] = "Sin accion: sin cupo"
        return cat

    def frase_asesor(self, reg) -> str:
        """Una frase corta, pensada para el asesor."""
        if reg["estado"] == "asignado":
            p = max(reg["productos"], key=lambda x: x["valor_esperado"])
            nombres = " y ".join(x["nombre"] for x in reg["productos"])
            s = (f"Ofrecer {nombres} por {reg['canal']}: {p['prob_compra']:.0%} de probabilidad de compra de "
                 f"{p['nombre']} y {p['prob_canal']:.0%} de responder por {reg['canal']}.")
            if reg["cupo"]:
                s += f" (Su canal ideal, {reg['cupo']['canal_ideal']}, ya no tenia cupo.)"
            return s
        m = reg["motivo_sin_accion"]
        cat = m["categoria"]
        if cat == "tope_semanal":
            return "No contactar: " + m["texto"] + "."
        if cat == "sin_campana_elegible":
            primeros = "; ".join(f"{d['nombre']}: {d['motivos'][0]['texto']}" for d in reg["descartados"])
            return "No contactar: no cumple las condiciones de ninguna campana. " + primeros + "."
        if cat == "sin_canal_habilitado":
            return "No contactar: ningun canal disponible. " + "; ".join(
                f"{c['canal']}: {c['motivos'][0]['texto']}" for c in reg["canales"] if c["motivos"]) + "."
        c = reg["cupo"]
        return (f"No contactar en esta corrida: su mejor opcion era {c['canal']} (valor {c['valor']:.3f}) "
                f"pero ese cupo se agoto con clientes que aportan mas.")

    # ---------- frase para la parrilla
    def frase(self, reg) -> str:
        if reg["estado"] == "asignado":
            det = " + ".join(f"{p['nombre']} [{p['prob_compra']:.2f} compra x {p['prob_canal']:.2f} {reg['canal']} x {p['valor_negocio']:.1f} valor = {p['valor_esperado']:.3f}]"
                             for p in reg["productos"])
            s = f"Se ofrece {det} por {reg['canal']}; valor esperado {reg['valor_esperado']:.3f}."
            c = reg["cupo"]
            if c:
                s += (f" Su mejor canal era {c['canal_ideal']} ({self.palabra} {c['valor_ideal']:.3f}) pero agoto su cupo; "
                      f"se uso {reg['canal']} cediendo {c['valor_cedido']:.3f}.")
            desc = [f"{d['campana']} ({self._etiquetas(d['motivos'])})" for d in reg["descartados"]]
            if desc:
                s += " No se ofrece: " + ", ".join(desc) + "."
            return s
        m = reg["motivo_sin_accion"]
        cat = m["categoria"]
        if cat == "tope_semanal":
            return "Tope semanal de contactos: " + m["texto"].lower()
        if cat == "sin_campana_elegible":
            return "Sin campana elegible (" + ";".join(
                f"{d['campana']}:{'+'.join(x['codigo'] for x in d['motivos'])}" for d in reg["descartados"]) + "). " + \
                "; ".join(f"{d['campana']} -> {self._etiquetas(d['motivos'])}" for d in reg["descartados"])
        if cat == "sin_canal_habilitado":
            return "Sin canal habilitado (" + ";".join(
                f"{c['canal']}:{'+'.join(x['codigo'] for x in c['motivos'])}" for c in reg["canales"]) + ")"
        c = reg["cupo"]
        if c["precio_cupo"] is not None:
            return (f"Sin cupo: su mejor contacto ({c['canal']}) tenia {self.palabra} {c['valor']:.3f} y ese cupo, agotado, "
                    f"vale {c['precio_cupo']:.3f} por contacto (aporte neto <= 0); se uso en clientes que aportan mas")
        return f"Sin cupo: los cupos de sus canales habilitados se agotaron antes de llegar a este cliente (mejor opcion {c['canal']}, {self.palabra} {c['valor']:.3f})"


def procesar(df, cfg, el, cand, asg, jsonl: Optional[str] = None):
    """Devuelve (razones[N], resumen). Si jsonl, escribe un registro estructurado por linea."""
    ex = Explicador(df, cfg, el, cand, asg)
    N = len(df)
    razones = np.empty(N, dtype=object)
    cats, ced_n, ced_v, sin_cupo_n, sin_cupo_v = Counter(), 0, 0.0, 0, 0.0
    import gzip
    f = (gzip.open(jsonl, "wt", encoding="utf-8") if jsonl.endswith(".gz") else open(jsonl, "w", encoding="utf-8")) if jsonl else None
    try:
        for i in range(N):
            reg = ex.registro(i)
            razones[i] = ex.frase(reg)
            if reg["estado"] == "sin_accion":
                cats[reg["motivo_sin_accion"]["categoria"]] += 1
                if reg["cupo"]:
                    sin_cupo_n += 1
                    sin_cupo_v += reg["cupo"]["valor"]
            elif reg["cupo"]:
                ced_n += 1
                ced_v += reg["cupo"]["valor_cedido"]
            if f:
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    finally:
        if f:
            f.close()

    def cuenta(why):
        return dict(pd.Series(why).str.split(";").explode().loc[lambda x: x != ""].value_counts())

    resumen = {
        "clientes": N,
        "embudo_campanas": {c.id: {"elegibles": int(el.prod_ok[c.id].sum()),
                                   "excluidos_por": {k: int(v) for k, v in cuenta(el.prod_why[c.id]).items()}}
                            for c in cand.campanas},
        "embudo_canales": {ch.id: {"habilitados": int(el.canal_ok[ch.id].sum()),
                                   "excluidos_por": {k: int(v) for k, v in cuenta(el.canal_why[ch.id]).items()}}
                           for ch in cand.canales},
        "tope_semanal_excluye": int((~el.semana_ok).sum()),
        "cupos": {ch.id: {"cupo": ch.cupo, "usado": int(ex.usado[j]), "uso_pct": round(100 * ex.usado[j] / max(1, ch.cupo), 1),
                          "precio_cupo": round(ex.sombra[ch.id], 4) if ch.id in ex.sombra else None}
                  for j, ch in enumerate(cand.canales)},
        "sin_accion_por": dict(cats),
        "desplazados_a_otro_canal": {"clientes": ced_n, "valor_cedido": round(ced_v, 2)},
        "sin_accion_por_cupo": {"clientes": sin_cupo_n, "valor_no_capturado": round(sin_cupo_v, 2)},
    }
    return razones, resumen
