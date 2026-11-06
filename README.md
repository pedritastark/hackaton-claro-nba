# Orquestador NBA configurable

Solución al reto **Claro Colombia × Universidad del Rosario: "Orquestador NBA configurable"**.

Para cada uno de 100.000 clientes decide **qué productos ofrecer** (Hogar, Terminales u OTT) y **por qué canal** (asesor, WhatsApp, correo o SMS), respetando las 16 restricciones (R01–R16). Con la configuración inicial, el optimizador maximiza el valor esperado; al cambiar los pesos puede maximizar otra utilidad de negocio. Las reglas, umbrales y cupos se editan desde la configuración y la consola. La [formulación y sus supuestos](docs/FORMULACION_MATEMATICA.md) precisan el alcance de esa garantía.

Resultados registrados en la entrega original; no son una nueva ejecución automática al leer este README:

| Resultado (datos oficiales) | Valor |
|---|---|
| Valor esperado, línea base del reto | 10.241,5 |
| Valor esperado, este motor | **10.940,0** (+6,8 %) |
| Violaciones de restricciones | **0** (validador + chequeo independiente) |
| Clientes con acción / productos ofertados | 60.422 / 76.841 |
| Indicador de jerarquía | 99,84 % |
| Pruebas automáticas | 88 en verde |

## Inicio rápido

Desarrollado originalmente con Python 3.9 y Pydantic v2. Las dependencias no están bloqueadas a versiones exactas; consultar [instalación, reproducción y entorno verificado](docs/REPRODUCIBILIDAD.md).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. Generar la parrilla
.venv/bin/python -m nba.run --clientes data/oficial/clientes.csv --config config_inicial \
    --out parrilla.csv --explicaciones explicaciones.jsonl.gz --resumen resumen.json

# 2. Validar (sale con código 1 si hay violaciones)
.venv/bin/python -m nba.validar parrilla.csv --clientes data/oficial/clientes.csv --config config_inicial

# 3. Chequeo independiente escrito desde el PDF (solo con la config inicial)
.venv/bin/python scripts/chequeo_pdf.py parrilla.csv data/oficial/clientes.csv

# 4. Consola web (React + API). Requiere Node 20 o superior
(cd web && npm install && npm run build)
.venv/bin/uvicorn api.main:app --port 8000        # abre http://localhost:8000

# 4b. Consola anterior en Streamlit (sigue disponible)
.venv/bin/streamlit run app/consola.py

# 5. Pruebas (~7 min; las de consola Streamlit son las lentas)
.venv/bin/pytest -q
```

Para desarrollar la interfaz con recarga en caliente, deja la API en el puerto 8000 y corre `cd web && npm run dev` (puerto 5173, reenvía `/api` a la API).

Opciones útiles de `nba.run`: `--algoritmo codicioso|optimo`, `--alpha 0.3` (peso de la jerarquía).
Si cambias código de `nba/`, **reinicia Streamlit**: no recarga esos módulos.

## Cómo funciona

```
clientes.csv + config/*.yaml
        │
        ▼
 1. Elegibilidad   ¿qué productos y canales se pueden usar con este cliente?  (nba/elegibilidad.py)
        │            cada "no" guarda la regla que lo causó
        ▼
 2. Candidatos     mejor paquete (≤ k productos) por cliente × canal          (nba/candidatos.py)
        │            valor = score_producto × score_canal × valor_negocio
        ▼
 3. Asignación     reparte los cupos entre todos los clientes a la vez        (nba/asignacion.py)
        │            óptimo: programación lineal (HiGHS) · alternativa: codicioso
        ▼
 4. Parrilla       id_cliente, estado, canal, campana_1, campana_2, razon     (nba/parrilla.py)
        │
        ▼
 Validador independiente (nba/validar.py) + explicaciones (nba/explicar.py)
```

Detalle completo en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

El modelo usa una variable por par cliente–canal, después de construir el mejor paquete local. La matriz bipartita permite un óptimo entero de la relajación lineal. La [demostración y las condiciones numéricas](docs/FORMULACION_MATEMATICA.md) explican por qué esto conserva el óptimo y cuándo deja de aplicarse. El [ejemplo con cuatro clientes](docs/EJEMPLO_ASIGNACION.md) muestra una mejora frente al codicioso, verificada también por enumeración.

## Configuración

Tres archivos YAML en `config/` (la versión viva que edita la consola) y `config_inicial/` (la del reto, que usan las pruebas):

- `campanas.yaml`: campañas, producto, columna de score, valor de negocio, canales permitidos, vigencia.
- `reglas.yaml`: reglas de exclusión del tipo *"si esta columna cumple esto, excluir"*, con alcance global, por campaña, producto, objetivo o canal.
- `parametros.yaml`: canales y cupos, topes de contacto, umbrales, jerarquía, pesos y algoritmo.

Una regla nueva puede usar **cualquier columna** de la base de clientes. Guía de edición y ejemplos: [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md).

## Consola

La consola React requiere iniciar sesión. En una instalación nueva, crea el primer administrador con la clave de `var/acceso/clave-inicial.txt`. Después puedes crear usuarios y asignar los roles Administrador, Editor, Analista de pruebas o Consulta desde «Usuarios y permisos». Instalación, permisos y operación: [`docs/ACCESO_USUARIOS.md`](docs/ACCESO_USUARIOS.md).

Pensada para un analista de negocio. Hay dos versiones con los mismos resultados del motor: la principal, en **React** (`web/`) sobre una **API FastAPI** (`api/`), y la original en Streamlit (`app/`), que no incluye Resumen, Escenarios ni la curva de sensibilidad. La lógica de negocio es la del mismo motor `nba/`; la API solo valida, calcula y guarda, y el borrador de configuración viaja como JSON desde el navegador. Secciones: **Resumen** (portada), **Tablero** (estado de la parrilla, cupos, embudo, reglas que más excluyen), **Cambiar configuración** (con estimación instantánea, vista previa del impacto y validación antes de aplicar), **Laboratorios** (pruebas de cupos, reglas y prioridades, alternativas guardadas y comparación de resultados), **Cliente** (por qué se decidió lo que se decidió), **Base de datos** y **Versiones** (historial y restauración). Guía: [`docs/GUIA_CONSOLA.md`](docs/GUIA_CONSOLA.md).

## Explicabilidad

Cada decisión genera un registro estructurado con productos y canales considerados, reglas que excluyeron y valor esperado. De ahí salen la columna `razon` de la parrilla, la versión para el asesor, `explicaciones.jsonl.gz` y el `resumen.json` con categorías.

## Cómo sabemos que está bien

1. **Validador** (`nba/validar.py`): revisa cliente por cliente las 16 restricciones.
2. **Chequeo independiente** (`scripts/chequeo_pdf.py`): escrito desde el PDF, con los números fijos y sin importar nada de `nba/`.
3. **Réplica de la línea base**: con la misma lógica sencilla se reproduce el valor oficial (10.241,6 vs 10.241,5).
4. **Pruebas de mutación**: se rompe el código a propósito para confirmar que las pruebas fallan.
5. **Pruebas automatizadas** del motor, de cada tipo de cambio, de la API y del acceso por roles. Evidencia de laboratorios: [`docs/VERIFICACION_LABORATORIOS.md`](docs/VERIFICACION_LABORATORIOS.md); verificación de usuarios: [`docs/ACCESO_USUARIOS.md`](docs/ACCESO_USUARIOS.md#verificación).
6. **Recorridos en navegador real** de la consola React (`cd web && npm run e2e`, con la API activa): tablero, cliente, base de datos, versiones, edición, impacto y borrador inválido; `npm run e2e:aplicar` prueba aplicar, versiones y restaurar y debe correrse contra una API con una copia de la configuración (`NBA_CONFIG_DIR`), porque escribe una versión.

Para verificar el **Centro de laboratorios**, ejecuta `cd web && npm run build && npm run e2e:laboratorios`. Este recorrido inicia su propia API con una configuración temporal: crea, ejecuta y duplica pruebas, guarda cambios de reglas y prioridades, recupera el último resultado tras recargar, calcula sensibilidad y comprueba que no se alteraron la configuración vigente ni las versiones. Requiere Chromium de Playwright; `NBA_CHROMIUM` permite indicar otro ejecutable instalado y `NBA_E2E_OUT` guardar las capturas de escritorio y móvil.

La cifra de 88 pruebas y los resultados de la tabla proceden del informe histórico. La [verificación de esta ampliación documental](docs/VERIFICACION_DOCUMENTACION.md) identifica qué se volvió a ejecutar. La [matriz R01–R16](docs/RESTRICCIONES.md) distingue numeración del PDF, reglas YAML, validadores y cobertura de pruebas.

## Estructura del repositorio

```
nba/             motor (config, reglas, elegibilidad, candidatos, asignación, parrilla, explicar, validar, run, comparar, versiones)
api/             API FastAPI de la consola (main.py: rutas; servicio.py: lógica sin interfaz)
web/             consola React (Vite + TypeScript + Tailwind + Recharts); web/e2e: recorridos con Playwright
app/             consola anterior en Streamlit (consola.py) y componentes del tablero (tablero.py)
config/          configuración viva (la edita la consola; versiones en config/versiones/)
config_inicial/  configuración oficial del reto
data/oficial/    base oficial de 100.000 clientes
docs/            documentación y diccionario de datos oficial
entrega/         parrilla final, explicaciones, resumen, validación e INFORME.md
scripts/         chequeo independiente del PDF, generación de la entrega
tests/           pruebas
extraido/        kit original del reto (PDFs, casos de ejemplo, config en CSV)
```

## Documentación

| Documento | Para qué |
|---|---|
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Pipeline, modelo de datos, algoritmo de asignación, decisiones de diseño |
| [`docs/FORMULACION_MATEMATICA.md`](docs/FORMULACION_MATEMATICA.md) | Variables, ecuaciones, utilidad exacta, demostración del óptimo y límites |
| [`docs/RESTRICCIONES.md`](docs/RESTRICCIONES.md) | Correspondencia R01–R16 con YAML, implementación, validadores y pruebas |
| [`docs/EJEMPLO_ASIGNACION.md`](docs/EJEMPLO_ASIGNACION.md) | Caso pequeño resuelto y ejecutable; comparación con el codicioso |
| [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md) | Cada campo de los YAML, operadores de reglas, recetas de cambios |
| [`docs/GUIA_CONSOLA.md`](docs/GUIA_CONSOLA.md) | Recorrido de la consola para el usuario de negocio |
| [`docs/SIMULACION_ESTRATEGIAS.md`](docs/SIMULACION_ESTRATEGIAS.md) | Ganancias y sacrificios de cada estrategia, impacto por campaña y explicación antes/después por cliente |
| [`docs/REPRODUCIBILIDAD.md`](docs/REPRODUCIBILIDAD.md) | Instalación, comandos, versiones, validación y reproducción de entregables |
| [`docs/VERIFICACION_DOCUMENTACION.md`](docs/VERIFICACION_DOCUMENTACION.md) | Evidencia y alcance de las comprobaciones de esta documentación |
| [`docs/diccionario_datos.md`](docs/diccionario_datos.md) | Columnas de la base de clientes |
| [`entrega/INFORME.md`](entrega/INFORME.md) | Informe de resultados |
| [`PLAN.md`](PLAN.md) | Plan y decisiones tomadas |
| [`docs/PENDIENTES.md`](docs/PENDIENTES.md) | Límites conocidos y siguientes pasos |
| [`CLAUDE.md`](CLAUDE.md) | Guía para trabajar el proyecto con Claude Code |

## Documentos originales del reto

Copias de los tres PDFs proporcionados, conservadas en [`docs/planteamiento_del_reto/`](docs/planteamiento_del_reto/):

- [Diccionario de datos y formatos](docs/planteamiento_del_reto/diccionario_datos_y_formatos.pdf).
- [El reto estudiantes](docs/planteamiento_del_reto/reto_estudiantes.pdf).
- [Presentación del reto Orquestador NBA](docs/planteamiento_del_reto/reto_hackaton_orquestador_nba.pdf).

Estos documentos definen el problema. La formulación matemática y las decisiones de implementación descritas en las guías son la solución del equipo.
