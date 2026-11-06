"""Logica de la consola de negocio, sin interfaz: la usa la API (React). El borrador de configuracion vive en el
navegador como JSON; aqui solo se valida, se calcula su impacto y se guarda."""
import copy
import json
import os
import re
import shutil
import sys
import threading
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from nba import asignacion, comparar, config, run, validar, versiones   # noqa: E402
from nba.config import Config, ConfigError                          # noqa: E402
from nba.explicar import Explicador                                  # noqa: E402
from nba.reglas import frase as frase_regla                          # noqa: E402
import tablero                                                       # noqa: E402  (funciones de datos del tablero)

DTYPES = {"canales_contactados_mes": str, "productos_ofertados_mes": str}
COL_CALIF, ORDEN_CALIF = "calificacion_riesgo", ["E", "A", "B", "C", "P"]
COL_LLAMADAS = "contactos_asesor_mes"
CATEGORIAS = {"Asignado": "Con acción asignada",
              "Asignado en canal alternativo (cupo del ideal agotado)": "Con acción, en su segundo mejor canal (cupo agotado)",
              "Sin accion: tope semanal": "Sin acción · tope semanal de contactos",
              "Sin accion: sin campana elegible": "Sin acción · sin campaña elegible",
              "Sin accion: sin canal habilitado": "Sin acción · sin canal habilitado",
              "Sin accion: sin cupo": "Sin acción · sin cupo en sus canales"}
METRICAS_CLAVE = ("valor_esperado", "clientes_con_accion", "productos_asignados", "jerarquia_pct")

_estado = {"ruta": None}
_candado = threading.RLock()


class ErrorNegocio(Exception):
    """Error que el usuario de negocio puede entender y corregir (la API lo devuelve con su mensaje)."""

    def __init__(self, mensaje, detalle=None, codigo=422):
        super().__init__(mensaje)
        self.mensaje, self.detalle, self.codigo = mensaje, detalle or [], codigo


# ------------------------------------------------------------------ utilidades
def config_dir() -> str:
    return os.environ.get("NBA_CONFIG_DIR", str(ROOT / "config"))


def limpio(x):
    """Convierte numpy/pandas a tipos JSON (NaN -> None)."""
    if isinstance(x, dict):
        return {str(k): limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v) for v in x]
    if isinstance(x, np.ndarray):
        return [limpio(v) for v in x.tolist()]
    if isinstance(x, pd.DataFrame):
        return limpio(x.to_dict("records"))
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if x != x else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if x is pd.NaT:
        return None
    return x


def describir_error(e) -> list:
    """Lista de {campo, mensaje} legible para negocio."""
    if isinstance(e, ValidationError):
        return [{"campo": ".".join(str(p) for p in x["loc"]) or "(general)",
                 "mensaje": x["msg"].replace("Value error, ", "")} for x in e.errors()]
    return [{"campo": "configuración", "mensaje": str(e)}]


def n(x, dec=0):
    return tablero.n(x, dec)


# ------------------------------------------------------------------ base de clientes
def ruta_activa() -> str:
    if _estado["ruta"] is None:
        oficial = ROOT / "data" / "oficial" / "clientes.csv"
        _estado["ruta"] = os.environ.get("NBA_CLIENTES", str(oficial))
    return _estado["ruta"]


def _mtime(ruta) -> float:
    p = Path(ruta)
    return p.stat().st_mtime if p.exists() else 0.0


def _exigir_base():
    ruta = ruta_activa()
    if not Path(ruta).is_file():
        raise ErrorNegocio("La base de clientes activa no existe. Elige otra en «Base de datos».", codigo=409)
    return ruta, _mtime(ruta)


@lru_cache(maxsize=2)
def _cargar_df(ruta, mtime):
    return pd.read_csv(ruta, dtype=DTYPES)


def cargar_df(ruta, mtime):
    with _candado:
        return _cargar_df(ruta, mtime)


# ------------------------------------------------------------------ motor (con cache)
@lru_cache(maxsize=4)
def _ejecutar(cfg_json, ruta, mtime):
    cfg = Config.model_validate_json(cfg_json)
    df = _cargar_df(ruta, mtime)
    el, cand, asg = comparar.nucleo(df, cfg)
    return {"cfg": cfg, "df": df, "el": el, "cand": cand, "asg": asg, "m": comparar.metricas(cand, el, asg, cfg)}


def ejecutar(cfg_json, ruta, mtime):
    with _candado:
        return _ejecutar(cfg_json, ruta, mtime)


@lru_cache(maxsize=6)
def _validar_corrida(cfg_json, ruta, mtime):
    r = _ejecutar(cfg_json, ruta, mtime)
    g = comparar.parrilla_ligera(r["df"], r["cfg"], r["el"], r["cand"], r["asg"])
    v = validar.validar(g, r["df"], r["cfg"])
    return {k: v[k] for k in ("violaciones_total", "violaciones", "ejemplos")}


def validar_corrida(cfg_json, ruta, mtime):
    with _candado:
        return limpio(_validar_corrida(cfg_json, ruta, mtime))


@lru_cache(maxsize=2)
def _explicador(cfg_json, ruta, mtime):
    r = _ejecutar(cfg_json, ruta, mtime)
    return Explicador(r["df"], r["cfg"], r["el"], r["cand"], r["asg"])


def explicador(cfg_json, ruta, mtime):
    with _candado:
        return _explicador(cfg_json, ruta, mtime)


def _metricas_publicas(m):
    return limpio({k: v for k, v in m.items() if k != "valor_por_cliente"})


# ------------------------------------------------------------------ configuracion
def _cfg_inicial():
    try:
        return config.cargar(str(ROOT / "config_inicial"))
    except Exception:
        return None


def cargar_vigente() -> Config:
    try:
        return config.cargar(config_dir())
    except Exception as e:
        raise ErrorNegocio("La configuración guardada no es válida.", describir_error(e), codigo=409)


def nombre_configuracion(cfg: Config) -> str:
    actual = cfg.model_dump_json()
    for v in versiones.listar(config_dir())[:20]:
        try:
            if versiones.cargar_version(v["version"], config_dir()).model_dump_json() == actual:
                return v["etiqueta"]
        except Exception:
            continue
    ini = _cfg_inicial()
    if ini is not None and ini.model_dump_json() == actual:
        return "configuración inicial del reto"
    return "modificada, sin versionar"


def version_anterior(cfg: Config):
    actual = cfg.model_dump_json()
    for v in versiones.listar(config_dir())[:20]:
        try:
            c = versiones.cargar_version(v["version"], config_dir())
        except Exception:
            continue
        if c.model_dump_json() != actual:
            return v["etiqueta"], c
    ini = _cfg_inicial()
    if ini is not None and ini.model_dump_json() != actual:
        return "configuración inicial del reto", ini
    return None


def _es_regla_llamadas(r):
    return (r.tipo == "canal" and r.alcance_nivel == "canal" and r.alcance_valores == ["asesor"]
            and r.atributo == COL_LLAMADAS and r.operador == ">=")


def _es_regla_calif(r):
    return (r.tipo == "elegibilidad" and r.alcance_nivel == "campana" and len(r.alcance_valores) == 1
            and r.atributo == COL_CALIF and r.operador in ("en", "no_en"))


def calificaciones_por_campana(cfg: Config) -> dict:
    res = {c.id: list(ORDEN_CALIF) for c in cfg.campanas}
    for r in cfg.reglas:
        if r.activa and _es_regla_calif(r) and r.alcance_valores[0] in res:
            vals = [str(v) for v in r.valor]
            permitidas = [o for o in ORDEN_CALIF if (o not in vals if r.operador == "en" else o in vals)]
            res[r.alcance_valores[0]] = [o for o in res[r.alcance_valores[0]] if o in permitidas]
    return res


def derivados(cfg: Config) -> dict:
    """Datos que alimentan los controles directos del borrador."""
    rl = next((r for r in cfg.reglas if _es_regla_llamadas(r)), None)
    return {"calificaciones": calificaciones_por_campana(cfg), "orden_calificaciones": ORDEN_CALIF,
            "tope_llamadas": int(rl.valor) if rl is not None else None,
            "posicion_jerarquia": {cid: i + 1 for i, (cid, _) in
                                   enumerate(sorted(cfg.nivel_jerarquia().items(), key=lambda x: -x[1]))}}


def info_configuracion() -> dict:
    cfg = cargar_vigente()
    ruta = ruta_activa()
    columnas = []
    if Path(ruta).is_file():
        columnas = list(cargar_df(ruta, _mtime(ruta)).columns)
    return {"config": cfg.model_dump(mode="json"), "nombre": nombre_configuracion(cfg), "columnas": columnas,
            "operadores": config.OPERADORES, "derivados": derivados(cfg)}


def revisar_borrador(d: dict) -> dict:
    """Valida un borrador: errores legibles, o derivados y frases de negocio si es valido."""
    try:
        cfg = Config.model_validate(d)
    except Exception as e:
        return {"ok": False, "errores": describir_error(e)}
    vigente = cargar_vigente()
    return {"ok": True, "config": cfg.model_dump(mode="json"), "derivados": derivados(cfg),
            "frases": [{"id": r.id, "activa": r.activa, "texto": frase_regla(r)} for r in cfg.reglas],
            "igual_a_vigente": cfg.model_dump_json() == vigente.model_dump_json()}


def fijar_llamadas(d: dict, valor: int) -> dict:
    cfg = Config.model_validate(d)
    for r in cfg.reglas:
        if _es_regla_llamadas(r):
            r.valor = int(valor)
    return cfg.model_dump(mode="json")


def fijar_calificaciones(d: dict, campana: str, permitidas: list) -> dict:
    """Traduce 'calificaciones permitidas' de una campana a una regla de elegibilidad (la regla sigue siendo comun)."""
    cfg = Config.model_validate(d)
    camp = next((c for c in cfg.campanas if c.id == campana), None)
    if camp is None:
        raise ErrorNegocio(f"No existe la campaña {campana}.")
    previas = [r for r in cfg.reglas if _es_regla_calif(r) and r.alcance_valores == [campana]]
    rid = previas[0].id if previas else f"CAL-{campana}"
    reglas = [r for r in cfg.reglas if r not in previas]
    permitidas = [o for o in ORDEN_CALIF if o in permitidas]
    if set(permitidas) != set(ORDEN_CALIF):
        reglas.append(config.Regla(
            id=rid, nombre=f"{camp.nombre}: solo con calificacion {', '.join(permitidas) or 'ninguna'}",
            tipo="elegibilidad", alcance_nivel="campana", alcance_valores=[campana], atributo=COL_CALIF,
            operador="no_en", valor=list(permitidas), activa=True))
    cfg.reglas = reglas
    return cfg.model_dump(mode="json")


def restaurar_inicial() -> dict:
    inicial = ROOT / "config_inicial"
    if not inicial.exists():
        raise ErrorNegocio("No encuentro la carpeta config_inicial/ para restaurar.", codigo=404)
    base = Path(config_dir())
    respaldo = base / "respaldo" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "_invalida")
    respaldo.mkdir(parents=True, exist_ok=True)
    for a in versiones.ARCHIVOS:
        if (base / a).exists():
            shutil.copy(base / a, respaldo / a)
        shutil.copy(inicial / a, base / a)
    return {"respaldo": str(respaldo)}


# ------------------------------------------------------------------ estado general (barra lateral)
def estado() -> dict:
    ruta = ruta_activa()
    p = Path(ruta)
    base = {"ruta": ruta, "nombre": p.name, "existe": p.is_file(), "filas": 0}
    if p.is_file():
        with open(p, "rb") as f:
            base["filas"] = sum(1 for _ in f) - 1
    out = {"base": base, "configuracion": None, "configuracion_valida": True}
    try:
        cfg = config.cargar(config_dir())
        out["configuracion"] = nombre_configuracion(cfg)
    except Exception as e:
        out["configuracion_valida"] = False
        out["errores"] = describir_error(e)
    return out


# ------------------------------------------------------------------ tablero
@lru_cache(maxsize=6)
def _datos_tablero(cfg_json, ruta, mtime):
    r = _ejecutar(cfg_json, ruta, mtime)
    cfg = r["cfg"]
    ex = _explicador(cfg_json, ruta, mtime)
    cat = pd.Series(ex.categorias())
    casos = []
    for k, nombre in CATEGORIAS.items():
        idx = np.where(cat.to_numpy() == k)[0]
        if k != "Asignado" and len(idx):
            casos.append({"nombre": nombre, "cantidad": int(len(idx)), "id": str(ex.ids[idx[0]])})
    return {"etapas": tablero.etapas_embudo(r["el"], r["cand"], r["asg"]),
            "reglas": tablero.reglas_que_mas_excluyen(r["el"], cfg, r["cand"]),
            "composicion": tablero.composicion(r["cand"], r["asg"]), "casos": casos}


def _alertas(m, datos, cfg, prev, total, cupo_sin):
    """Avisos para revisar. Cada uno puede traer una accion: abrir un cliente de ejemplo o ir a otra seccion."""
    out = []
    llenos = [tablero.canal(ch.id) for ch in cfg.canales if m["uso_canales"][ch.id] >= ch.cupo]
    if llenos:
        out.append({"texto": f"**{' y '.join(llenos)}** {'está lleno' if len(llenos) == 1 else 'están llenos'}: "
                             "hay clientes que recibieron su segundo mejor canal.",
                    "pagina": "Cambiar configuración", "etiqueta_accion": "Ajustar cupos"})
    if cupo_sin:
        out.append({"texto": f"**{n(cupo_sin['cantidad'])}** clientes quedaron sin acción por falta de cupo.",
                    "cliente": cupo_sin["id"], "etiqueta_accion": "Ver un ejemplo"})
    if prev:
        etq, mp, dp = prev
        dv = 100 * (m["valor_esperado"] - mp["valor_esperado"]) / max(1e-9, mp["valor_esperado"])
        if abs(dv) >= 1:
            out.append({"texto": f"El valor esperado cambió **{tablero.signo(dv, 1)} %** frente a «{etq}».",
                        "pagina": "Versiones", "etiqueta_accion": "Ver versiones"})
        antes = dp["reglas"].set_index(["codigo", "tipo"])["clientes"]
        ahora = datos["reglas"].set_index(["codigo", "tipo"])
        dif = ahora["clientes"].sub(antes, fill_value=0)
        for clave, d in dif.sort_values(ascending=False).items():
            if d >= 0.02 * total and clave in ahora.index:
                out.append({"texto": f"La regla «{ahora.loc[clave, 'regla']}» excluye **{n(d)}** clientes más que en «{etq}»."})
                break
    return out[:4]


def optimalidad(cfg: Config, info: dict) -> dict:
    """Que se puede afirmar, con honestidad, sobre la calidad del reparto de cupos."""
    pr, asg = cfg.priorizacion, cfg.asignacion
    metrica_reto = pr.alpha == 0 and pr.peso_modelo == 1 and pr.peso_valor == 1 and asg.criterio_canal == "score_canal"
    if info.get("algoritmo") != "optimo":
        return {"estado": "heuristica", "titulo": "Reparto codicioso",
                "texto": "Reparto por orden de puntaje (la línea base del reto). No garantiza el máximo."}
    if not info.get("lp_entero"):
        return {"estado": "aproximado", "titulo": "Reparto casi óptimo",
                "texto": "El problema relajado dio clientes fraccionados y se redondeó; la pérdida es mínima."}
    if metrica_reto:
        return {"estado": "optimo", "titulo": "Reparto óptimo verificado",
                "texto": "La solución exacta del problema relajado resultó entera: ningún reparto de cupos da más valor esperado."}
    return {"estado": "optimo_configurado", "titulo": "Óptimo para la prioridad configurada",
            "texto": "El reparto es óptimo para la utilidad configurada, que ya no coincide con la métrica del reto."}


def tablero_vigente() -> dict:
    ruta, mt = _exigir_base()
    cfg = cargar_vigente()
    cj = cfg.model_dump_json()
    with _candado:
        r = _ejecutar(cj, ruta, mt)
        m = r["m"]
        v = _validar_corrida(cj, ruta, mt)
        base_cfg = cfg.model_copy(deep=True)
        base_cfg.asignacion.algoritmo = "codicioso"
        base_cfg.priorizacion.alpha = 0.0
        base_cfg.priorizacion.peso_modelo = base_cfg.priorizacion.peso_valor = 1.0
        mb = _ejecutar(base_cfg.model_dump_json(), ruta, mt)["m"]
        datos = _datos_tablero(cj, ruta, mt)
        ant = version_anterior(cfg)
        prev = None
        if ant:
            pj = ant[1].model_dump_json()
            prev = (ant[0], _ejecutar(pj, ruta, mt)["m"], _datos_tablero(pj, ruta, mt))
    mejora = 100 * (m["valor_esperado"] - mb["valor_esperado"]) / max(1e-9, mb["valor_esperado"])
    cupos = [{"canal": ch.id, "nombre": tablero.canal(ch.id), "usado": m["uso_canales"][ch.id], "cupo": ch.cupo}
             for ch in cfg.canales]
    precio = r["asg"].info.get("precio_sombra", {})
    notas = [f"**{tablero.canal(c['canal'])}** está lleno: cada 100 cupos adicionales sumarían ≈ {n(100 * (precio.get(c['canal'], 0) or 0), 1)} de valor esperado."
             for c in cupos if c["usado"] >= c["cupo"] and (precio.get(c["canal"], 0) or 0) > 0]
    cupo_sin = next((c for c in datos["casos"] if c["nombre"] == CATEGORIAS["Sin accion: sin cupo"]), None)
    return limpio({
        "estado": {"violaciones_total": v["violaciones_total"], "violaciones": v["violaciones"],
                   "configuracion": nombre_configuracion(cfg), "algoritmo": cfg.asignacion.algoritmo, "mejora_pct": mejora},
        "metricas": _metricas_publicas(m), "baseline": _metricas_publicas(mb),
        "anterior": {"etiqueta": prev[0], "metricas": _metricas_publicas(prev[1])} if prev else None,
        "alertas": _alertas(m, datos, cfg, prev, len(r["df"]), cupo_sin),
        "cupos": cupos, "notas_cupo": notas,
        "embudo": [{"nombre": a, "cantidad": b, "motivo": c} for a, b, c in datos["etapas"]],
        "composicion": datos["composicion"], "canales": [{"id": ch.id, "nombre": tablero.canal(ch.id)} for ch in cfg.canales],
        "campanas": [c.nombre for c in cfg.campanas_vigentes()],
        "reglas": datos["reglas"], "total": len(r["df"]), "casos": datos["casos"],
        "optimalidad": optimalidad(cfg, r["asg"].info),
        "precios_sombra": {c["canal"]: float(precio.get(c["canal"], 0) or 0) for c in cupos},
        "parametros": {"algoritmo": cfg.asignacion.algoritmo, "alpha": cfg.priorizacion.alpha,
                       "peso_modelo": cfg.priorizacion.peso_modelo, "peso_valor": cfg.priorizacion.peso_valor}})


# ------------------------------------------------------------------ impacto y aplicar
def _validar_config(d: dict) -> Config:
    try:
        return Config.model_validate(d)
    except Exception as e:
        raise ErrorNegocio("El borrador no es válido.", describir_error(e))


def impacto(d: dict) -> dict:
    ruta, mt = _exigir_base()
    borrador = _validar_config(d)
    vigente = cargar_vigente()
    try:
        with _candado:
            A = _ejecutar(vigente.model_dump_json(), ruta, mt)
            B = _ejecutar(borrador.model_dump_json(), ruta, mt)
            vb = _validar_corrida(borrador.model_dump_json(), ruta, mt)
    except (ConfigError, KeyError, ValueError) as e:
        raise ErrorNegocio(f"No se pudo calcular: {e}")
    c = comparar.comparar(A["df"]["id_cliente"].to_numpy(), (A["cand"], A["asg"], A["m"]), (B["cand"], B["asg"], B["m"]))
    return limpio({"comparacion": c, "antes": _metricas_publicas(A["m"]), "despues": _metricas_publicas(B["m"]),
                   "validacion": vb})


def aplicar(d: dict, etiqueta: str) -> dict:
    ruta, mt = _exigir_base()
    borrador = _validar_config(d)
    with _candado:
        B = _ejecutar(borrador.model_dump_json(), ruta, mt)
        vb = _validar_corrida(borrador.model_dump_json(), ruta, mt)
    if vb["violaciones_total"]:
        raise ErrorNegocio(f"El cambio produce {vb['violaciones_total']} violaciones y no se puede aplicar.",
                           [{"campo": k, "mensaje": str(v)} for k, v in vb["violaciones"].items()])
    nombre = versiones.guardar_version(borrador, config_dir(), etiqueta or "Ajuste de configuración",
                                       {k: B["m"][k] for k in METRICAS_CLAVE})
    return {"version": nombre, "config": borrador.model_dump(mode="json")}


# ------------------------------------------------------------------ versiones
def listar_versiones() -> list:
    return limpio(versiones.listar(config_dir()))


def cargar_version(nombre: str) -> dict:
    if "/" in nombre or ".." in nombre:
        raise ErrorNegocio("Versión no válida.")
    try:
        return versiones.cargar_version(nombre, config_dir()).model_dump(mode="json")
    except Exception as e:
        raise ErrorNegocio("No se pudo abrir esa versión.", describir_error(e), codigo=404)


# ------------------------------------------------------------------ cliente
def situaciones() -> list:
    ruta, mt = _exigir_base()
    cfg = cargar_vigente()
    ex = explicador(cfg.model_dump_json(), ruta, mt)
    cats = pd.Series(ex.categorias()).value_counts()
    return [{"clave": k, "cantidad": int(c)} for k, c in cats.items()]


def clientes_de(situacion: str, limite: int = 300) -> list:
    ruta, mt = _exigir_base()
    ex = explicador(cargar_vigente().model_dump_json(), ruta, mt)
    cats = ex.categorias()
    ids = ex.ids if not situacion else ex.ids[cats == situacion]
    return [str(x) for x in ids[:limite]]


def cliente(cid: str) -> dict:
    ruta, mt = _exigir_base()
    ex = explicador(cargar_vigente().model_dump_json(), ruta, mt)
    pos = np.where(ex.ids == cid)[0]
    if not len(pos):
        raise ErrorNegocio("No se encontró ese cliente.", codigo=404)
    reg = ex.registro(int(pos[0]))
    return limpio({"registro": reg, "frase_asesor": ex.frase_asesor(reg), "frase": ex.frase(reg),
                   "datos": _datos_cliente(int(pos[0]), ruta, mt)})


def _datos_cliente(i: int, ruta, mt) -> list:
    """Atributos del cliente que usan las reglas y los puntajes, con la regla que los mira (para leer la decision)."""
    cfg = cargar_vigente()
    df = cargar_df(ruta, mt)
    usadas = {}
    for r in cfg.reglas:
        if r.activa:
            usadas.setdefault(r.atributo, []).append(r.id)
    cols = list(usadas) + [c.columna_score for c in cfg.campanas] + [c.columna_score for c in cfg.canales]
    vistos, out = set(), []
    for c in cols:
        if c in df.columns and c not in vistos:
            vistos.add(c)
            out.append({"columna": c, "valor": df.iloc[i][c], "reglas": usadas.get(c, [])})
    return out


# ------------------------------------------------------------------ base de datos
def info_base() -> dict:
    ruta = ruta_activa()
    locales = sorted(str(p) for p in (ROOT / "data").glob("*.csv")) + sorted(str(p) for p in (ROOT / "data").glob("*/*.csv"))
    out = {"ruta": ruta, "existe": Path(ruta).is_file(), "disponibles": locales}
    if not out["existe"]:
        return out
    df = cargar_df(ruta, _mtime(ruta))
    try:
        cfg = config.cargar(config_dir())
        req = {"id_cliente", cfg.politica_contacto.columna_contactos_semana}
        req |= {c.columna_score for c in cfg.campanas} | {c.columna_score for c in cfg.canales}
        req |= {r.atributo for r in cfg.reglas if r.activa}
    except Exception:
        req = set()
    out.update({"calidad": _calidad(df), "filas": len(df), "columnas": len(df.columns),
                "ids_unicos": bool("id_cliente" in df.columns and df["id_cliente"].is_unique),
                "faltan": sorted(req - set(df.columns)),
                "perfil": [{"columna": c, "tipo": str(t), "vacios": int(df[c].isna().sum()), "usada": c in req,
                            "min": float(df[c].min()) if pd.api.types.is_numeric_dtype(df[c]) else None,
                            "max": float(df[c].max()) if pd.api.types.is_numeric_dtype(df[c]) else None}
                           for c, t in zip(df.columns, df.dtypes)],
                "vista_previa": limpio(df.head(50))})
    return out


def _calidad(df: pd.DataFrame) -> list:
    """Chequeos de calidad de la base que importan al motor."""
    checks = []
    dup = int(df["id_cliente"].duplicated().sum()) if "id_cliente" in df.columns else None
    checks.append({"ok": dup == 0, "titulo": "Identificadores únicos",
                   "detalle": "Cada cliente aparece una sola vez." if dup == 0 else f"{n(dup)} ids repetidos." if dup else "Falta la columna id_cliente."})
    cols_prob = [c for c in df.columns if c.startswith("score_")] + [c for c in ("riesgo_churn",) if c in df.columns]
    fuera = {c: int(((df[c] < 0) | (df[c] > 1)).sum()) for c in cols_prob}
    malos = {c: v for c, v in fuera.items() if v}
    checks.append({"ok": not malos, "titulo": "Puntajes y probabilidades entre 0 y 1",
                   "detalle": f"{len(cols_prob)} columnas revisadas, todas en rango." if not malos
                   else "; ".join(f"{c}: {n(v)} filas fuera de rango" for c, v in malos.items())})
    try:
        cfg = config.cargar(config_dir())
        validos = {"productos_ofertados_mes": {c.producto for c in cfg.campanas}, "canales_contactados_mes": {c.id for c in cfg.canales}}
    except Exception:
        validos = {}
    for col, ok_set in validos.items():
        if col not in df.columns:
            continue
        toks = df[col].dropna().astype(str).str.split("|").explode()
        malos_t = toks[~toks.isin(ok_set)]
        checks.append({"ok": malos_t.empty, "titulo": f"Formato de {col} (valores separados por |)",
                       "detalle": "Todos los valores son reconocidos." if malos_t.empty
                       else f"{n(len(malos_t))} valores no reconocidos, por ejemplo: {', '.join(sorted(set(malos_t))[:4])}."})
    vac = df.isna().sum()
    vac = vac[vac > 0]
    checks.append({"ok": True, "titulo": "Columnas con vacíos",
                   "detalle": "Ninguna." if vac.empty else "; ".join(f"{c}: {n(v)}" for c, v in vac.items()) + ". Los vacíos de historial significan «sin contactos»."})
    neg = [c for c in df.select_dtypes("number").columns if c in ("edad", "antiguedad_meses", "dias_mora", "quejas_90d", "edad_equipo_meses") and (df[c] < 0).any()]
    checks.append({"ok": not neg, "titulo": "Sin valores negativos donde no corresponden",
                   "detalle": "Edad, antigüedad, mora, quejas y edad del equipo son no negativos." if not neg else "Hay negativos en: " + ", ".join(neg)})
    return checks


def usar_ruta(ruta: str) -> dict:
    if not Path(ruta).is_file():
        raise ErrorNegocio("No existe ese archivo.", codigo=404)
    _estado["ruta"] = ruta
    return info_base()


def subir_base(contenido: bytes) -> dict:
    destino = ROOT / "data" / "clientes_cargado.csv"
    destino.write_bytes(contenido)
    _estado["ruta"] = str(destino)
    return info_base()


def parrilla_csv() -> bytes:
    ruta, mt = _exigir_base()
    cfg = cargar_vigente()
    with _candado:
        g, _ = run.correr(cargar_df(ruta, mt), cfg)
    return g.to_csv(index=False).encode("utf-8")


def precalentar():
    """Calcula el tablero de la configuracion vigente para que la primera pantalla no espere."""
    try:
        if Path(ruta_activa()).is_file():
            tablero_vigente()
    except Exception:
        pass


# ------------------------------------------------------------------ diferencias entre configuraciones
def diferencias(a: Config, b: Config) -> list:
    """Frases de negocio con lo que cambia al pasar de la configuracion a a la b."""
    out = []
    ca, cb = {c.id: c for c in a.canales}, {c.id: c for c in b.canales}
    for i, c in cb.items():
        if i not in ca:
            out.append(f"Canal nuevo {tablero.canal(i)} con cupo {n(c.cupo)}")
            continue
        if c.cupo != ca[i].cupo:
            out.append(f"Cupo de {tablero.canal(i)}: {n(ca[i].cupo)} → {n(c.cupo)}")
        if c.max_productos != ca[i].max_productos:
            out.append(f"Productos por contacto en {tablero.canal(i)}: {ca[i].max_productos} → {c.max_productos}")
    out += [f"Canal eliminado {tablero.canal(i)}" for i in ca if i not in cb]
    pa, pb = {c.id: c for c in a.campanas}, {c.id: c for c in b.campanas}
    for i, c in pb.items():
        if i not in pa:
            out.append(f"Campaña nueva {c.nombre}")
            continue
        o = pa[i]
        if c.activa != o.activa:
            out.append(f"{c.nombre}: {'activada' if c.activa else 'pausada'}")
        if c.valor_negocio != o.valor_negocio:
            out.append(f"{c.nombre}: valor de negocio {o.valor_negocio} → {c.valor_negocio}")
        if c.canales_permitidos != o.canales_permitidos:
            out.append(f"{c.nombre}: canales {'|'.join(o.canales_permitidos)} → {'|'.join(c.canales_permitidos)}")
        if (c.vigencia_inicio, c.vigencia_fin) != (o.vigencia_inicio, o.vigencia_fin):
            out.append(f"{c.nombre}: cambia su vigencia")
    out += [f"Campaña eliminada {pa[i].nombre}" for i in pa if i not in pb]
    ra, rb = {r.id: r for r in a.reglas}, {r.id: r for r in b.reglas}
    for i, r in rb.items():
        if i not in ra:
            out.append(f"Regla nueva {i}: {r.nombre}")
            continue
        o = ra[i]
        if r.activa != o.activa:
            out.append(f"Regla {i} ({r.nombre}): {'activada' if r.activa else 'pausada'}")
        elif (r.atributo, r.operador, r.valor, r.alcance_nivel, r.alcance_valores, r.tipo) != (o.atributo, o.operador, o.valor, o.alcance_nivel, o.alcance_valores, o.tipo):
            out.append(f"Regla {i} ({r.nombre}) modificada: {frase_regla(r)}")
    out += [f"Regla eliminada {i}: {ra[i].nombre}" for i in ra if i not in rb]
    esc = [("Probabilidad mínima de compra", lambda c: c.priorizacion.umbral_score_producto),
           ("Probabilidad mínima de respuesta", lambda c: c.asignacion.umbral_score_canal),
           ("Máximo de contactos por semana", lambda c: c.politica_contacto.max_contactos_semana),
           ("Algoritmo", lambda c: c.asignacion.algoritmo), ("Criterio de canal", lambda c: c.asignacion.criterio_canal),
           ("Orden de preferencia de canales", lambda c: "|".join(c.asignacion.orden_preferencia)),
           ("α (jerarquía)", lambda c: c.priorizacion.alpha), ("Peso del modelo", lambda c: c.priorizacion.peso_modelo),
           ("Peso del valor", lambda c: c.priorizacion.peso_valor), ("Prioridad de campañas", lambda c: " > ".join(c.priorizacion.jerarquia)),
           ("Desempate", lambda c: "|".join(c.priorizacion.desempate)), ("Modo", lambda c: c.priorizacion.modo)]
    for et, f in esc:
        if f(a) != f(b):
            out.append(f"{et}: {f(a)} → {f(b)}")
    if a.priorizacion.pesos != b.priorizacion.pesos:
        out.append("Pesos del baseline modificados")
    return out


# ------------------------------------------------------------------ escenarios guardados
def _carpeta_escenarios() -> Path:
    return Path(config_dir()) / "escenarios"


def _id_valido(i: str):
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}_[A-Za-z0-9-]*", i):
        raise ErrorNegocio("Escenario no válido.", codigo=404)


def guardar_escenario(nombre: str, d: dict) -> dict:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ErrorNegocio("Ponle un nombre al escenario.")
    cfg = _validar_config(d)
    carpeta = _carpeta_escenarios()
    carpeta.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", nombre)[:40].strip("-")
    eid = datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + slug
    (carpeta / f"{eid}.json").write_text(json.dumps(
        {"nombre": nombre, "fecha": datetime.now().isoformat(timespec="seconds"), "config": cfg.model_dump(mode="json")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": eid, "nombre": nombre}


def listar_escenarios() -> list:
    carpeta = _carpeta_escenarios()
    if not carpeta.exists():
        return []
    try:
        vigente = cargar_vigente()
    except ErrorNegocio:
        vigente = None
    out = []
    for f in sorted(carpeta.glob("*.json"), reverse=True):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            cfg = Config.model_validate(j["config"])
        except Exception:
            continue
        out.append({"id": f.stem, "nombre": j["nombre"], "fecha": j["fecha"],
                    "cambios": diferencias(vigente, cfg) if vigente else []})
    return out


def cargar_escenario(eid: str) -> dict:
    _id_valido(eid)
    f = _carpeta_escenarios() / f"{eid}.json"
    if not f.is_file():
        raise ErrorNegocio("No existe ese escenario.", codigo=404)
    return json.loads(f.read_text(encoding="utf-8"))["config"]


def borrar_escenario(eid: str) -> dict:
    _id_valido(eid)
    f = _carpeta_escenarios() / f"{eid}.json"
    if not f.is_file():
        raise ErrorNegocio("No existe ese escenario.", codigo=404)
    f.unlink()
    return {"borrado": eid}


# ------------------------------------------------------------------ trabajos en segundo plano (el motor tarda ~12 s por corrida)
_trabajos: dict = {}


def _lanzar(total: int, tarea) -> str:
    tid = uuid.uuid4().hex[:10]
    estado_ = {"estado": "corriendo", "hecho": 0, "total": total, "parcial": [], "resultado": None, "error": None}
    _trabajos[tid] = estado_

    def correr():
        try:
            tarea(estado_)
            estado_["estado"] = "listo"
        except ErrorNegocio as e:
            estado_["estado"], estado_["error"] = "error", e.mensaje
        except Exception as e:                        # un fallo del motor no debe dejar el trabajo colgado
            estado_["estado"], estado_["error"] = "error", f"No se pudo calcular: {e}"

    threading.Thread(target=correr, daemon=True).start()
    return tid


def estado_trabajo(tid: str) -> dict:
    if tid not in _trabajos:
        raise ErrorNegocio("No existe ese trabajo.", codigo=404)
    return limpio(_trabajos[tid])


def comparar_escenarios(ids: list) -> dict:
    ruta, mt = _exigir_base()
    vigente = cargar_vigente()
    items = [("vigente", "Configuración vigente", vigente)]
    for i in ids:
        j = cargar_escenario(i)
        nombre = next((e["nombre"] for e in listar_escenarios() if e["id"] == i), i)
        items.append((i, nombre, Config.model_validate(j)))

    def tarea(est):
        for eid, nombre, cfg in items:
            cj = cfg.model_dump_json()
            with _candado:
                m = _ejecutar(cj, ruta, mt)["m"]
                v = _validar_corrida(cj, ruta, mt)
            est["parcial"].append(limpio({"id": eid, "nombre": nombre, "metricas": _metricas_publicas(m),
                                          "violaciones_total": v["violaciones_total"], "violaciones": v["violaciones"],
                                          "cambios": [] if eid == "vigente" else diferencias(vigente, cfg)}))
            est["hecho"] += 1

    return {"trabajo": _lanzar(len(items), tarea)}


# ------------------------------------------------------------------ sensibilidad de un cupo
FACTORES = (0.5, 0.75, 1.0, 1.5, 2.0)
_cache_sens: dict = {}


def sensibilidad(canal: str, factores=FACTORES) -> dict:
    """Valor esperado al subir o bajar el cupo de un canal. Solo cambia el reparto, asi que se reutilizan los candidatos."""
    ruta, mt = _exigir_base()
    cfg = cargar_vigente()
    if canal not in {c.id for c in cfg.canales}:
        raise ErrorNegocio(f"No existe el canal {canal}.", codigo=404)
    cj = cfg.model_dump_json()
    clave = (cj, ruta, mt, canal, tuple(factores))
    base = _ejecutar_seguro(cj, ruta, mt)
    m0 = base["m"]
    cupo0 = next(c.cupo for c in cfg.canales if c.id == canal)
    usado = m0["uso_canales"][canal]
    lleno = usado >= cupo0
    precio = float(base["asg"].info.get("precio_sombra", {}).get(canal, 0) or 0)

    def tarea(est):
        est["resultado"] = {"canal": canal, "cupo_actual": cupo0, "usado": usado, "precio_sombra": precio, "valor_actual": m0["valor_esperado"]}
        for f in sorted(factores):
            nuevo = int(round(cupo0 * f))
            if f == 1.0:
                valor, calc = m0["valor_esperado"], False
            elif not lleno and nuevo >= usado:
                valor, calc = m0["valor_esperado"], False       # el canal no esta lleno: el optimo no cambia
            else:
                cfg2 = cfg.model_copy(deep=True)
                for ch in cfg2.canales:
                    if ch.id == canal:
                        ch.cupo = nuevo
                cand2 = copy.copy(base["cand"])
                cand2.canales = [ch.model_copy(update={"cupo": nuevo}) if ch.id == canal else ch for ch in base["cand"].canales]
                with _candado:
                    asg = asignacion.asignar(cand2, cfg2)
                    valor, calc = comparar.metricas(cand2, base["el"], asg, cfg2)["valor_esperado"], True
            est["parcial"].append({"factor": f, "cupo": nuevo, "valor": valor, "calculado": calc})
            est["hecho"] += 1

    if clave in _cache_sens and _cache_sens[clave]["estado"] != "error":
        tid = uuid.uuid4().hex[:10]
        _trabajos[tid] = _cache_sens[clave]
        return {"trabajo": tid}
    tid = _lanzar(len(factores), tarea)
    _cache_sens[clave] = _trabajos[tid]
    return {"trabajo": tid}


def _ejecutar_seguro(cj, ruta, mt):
    with _candado:
        return _ejecutar(cj, ruta, mt)
