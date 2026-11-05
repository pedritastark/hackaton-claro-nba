"""Etapa 2: para cada cliente y canal, el mejor paquete de hasta k productos."""
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from nba.config import Campana, Canal, Config
from nba.elegibilidad import Elegibilidad


EPS_DESEMPATE = 1e-3


@dataclass
class Candidatos:
    campanas: List[Campana]
    canales: List[Canal]
    sp: np.ndarray          # (N,P) score producto
    sc: np.ndarray          # (N,C) score canal
    valor: np.ndarray       # (P,) valor de negocio
    nivel: np.ndarray       # (P,) nivel de jerarquia 1..0
    factible: np.ndarray    # (N,C,P) bool
    paq: np.ndarray         # (N,C,K) indice de campana o -1
    n_paq: np.ndarray       # (N,C)
    v_real: np.ndarray      # (N,C) valor esperado real del paquete
    v_util: np.ndarray      # (N,C) utilidad que se optimiza (mezcla con jerarquia segun alpha)
    puntaje: np.ndarray     # (N,P) puntaje de la linea base


def puntaje_producto(cfg: Config, sp, valor, nivel):
    p = cfg.priorizacion
    if p.modo == "jerarquia_estricta":
        return nivel[None, :] * 10 + sp
    w = p.pesos
    return w.score_producto * sp + w.valor_negocio * valor[None, :] + w.jerarquia * nivel[None, :]


def claves_desempate(cfg: Config, sp, valor, nivel, forma):
    """Arreglos (broadcast a `forma`) de los criterios de desempate configurados, en orden de prioridad."""
    base = {"score_producto": sp, "valor_negocio": valor[None, :], "jerarquia": nivel[None, :]}
    out = []
    for d in cfg.priorizacion.desempate:
        a = base[d]
        a = a[:, None, :] if len(forma) == 3 and a.ndim == 2 else a
        out.append(np.broadcast_to(a, forma))
    return out


def _paquetes(clave, factible, k_canal, desempate=()):
    """Top-k por clave dentro de cada canal (empates: criterios de desempate, luego orden de campana).
    clave y factible: (N,C,P)."""
    n, c, p = clave.shape
    kmax = max(k_canal)
    m = np.where(factible, clave, -np.inf)
    claves = tuple(-d for d in reversed(list(desempate))) + (-m,)     # la ultima es la principal
    orden = np.lexsort(claves, axis=2)[:, :, :kmax]
    ok = np.take_along_axis(m, orden, axis=2) > -np.inf
    for j, k in enumerate(k_canal):
        ok[:, j, k:] = False
    paq = np.where(ok, orden, -1)
    return paq, ok.sum(axis=2)


def construir(df: pd.DataFrame, cfg: Config, el: Elegibilidad) -> Candidatos:
    camps, canales = cfg.campanas_vigentes(), cfg.canales
    N, P, C = len(df), len(camps), len(canales)
    sp = np.stack([df[c.columna_score].to_numpy() for c in camps], 1)
    sc = np.stack([df[ch.columna_score].to_numpy() for ch in canales], 1)
    valor = np.array([c.valor_negocio for c in camps])
    niv = cfg.nivel_jerarquia()
    nivel = np.array([niv[c.id] for c in camps])
    a = cfg.priorizacion.alpha
    valor_ef = (1 - a) * valor + a * nivel

    fact = np.zeros((N, C, P), dtype=bool)
    for j, ch in enumerate(canales):
        base = el.canal_ok[ch.id] & el.semana_ok
        for i, c in enumerate(camps):
            if ch.id in c.canales_permitidos:
                fact[:, j, i] = base & el.prod_ok[c.id]

    real = sp[:, None, :] * sc[:, :, None] * valor[None, None, :]
    # desempate: con alpha=1 el producto de menor jerarquia tendria utilidad 0 y dejaria de asignarse
    pr = cfg.priorizacion
    util = (sp[:, None, :] ** pr.peso_modelo) * sc[:, :, None] * \
        ((valor_ef + EPS_DESEMPATE * valor)[None, None, :] ** pr.peso_valor)
    paq, npq = _paquetes(util, fact, [ch.max_productos for ch in canales],
                         claves_desempate(cfg, sp, valor, nivel, util.shape))
    sel = np.where(paq >= 0, paq, 0)
    pick = lambda m: np.where(paq >= 0, np.take_along_axis(m, sel, axis=2), 0).sum(axis=2)
    return Candidatos(camps, canales, sp, sc, valor, nivel, fact, paq, npq,
                      pick(real), pick(util), puntaje_producto(cfg, sp, valor, nivel))


def paquete_por_puntaje(cand: Candidatos, cfg: Config):
    """Variante de paquetes ordenados por el puntaje de la linea base (para el modo codicioso)."""
    clave = np.broadcast_to(cand.puntaje[:, None, :], cand.factible.shape)
    return _paquetes(clave, cand.factible, [ch.max_productos for ch in cand.canales],
                     claves_desempate(cfg, cand.sp, cand.valor, cand.nivel, cand.factible.shape))
