# Instalación, ejecución y reproducción de resultados

Los comandos siguientes parten de la raíz del repositorio. Hay dos usos distintos: reproducir la configuración inicial del reto (`config_inicial/`) y ejecutar una estrategia de negocio editable (`config/`). La carpeta `entrega/config/` es la instantánea asociada a los entregables guardados.

## 1. Preparar el entorno

El proyecto se desarrolló originalmente para Python 3.9. Las dependencias están en [`requirements.txt`](../requirements.txt); Pydantic debe ser v2. **No hay un archivo de versiones bloqueadas del entorno original**: instalar hoy los requisitos no garantiza reproducir exactamente sus versiones ni sus tiempos.

En Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python --version
.venv/bin/python -m pip freeze
```

En Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip freeze
```

En el resto de esta guía se muestra la ruta Linux. En Windows, sustituir `.venv/bin/python` por `.venv\Scripts\python.exe` y `export VARIABLE=valor` por `$env:VARIABLE="valor"`.

## 2. Generar y validar una corrida aparte

Crear una carpeta de salida propia evita reemplazar los resultados entregados:

```bash
mkdir -p /tmp/claro-reproduccion
.venv/bin/python -m nba.run --clientes data/oficial/clientes.csv --config config_inicial \
    --algoritmo optimo --alpha 0 \
    --out /tmp/claro-reproduccion/parrilla.csv \
    --explicaciones /tmp/claro-reproduccion/explicaciones.jsonl.gz \
    --resumen /tmp/claro-reproduccion/resumen.json

.venv/bin/python -m nba.validar /tmp/claro-reproduccion/parrilla.csv \
    --clientes data/oficial/clientes.csv --config config_inicial

.venv/bin/python scripts/chequeo_pdf.py \
    /tmp/claro-reproduccion/parrilla.csv data/oficial/clientes.csv
```

En Windows, crear una carpeta equivalente dentro de `$env:TEMP` y usar sus rutas completas en cada argumento. Los continuadores `\` de los ejemplos anteriores son de Bash; en PowerShell se puede escribir cada comando en una sola línea.

La consola de `nba.run` informa `lp_entero` y `valor_lp`. Para la garantía del valor puro también deben estar en 1 los exponentes de modelo y valor, y en `score_canal` el criterio de canal. Esos son los valores de `config_inicial/`. `--alpha` y `--algoritmo` solo sustituyen esos campos para la corrida; no guardan los YAML.

El valor LP por defecto es 1,001 veces la métrica real. La métrica reportada por el validador es la del reto, redondeada a dos decimales. Véanse las [ecuaciones y condiciones de optimalidad](FORMULACION_MATEMATICA.md).

Para comparar con la línea base, repetir `nba.run` con `--algoritmo codicioso` y otra ruta de salida. Usar el mismo CSV y la misma configuración en generación y validación. Un código de salida 1 en los validadores indica violaciones; revisar el detalle antes de interpretar el valor.

### Qué validador utilizar

| Situación | Comprobación |
|---|---|
| Configuración inicial, sin cambios de reglas o cupos | Validador configurable **y** chequeo fijo del PDF |
| Estrategia modificada o campaña/canal nuevo | Validador configurable con exactamente esos YAML; el chequeo fijo no describe ese escenario |
| Parrilla ya guardada en `entrega/` | Validador con `entrega/config/` y base oficial; además, chequeo del PDF si mantiene la configuración inicial |

El script independiente también comprueba aspectos del formato que no cubre completamente el validador configurable. Las coberturas y numeraciones están en [RESTRICCIONES.md](RESTRICCIONES.md).

## 3. Pruebas

```bash
# Operadores, casos del kit, ambos algoritmos y requisitos oficiales
.venv/bin/python -m pytest -q tests/test_motor.py tests/test_requisitos_oficiales.py

# Chequeo fijo y casos que introducen violaciones a propósito
.venv/bin/python -m pytest -q tests/test_chequeo_pdf.py

# Cambios de negocio y pruebas de consola
.venv/bin/python -m pytest -q tests/test_cambios.py tests/test_consola_cambios.py tests/test_consola.py

# Suite completa
.venv/bin/python -m pytest -q
```

Las pruebas de consola necesitan Streamlit. La duración depende del equipo y del entorno. Algunas pruebas leen la parrilla de `entrega/`; otras generan corridas en memoria. El informe histórico registra 88 pruebas; una afirmación sobre el estado actual debe acompañarse de la salida de la ejecución correspondiente.

El [ejemplo pequeño](EJEMPLO_ASIGNACION.md) se puede ejecutar por separado: verifica dos algoritmos, cero violaciones y el óptimo por enumeración exhaustiva de 27 combinaciones, sin usar los archivos de entrega.

## 4. Consola y recuperación

```bash
.venv/bin/python -m streamlit run app/consola.py
```

Para trabajar en una copia de configuración en lugar de la carpeta viva:

```bash
cp -R config_inicial /tmp/claro-reproduccion/config
export NBA_CONFIG_DIR=/tmp/claro-reproduccion/config
export NBA_CLIENTES="$PWD/data/oficial/clientes.csv"
.venv/bin/python -m streamlit run app/consola.py
```

La variable `NBA_CONFIG_DIR` afecta a la consola; la CLI recibe la carpeta con `--config`. Lo mismo ocurre con `NBA_CLIENTES` frente a `--clientes`. El historial se guarda dentro de la carpeta de configuración seleccionada. Los pasos de cambio, restauración y diagnóstico están en [GUIA_CONSOLA.md](GUIA_CONSOLA.md).

## 5. Regenerar la entrega publicada

```bash
.venv/bin/python scripts/generar_entrega.py
```

Este comando **reemplaza** archivos de `entrega/` y guarda una instantánea de la configuración. Usa por defecto la base oficial y `config_inicial/`. Admite argumentos posicionales `[clientes.csv] [carpeta_config]`. No regenera automáticamente el texto de `entrega/INFORME.md`: si cambian las métricas hay que actualizar también el informe. Para experimentar, utilizar antes el flujo de la sección 2.

## 6. Evidencia mínima de una corrida reproducible

Guardar juntos:

- Commit de código (`git rev-parse HEAD`) y estado local (`git status --short`).
- Versión de Python, sistema operativo y versiones exactas (`python -m pip freeze`).
- CSV de entrada y su SHA-256; los tres YAML realmente utilizados y sus SHA-256.
- Comando completo y sustituciones de parámetros de CLI; fecha configurada en `fecha_corrida`.
- Salida del solver (`lp_entero`, `valor_lp`), resultados de validación y de las pruebas ejecutadas.
- Parrilla, explicaciones, resumen y duración, indicando equipo y si se generaron explicaciones.

Se pueden calcular hashes sin herramientas adicionales:

```bash
.venv/bin/python -c 'from pathlib import Path; from hashlib import sha256; paths=[Path("data/oficial/clientes.csv"), *sorted(Path("config_inicial").glob("*.yaml"))]; [print(sha256(p.read_bytes()).hexdigest(), p.as_posix()) for p in paths]'
```

El comando de hashes usa comillas de Bash; en PowerShell se puede ejecutar el mismo código desde Python. Una lista de versiones capturada hoy describe ese entorno, no reconstruye retroactivamente el entorno histórico.

La igualdad de objetivo no implica identidad de CSV: puede haber varias asignaciones óptimas. Un cambio de versión del solver o del orden de entrada puede seleccionar otra. Si se requiere comparar parrillas, hacerlo por `id_cliente` y distinguir cambios de decisión de cambios de factibilidad o valor.

## 7. Resultados históricos y verificación de esta documentación

Los archivos existentes `entrega/validacion.json` y `entrega/comparacion.json` registran, entre otros resultados, valor 10.940,0 y cero violaciones para la entrega original. Son artefactos históricos, no evidencia de haber vuelto a ejecutar toda la suite en cada cambio documental.

La verificación realizada al preparar esta ampliación, con entorno, comandos y alcance, se registra en [VERIFICACION_DOCUMENTACION.md](VERIFICACION_DOCUMENTACION.md). No se modifican el motor ni los datos para obtenerla.
