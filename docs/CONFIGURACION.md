# Guía de configuración

La configuración son tres archivos YAML. La consola los edita por ti; también puedes editarlos a mano (se validan al cargar). `config_inicial/` es la del reto y no se toca; `config/` es la viva. Cambia de carpeta con la variable `NBA_CONFIG_DIR`.

## `campanas.yaml`
| Campo | Significado |
|---|---|
| `id` | Identificador (`C-VCH`, `C-TER`, `C-OTT`) |
| `producto` | `VCH`, `TER` u `OTT` |
| `columna_score` | Columna de la base con el score de compra |
| `valor_negocio` | Valor del producto (VCH 1,0 · TER 0,8 · OTT 0,4) |
| `canales_permitidos` | Canales por los que puede ofrecerse |
| `objetivo` | Texto libre, usable en reglas con alcance `objetivo` |
| `vigencia_inicio` / `vigencia_fin` | Fuera de rango, la campaña no participa |
| `activa` | Apagar sin borrar |

## `reglas.yaml`
Cada regla dice: *"si `atributo` `operador` `valor`, entonces `excluir`"*.

```yaml
- id: R02
  nombre: Terminales solo con calificacion E, A o B
  alcance_nivel: campana        # global | campana | producto | objetivo | canal
  alcance_valores: [C-TER]      # a quién aplica (vacío si es global)
  atributo: calificacion_riesgo # cualquier columna de la base
  operador: en                  # == != < <= > >= en no_en contiene no_contiene
  valor: [C, P]
  accion: excluir
  activa: true
```

Notas:
- La regla **excluye cuando la condición es verdadera**. Para "solo E, A, B" se excluye `C|P`.
- Si el dato está vacío, la regla no se cumple (no excluye), salvo `contiene`/`no_contiene`.
- Calificación de riesgo, de mejor a peor: E, A, B, C, P.
- Los campos `productos_ofertados_mes` y `canales_contactados_mes` vienen separados por `|`.
- Usa `$producto` como valor para comparar con el producto evaluado.

## `parametros.yaml`
| Bloque | Qué controla |
|---|---|
| `canales` | Por canal: `cupo`, `max_productos`, `columna_score` |
| `priorizacion.jerarquia` | Orden de importancia de las campañas |
| `priorizacion.pesos` | Pesos del puntaje de la línea base; **deben sumar 1** |
| `priorizacion.umbral_score_producto` | R08: score mínimo de producto (0,35) |
| `priorizacion.desempate` | Orden de criterios para empates |
| `priorizacion.alpha` | 0 = valor puro; 1 = valor ponderado por jerarquía |
| `priorizacion.peso_modelo` / `peso_valor` | Exponentes del score y del valor en la utilidad |
| `politica_contacto` | Tope de contactos por semana; `canales_por_cliente` debe ser 1 |
| `asignacion.algoritmo` | `optimo` o `codicioso` |
| `asignacion.criterio_canal` | `score_canal` u `orden_preferencia` |
| `asignacion.umbral_score_canal` | R11: score mínimo de canal (0,25) |

## Recetas
- **Subir el cupo de WhatsApp:** `canales[whatsapp].cupo`.
- **Lanzar una campaña nueva:** añadir un bloque en `campanas.yaml` con su `columna_score` (debe existir en la base).
- **No ofrecer Terminales a calificación C:** regla con alcance `campana` = `C-TER`, `calificacion_riesgo` `==` `C`.
- **Pausar un producto en un canal:** quitar el canal de `canales_permitidos`.
- **Favorecer Hogar sobre el resto:** subir `alpha`; mide el costo en valor con la vista previa.

## Qué pasa si la configuración es inválida
El motor y la consola la rechazan con el campo que falla (por ejemplo pesos que no suman 1). La consola ofrece restaurar `config_inicial/`.
