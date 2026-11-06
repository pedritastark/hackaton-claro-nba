# PLAN — Orquestador NBA configurable

Registro del plan original y las decisiones implementadas. El informe y los artefactos de `entrega/` ya existen; sus resultados históricos incluyen 88 pruebas reportadas. La evidencia de las comprobaciones de la ampliación documental está en `docs/VERIFICACION_DOCUMENTACION.md`; no se presenta esa cifra histórica como una ejecución nueva.

## Calendario original (referencia histórica)
- **Día 1 (hecho en gran parte):** config, reglas, validador, línea base, óptimo exacto.
- **Día 2 mañana:** perilla α + curva valor/jerarquía (paso 5); consola mínima funcional (paso 6: editar config, vista previa con diff, pantalla de cliente).
- **Día 2 tarde:** pruebas por tipo de cambio (paso 7), corrida final, parrilla de entrega, demo. Recorte si falta tiempo: precios sombra y escenarios en la consola.

## Objetivo y criterios de éxito
1. 0 violaciones de R01–R16 (validador independiente).
2. Valor esperado mayor que la línea base codiciosa (referencia oficial 10.241,5; con datos sintéticos se compara contra nuestra propia línea base).
3. Los 7 tipos de cambio de negocio se resuelven por configuración, sin tocar código.
4. Jerarquía visible y ajustable; cada decisión con razón.

## Entorno y datos de la implementación
- Python 3 (desarrollo original en 3.9) + pandas/numpy/scipy + Pydantic v2 + PyYAML + Streamlit. Sin DB ni servicios. Versiones y reproducción: `docs/REPRODUCIBILIDAD.md`.
- Datos usados por defecto: `data/oficial/clientes.csv`; son los datos sintéticos oficiales del reto. `data/clientes.csv` corresponde a una generación anterior y no es la referencia de entrega. Diccionario oficial resumido en `docs/diccionario_datos.md`.

## Arquitectura
`config/ + datos → Elegibilidad → Candidatos → Asignación → Parrilla(+razón)`; `Validador` aparte, sin importar el motor.

Estructura: `nba/{config,reglas,elegibilidad,candidatos,asignacion,parrilla,validar,run}.py`, `app/` (Streamlit), `config/*.yaml`, `tests/`.

## Decisiones clave
| Tema | Decisión | Alternativa descartada |
|---|---|---|
| Config | YAML validado con Pydantic, versionado | constantes en código / CSV sueltos |
| Reglas | tabla atributo/operador/valor/alcance, intérprete vectorizado, frase de negocio autogenerada | `if` por campaña |
| Prioridad | Utilidad por oferta con mezcla de valor y nivel de jerarquía, exponentes y término epsilon; fórmula exacta en `docs/FORMULACION_MATEMATICA.md` | solo pesos fijos |
| Asignación | LP bipartito capacitado (HiGHS); respaldo por redondeo sin garantía de óptimo; no hay respaldo lagrangiano implementado | codicioso por cliente como única opción |
| Explicación | códigos de razón + frase desde matrices de elegibilidad | texto libre sin trazabilidad |

La integralidad de los vértices del modelo reducido se justifica por su matriz bipartita y los cupos enteros; la reducción a paquetes requiere utilidad aditiva no negativa y ausencia de otros recursos globales por producto. El código comprueba integralidad numérica y conserva límites de asignación al extraer o redondear. Ver demostración y alcance en `docs/FORMULACION_MATEMATICA.md`.

## Pasos del plan original
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
- Una base nueva debe respetar el diccionario y sus dominios; no asumir que la validación de configuración valida también todo el CSV.
- Con α>0 el valor optimizado ≠ valor medido: reportar siempre ambos.
- Reglas con `$producto` requieren evaluación por producto.
- No confundir el identificador de una regla del YAML con su número en el PDF. Trazabilidad en `docs/RESTRICCIONES.md`.
- La salida actual solo escribe dos campañas; topes mayores requieren adaptar el formato.

## Documentación y próximos pasos actuales

- Formulación, equivalencia a paquetes, integralidad, fórmula exacta y límites: `docs/FORMULACION_MATEMATICA.md`.
- R01–R16, validadores y cobertura: `docs/RESTRICCIONES.md`.
- Caso pequeño ejecutable con enumeración exhaustiva: `docs/EJEMPLO_ASIGNACION.md`.
- Instalación y operación: `README.md`, `docs/CONFIGURACION.md`, `docs/GUIA_CONSOLA.md`, `docs/REPRODUCIBILIDAD.md`.
- Trabajo de producto y límites pendientes: `docs/PENDIENTES.md`. Este plan no implica que esas mejoras estén implementadas.

## Fuera de alcance
Entrenar modelos, RL, microservicios, base de datos.

## Flujo de trabajo
Un paso por vez, commit modular, `/clear` al ~60% de contexto, evidencia de terminal antes de dar un paso por terminado.

## Migración de la consola a React (Streamlit sigue vivo)
Decisión: Vite + React + TypeScript + Tailwind + Recharts sobre una API FastAPI. `nba/` no cambia.

| Paso | Contenido | Estado |
|---|---|---|
| 1 | `api/`: servicio sin interfaz + rutas (estado, config, revisar, impacto, aplicar, tablero, cliente, base, versiones, parrilla) y `tests/test_api.py` (10 pruebas) | hecho |
| 2 | `web/`: estructura, navegación lateral, estado global, pantalla de configuración inválida | hecho |
| 3 | Tablero, Cliente, Base de datos, Versiones | hecho |
| 4 | Cambiar configuración: 6 pestañas, controles directos, asistente de reglas, vista previa, aplicar | hecho |
| 5 | Recorridos en navegador real con Playwright (`web/e2e`) | hecho: 8 pasos de lectura/edición + 5 de aplicar/versiones/restaurar, sin errores |
| 6 | Retirar Streamlit | pendiente: solo cuando el equipo valide la paridad |

Decisiones de diseño: el borrador de configuración vive en el navegador como JSON del esquema de `nba/config.py` (se eliminó la conversión tabla↔config de Streamlit); la API valida con el mismo Pydantic y reutiliza `comparar`, `versiones` y `Explicador`; los controles directos (tope de llamadas, calificaciones por campaña) son endpoints para no duplicar la lógica en JavaScript; el orden de prioridad se cambia con flechas y no reordena la lista de campañas (para no alterar desempates).

Ronda de presentación de la información: portada de Resumen, Tablero con medidores/embudo centrado/mapa de calor, ficha de decisión por cliente (con sus datos), simulador con estimación instantánea por precios sombra y barras divergentes, **Escenarios** guardados con comparación lado a lado, **curva de sensibilidad** de cupos y calidad de datos. Cálculos largos (comparar escenarios, curva) corren como trabajos en segundo plano con avance parcial (`/api/trabajos/{id}`).

Diferencias conocidas frente a Streamlit: solo tema claro; el cálculo del tablero (3 corridas del motor la primera vez) bloquea la pantalla con un indicador en lugar de ejecutarse en segundo plano; no hay usuarios ni roles (igual que antes).

### Rediseño visual de la consola React
Estilo sobrio, minimalista, blanco y negro: el negro es la interfaz (barra lateral, botones primarios, franja de estado, barra flotante de cambios sin aplicar) y el color queda reservado para los datos. Tipografía Inter incluida en el paquete (sin depender de internet). Paleta de gráficos validada con el validador de la guía de visualización (claro): azul `#2d6fcf` para series únicas y, para canales, `#2d6fcf #d1702a #1d9b73 #8161be #c19a1b #c5517a`; el texto de leyendas y ejes va siempre en tinta neutra, nunca en el color de la serie. Mejoras de uso: esqueletos de carga en el tablero y barra flotante en «Cambiar configuración» con acceso directo a la vista previa. Solo tema claro.
