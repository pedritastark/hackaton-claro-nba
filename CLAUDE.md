# Orquestador NBA configurable (Hackatón Claro)

Motor que decide, para 100.000 clientes, qué productos (VCH, TER, OTT) ofrecer y por qué canal (asesor, whatsapp, correo, sms). Negocio cambia reglas desde una consola, sin tocar código.

## Regla de oro
Ningún número, letra, umbral, cupo ni regla de negocio vive en el código: todo en `config/`. Primero 0 violaciones, después maximizar valor.

## Datos del reto (kit)
`extraido/Hackatón Orquestador NBA configurable/`: `config_*.csv` (campañas, reglas, parámetros = config inicial), `casos_ejemplo_*.csv` (5 casos de prueba), 2 PDFs del reto. Datos OFICIALES en `data/oficial/clientes.csv` (la línea base debe dar ≈10.241,5 / 55.393 clientes) y PDF oficial en `docs/oficial/`; resumen en `docs/diccionario_datos.md`. `data/clientes.csv` es la base sintética anterior (ya no se usa). Configuración inicial del reto: `config_inicial/` (las pruebas la usan; `config/` es la viva de la consola).

## Comandos (Python 3.9, venv en `.venv/`)
- Instalar: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Tests: `.venv/bin/pytest -q` · un archivo: `.venv/bin/pytest -q tests/test_motor.py`
- Correr: `.venv/bin/python -m nba.run --clientes data/oficial/clientes.csv --config config_inicial --out parrilla.csv [--algoritmo codicioso|optimo] [--alpha 0.3]`
- Validar (exit 1 si hay violaciones): `.venv/bin/python -m nba.validar parrilla.csv --clientes data/oficial/clientes.csv --config config_inicial`
- Consola: `.venv/bin/streamlit run app/consola.py` (NBA_CONFIG_DIR cambia la carpeta de config; tests en `tests/test_consola.py`)
- Explicaciones: `... nba.run --explicaciones e.jsonl.gz --resumen r.json`
- Chequeo independiente del PDF (solo config inicial): `.venv/bin/python scripts/chequeo_pdf.py parrilla.csv data/oficial/clientes.csv`
- Regenerar config desde el kit: `.venv/bin/python -m nba.importar_kit extraido/*/ config`
- Python 3.9: no usar `X | Y` en tipos (pydantic); usar `Optional/Union`.

## Definición de "terminado"
Salida real de terminal pegada: tests en verde + validador con 0 violaciones + valor esperado (a superar: **10.241,5** de la línea base). No decir "pasa" sin evidencia.

## Trampas
- Calificación riesgo, de mejor a peor: E, A, B, C, P. `config_reglas.csv` R02 excluye `C|P` (op `en`); el texto del reto dice "solo E, A, B".
- R08 (score producto ≥ 0,35) y R11 (score canal ≥ 0,25) viven en `config_parametros.csv`, no en `config_reglas.csv`.
- `productos_ofertados_mes` y `canales_contactados_mes` vienen separados por `|`; vacíos = NaN.
- Un contacto con 2 productos consume 1 solo cupo. Asesor: 1 producto.
- Valor = Σ score_producto × score_canal × valor_negocio.

## Flujo
Cambios no triviales: escribir `PLAN.md`, esperar aprobación, ejecutar en pasos pequeños. `/clear` al ~60% de contexto.
Skills en `.claude/skills/`: config-reglas, validador-metrica, asignacion-cupos, consola-cambios.
