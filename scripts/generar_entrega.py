"""Genera la entrega final en entrega/: parrilla, explicaciones, resumen, validacion y comparaciones.
Uso: .venv/bin/python scripts/generar_entrega.py [clientes.csv] [config]
Por defecto: datos oficiales (data/oficial/clientes.csv) y la configuracion inicial del reto (config_inicial/)."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pandas as pd

from nba import comparar, config, run
from nba.validar import validar

clientes = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "oficial" / "clientes.csv")
cfg_dir = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / "config_inicial")   # configuracion inicial del reto
out = ROOT / "entrega"
out.mkdir(exist_ok=True)

df = pd.read_csv(clientes, dtype=run.DTYPES)
cfg = config.cargar(cfg_dir)
t = time.time()
g, info = run.correr(df, cfg, str(out / "explicaciones.jsonl.gz"))
seg = time.time() - t
g.to_csv(out / "parrilla.csv", index=False)
(out / "resumen.json").write_text(json.dumps(info["resumen"], ensure_ascii=False, indent=2), encoding="utf-8")
v = validar(g, df, cfg)
v["segundos_motor_con_explicaciones"] = round(seg, 1)
v["algoritmo"] = cfg.asignacion.algoritmo
v["alpha"] = cfg.priorizacion.alpha
v["precio_cupo"] = info.get("precio_sombra")
(out / "validacion.json").write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def corrida(c):
    t0 = time.time()
    el, cand, asg = comparar.nucleo(df, c)
    m = comparar.metricas(cand, el, asg, c)
    m.pop("valor_por_cliente")
    m["segundos"] = round(time.time() - t0, 1)
    return m

comp = {}
b = cfg.model_copy(deep=True)
b.asignacion.algoritmo, b.priorizacion.alpha = "codicioso", 0.0
comp["linea_base_codiciosa"] = corrida(b)
comp["motor_optimo"] = corrida(cfg)
sens = {}
for a in (0.0, 0.25, 0.5, 0.75, 1.0):
    c = cfg.model_copy(deep=True)
    c.priorizacion.alpha = a
    sens[str(a)] = corrida(c)
comp["sensibilidad_alpha"] = sens
(out / "comparacion.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")
cfg_snap = out / "config"
config.guardar(cfg, str(cfg_snap))
print(json.dumps({"violaciones": v["violaciones_total"], "valor": v["valor_esperado"], "clientes": v["clientes_con_accion"],
                  "productos": v["productos_asignados"], "jerarquia": v["jerarquia_pct"], "seg": round(seg, 1)}))
