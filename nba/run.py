"""Corre el orquestador. Uso: python -m nba.run --clientes data/oficial/clientes.csv --config config_inicial --out parrilla.csv"""
import argparse
import time

import pandas as pd

from nba import asignacion, candidatos, config, elegibilidad, explicar, parrilla

DTYPES = {"canales_contactados_mes": str, "productos_ofertados_mes": str}


def correr(df, cfg, jsonl=None):
    el = elegibilidad.calcular(df, cfg)
    cand = candidatos.construir(df, cfg, el)
    asg = asignacion.asignar(cand, cfg)
    razones, resumen = explicar.procesar(df, cfg, el, cand, asg, jsonl)
    return parrilla.construir(df, cfg, el, cand, asg, razones), {**asg.info, "resumen": resumen}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clientes", default="data/oficial/clientes.csv")
    ap.add_argument("--config", default="config")
    ap.add_argument("--out", default="parrilla.csv")
    ap.add_argument("--algoritmo", choices=["optimo", "codicioso"])
    ap.add_argument("--alpha", type=float)
    ap.add_argument("--explicaciones", help="ruta de explicaciones.jsonl (un registro por cliente)")
    ap.add_argument("--resumen", help="ruta de resumen.json (embudo, cupos, costo de cupo)")
    a = ap.parse_args()
    cfg = config.cargar(a.config)
    if a.algoritmo:
        cfg.asignacion.algoritmo = a.algoritmo
    if a.alpha is not None:
        cfg.priorizacion.alpha = a.alpha
    df = pd.read_csv(a.clientes, dtype=DTYPES)
    t = time.time()
    g, info = correr(df, cfg, a.explicaciones)
    g.to_csv(a.out, index=False)
    if a.resumen:
        import json
        open(a.resumen, "w", encoding="utf-8").write(json.dumps(info["resumen"], ensure_ascii=False, indent=2))
    print(f"{len(g)} clientes -> {a.out} en {time.time() - t:.1f}s | " + str({k: v for k, v in info.items() if k != "resumen"}))


if __name__ == "__main__":
    main()
