"""Etapa 3: reparto de cupos. Dos algoritmos: codicioso (linea base) y optimo (LP de transporte)."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack

from nba.candidatos import Candidatos, claves_desempate, paquete_por_puntaje
from nba.config import Config


@dataclass
class Asignacion:
    canal: np.ndarray      # (N,) indice de canal o -1
    paq: np.ndarray        # (N,K) indices de campana o -1
    info: dict


def _desde_canal(canal, paq_nck):
    n = len(canal)
    k = paq_nck.shape[2]
    out = np.full((n, k), -1)
    m = canal >= 0
    out[m] = paq_nck[np.where(m)[0], canal[m]]
    return out


BONO_ORDEN = 10.0      # domina cualquier diferencia de valor de un cliente (maximo ~2)


def ordenar_por_puntaje(asg: Asignacion, cand: Candidatos, cfg: Config) -> Asignacion:
    """campana_1 = la de mayor puntaje entre las asignadas (empates: criterios de desempate)."""
    paq = asg.paq
    valido = paq >= 0
    idx = np.where(valido, paq, 0)
    toma = lambda m: np.where(valido, np.take_along_axis(m, idx, axis=1), -np.inf)
    pu = toma(cand.puntaje)
    ties = [toma(np.asarray(k)) for k in claves_desempate(cfg, cand.sp, cand.valor, cand.nivel, cand.sp.shape)]
    claves = tuple(-t for t in reversed(ties)) + (-pu,)
    asg.paq = np.take_along_axis(paq, np.lexsort(claves, axis=1), axis=1)
    return asg


def codicioso(cand: Candidatos, cfg: Config) -> Asignacion:
    paq, npq = paquete_por_puntaje(cand, cfg)
    N, C = npq.shape
    cupo = np.array([ch.cupo for ch in cand.canales])
    usado = np.zeros(C, int)
    mejor = np.where(cand.factible, cand.puntaje[:, None, :], -np.inf).max(axis=(1, 2))
    if cfg.asignacion.criterio_canal == "orden_preferencia":
        ids = [ch.id for ch in cand.canales]
        rank = np.array([cfg.asignacion.orden_preferencia.index(i) if i in cfg.asignacion.orden_preferencia
                         else 99 for i in ids])
        pref = np.broadcast_to(-rank.astype(float), cand.sc.shape)
    else:
        pref = cand.sc
    canal = np.full(N, -1)
    for i in np.argsort(-mejor, kind="stable"):
        if mejor[i] == -np.inf:
            break
        for j in np.argsort(-pref[i], kind="stable"):
            if npq[i, j] > 0 and usado[j] < cupo[j]:
                canal[i] = j
                usado[j] += 1
                break
    return Asignacion(canal, _desde_canal(canal, paq), {"algoritmo": "codicioso"})


def optimo(cand: Candidatos, cfg: Config) -> Asignacion:
    N, C = cand.n_paq.shape
    cupo = np.array([ch.cupo for ch in cand.canales], float)
    ii, jj = np.where(cand.n_paq > 0)
    m = len(ii)
    if m == 0:
        return Asignacion(np.full(N, -1), _desde_canal(np.full(N, -1), cand.paq),
                          {"algoritmo": "optimo", "lp_entero": True, "valor_lp": 0.0, "precio_sombra": {}})
    v = cand.v_util[ii, jj]
    por_orden = cfg.asignacion.criterio_canal == "orden_preferencia"
    if por_orden:    # canal por orden fijo de preferencia: los primeros de la lista dominan; el valor desempata
        orden = cfg.asignacion.orden_preferencia
        rank = np.array([orden.index(ch.id) if ch.id in orden else len(orden) for ch in cand.canales])
        v = v + BONO_ORDEN * (C - rank[jj])
    idx = np.arange(m)
    a_cli = coo_matrix((np.ones(m), (ii, idx)), shape=(N, m)).tocsr()
    a_can = coo_matrix((np.ones(m), (jj, idx)), shape=(C, m)).tocsr()
    res = linprog(-v, A_ub=vstack([a_cli, a_can]).tocsr(), b_ub=np.concatenate([np.ones(N), cupo]),
                  bounds=(0, 1), method="highs")
    if res.status != 0:
        raise RuntimeError(f"LP sin solucion: {res.message}")
    x = res.x
    entero = bool(np.all((x < 1e-6) | (x > 1 - 1e-6)))
    canal = np.full(N, -1)
    usado = np.zeros(C, int)
    # redondeo: primero lo seguro (x alto), respetando cupos; en solucion entera es identico al LP
    for k in np.argsort(-x, kind="stable"):
        if x[k] < 0.5 and entero:
            break
        if x[k] <= 1e-6:
            break
        i, j = ii[k], jj[k]
        if canal[i] == -1 and usado[j] < cupo[j]:
            canal[i] = j
            usado[j] += 1
    # precios sombra de los cupos (marginales del LP)
    sombra = {} if por_orden else {cand.canales[j].id: float(-res.ineqlin.marginals[N + j]) for j in range(C)}
    info = {"algoritmo": "optimo", "lp_entero": entero, "valor_lp": None if por_orden else float(-res.fun),
            "precio_sombra": sombra}
    return Asignacion(canal, _desde_canal(canal, cand.paq), info)


def asignar(cand: Candidatos, cfg: Config) -> Asignacion:
    asg = {"codicioso": codicioso, "optimo": optimo}[cfg.asignacion.algoritmo](cand, cfg)
    return ordenar_por_puntaje(asg, cand, cfg)
