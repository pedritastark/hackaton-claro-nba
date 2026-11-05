"""Interprete generico de reglas (vectorizado). La regla EXCLUYE cuando su condicion es verdadera."""
import numpy as np
import pandas as pd
from nba.config import ConfigError, Regla

_CMP = {"==": np.equal, "!=": np.not_equal, "<": np.less, "<=": np.less_equal,
        ">": np.greater, ">=": np.greater_equal}


def evaluar(df: pd.DataFrame, atributo, operador, valor, producto=None) -> np.ndarray:
    """Devuelve bool[N]: True si la condicion se cumple. Un dato faltante nunca cumple (salvo contiene/no_contiene)."""
    if atributo not in df.columns:
        raise ConfigError(f"la regla usa la columna '{atributo}', que no existe en la base")
    col = df[atributo]
    if valor == "$producto":
        valor = producto
    if operador in ("contiene", "no_contiene"):
        txt = "|" + col.fillna("").astype(str) + "|"
        r = txt.str.contains("|" + str(valor) + "|", regex=False).to_numpy()
        return r if operador == "contiene" else ~r
    num = pd.api.types.is_numeric_dtype(col)
    validos = col.notna().to_numpy()
    if operador in ("en", "no_en"):
        lista = [float(v) for v in valor] if num else [str(v) for v in valor]
        r = col.isin(lista).to_numpy()
        return (r if operador == "en" else ~r) & validos
    v = float(valor) if num else valor
    return _CMP[operador](col.to_numpy(), v) & validos


def frase(r: Regla) -> str:
    """Descripcion corta para la consola."""
    alc = {"global": "todos", "campana": "campanas " + "/".join(r.alcance_valores),
           "producto": "productos " + "/".join(r.alcance_valores), "objetivo": "objetivos " + "/".join(r.alcance_valores),
           "canal": "canales " + "/".join(r.alcance_valores)}[r.alcance_nivel]
    return f"[{r.id}] {r.nombre} — excluye ({alc}) si {r.atributo} {r.operador} {r.valor}"
