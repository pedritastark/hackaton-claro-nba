"""Versionado de la configuracion: cada cambio aplicado queda en config/versiones/<fecha>_<etiqueta>/."""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from nba import config

ARCHIVOS = ("parametros.yaml", "campanas.yaml", "reglas.yaml")


def guardar_version(cfg, directorio="config", etiqueta="cambio", metricas=None) -> str:
    d = Path(directorio)
    config.guardar(cfg, directorio)
    nombre = datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + re.sub(r"[^a-zA-Z0-9]+", "-", etiqueta)[:40].strip("-")
    v = d / "versiones" / nombre
    v.mkdir(parents=True, exist_ok=True)
    for a in ARCHIVOS:
        shutil.copy(d / a, v / a)
    (v / "meta.json").write_text(json.dumps({"etiqueta": etiqueta, "fecha": datetime.now().isoformat(timespec="seconds"),
                                              "metricas": metricas or {}}, ensure_ascii=False, indent=2), encoding="utf-8")
    return nombre


def listar(directorio="config"):
    base = Path(directorio) / "versiones"
    if not base.exists():
        return []
    out = []
    for v in sorted(base.iterdir(), reverse=True):
        if (v / "meta.json").exists():
            out.append({"version": v.name, **json.loads((v / "meta.json").read_text(encoding="utf-8"))})
    return out


def cargar_version(nombre, directorio="config"):
    return config.cargar(str(Path(directorio) / "versiones" / nombre))
