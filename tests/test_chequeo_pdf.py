"""El chequeo independiente (scripts/chequeo_pdf.py, escrito desde el PDF) debe:
  1) dar 0 violaciones en las parrillas que produce el motor,
  2) coincidir con el validador del motor en las metricas,
  3) detectar CADA una de las 16 restricciones cuando se inyecta una violacion."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from nba import config, run
from nba.validar import validar

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("chequeo_pdf", ROOT / "scripts" / "chequeo_pdf.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)
DT = {"canales_contactados_mes": str, "productos_ofertados_mes": str}


@pytest.fixture(scope="module")
def clientes():
    return pd.read_csv(ROOT / "data" / "oficial" / "clientes.csv", dtype=DT)


def leer(ruta):
    return pd.read_csv(ruta, dtype=str, keep_default_na=False).replace("", pd.NA)


@pytest.fixture(scope="module")
def parrilla(clientes):
    return leer(ROOT / "entrega" / "parrilla.csv")


def test_parrilla_entregada_sin_violaciones_y_metricas_coinciden(parrilla, clientes):
    r = chk.chequear(parrilla, clientes)
    assert r["violaciones_total"] == 0, r["violaciones"]
    v = json.load(open(ROOT / "entrega" / "validacion.json"))
    assert abs(r["valor_esperado"] - v["valor_esperado"]) < 0.05
    assert r["clientes_con_accion"] == v["clientes_con_accion"] and r["productos_asignados"] == v["productos_asignados"]
    assert r["jerarquia_pct"] == v["jerarquia_pct"]


@pytest.mark.parametrize("alg", ["codicioso", "optimo"])
def test_ambos_algoritmos_pasan_el_chequeo_del_pdf(clientes, alg):
    df = clientes.head(20000)
    cfg = config.cargar(str(ROOT / "config_inicial"))
    cfg.asignacion.algoritmo = alg
    g, _ = run.correr(df, cfg)
    r = chk.chequear(g.replace("", pd.NA), df)
    assert r["violaciones_total"] == 0, r["violaciones"]
    vm = validar(g, df, cfg)
    assert abs(r["valor_esperado"] - vm["valor_esperado"]) < 0.05 and r["jerarquia_pct"] == vm["jerarquia_pct"]


# ---- inyeccion de violaciones: una por restriccion
def primero(df, mask):
    return df[mask].iloc[0].id_cliente


CASOS = {  # restriccion: (condicion sobre el cliente, canal, campana_1, campana_2)
    "R01": (lambda d: d.en_mora == 1, "sms", "C-OTT", None),
    "R02": (lambda d: d.calificacion_riesgo == "C", "sms", "C-TER", None),
    "R03": (lambda d: d.edad_equipo_meses < 18, "sms", "C-TER", None),
    "R04": (lambda d: d.tiene_hogar == 1, "sms", "C-VCH", None),
    "R05": (lambda d: (d.tiene_netflix == 1) & (d.tiene_amazon_prime == 1) & (d.tiene_win == 1), "sms", "C-OTT", None),
    "R06": (lambda d: d.productos_ofertados_mes.fillna("").str.contains("VCH"), "sms", "C-VCH", None),
    "R07": (lambda d: d.quejas_90d >= 3, "sms", "C-OTT", None),
    "R08": (lambda d: d.score_upgrade_ott < 0.35, "sms", "C-OTT", None),
    "R09": (lambda d: d.autoriza_whatsapp == 0, "whatsapp", "C-OTT", None),
    "R10": (lambda d: d.contactos_asesor_mes >= 2, "asesor", "C-VCH", None),
    "R11": (lambda d: d.score_canal_sms < 0.25, "sms", "C-OTT", None),
    "R12": (lambda d: d.id_cliente.notna(), "asesor", "C-OTT", None),
    "R13": (lambda d: d.id_cliente.notna(), "telepatia", "C-OTT", None),
    "R14": (lambda d: d.id_cliente.notna(), "asesor", "C-VCH", "C-TER"),
    "R15": (lambda d: d.contactos_semana_actual >= 3, "sms", "C-OTT", None),
}


@pytest.mark.parametrize("regla", sorted(CASOS))
def test_el_chequeo_detecta_cada_restriccion(regla, parrilla, clientes):
    cond, canal, c1, c2 = CASOS[regla]
    cid = primero(clientes, cond(clientes))
    g = parrilla.copy()
    i = g.index[g.id_cliente == cid][0]
    g.loc[i, ["estado", "canal", "campana_1", "campana_2"]] = ["asignado", canal, c1, c2 if c2 else pd.NA]
    r = chk.chequear(g, clientes)
    assert r["violaciones"].get(regla, 0) >= 1, (regla, r["violaciones"])


def test_el_chequeo_detecta_cupo_excedido(parrilla, clientes):
    g = parrilla.copy()
    libres = g.index[g.estado == "sin_accion"][:600]
    g.loc[libres, ["estado", "canal", "campana_1"]] = ["asignado", "asesor", "C-OTT"]
    assert chk.chequear(g, clientes)["violaciones"].get("R16", 0) >= 1      # 2.500 + 600 > 2.500


def test_el_chequeo_detecta_errores_de_formato(parrilla, clientes):
    g = parrilla.copy()
    g = pd.concat([g, g.head(1)], ignore_index=True)          # cliente duplicado
    assert chk.chequear(g, clientes)["violaciones"].get("FORMATO_una_fila_por_cliente")
    g2 = parrilla.rename(columns={"razon": "motivo"})
    assert chk.chequear(g2, clientes)["violaciones"].get("FORMATO_columnas")
