# Restricciones del reto: configuración, ejecución y pruebas

La referencia de numeración es [El reto estudiantes](planteamiento_del_reto/reto_estudiantes.pdf), páginas 3–4. Todos los valores de la tabla son los **iniciales**: al cambiar la configuración, el validador configurable comprueba las reglas nuevas; el chequeo independiente del PDF sigue comprobando los valores iniciales.

## Dónde se aplica cada condición

- **EP:** [`elegibilidad.calcular`](../nba/elegibilidad.py) aplica reglas de producto mediante [`reglas.evaluar`](../nba/reglas.py) y construye `prod_ok`.
- **EC:** la misma función aplica reglas de canal y construye `canal_ok`.
- **F:** [`candidatos.construir`](../nba/candidatos.py) combina elegibilidad, política semanal y canales permitidos en `factible`.
- **P:** `_paquetes` limita productos por contacto antes de optimizar.
- **LP:** [`asignacion.optimo`](../nba/asignacion.py) restringe cliente y cupos; `codicioso` mantiene esos límites mediante contadores.
- **V:** [`validar.validar`](../nba/validar.py) comprueba la parrilla con una implementación escalar separada. Los códigos de la tabla son los que realmente devuelve; no siempre son los números del PDF.

## Matriz R01–R16

| PDF | Condición inicial para asignar | Configuración / dato | Motor y representación matemática | Código en V |
|---|---|---|---|---|
| R01 | Cliente sin mora | Regla YAML `R01`: excluir `en_mora == 1` | EP → $e_{icp}=0$ para toda campaña excluida | `R01` |
| R02 | TER solo con riesgo E, A o B | YAML `R02`: excluir C y P en `C-TER` | EP → elimina TER del paquete | `R02` |
| R03 | TER con equipo de al menos 18 meses | YAML `R03`: excluir `edad_equipo_meses < 18` | EP → elimina TER | `R03` |
| R04 | VCH solo si no tiene Hogar | YAML `R04`: excluir `tiene_hogar == 1` | EP → elimina VCH | `R04` |
| R05 | OTT solo si falta alguna de las tres OTT | YAML `R05`: excluir `cantidad_ott >= 3` | EP → elimina OTT | `R05` |
| R06 | No repetir un producto ofertado en el mes | YAML `R06`: `productos_ofertados_mes contiene $producto` | EP → elimina la campaña de ese producto | `R06` |
| R07 | Menos de 3 quejas en 90 días | YAML `R07`: excluir `quejas_90d >= 3` | EP → elimina todas las campañas | `R07` |
| R08 | Score de producto ≥ 0,35 | `priorizacion.umbral_score_producto` | EP → elimina la campaña bajo umbral | `UMBRAL_PRODUCTO` |
| R09 | Autorización del canal digital | YAML `R08` WhatsApp, `R09` correo, `R10` SMS: excluir autorización igual a 0 | EC/F → elimina el canal para ese cliente | `R08`, `R09` o `R10`, según el canal |
| R10 | Asesor con menos de 2 llamadas previas en el mes | YAML `R11`: excluir `contactos_asesor_mes >= 2` | EC/F → elimina asesor | `R11` |
| R11 | Score de canal ≥ 0,25 | `asignacion.umbral_score_canal` | EC/F → elimina el canal bajo umbral | `UMBRAL_CANAL` |
| R12 | Producto solo por sus canales permitidos | `campanas[].canales_permitidos` | F → $e_{icp}=0$ fuera de esos canales | `CANAL_NO_PERMITIDO` |
| R13 | A lo sumo un canal por cliente y corrida | `politica_contacto.canales_por_cliente: 1` | LP: $\sum_c x_{ic}\leq1$; codicioso: una posición `canal[i]` | `CLIENTE_DUPLICADO` detecta filas repetidas; la salida tiene un campo `canal` |
| R14 | Asesor: 1 producto; digitales: hasta 2 | `canales[].max_productos` | P: $|S_{ic}|\leq k_c$; campañas distintas | `TOPE_PRODUCTOS`, `PRODUCTO_REPETIDO` |
| R15 | Como máximo 3 contactos semanales, incluido el nuevo | `politica_contacto.max_contactos_semana`, `columna_contactos_semana` | `semana_ok`: historial + 1 ≤ tope; F elimina las opciones si no cumple | `TOPE_SEMANAL` |
| R16 | No exceder cupos; dos productos consumen un contacto | `canales[].cupo`: asesor 2.500, WhatsApp 15.000, correo 30.000, SMS 40.000 | LP: $\sum_i x_{ic}\leq B_c$; codicioso: contador por canal | `CUPO_EXCEDIDO` |

Las reglas YAML viven en [`config_inicial/reglas.yaml`](../config_inicial/reglas.yaml), y los topes y umbrales en [`parametros.yaml`](../config_inicial/parametros.yaml). Las campañas y canales permitidos están en [`campanas.yaml`](../config_inicial/campanas.yaml). La consola escribe sus equivalentes en `config/`.

### Numeraciones y códigos que no deben confundirse

`R08` en el YAML significa autorización de WhatsApp; `R08` en el PDF significa umbral de producto. `R11` en el YAML significa llamadas del asesor; `R11` en el PDF significa umbral de canal. No se debe interpretar una incidencia solo por su número: hay que identificar si viene del PDF, del YAML o del validador.

`ESTRUCTURALES` en `nba/validar.py` contiene equivalencias para algunos códigos, pero el resultado de `validar()` no renombra automáticamente todas las incidencias con la numeración del PDF. En particular, `VARIOS_CANALES` está en ese diccionario, pero el código actual controla la representación de R13 mediante unicidad de filas y el único campo de canal, no emitiendo ese código.

## Pruebas existentes y qué demuestran

| Evidencia | Cobertura real |
|---|---|
| [`tests/test_chequeo_pdf.py`](../tests/test_chequeo_pdf.py), `test_el_chequeo_detecta_cada_restriccion` | Casos parametrizados R01–R15 que alteran una parrilla. Para R09 el caso inyectado es WhatsApp; R13 inyecta un canal desconocido, no dos contactos válidos al mismo cliente. |
| Mismo archivo, `test_el_chequeo_detecta_cupo_excedido` | R16: fuerza contactos por encima del cupo de asesor. |
| Mismo archivo, `test_el_chequeo_detecta_errores_de_formato` | Una fila por cliente y nombres de columnas; incluye cliente duplicado. |
| Mismo archivo, `test_ambos_algoritmos_pasan_el_chequeo_del_pdf` | Las parrillas del codicioso y del LP cumplen el chequeo fijo con datos del reto. |
| [`tests/test_motor.py`](../tests/test_motor.py), `test_cero_violaciones_y_cupos` | Ambos algoritmos pasan el validador configurable con 20.000 clientes y cupos reducidos. |
| [`tests/test_requisitos_oficiales.py`](../tests/test_requisitos_oficiales.py), `test_mas_de_un_canal_por_cliente_se_rechaza_con_mensaje_claro` | Se rechaza configurar más de un canal por cliente. |
| [`tests/test_cambios.py`](../tests/test_cambios.py) | Cambios de umbrales, cupos, canales permitidos, productos por contacto, tope semanal, llamadas, calificaciones y reglas; verifica cumplimiento con la configuración modificada. |
| [`scripts/chequeo_pdf.py`](../scripts/chequeo_pdf.py) | Recalcula las restricciones iniciales y las métricas sin importar `nba/` ni leer los YAML. |

Estos son controles de factibilidad y regresión. La optimalidad requiere además la [justificación del modelo y los chequeos numéricos](FORMULACION_MATEMATICA.md), no se deduce de tener cero violaciones.

## Supuestos de datos y límites de cobertura

- Para R02, excluir C y P equivale a admitir E, A y B **dentro del dominio oficial**. Un valor nuevo o ausente requiere validación de datos; la exclusión configurada no es una lista positiva universal.
- Para R05, el motor usa `cantidad_ott`; el chequeo del PDF usa los tres indicadores `tiene_*`. Se presupone coherencia entre ambos. Un CSV contradictorio puede producir discrepancias.
- Las reglas numéricas o categóricas con dato ausente normalmente no excluyen; `contiene` y `no_contiene` tratan la lista vacía de forma específica. El tope semanal del motor rellena ausentes con cero, mientras que V considera ausente una violación si ese cliente queda asignado. No se garantiza cumplimiento sobre una base incompleta.
- R13 se representa también por el formato: una fila por cliente, con un canal. V comprueba duplicados y cantidad de filas; el chequeo del PDF comprueba además el conjunto exacto de identificadores, estado, columnas y coherencia de campos vacíos. Conviene usar ambos para la entrega inicial.
- `max_productos` mayor que dos no cabe en el CSV actual: el motor puede construir un paquete mayor, pero la parrilla solo tiene dos columnas de campaña. La guía operativa mantiene topes de hasta dos.
- Las campañas vigentes y activas también se comprueban, aunque esa condición no tenga un número propio entre R01–R16. El reto permite agregar campañas; usar varias campañas para el mismo producto requiere definir su compatibilidad, no asumir que son productos diferentes.

Para ejecutar los controles sin modificar los entregables guardados, véase [REPRODUCIBILIDAD.md](REPRODUCIBILIDAD.md).
