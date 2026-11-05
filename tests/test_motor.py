import glob
import pandas as pd
import pytest
from nba import config, run, reglas
from nba.validar import validar

KIT = glob.glob("extraido/*/")[0]
DT = {"canales_contactados_mes": str, "productos_ofertados_mes": str}


@pytest.fixture(scope="module")
def cfg():
    return config.cargar("config_inicial")


@pytest.fixture(scope="module")
def casos():
    return pd.read_csv(KIT + "casos_ejemplo_clientes.csv", dtype=DT)


def test_operadores():
    df = pd.DataFrame({"a": [1, 5, None], "s": ["C", "E", None], "l": ["VCH|TER", "", None]})
    assert reglas.evaluar(df, "a", ">=", 5).tolist() == [False, True, False]
    assert reglas.evaluar(df, "a", "!=", 1).tolist() == [False, True, False]  # faltante no cumple
    assert reglas.evaluar(df, "s", "en", ["C", "P"]).tolist() == [True, False, False]
    assert reglas.evaluar(df, "l", "contiene", "$producto", "TER").tolist() == [True, False, False]
    with pytest.raises(config.ConfigError):
        reglas.evaluar(df, "no_existe", "==", 1)


def test_casos_ejemplo_con_whatsapp_agotado(cfg, casos):
    """En la corrida oficial el cupo de WhatsApp ya estaba agotado cuando llegaba CL000741: se simula con cupo 0."""
    cfg = cfg.model_copy(deep=True)
    cfg.asignacion.algoritmo = "codicioso"
    next(c for c in cfg.canales if c.id == "whatsapp").cupo = 0
    g, _ = run.correr(casos, cfg)
    esp = pd.read_csv(KIT + "casos_ejemplo_parrilla_esperada.csv").fillna("").set_index("id_cliente")
    g = g.set_index("id_cliente")
    for col in ("estado", "canal", "campana_1", "campana_2"):
        assert g[col].tolist() == esp.loc[g.index, col].tolist(), col


def test_validador_detecta_violaciones(cfg, casos):
    g, _ = run.correr(casos, cfg)
    assert validar(g, casos, cfg)["violaciones_total"] == 0
    mal = g.copy()
    mal.loc[mal.id_cliente == "CL000020", ["estado", "canal", "campana_1"]] = ["asignado", "sms", "C-TER"]  # en mora
    mal.loc[mal.id_cliente == "CL000039", ["estado", "canal", "campana_1", "campana_2"]] = ["asignado", "asesor", "C-VCH", "C-OTT"]  # asesor con 2 productos
    v = validar(mal, casos, cfg)["violaciones"]
    assert v["R01"] >= 1 and v["TOPE_PRODUCTOS"] >= 1


@pytest.mark.parametrize("alg", ["codicioso", "optimo"])
def test_cero_violaciones_y_cupos(cfg, alg):
    df = pd.read_csv("data/oficial/clientes.csv", dtype=DT).head(20000)
    c = cfg.model_copy(deep=True)
    c.asignacion.algoritmo = alg
    for ch in c.canales:
        ch.cupo //= 5
    g, _ = run.correr(df, c)
    assert validar(g, df, c)["violaciones_total"] == 0


def test_cambio_de_umbral_sin_codigo(cfg, casos):
    base, _ = run.correr(casos, cfg)
    c = cfg.model_copy(deep=True)
    c.priorizacion.umbral_score_producto = 0.7
    nuevo, _ = run.correr(casos, c)
    assert (nuevo.estado == "asignado").sum() < (base.estado == "asignado").sum()


def test_explicaciones_coherentes_con_parrilla(cfg, tmp_path):
    import json
    df = pd.read_csv("data/oficial/clientes.csv", dtype=DT).head(5000)
    ruta = str(tmp_path / "e.jsonl")
    g, info = run.correr(df, cfg, ruta)
    regs = [json.loads(x) for x in open(ruta, encoding="utf-8")]
    assert len(regs) == len(df)
    v = validar(g, df, cfg)
    assert abs(sum(r["valor_esperado"] for r in regs) - v["valor_esperado"]) < 0.05
    for r, (_, fila) in zip(regs, g.iterrows()):
        assert r["id_cliente"] == fila.id_cliente and r["estado"] == fila.estado
        assert (r["canal"] or "") == (fila.canal or "")
        assert r["estado"] == "asignado" or r["motivo_sin_accion"]["categoria"] in (
            "tope_semanal", "sin_campana_elegible", "sin_canal_habilitado", "sin_cupo")
        assert fila.razon
    cupos = info["resumen"]["cupos"]
    assert all(c["usado"] <= c["cupo"] for c in cupos.values())
