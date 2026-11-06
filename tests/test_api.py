"""Pruebas de la API de la consola (la que usa React). Corren sobre la base oficial y una copia temporal de config_inicial."""
import copy
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def cliente(tmp_path_factory):
    cfg_dir = tmp_path_factory.mktemp("cfg")
    for f in (ROOT / "config_inicial").glob("*.yaml"):
        shutil.copy(f, cfg_dir / f.name)
    mp = pytest.MonkeyPatch()
    mp.setenv("NBA_CONFIG_DIR", str(cfg_dir))
    mp.setenv("NBA_CLIENTES", str(ROOT / "data" / "oficial" / "clientes.csv"))
    from api import servicio
    servicio._estado["ruta"] = None
    from api.main import app
    yield TestClient(app)
    mp.undo()


def test_estado_y_configuracion(cliente):
    e = cliente.get("/api/estado").json()
    assert e["base"]["existe"] and e["base"]["filas"] == 100000
    assert e["configuracion"] == "configuración inicial del reto"
    c = cliente.get("/api/config").json()
    assert {x["id"] for x in c["config"]["canales"]} == {"asesor", "whatsapp", "correo", "sms"}
    assert "operadores" in c and "calificacion_riesgo" in c["columnas"]
    assert c["derivados"]["tope_llamadas"] == 2
    assert c["derivados"]["calificaciones"]["C-TER"] == ["E", "A", "B"]


def test_revisar_borrador_valido_e_invalido(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    ok = cliente.post("/api/config/revisar", json={"config": cfg}).json()
    assert ok["ok"] and ok["igual_a_vigente"] and ok["frases"]
    malo = copy.deepcopy(cfg)
    malo["priorizacion"]["pesos"] = {"score_producto": 0, "valor_negocio": 0, "jerarquia": 0}
    r = cliente.post("/api/config/revisar", json={"config": malo}).json()
    assert not r["ok"] and "sumar 1" in r["errores"][0]["mensaje"]


def test_controles_directos(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    c2 = cliente.post("/api/borrador/llamadas", json={"config": cfg, "valor": 5}).json()["config"]
    assert cliente.post("/api/config/revisar", json={"config": c2}).json()["derivados"]["tope_llamadas"] == 5
    c3 = cliente.post("/api/borrador/calificaciones",
                      json={"config": cfg, "campana": "C-TER", "permitidas": ["E", "A"]}).json()["config"]
    assert cliente.post("/api/config/revisar", json={"config": c3}).json()["derivados"]["calificaciones"]["C-TER"] == ["E", "A"]
    todas = cliente.post("/api/borrador/calificaciones",
                         json={"config": cfg, "campana": "C-OTT", "permitidas": ["E", "A", "B", "C", "P"]}).json()["config"]
    assert not any(r["id"] == "CAL-C-OTT" for r in todas["reglas"])


def test_tablero_replica_resultados_oficiales(cliente):
    t = cliente.get("/api/tablero").json()
    assert t["estado"]["violaciones_total"] == 0
    assert t["metricas"]["valor_esperado"] == pytest.approx(10940.0, abs=1.0)
    assert t["baseline"]["valor_esperado"] == pytest.approx(10241.5, abs=1.0)
    assert t["metricas"]["clientes_con_accion"] == 60422
    assert [e["nombre"] for e in t["embudo"]][0] == "Clientes en la base" and t["embudo"][0]["cantidad"] == 100000
    assert t["reglas"] and t["composicion"] and t["casos"]
    assert all(c["usado"] <= c["cupo"] for c in t["cupos"])
    assert t["optimalidad"]["estado"] == "optimo"
    assert t["precios_sombra"]["asesor"] == pytest.approx(0.0925, abs=0.001) and t["precios_sombra"]["sms"] == 0
    assert all("texto" in a for a in t["alertas"]) and any(a.get("cliente") for a in t["alertas"])


def test_impacto_aplicar_y_versiones(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    nuevo = copy.deepcopy(cfg)
    for ch in nuevo["canales"]:
        if ch["id"] == "whatsapp":
            ch["cupo"] += 100
    imp = cliente.post("/api/impacto", json={"config": nuevo}).json()
    assert imp["validacion"]["violaciones_total"] == 0
    assert imp["comparacion"]["delta_valor"] > 0
    assert imp["despues"]["cupo_canales"]["whatsapp"] == imp["antes"]["cupo_canales"]["whatsapp"] + 100
    ap = cliente.post("/api/aplicar", json={"config": nuevo, "etiqueta": "Mas cupo whatsapp"}).json()
    assert ap["version"].endswith("Mas-cupo-whatsapp")
    vs = cliente.get("/api/versiones").json()
    assert vs[0]["etiqueta"] == "Mas cupo whatsapp" and vs[0]["metricas"]["valor_esperado"] > 10940
    assert cliente.get("/api/estado").json()["configuracion"] == "Mas cupo whatsapp"
    v = cliente.get(f"/api/versiones/{vs[0]['version']}").json()["config"]
    assert next(c for c in v["canales"] if c["id"] == "whatsapp")["cupo"] == 15100
    # ahora el tablero compara contra la version anterior (configuracion inicial)
    assert cliente.get("/api/tablero").json()["anterior"]["etiqueta"] == "configuración inicial del reto"


def test_aplicar_rechaza_borrador_invalido(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    cfg["priorizacion"]["umbral_score_producto"] = "mucho"
    r = cliente.post("/api/aplicar", json={"config": cfg})
    assert r.status_code == 422 and r.json()["detalle"]


def test_cliente_y_situaciones(cliente):
    sit = cliente.get("/api/situaciones").json()
    assert sum(x["cantidad"] for x in sit) == 100000
    ids = cliente.get("/api/clientes", params={"situacion": sit[0]["clave"], "limite": 5}).json()
    assert len(ids) == 5
    d = cliente.get(f"/api/cliente/{ids[0]}").json()
    assert d["registro"]["id_cliente"] == ids[0] and d["frase_asesor"] and d["frase"]
    assert cliente.get("/api/cliente/NO_EXISTE").status_code == 404


def test_base_de_datos(cliente):
    b = cliente.get("/api/base").json()
    assert b["filas"] == 100000 and b["columnas"] == 45 and b["ids_unicos"] and b["faltan"] == []
    assert len(b["vista_previa"]) == 50 and any(p["usada"] for p in b["perfil"])
    assert cliente.post("/api/base/ruta", json={"ruta": "/no/existe.csv"}).status_code == 404


def test_parrilla_csv(cliente):
    r = cliente.get("/api/parrilla.csv")
    assert r.status_code == 200
    lineas = r.text.splitlines()
    assert lineas[0] == "id_cliente,estado,canal,campana_1,campana_2,razon" and len(lineas) == 100001


def test_optimalidad_depende_de_la_prioridad_configurada(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    alterado = copy.deepcopy(cfg)
    alterado["priorizacion"]["alpha"] = 0.3
    from api import servicio
    from nba.config import Config
    info = {"algoritmo": "optimo", "lp_entero": True}
    assert servicio.optimalidad(Config.model_validate(alterado), info)["estado"] == "optimo_configurado"
    assert servicio.optimalidad(Config.model_validate(cfg), {"algoritmo": "codicioso"})["estado"] == "heuristica"
    assert servicio.optimalidad(Config.model_validate(cfg), {"algoritmo": "optimo", "lp_entero": False})["estado"] == "aproximado"


def _esperar(cliente, tid, timeout=300):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        e = cliente.get(f"/api/trabajos/{tid}").json()
        if e["estado"] != "corriendo":
            return e
        time.sleep(1)
    raise AssertionError("el trabajo no termino")


def test_escenarios_guardar_comparar_y_borrar(cliente):
    cfg = cliente.get("/api/config").json()["config"]
    nuevo = copy.deepcopy(cfg)
    antes = next(c for c in nuevo["canales"] if c["id"] == "whatsapp")["cupo"]   # depende de las pruebas previas
    next(c for c in nuevo["canales"] if c["id"] == "whatsapp")["cupo"] += 100
    miles = lambda x: f"{x:,}".replace(",", ".")
    r = cliente.post("/api/escenarios", json={"nombre": "WhatsApp mas 100", "config": nuevo})
    assert r.status_code == 200
    eid = r.json()["id"]
    lista = cliente.get("/api/escenarios").json()
    esc = next(e for e in lista if e["id"] == eid)
    assert esc["nombre"] == "WhatsApp mas 100" and esc["cambios"] == [f"Cupo de WhatsApp: {miles(antes)} → {miles(antes + 100)}"]
    assert next(c for c in cliente.get(f"/api/escenarios/{eid}").json()["config"]["canales"] if c["id"] == "whatsapp")["cupo"] == antes + 100
    job = cliente.post("/api/escenarios/comparar", json={"ids": [eid]}).json()["trabajo"]
    fin = _esperar(cliente, job)
    assert fin["estado"] == "listo" and [p["id"] for p in fin["parcial"]] == ["vigente", eid]
    vig, esc_res = fin["parcial"]
    assert vig["violaciones_total"] == 0 and esc_res["violaciones_total"] == 0
    assert esc_res["metricas"]["valor_esperado"] - vig["metricas"]["valor_esperado"] == pytest.approx(6.5, abs=1.5)
    assert cliente.delete(f"/api/escenarios/{eid}").status_code == 200
    assert not any(e["id"] == eid for e in cliente.get("/api/escenarios").json())
    assert cliente.get("/api/escenarios/mal-id").status_code == 404          # id con formato invalido
    assert cliente.get("/api/escenarios/..%2Fhack").status_code == 404
    r404 = cliente.get("/api/no-existe")
    assert r404.status_code == 404 and r404.headers["content-type"].startswith("application/json")
    assert cliente.post("/api/escenarios", json={"nombre": " ", "config": cfg}).status_code == 422


def test_sensibilidad_de_cupos(cliente):
    from api import servicio
    base = cliente.get("/api/tablero").json()["metricas"]["valor_esperado"]
    # canal lleno: subir suma valor, bajar lo resta, y el punto 1,0 coincide con el tablero
    t = servicio.sensibilidad("whatsapp", (0.75, 1.0, 1.25))["trabajo"]
    fin = _esperar(cliente, t)
    v = {p["factor"]: p for p in fin["parcial"]}
    assert fin["estado"] == "listo" and v[1.0]["valor"] == pytest.approx(base)
    assert v[0.75]["valor"] < base < v[1.25]["valor"] and v[0.75]["calculado"] and v[1.25]["calculado"]
    # canal no lleno: ampliar o reducir sin bajar de lo que usa no cambia nada y no se recalcula
    t = servicio.sensibilidad("sms", (0.9, 1.0, 1.5))["trabajo"]
    fin = _esperar(cliente, t)
    assert all(p["valor"] == pytest.approx(base) and not p["calculado"] for p in fin["parcial"])
    assert cliente.post("/api/sensibilidad", json={"canal": "no_existe"}).status_code == 404


def test_datos_del_cliente_y_calidad_de_la_base(cliente):
    d = cliente.get("/api/cliente/CL000003").json()
    en_mora = next(x for x in d["datos"] if x["columna"] == "en_mora")
    assert en_mora["reglas"] == ["R01"] and en_mora["valor"] in (0, 1)
    assert any(x["columna"].startswith("score_") for x in d["datos"])
    b = cliente.get("/api/base").json()
    titulos = {c["titulo"]: c for c in b["calidad"]}
    assert titulos["Identificadores únicos"]["ok"] and titulos["Puntajes y probabilidades entre 0 y 1"]["ok"]
    assert titulos["Formato de productos_ofertados_mes (valores separados por |)"]["ok"]
    edad = next(p for p in b["perfil"] if p["columna"] == "edad")
    assert edad["min"] == 18 and edad["max"] == 80
