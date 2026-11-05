# Verificación de la ampliación documental

Fecha: **4 de noviembre de 2026**, zona America/Bogota. Base de trabajo: commit `1109f5a` de `origin/main` («Agregar README y documentación»). Rama de revisión: `documentacion`.

## Alcance

Esta ampliación documenta el comportamiento existente: formulación, demostración bajo supuestos, trazabilidad de restricciones, utilidad exacta, ejemplo pequeño, configuración, operación y reproducción. Incluye las tres copias PDF proporcionadas en `docs/planteamiento_del_reto/`.

No cambia código Python, pruebas, dependencias declaradas, datos, YAML ni resultados CSV/JSON de `entrega/`. El texto de `entrega/INFORME.md` se precisa para mantenerlo coherente con las ecuaciones y las garantías descritas.

## Entorno de las comprobaciones

Se utilizó un entorno virtual temporal aislado de las dependencias del proyecto, en Windows 11, con acceso al repositorio en WSL. No se reconstruyó el entorno original de Python 3.9 ni se modificó `requirements.txt`.

| Componente | Versión observada |
|---|---|
| Python | 3.12.14 |
| NumPy | 2.5.4 |
| pandas | 3.0.1 |
| SciPy | 1.18.1 |
| Pydantic | 2.14.1 |
| PyYAML | 6.0.3 |
| pytest | 9.2.0 |

El entorno temporal reutiliza paquetes disponibles del runtime mediante `--system-site-packages` y añade SciPy, PyYAML y pytest dentro del entorno virtual. Estas versiones documentan la comprobación realizada; no constituyen un bloqueo completo de dependencias ni una recomendación de actualizar producción a ellas.

## Ejemplo numérico

Se extrajo y ejecutó directamente el bloque Python de [EJEMPLO_ASIGNACION.md](EJEMPLO_ASIGNACION.md), sin mantener una segunda copia de la lógica de demostración. Salida:

```text
codicioso valor=2.394 violaciones=0
optimo valor=2.988 violaciones=0
Enumeración de las 27 combinaciones: óptimo=2.988
```

El bloque también comprueba `lp_entero=True`, objetivo LP igual a `1.001 * 2.988`, asignación por canal esperada y cero violaciones con ambos algoritmos. La enumeración calcula independientemente el mejor valor del caso pequeño.

## Pruebas existentes ejecutadas

Comando, usando el Python del entorno temporal:

```bash
python -m pytest -q tests/test_motor.py tests/test_requisitos_oficiales.py
```

Salida final:

```text
18 passed in 196.57s (0:03:16)
```

Incluye operadores y ejemplos del kit, límites de cupos con ambos algoritmos, coherencia de explicaciones, réplica de la línea base oficial, mejora del optimizador con los datos oficiales, alcances de reglas, desempates y validación de configuración.

No se ejecutó nuevamente la suite completa de 88 pruebas reportada por el informe original ni las pruebas de consola Streamlit en este entorno. Tampoco se realizó una prueba visual de la consola. Los tiempos de la entrega original se conservan como históricos y no se sustituyen por los de esta comprobación documental.

## Revisión documental

Se comprueba la existencia de los destinos de enlaces locales en los Markdown de la documentación y se ejecuta `git diff --check`. Se cotejan las fórmulas y las referencias a funciones, parámetros y pruebas con el código de la base indicada. Las copias PDF se verificaron byte a byte mediante SHA-256 frente a los tres archivos proporcionados.

Para repetir o ampliar estas verificaciones, seguir [REPRODUCIBILIDAD.md](REPRODUCIBILIDAD.md). La prueba de integralidad es un argumento sobre la matriz del modelo reducido, no una afirmación de que estas 18 pruebas cubran cualquier cambio futuro de formulación o de datos.
