# PLAN — Orquestador NBA configurable

Estado: pasos 1–4 HECHOS + explicabilidad + consola (tablero, cambios con vista previa, cliente, versiones; 88 tests en verde). Pendiente: pruebas por tipo de cambio (paso 7), pulido y entrega. Plazo total: 2 días.

## Calendario (2 días)
- **Día 1 (hecho en gran parte):** config, reglas, validador, línea base, óptimo exacto.
- **Día 2 mañana:** perilla α + curva valor/jerarquía (paso 5); consola mínima funcional (paso 6: editar config, vista previa con diff, pantalla de cliente).
- **Día 2 tarde:** pruebas por tipo de cambio (paso 7), corrida final, parrilla de entrega, demo. Recorte si falta tiempo: precios sombra y escenarios en la consola.

## Objetivo y criterios de éxito
1. 0 violaciones de R01–R16 (validador independiente).
2. Valor esperado mayor que la línea base codiciosa (referencia oficial 10.241,5; con datos sintéticos se compara contra nuestra propia línea base).
3. Los 7 tipos de cambio de negocio se resuelven por configuración, sin tocar código.
4. Jerarquía visible y ajustable; cada decisión con razón.

## Supuestos (confirmar)
- Python 3 + pandas/numpy/scipy + Pydantic + PyYAML + Streamlit. Sin DB ni servicios.
- Datos: `data/clientes.csv` sintético; diccionario inferido (`docs/diccionario_datos.md`).
- Plazo y prioridad de evaluación: sin definir.

## Arquitectura
`config/ + datos → Elegibilidad → Candidatos → Asignación → Parrilla(+razón)`; `Validador` aparte, sin importar el motor.

Estructura: `nba/{config,reglas,elegibilidad,candidatos,asignacion,parrilla,validar,run}.py`, `app/` (Streamlit), `config/*.yaml`, `tests/`.

## Decisiones clave
| Tema | Decisión | Alternativa descartada |
|---|---|---|
| Config | YAML validado con Pydantic, versionado | constantes en código / CSV sueltos |
| Reglas | tabla atributo/operador/valor/alcance, intérprete vectorizado, frase de negocio autogenerada | `if` por campaña |
| Prioridad | `U = (1−α)·valor_esperado + α·bono_jerarquía`; modo ponderado de línea base disponible | solo pesos fijos |
| Asignación | LP de transporte exacto (HiGHS); respaldo lagrangiano con precio por canal | codicioso por cliente |
| Explicación | códigos de razón + frase desde matrices de elegibilidad | texto libre sin trazabilidad |

Hipótesis a verificar en el paso 4: la relajación LP da solución entera (problema de transporte). Si no, redondeo + reparación.

## Pasos (cada uno cierra con evidencia en terminal)
1. **Config + reglas:** cargar/validar los 3 CSV del kit → YAML; intérprete de operadores. *Verif:* tests de cada operador y de `$producto`.
2. **Validador + métricas:** R01–R16, valor, % jerarquía. *Verif:* acepta `casos_ejemplo_parrilla_esperada.csv` con 0 violaciones; detecta violaciones inyectadas a propósito.
3. **Elegibilidad + línea base codiciosa:** *Verif:* reproduce los 5 casos esperados; 0 violaciones en 100k; registrar valor base sintético.
4. **Optimizador exacto:** candidatos + LP + precios sombra. *Verif:* 0 violaciones, valor > línea base, tiempo < 1 min.
5. **Perilla α + curva valor/jerarquía.**
6. **Consola:** edición de los 7 tipos de cambio, vista previa con diff, pantalla de cliente, escenarios.
7. **Pruebas de cambio:** una por tipo de cambio; determinismo; informe final.

## Tipos de cambio y dónde se resuelven
Campañas → `campanas`; Reglas → `reglas`; Umbrales → `parametros`/reglas; Prioridad → `priorizacion` (jerarquía, pesos, α); Canales y cupos → `canales`; Política de contacto → `politica_contacto`; Datos nuevos → atributo por nombre de columna.

## Riesgos
- Datos sintéticos distintos al oficial: no asumir distribuciones.
- Con α>0 el valor optimizado ≠ valor medido: reportar siempre ambos.
- Reglas con `$producto` requieren evaluación por producto.
- Diccionario inferido: validar contra el oficial si aparece.

## Fuera de alcance
Entrenar modelos, RL, microservicios, base de datos.

## Flujo de trabajo
Un paso por vez, commit modular, `/clear` al ~60% de contexto, evidencia de terminal antes de dar un paso por terminado.
