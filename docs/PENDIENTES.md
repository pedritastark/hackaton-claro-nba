# Límites conocidos y siguientes pasos

## Límites conocidos
- **Un solo canal por cliente.** Lo exige el reto; el motor rechaza `canales_por_cliente ≠ 1`.
- **No entrena modelos.** Los scores ya vienen calculados en la base.
- **Réplica de la línea base:** difiere en 1 producto y 0,1 de valor (10.241,6 vs 10.241,5), probablemente por el orden de empates entre clientes. Documentado, no corregido.
- **Precios sombra:** fiables para cambios pequeños de cupo (+100); con +2.000 sobreestiman cerca de un 50 %.
- **Consola sin usuarios, roles ni aprobaciones.**
- **Consola sin prueba visual en navegador por parte del equipo de desarrollo:** se probó con `AppTest`, que no puede teclear en las tablas editables. Conviene un recorrido manual antes de presentar.
- **Streamlit no recarga `nba/`:** reiniciar tras cambios de motor.

## Ideas, por valor
1. **Barrido de configuraciones.** Script que evalúe muchas configuraciones y reporte la frontera valor vs jerarquía y el costo de cada regla o cupo. Responde «¿cuál es la mejor configuración?».
2. **Constructor de reglas en español** («no ofrecer Terminales si…») además del asistente actual.
3. **Autoría y aprobación de cambios** en la consola (quién cambió qué, quién aprobó).
4. **Recorrido manual de la consola** en navegador y ajustes de UX resultantes.
5. **Material de presentación/demo**, si el reto lo pide (confirmar entregables).

## Limpieza pendiente
- `tests/config_inicial/` es una copia vieja sin uso (las pruebas usan `config_inicial/`).
- `config/versiones/20261104-165826_Ajuste-de-configuraci-n/` guarda una configuración exploratoria antigua.
