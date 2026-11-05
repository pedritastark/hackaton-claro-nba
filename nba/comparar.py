"""Metricas rapidas y comparacion entre dos corridas (vista previa de cambios de configuracion)."""
import numpy as np
import pandas as pd

from nba import asignacion, candidatos, elegibilidad, parrilla
from nba.config import Config


def nucleo(df: pd.DataFrame, cfg: Config):
    el = elegibilidad.calcular(df, cfg)
    cand = candidatos.construir(df, cfg, el)
    asg = asignacion.asignar(cand, cfg)
    return el, cand, asg


def matriz_productos(cand, asg) -> pd.DataFrame:
    """bool (N x campanas): producto asignado a cada cliente."""
    ids = [c.id for c in cand.campanas]
    M = np.zeros((len(asg.canal), len(ids)), dtype=bool)
    for s in range(asg.paq.shape[1]):
        k = asg.paq[:, s]
        m = k >= 0
        M[np.where(m)[0], k[m]] = True
    return pd.DataFrame(M, columns=ids)


def metricas(cand, el, asg, cfg: Config) -> dict:
    M = matriz_productos(cand, asg)
    j = np.where(asg.canal >= 0, asg.canal, 0)
    sc = cand.sc[np.arange(len(j)), j]
    v = (M.to_numpy() * cand.sp * cand.valor[None, :]).sum(axis=1) * sc * (asg.canal >= 0)
    con_accion = asg.canal >= 0
    # jerarquia: % de clientes con accion que recibieron su producto elegible de mayor nivel
    niv = np.where(np.stack([el.prod_ok[c.id] for c in cand.campanas], 1), cand.nivel[None, :], -1)
    mejor = niv.argmax(axis=1)
    tiene = niv.max(axis=1) >= 0
    recibio = M.to_numpy()[np.arange(len(mejor)), mejor]
    base = con_accion & tiene
    return {
        "valor_esperado": float(v.sum()),
        "clientes_con_accion": int(con_accion.sum()),
        "productos_asignados": int(M.to_numpy().sum()),
        "jerarquia_pct": round(100 * float(recibio[base].sum()) / max(1, int(base.sum())), 2),
        "uso_canales": {ch.id: int((asg.canal == i).sum()) for i, ch in enumerate(cand.canales)},
        "cupo_canales": {ch.id: ch.cupo for ch in cand.canales},
        "productos_por_campana": {c: int(M[c].sum()) for c in M.columns},
        "valor_por_cliente": v,
    }


def parrilla_ligera(df, cfg, el, cand, asg) -> pd.DataFrame:
    return parrilla.construir(df, cfg, el, cand, asg, np.full(len(df), "", dtype=object))


def comparar(ids, A, B) -> dict:
    """A y B = (cand, asg, metricas). Devuelve deltas y listas de clientes afectados."""
    (ca, aa, ma), (cb, ab, mb) = A, B
    Ma, Mb = matriz_productos(ca, aa), matriz_productos(cb, ab)
    cols = sorted(set(Ma.columns) | set(Mb.columns))
    Ma, Mb = Ma.reindex(columns=cols, fill_value=False), Mb.reindex(columns=cols, fill_value=False)
    acc_a, acc_b = aa.canal >= 0, ab.canal >= 0
    canal_a = np.array([ca.canales[j].id if j >= 0 else "" for j in aa.canal])
    canal_b = np.array([cb.canales[j].id if j >= 0 else "" for j in ab.canal])
    cambia_prod = (Ma.to_numpy() != Mb.to_numpy()).any(axis=1) & acc_a & acc_b
    cambia_canal = (canal_a != canal_b) & acc_a & acc_b
    muestra = lambda m: [str(x) for x in ids[m][:25]]
    return {
        "delta_valor": mb["valor_esperado"] - ma["valor_esperado"],
        "delta_clientes": mb["clientes_con_accion"] - ma["clientes_con_accion"],
        "delta_productos": mb["productos_asignados"] - ma["productos_asignados"],
        "delta_jerarquia": round(mb["jerarquia_pct"] - ma["jerarquia_pct"], 2),
        "ganan_accion": int((~acc_a & acc_b).sum()), "pierden_accion": int((acc_a & ~acc_b).sum()),
        "cambian_canal": int(cambia_canal.sum()), "cambian_productos": int(cambia_prod.sum()),
        "ejemplos": {"ganan_accion": muestra(~acc_a & acc_b), "pierden_accion": muestra(acc_a & ~acc_b),
                     "cambian_canal": muestra(cambia_canal), "cambian_productos": muestra(cambia_prod)},
        "productos_por_campana": {c: (int(Ma[c].sum()), int(Mb[c].sum())) for c in cols},
    }
