"""Consola de negocio del orquestador NBA.  Ejecutar:  .venv/bin/streamlit run app/consola.py"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import numpy as np
import pandas as pd
import streamlit as st

from nba import comparar, config, run, validar, versiones
from nba.config import Config, ConfigError
from nba.explicar import Explicador
from nba.reglas import frase as frase_regla
import tablero

CONFIG_DIR = os.environ.get("NBA_CONFIG_DIR", str(ROOT / "config"))
DTYPES = {"canales_contactados_mes": str, "productos_ofertados_mes": str}
OPERADORES = config.OPERADORES
# Columnas a las que se atan los controles directos (la regla subyacente sigue siendo una regla comun)
COL_CALIF, ORDEN_CALIF = "calificacion_riesgo", ["E", "A", "B", "C", "P"]
COL_LLAMADAS = "contactos_asesor_mes"

st.set_page_config(page_title="Orquestador NBA", page_icon=":material/hub:", layout="wide")


# ------------------------------------------------------------------ datos y motor (cacheados)
@st.cache_data(show_spinner="Cargando base de clientes...")
def cargar_df(ruta, mtime):
    return pd.read_csv(ruta, dtype=DTYPES)


@st.cache_resource(show_spinner="Calculando parrilla...", max_entries=4)
def ejecutar(cfg_json, ruta, mtime):
    cfg = Config.model_validate_json(cfg_json)
    df = cargar_df(ruta, mtime)
    el, cand, asg = comparar.nucleo(df, cfg)
    m = comparar.metricas(cand, el, asg, cfg)
    return {"cfg": cfg, "df": df, "el": el, "cand": cand, "asg": asg, "m": m}


@st.cache_data(show_spinner="Validando restricciones...", max_entries=6)
def validar_corrida(cfg_json, ruta, mtime):
    r = ejecutar(cfg_json, ruta, mtime)
    g = comparar.parrilla_ligera(r["df"], r["cfg"], r["el"], r["cand"], r["asg"])
    v = validar.validar(g, r["df"], r["cfg"])
    return {k: v[k] for k in ("violaciones_total", "violaciones", "ejemplos")}


def resumen_corrida(cfg_json, ruta, mtime):
    r = ejecutar(cfg_json, ruta, mtime)
    ex = Explicador(r["df"], r["cfg"], r["el"], r["cand"], r["asg"])
    return r, ex


# ------------------------------------------------------------------ conversiones tabla <-> config
def describir_error(e) -> list:
    """Lista de (campo, explicacion) legible para negocio, a partir de una excepcion de configuracion."""
    from pydantic import ValidationError
    if isinstance(e, ValidationError):
        return [(".".join(str(p) for p in x["loc"]) or "(general)", x["msg"].replace("Value error, ", ""))
                for x in e.errors()]
    return [("configuración", str(e))]


def mostrar_errores(errores):
    for campo, msg in errores:
        st.markdown(f"- **{campo}**: {msg}")


def pantalla_configuracion_invalida(e):
    """La configuracion guardada no se puede cargar: explicar que falla y ofrecer restaurar la inicial."""
    inicial = ROOT / "config_inicial"
    st.header("La configuración guardada no es válida")
    st.error("La consola no puede abrir la configuración vigente porque algún valor no cumple las reglas del reto.")
    st.markdown("**Qué falla:**")
    mostrar_errores(describir_error(e))
    st.caption(f"Carpeta de configuración: `{CONFIG_DIR}`")
    if not inicial.exists():
        st.warning("No encuentro la carpeta `config_inicial/` para restaurar. Corrige los archivos a mano.")
        st.stop()
    st.markdown("Puedes **restaurar la configuración inicial del reto**. Antes de reemplazarla, la configuración actual "
                "se guarda como respaldo en `respaldo/` dentro de la carpeta de configuración.")
    if st.button("Restaurar la configuración inicial", type="primary"):
        base = Path(CONFIG_DIR)
        respaldo = base / "respaldo" / (datetime.now().strftime("%Y%m%d-%H%M%S") + "_invalida")
        respaldo.mkdir(parents=True, exist_ok=True)
        for a in versiones.ARCHIVOS:
            if (base / a).exists():
                shutil.copy(base / a, respaldo / a)
            shutil.copy(inicial / a, base / a)
        st.session_state.pop("vigente", None)
        st.rerun()
    st.stop()


def _lista(s):
    return [x.strip() for x in str(s or "").replace(",", "|").split("|") if x.strip()]


def _valor_a_texto(v):
    return "|".join(map(str, v)) if isinstance(v, list) else str(v)


def _texto_a_valor(txt, operador):
    if operador in ("en", "no_en"):
        return [x.strip() for x in str(txt).split("|") if x.strip()]
    t = str(txt).strip()
    try:
        f = float(t)
        return int(f) if f.is_integer() else f
    except ValueError:
        return t


def _es_regla_llamadas(r):
    return (r.tipo == "canal" and r.alcance_nivel == "canal" and r.alcance_valores == ["asesor"]
            and r.atributo == COL_LLAMADAS and r.operador == ">=")


def _es_regla_calif(r, camp=None):
    return (r.tipo == "elegibilidad" and r.alcance_nivel == "campana" and len(r.alcance_valores) == 1
            and r.atributo == COL_CALIF and r.operador in ("en", "no_en")
            and (camp is None or r.alcance_valores[0] == camp))


def calificaciones_por_campana(cfg: Config):
    """campana -> calificaciones permitidas, inferidas de las reglas de calificacion de esa campana."""
    res = {c.id: list(ORDEN_CALIF) for c in cfg.campanas}
    for r in cfg.reglas:
        if r.activa and _es_regla_calif(r) and r.alcance_valores[0] in res:
            vals = [str(v) for v in r.valor]
            permitidas = [o for o in ORDEN_CALIF if (o not in vals if r.operador == "en" else o in vals)]
            res[r.alcance_valores[0]] = [o for o in res[r.alcance_valores[0]] if o in permitidas]
    return res


def tablas_desde_config(cfg: Config):
    niv = list(cfg.nivel_jerarquia().items())
    pos = {cid: i + 1 for i, (cid, _) in enumerate(sorted(niv, key=lambda x: -x[1]))}
    camp = pd.DataFrame([{
        "activa": c.activa, "id": c.id, "nombre": c.nombre, "producto": c.producto, "objetivo": c.objetivo,
        "columna_score": c.columna_score,
        "valor_negocio": c.valor_negocio, "canales_permitidos": "|".join(c.canales_permitidos),
        "vigencia_inicio": c.vigencia_inicio, "vigencia_fin": c.vigencia_fin, "posicion_jerarquia": pos[c.id]}
        for c in cfg.campanas])
    reg = pd.DataFrame([{
        "activa": r.activa, "id": r.id, "nombre": r.nombre, "tipo": r.tipo, "alcance_nivel": r.alcance_nivel,
        "alcance_valores": "|".join(r.alcance_valores), "atributo": r.atributo, "operador": r.operador,
        "valor": _valor_a_texto(r.valor)} for r in cfg.reglas])
    can = pd.DataFrame([{"id": c.id, "columna_score": c.columna_score, "cupo": c.cupo, "max_productos": c.max_productos}
                        for c in cfg.canales])
    return {"campanas": camp, "reglas": reg, "canales": can}


def iniciar_borrador(cfg: Config):
    st.session_state.vigente = cfg
    st.session_state.tablas = tablas_desde_config(cfg)
    st.session_state.ver = st.session_state.get("ver", 0) + 1
    st.session_state.impacto = None
    for k in [k for k in st.session_state if str(k).startswith("p_cal_")]:
        del st.session_state[k]
    st.session_state.cal_inicial = calificaciones_por_campana(cfg)
    rl = next((r for r in cfg.reglas if _es_regla_llamadas(r)), None)
    st.session_state.llamadas_ok = rl is not None
    for k, v in {"llamadas": int(rl.valor) if rl is not None else 2,"u_prod": cfg.priorizacion.umbral_score_producto, "u_canal": cfg.asignacion.umbral_score_canal,
                 "tope_sem": cfg.politica_contacto.max_contactos_semana, "alpha": cfg.priorizacion.alpha,
                 "algoritmo": cfg.asignacion.algoritmo, "modo": cfg.priorizacion.modo,
                 "peso_modelo": cfg.priorizacion.peso_modelo, "peso_valor": cfg.priorizacion.peso_valor,
                 "desempate": "|".join(cfg.priorizacion.desempate), "criterio_canal": cfg.asignacion.criterio_canal,
                 "orden_pref": "|".join(cfg.asignacion.orden_preferencia),
                 "w_score": cfg.priorizacion.pesos.score_producto, "w_valor": cfg.priorizacion.pesos.valor_negocio,
                 "w_jer": cfg.priorizacion.pesos.jerarquia, "fecha": cfg.fecha_corrida}.items():
        st.session_state[f"p_{k}"] = v


def programar_reinicio(cfg: Config, mensaje=None, pagina=None):
    """Streamlit no deja modificar controles ya dibujados: se reinicia el borrador al comienzo de la siguiente ejecucion."""
    st.session_state._reiniciar = (cfg, mensaje, pagina)
    st.rerun()


def _fecha(x):
    if x is None or (isinstance(x, float) and x != x) or x is pd.NaT:
        return None
    return pd.to_datetime(x).date().isoformat()


def construir_borrador(tablas) -> Config:
    ss = st.session_state
    camp = tablas["campanas"].dropna(subset=["id"])
    camp = camp[camp["id"].astype(str).str.strip() != ""]
    campanas = [dict(id=str(r.id).strip(), nombre=str(r.nombre or r.id), producto=str(r.producto or r.id),
                     objetivo=str(r.objetivo) if pd.notna(r.objetivo) else "",
                     columna_score=str(r.columna_score), valor_negocio=float(r.valor_negocio),
                     canales_permitidos=_lista(r.canales_permitidos), vigencia_inicio=_fecha(r.vigencia_inicio),
                     vigencia_fin=_fecha(r.vigencia_fin), activa=bool(r.activa)) for r in camp.itertuples()]
    pos = {str(r.id).strip(): (r.posicion_jerarquia if pd.notna(r.posicion_jerarquia) else 999) for r in camp.itertuples()}
    reg = tablas["reglas"].dropna(subset=["id"])
    reglas = [dict(id=str(r.id).strip(), nombre=str(r.nombre), tipo=r.tipo, alcance_nivel=r.alcance_nivel,
                   alcance_valores=_lista(r.alcance_valores), atributo=str(r.atributo), operador=r.operador,
                   valor=_texto_a_valor(r.valor, r.operador), activa=bool(r.activa))
              for r in reg.itertuples() if str(r.id).strip()]
    # control directo: tope de llamadas de asesor al mes
    if ss.get("llamadas_ok"):
        for r in reglas:
            if r["tipo"] == "canal" and r["alcance_nivel"] == "canal" and r["alcance_valores"] == ["asesor"] \
                    and r["atributo"] == COL_LLAMADAS and r["operador"] == ">=":
                r["valor"] = int(ss.p_llamadas)
    # control directo: calificaciones permitidas por campana (solo si el usuario las cambio)
    for c in campanas:
        sel = ss.get(f"p_cal_{c['id']}")
        if sel is None or set(sel) == set(ss.cal_inicial.get(c["id"], ORDEN_CALIF)):
            continue
        previas = [r for r in reglas if r["tipo"] == "elegibilidad" and r["alcance_nivel"] == "campana"
                   and r["alcance_valores"] == [c["id"]] and r["atributo"] == COL_CALIF and r["operador"] in ("en", "no_en")]
        rid = previas[0]["id"] if previas else f"CAL-{c['id']}"
        reglas = [r for r in reglas if r not in previas]
        if set(sel) != set(ORDEN_CALIF):
            reglas.append(dict(id=rid, nombre=f"{c['nombre']}: solo con calificacion {', '.join(sel) or 'ninguna'}",
                               tipo="elegibilidad", alcance_nivel="campana", alcance_valores=[c["id"]],
                               atributo=COL_CALIF, operador="no_en", valor=list(sel), activa=True))
    can = tablas["canales"].dropna(subset=["id"])
    canales = [dict(id=str(r.id).strip(), columna_score=str(r.columna_score), cupo=int(r.cupo),
                    max_productos=int(r.max_productos)) for r in can.itertuples() if str(r.id).strip()]
    base = ss.vigente
    suma_pesos = ss.p_w_score + ss.p_w_valor + ss.p_w_jer
    if suma_pesos <= 0:
        raise ValueError("los pesos del baseline no pueden ser todos cero (deben sumar 1)")
    return Config(
        fecha_corrida=ss.p_fecha, campanas=campanas, reglas=reglas, canales=canales,
        priorizacion=dict(modo=ss.p_modo, jerarquia=sorted(pos, key=pos.get),
                          pesos=dict(score_producto=ss.p_w_score / suma_pesos, valor_negocio=ss.p_w_valor / suma_pesos,
                                     jerarquia=ss.p_w_jer / suma_pesos),
                          umbral_score_producto=ss.p_u_prod, alpha=ss.p_alpha, desempate=_lista(ss.p_desempate),
                          peso_modelo=ss.p_peso_modelo, peso_valor=ss.p_peso_valor),
        politica_contacto=dict(max_contactos_semana=int(ss.p_tope_sem),
                               columna_contactos_semana=base.politica_contacto.columna_contactos_semana,
                               canales_por_cliente=base.politica_contacto.canales_por_cliente),
        asignacion=dict(algoritmo=ss.p_algoritmo, criterio_canal=ss.p_criterio_canal,
                        orden_preferencia=_lista(ss.p_orden_pref), umbral_score_canal=ss.p_u_canal))


# ------------------------------------------------------------------ barra lateral
CSS = """
<style>
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
[data-testid="stSidebar"] * { color: #e2e8f0; }
[data-testid="stSidebar"] .marca { padding: 4px 4px 14px 4px; border-bottom: 1px solid #334155; margin-bottom: 14px; }
[data-testid="stSidebar"] .marca b { font-size: 1.25rem; letter-spacing: .3px; color: #ffffff; }
[data-testid="stSidebar"] .marca span { display:block; font-size: .78rem; color: #94a3b8; margin-top: 2px; }
[data-testid="stSidebar"] .etiqueta { font-size: .68rem; letter-spacing: 1.4px; color: #64748b; margin: 14px 0 6px 6px; text-transform: uppercase; }
[data-testid="stSidebar"] [role="radiogroup"] { gap: 2px; }
[data-testid="stSidebar"] [data-baseweb="radio"] { width: 100%; padding: 9px 12px; border-radius: 8px; margin: 0; cursor: pointer;
    border-left: 3px solid transparent; transition: background .15s; }
[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child { display: none; }
[data-testid="stSidebar"] [data-baseweb="radio"]:hover { background: #334155; }
[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) { background: #1d4ed8; border-left-color: #93c5fd; }
[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) * { color: #ffffff; font-weight: 600; }
[data-testid="stSidebar"] .estado { background: #0b1220; border: 1px solid #334155; border-radius: 10px; padding: 10px 12px;
    font-size: .8rem; line-height: 1.5; }
[data-testid="stSidebar"] .estado b { color: #ffffff; }
[data-testid="stSidebar"] .estado .ok { color: #4ade80; }
</style>
"""
SECCIONES = ["Tablero", "Cambiar configuración", "Cliente", "Base de datos", "Versiones"]


def ruta_activa():
    ss = st.session_state
    if "db_ruta" not in ss:
        oficial = ROOT / "data" / "oficial" / "clientes.csv"
        ss.db_ruta = os.environ.get("NBA_CLIENTES", str(oficial if oficial.exists() else ROOT / "data" / "oficial" / "clientes.csv"))
    return ss.db_ruta


def barra_lateral():
    ss = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)
    ruta = ruta_activa()
    with st.sidebar:
        st.markdown('<div class="marca"><b>Orquestador NBA</b><span>Next Best Action configurable</span></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="etiqueta">Navegación</div>', unsafe_allow_html=True)
        pagina = st.radio("Sección", SECCIONES, label_visibility="collapsed", key="pagina")
        st.markdown('<div class="etiqueta">Estado</div>', unsafe_allow_html=True)
        p = Path(ruta)
        if p.exists():
            try:
                filas = sum(1 for _ in open(p, "rb")) - 1
            except OSError:
                filas = 0
            ver = versiones.listar(CONFIG_DIR)
            ult = ver[0]["etiqueta"] if ver else "configuración inicial"
            st.markdown(f'<div class="estado"><span class="ok">&#9679;</span> <b>Base activa</b><br>{p.name}<br>'
                        f'{filas:,} clientes<br><b>Configuración</b><br>{ult}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="estado"><b>Sin base de datos</b><br>Elige una en «Base de datos».</div>',
                        unsafe_allow_html=True)
    if not Path(ruta).exists():
        return "Base de datos", ruta, 0.0
    return pagina, ruta, Path(ruta).stat().st_mtime


# ------------------------------------------------------------------ páginas
def _cfg_inicial():
    try:
        return config.cargar(str(ROOT / "config_inicial"))
    except Exception:
        return None


def nombre_configuracion(cfg: Config) -> str:
    """Como se llama la configuracion vigente: version del historial, configuracion inicial o sin versionar."""
    actual = cfg.model_dump_json()
    for v in versiones.listar(CONFIG_DIR)[:20]:
        try:
            if versiones.cargar_version(v["version"], CONFIG_DIR).model_dump_json() == actual:
                return v["etiqueta"]
        except Exception:
            continue
    ini = _cfg_inicial()
    if ini is not None and ini.model_dump_json() == actual:
        return "configuración inicial del reto"
    return "modificada, sin versionar"


def version_anterior(cfg: Config):
    """(etiqueta, config) de la version guardada mas reciente que sea distinta de la vigente; si no hay, la inicial."""
    actual = cfg.model_dump_json()
    for v in versiones.listar(CONFIG_DIR)[:20]:
        try:
            c = versiones.cargar_version(v["version"], CONFIG_DIR)
        except Exception:
            continue
        if c.model_dump_json() != actual:
            return v["etiqueta"], c
    ini = _cfg_inicial()
    if ini is not None and ini.model_dump_json() != actual:
        return "configuración inicial del reto", ini
    return None


CATEGORIAS = {"Asignado": "Con acción asignada",
              "Asignado en canal alternativo (cupo del ideal agotado)": "Con acción, en su segundo mejor canal (cupo agotado)",
              "Sin accion: tope semanal": "Sin acción · tope semanal de contactos",
              "Sin accion: sin campana elegible": "Sin acción · sin campaña elegible",
              "Sin accion: sin canal habilitado": "Sin acción · sin canal habilitado",
              "Sin accion: sin cupo": "Sin acción · sin cupo en sus canales"}


@st.cache_data(show_spinner=False, max_entries=6)
def datos_tablero(cfg_json, ruta, mtime):
    r = ejecutar(cfg_json, ruta, mtime)
    cfg = r["cfg"]
    ex = Explicador(r["df"], cfg, r["el"], r["cand"], r["asg"])
    cat = pd.Series(ex.categorias())
    casos = {}
    for k, nombre in CATEGORIAS.items():
        idx = np.where(cat.to_numpy() == k)[0]
        if k != "Asignado" and len(idx):
            casos[nombre] = (int(len(idx)), str(ex.ids[idx[0]]))
    return {"etapas": tablero.etapas_embudo(r["el"], r["cand"], r["asg"]),
            "reglas": tablero.reglas_que_mas_excluyen(r["el"], cfg, r["cand"]),
            "composicion": tablero.composicion(r["cand"], r["asg"]),
            "casos": casos}


def _delta(valor, base, dec=1, unidad=""):
    d = valor - base
    pct = f" ({tablero.signo(100 * d / base, 1)} %)" if base else ""
    return f"{tablero.signo(d, dec, unidad)}{pct}"


def _tema():
    try:
        return "oscuro" if st.context.theme.type == "dark" else "claro"
    except Exception:
        return "claro"


def alertas(m, datos, cfg, prev, total):
    """Lineas de 'para revisar'. prev = (etiqueta, metricas, datos) de la version anterior, o None."""
    out = []
    llenos = [tablero.canal(ch.id) for ch in cfg.canales if m["uso_canales"][ch.id] >= ch.cupo]
    if llenos:
        out.append(f"<b>{' y '.join(llenos)}</b> {'está lleno' if len(llenos) == 1 else 'están llenos'}: "
                   "hay clientes que recibieron su segundo mejor canal.")
    sc = datos["casos"].get(CATEGORIAS["Sin accion: sin cupo"])
    if sc:
        out.append(f"<b>{tablero.n(sc[0])}</b> clientes quedaron sin acción por falta de cupo.")
    if prev:
        etq, mp, dp = prev
        dv = 100 * (m["valor_esperado"] - mp["valor_esperado"]) / max(1e-9, mp["valor_esperado"])
        if abs(dv) >= 1:
            out.append(f"El valor esperado cambió <b>{tablero.signo(dv, 1)} %</b> frente a «{etq}».")
        antes = dp["reglas"].set_index(["codigo", "tipo"])["clientes"]
        ahora_df = datos["reglas"].set_index(["codigo", "tipo"])
        dif = ahora_df["clientes"].sub(antes, fill_value=0)
        umbral = 0.02 * total          # un cambio de al menos 2 % de la base merece un aviso
        for clave, d in dif.sort_values(ascending=False).items():
            if d >= umbral and clave in ahora_df.index:
                out.append(f"La regla «{ahora_df.loc[clave, 'regla']}» excluye <b>{tablero.n(d)}</b> clientes más que en «{etq}».")
                break
    return out[:4]


def pagina_tablero(ruta, mt):
    ss = st.session_state
    cfg = ss.vigente
    cj = cfg.model_dump_json()
    r, ex = resumen_corrida(cj, ruta, mt)
    m = r["m"]
    v = validar_corrida(cj, ruta, mt)
    cfg_base = cfg.model_copy(deep=True)
    cfg_base.asignacion.algoritmo = "codicioso"
    cfg_base.priorizacion.alpha = 0.0
    cfg_base.priorizacion.peso_modelo = cfg_base.priorizacion.peso_valor = 1.0
    mb = ejecutar(cfg_base.model_dump_json(), ruta, mt)["m"]
    mejora = 100 * (m["valor_esperado"] - mb["valor_esperado"]) / max(1e-9, mb["valor_esperado"])
    datos = datos_tablero(cj, ruta, mt)
    ant = version_anterior(cfg)

    st.markdown(tablero.CSS, unsafe_allow_html=True)
    st.header("Tablero")
    st.markdown(tablero.franja_estado(v["violaciones_total"], nombre_configuracion(cfg), cfg.asignacion.algoritmo, mejora,
                                      v["violaciones"] if v["violaciones_total"] else None), unsafe_allow_html=True)

    # --- comparacion: baseline o version anterior del historial
    ref_nombre, mref = "baseline", mb
    prev = None
    if ant:
        pj = ant[1].model_dump_json()
        prev = (ant[0], ejecutar(pj, ruta, mt)["m"], datos_tablero(pj, ruta, mt))
        opcion = st.radio("Comparar con", ["Baseline", f"Versión anterior · {ant[0]}"], horizontal=True, key="comparar_con")
        if opcion.startswith("Versión"):
            ref_nombre, mref = f"«{ant[0]}»", prev[1]

    k = st.columns(4)
    with k[0].container(border=True):
        st.metric("Valor esperado", tablero.n(m["valor_esperado"], 1), _delta(m["valor_esperado"], mref["valor_esperado"]),
                  help="Suma de prob. de compra × prob. del canal × valor de negocio.")
    with k[1].container(border=True):
        st.metric("Clientes con acción", tablero.n(m["clientes_con_accion"]),
                  _delta(m["clientes_con_accion"], mref["clientes_con_accion"], 0))
    with k[2].container(border=True):
        st.metric("Productos asignados", tablero.n(m["productos_asignados"]),
                  _delta(m["productos_asignados"], mref["productos_asignados"], 0))
    with k[3].container(border=True):
        st.metric("Jerarquía respetada", f"{tablero.n(m['jerarquia_pct'], 2)} %",
                  f"{tablero.signo(m['jerarquia_pct'] - mref['jerarquia_pct'], 2)} pp",
                  help="% de clientes con acción que recibieron su producto elegible de mayor jerarquía.")
    st.caption(f"Variaciones frente a {ref_nombre}.")

    avisos = alertas(m, datos, cfg, prev, len(r["df"]))
    if avisos:
        st.markdown('<div class="nba-sec">Para revisar</div>' + tablero.alertas_html(avisos), unsafe_allow_html=True)

    izq, der = st.columns(2, gap="large")
    with izq.container(border=True):
        st.markdown('<div class="nba-sec">Uso de cupos por canal</div>'
                    '<div class="nba-sub">Cuánto del cupo de cada canal se ocupó</div>', unsafe_allow_html=True)
        cupos = [{"canal": ch.id, "usado": m["uso_canales"][ch.id], "cupo": ch.cupo} for ch in cfg.canales]
        st.markdown(tablero.medidores_cupo(cupos), unsafe_allow_html=True)
        for t in tablero.notas_cupo(cupos, r["asg"].info.get("precio_sombra", {})):
            st.markdown(f'<div class="nba-nota">{t}</div>', unsafe_allow_html=True)
        st.caption("Estimación del modelo, fiable para ampliaciones pequeñas.")
    with der.container(border=True):
        st.markdown('<div class="nba-sec">¿Dónde se pierden los clientes?</div>'
                    '<div class="nba-sub">De la base completa a los clientes que reciben una acción</div>', unsafe_allow_html=True)
        st.markdown(tablero.embudo(datos["etapas"]), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="nba-sec">¿Qué se ofrece y por dónde?</div>'
                    '<div class="nba-sub">Productos asignados por campaña y canal</div>', unsafe_allow_html=True)
        gc = tablero.grafico_composicion(datos["composicion"], [ch.id for ch in cfg.canales],
                                         [c.nombre for c in cand_vigentes(cfg)], _tema())
        if gc is None:
            st.caption("No hay productos asignados.")
        else:
            st.altair_chart(gc, use_container_width=True)
            with st.expander("Ver como tabla"):
                tb = datos["composicion"].assign(canal=lambda d: d["canal"].map(tablero.canal)) \
                    .pivot_table(index="campana", columns="canal", values="productos", fill_value=0, aggfunc="sum")
                tb["Total"] = tb.sum(axis=1)
                st.dataframe(tb, width="stretch")

    with st.container(border=True):
        st.markdown('<div class="nba-sec">Reglas que más clientes excluyen</div>'
                    '<div class="nba-sub">Clientes que cada regla deja fuera de al menos una campaña o canal; '
                    'un cliente puede quedar fuera por varias reglas a la vez</div>', unsafe_allow_html=True)
        total = len(r["df"])
        g1, g2 = st.columns(2, gap="large")
        for col, tipo in ((g1, "Qué productos se ofrecen"), (g2, "Por qué canal")):
            with col:
                st.markdown(f"**{tipo}**")
                ch = tablero.grafico_reglas(datos["reglas"], total, tipo)
                if ch is None:
                    st.caption("Ninguna regla excluyó clientes.")
                else:
                    st.altair_chart(ch, use_container_width=True)

    with st.container(border=True):
        st.markdown('<div class="nba-sec">De la cifra al cliente</div>'
                    '<div class="nba-sub">Abre un caso real de cada situación para ver su explicación</div>', unsafe_allow_html=True)
        for i, (nombre, (cant, cid)) in enumerate(datos["casos"].items()):
            a, b, c = st.columns([5, 2, 2])
            a.markdown(nombre)
            b.markdown(f"**{tablero.n(cant)}** clientes")
            if c.button("Ver un ejemplo", key=f"caso_{i}"):
                ss._ir_a = ("Cliente", cid)
                st.rerun()

    with st.expander("Detalle de la comparación"):
        cols = {"Baseline": [mb["valor_esperado"], mb["clientes_con_accion"], mb["productos_asignados"], mb["jerarquia_pct"]]}
        if prev:
            cols[f"Anterior · {prev[0]}"] = [prev[1]["valor_esperado"], prev[1]["clientes_con_accion"],
                                              prev[1]["productos_asignados"], prev[1]["jerarquia_pct"]]
        cols["Motor actual"] = [m["valor_esperado"], m["clientes_con_accion"], m["productos_asignados"], m["jerarquia_pct"]]
        comp = pd.DataFrame(cols, index=["Valor esperado", "Clientes con acción", "Productos asignados", "% jerarquía"])
        comp["Diferencia vs. baseline"] = comp["Motor actual"] - comp["Baseline"]
        comp["Variación %"] = 100 * comp["Diferencia vs. baseline"] / comp["Baseline"].replace(0, np.nan)

        def _color(x):
            return "color: #15803d; font-weight: 600" if x > 0 else ("color: #b91c1c; font-weight: 600" if x < 0 else "")

        fmt = {c: "{:,.2f}" for c in comp.columns}
        fmt.update({"Diferencia vs. baseline": "{:+,.2f}", "Variación %": "{:+.1f}%"})
        st.dataframe(comp.style.format(fmt).map(_color, subset=["Diferencia vs. baseline", "Variación %"]), width="stretch")
        st.caption(f"Algoritmo: **{cfg.asignacion.algoritmo}** · α: **{cfg.priorizacion.alpha}** · peso del modelo: "
                   f"**{cfg.priorizacion.peso_modelo}** · peso del valor: **{cfg.priorizacion.peso_valor}**.")

    if st.button("Generar parrilla completa (con explicaciones)"):
        with st.spinner("Generando parrilla..."):
            g, _ = run.correr(r["df"], cfg)
        ss.parrilla_csv = g.to_csv(index=False).encode("utf-8")
    if ss.get("parrilla_csv"):
        st.download_button("Descargar parrilla.csv", ss.parrilla_csv, "parrilla.csv", "text/csv")


def cand_vigentes(cfg: Config):
    return cfg.campanas_vigentes()


def _editor_tabla(nombre, columnas, **kw):
    return st.data_editor(st.session_state.tablas[nombre], column_config=columnas, num_rows="dynamic",
                          width='stretch', hide_index=True, key=f"ed_{nombre}_{st.session_state.ver}", **kw)


def pagina_cambiar(ruta, mt):
    ss = st.session_state
    st.header("Cambiar la configuración")
    st.caption("Los cambios quedan en un borrador. Antes de aplicarlos puedes ver su impacto completo en la parrilla.")
    df = cargar_df(ruta, mt)
    cols_num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cols_score = [c for c in df.columns if c.startswith("score_")]
    edit = {k: v.copy() for k, v in ss.tablas.items()}

    t1, t2, t3, t4, t5, t6 = st.tabs(["Umbrales y contacto", "Prioridad", "Campañas", "Reglas", "Canales y cupos", "Datos nuevos"])
    with t1:
        a, b, c = st.columns(3)
        a.slider("Probabilidad mínima de compra de un producto", 0.0, 1.0, key="p_u_prod", step=0.01)
        b.slider("Probabilidad mínima de respuesta de un canal", 0.0, 1.0, key="p_u_canal", step=0.01)
        c.number_input("Máximo de contactos por semana", 1, 20, key="p_tope_sem")
        if ss.get("llamadas_ok"):
            st.number_input("Llamar por asesor solo a clientes con menos de … llamadas de asesor en el mes", 0, 30,
                            key="p_llamadas", help="Con 2, un cliente que ya recibió 2 llamadas este mes no vuelve a recibir una")
        else:
            st.info("No hay una regla de tope de llamadas de asesor en la configuración; créala en la pestaña **Reglas**.")
    with t2:
        st.markdown("**Balance entre valor esperado y jerarquía de negocio**")
        st.slider("α · 0 = maximizar valor esperado · 1 = priorizar la jerarquía", 0.0, 1.0, key="p_alpha", step=0.05)
        st.markdown("**Peso del modelo frente al valor de negocio**")
        m1, m2 = st.columns(2)
        m1.slider("Peso del modelo (probabilidad de compra)", 0.0, 3.0, key="p_peso_modelo", step=0.1,
                  help="Más de 1: se prefiere al producto que el modelo cree más probable, aunque valga menos")
        m2.slider("Peso del valor de negocio", 0.0, 3.0, key="p_peso_valor", step=0.1,
                  help="Más de 1: se prefiere al producto de mayor valor, aunque sea menos probable")
        st.caption("1 y 1 = maximizar el valor esperado (la métrica del reto). Cualquier otro valor inclina la decisión "
                   "y suele costar algo de valor esperado; la vista previa muestra cuánto. Rige para el algoritmo óptimo.")
        st.selectbox("Algoritmo de reparto de cupos", ["optimo", "codicioso"], key="p_algoritmo",
                     help="óptimo: reparte los cupos con visión global; codicioso: el baseline del reto")
        st.text_input("Criterios de desempate entre campañas (en orden, separados por |)", key="p_desempate",
                      help="Se usan cuando dos campañas empatan en puntaje. Válidos: score_producto, valor_negocio, jerarquia")
        with st.expander("Parámetros del baseline (suma ponderada)"):
            st.selectbox("Modo", ["ponderado", "jerarquia_estricta"], key="p_modo")
            st.caption("Los tres pesos se normalizan para que sumen 1.")
            x, y, z = st.columns(3)
            x.number_input("Peso score del producto", 0.0, 1.0, key="p_w_score", step=0.05)
            y.number_input("Peso valor de negocio", 0.0, 1.0, key="p_w_valor", step=0.05)
            z.number_input("Peso jerarquía", 0.0, 1.0, key="p_w_jer", step=0.05)
        st.caption("El orden de la jerarquía se cambia en la pestaña **Campañas** (columna «posicion_jerarquia», 1 = primera).")
    with t3:
        st.caption("Agrega una fila para lanzar una campaña nueva; desmarca «activa» para pausarla sin borrarla; "
                   "edita «canales_permitidos» con `|` (ej. whatsapp|sms).")
        edit["campanas"] = _editor_tabla("campanas", {
            "activa": st.column_config.CheckboxColumn("activa", default=True),
            "columna_score": st.column_config.SelectboxColumn("columna_score", options=cols_score, required=True),
            "valor_negocio": st.column_config.NumberColumn("valor_negocio", min_value=0.0, max_value=1.0, step=0.05, default=0.5),
            "vigencia_inicio": st.column_config.DateColumn("vigencia_inicio"),
            "vigencia_fin": st.column_config.DateColumn("vigencia_fin"),
            "posicion_jerarquia": st.column_config.NumberColumn("posicion_jerarquia", min_value=1, step=1)})
        st.markdown("**Calificación de riesgo permitida por campaña**")
        st.caption("Quita las calificaciones a las que NO se debe ofrecer la campaña. Se traduce en una regla de elegibilidad.")
        ids_camp = [str(i).strip() for i in edit["campanas"]["id"].dropna() if str(i).strip()]
        for fila in [ids_camp[i:i + 3] for i in range(0, len(ids_camp), 3)]:
            for col, cid in zip(st.columns(3), fila):
                ss.setdefault(f"p_cal_{cid}", list(ss.cal_inicial.get(cid, ORDEN_CALIF)))
                col.multiselect(cid, ORDEN_CALIF, key=f"p_cal_{cid}")
    with t4:
        st.caption("Cada regla EXCLUYE al cliente cuando su condición se cumple. "
                   "Para «en»/«no_en» separa los valores con `|`; `$producto` hace referencia al producto evaluado.")
        with st.expander("Crear una regla nueva (asistente)"):
            with st.form("nueva_regla", clear_on_submit=True):
                nombre = st.text_input("Nombre en lenguaje de negocio", "Terminales solo a clientes sin quejas")
                f1, f2 = st.columns(2)
                tipo = f1.selectbox("Aplica a", ["elegibilidad (qué productos se ofrecen)", "canal (por qué canal)"])
                nivel = f2.selectbox("Alcance", ["global", "campana", "producto", "objetivo", "canal"],
                                     help="campana: por id (C-TER); producto: por código (TER); objetivo: grupo de campañas (Upgrade); canal: (sms)")
                alc = st.text_input("Campañas, productos, objetivos o canales afectados (separados por |; vacío si es global)", "")
                g1, g2, g3 = st.columns(3)
                atr = g1.selectbox("Columna de la base", list(df.columns), index=list(df.columns).index("quejas_90d"))
                op = g2.selectbox("Excluir si la columna…", OPERADORES, index=OPERADORES.index(">="))
                val = g3.text_input("…este valor", "1")
                if st.form_submit_button("Agregar al borrador"):
                    ids = [int(x[1:]) for x in ss.tablas["reglas"]["id"].astype(str) if x[1:].isdigit()]
                    nueva = {"activa": True, "id": f"R{max(ids + [0]) + 1:02d}", "nombre": nombre, "tipo": tipo.split()[0],
                             "alcance_nivel": nivel, "alcance_valores": alc, "atributo": atr, "operador": op, "valor": val}
                    ss.tablas["reglas"] = pd.concat([edit["reglas"], pd.DataFrame([nueva])], ignore_index=True)
                    ss.ver += 1
                    st.rerun()
        edit["reglas"] = _editor_tabla("reglas", {
            "activa": st.column_config.CheckboxColumn("activa", default=True),
            "tipo": st.column_config.SelectboxColumn("tipo", options=["elegibilidad", "canal"], required=True),
            "alcance_nivel": st.column_config.SelectboxColumn("alcance", options=["global", "campana", "producto", "objetivo", "canal"], required=True),
            "atributo": st.column_config.SelectboxColumn("columna", options=list(df.columns), required=True),
            "operador": st.column_config.SelectboxColumn("operador", options=OPERADORES, required=True)})
    with t5:
        st.caption("Cambia cupos y productos por contacto; agrega una fila para un canal nuevo "
                   "(necesita una columna `score_canal_...` en la base y quedar permitido en las campañas).")
        c1, c2 = st.columns(2)
        c1.selectbox("Cómo se elige el canal de cada cliente", ["score_canal", "orden_preferencia"], key="p_criterio_canal",
                     help="score_canal: el de mayor probabilidad de respuesta; orden_preferencia: el primero de la lista que tenga cupo")
        c2.text_input("Orden de preferencia de canales (separados por |)", key="p_orden_pref")
        edit["canales"] = _editor_tabla("canales", {
            "columna_score": st.column_config.SelectboxColumn("columna_score", options=[c for c in df.columns if c.startswith("score_canal")], required=True),
            "cupo": st.column_config.NumberColumn("cupo", min_value=0, step=100, required=True),
            "max_productos": st.column_config.NumberColumn("max_productos", min_value=1, step=1, required=True, default=2)})
    with t6:
        st.write(f"La base tiene **{len(df.columns)} columnas** y **{len(df):,} clientes**. Cualquier columna sirve en una regla "
                 "(pestaña Reglas). Para agregar una columna nueva, sube una base ampliada en la barra lateral.")
        st.dataframe(pd.DataFrame({"columna": df.columns, "tipo": [str(t) for t in df.dtypes]}), hide_index=True, height=250)

    try:
        borrador = construir_borrador(edit)
    except Exception as e:
        st.error("El borrador no es válido. Corrige lo siguiente para poder calcular su impacto:")
        mostrar_errores(describir_error(e))
        return
    with st.expander("Reglas en lenguaje de negocio"):
        for r in borrador.reglas:
            st.write(("[activa] " if r.activa else "[pausada] ") + frase_regla(r))

    st.divider()
    st.subheader("Vista previa del impacto")
    vigente = ss.vigente
    if borrador.model_dump_json() == vigente.model_dump_json():
        st.info("El borrador es igual a la configuración vigente.")
        return
    if st.button("Calcular impacto del cambio", type="primary"):
        try:
            A = ejecutar(vigente.model_dump_json(), ruta, mt)
            B = ejecutar(borrador.model_dump_json(), ruta, mt)
            vb = validar_corrida(borrador.model_dump_json(), ruta, mt)
            ss.impacto = {"cfg": borrador.model_dump_json(), "viol": vb,
                          "cmp": comparar.comparar(df["id_cliente"].to_numpy(), (A["cand"], A["asg"], A["m"]), (B["cand"], B["asg"], B["m"])),
                          "A": A["m"], "B": B["m"]}
        except (ConfigError, KeyError, ValueError) as e:
            ss.impacto = None
            st.error(f"No se pudo calcular: {e}")
    imp = ss.get("impacto")
    if imp and imp["cfg"] == borrador.model_dump_json():
        c, A, B = imp["cmp"], imp["A"], imp["B"]
        k = st.columns(4)
        k[0].metric("Valor esperado", f"{B['valor_esperado']:,.1f}", f"{c['delta_valor']:+,.1f}")
        k[1].metric("Clientes con acción", f"{B['clientes_con_accion']:,}", f"{c['delta_clientes']:+,}")
        k[2].metric("Productos asignados", f"{B['productos_asignados']:,}", f"{c['delta_productos']:+,}")
        k[3].metric("% jerarquía", f"{B['jerarquia_pct']:.2f}%", f"{c['delta_jerarquia']:+.2f} pp")
        s = st.columns(4)
        s[0].metric("Clientes que ganan acción", c["ganan_accion"])
        s[1].metric("Clientes que pierden acción", c["pierden_accion"])
        s[2].metric("Cambian de canal", c["cambian_canal"])
        s[3].metric("Cambian de productos", c["cambian_productos"])
        pc = pd.DataFrame(c["productos_por_campana"], index=["Antes", "Después"]).T
        pc["Cambio"] = pc["Después"] - pc["Antes"]
        l, r_ = st.columns(2)
        l.markdown("**Productos asignados por campaña**")
        l.dataframe(pc, width='stretch')
        r_.markdown("**Uso de cupos**")
        r_.dataframe(pd.DataFrame({"Antes": A["uso_canales"], "Después": B["uso_canales"], "Cupo": B["cupo_canales"]}),
                     width='stretch')
        with st.expander("Ejemplos de clientes afectados (cópialos en la sección Cliente)"):
            for kk, v in c["ejemplos"].items():
                if v:
                    st.write(f"**{kk.replace('_', ' ')}**: " + ", ".join(v[:10]))
        if imp["viol"]["violaciones_total"]:
            st.error(f"El cambio produce {imp['viol']['violaciones_total']} violaciones: {imp['viol']['violaciones']}")
        else:
            st.success("Validador: el cambio mantiene 0 violaciones.")
        etiqueta = st.text_input("Describe el cambio (queda en el historial)", "Ajuste de configuración")
        a, b = st.columns(2)
        if a.button("Aplicar cambio", disabled=bool(imp["viol"]["violaciones_total"])):
            nombre = versiones.guardar_version(borrador, CONFIG_DIR, etiqueta, {
                k: B[k] for k in ("valor_esperado", "clientes_con_accion", "productos_asignados", "jerarquia_pct")})
            programar_reinicio(borrador, f"Configuración aplicada (versión {nombre}).")
        if b.button("Descartar borrador"):
            programar_reinicio(vigente)


def pagina_cliente(ruta, mt):
    st.header("Explicación por cliente")
    cfg = st.session_state.vigente
    r, ex = resumen_corrida(cfg.model_dump_json(), ruta, mt)
    cats = ex.categorias()
    ids = ex.ids
    sit = st.selectbox("Ver un ejemplo de", ["(buscar por id)"] + sorted(set(cats)))
    cand_ids = ids if sit == "(buscar por id)" else ids[cats == sit]
    por_defecto = st.session_state.get("cliente_sel") or str(cand_ids[0])
    cid = st.text_input("Id del cliente", por_defecto)
    if sit != "(buscar por id)":
        cid = st.selectbox("Clientes de esa situación", [str(x) for x in cand_ids[:300]])
    st.session_state.cliente_sel = cid
    pos = np.where(ids == cid)[0]
    if not len(pos):
        st.warning("No se encontró ese cliente.")
        return
    reg = ex.registro(int(pos[0]))
    (st.success if reg["estado"] == "asignado" else st.warning)(ex.frase_asesor(reg))
    a, b = st.columns([3, 2])
    with a:
        if reg["productos"]:
            st.markdown(f"**Decisión: {reg['canal']}** · valor esperado {reg['valor_esperado']:.3f}")
            st.dataframe(pd.DataFrame(reg["productos"]).rename(columns={
                "nombre": "Producto", "prob_compra": "Prob. compra", "prob_canal": "Prob. respuesta canal",
                "valor_negocio": "Valor negocio", "valor_esperado": "Valor esperado"}).drop(columns="campana"),
                hide_index=True, width='stretch')
        st.markdown("**Por qué no los otros productos**")
        if reg["descartados"]:
            st.dataframe(pd.DataFrame([{"Producto": d["nombre"], "Motivo": " · ".join(m["texto"] for m in d["motivos"])}
                                       for d in reg["descartados"]]), hide_index=True, width='stretch')
        else:
            st.write("Se ofrecieron todos los productos disponibles.")
    with b:
        st.markdown("**Canales**")
        st.dataframe(pd.DataFrame([{"Canal": c["canal"], "Resultado": c["resultado"].replace("_", " "),
                                    "Valor": c["valor"], "Motivo": " · ".join(m["texto"] for m in c["motivos"])}
                                   for c in reg["canales"]]), hide_index=True, width='stretch')
        if reg["cupo"] and reg["cupo"]["tipo"] == "canal_alternativo":
            c = reg["cupo"]
            st.info(f"Su mejor canal era **{c['canal_ideal']}** (valor {c['valor_ideal']:.3f}), pero su cupo se agotó. "
                    f"Se asignó {reg['canal']} (valor {c['valor_asignado']:.3f}); valor cedido: {c['valor_cedido']:.3f}.")
    with st.expander("Frase completa de la parrilla y detalle técnico"):
        st.write(ex.frase(reg))
        if st.toggle("Ver el registro técnico (JSON)", key=f"json_{cid}"):
            st.json(reg)


def pagina_datos(ruta, mt):
    ss = st.session_state
    st.header("Base de datos")
    st.caption("Elige de dónde se leen los clientes. Cualquier columna de la base puede usarse en las reglas.")
    st.markdown(f"**Archivo activo:** `{ruta}`")
    if not Path(ruta).exists():
        st.error("El archivo activo no existe. Elige otro.")
    t1, t2, t3 = st.tabs(["Elegir un archivo", "Escribir una ruta", "Subir un archivo"])
    with t1:
        locales = sorted(str(p) for p in (ROOT / "data").glob("*.csv"))
        if locales:
            sel = st.selectbox("Archivos CSV disponibles en data/", locales,
                               index=locales.index(ruta) if ruta in locales else 0)
            if st.button("Usar este archivo", key="usar_sel"):
                ss.db_ruta = sel
                st.rerun()
        else:
            st.info("No hay archivos CSV en la carpeta data/.")
    with t2:
        nueva = st.text_input("Ruta del CSV", ruta, key="ruta_texto")
        if st.button("Usar esta ruta", key="usar_ruta"):
            if Path(nueva).is_file():
                ss.db_ruta = nueva
                st.rerun()
            else:
                st.error("No existe ese archivo.")
    with t3:
        sub = st.file_uploader("Sube una base (puede traer columnas nuevas)", type="csv")
        if sub is not None and st.button("Cargar y usar", key="usar_sub"):
            destino = ROOT / "data" / "clientes_cargado.csv"
            destino.write_bytes(sub.getvalue())
            ss.db_ruta = str(destino)
            st.rerun()

    if not Path(ruta).exists():
        return
    df = cargar_df(ruta, mt)
    cfg = ss.vigente
    st.divider()
    k = st.columns(3)
    k[0].metric("Clientes", f"{len(df):,}")
    k[1].metric("Columnas", len(df.columns))
    k[2].metric("Id únicos", "sí" if "id_cliente" in df.columns and df["id_cliente"].is_unique else "no")
    requeridas = {"id_cliente", cfg.politica_contacto.columna_contactos_semana}
    requeridas |= {c.columna_score for c in cfg.campanas} | {c.columna_score for c in cfg.canales}
    requeridas |= {r.atributo for r in cfg.reglas if r.activa}
    faltan = sorted(requeridas - set(df.columns))
    if faltan:
        st.error("Faltan columnas que la configuración vigente necesita: " + ", ".join(faltan))
    else:
        st.success("La base trae todas las columnas que usa la configuración vigente.")
    st.subheader("Vista previa")
    st.dataframe(df.head(50), width="stretch", height=260)
    st.subheader("Columnas")
    perfil = pd.DataFrame({"columna": df.columns, "tipo": [str(t) for t in df.dtypes],
                           "vacíos": df.isna().sum().values,
                           "usada en la configuración": ["sí" if c in requeridas else "" for c in df.columns]})
    st.dataframe(perfil, hide_index=True, width="stretch", height=300)


def pagina_versiones():
    st.header("Historial de versiones")
    vs = versiones.listar(CONFIG_DIR)
    if not vs:
        st.info("Aún no se ha aplicado ningún cambio desde la consola.")
        return
    for v in vs:
        m = v["metricas"]
        with st.container(border=True):
            c = st.columns([4, 3, 1])
            c[0].markdown(f"**{v['etiqueta']}**  \n`{v['version']}`")
            c[1].write(f"Valor {m.get('valor_esperado', 0):,.1f} · {m.get('clientes_con_accion', 0):,} clientes · "
                       f"jerarquía {m.get('jerarquia_pct', 0)}%")
            if c[2].button("Restaurar", key=v["version"]):
                programar_reinicio(versiones.cargar_version(v["version"], CONFIG_DIR),
                                   "Versión restaurada como borrador. Calcula su impacto abajo y aplícala si es lo que quieres.",
                                   "Cambiar configuración")
    st.caption("«Restaurar» carga esa versión como borrador: revisa su impacto en «Cambiar configuración» y aplícala.")


# ------------------------------------------------------------------ main
mensaje = None
if "_ir_a" in st.session_state:
    _pag, _cid = st.session_state.pop("_ir_a")
    st.session_state.pagina = _pag
    st.session_state.cliente_sel = _cid
if "_reiniciar" in st.session_state:
    cfg_nueva, mensaje, forzar = st.session_state.pop("_reiniciar")
    iniciar_borrador(cfg_nueva)
    if forzar:
        st.session_state.pagina = forzar  # antes de dibujar el menu
pagina, ruta, mt = barra_lateral()
if mensaje:
    st.success(mensaje)
if "vigente" not in st.session_state:
    try:
        iniciar_borrador(config.cargar(CONFIG_DIR))
    except Exception as e:      # ValidationError, ConfigError, YAML mal formado...
        pantalla_configuracion_invalida(e)
try:
    {"Tablero": lambda: pagina_tablero(ruta, mt), "Cambiar configuración": lambda: pagina_cambiar(ruta, mt),
     "Cliente": lambda: pagina_cliente(ruta, mt), "Base de datos": lambda: pagina_datos(ruta, mt),
     "Versiones": pagina_versiones}[pagina]()
except ConfigError as e:
    st.error(f"Error de configuración: {e}")
