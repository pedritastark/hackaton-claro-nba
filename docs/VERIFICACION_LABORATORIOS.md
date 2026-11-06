# Verificación del Centro de laboratorios

Fecha: 2026-11-06. La consola React incorpora laboratorios de cupos, reglas y umbrales, prioridades y algoritmo, pruebas combinadas y sensibilidad. Los escenarios existentes se conservan.

## Suite de Python

Comando ejecutado: `.venv/bin/python -m pytest -q`.

```text
102 passed, 7 warnings in 1034.78s (0:17:14)
```

Incluye catorce pruebas de API, la persistencia del resultado y su referencia, compatibilidad con escenarios anteriores, identificadores independientes para nombres repetidos y límites de comparación. Las advertencias proceden de la integración Starlette/httpx y de conversiones de tipos de pandas en el motor existente.

## Compilación y revisión

Se ejecutaron el compilador TypeScript (`tsc -b`), la compilación de Vite y Oxlint. TypeScript y Vite terminaron correctamente. Oxlint terminó sin errores; permanecen diez advertencias anteriores en `store.tsx` y `graficos.tsx`. Vite mantiene la advertencia de tamaño del paquete principal, de aproximadamente 706 kB antes de gzip.

## Navegador real con configuración temporal

Comando reproducible: `cd web && npm run build && npm run e2e:laboratorios`. El script inicia una API separada, copia `config_inicial/` a una carpeta temporal y la elimina al terminar. No requiere cambiar el servidor ni la configuración de uso habitual.

En este entorno se utilizó Node 24.21.0 y Chromium headless 145 instalado en la caché de Playwright, seleccionado mediante `NBA_CHROMIUM`. Sus bibliotecas de ejecución y Fontconfig se resolvieron desde el almacén local de Nix. `NBA_E2E_OUT` permitió guardar las capturas fuera del repositorio.

Salida de la ejecución completada:

```text
OK crear y ejecutar: 0 violaciones; valor 10946.488863804
OK duplicar y editar conserva la prueba original
OK guardar pruebas de reglas y de prioridades
OK resultado conservado tras recargar y sensibilidad de SMS
OK vigente intacta, sin versiones nuevas ni errores de navegador
```

El primer experimento aumenta el cupo de WhatsApp en 100 contactos frente a la configuración inicial. El recorrido también comprueba que cambiar de pestaña en una prueba personalizada no guarda el formulario, que la duplicación no altera la alternativa original y que los cambios de reglas, algoritmo y jerarquía se guardan con sus valores correctos. Se comprobó el ancho a 1440 y 390 píxeles, sin desbordamiento de la página, y se inspeccionaron ambas capturas.

## Servidor local

Se reinició la API local de `http://localhost:8000`, conservando su entorno y la ruta activa de clientes. Se comprobaron los hashes de los YAML antes y después del reinicio, la nueva definición de la API, la respuesta 200 de la interfaz y la lectura del escenario existente con los nuevos campos compatibles.

## Alcance de los resultados guardados

Se conserva el último resultado de cada experimento con sus métricas, validación, fecha, referencia y contexto del archivo de datos. Los resultados anteriores se muestran como históricos; una nueva comparación recalcula contra la configuración vigente y la base activa. Los trabajos en curso viven en memoria y no se recuperan después de reiniciar la API. La consola continúa sin usuarios ni roles.
