"""Paso 7: cada tipo de cambio que pide negocio se resuelve SOLO modificando la configuracion (ni una linea de codigo)
y la parrilla resultante sigue con 0 violaciones segun el validador independiente."""
import numpy as np
import pandas as pd
import pytest

from nba import comparar, config, run
from nba.config import Campana, Canal, Config, ConfigError, Regla
from nba.validar import validar

DT = {"canales_contactados_mes": str, "productos_ofertados_mes": str}


@pytest.fixture(scope="module")
def df():
    d = pd.read_csv("data/oficial/clientes.csv", dtype=DT).head(20000).copy()
    rng = np.random.default_rng(7)
    d["score_canal_push"] = rng.beta(3, 4, len(d)).round(4)   # columnas nuevas en la base
    d["score_seguros"] = rng.beta(2.5, 4, len(d)).round(4)
    d["es_vip"] = (rng.random(len(d)) < 0.2).astype(int)
    return d


@pytest.fixture(scope="module")
def base():
    c = config.cargar("config_inicial")
    for ch in c.canales:
        ch.cupo //= 5            # misma proporcion de cupos que el volumen de prueba
    return c


@pytest.fixture(scope="module")
def ref(df, base):
    return correr(df, base)


def copia(cfg):
    return Config.model_validate(cfg.model_copy(deep=True).model_dump())


def correr(df, cfg):
    cfg = Config.model_validate(cfg.model_dump())     # revalida: un cambio invalido falla aqui
    g, info = run.correr(df, cfg)
    v = validar(g, df, cfg)
    assert v["violaciones_total"] == 0, v
    return g, info, v, cfg


def con(g, camp):
    return (g.campana_1 == camp) | (g.campana_2 == camp)


# ---------------------------------------------------------------- 1. Campanas
def test_lanzar_campana_nueva(df, base, ref):
    c = copia(base)
    c.campanas.append(Campana(id="C-SEG", nombre="Seguros", producto="SEG", columna_score="score_seguros",
                              valor_negocio=0.9, canales_permitidos=["whatsapp", "correo", "sms"]))
    g, _, v, _ = correr(df, c)
    assert con(g, "C-SEG").sum() > 0
    assert v["valor_esperado"] > ref[2]["valor_esperado"]
    # solo por sus canales permitidos
    assert set(g[con(g, "C-SEG")].canal) <= {"whatsapp", "correo", "sms"}


def test_pausar_campana_sin_borrarla(df, base, ref):
    c = copia(base)
    next(x for x in c.campanas if x.id == "C-VCH").activa = False
    g, _, _, _ = correr(df, c)
    assert con(g, "C-VCH").sum() == 0 and con(ref[0], "C-VCH").sum() > 0


def test_cambiar_canales_de_una_campana(df, base):
    c = copia(base)
    next(x for x in c.campanas if x.id == "C-TER").canales_permitidos = ["sms"]
    g, _, _, _ = correr(df, c)
    assert set(g[con(g, "C-TER")].canal) == {"sms"}


def test_vigencia_de_campana(df, base):
    c = copia(base)
    next(x for x in c.campanas if x.id == "C-OTT").vigencia_fin = pd.Timestamp("2026-10-01").date()  # ya vencida
    g, _, _, _ = correr(df, c)
    assert con(g, "C-OTT").sum() == 0


# ---------------------------------------------------------------- 2. Reglas
def test_crear_regla_sobre_cualquier_columna(df, base):
    c = copia(base)
    c.reglas.append(Regla(id="R90", nombre="Hogar solo a quien usa banca digital", tipo="elegibilidad",
                          alcance_nivel="campana", alcance_valores=["C-VCH"], atributo="usa_banca_digital",
                          operador="==", valor=0))
    g, _, _, _ = correr(df, c)
    m = g[con(g, "C-VCH")].merge(df[["id_cliente", "usa_banca_digital"]], on="id_cliente")
    assert len(m) > 0 and (m.usa_banca_digital == 1).all()


def test_restringir_campana_a_calificaciones(df, base):
    c = copia(base)
    r2 = next(r for r in c.reglas if r.id == "R02")
    r2.valor = ["B", "C", "P"]            # ahora Terminales solo para E y A
    g, _, _, _ = correr(df, c)
    m = g[con(g, "C-TER")].merge(df[["id_cliente", "calificacion_riesgo"]], on="id_cliente")
    assert len(m) > 0 and set(m.calificacion_riesgo) <= {"E", "A"}


def test_regla_para_un_grupo_de_campanas(df, base):
    c = copia(base)
    c.reglas.append(Regla(id="R91", nombre="Solo clientes con 12+ meses", tipo="elegibilidad",
                          alcance_nivel="campana", alcance_valores=["C-VCH", "C-TER"], atributo="antiguedad_meses",
                          operador="<", valor=12))
    g, _, _, _ = correr(df, c)
    jov = df[df.antiguedad_meses < 12].id_cliente
    sub = g[g.id_cliente.isin(jov)]
    assert con(sub, "C-VCH").sum() == 0 and con(sub, "C-TER").sum() == 0
    assert con(sub, "C-OTT").sum() > 0        # OTT no estaba en el grupo


def test_apagar_una_regla(df, base, ref):
    c = copia(base)
    next(r for r in c.reglas if r.id == "R07").activa = False   # quejas
    g, _, _, _ = correr(df, c)
    q = df[df.quejas_90d >= 3].id_cliente
    assert g[g.id_cliente.isin(q)].estado.eq("asignado").sum() > ref[0][ref[0].id_cliente.isin(q)].estado.eq("asignado").sum()


# ---------------------------------------------------------------- 3. Umbrales
def test_subir_umbral_de_producto(df, base):
    c = copia(base)
    c.priorizacion.umbral_score_producto = 0.55
    g, _, _, _ = correr(df, c)
    cols = {"C-VCH": "score_venta_cruzada_hogar", "C-TER": "score_terminales", "C-OTT": "score_upgrade_ott"}
    for camp, col in cols.items():
        m = g[con(g, camp)].merge(df[["id_cliente", col]], on="id_cliente")
        assert (m[col] >= 0.55).all()


def test_subir_umbral_de_canal(df, base):
    c = copia(base)
    c.asignacion.umbral_score_canal = 0.5
    g, _, _, _ = correr(df, c)
    for ch in ("sms", "correo", "whatsapp", "asesor"):
        m = g[g.canal == ch].merge(df[["id_cliente", f"score_canal_{ch}"]], on="id_cliente")
        assert (m[f"score_canal_{ch}"] >= 0.5).all()


# ---------------------------------------------------------------- 4. Prioridad
def test_cambiar_jerarquia_mueve_la_parrilla(df, base, ref):
    c = copia(base)
    c.priorizacion.jerarquia = ["C-OTT", "C-TER", "C-VCH"]     # OTT pasa a ser lo mas importante
    c.priorizacion.alpha = 1.0
    g, _, _, _ = correr(df, c)
    assert con(g, "C-OTT").sum() > con(ref[0], "C-OTT").sum()
    assert con(g, "C-VCH").sum() < con(ref[0], "C-VCH").sum()


def test_peso_modelo_vs_valor_en_linea_base(df, base):
    a, b = copia(base), copia(base)
    for c, w in ((a, (1.0, 0.0, 0.0)), (b, (0.0, 1.0, 0.0))):
        c.asignacion.algoritmo = "codicioso"
        c.priorizacion.pesos.score_producto, c.priorizacion.pesos.valor_negocio, c.priorizacion.pesos.jerarquia = w
    ga, _, va, _ = correr(df, a)
    gb, _, vb, _ = correr(df, b)
    assert not ga[["canal", "campana_1", "campana_2"]].fillna("").equals(gb[["canal", "campana_1", "campana_2"]].fillna(""))


def _prob_media(df, c):
    el, cand, asg = comparar.nucleo(df, c)
    M = comparar.matriz_productos(cand, asg).to_numpy()
    m = comparar.metricas(cand, el, asg, c)
    return float((M * cand.sp).sum() / M.sum()), float((M * cand.valor).sum() / M.sum()), m["valor_esperado"]


def test_pesos_modelo_y_valor_por_defecto_son_la_metrica_pura(df, base):
    assert (base.priorizacion.peso_modelo, base.priorizacion.peso_valor) == (1.0, 1.0)
    explicito = copia(base)
    explicito.priorizacion.peso_modelo, explicito.priorizacion.peso_valor = 1.0, 1.0
    g1, g2 = run.correr(df, base)[0], run.correr(df, explicito)[0]
    assert g1.equals(g2)


def test_mas_peso_al_modelo_prefiere_lo_mas_probable(df, base):
    pm0, _, v0 = _prob_media(df, base)
    c = copia(base)
    c.priorizacion.peso_modelo = 3.0
    pm3, _, v3 = _prob_media(df, c)
    assert pm3 > pm0          # el efecto: se ofrece lo que el modelo cree mas probable
    assert v3 < v0            # el costo: la metrica pura es el maximo
    g, _, _, _ = correr(df, c)
    assert not g[["canal", "campana_1", "campana_2"]].fillna("").equals(
        run.correr(df, base)[0][["canal", "campana_1", "campana_2"]].fillna(""))


def test_mas_peso_al_valor_prefiere_lo_que_mas_vale(df, base):
    _, vn0, v0 = _prob_media(df, base)
    c = copia(base)
    c.priorizacion.peso_valor = 3.0
    _, vn3, v3 = _prob_media(df, c)
    assert vn3 > vn0 and v3 < v0
    correr(df, c)


def test_el_efecto_de_los_pesos_es_monotono(df, base):
    pms = []
    for w in (0.0, 1.0, 3.0):
        c = copia(base)
        c.priorizacion.peso_modelo = w
        pms.append(_prob_media(df, c)[0])
    assert pms[0] < pms[1] < pms[2]


def test_optimo_supera_o_iguala_a_la_linea_base(df, base):
    a, b = copia(base), copia(base)
    a.asignacion.algoritmo, b.asignacion.algoritmo = "codicioso", "optimo"
    assert correr(df, b)[2]["valor_esperado"] >= correr(df, a)[2]["valor_esperado"]


# ---------------------------------------------------------------- 5. Canales y cupos
def test_cambiar_cupo_de_un_canal(df, base):
    c = copia(base)
    next(ch for ch in c.canales if ch.id == "asesor").cupo = 40
    g, _, v, _ = correr(df, c)
    assert (g.canal == "asesor").sum() <= 40 and v["uso_canales"].get("asesor", 0) <= 40


def test_cambiar_productos_por_contacto(df, base, ref):
    c = copia(base)
    next(ch for ch in c.canales if ch.id == "asesor").max_productos = 2
    g, _, _, _ = correr(df, c)
    ase = g[g.canal == "asesor"]
    assert (ase.campana_2 != "").sum() > 0 and (ref[0][ref[0].canal == "asesor"].campana_2 != "").sum() == 0


def test_agregar_un_canal_nuevo(df, base):
    c = copia(base)
    c.canales.append(Canal(id="push", columna_score="score_canal_push", cupo=800, max_productos=2))
    for camp in c.campanas:
        camp.canales_permitidos.append("push")
    g, _, v, _ = correr(df, c)
    assert 0 < (g.canal == "push").sum() <= 800


# ---------------------------------------------------------------- 6. Politica de contacto
def test_cambiar_tope_semanal(df, base):
    c = copia(base)
    c.politica_contacto.max_contactos_semana = 1
    g, _, _, _ = correr(df, c)
    m = g[g.estado == "asignado"].merge(df[["id_cliente", "contactos_semana_actual"]], on="id_cliente")
    assert (m.contactos_semana_actual == 0).all()


def test_cambiar_tope_de_llamadas_de_asesor(df, base):
    c = copia(base)
    next(r for r in c.reglas if r.id == "R11").valor = 1           # maximo 0 llamadas previas
    g, _, _, _ = correr(df, c)
    m = g[g.canal == "asesor"].merge(df[["id_cliente", "contactos_asesor_mes"]], on="id_cliente")
    assert len(m) > 0 and (m.contactos_asesor_mes == 0).all()


# ---------------------------------------------------------------- 7. Datos nuevos
def test_columna_nueva_en_una_regla(df, base):
    c = copia(base)
    c.reglas.append(Regla(id="R92", nombre="Terminales solo a clientes VIP", tipo="elegibilidad",
                          alcance_nivel="campana", alcance_valores=["C-TER"], atributo="es_vip",
                          operador="==", valor=0))
    g, _, _, _ = correr(df, c)
    m = g[con(g, "C-TER")].merge(df[["id_cliente", "es_vip"]], on="id_cliente")
    assert len(m) > 0 and (m.es_vip == 1).all()


def test_columna_inexistente_da_error_claro(df, base):
    c = copia(base)
    c.reglas.append(Regla(id="R93", nombre="x", tipo="elegibilidad", alcance_nivel="global",
                          atributo="columna_que_no_existe", operador="==", valor=1))
    with pytest.raises(ConfigError, match="columna_que_no_existe"):
        run.correr(df, c)


# ---------------------------------------------------------------- invariantes
def test_determinismo(df, base):
    g1 = run.correr(df, base)[0]
    g2 = run.correr(df, base)[0]
    assert g1.equals(g2)


def test_configuracion_invalida_se_rechaza(base):
    d = base.model_dump()
    d["campanas"][0]["canales_permitidos"].append("telepatia")
    with pytest.raises(Exception, match="telepatia"):
        Config.model_validate(d)


def test_metrica_rapida_coincide_con_el_validador(df, base):
    el, cand, asg = comparar.nucleo(df, base)
    m = comparar.metricas(cand, el, asg, base)
    g, _, v, _ = correr(df, base)
    assert abs(m["valor_esperado"] - v["valor_esperado"]) < 0.05
    assert m["clientes_con_accion"] == v["clientes_con_accion"] and m["productos_asignados"] == v["productos_asignados"]
    assert m["jerarquia_pct"] == v["jerarquia_pct"]
