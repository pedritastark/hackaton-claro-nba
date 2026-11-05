"""Componentes visuales del Tablero: franja de estado, medidores de cupo, embudo y reglas que mas excluyen.

Paleta: la de referencia de la guia de visualizacion (azul para la serie; gris de contexto; colores de estado
reservados y siempre con icono + texto). Los textos heredan el color del tema de Streamlit y las pistas
usan grises translucidos, asi funcionan igual en tema claro y oscuro."""
import html

import altair as alt
import numpy as np
import pandas as pd

AZUL = "#2a78d6"                                              # serie / magnitud
GRIS = "#898781"                                             # etapas de contexto (el resultado va en azul)
BUENO, ALERTA, CRITICO = "#0ca30c", "#fab219", "#d03b3b"          # estados (con icono + texto)

CSS = """
<style>
.nba-estado { display:flex; align-items:center; gap:14px; padding:14px 18px; border-radius:12px;
  border:1px solid rgba(128,128,128,.28); border-left:6px solid var(--c); margin:2px 0 14px 0; }
.nba-estado .t { font-size:1.12rem; font-weight:650; line-height:1.25; }
.nba-estado .s { font-size:.86rem; opacity:.75; margin-top:2px; }
.nba-estado svg { flex:none; }
.nba-sec { font-size:1.02rem; font-weight:650; margin:4px 0 2px 0; }
.nba-sub { font-size:.82rem; opacity:.7; margin:0 0 10px 0; }
.nba-fila { display:grid; grid-template-columns: 92px 1fr 150px; align-items:center; gap:10px; margin:9px 0; }
.nba-fila .n { font-weight:600; }
.nba-pista { height:14px; border-radius:7px; background:rgba(128,128,128,.22); overflow:hidden; }
.nba-relleno { height:100%; border-radius:7px; background:__AZUL__; }
.nba-fila .v { font-size:.84rem; text-align:right; white-space:nowrap; }
.nba-lleno { display:inline-flex; align-items:center; gap:4px; font-size:.74rem; font-weight:650; margin-left:6px;
  padding:1px 7px; border-radius:9px; border:1px solid rgba(128,128,128,.4); }
.nba-nota { font-size:.84rem; margin:3px 0; padding-left:10px; border-left:3px solid rgba(128,128,128,.35); }
.nba-emb { display:grid; grid-template-columns: 1fr; gap:2px; margin:2px 0; }
.nba-emb .et { display:flex; justify-content:space-between; font-size:.85rem; margin-top:8px; }
.nba-emb .et b { font-weight:600; }
.nba-emb .pi { height:22px; border-radius:6px; background:rgba(128,128,128,.14); }
.nba-emb .re { height:100%; border-radius:6px; }
.nba-emb .pe { font-size:.76rem; opacity:.7; padding-left:2px; }
[data-testid="stMetricValue"] { font-size:2.1rem; font-weight:700; }
[data-testid="stMetricLabel"] p { font-size:.86rem; opacity:.75; }
.nba-sec { border-left:4px solid #1d4ed8; padding-left:10px; }
.nba-alerta { display:flex; align-items:center; gap:10px; padding:8px 12px; border-radius:8px;
  border:1px solid rgba(128,128,128,.28); margin:4px 0; font-size:.9rem; }
.nba-caso { display:flex; justify-content:space-between; align-items:center; }
</style>
""".replace("__AZUL__", AZUL)

_ICONO_OK = ('<svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="10" '
             f'fill="{BUENO}"/><path d="M7 12.5l3.2 3.2L17 8.8" stroke="#fff" stroke-width="2.4" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')
_ICONO_MAL = ('<svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 2.8L22 20.5H2z" '
              f'fill="{CRITICO}"/><path d="M12 9v5.2M12 17.2v.1" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/></svg>')
_ICONO_LLENO = (f'<svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8L22 20.5H2z" fill="{ALERTA}"/>'
                '<path d="M12 9v5M12 17v.1" stroke="#000" stroke-width="2.4" stroke-linecap="round"/></svg>')


def n(x, dec=0):
    """Numero con punto de miles y coma decimal, como se lee en Colombia."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


NOMBRE_CANAL = {"whatsapp": "WhatsApp", "sms": "SMS", "correo": "Correo", "asesor": "Asesor"}
NOMBRE_ALGORITMO = {"optimo": "óptimo", "codicioso": "codicioso"}


def canal(c: str) -> str:
    return NOMBRE_CANAL.get(c, c.capitalize())


def signo(x, dec=1, unidad="") -> str:
    """Numero con signo explicito y formato colombiano: +698,4 / −12,0."""
    return f"{'+' if x >= 0 else '−'}{n(abs(x), dec)}{unidad}"


def franja_estado(violaciones: int, configuracion: str, algoritmo: str, mejora_pct: float, detalle_viol: dict = None) -> str:
    ok = violaciones == 0
    color = BUENO if ok else CRITICO
    titulo = "Parrilla válida · 0 violaciones de las restricciones" if ok else \
        f"Parrilla con {n(violaciones)} violaciones de las restricciones"
    sub = (f"Configuración: <b>{html.escape(configuracion)}</b> · algoritmo {html.escape(NOMBRE_ALGORITMO.get(algoritmo, algoritmo))} · "
           f"{'+' if mejora_pct >= 0 else '−'}{n(abs(mejora_pct), 1)} % de valor esperado frente al baseline")
    if not ok and detalle_viol:
        sub += " · " + html.escape(", ".join(f"{k}: {v}" for k, v in detalle_viol.items()))
    return (f'<div class="nba-estado" style="--c:{color}" role="status">{_ICONO_OK if ok else _ICONO_MAL}'
            f'<div><div class="t">{titulo}</div><div class="s">{sub}</div></div></div>')


def medidores_cupo(cupos: list) -> str:
    """cupos: [{canal, usado, cupo}] -> medidores horizontales (un ratio contra su limite)."""
    filas = []
    for c in cupos:
        pct = 100 * c["usado"] / max(1, c["cupo"])
        lleno = pct >= 99.5
        etiqueta = f'<span class="nba-lleno">{_ICONO_LLENO}Lleno</span>' if lleno else ""
        filas.append(
            f'<div class="nba-fila" title="{html.escape(canal(c["canal"]))}: {n(c["usado"])} de {n(c["cupo"])} cupos">'
            f'<div class="n">{html.escape(canal(c["canal"]))}</div>'
            f'<div class="nba-pista" role="img" aria-label="{n(pct, 1)} % usado"><div class="nba-relleno" style="width:{min(pct, 100):.1f}%"></div></div>'
            f'<div class="v">{n(c["usado"])} / {n(c["cupo"])} · {n(pct, 0)} %{etiqueta}</div></div>')
    return "".join(filas)


def notas_cupo(cupos: list, precio: dict) -> list:
    """Frases de negocio para los canales llenos. El precio sombra es fiable para ampliaciones pequenas."""
    out = []
    for c in cupos:
        p = precio.get(c["canal"], 0.0) or 0.0
        if c["usado"] >= c["cupo"] and p > 0:
            out.append(f'<b>{html.escape(canal(c["canal"]))}</b> está lleno: cada 100 cupos adicionales sumarían '
                       f'≈ {n(100 * p, 1)} de valor esperado.')
    return out


def embudo(etapas: list) -> str:
    """etapas: [(nombre, cantidad, motivo_de_la_perdida_hacia_esta_etapa)]. Enfasis: contexto en gris, resultado en azul."""
    base = max(1, etapas[0][1])
    out = ['<div class="nba-emb">']
    for i, (nombre, cant, motivo) in enumerate(etapas):
        pct = 100 * cant / base
        out.append(f'<div class="et"><span>{html.escape(nombre)}</span><b>{n(cant)} · {n(pct, 1)} %</b></div>'
                   f'<div class="pi" title="{html.escape(nombre)}: {n(cant)} clientes ({n(pct, 1)} %)">'
                   f'<div class="re" style="width:{pct:.2f}%;background:{AZUL if i == len(etapas) - 1 else GRIS}"></div></div>')
        if i + 1 < len(etapas):
            perdida = cant - etapas[i + 1][1]
            if perdida > 0:
                out.append(f'<div class="pe">− {n(perdida)} · {html.escape(etapas[i + 1][2])}</div>')
    out.append("</div>")
    return "".join(out)


def etapas_embudo(el, cand, asg, textos: dict = None) -> list:
    """Cuantos clientes sobreviven a cada filtro (los filtros se aplican en este orden)."""
    N = len(asg.canal)
    camp_ok = np.any([el.prod_ok[c.id] for c in cand.campanas], axis=0)
    s2 = int(el.semana_ok.sum())
    s3 = int((el.semana_ok & camp_ok).sum())
    s4 = int((cand.n_paq.sum(axis=1) > 0).sum())
    s5 = int((asg.canal >= 0).sum())
    return [("Clientes en la base", N, ""),
            ("Dentro del tope semanal de contactos", s2, "ya alcanzaron el tope semanal"),
            ("Con al menos una campaña elegible", s3, "no cumplen las reglas de ninguna campaña"),
            ("Con un canal habilitado para sus productos", s4, "sin canal autorizado o con baja probabilidad de respuesta"),
            ("Con acción asignada", s5, "sin cupo en sus canales")]


def reglas_que_mas_excluyen(el, cfg, cand) -> pd.DataFrame:
    """Clientes que cada regla deja fuera de al menos una campana (o canal). Un cliente puede estar en varias."""
    nombres = {r.id: r.nombre for r in cfg.reglas}
    nombres["UMBRAL_PRODUCTO"] = f"Probabilidad de compra menor a {n(cfg.priorizacion.umbral_score_producto, 2)}"
    nombres["UMBRAL_CANAL"] = f"Probabilidad de respuesta menor a {n(cfg.asignacion.umbral_score_canal, 2)}"

    def distintos(mapa):
        cods = set()
        for w in mapa.values():
            cods |= {c for c in pd.unique(np.concatenate([x.split(";") for x in pd.unique(w)])) if c}
        out = {}
        for cod in cods:
            m = np.zeros(len(next(iter(mapa.values()))), dtype=bool)
            for w in mapa.values():
                m |= np.char.find(w, cod + ";") >= 0
            out[cod] = int(m.sum())
        return out

    filas = []
    for cod, cant in distintos(el.prod_why).items():
        filas.append({"codigo": cod, "regla": nombres.get(cod, cod), "tipo": "Qué productos se ofrecen", "clientes": cant})
    for cod, cant in distintos(el.canal_why).items():
        filas.append({"codigo": cod, "regla": nombres.get(cod, cod), "tipo": "Por qué canal", "clientes": cant})
    return pd.DataFrame(filas).sort_values("clientes", ascending=False, ignore_index=True)


def grafico_reglas(df: pd.DataFrame, total: int, tipo: str):
    d = df[df.tipo == tipo].copy()
    if d.empty:
        return None
    d["porcentaje"] = (100 * d.clientes / total).round(1)
    base = alt.Chart(d).encode(
        y=alt.Y("regla:N", sort="-x", title=None, axis=alt.Axis(labelLimit=330, labelPadding=6, ticks=False, domain=False)),
        x=alt.X("clientes:Q", title=None, axis=None),
        tooltip=[alt.Tooltip("regla:N", title="Regla"), alt.Tooltip("clientes:Q", title="Clientes excluidos", format=","),
                 alt.Tooltip("porcentaje:Q", title="% de la base")])
    barras = base.mark_bar(color=AZUL, cornerRadiusEnd=4, size=16)
    etiquetas = base.mark_text(align="left", dx=5, fontSize=12).encode(text=alt.Text("clientes:Q", format=","))
    return (barras + etiquetas).properties(height=max(60, 34 * len(d))).configure_view(strokeWidth=0) \
        .configure_axis(grid=False)


# ------------------------------------------------------------------ composicion de la parrilla (barras apiladas)
SERIES = {"claro": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
          "oscuro": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]}
TINTA_SOBRE_SERIE = ["#ffffff", "#0b0b0b", "#0b0b0b", "#0b0b0b", "#0b0b0b", "#ffffff", "#ffffff", "#0b0b0b"]
SUPERFICIE = {"claro": "#fcfcfb", "oscuro": "#1a1a19"}


def composicion(cand, asg) -> pd.DataFrame:
    """Productos asignados por campana y canal."""
    filas = []
    for s in range(asg.paq.shape[1]):
        k = asg.paq[:, s]
        for ki, c in enumerate(cand.campanas):
            for ji, ch in enumerate(cand.canales):
                cant = int(((k == ki) & (asg.canal == ji)).sum())
                if cant:
                    filas.append({"campana": c.nombre, "canal": ch.id, "productos": cant})
    d = pd.DataFrame(filas, columns=["campana", "canal", "productos"])
    return d.groupby(["campana", "canal"], as_index=False)["productos"].sum()


def grafico_composicion(d: pd.DataFrame, canales: list, campanas: list, tema: str = "claro"):
    """Barras horizontales apiladas: un color fijo por canal (no depende del filtro ni del orden)."""
    if d.empty:
        return None
    colores = SERIES[tema]
    dom = [canal(c) for c in canales]
    rango = colores[:len(dom)]
    tinta = TINTA_SOBRE_SERIE[:len(dom)]
    d = d.copy()
    d["canal_nombre"] = d["canal"].map(canal)
    d["orden"] = d["canal"].map({c: i for i, c in enumerate(canales)})
    d = d.sort_values(["campana", "orden"])
    d["fin"] = d.groupby("campana")["productos"].cumsum()
    d["inicio"] = d["fin"] - d["productos"]
    d["medio"] = (d["inicio"] + d["fin"]) / 2
    d["tinta"] = d["orden"].map(lambda i: tinta[int(i)])
    total = d.groupby("campana", as_index=False)["productos"].sum().rename(columns={"productos": "total"})
    maximo = float(total["total"].max())
    d["pct_campana"] = (100 * d["productos"] / d["campana"].map(total.set_index("campana")["total"])).round(1)
    ejex_y = alt.Y("campana:N", sort=campanas, title=None, axis=alt.Axis(labelLimit=260, ticks=False, domain=False, labelPadding=8))
    color = alt.Color("canal_nombre:N", scale=alt.Scale(domain=dom, range=rango),
                      legend=alt.Legend(title=None, orient="top", symbolType="square", labelFontSize=12))
    barras = alt.Chart(d).mark_bar(stroke=SUPERFICIE[tema], strokeWidth=2, size=34).encode(
        y=ejex_y, x=alt.X("inicio:Q", title=None, axis=None), x2="fin:Q", color=color,
        tooltip=[alt.Tooltip("campana:N", title="Campaña"), alt.Tooltip("canal_nombre:N", title="Canal"),
                 alt.Tooltip("productos:Q", title="Productos", format=","),
                 alt.Tooltip("pct_campana:Q", title="% de la campaña")])
    etiquetas = alt.Chart(d[d["productos"] >= 0.07 * maximo]).mark_text(fontSize=12, fontWeight=600).encode(
        y=alt.Y("campana:N", sort=campanas), x=alt.X("medio:Q"), text=alt.Text("productos:Q", format=","),
        color=alt.Color("tinta:N", scale=None))
    totales = alt.Chart(total).mark_text(align="left", dx=6, fontSize=12, fontWeight=600).encode(
        y=alt.Y("campana:N", sort=campanas), x=alt.X("total:Q"), text=alt.Text("total:Q", format=","))
    return (barras + etiquetas + totales).properties(height=max(70, 52 * d["campana"].nunique())) \
        .configure_view(strokeWidth=0).configure_axis(grid=False)


def alertas_html(textos: list) -> str:
    return "".join(f'<div class="nba-alerta" role="note">{_ICONO_LLENO}<span>{t}</span></div>' for t in textos)
