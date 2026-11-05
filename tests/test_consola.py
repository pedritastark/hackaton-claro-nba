import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _config_aislada(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config_inicial", tmp_path / "cfg_aislada")
    monkeypatch.setenv("NBA_CONFIG_DIR", str(tmp_path / "cfg_aislada"))


def _app():
    return AppTest.from_file(str(ROOT / "app" / "consola.py"), default_timeout=180)


@pytest.mark.parametrize("pagina", ["Tablero", "Cliente", "Versiones", "Cambiar configuración", "Base de datos"])
def test_paginas_sin_excepciones(pagina):
    at = _app().run()
    at.sidebar.radio[0].set_value(pagina).run()
    assert not at.exception, [e.value for e in at.exception]


def test_cambio_de_umbral_y_vista_previa(tmp_path):
    at = _app().run()
    at.sidebar.radio[0].set_value("Cambiar configuración").run()
    at.slider(key="p_u_prod").set_value(0.5).run()
    [b for b in at.button if "impacto" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    textos = " ".join(m.value for m in at.markdown) + " ".join(str(x.value) for x in at.success)
    assert "0 violaciones" in textos
    d = {m.label: m.delta for m in at.metric if m.delta}
    assert d["Valor esperado"].startswith("-")


def test_crear_regla_aplicar_y_versionar(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config_inicial", tmp_path / "cfg")
    monkeypatch.setenv("NBA_CONFIG_DIR", str(tmp_path / "cfg"))
    at = _app().run()
    at.sidebar.radio[0].set_value("Cambiar configuración").run()
    # regla nueva desde el asistente: excluir a quien tenga 1 o mas quejas
    [t for t in at.text_input if t.label.startswith("Nombre")][0].set_value("Sin venta a clientes con alguna queja")
    [t for t in at.text_input if t.label.startswith("…este")][0].set_value("1")
    [b for b in at.button if "Agregar" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    [b for b in at.button if "impacto" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    d = {m.label: m.delta for m in at.metric if m.delta}
    assert d["Valor esperado"].startswith("-")  # la regla nueva reduce el alcance
    [b for b in at.button if "Aplicar" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    from nba import config, versiones
    cfg = config.cargar(str(tmp_path / "cfg"))
    assert any(r.nombre == "Sin venta a clientes con alguna queja" for r in cfg.reglas)
    assert len(versiones.listar(str(tmp_path / "cfg"))) == 1


def test_cambiar_base_de_datos(tmp_path):
    import pandas as pd
    ruta = tmp_path / "pequena.csv"
    pd.read_csv(ROOT / "data" / "oficial" / "clientes.csv").head(300).to_csv(ruta, index=False)
    at = _app().run()
    at.sidebar.radio[0].set_value("Base de datos").run()
    [t for t in at.text_input if t.label == "Ruta del CSV"][0].set_value(str(ruta))
    [b for b in at.button if b.label == "Usar esta ruta"][0].click().run()
    assert at.session_state["db_ruta"] == str(ruta)
    assert any("300" in m.value for m in at.metric)
    at.sidebar.radio[0].set_value("Tablero").run()
    assert not at.exception, [e.value for e in at.exception]


def test_pesos_modelo_valor_desde_la_consola():
    at = _app().run()
    at.sidebar.radio[0].set_value("Cambiar configuración").run()
    at.slider(key="p_peso_modelo").set_value(3.0).run()
    [b for b in at.button if "impacto" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    d = {m.label: m.delta for m in at.metric if m.delta}
    assert d["Valor esperado"].startswith("-")      # alejarse de la metrica pura cuesta valor
    cambios = {m.label: m.value for m in at.metric if m.label.startswith("Cambian")}
    assert int(cambios["Cambian de productos"]) + int(cambios["Cambian de canal"]) > 0


def test_configuracion_invalida_explica_y_se_puede_restaurar(tmp_path):
    import os
    import yaml
    cfg = Path(os.environ["NBA_CONFIG_DIR"])
    datos = yaml.safe_load((cfg / "parametros.yaml").read_text(encoding="utf-8"))
    datos["priorizacion"]["pesos"] = {"score_producto": 0.0, "valor_negocio": 0.0, "jerarquia": 0.0}
    (cfg / "parametros.yaml").write_text(yaml.safe_dump(datos), encoding="utf-8")
    at = _app().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("no es válida" in h.value for h in at.header)
    texto = " ".join(m.value for m in at.markdown)
    assert "priorizacion" in texto and "sumar 1" in texto            # dice QUE campo falla y por que
    [b for b in at.button if "Restaurar" in b.label][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not any("no es válida" in h.value for h in at.header)    # la consola vuelve a abrir
    from nba import config
    assert config.cargar(str(cfg)).priorizacion.pesos.score_producto == 0.6
    assert len(list((cfg / "respaldo").iterdir())) == 1              # quedo un respaldo de la invalida


def test_borrador_invalido_explica_el_problema():
    at = _app().run()
    at.sidebar.radio[0].set_value("Cambiar configuración").run()
    for k in ("p_w_score", "p_w_valor", "p_w_jer"):
        at.number_input(key=k).set_value(0.0).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("borrador no es válido" in e.value for e in at.error)
    assert "todos cero" in " ".join(m.value for m in at.markdown)


def test_tablero_muestra_estado_cupos_y_embudo_correctos():
    import re
    at = _app().run()
    assert not at.exception, [e.value for e in at.exception]
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(m.value for m in at.markdown)))
    assert "Parrilla válida · 0 violaciones" in txt and "configuración inicial del reto" in txt
    assert "algoritmo óptimo" in txt and "+6,8 % de valor esperado" in txt
    # cupos: asesor y WhatsApp llenos, con la estimacion por cada 100 cupos
    assert "Asesor 2.500 / 2.500 · 100 % Lleno" in txt and "WhatsApp 15.000 / 15.000 · 100 % Lleno" in txt
    assert "cada 100 cupos adicionales" in txt
    # embudo: mismas cifras del resumen validado de la entrega
    for esperado in ("100.000 · 100,0 %", "98.612 · 98,6 %", "63.176 · 63,2 %", "60.807 · 60,8 %", "60.422 · 60,4 %",
                     "− 1.388", "− 35.436", "− 2.369", "− 385"):
        assert esperado in txt, esperado
    d = {m.label: m.delta for m in at.metric}
    assert d["Valor esperado"].startswith("+698,4") and "(+6,8 %)" in d["Valor esperado"]


def _texto_tablero(at):
    import re
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", " ".join(m.value for m in at.markdown)))


def test_tablero_composicion_alertas_y_ejemplos():
    at = _app().run()
    assert not at.exception, [e.value for e in at.exception]
    txt = _texto_tablero(at)
    # alerta de cupos llenos (sin historial no hay alertas de comparacion)
    assert "Para revisar" in txt and "WhatsApp y Asesor están llenos" in txt
    assert "frente a «" not in txt.split("Para revisar")[1].split("Uso de cupos")[0]
    # composicion: el total por campana y canal suma los 76.841 productos asignados
    tablas = [d.value for d in at.dataframe]
    comp = next(t for t in tablas if "Total" in t.columns and "WhatsApp" in t.columns)
    assert int(comp["Total"].sum()) == 76841
    assert set(comp.columns) >= {"WhatsApp", "Correo", "SMS", "Asesor", "Total"}
    # de la cifra al cliente: un boton por situacion
    botones = [b for b in at.button if b.label == "Ver un ejemplo"]
    assert len(botones) >= 4


def test_ver_un_ejemplo_lleva_a_la_explicacion_del_cliente():
    at = _app().run()
    botones = [b for b in at.button if b.label == "Ver un ejemplo"]
    botones[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.sidebar.radio[0].value == "Cliente"
    cid = at.session_state["cliente_sel"]
    assert [t for t in at.text_input if t.label == "Id del cliente"][0].value == cid
    assert "Explicación por cliente" in " ".join(h.value for h in at.header)
    assert len(at.success) + len(at.warning) >= 1                    # la frase para el asesor de ese cliente


def test_comparar_con_la_version_anterior(tmp_path):
    import os
    from nba import config, versiones
    cfg = Path(os.environ["NBA_CONFIG_DIR"])
    c1 = config.cargar(str(cfg))
    c1.priorizacion.umbral_score_producto = 0.45
    versiones.guardar_version(c1, str(cfg), "Umbral 0,45")
    c2 = config.cargar(str(cfg))
    c2.priorizacion.umbral_score_producto = 0.50
    versiones.guardar_version(c2, str(cfg), "Umbral 0,50")
    at = _app().run()
    assert not at.exception, [e.value for e in at.exception]
    opciones = at.radio(key="comparar_con").options
    assert opciones == ["Baseline", "Versión anterior · Umbral 0,45"]
    frente_baseline = {m.label: m.delta for m in at.metric}
    at.radio(key="comparar_con").set_value(opciones[1]).run()
    assert not at.exception, [e.value for e in at.exception]
    frente_anterior = {m.label: m.delta for m in at.metric}
    assert frente_anterior["Valor esperado"] != frente_baseline["Valor esperado"]
    assert frente_anterior["Valor esperado"].startswith("−")          # 0,50 produce menos valor que 0,45
    assert "frente a «Umbral 0,45»" in _texto_tablero(at)
    assert "El valor esperado cambió" in _texto_tablero(at)
