"""Etapa 4: parrilla de salida con razon por cliente."""
import numpy as np
import pandas as pd

from nba.asignacion import Asignacion
from nba.candidatos import Candidatos
from nba.config import Config
from nba.elegibilidad import Elegibilidad


def construir(df: pd.DataFrame, cfg: Config, el: Elegibilidad, cand: Candidatos, asg: Asignacion, razon) -> pd.DataFrame:
    N = len(df)
    camps, canales = cand.campanas, cand.canales
    ids_camp = [c.id for c in camps]
    out_canal = np.array([canales[j].id if j >= 0 else "" for j in asg.canal], dtype=object)
    k_cols = asg.paq.shape[1]
    camp_cols = [np.array([ids_camp[k] if k >= 0 else "" for k in asg.paq[:, s]], dtype=object)
                 for s in range(k_cols)]
    g = pd.DataFrame({
        "id_cliente": df["id_cliente"].to_numpy(),
        "estado": np.where(asg.canal >= 0, "asignado", "sin_accion"),
        "canal": out_canal,
        "campana_1": camp_cols[0],
        "campana_2": camp_cols[1] if k_cols > 1 else "",
        "razon": razon,
    })
    return g
