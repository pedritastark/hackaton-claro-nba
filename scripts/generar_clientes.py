"""Genera clientes.csv sintetico (100k x 45) inferido de casos_ejemplo_clientes.csv.

Uso: python -I scripts/generar_clientes.py <casos_ejemplo.csv> <salida.csv> [n] [seed]
Los 5 casos de ejemplo se conservan tal cual (mismo id_cliente).
"""
import sys
import numpy as np
import pandas as pd

casos_path, out_path = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 100_000
rng = np.random.default_rng(int(sys.argv[4]) if len(sys.argv) > 4 else 42)
casos = pd.read_csv(casos_path, dtype={"canales_contactados_mes": str, "productos_ofertados_mes": str})
cols = list(casos.columns)

def bern(p, n=N):
    return (rng.random(n) < p).astype(int)

def pick(vals, p, n=N):
    return rng.choice(vals, size=n, p=p)

df = pd.DataFrame({"id_cliente": [f"CL{i:06d}" for i in range(1, N + 1)]})
df["region"] = pick(["Bogota", "Antioquia", "Valle", "Centro", "Santanderes", "Costa", "Sur"],
                    [.27, .17, .12, .12, .08, .16, .08])
df["estrato"] = pick([1, 2, 3, 4, 5, 6], [.12, .26, .30, .18, .09, .05])
df["edad"] = np.clip(rng.normal(40, 13, N), 18, 80).round().astype(int)
df["antiguedad_meses"] = np.clip(rng.gamma(2.0, 24, N), 1, 240).round().astype(int)
df["tipo_linea"] = pick(["Postpago", "Prepago"], [.62, .38])
post = df.tipo_linea.eq("Postpago").values
df["plan_datos_gb"] = np.where(post, pick([5, 10, 20, 40, 999], [.2, .2, .2, .25, .15]),
                               pick([1, 2, 5, 10], [.25, .3, .3, .15]))
df["consumo_datos_pct"] = (rng.beta(2, 2.2, N) * 100).round(1)
arpu = np.exp(rng.normal(np.where(post, 11.0, 9.9), .55)) * (1 + .08 * (df.estrato.values - 3))
df["arpu_movil"] = (np.clip(arpu, 3000, 250000) / 100).round() .astype(int) * 100

rating = pick(["E", "A", "B", "C", "P"], [.25, .20, .25, .15, .15])
df["calificacion_riesgo"] = rating
p_mora = pd.Series(rating).map({"E": .02, "A": .04, "B": .07, "C": .14, "P": .25}).values
mora = bern(p_mora)
df["en_mora"] = mora
df["dias_mora"] = np.where(mora == 1, np.clip(rng.gamma(2, 15, N), 1, 120).round().astype(int), 0)

hogar = bern(.40)
df["tiene_hogar"] = hogar
df["arpu_hogar"] = np.where(hogar == 1, (np.clip(rng.normal(150000, 40000, N), 60000, 300000) / 100).round().astype(int) * 100, 0)
nf, am, win = bern(.45), bern(.25), bern(.20)
df["tiene_netflix"], df["tiene_amazon_prime"], df["tiene_win"] = nf, am, win
df["cantidad_ott"] = nf + am + win
df["usa_redes_sociales"] = bern(.85)
df["usa_banca_digital"] = bern(.6)
df["compras_digitales"] = bern(.5)

edad_eq = np.clip(rng.gamma(2.2, 14, N), 1, 72).round().astype(int)
df["edad_equipo_meses"] = edad_eq
df["gama_equipo"] = pick(["Baja", "Media", "Alta"], [.3, .5, .2])
df["quejas_90d"] = rng.poisson(.7, N)
df["riesgo_churn"] = np.clip(rng.beta(1.6, 7, N) + .03 * (df.quejas_90d.values > 0), 0, 1).round(4)

df["tiene_correo"] = bern(.7)
df["autoriza_sms"] = bern(.88)
df["autoriza_correo"] = bern(.75) * df.tiene_correo.values
df["autoriza_whatsapp"] = bern(.8)

# historial de contactos del mes (coherente: total = suma de canales)
act = rng.random(N)
base = np.where(act < .45, 0, rng.poisson(1.6, N) + 1)
w = rng.dirichlet([.5, 1.2, 1.5, 1.5], N)  # asesor, sms, correo, whatsapp
asesor = np.minimum(rng.binomial(base, np.clip(w[:, 0], 0, 1)), 3)
rest = base - asesor
sms = rng.binomial(rest, w[:, 1] / np.maximum(1e-9, 1 - w[:, 0]))
rest2 = rest - sms
correo = rng.binomial(rest2, w[:, 2] / np.maximum(1e-9, w[:, 2] + w[:, 3]))
wa = rest2 - correo
total = asesor + sms + correo + wa
df["contactos_mes"] = total
df["contactos_semana_actual"] = np.minimum(total, rng.binomial(4, .42, N))
df["contactos_asesor_mes"], df["contactos_sms_mes"] = asesor, sms
df["contactos_correo_mes"], df["contactos_whatsapp_mes"] = correo, wa
canales = np.array(["asesor", "sms", "correo", "whatsapp"])
mat = np.stack([asesor, sms, correo, wa], 1) > 0
df["canales_contactados_mes"] = ["|".join(canales[r]) if r.any() else "" for r in mat]
nprod = np.where(total == 0, 0, np.minimum(rng.integers(1, 4, N), 2 * total))
prods = np.array(["VCH", "TER", "OTT"])
ofert = []
for k in nprod:
    ofert.append("|".join(rng.permutation(prods)[:k]) if k else "")
df["productos_ofertados_mes"] = ofert
df["dias_ultimo_contacto"] = np.where(total > 0, rng.integers(1, 31, N), rng.integers(31, 181, N))

def score(a, b, shift=0.0):
    return np.clip(rng.beta(a, b, N) + shift, 0.01, 0.99).round(4)

df["score_terminales"] = score(2.2, 4, np.clip((edad_eq - 24) / 200, -.1, .15))
df["score_venta_cruzada_hogar"] = score(2, 4.5, -.05 * hogar)
df["score_upgrade_ott"] = score(3, 4.5, .03 * df.usa_redes_sociales.values)
df["score_canal_asesor"] = score(3, 5.5)
df["score_canal_sms"] = score(3, 5.5)
df["score_canal_correo"] = score(3, 5.5, -.08 * (1 - df.tiene_correo.values))
df["score_canal_whatsapp"] = score(3.2, 5, .04 * df.usa_redes_sociales.values)

df = df[cols]
# conservar los casos de ejemplo tal cual
idx = df.id_cliente.isin(casos.id_cliente)
df = df[~idx]
df = pd.concat([df, casos]).sort_values("id_cliente").reset_index(drop=True)[cols]
df.to_csv(out_path, index=False)
print(f"{len(df)} filas, {len(df.columns)} columnas -> {out_path}")
