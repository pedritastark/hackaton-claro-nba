---
name: nba-consola-cambios
description: Diseñar la consola de negocio del orquestador NBA para editar configuración, previsualizar el impacto y explicar decisiones. Úsalo al construir la UI/CLI de configuración o la vista de explicaciones.
---

# Consola de configuración

## Requisitos
- Edita config sin abrir código: campañas, reglas, umbrales, prioridad (jerarquía + pesos), canales/cupos, política de contacto, columnas nuevas.
- **Vista previa antes de aplicar** (diff vs parrilla actual): Δ valor esperado, Δ clientes con acción, Δ % jerarquía, clientes que ganan/pierden producto, uso de cada cupo, violaciones (debe ser 0).
- Validación del cambio al guardar (esquema, columna existente, operador válido); versionar configs y permitir revertir.
- Lenguaje de negocio en la UI (no ids técnicos); mostrar el balance jerarquía vs valor y cómo cambiarlo.

## Explicabilidad
Por cliente: una frase para el asesor, ej. "Se ofrece Hogar por WhatsApp: score 0,62, sin servicio Hogar, canal autorizado". Para `sin_accion`: reglas que lo excluyeron.

## Pautas
- Motor y consola desacoplados: la consola solo lee/escribe `config/` y llama al motor.
- UI sencilla (Streamlit/FastAPI+HTML). Verificar con una demo end-to-end de los 6 tipos de cambio; si hay UI, validar con screenshot.
