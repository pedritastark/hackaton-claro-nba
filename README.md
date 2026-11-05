# Orquestador NBA configurable

Solución al reto **Claro Colombia × Universidad del Rosario: "Orquestador NBA configurable"**.

Para cada uno de 100.000 clientes decide **qué producto ofrecer** (Hogar, Terminales u OTT) y **por qué canal** (asesor, WhatsApp, correo o SMS), de forma que el valor esperado sea máximo y **no se viole ninguna de las 16 restricciones** (R01–R16). Todas las reglas y números viven en archivos de configuración que el negocio cambia desde una consola web, sin tocar código.

| Resultado (datos oficiales) | Valor |
|---|---|
| Valor esperado, línea base del reto | 10.241,5 |
| Valor esperado, este motor | **10.940,0** (+6,8 %) |
| Violaciones de restricciones | **0** (validador + chequeo independiente) |
| Clientes con acción / productos ofertados | 60.422 / 76.841 |
| Indicador de jerarquía | 99,84 % |
| Pruebas automáticas | 88 en verde |

## Inicio rápido

Requiere Python 3.9.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. Generar la parrilla
.venv/bin/python -m nba.run --clientes data/oficial/clientes.csv --config config_inicial \
    --out parrilla.csv --explicaciones explicaciones.jsonl.gz --resumen resumen.json

# 2. Validar (sale con código 1 si hay violaciones)
.venv/bin/python -m nba.validar parrilla.csv --clientes data/oficial/clientes.csv --config config_inicial

# 3. Chequeo independiente escrito desde el PDF (solo con la config inicial)
.venv/bin/python scripts/chequeo_pdf.py parrilla.csv data/oficial/clientes.csv

# 4. Consola web
.venv/bin/streamlit run app/consola.py

# 5. Pruebas (~7 min; las de consola son las lentas)
.venv/bin/pytest -q
```

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

## Configuración

Tres archivos YAML en `config/` (la versión viva que edita la consola) y `config_inicial/` (la del reto, que usan las pruebas):

- `campanas.yaml`: campañas, producto, columna de score, valor de negocio, canales permitidos, vigencia.
- `reglas.yaml`: reglas de exclusión del tipo *"si esta columna cumple esto, excluir"*, con alcance global, por campaña, producto, objetivo o canal.
- `parametros.yaml`: canales y cupos, topes de contacto, umbrales, jerarquía, pesos y algoritmo.

Una regla nueva puede usar **cualquier columna** de la base de clientes. Guía de edición y ejemplos: [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md).

## Consola

Pensada para un analista de negocio. Secciones: **Tablero** (estado de la parrilla, cupos, embudo, reglas que más excluyen), **Cambiar configuración** (con vista previa del impacto y validación antes de aplicar), **Cliente** (por qué se decidió lo que se decidió), **Base de datos** y **Versiones** (historial y restauración). Guía: [`docs/GUIA_CONSOLA.md`](docs/GUIA_CONSOLA.md).

## Explicabilidad

Cada decisión genera un registro estructurado con productos y canales considerados, reglas que excluyeron y valor esperado. De ahí salen la columna `razon` de la parrilla, la versión para el asesor, `explicaciones.jsonl.gz` y el `resumen.json` con categorías.

## Cómo sabemos que está bien

1. **Validador** (`nba/validar.py`): revisa cliente por cliente las 16 restricciones.
2. **Chequeo independiente** (`scripts/chequeo_pdf.py`): escrito desde el PDF, con los números fijos y sin importar nada de `nba/`.
3. **Réplica de la línea base**: con la misma lógica sencilla se reproduce el valor oficial (10.241,6 vs 10.241,5).
4. **Pruebas de mutación**: se rompe el código a propósito para confirmar que las pruebas fallan.
5. **88 pruebas**, incluida una por cada tipo de cambio de configuración.

## Estructura del repositorio

```
nba/             motor (config, reglas, elegibilidad, candidatos, asignación, parrilla, explicar, validar, run, comparar, versiones)
app/             consola Streamlit (consola.py) y componentes del tablero (tablero.py)
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
| [`docs/CONFIGURACION.md`](docs/CONFIGURACION.md) | Cada campo de los YAML, operadores de reglas, recetas de cambios |
| [`docs/GUIA_CONSOLA.md`](docs/GUIA_CONSOLA.md) | Recorrido de la consola para el usuario de negocio |
| [`docs/diccionario_datos.md`](docs/diccionario_datos.md) | Columnas de la base de clientes |
| [`entrega/INFORME.md`](entrega/INFORME.md) | Informe de resultados |
| [`PLAN.md`](PLAN.md) | Plan y decisiones tomadas |
| [`docs/PENDIENTES.md`](docs/PENDIENTES.md) | Límites conocidos y siguientes pasos |
| [`CLAUDE.md`](CLAUDE.md) | Guía para trabajar el proyecto con Claude Code |
