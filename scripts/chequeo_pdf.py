"""Chequeo INDEPENDIENTE de las 16 restricciones, escrito desde el texto del PDF del reto.
No importa nada de nba/ ni lee config/: los numeros son los de la configuracion inicial del PDF.
Solo aplica a parrillas generadas con esa configuracion inicial.

Uso: python scripts/chequeo_pdf.py <parrilla.csv> <clientes.csv>    (exit 1 si hay violaciones)"""
import json
import sys

import pandas as pd

# ---- cifras del PDF (seccion 3 y tablas de la seccion 2)
PRODUCTOS = {  # campana: (codigo, columna de score, valor de negocio, jerarquia, canales permitidos)
    "C-VCH": ("VCH", "score_venta_cruzada_hogar", 1.0, 1, {"asesor", "whatsapp", "correo", "sms"}),
    "C-TER": ("TER", "score_terminales", 0.8, 2, {"asesor", "whatsapp", "correo", "sms"}),
    "C-OTT": ("OTT", "score_upgrade_ott", 0.4, 3, {"whatsapp", "correo", "sms"}),
}
CANALES = {  # canal: (columna de score, cupo por corrida, maximo de productos por contacto)
    "asesor": ("score_canal_asesor", 2500, 1), "whatsapp": ("score_canal_whatsapp", 15000, 2),
    "correo": ("score_canal_correo", 30000, 2), "sms": ("score_canal_sms", 40000, 2)}
AUTORIZA = {"whatsapp": "autoriza_whatsapp", "correo": "autoriza_correo", "sms": "autoriza_sms"}
MIN_SCORE_PRODUCTO, MIN_SCORE_CANAL = 0.35, 0.25          # R08, R11
EQUIPO_MIN_MESES, QUEJAS_MAX, CALIF_TER = 18, 3, {"E", "A", "B"}   # R03, R07, R02
LLAMADAS_ASESOR_MAX, CONTACTOS_SEMANA_MAX = 2, 3          # R10, R15
COLS_SALIDA = ["id_cliente", "estado", "canal", "campana_1", "campana_2", "razon"]


def _vacio(s):
    return s.fillna("").astype(str).str.strip() == ""


def chequear(parrilla: pd.DataFrame, clientes: pd.DataFrame) -> dict:
    v = {}
    # --- formato
    if list(parrilla.columns) != COLS_SALIDA:
        v["FORMATO_columnas"] = 1
    if len(parrilla) != len(clientes) or parrilla.id_cliente.duplicated().any() or \
            set(parrilla.id_cliente) != set(clientes.id_cliente):
        v["FORMATO_una_fila_por_cliente"] = 1
    if not parrilla.estado.isin(["asignado", "sin_accion"]).all():
        v["FORMATO_estado"] = int((~parrilla.estado.isin(["asignado", "sin_accion"])).sum())
    g = parrilla.merge(clientes, on="id_cliente", how="left", validate="many_to_one")
    asig = g.estado == "asignado"
    sin = ~asig
    v["FORMATO_sin_accion_con_datos"] = int((sin & (~_vacio(g.canal) | ~_vacio(g.campana_1) | ~_vacio(g.campana_2))).sum())
    v["FORMATO_asignado_incompleto"] = int((asig & (_vacio(g.canal) | _vacio(g.campana_1))).sum())
    v["FORMATO_campana2_sin_campana1"] = int((_vacio(g.campana_1) & ~_vacio(g.campana_2)).sum())

    # --- R13: un solo canal por cliente, y debe ser un canal conocido
    v["R13"] = int((asig & ~g.canal.isin(CANALES)).sum())

    # --- a nivel (cliente, producto asignado)
    filas = []
    for pos in ("campana_1", "campana_2"):
        s = g[asig & ~_vacio(g[pos])].copy()
        s["camp"] = s[pos]
        filas.append(s)
    p = pd.concat(filas, ignore_index=True)
    desconocida = ~p.camp.isin(PRODUCTOS)
    v["R12_campana_desconocida"] = int(desconocida.sum())
    p = p[~desconocida & p.canal.isin(CANALES)].copy()
    cod = p.camp.map(lambda c: PRODUCTOS[c][0])
    sc_prod = p.apply(lambda r: r[PRODUCTOS[r.camp][1]], axis=1)
    sc_can = p.apply(lambda r: r[CANALES[r.canal][0]], axis=1)

    v["R01"] = int((p.en_mora == 1).sum())
    ter = p.camp == "C-TER"
    v["R02"] = int((ter & ~p.calificacion_riesgo.isin(CALIF_TER)).sum())
    v["R03"] = int((ter & (p.edad_equipo_meses < EQUIPO_MIN_MESES)).sum())
    v["R04"] = int(((p.camp == "C-VCH") & (p.tiene_hogar == 1)).sum())
    ya_tiene_las_3 = (p.tiene_netflix == 1) & (p.tiene_amazon_prime == 1) & (p.tiene_win == 1)
    v["R05"] = int(((p.camp == "C-OTT") & ya_tiene_las_3).sum())
    ofertados = p.productos_ofertados_mes.fillna("").astype(str).str.split("|")
    v["R06"] = int(sum(c in o for c, o in zip(cod, ofertados)))
    v["R07"] = int((p.quejas_90d >= QUEJAS_MAX).sum())
    v["R08"] = int((sc_prod < MIN_SCORE_PRODUCTO).sum())
    aut_ok = p.apply(lambda r: True if r.canal == "asesor" else r[AUTORIZA[r.canal]] == 1, axis=1)
    v["R09"] = int((~aut_ok).sum())
    v["R10"] = int(((p.canal == "asesor") & (p.contactos_asesor_mes >= LLAMADAS_ASESOR_MAX)).sum())
    v["R11"] = int((sc_can < MIN_SCORE_CANAL).sum())
    v["R12"] = int(sum(c not in PRODUCTOS[k][4] for c, k in zip(p.canal, p.camp)))

    # --- a nivel cliente
    a = g[asig & g.canal.isin(CANALES)]
    tope = a.canal.map(lambda c: CANALES[c][2])
    n_prod = (~_vacio(a.campana_1)).astype(int) + (~_vacio(a.campana_2)).astype(int)
    v["R14"] = int((n_prod > tope).sum()) + int(((a.campana_1 == a.campana_2) & ~_vacio(a.campana_2)).sum())
    v["R15"] = int((a.contactos_semana_actual + 1 > CONTACTOS_SEMANA_MAX).sum())
    usos = a.canal.value_counts()
    v["R16"] = int(sum(max(0, usos.get(c, 0) - cfg[1]) for c, cfg in CANALES.items()))

    # --- metricas, recalculadas desde cero
    valor = float((sc_prod * sc_can * p.camp.map(lambda c: PRODUCTOS[c][2])).sum())
    # jerarquia: producto elegible (R01-R08) de mayor jerarquia que el cliente recibio, entre clientes con accion
    def elegibles(c):
        cod_, col, _, _, _ = PRODUCTOS[c]
        ok = (c_["en_mora"] == 0) & (c_["quejas_90d"] < QUEJAS_MAX) & (c_[col] >= MIN_SCORE_PRODUCTO)
        ok &= ~c_.productos_ofertados_mes.fillna("").astype(str).str.split("|").map(lambda o: cod_ in o)
        if c == "C-TER":
            ok &= c_.calificacion_riesgo.isin(CALIF_TER) & (c_.edad_equipo_meses >= EQUIPO_MIN_MESES)
        if c == "C-VCH":
            ok &= c_.tiene_hogar == 0
        if c == "C-OTT":
            ok &= ~((c_.tiene_netflix == 1) & (c_.tiene_amazon_prime == 1) & (c_.tiene_win == 1))
        return ok
    c_ = a
    mejor = pd.Series("", index=a.index)
    for camp in sorted(PRODUCTOS, key=lambda k: -PRODUCTOS[k][3]):   # de menor a mayor prioridad: la ultima en elegibles gana
        mejor = mejor.where(~elegibles(camp), camp)
    recibio = (a.campana_1 == mejor) | (a.campana_2 == mejor)
    jer = round(100 * float(recibio[mejor != ""].sum()) / max(1, int((mejor != "").sum())), 2)
    return {"violaciones": {k: n for k, n in v.items() if n}, "violaciones_total": int(sum(v.values())),
            "valor_esperado": round(valor, 2), "clientes_con_accion": int(len(a)),
            "productos_asignados": int(len(p)), "jerarquia_pct": jer, "uso_canales": usos.to_dict()}


if __name__ == "__main__":
    dt = {"canales_contactados_mes": str, "productos_ofertados_mes": str}
    r = chequear(pd.read_csv(sys.argv[1], dtype=str, keep_default_na=False).replace("", pd.NA),
                 pd.read_csv(sys.argv[2], dtype=dt))
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    sys.exit(1 if r["violaciones_total"] else 0)
