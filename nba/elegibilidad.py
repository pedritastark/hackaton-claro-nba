"""Etapa 1: matrices de elegibilidad cliente x campana y cliente x canal, con la razon de cada exclusion."""
from dataclasses import dataclass, field
from typing import Dict

import numpy as np
import pandas as pd

from nba.config import Config
from nba.reglas import evaluar


@dataclass
class Elegibilidad:
    prod_ok: Dict[str, np.ndarray] = field(default_factory=dict)    # campana -> bool[N]
    prod_why: Dict[str, np.ndarray] = field(default_factory=dict)   # campana -> str[N] ("R01;R07")
    canal_ok: Dict[str, np.ndarray] = field(default_factory=dict)   # canal -> bool[N]
    canal_why: Dict[str, np.ndarray] = field(default_factory=dict)
    semana_ok: np.ndarray = None


def _agrega(motivo, mask, cod):
    return np.where(mask, np.char.add(motivo, cod + ";"), motivo)


def calcular(df: pd.DataFrame, cfg: Config) -> Elegibilidad:
    n = len(df)
    el = Elegibilidad()
    col_sem = cfg.politica_contacto.columna_contactos_semana
    el.semana_ok = (df[col_sem].fillna(0).to_numpy() + 1) <= cfg.politica_contacto.max_contactos_semana

    reglas = [r for r in cfg.reglas if r.activa]
    for c in cfg.campanas_vigentes():
        why = np.full(n, "", dtype="U60")
        for r in reglas:
            if r.tipo != "elegibilidad":
                continue
            if not Config.regla_aplica(r, c):
                continue
            why = _agrega(why, evaluar(df, r.atributo, r.operador, r.valor, c.producto), r.id)
        bajo = df[c.columna_score].to_numpy() < cfg.priorizacion.umbral_score_producto
        why = _agrega(why, bajo, "UMBRAL_PRODUCTO")
        el.prod_why[c.id] = why
        el.prod_ok[c.id] = why == ""

    for ch in cfg.canales:
        why = np.full(n, "", dtype="U60")
        for r in reglas:
            if r.tipo != "canal":
                continue
            if r.alcance_nivel == "canal" and ch.id not in r.alcance_valores:
                continue
            why = _agrega(why, evaluar(df, r.atributo, r.operador, r.valor), r.id)
        bajo = df[ch.columna_score].to_numpy() < cfg.asignacion.umbral_score_canal
        why = _agrega(why, bajo, "UMBRAL_CANAL")
        el.canal_why[ch.id] = why
        el.canal_ok[ch.id] = why == ""
    return el
