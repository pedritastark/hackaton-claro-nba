"""Requisitos del diccionario oficial (docs/oficial/) y regresion contra las cifras oficiales de la linea base."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from nba import comparar, config, run
from nba.config import Config, Priorizacion, Regla
from nba.validar import validar

ROOT = Path(__file__).resolve().parent.parent
DT = {"canales_contactados_mes": str, "productos_ofertados_mes": str}
spec = importlib.util.spec_from_file_location("chequeo_pdf", ROOT / "scripts" / "chequeo_pdf.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)


@pytest.fixture(scope="module")
def real():
    return pd.read_csv(ROOT / "data" / "oficial" / "clientes.csv", dtype=DT)


@pytest.fixture(scope="module")
def cfg0():
    return config.cargar(str(ROOT / "config_inicial"))


def copia(c):
    return Config.model_validate(c.model_copy(deep=True).model_dump())


# ------------------------------------------------ regresion contra las cifras oficiales (PDF del reto, p. 6)
def test_la_linea_base_reproduce_las_cifras_oficiales(real, cfg0):
    c = copia(cfg0)
    c.asignacion.algoritmo = "codicioso"
    g, _ = run.correr(real, c)
    v = validar(g, real, c)
    assert v["violaciones_total"] == 0
    assert v["clientes_con_accion"] == 55393                      # oficial: 55.393
    assert abs(v["valor_esperado"] - 10241.5) < 0.5               # oficial: 10.241,5
    assert abs(v["productos_asignados"] - 70443) <= 2             # oficial: 70.443
    assert abs(v["jerarquia_pct"] - 99.7) < 0.1                   # oficial: 99,7 %


def test_el_motor_optimo_supera_la_linea_base_con_datos_reales(real, cfg0):
    g, _ = run.correr(real, cfg0)
    v = validar(g, real, cfg0)
    assert v["violaciones_total"] == 0 and v["valor_esperado"] > 10241.5 * 1.05
    r = chk.chequear(g.replace("", pd.NA), real)                  # chequeo independiente escrito desde el PDF
    assert r["violaciones_total"] == 0 and abs(r["valor_esperado"] - v["valor_esperado"]) < 0.05


# ------------------------------------------------ alcance de reglas: global, campana, producto, objetivo, canal
def test_regla_por_producto(real, cfg0):
    df = real.head(20000)
    c = copia(cfg0)
    c.reglas.append(Regla(id="R90", nombre="OTT solo con banca digital", tipo="elegibilidad", alcance_nivel="producto",
                          alcance_valores=["OTT"], atributo="usa_banca_digital", operador="==", valor=0))
    g, _ = run.correr(df, c)
    assert validar(g, df, c)["violaciones_total"] == 0
    m = g[(g.campana_1 == "C-OTT") | (g.campana_2 == "C-OTT")].merge(df[["id_cliente", "usa_banca_digital"]], on="id_cliente")
    assert len(m) > 0 and (m.usa_banca_digital == 1).all()


def test_regla_por_objetivo(real, cfg0):
    df = real.head(20000)
    c = copia(cfg0)
    c.reglas.append(Regla(id="R91", nombre="Upgrade solo estratos 3 o mas", tipo="elegibilidad", alcance_nivel="objetivo",
                          alcance_valores=["Upgrade"], atributo="estrato", operador="<", valor=3))
    g, _ = run.correr(df, c)
    assert validar(g, df, c)["violaciones_total"] == 0
    m = g[(g.campana_1 == "C-OTT") | (g.campana_2 == "C-OTT")].merge(df[["id_cliente", "estrato"]], on="id_cliente")
    assert len(m) > 0 and (m.estrato >= 3).all()
    # y el mismo objetivo no toca a las otras campanas
    bajos = df[df.estrato < 3].id_cliente
    g2 = g[g.id_cliente.isin(bajos)]
    assert ((g2.campana_1 == "C-VCH") | (g2.campana_1 == "C-TER")).sum() > 0


def test_alcance_con_valores_inexistentes_se_rechaza(cfg0):
    d = cfg0.model_dump()
    d["reglas"].append(dict(id="R92", nombre="x", tipo="elegibilidad", alcance_nivel="objetivo", alcance_valores=["Inexistente"],
                            atributo="estrato", operador="<", valor=3))
    with pytest.raises(ValidationError, match="objetivos inexistentes"):
        Config.model_validate(d)


# ------------------------------------------------ desempate entre campanas
def _cliente_empatado(real):
    r = real.iloc[[0]].copy()
    r.loc[:, ["en_mora", "dias_mora", "quejas_90d", "tiene_hogar", "arpu_hogar", "contactos_semana_actual",
              "contactos_asesor_mes", "edad_equipo_meses", "cantidad_ott", "tiene_netflix", "tiene_amazon_prime", "tiene_win"]] = \
        [0, 0, 0, 0, 0, 0, 0, 40, 3, 1, 1, 1]
    r["calificacion_riesgo"] = "E"
    r["productos_ofertados_mes"] = np.nan
    r["autoriza_sms"] = r["autoriza_correo"] = r["autoriza_whatsapp"] = 0       # solo queda el asesor
    r["score_canal_asesor"] = 0.9
    r["score_venta_cruzada_hogar"] = r["score_terminales"] = 0.6              # empate exacto en score
    r["score_upgrade_ott"] = 0.1
    return r


def test_desempate_decide_entre_campanas_empatadas(real, cfg0):
    df = _cliente_empatado(real)
    a = copia(cfg0)
    a.asignacion.algoritmo = "codicioso"
    a.priorizacion.pesos.score_producto, a.priorizacion.pesos.valor_negocio, a.priorizacion.pesos.jerarquia = 1.0, 0.0, 0.0
    b = copia(a)
    a.priorizacion.desempate = ["valor_negocio"]                       # VCH vale 1,0 y TER 0,8
    b.priorizacion.desempate = ["jerarquia"]
    b.priorizacion.jerarquia = ["C-TER", "C-VCH", "C-OTT"]            # TER primero en la jerarquia
    ga, gb = run.correr(df, a)[0], run.correr(df, b)[0]
    assert ga.loc[0, "campana_1"] == "C-VCH" and gb.loc[0, "campana_1"] == "C-TER"
    assert ga.loc[0, "canal"] == "asesor" and gb.loc[0, "canal"] == "asesor"


def test_campana_1_es_la_de_mayor_puntaje(real, cfg0):
    df = real.head(20000)
    c = copia(cfg0)
    for ch in c.canales:
        ch.cupo //= 5
    el, cand, asg = comparar.nucleo(df, c)
    par = (asg.paq >= 0).sum(axis=1) == 2
    assert par.sum() > 1000
    i = np.where(par)[0]
    p1 = cand.puntaje[i, asg.paq[i, 0]]
    p2 = cand.puntaje[i, asg.paq[i, 1]]
    assert (p1 >= p2 - 1e-12).all()


# ------------------------------------------------ parametros del diccionario
def test_los_pesos_deben_sumar_uno():
    ok = Priorizacion(jerarquia=["C-VCH"], pesos=dict(score_producto=0.5, valor_negocio=0.3, jerarquia=0.2))
    assert ok.pesos.valor_negocio == 0.3
    for malos in (dict(score_producto=0, valor_negocio=0, jerarquia=0), dict(score_producto=0.6, valor_negocio=0.6, jerarquia=0.2)):
        with pytest.raises(ValidationError, match="deben sumar 1"):
            Priorizacion(jerarquia=["C-VCH"], pesos=malos)


def test_desempate_con_criterio_desconocido_se_rechaza():
    with pytest.raises(ValidationError, match="desempate"):
        Priorizacion(jerarquia=["C-VCH"], desempate=["suerte"])


def test_mas_de_un_canal_por_cliente_se_rechaza_con_mensaje_claro(cfg0):
    d = cfg0.model_dump()
    d["politica_contacto"]["canales_por_cliente"] = 2
    with pytest.raises(ValidationError, match="canales_por_cliente"):
        Config.model_validate(d)


def test_criterio_de_canal_orden_de_preferencia_tiene_efecto_en_el_optimo(real, cfg0):
    df = real.head(20000)
    base = copia(cfg0)
    for ch in base.canales:
        ch.cupo //= 5
    por_orden = copia(base)
    por_orden.asignacion.criterio_canal = "orden_preferencia"
    por_orden.asignacion.orden_preferencia = ["sms", "correo", "whatsapp", "asesor"]
    g0, g1 = run.correr(df, base)[0], run.correr(df, por_orden)[0]
    assert validar(g1, df, por_orden)["violaciones_total"] == 0
    cupo_sms = next(c.cupo for c in por_orden.canales if c.id == "sms")
    assert (g1.canal == "sms").sum() > (g0.canal == "sms").sum()          # el canal preferido pasa a dominar
    assert (g1.canal == "sms").sum() == cupo_sms or (g1.canal == "sms").sum() > 0.9 * cupo_sms
    assert (g1.canal == "whatsapp").sum() < (g0.canal == "whatsapp").sum()
