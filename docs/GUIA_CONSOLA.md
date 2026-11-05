# Guía de la consola

Para el analista comercial. Arranque:

```bash
.venv/bin/streamlit run app/consola.py     # abre http://localhost:8501
```

Variables opcionales: `NBA_CONFIG_DIR` (carpeta de configuración, por defecto `config/`) y `NBA_CLIENTES` (CSV de clientes, por defecto `data/oficial/clientes.csv`).

## Secciones (barra lateral)

**Tablero.** ¿Cómo está la parrilla hoy?
- Franja de estado: valor esperado, clientes con acción, violaciones.
- Medidores de cupo por canal: cuánto se usa de cada uno.
- Embudo: de todos los clientes, cuántos pasan cada filtro hasta quedar con acción.
- Reglas que más excluyen: dónde se pierden clientes.
- Composición por canal y producto.
- Alertas y comparación con la versión anterior.
- «Ver un ejemplo» abre un cliente representativo.

**Cambiar configuración.** Pestañas: *Umbrales y contacto*, *Prioridad*, *Campañas*, *Reglas*, *Canales y cupos*, *Datos nuevos*.
1. Modifica el borrador.
2. Pulsa **Calcular impacto del cambio**: valor, clientes, productos por campaña y canal, diferencia con signo frente a la configuración vigente.
3. El validador debe dar 0 violaciones; si no, no se puede aplicar.
4. *Aplicar* guarda una nueva versión.

Incluye un asistente para crear reglas en lenguaje sencillo y controles directos para el tope de llamadas y las calificaciones por campaña.

**Cliente.** Busca un `id_cliente`: qué se decidió, por qué, qué se descartó y qué regla lo descartó, con la explicación en lenguaje de negocio y la versión para el asesor.

**Base de datos.** Ruta o archivo CSV activo. Al cambiarla, el tablero se recalcula; columnas nuevas quedan disponibles para reglas.

**Versiones.** Historial de configuraciones aplicadas (`config/versiones/`), con comparación y restauración.

## Si algo sale mal
- *«El borrador no es válido»*: la consola indica el campo; corrige y reintenta.
- *Configuración viva dañada*: aparece una pantalla con el campo que falla y un botón para restaurar la inicial (deja un respaldo en `respaldo/`).
- *Tras cambiar código de `nba/`*: reinicia Streamlit.

## Ejercicio: ampliar el cupo de WhatsApp

1. En **Cambiar configuración → Canales y cupos**, localiza `whatsapp` y cambia su cupo, por ejemplo de 15.000 a 15.100. El cambio está todavía en el borrador.
2. Pulsa **Calcular impacto del cambio**. Compara valor esperado, clientes con acción, productos, jerarquía y uso de canales. Revisa también los clientes que ganan o pierden acción y los que cambian de canal.
3. Comprueba que el validador indica cero violaciones. No esperes que el valor suba exactamente cien veces el precio sombra: es una estimación local y está expresada en la utilidad del optimizador.
4. Escribe una etiqueta descriptiva y pulsa **Aplicar cambio**. Se guardan los tres YAML y una versión en la carpeta seleccionada por `NBA_CONFIG_DIR`.
5. Para probar sin guardar, utiliza **Descartar borrador** en la vista previa.

Para modificar prioridades, sigue el mismo flujo en **Prioridad**. `alpha=0` favorece el valor del reto; aumentar `alpha` favorece la jerarquía, con posible costo en valor. El indicador de jerarquía se reporta aparte: no se suma a la métrica oficial. Los [parámetros por algoritmo](CONFIGURACION.md) evitan confundir los pesos del codicioso con los exponentes del optimizador.

## Restaurar una configuración anterior

En **Versiones**, pulsa **Restaurar** en la versión deseada. Esto la carga **como borrador** y lleva a **Cambiar configuración**. Calcula su impacto y pulsa **Aplicar cambio** para convertirla en la configuración vigente; restaurar el borrador por sí solo no reemplaza los YAML.

El historial contiene versiones guardadas, no reconstruye un estado anterior al primer guardado. Para recuperar exactamente un punto de partida propio, guarda antes una copia de sus tres YAML. Si la configuración viva no puede cargarse, la recuperación especial de la pantalla de error copia los archivos presentes a `NBA_CONFIG_DIR/respaldo/<fecha>_invalida/` y restaura la inicial.

## Leer una decisión y exportar

En **Cliente**, busca un identificador o un ejemplo de situación. Revisa los productos elegidos, reglas de descarte y alternativas de canal. Un canal con mayor score puede no elegirse si su cupo tiene más utilidad para otro cliente; el [ejemplo pequeño](EJEMPLO_ASIGNACION.md) muestra ese caso.

En **Tablero**, **Generar parrilla completa (con explicaciones)** prepara la descarga. Conserva también la configuración utilizada. La consola calcula decisiones sobre el historial del CSV, pero no registra contactos nuevos en ese archivo ni despacha ofertas: ejecutar de nuevo con la misma base no actualiza automáticamente los contadores semanales o mensuales.

## Diagnóstico práctico

| Síntoma | Qué revisar |
|---|---|
| Falta una columna o aparece `KeyError` | Nombre exacto de `atributo`, `columna_score` y columna semanal; CSV activo en **Base de datos** |
| Un cliente queda sin acción | Explicación en **Cliente**: campaña no elegible, canal no habilitado, tope semanal o falta de cupo |
| El peso cambiado no afecta la selección | Algoritmo activo y tabla de parámetros de [CONFIGURACION.md](CONFIGURACION.md) |
| El chequeo del PDF rechaza un escenario modificado | Ese chequeo conserva reglas y cupos iniciales; utilizar el validador con los YAML del escenario |
| Un cambio no se puede aplicar | Corregir la estructura del borrador o las violaciones de la vista previa; volver a calcular tras editar |
| El solver informa `LP sin solucion` | Revisar el mensaje, datos numéricos y configuración. El LP descrito es factible con cero contactos; un fallo no demuestra que el negocio necesite violar reglas |

La [guía de reproducción](REPRODUCIBILIDAD.md) permite iniciar la consola sobre una copia de configuración y generar archivos sin reemplazar la entrega.

## Limitaciones
No hay usuarios ni roles ni aprobación de cambios: cualquiera con acceso puede aplicar una configuración.
