# Límites conocidos y siguientes pasos

## Límites conocidos
- **Un solo canal por cliente.** Lo exige el reto; el motor rechaza `canales_por_cliente ≠ 1`.
- **No entrena modelos.** Los scores ya vienen calculados en la base.
- **Réplica de la línea base:** difiere en 1 producto y 0,1 de valor (10.241,6 vs 10.241,5), probablemente por el orden de empates entre clientes. Documentado, no corregido.
- **Precios sombra:** sensibilidades locales de la utilidad optimizada; no extrapolar grandes cambios linealmente. Con parámetros iniciales están escalados por 1,001 respecto al valor reportado.
- **Alcance del óptimo:** requiere la reducción a paquetes y la estructura bipartita documentadas en [FORMULACION_MATEMATICA.md](FORMULACION_MATEMATICA.md). Un redondeo fraccionario no tiene garantía de optimalidad. Pesos o bonos distintos cambian el objetivo.
- **Salida de dos campañas:** topes internos mayores que dos no caben en las columnas actuales. Hay que adaptar el formato antes de utilizarlos en una entrega.
- **Calidad de datos:** el motor presupone dominios y columnas coherentes. Los ausentes no se tratan igual en todos los filtros y validadores; detalle en [RESTRICCIONES.md](RESTRICCIONES.md).
- **Reproducibilidad histórica:** no se conservaron versiones exactas de todas las dependencias. La guía registra cómo capturarlas; un entorno nuevo no prueba identidad con el original.
- **Consola sin usuarios, roles ni aprobaciones.**
- **Consola sin prueba visual en navegador por parte del equipo de desarrollo:** se probó con `AppTest`, que no puede teclear en las tablas editables. Conviene un recorrido manual antes de presentar.
- **Streamlit no recarga `nba/`:** reiniciar tras cambios de motor.

## Ideas, por valor
1. **Barrido de configuraciones.** Script que evalúe muchas configuraciones y reporte la frontera valor vs jerarquía y el costo de cada regla o cupo. Responde «¿cuál es la mejor configuración?».
2. **Constructor de reglas en español** («no ofrecer Terminales si…») además del asistente actual.
3. **Autoría y aprobación de cambios** en la consola (quién cambió qué, quién aprobó).
4. **Recorrido manual de la consola** en navegador y ajustes de UX resultantes.
5. **Material de presentación/demo**, si el reto lo pide (confirmar entregables).
6. **Validación de datos y cobertura adicional:** probar explícitamente las tres autorizaciones digitales y un duplicado con canales válidos como escenarios de contacto múltiple; no confundir los casos actuales con cobertura exhaustiva.
7. **Manifiesto de ejecución:** persistir commit, hashes de datos/configuración, versiones, estado e integralidad del solver junto a cada entrega. Actualmente algunos de esos datos solo se imprimen o se deben capturar manualmente.

## Limpieza pendiente
- `tests/config_inicial/` es una copia vieja sin uso (las pruebas usan `config_inicial/`).
- `config/versiones/20261104-165826_Ajuste-de-configuraci-n/` guarda una configuración exploratoria antigua.
