# Orquestador NBA configurable — Informe de solución

Hackatón Claro Colombia · Universidad del Rosario · Reto «Orquestador NBA configurable»

Todas las cifras de este informe salen de la base oficial del reto (`clientes.csv`, 100.000 clientes, 45 variables; los datos son sintéticos, según el propio diccionario) y de la configuración inicial del PDF.

Este informe conserva los resultados de la entrega original. La ampliación documental no regenera sus archivos ni atribuye esos tiempos al entorno actual. La [formulación completa](../docs/FORMULACION_MATEMATICA.md), la [matriz de restricciones](../docs/RESTRICCIONES.md), el [ejemplo reproducible](../docs/EJEMPLO_ASIGNACION.md) y la [guía de reproducción](../docs/REPRODUCIBILIDAD.md) desarrollan y precisan la explicación de la solución.

## 1. Resultado

| Indicador | Línea base oficial (PDF) | Nuestra réplica de la línea base | **Nuestro motor (óptimo)** |
|---|---|---|---|
| Violaciones de restricciones | 0 | 0 | **0** |
| Valor esperado | 10.241,5 | 10.241,6 | **10.940,0** (+6,8 %) |
| Clientes con acción | 55.393 | 55.393 | **60.422** |
| Productos asignados | 70.443 | 70.444 | **76.841** |
| Indicador de jerarquía | 99,7 % | 99,68 % | **99,84 %** |
| Tiempo de la corrida | — | 0,5 s | 12 s (17 s con explicaciones) |

Que nuestra réplica de la línea base reproduzca las cifras oficiales (mismo número de clientes, valor con diferencia de 0,1, un producto de diferencia) valida que interpretamos igual los datos y las restricciones. La diferencia residual de un producto probablemente viene del orden de los empates entre clientes en la implementación oficial, que no conocemos. Esta réplica es una prueba automática de regresión.

La parrilla entregada pasa dos verificaciones independientes entre sí, con 0 violaciones: el validador del motor y un chequeo escrito directamente desde el texto del PDF.

## 2. Qué se pidió y cómo lo abordamos

Decidir, para cada cliente, qué productos (Hogar, Terminales, OTT) ofrecer y por qué canal (asesor, WhatsApp, correo, SMS), maximizando el valor esperado sin violar ninguna de las 16 restricciones, y con reglas que negocio cambie sin tocar código.

Principios de diseño:
1. **Reglas, umbrales y cupos de negocio viven en la configuración** (`config/*.yaml`). Las constantes de implementación (tolerancias, bonos y `EPS_DESEMPATE`) se identifican en la formulación.
2. **Primero se cumple, después se optimiza.** El validador es un módulo independiente del motor.
3. **Cada decisión se explica**, con la misma fuente para la parrilla, el archivo de explicaciones y la consola.

## 3. Arquitectura

```
config/ + datos → Elegibilidad → Candidatos → Asignación → Parrilla + razón
                                                   └──────→ Explicaciones / resumen
                    Validador (independiente, lee solo la config y la parrilla)
                    Chequeo del PDF (scripts/chequeo_pdf.py: ni siquiera lee la config)
```

| Módulo | Responsabilidad |
|---|---|
| `nba/config.py` | Esquema validado (Pydantic) de campañas, reglas, canales, prioridad y política de contacto. |
| `nba/reglas.py` | Intérprete genérico y vectorizado de reglas (`== != < <= > >= en no_en contiene no_contiene`). |
| `nba/elegibilidad.py` | Matrices cliente × producto y cliente × canal, con la regla que excluyó cada celda. |
| `nba/candidatos.py` | Mejor paquete de hasta *k* productos por cliente y canal, con desempate configurable. |
| `nba/asignacion.py` | Reparto de cupos: óptimo (programación lineal) o codicioso (baseline). |
| `nba/explicar.py` | Registro estructurado por cliente, frase, resumen y costo de los cupos. |
| `nba/validar.py` | Validador independiente de las restricciones y de las métricas. |
| `app/consola.py` | Consola de negocio (Streamlit). |

**Formato de la configuración.** El diccionario oficial propone tres archivos JSON y permite cambiar el formato siempre que se conserven los campos y su significado. Usamos YAML (campañas, reglas y parámetros) con todos los campos del diccionario: alcance de las reglas en los cinco niveles (global, campaña, producto, objetivo, canal), `desempate`, `criterio` y `orden_preferencia` de canal, pesos que suman 1, cupos y topes.

## 4. Cumplimiento de las restricciones

El validador revisa cliente por cliente, con su propia implementación escalar de las reglas, leyendo umbrales, cupos, campañas y reglas desde la configuración. Cubre las reglas de elegibilidad y de canal configuradas, los umbrales de producto y de canal, los canales permitidos por campaña, un solo canal por cliente, los topes de productos por contacto, el tope semanal y los cupos.

Además, `scripts/chequeo_pdf.py` verifica las 16 restricciones y el formato de la parrilla con las cifras escritas a mano desde el PDF, sin importar el motor ni leer la configuración. Sus pruebas inyectan una violación de cada restricción y verifican que la detecta.

Nota: la numeración de reglas del kit (`config_reglas.csv`) no coincide con la del PDF (en el kit, R08–R10 son las autorizaciones de canal y R11 el tope de llamadas del asesor). Los umbrales de producto (0,35) y de canal (0,25) viven en los parámetros, no en la tabla de reglas.

## 5. Optimización de cupos

La línea base decide cliente por cliente y agota los cupos escasos con los primeros clientes que recorre. Nuestra formulación:

1. Para cada cliente y canal se arma el mejor paquete de hasta *k* productos (*k* = productos por contacto del canal) y se calcula su valor `Σ score_producto × score_canal × valor_negocio`.
2. Elegir un canal por cliente respetando los cupos es un **problema de transporte**: se resuelve como programación lineal (HiGHS, `scipy`), con una variable por par cliente–canal con opciones.
3. En la corrida final se reportó una solución **entera**. La matriz cliente–canal es de incidencia bipartita y, con cupos enteros, admite un óptimo entero de la relajación. La [demostración](../docs/FORMULACION_MATEMATICA.md) explica los supuestos de equivalencia entre los paquetes y el modelo original. Si se recurre al redondeo fraccionario de respaldo, no se conserva una garantía de óptimo.
4. Las dos campañas de un contacto se ordenan por puntaje, como pide el diccionario (`campana_1` es la de mayor puntaje), con el desempate configurado.

La pregunta del PDF «¿dos productos por WhatsApp o uno por asesor?» se resuelve sola: cada canal compite con el valor de su mejor paquete.

Precisión sobre los coeficientes: con los parámetros iniciales, `EPS_DESEMPATE` hace que la utilidad LP sea 1,001 veces el valor esperado, por lo que conserva el mismo óptimo. Las cifras de valor de este informe son las de la métrica original; los precios sombra guardados son de la utilidad LP y se dividen por 1,001 para expresarlos en valor real.

**Qué muestran los cupos:**

| Canal | Usado / cupo | Valor de un cupo adicional |
|---|---|---|
| Asesor | 2.500 / 2.500 | 0,093 |
| WhatsApp | 15.000 / 15.000 | 0,065 |
| Correo | 18.806 / 30.000 | 0 |
| SMS | 24.116 / 40.000 | 0 |

Solo asesor y WhatsApp limitan. 19.204 clientes recibieron su segundo mejor canal porque el ideal estaba lleno, con un costo de 597 de valor (5,5 % del total); otros 385 quedaron sin acción por falta de cupo (23 de valor no capturado). El valor de un cupo adicional sale del propio LP y le dice a negocio cuánto ganaría ampliando cada canal.

Clientes sin acción (39.578): 35.436 sin campaña elegible, 2.369 sin canal habilitado, 1.388 por el tope semanal y 385 por cupo.

## 6. Jerarquía de negocio vs. valor

El reto pide dejar claro qué balance se eligió y cómo se cambia. **Elegimos α = 0** (maximizar el valor esperado; la jerarquía se reporta como indicador). El balance se cambia con `priorizacion.alpha` (0 a 1), que mezcla el valor de negocio de cada producto con su nivel de jerarquía; el orden de la jerarquía está en `priorizacion.jerarquia`.

| α | Valor esperado | Clientes con acción | Jerarquía |
|---|---|---|---|
| **0 (elegido)** | **10.940,0** | 60.422 | 99,84 % |
| 0,25 | 10.935,6 | 60.263 | 99,88 % |
| 0,5 | 10.915,6 | 59.947 | 99,92 % |
| 0,75 | 10.855,3 | 59.320 | 99,95 % |
| 1 | 10.615,4 | 57.289 | 99,98 % |

Con la jerarquía inicial (Hogar > Terminales > OTT) el valor de negocio ya ordena los productos igual, por eso priorizar la jerarquía cuesta poco: pasar de α = 0 a α = 1 sube 0,14 puntos de jerarquía a cambio de 3,0 % del valor. El parámetro importa cuando negocio contradice ese orden; los tests lo muestran invirtiendo la jerarquía. El indicador de jerarquía se calcula como el porcentaje de clientes con acción que recibieron su producto elegible de mayor jerarquía (el PDF no precisa la definición).

### Peso del modelo frente al valor de negocio

Otro cambio que negocio debe poder pedir es «dar más o menos peso al modelo frente al valor de negocio». La utilidad exacta por oferta es `score_producto^peso_modelo × score_canal × ((1-alpha)·valor_negocio + alpha·nivel_jerarquia + 0,001·valor_negocio)^peso_valor`. Con `alpha=0` y exponentes en 1 es 1,001 veces la métrica del reto y conserva el mismo óptimo. Subir `peso_modelo` favorece scores de producto mayores; subir `peso_valor`, el valor efectivo mayor. Los pesos 0,6 / 0,2 / 0,2 del diccionario (que deben sumar 1) rigen la selección de la línea base codiciosa. La jerarquía ponderada no implica prioridad lexicográfica estricta.

| peso modelo | peso valor | Valor esperado | Prob. de compra media de lo ofrecido | Valor medio por producto |
|---|---|---|---|---|
| **1 (elegido)** | **1 (elegido)** | **10.940,0** | 0,5669 | 0,605 |
| 3 | 1 | 10.786,5 | 0,5726 | 0,597 |
| 1 | 3 | 10.810,4 | 0,5671 | 0,609 |
| 1 | 0 | 10.792,0 | 0,5703 | 0,593 |

El efecto va en la dirección esperada. Moverse de 1 y 1 siempre cuesta algo de valor esperado, porque ese punto es el máximo de la métrica. La vista previa de la consola muestra cuánto.

## 7. Explicabilidad

Cada cliente tiene un registro estructurado del que salen tres productos:
- **`razon` en la parrilla:** el cálculo por producto (`prob. compra × prob. canal × valor = valor esperado`), los productos no ofrecidos y por qué, y si el cupo del canal ideal se agotó. Ejemplo: «Se ofrece Venta cruzada Hogar [0.48 compra x 0.63 sms x 1.0 valor = 0.304] por sms; valor esperado 0.304. No se ofrece: C-TER (R02 Terminales solo con calificación E, A o B)…».
- **`explicaciones.jsonl.gz`:** el registro completo: productos, descartados con su motivo y el valor de cada canal.
- **Consola, sección Cliente:** una frase corta para el asesor, la tabla de decisión y las alternativas descartadas con su motivo.

## 8. Configurabilidad y consola

Los siete tipos de cambio del reto se resuelven editando la configuración:

| Cambio | Dónde |
|---|---|
| Campañas: lanzar, pausar, cambiar canales o vigencia | `campanas` |
| Reglas: crear sobre cualquier columna, limitar por calificación, aplicar a un grupo (por campaña, producto u objetivo), apagar | `reglas` |
| Umbrales | `priorizacion.umbral_score_producto`, `asignacion.umbral_score_canal` |
| Prioridad: jerarquía, desempate, balance valor/jerarquía, peso del modelo frente al valor | `priorizacion` |
| Canales y cupos: cupo, productos por contacto, canal nuevo, criterio de elección de canal | `canales`, `asignacion` |
| Política de contacto: tope semanal, llamadas de asesor | `politica_contacto`, regla de llamadas |
| Datos: columna nueva en una regla | cualquier columna de la base |

La consola (`streamlit run app/consola.py`) tiene cuatro secciones de trabajo: **Tablero** (estado de la parrilla, métricas con su variación frente al baseline o a la versión anterior, avisos, uso de cupos, embudo de clientes, composición por campaña y canal, reglas que más excluyen, y casos reales de cada situación), **Cambiar configuración** (edición con **vista previa del impacto** antes de aplicar: valor, clientes, jerarquía, quién gana o pierde acción, y validación de 0 violaciones; controles directos para el tope de llamadas del asesor y las calificaciones permitidas por campaña), **Cliente** (explicación) y **Base de datos**, más un historial de **Versiones** con restauración.

## 9. Verificación

- **Regresión contra la línea base oficial** (`tests/test_requisitos_oficiales.py`): con los datos oficiales la réplica reproduce las cifras del PDF.
- **Chequeo independiente escrito desde el PDF** (`scripts/chequeo_pdf.py`): no importa nada del motor ni lee la configuración. Revisa las 16 restricciones y el formato, y recalcula valor y jerarquía desde cero.
- **88 pruebas automáticas.** Entre ellas, una por cada tipo de cambio de negocio, a nivel de motor y también desde la consola; cada una comprueba que la parrilla cambia como se espera y que el validador sigue en 0 violaciones.
- **Pruebas de mutación:** al romper a propósito piezas del motor (operador `en`, peso del modelo, alcance por producto, desempate, controles de la consola), las pruebas correspondientes fallan.
- La corrida completa es **determinista** (dos corridas dan la misma parrilla) y las métricas rápidas de la consola coinciden con las del validador.
- **Defectos hallados y corregidos** en el camino, entre ellos: con α = 1 un producto dejaba de asignarse; los pesos modelo/valor no afectaban al óptimo; la consola borraba el campo `objetivo` de las campañas al aplicar un cambio.

## 10. Limitaciones y supuestos

- **Un canal por cliente.** `politica_contacto.canales_por_cliente` distinto de 1 se rechaza con un mensaje claro: el motor asigna un solo canal por cliente (restricción R13). Soportar varios canales cambiaría la formulación del optimizador.
- **Optimalidad:** para los parámetros iniciales se justifica por la reducción a paquetes y la integralidad del LP bipartito, bajo los supuestos detallados en la formulación. La ejecución debe terminar correctamente y producir una solución entera. Con otros pesos o bonos se optimiza otra utilidad; el redondeo fraccionario no tiene garantía de óptimo.
- **Formato:** la parrilla tiene dos columnas de campaña. Topes superiores a dos productos requieren adaptar la salida; la demostración del modelo interno no corrige por sí sola esa diferencia de representación.
- **Interpretación de R15:** un cliente puede contactarse si `contactos_semana_actual + 1 ≤ tope`.
- **Diferencia de un producto** frente a la línea base oficial (70.444 frente a 70.443), probablemente por el orden de empates entre clientes.
- **Consola:** el simulador de pruebas no puede teclear dentro de las tablas editables, así que esos cambios se prueban reemplazando el contenido de la tabla en el estado de la sesión. Conviene un recorrido manual en el navegador.
- **Producto:** la consola no tiene usuarios ni roles, y registra el cambio pero no quién lo hizo. Está pensada para un analista de mercadeo; para producción se rehacería como aplicación interna con autenticación y aprobación.
- Las pruebas de cambios usan 20.000 clientes con los cupos reducidos a la quinta parte; la validación con 100.000 se hace en la corrida final.

## 11. Cómo reproducir

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q                                   # 88 pruebas
.venv/bin/python scripts/generar_entrega.py           # regenera esta carpeta (datos oficiales + config_inicial/)
.venv/bin/python -m nba.validar entrega/parrilla.csv --clientes data/oficial/clientes.csv --config entrega/config
.venv/bin/python scripts/chequeo_pdf.py entrega/parrilla.csv data/oficial/clientes.csv   # chequeo independiente del PDF
.venv/bin/streamlit run app/consola.py                # consola
```

## 12. Contenido de esta carpeta

| Archivo | Contenido |
|---|---|
| `parrilla.csv` | Parrilla final: una fila por cliente (`id_cliente, estado, canal, campana_1, campana_2, razon`). |
| `explicaciones.jsonl.gz` | Registro de explicación por cliente. |
| `resumen.json` | Embudo por regla, cupos, costo de cupos. |
| `validacion.json` | Resultado del validador y métricas. |
| `comparacion.json` | Baseline vs. óptimo y sensibilidad a α. |
| `config/` | Configuración inicial usada para generar esta parrilla. |

## 13. Trabajo futuro

Constructor de reglas en lenguaje de negocio, flujo de aprobación con autoría, entrega de la frase por cliente a la herramienta del asesor, y soporte de varios canales por cliente.
