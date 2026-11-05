# Ejemplo: por qué conviene reservar el canal escaso

Este caso didáctico usa las reglas iniciales y reduce los cupos para poder revisar todas las decisiones a mano. No representa una nueva corrida de los 100.000 clientes ni utiliza sus cifras de evaluación.

## 1. Datos y filtros

Hay cuatro clientes y las tres campañas iniciales. Hogar vale 1 y Terminales 0,8. Todos tienen riesgo E, equipo de 24 meses, no tienen Hogar, no tienen productos ofertados en el mes, no tienen quejas ni contactos previos, y autorizan los canales digitales. El score OTT es 0,1, por debajo del umbral 0,35.

| Cliente | Score Hogar | Score TER | Score WhatsApp | Score SMS | Mora |
|---|---|---|---|---|---|
| A | 0,90 | 0,80 | 0,90 | 0,80 | 0 |
| B | 0,80 | 0,70 | 0,85 | 0,30 | 0 |
| C | 0,60 | 0,50 | 0,40 | 0,60 | 0 |
| D | 0,90 | 0,80 | 0,90 | 0,80 | 1 |

WhatsApp tiene **un contacto** disponible; SMS tiene **dos**. Ambos permiten dos productos por contacto. Asesor y correo tienen cupo cero. Se usa `alpha=0`, exponentes en 1 y `criterio_canal=score_canal`.

Los filtros eliminan todas las ofertas de D por R01 y OTT para A, B y C por R08. Los scores de los dos canales superan el umbral 0,25. Los paquetes digitales de A, B y C son Hogar + TER; cada uno consume un solo cupo.

## 2. Valor de los paquetes

Por ejemplo, A por WhatsApp aporta:

$$
0{,}90\times0{,}90\times1+0{,}80\times0{,}90\times0{,}8=1{,}386.
$$

| Cliente | Paquete por WhatsApp | Paquete por SMS | Ventaja WhatsApp − SMS |
|---|---|---|---|
| A | 1,386 | 1,232 | 0,154 |
| B | 1,156 | 0,408 | **0,748** |
| C | 0,400 | 0,600 | −0,200 |

Estas son cifras de valor real $R_{ic}$. La utilidad que recibe el LP es 1,001 veces cada cifra por el término `EPS_DESEMPATE`; el factor común no cambia qué asignación gana.

## 3. Lo que hace el codicioso

Con los pesos iniciales, el mejor puntaje de cada cliente es el de Hogar: A = 0,94; B = 0,88; C = 0,76. El codicioso recorre ese orden:

1. A toma WhatsApp por su mayor score y agota el cupo.
2. B toma SMS porque WhatsApp ya no tiene cupo.
3. C toma SMS.
4. D queda sin acción por mora.

Total: **1,386 + 0,408 + 0,600 = 2,394**. Cumple las restricciones, pero no es el máximo.

## 4. Lo que decide el LP

El único cupo de WhatsApp se aprovecha más en B: perderlo le cuesta 0,748, frente a 0,154 en A. El LP asigna:

| Cliente | Estado | Canal | Campaña 1 | Campaña 2 | Valor |
|---|---|---|---|---|---|
| A | asignado | sms | C-VCH | C-TER | 1,232 |
| B | asignado | whatsapp | C-VCH | C-TER | 1,156 |
| C | asignado | sms | C-VCH | C-TER | 0,600 |
| D | sin_accion | vacío | vacío | vacío | 0 |

Total: **2,988**, una mejora de 0,594 sobre el codicioso. No se gana ofreciendo más productos: ambos asignan seis; se gana ubicando mejor los contactos.

También se puede verificar el óptimo enumerando quién recibe WhatsApp. Si lo recibe A, el mejor total es 2,394; si B, 2,988; si C, 2,040; si nadie, los dos mejores contactos SMS suman 1,832. B produce el mayor total.

El objetivo interno del LP es **2,990988** (= 1,001 × 2,988). El validador redondea el valor real a dos decimales y reporta **2,99**; para el codicioso reporta **2,39**.

## 5. Reproducir con el motor existente

Desde la raíz del repositorio, con las dependencias instaladas, ejecutar este bloque en Python o en un notebook. Solo construye objetos en memoria; no cambia los YAML ni la carpeta `entrega/`.

```python
from itertools import product

import numpy as np
import pandas as pd

from nba import comparar, config, run
from nba.validar import validar

cfg = config.cargar("config_inicial")
for canal in cfg.canales:
    canal.cupo = {"whatsapp": 1, "sms": 2}.get(canal.id, 0)

df = pd.DataFrame({
    "id_cliente": ["A", "B", "C", "D"],
    "en_mora": [0, 0, 0, 1],
    "calificacion_riesgo": ["E"] * 4,
    "edad_equipo_meses": [24] * 4,
    "tiene_hogar": [0] * 4,
    "cantidad_ott": [0] * 4,
    "productos_ofertados_mes": [""] * 4,
    "quejas_90d": [0] * 4,
    "contactos_asesor_mes": [0] * 4,
    "contactos_semana_actual": [0] * 4,
    "autoriza_whatsapp": [1] * 4,
    "autoriza_correo": [1] * 4,
    "autoriza_sms": [1] * 4,
    "score_venta_cruzada_hogar": [0.9, 0.8, 0.6, 0.9],
    "score_terminales": [0.8, 0.7, 0.5, 0.8],
    "score_upgrade_ott": [0.1] * 4,
    "score_canal_whatsapp": [0.9, 0.85, 0.4, 0.9],
    "score_canal_sms": [0.8, 0.3, 0.6, 0.8],
    "score_canal_correo": [0.1] * 4,
    "score_canal_asesor": [0.1] * 4,
})

for algoritmo, esperado in [("codicioso", 2.394), ("optimo", 2.988)]:
    c = cfg.model_copy(deep=True)
    c.asignacion.algoritmo = algoritmo
    g, info = run.correr(df, c)
    v = validar(g, df, c)
    el, cand, asg = comparar.nucleo(df, c)
    valor = comparar.metricas(cand, el, asg, c)["valor_esperado"]
    assert v["violaciones_total"] == 0
    assert np.isclose(valor, esperado)
    if algoritmo == "optimo":
        assert info["lp_entero"]
        assert np.isclose(info["valor_lp"], 1.001 * esperado)
        assert g["canal"].tolist() == ["sms", "whatsapp", "sms", ""]
    print(algoritmo, f"valor={valor:.3f}", "violaciones=0")

# Comprobación independiente del solver: 3 opciones por cliente A, B, C.
valores = [{"": 0, "whatsapp": w, "sms": s}
           for w, s in [(1.386, 1.232), (1.156, 0.408), (0.400, 0.600)]]
mejor = max(sum(valores[i][c] for i, c in enumerate(opcion))
            for opcion in product(["", "whatsapp", "sms"], repeat=3)
            if opcion.count("whatsapp") <= 1 and opcion.count("sms") <= 2)
assert np.isclose(mejor, 2.988)
print(f"Enumeración de las 27 combinaciones: óptimo={mejor:.3f}")
```

La base mínima de este ejemplo contiene las columnas utilizadas por la configuración y el motor; no sustituye el contrato de 45 columnas del archivo oficial. El chequeo fijo del PDF no aplica a sus cupos reducidos ni a sus identificadores didácticos. Para el caso completo, seguir [REPRODUCIBILIDAD.md](REPRODUCIBILIDAD.md).
