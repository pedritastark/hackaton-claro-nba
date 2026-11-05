"""Convierte los 3 CSV del kit del reto a config/*.yaml (una sola vez).
Uso: python -m nba.importar_kit <carpeta_kit> [config]"""
import sys
import pandas as pd
from nba.config import Config, guardar


def _num(x):
    try:
        f = float(x)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return x


def importar(kit, salida="config"):
    from pathlib import Path
    kit = Path(kit)
    p = dict(pd.read_csv(kit / "config_parametros.csv", dtype=str).values)
    camps = pd.read_csv(kit / "config_campanas.csv")
    reglas = pd.read_csv(kit / "config_reglas.csv", dtype=str, keep_default_na=False)
    lista = lambda s: [v for v in str(s).split("|") if v]
    canales = lista(p["canal.orden_preferencia"])
    cfg = Config(
        fecha_corrida="2026-11-04",
        campanas=[dict(id=r.id, nombre=r.nombre, producto=r.producto, objetivo=r.objetivo,
                       columna_score=r.columna_score, valor_negocio=float(r.valor_negocio),
                       canales_permitidos=lista(r.canales_permitidos),
                       vigencia_inicio=r.vigencia_inicio, vigencia_fin=r.vigencia_fin,
                       activa=bool(r.activa)) for r in camps.itertuples()],
        reglas=[dict(id=r.id, nombre=r.nombre, tipo=r.tipo, alcance_nivel=r.alcance_nivel,
                     alcance_valores=lista(r.alcance_valores), atributo=r.atributo, operador=r.operador,
                     valor=(lista(r.valor) if r.operador in ("en", "no_en") else _num(r.valor)),
                     accion=r.accion, activa=r.activa == "1") for r in reglas.itertuples()],
        canales=[dict(id=c, columna_score=f"score_canal_{c}",
                      cupo=int(p[f"canal.capacidad_por_corrida.{c}"]),
                      max_productos=int(p[f"politica_contacto.max_productos_por_canal.{c}"])) for c in canales],
        priorizacion=dict(modo=p["priorizacion.modo"], jerarquia=lista(p["priorizacion.jerarquia"]),
                          pesos=dict(score_producto=float(p["priorizacion.pesos.score_producto"]),
                                     valor_negocio=float(p["priorizacion.pesos.valor_negocio"]),
                                     jerarquia=float(p["priorizacion.pesos.jerarquia"])),
                          umbral_score_producto=float(p["priorizacion.umbral_score_producto"]),
                          desempate=lista(p["priorizacion.desempate"])),
        politica_contacto=dict(max_contactos_semana=int(p["politica_contacto.max_contactos_semana"]),
                               canales_por_cliente=int(p["politica_contacto.canales_por_cliente"])),
        asignacion=dict(algoritmo="optimo", criterio_canal=p["canal.criterio"],
                        orden_preferencia=canales, umbral_score_canal=float(p["canal.umbral_score_canal"])),
    )
    guardar(cfg, salida)
    return cfg


if __name__ == "__main__":
    importar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "config")
    print("config/ generado")
