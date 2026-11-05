"""Cada tipo de cambio que pide negocio, HECHO DESDE LA CONSOLA (AppTest): se edita, se ve el impacto,
se aplica, se lee la configuracion guardada y se corre el motor para verificar la parrilla resultante.

Limite de AppTest: no puede teclear dentro de las tablas editables (st.data_editor). Para esos cambios se
reemplaza el contenido de la tabla en el estado de la sesion (equivale a lo que la tabla devolveria tras editarla)."""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from nba import comparar, config
from nba.validar import validar

ROOT = Path(__file__).resolve().parent.parent
DT = {"canales_contactados_mes": str, "productos_ofertados_mes": str}


@pytest.fixture(scope="module")
def df_base():
    return pd.read_csv(ROOT / "data" / "oficial" / "clientes.csv", dtype=DT)


@pytest.fixture(scope="module")
def df_ext(df_base, tmp_path_factory):
    """Base ampliada con columnas nuevas (datos nuevos) para los cambios que las necesitan."""
    d = df_base.copy()
    rng = np.random.default_rng(11)
    d["score_seguros"] = rng.beta(2.5, 4, len(d)).round(4)
    d["score_canal_push"] = rng.beta(3, 4, len(d)).round(4)
    d["es_vip"] = (rng.random(len(d)) < 0.25).astype(int)
    ruta = tmp_path_factory.mktemp("datos") / "clientes_ext.csv"
    d.to_csv(ruta, index=False)
    return d, str(ruta)


@pytest.fixture
def consola(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config_inicial", tmp_path / "cfg")
    monkeypatch.setenv("NBA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("NBA_CLIENTES", str(ROOT / "data" / "oficial" / "clientes.csv"))
    at = AppTest.from_file(str(ROOT / "app" / "consola.py"), default_timeout=240).run()
    at.cfg_dir = str(tmp_path / "cfg")
    return at


def nueva_sesion(at):
    """Equivale a recargar la pagina: lee de disco la configuracion ya aplicada."""
    nuevo = AppTest.from_file(str(ROOT / "app" / "consola.py"), default_timeout=240).run()
    nuevo.cfg_dir = at.cfg_dir
    return nuevo


# ---------------------------------------------------------------- utilidades
def ir(at, seccion):
    at.sidebar.radio[0].set_value(seccion).run()
    assert not at.exception, [e.value for e in at.exception]


def tabla(at, nombre, nueva=None):
    t = at.session_state["tablas"]
    if nueva is not None:
        t[nombre] = nueva
        at.session_state["ver"] = at.session_state["ver"] + 1
    return t[nombre].copy()


def impacto(at):
    [b for b in at.button if "impacto" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert any("0 violaciones" in s.value for s in at.success), "la vista previa debe confirmar 0 violaciones"


def aplicar(at):
    [b for b in at.button if "Aplicar" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    return config.cargar(at.cfg_dir)


def parrilla(df, cfg):
    el, cand, asg = comparar.nucleo(df, cfg)
    g = comparar.parrilla_ligera(df, cfg, el, cand, asg).replace("", pd.NA)
    assert validar(g.fillna(""), df, cfg)["violaciones_total"] == 0
    return g


def con(g, camp):
    return ((g.campana_1 == camp) | (g.campana_2 == camp)).fillna(False)


# ---------------------------------------------------------------- 3. Umbrales y 6. Politica de contacto
def test_umbrales_y_tope_semanal(consola, df_base):
    at = consola
    ir(at, "Cambiar configuración")
    at.slider(key="p_u_prod").set_value(0.5).run()
    at.slider(key="p_u_canal").set_value(0.4).run()
    at.number_input(key="p_tope_sem").set_value(1).run()
    impacto(at)
    cfg = aplicar(at)
    assert (cfg.priorizacion.umbral_score_producto, cfg.asignacion.umbral_score_canal,
            cfg.politica_contacto.max_contactos_semana) == (0.5, 0.4, 1)
    assert [c.objetivo for c in cfg.campanas] == ["Venta cruzada", "Terminales", "Upgrade"]   # aplicar no borra datos de las campanas
    g = parrilla(df_base, cfg).merge(df_base, on="id_cliente")
    a = g[g.estado == "asignado"]
    assert (a.contactos_semana_actual == 0).all()
    for camp, col in (("C-VCH", "score_venta_cruzada_hogar"), ("C-TER", "score_terminales"), ("C-OTT", "score_upgrade_ott")):
        assert (g[con(g, camp)][col] >= 0.5).all()
    for ch in ("sms", "correo", "whatsapp", "asesor"):
        assert (g[g.canal == ch][f"score_canal_{ch}"] >= 0.4).all()


def test_tope_de_llamadas_de_asesor_con_control_directo(consola, df_base):
    at = consola
    ir(at, "Cambiar configuración")
    at.number_input(key="p_llamadas").set_value(1).run()
    impacto(at)
    cfg = aplicar(at)
    assert next(r for r in cfg.reglas if r.id == "R11").valor == 1
    g = parrilla(df_base, cfg).merge(df_base, on="id_cliente")
    ase = g[g.canal == "asesor"]
    assert len(ase) > 0 and (ase.contactos_asesor_mes == 0).all()


# ---------------------------------------------------------------- 2. Reglas
def test_calificaciones_por_campana_con_control_directo(consola, df_base):
    at = consola
    ir(at, "Cambiar configuración")
    assert set(at.multiselect(key="p_cal_C-TER").value) == {"E", "A", "B"}      # inferido de R02 del kit
    at.multiselect(key="p_cal_C-TER").set_value(["E"]).run()
    at.multiselect(key="p_cal_C-VCH").set_value(["E", "A", "B"]).run()
    impacto(at)
    cfg = aplicar(at)
    g = parrilla(df_base, cfg).merge(df_base, on="id_cliente")
    assert set(g[con(g, "C-TER")].calificacion_riesgo) == {"E"}
    assert set(g[con(g, "C-VCH")].calificacion_riesgo) <= {"E", "A", "B"} and con(g, "C-VCH").sum() > 0
    assert set(g[con(g, "C-OTT")].calificacion_riesgo) > {"E", "A", "B"}         # OTT sin restriccion
    # volver a todas las calificaciones elimina la restriccion
    at = nueva_sesion(at)
    ir(at, "Cambiar configuración")
    assert at.multiselect(key="p_cal_C-TER").value == ["E"]          # la restriccion aplicada se lee de la configuracion
    at.multiselect(key="p_cal_C-TER").set_value(["E", "A", "B", "C", "P"]).run()
    impacto(at)
    cfg2 = aplicar(at)
    assert not any(r.alcance_valores == ["C-TER"] and r.atributo == "calificacion_riesgo" and r.activa for r in cfg2.reglas)


def test_crear_regla_con_el_asistente_y_apagar_otra(consola, df_base):
    at = consola
    ir(at, "Cambiar configuración")
    [t for t in at.text_input if t.label.startswith("Nombre")][0].set_value("Hogar solo a clientes con banca digital")
    [s for s in at.selectbox if s.label == "Alcance"][0].set_value("campana")
    [t for t in at.text_input if t.label.startswith("Campañas, productos")][0].set_value("C-VCH")
    [s for s in at.selectbox if s.label == "Columna de la base"][0].set_value("usa_banca_digital")
    [s for s in at.selectbox if s.label.startswith("Excluir si")][0].set_value("==")
    [t for t in at.text_input if t.label.startswith("…este")][0].set_value("0")
    [b for b in at.button if "Agregar" in b.label][0].click().run()
    t = tabla(at, "reglas")
    t.loc[t.id == "R07", "activa"] = False                      # apagar la regla de quejas
    tabla(at, "reglas", t)
    at.run()
    impacto(at)
    cfg = aplicar(at)
    g = parrilla(df_base, cfg).merge(df_base, on="id_cliente")
    assert (g[con(g, "C-VCH")].usa_banca_digital == 1).all() and con(g, "C-VCH").sum() > 0
    assert (g[g.estado == "asignado"].quejas_90d >= 3).sum() > 0     # R07 apagada: ahora si se ofrece


# ---------------------------------------------------------------- 4. Prioridad
def test_prioridad_jerarquia_y_pesos(consola, df_base):
    at = consola
    ref = parrilla(df_base, config.cargar(at.cfg_dir))
    ir(at, "Cambiar configuración")
    c = tabla(at, "campanas")
    c["posicion_jerarquia"] = c["id"].map({"C-OTT": 1, "C-TER": 2, "C-VCH": 3})     # OTT pasa a ser la primera
    tabla(at, "campanas", c)
    at.slider(key="p_alpha").set_value(1.0).run()
    at.slider(key="p_peso_modelo").set_value(2.0).run()
    impacto(at)
    cfg = aplicar(at)
    assert cfg.priorizacion.jerarquia == ["C-OTT", "C-TER", "C-VCH"]
    assert (cfg.priorizacion.alpha, cfg.priorizacion.peso_modelo) == (1.0, 2.0)
    g = parrilla(df_base, cfg)
    assert con(g, "C-OTT").sum() > con(ref, "C-OTT").sum() and con(g, "C-VCH").sum() < con(ref, "C-VCH").sum()


# ---------------------------------------------------------------- 1. Campanas y 7. Datos nuevos
def test_datos_nuevos_y_campana_nueva_pausando_otra(consola, df_ext):
    d, ruta = df_ext
    at = consola
    ir(at, "Base de datos")
    [t for t in at.text_input if t.label == "Ruta del CSV"][0].set_value(ruta)
    [b for b in at.button if b.label == "Usar esta ruta"][0].click().run()
    ir(at, "Cambiar configuración")
    c = tabla(at, "campanas")
    nueva = {"activa": True, "id": "C-SEG", "nombre": "Seguros", "producto": "SEG", "columna_score": "score_seguros",
             "valor_negocio": 0.9, "canales_permitidos": "whatsapp|correo|sms", "vigencia_inicio": None,
             "vigencia_fin": None, "posicion_jerarquia": 4}
    c = pd.concat([c, pd.DataFrame([nueva])], ignore_index=True)
    c.loc[c.id == "C-VCH", "activa"] = False                      # pausar sin borrar
    c.loc[c.id == "C-TER", "canales_permitidos"] = "sms"          # cambiar canales
    tabla(at, "campanas", c)
    at.run()
    impacto(at)
    cfg = aplicar(at)
    assert [x.id for x in cfg.campanas] == ["C-VCH", "C-TER", "C-OTT", "C-SEG"] and not cfg.campanas[0].activa
    g = parrilla(d, cfg)
    assert con(g, "C-SEG").sum() > 0 and set(g[con(g, "C-SEG")].canal) <= {"whatsapp", "correo", "sms"}
    assert con(g, "C-VCH").sum() == 0
    assert set(g[con(g, "C-TER")].canal) == {"sms"}


def test_columna_nueva_en_una_regla_desde_la_consola(consola, df_ext):
    d, ruta = df_ext
    at = consola
    ir(at, "Base de datos")
    [t for t in at.text_input if t.label == "Ruta del CSV"][0].set_value(ruta)
    [b for b in at.button if b.label == "Usar esta ruta"][0].click().run()
    ir(at, "Cambiar configuración")
    [t for t in at.text_input if t.label.startswith("Nombre")][0].set_value("Terminales solo a clientes VIP")
    [s for s in at.selectbox if s.label == "Alcance"][0].set_value("campana")
    [t for t in at.text_input if t.label.startswith("Campañas, productos")][0].set_value("C-TER")
    [s for s in at.selectbox if s.label == "Columna de la base"][0].set_value("es_vip")     # columna que antes no existia
    [s for s in at.selectbox if s.label.startswith("Excluir si")][0].set_value("==")
    [t for t in at.text_input if t.label.startswith("…este")][0].set_value("0")
    [b for b in at.button if "Agregar" in b.label][0].click().run()
    impacto(at)
    cfg = aplicar(at)
    g = parrilla(d, cfg).merge(d[["id_cliente", "es_vip"]], on="id_cliente")
    assert con(g, "C-TER").sum() > 0 and (g[con(g, "C-TER")].es_vip == 1).all()


# ---------------------------------------------------------------- 5. Canales y cupos
def test_cupos_productos_por_contacto_y_canal_nuevo(consola, df_ext):
    d, ruta = df_ext
    at = consola
    ir(at, "Base de datos")
    [t for t in at.text_input if t.label == "Ruta del CSV"][0].set_value(ruta)
    [b for b in at.button if b.label == "Usar esta ruta"][0].click().run()
    ir(at, "Cambiar configuración")
    ca = tabla(at, "canales")
    ca.loc[ca.id == "asesor", ["cupo", "max_productos"]] = [300, 2]            # cupo menor y 2 productos por llamada
    ca = pd.concat([ca, pd.DataFrame([{"id": "push", "columna_score": "score_canal_push", "cupo": 5000, "max_productos": 2}])],
                   ignore_index=True)
    tabla(at, "canales", ca)
    cm = tabla(at, "campanas")
    cm["canales_permitidos"] = cm["canales_permitidos"] + "|push"
    tabla(at, "campanas", cm)
    at.run()
    impacto(at)
    cfg = aplicar(at)
    g = parrilla(d, cfg)
    assert (g.canal == "asesor").sum() <= 300
    assert (g[g.canal == "asesor"].campana_2.notna()).sum() > 0               # ahora el asesor ofrece dos productos
    assert 0 < (g.canal == "push").sum() <= 5000
