# Formulación matemática y alcance del óptimo

Este documento describe el modelo **que ya implementa el repositorio**. No propone cambios al motor. La métrica y las restricciones vienen de [El reto estudiantes](planteamiento_del_reto/reto_estudiantes.pdf), páginas 3–6; la elección del algoritmo corresponde al equipo.

La implementación relevante está en [`elegibilidad.py`](../nba/elegibilidad.py), [`candidatos.py`](../nba/candidatos.py) y [`asignacion.py`](../nba/asignacion.py). La correspondencia R01–R16 se detalla en [RESTRICCIONES.md](RESTRICCIONES.md).

## 1. Conjuntos y parámetros

| Símbolo | Significado | Fuente |
|---|---|---|
| $I$ | Clientes de la corrida | Filas de `clientes.csv` |
| $P$ | Campañas activas y vigentes | `Config.campanas_vigentes()` |
| $C$ | Canales configurados | `parametros.yaml`, `canales` |
| $s_{ip}$ | Score del cliente $i$ para la campaña $p$ | `campanas[p].columna_score` |
| $q_{ic}$ | Score del cliente $i$ en el canal $c$ | `canales[c].columna_score` |
| $v_p$ | Valor de negocio de la campaña | `campanas[p].valor_negocio` |
| $B_c$ | Cupo entero de contactos del canal | `canales[c].cupo` |
| $k_c$ | Máximo de productos en un contacto | `canales[c].max_productos` |
| $e_{icp}$ | 1 si la combinación cliente–canal–campaña está habilitada; 0 si no | Máscara `factible` |

En el kit inicial hay una campaña por producto: C-VCH, C-TER y C-OTT. En las ecuaciones, $p$ identifica una campaña. El código del producto se usa, entre otras cosas, para consultar el historial mensual.

La máscara $e$ reúne las reglas activas de elegibilidad, los umbrales de producto y canal, las reglas de canal, el tope semanal y los canales permitidos por campaña. Un cupo cero no cambia la elegibilidad: impide asignar el canal en el optimizador.

Los scores llegan calculados. Este sistema no entrena modelos ni estima esas probabilidades. La métrica impuesta por el reto, sin recalibrarla, atribuye a cada oferta el valor:

$$
r_{icp}=s_{ip}\,q_{ic}\,v_p.
$$

## 2. Modelo con decisiones de canal y producto

Una forma explícita de expresar el problema original utiliza dos variables binarias:

- $y_{ic}=1$ si se contacta al cliente $i$ por el canal $c$.
- $z_{icp}=1$ si se incluye la campaña $p$ en ese contacto.

La función objetivo de valor esperado es:

$$
\max \sum_{i\in I}\sum_{c\in C}\sum_{p\in P}r_{icp}z_{icp}.
$$

Las restricciones son:

$$
\sum_{c\in C}y_{ic}\leq 1 \qquad \forall i\in I,
$$

$$
\sum_{i\in I}y_{ic}\leq B_c \qquad \forall c\in C,
$$

$$
z_{icp}\leq e_{icp}y_{ic} \qquad \forall i,c,p,
$$

$$
y_{ic}\leq\sum_{p\in P}z_{icp}\leq k_cy_{ic} \qquad \forall i,c,
$$

$$
y_{ic},z_{icp}\in\{0,1\}.
$$

La primera condición representa R13; la segunda, R16; la última desigualdad doble evita contactos vacíos y representa R14. Las demás restricciones se incorporan a través de $e$. No es necesario introducir una variable para `sin_accion`: corresponde a $\sum_c y_{ic}=0$.

Esta es una descripción matemática equivalente bajo los supuestos de la sección 5. El código no entrega todas estas variables a un solver entero: elimina primero las decisiones de producto mediante paquetes.

## 3. Utilidad que realmente usa el motor

La métrica reportada siempre usa $r_{icp}$. La utilidad de selección puede ser distinta. Sean $a=\texttt{alpha}$, $m=\texttt{peso_modelo}$, $w=\texttt{peso_valor}$ y $\epsilon=10^{-3}$ (`EPS_DESEMPATE`). Si hay $L$ campañas vigentes ordenadas, el nivel de jerarquía es:

$$
h_p=1-\frac{\operatorname{pos}(p)}{L-1},
$$

con posiciones desde cero; para $L=1$, $h_p=1$. Las campañas vigentes no listadas se añaden al final, en su orden de configuración. Para las tres campañas iniciales, los niveles son 1, 0,5 y 0.

La implementación calcula:

$$
\widetilde v_p=(1-a)v_p+ah_p,
\qquad
u_{icp}=s_{ip}^{m}\,q_{ic}\,(\widetilde v_p+\epsilon v_p)^{w}.
$$

Consecuencias:

- Con `alpha=0` y ambos exponentes en 1, $u_{icp}=1{,}001\,r_{icp}$. **No son coeficientes numéricamente idénticos**, pero el factor positivo común conserva exactamente las soluciones óptimas de la métrica del reto, en aritmética exacta.
- Con otros parámetros se maximiza una utilidad elegida por negocio. El valor reportado sigue siendo la métrica original; no se debe presentar esa solución como máximo del valor puro.
- `alpha=1` favorece la jerarquía, pero mantiene scores y el término $\epsilon v_p$. No impone un orden lexicográfico estricto ni maximiza directamente el porcentaje de jerarquía.
- $\epsilon$ evita que el último nivel de jerarquía anule el valor de un producto. Fuera del caso por defecto puede modificar preferencias cercanas: no es un desempate lexicográfico exacto.

### Puntaje de la línea base y orden de salida

El algoritmo `codicioso` selecciona productos con otro puntaje:

$$
t_{ip}=w_s s_{ip}+w_v v_p+w_h h_p,
\qquad w_s+w_v+w_h=1.
$$

Los pesos iniciales son 0,6 / 0,2 / 0,2. En modo `jerarquia_estricta`, ese puntaje es $10h_p+s_{ip}$: es una codificación por bono fijo, no una garantía lexicográfica para cualquier número de campañas.

Los empates de productos se resuelven con `priorizacion.desempate`, cuyos criterios pueden ser `score_producto`, `valor_negocio` y `jerarquia`. Si siguen empatados, conserva el orden de campañas. Después de asignar, ambos algoritmos ordenan las campañas elegidas por $t_{ip}$ para producir `campana_1` y `campana_2`; esto no cambia el conjunto asignado.

### Preferencia fija de canales

Con `criterio_canal: score_canal`, el optimizador utiliza directamente la utilidad del paquete; no elige primero el canal de mayor score para cada cliente de forma aislada.

Con `criterio_canal: orden_preferencia`, añade al paquete:

$$
U'_{ic}=U_{ic}+10\,(|C|-\operatorname{rango}(c)).
$$

El rango empieza en cero; un canal no listado recibe como rango la longitud de la lista de preferencias. Es un **bono aditivo por contacto**, no una secuencia de optimizaciones lexicográficas. La garantía de LP aplica a $U'$, no al valor puro ni a una jerarquía estricta de canales. El bono fijo tampoco garantiza dominar utilidades arbitrarias al cambiar la configuración.

## 4. Reducción a paquetes y LP implementado

Para cada par $(i,c)$ se toman las campañas habilitadas de mayor $u_{icp}$, hasta $k_c$. Se obtiene un paquete $S_{ic}$, su utilidad $U_{ic}$ y su valor real $R_{ic}$:

$$
U_{ic}=\sum_{p\in S_{ic}}u_{icp},
\qquad R_{ic}=\sum_{p\in S_{ic}}r_{icp}.
$$

Sea $E=\{(i,c):S_{ic}\ne\varnothing\}$. El optimizador crea una variable $x_{ic}$ solo para esos pares. Resuelve:

$$
\max \sum_{(i,c)\in E}U_{ic}x_{ic}
$$

sujeto a:

$$
\sum_{c:(i,c)\in E}x_{ic}\leq1 \quad\forall i,
\qquad
\sum_{i:(i,c)\in E}x_{ic}\leq B_c \quad\forall c,
\qquad 0\leq x_{ic}\leq1.
$$

Se usa $U'$ en lugar de $U$ si se activó la preferencia fija de canales. En [`optimo()`](../nba/asignacion.py), `ii,jj` enumeran $E$, `a_cli` y `a_can` son las matrices de las dos familias de restricciones, y `v` contiene los coeficientes del objetivo. Como `linprog` minimiza, recibe `-v`, con `bounds=(0,1)` y `method="highs"`. La [documentación de SciPy](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html) describe estos argumentos y el estado de terminación.

## 5. Por qué esta reducción conserva el óptimo

La justificación requiere: utilidades finitas y no negativas; valor aditivo por oferta; un contacto consume un cupo, independientemente de llevar uno o dos productos; las decisiones de producto no consumen recursos globales adicionales. Se supone además una base válida y coherente con el diccionario, y campañas distintas para los productos del kit.

**Paso 1: el mejor paquete local basta.** Fijado un contacto $(i,c)$, escoger hasta $k_c$ campañas de mayor utilidad es óptimo: si un paquete contiene una campaña de menor utilidad que otra habilitada no elegida, se pueden intercambiar sin perder factibilidad y sin reducir utilidad. Repetir esos intercambios produce $S_{ic}$. Al ser las utilidades no negativas, completar el paquete hasta el tope tampoco perjudica.

**Paso 2: no se pierde una solución global.** En cualquier solución del modelo completo, se puede sustituir el paquete de cada contacto por $S_{ic}$. Se mantienen el cliente, el canal y el consumo de cupos; solo mejora o se conserva el objetivo. Recíprocamente, cada asignación binaria del modelo reducido se expande usando sus paquetes. Por tanto, ambos modelos tienen el mismo valor óptimo para la utilidad elegida.

**Paso 3: la relajación lineal tiene vértices enteros.** Cada columna de la matriz reducida tiene dos unos: uno en la fila del cliente y otro en la del canal. Es la matriz de incidencia de un grafo bipartito. Cambiando el signo de las filas de canales se obtiene una matriz de incidencia orientada. Para ver su unimodularidad total, considérese cualquier submatriz cuadrada: si una columna tiene cero o un elemento no nulo, su determinante se reduce por expansión; si todas tienen dos, cada una suma cero y el determinante es cero. Por inducción, todo menor vale 0, 1 o −1. Cambiar signos y agregar cotas unitarias conserva esa propiedad.

Los lados derechos son enteros (1 y los cupos $B_c$), por lo que los vértices del poliedro son enteros. La región es no vacía ($x=0$) y acotada; existe un óptimo en un vértice. Así, **existe un óptimo binario del LP**, sin necesidad de imponer integridad mediante MILP. El resultado general sobre incidencia bipartita e integralidad se desarrolla en las [notas de Michel X. Goemans, MIT, sección 3](https://math.mit.edu/~goemans/18433S07/matching-notes.pdf).

Esto no significa que cualquier solución óptima de un LP sea entera: combinaciones convexas de óptimos empatados pueden ser fraccionarias. La afirmación se refiere a sus vértices y a la existencia de un óptimo entero.

## 6. Garantía matemática y comprobación numérica

El código exige `res.status == 0`; de lo contrario, lanza `RuntimeError`. Después verifica que cada coordenada esté a menos de $10^{-6}$ de 0 o de 1 y registra `lp_entero`. Con una solución entera, extraer los pares seleccionados conserva el objetivo del LP, salvo tolerancias numéricas.

Si recibe fracciones, el respaldo recorre las variables de mayor a menor $x$ y acepta contactos que aún tienen cupo y cliente libre. **Ese redondeo mantiene los límites de asignación, pero no tiene garantía de optimalidad.** No hay un respaldo lagrangiano implementado. Tampoco se comprueba ni persiste un certificado dual completo en los archivos de entrega.

Para sostener que una corrida maximizó el valor del reto se deben reunir:

1. Los supuestos de la sección 5 y los datos/configuración correspondientes.
2. `algoritmo=optimo`, `criterio_canal=score_canal`, `alpha=0`, exponentes en 1.
3. Terminación exitosa del solver y `lp_entero=True`, sin depender de redondeo fraccionario.
4. Parrilla final sin violaciones, revisada con la misma configuración. El chequeo fijo del PDF solo aplica a la configuración inicial.

Superar al codicioso o pasar el validador por sí solos no demuestran optimalidad. La demostración proviene de la equivalencia de paquetes y la estructura del LP; los chequeos confirman que la ejecución corresponde a ese modelo. Cambiar $a,m,w$ conserva la estructura entera, pero cambia qué objetivo se maximiza.

### Precios sombra

El motor toma el negativo del marginal de cada restricción de cupo porque resolvió una minimización con `-v`. Son sensibilidades locales del objetivo optimizado, como explica [SciPy](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html). Con los parámetros por defecto están escaladas por 1,001 respecto al valor real; dividir por ese factor las expresa en unidades de la métrica. Con otros pesos son unidades de utilidad. No son dinero ni una promesa de ganancia lineal para aumentos grandes de capacidad. En modo `orden_preferencia` no se reportan.

## 7. Límites de la demostración y de la salida

- Cupos por producto, presupuestos con costos distintos, combinaciones con sinergias, cuotas entre grupos o varios canales por cliente requieren revisar la reducción y la matriz. La prueba no se hereda automáticamente.
- El código presupone scores y valores válidos; Pydantic valida la estructura de configuración, no toda la calidad del CSV. Datos faltantes o contradictorios pueden romper la correspondencia con las reglas del negocio.
- El paquete interno admite un tope configurable, pero el CSV solo escribe `campana_1` y `campana_2`. Para una entrega coherente con este formato se deben usar topes de hasta dos productos. Más productos requieren adaptar la salida antes de afirmar equivalencia entre la solución interna y la parrilla.
- La solución exacta puede no ser única. El orden estable del codicioso no constituye una regla de desempate entre óptimos globales del solver; cambios de versión pueden escoger otra parrilla con igual objetivo.

## 8. Secuencia de los algoritmos

El flujo del optimizador implementado puede leerse así:

```text
cargar configuración y campañas vigentes
evaluar restricciones por cliente, campaña y canal
para cada (cliente, canal):
    filtrar campañas habilitadas
    ordenar por utilidad u; resolver empates configurados
    conservar hasta k_c campañas y sumar su utilidad
crear una variable por paquete no vacío
resolver LP de máxima utilidad, con un canal por cliente y cupos B_c
exigir terminación exitosa y comprobar integralidad numérica
extraer asignaciones; si hay fracciones, usar el respaldo sin garantía de óptimo
ordenar campañas elegidas por puntaje para la salida
construir parrilla, explicaciones y métricas
validar por separado contra la misma configuración
```

El codicioso reemplaza las etapas de LP por: ordenar clientes por su mejor puntaje de campaña, recorrerlos, escoger el primer canal habilitado con cupo según score u orden de preferencia y cargar sus mejores campañas por puntaje. Sus empates entre clientes y canales conservan el orden de entrada. No reconsidera decisiones previas; por eso no tiene una garantía general de óptimo.

Con $N$ clientes y $M$ canales hay como máximo $NM$ variables LP. Cada columna aporta dos elementos no nulos a las restricciones de cliente y canal; se almacenan con matrices dispersas. La construcción de candidatos utiliza matrices de tamaño proporcional a $N M |P|$ y ordena campañas por par cliente–canal. Los tiempos históricos no son una garantía de rendimiento para más campañas, otros equipos o datos nuevos.

Continúa con el [ejemplo numérico reproducible](EJEMPLO_ASIGNACION.md) y la [guía de reproducción](REPRODUCIBILIDAD.md).
