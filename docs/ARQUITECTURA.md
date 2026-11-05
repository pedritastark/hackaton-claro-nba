# Arquitectura

## Principios

1. **Config como datos.** Las reglas, letras de riesgo, umbrales y cupos de negocio están en `config/*.yaml`, validado con Pydantic v2 (`nba/config.py`). El motor también contiene constantes de implementación, como tolerancias, `EPS_DESEMPATE` y bonos de prioridad; su efecto está documentado en la formulación.
2. **Primero 0 violaciones, después valor.** Las reglas son filtros duros; el valor se maximiza solo entre lo permitido.
3. **Todo decide con una sola fuente de verdad.** Un único registro estructurado por cliente alimenta la razón, la explicación para el asesor, el JSONL y el resumen.
4. **Verificación independiente.** El validador y el chequeo del PDF no comparten lógica con el motor.

## Pipeline

### 1. Elegibilidad (`nba/elegibilidad.py`, `nba/reglas.py`)
Un intérprete de reglas vectorizado evalúa cada regla activa sobre todo el DataFrame.
- Operadores: `==  !=  <  <=  >  >=  en  no_en  contiene  no_contiene`; el valor puede referirse al producto con `$producto`.
- **Una regla excluye cuando su condición es verdadera.** Un valor ausente (NaN) nunca la cumple, salvo en `contiene`/`no_contiene`.
- Alcance: `global`, `campana`, `producto`, `objetivo` o `canal` (`Config.regla_aplica`).
- Salida: `prod_ok`, `prod_why`, `canal_ok`, `canal_why`, `semana_ok`. Siempre se guarda **qué regla** dijo no.
- R08 (score de producto ≥ 0,35) y R11 (score de canal ≥ 0,25) son umbrales de `parametros.yaml`, no reglas del CSV.

### 2. Candidatos (`nba/candidatos.py`)
Para cada cliente y canal habilitado construye el mejor paquete de hasta `max_productos` productos (1 en asesor, 2 en digital). El orden y los empates se resuelven con `np.lexsort` y la lista `desempate`.

Utilidad de una oferta dentro del paquete (la utilidad del paquete es la suma de sus ofertas):

```
score_producto^peso_modelo × score_canal × (valor_ef + 1e-3·valor)^peso_valor
valor_ef = (1 − alpha)·valor_negocio + alpha·nivel_jerarquia
```

Con los valores por defecto (`alpha=0`, exponentes 1) la utilidad es **1,001 veces** la métrica del reto: Σ score_producto × score_canal × valor_negocio. El factor común conserva el óptimo, pero el objetivo LP y los precios sombra quedan escalados. Con otros parámetros se optimiza una utilidad distinta; el valor real se sigue reportando por separado.
Un contacto con 2 productos consume **un solo cupo**.

### 3. Asignación (`nba/asignacion.py`)
Cada cliente recibe como máximo un canal; cada canal tiene un cupo.

- **`codicioso`** (réplica de la línea base): ordena por puntaje ponderado (0,6 score, 0,2 valor, 0,2 jerarquía) y llena cupos en ese orden.
- **`optimo`** (por defecto): asignación bipartita capacitada resuelta con `scipy.optimize.linprog` (HiGHS). La estructura de la matriz y los cupos enteros garantizan que existe un óptimo entero del LP. El código comprueba integralidad; si recibe fracciones, usa un redondeo que conserva límites de asignación, pero pierde la garantía de óptimo. Los aproximadamente 12 s con 100.000 clientes son una medición histórica.
- Los **precios sombra** de los cupos (asesor ≈ 0,0925, WhatsApp ≈ 0,0652 en los archivos históricos) son sensibilidades locales de la utilidad optimizada. Con los parámetros iniciales, dividirlos por 1,001 los expresa en valor real. No deben extrapolarse linealmente a ampliaciones grandes.
- `criterio_canal: orden_preferencia` añade un bono de rango por contacto; cambia el objetivo y no garantiza prioridad lexicográfica estricta. En ese modo no se reportan precios sombra.

La [formulación matemática](FORMULACION_MATEMATICA.md) desarrolla las ecuaciones, la equivalencia de los paquetes y la integralidad. La [tabla de restricciones](RESTRICCIONES.md) conecta cada regla del PDF con los filtros o restricciones del LP. El [ejemplo resuelto](EJEMPLO_ASIGNACION.md) permite seguir el flujo completo con cuatro clientes.

### 4. Parrilla y explicación (`nba/parrilla.py`, `nba/explicar.py`)
`Explicador.registro` construye el registro por cliente; de él salen `frase` (columna `razon`), `frase_asesor`, `explicaciones.jsonl(.gz)` y `resumen.json` con `categorias()`.

### 5. Validación (`nba/validar.py`)
Validador escalar, cliente por cliente, sin reutilizar el motor. Comprueba R01–R16, formato de la parrilla y cupos. `scripts/chequeo_pdf.py` repite el chequeo con los números del PDF escritos a mano.

## Módulos de apoyo
- `nba/comparar.py`: compara dos configuraciones (matriz de productos, métricas) para la vista previa de la consola.
- `nba/versiones.py`: guarda y restaura versiones de configuración en `config/versiones/<fecha>_<etiqueta>/`.
- `nba/importar_kit.py`: convierte los CSV del kit a YAML.

## Consola (`app/`)
Consola Streamlit. Flujo de cambio: editar borrador → vista previa del impacto → el validador debe dar 0 violaciones → aplicar (se guarda una versión). Si la configuración viva queda inválida, una pantalla muestra el campo que falla y ofrece restaurar la inicial (con respaldo). La versión exacta de Streamlit debe registrarse en cada entorno de reproducción.

## Decisiones y por qué
| Decisión | Motivo |
|---|---|
| Óptimo por LP en vez de solo codicioso | +6,8 % de valor, entero y verificable; el codicioso queda como línea base |
| Config en YAML + Pydantic | Editable por consola, validada antes de usarse, versionable |
| Reglas genéricas sobre columnas | Una regla nueva no requiere programar |
| Un solo canal por cliente | Lo exige el reto; `canales_por_cliente ≠ 1` se rechaza |
| `alpha=0` por defecto | La métrica del reto es el valor puro; `alpha` permite favorecer la jerarquía a conciencia |
| Tie-break `EPS_DESEMPATE` | Con `alpha=1` el LP descartaba el producto de menor jerarquía |

## Límites conocidos
Ver [`PENDIENTES.md`](PENDIENTES.md).
