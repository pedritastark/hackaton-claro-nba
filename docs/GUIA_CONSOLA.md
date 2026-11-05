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
2. Pulsa para ver el **impacto antes de aplicar**: valor, clientes, productos por campaña y canal, diferencia con signo frente a la línea base.
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

## Limitaciones
No hay usuarios ni roles ni aprobación de cambios: cualquiera con acceso puede aplicar una configuración.
