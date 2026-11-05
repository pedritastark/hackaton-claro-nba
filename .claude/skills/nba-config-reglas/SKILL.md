---
name: nba-config-reglas
description: Diseñar o modificar el esquema de configuración y el motor de reglas del orquestador NBA (campañas, reglas, umbrales, canales, política de contacto). Úsalo al tocar config/ o al evaluar reglas sobre columnas.
---

# Configuración y reglas

Fuente inicial: `config_campanas.csv`, `config_reglas.csv`, `config_parametros.csv` del kit. Convertirlos a un formato único (YAML/JSON) en `config/` y validarlos al cargar (fallar con mensaje claro).

## Esquema de regla
`id, nombre, tipo (elegibilidad|canal), alcance_nivel (global|campana|canal), alcance_valores, atributo, operador, valor, accion (excluir), activa`.
- Operadores: `== != < <= > >= en no_en contiene`. `valor` puede ser `$producto` (referencia al producto evaluado).
- Regla = datos, evaluada con un intérprete genérico vectorizado (pandas/numpy). Prohibido `if campana == "C-TER"` en el código.
- Columna nueva en la base ⇒ usable en una regla sin cambiar código (resolver `atributo` por nombre de columna).
- Alcance por grupo de campañas: `alcance_valores` admite lista `C-TER|C-VCH`.

## Cubrir los 6 tipos de cambio
Campañas (alta/pausa `activa`/canales), Reglas (crear/apagar/limitar por calificación), Umbrales (`umbral_score_producto`, `umbral_score_canal`), Prioridad (jerarquía y pesos), Canales y cupos (cupo, productos por canal, canal nuevo), Política de contacto (tope semanal, llamadas asesor), Datos (columna nueva).

## Checklist
- Canal nuevo: requiere columna `score_canal_<x>`; el motor itera canales desde la config.
- Vigencia de campaña (`vigencia_inicio/fin`) y `activa` respetadas.
- Tests: cada tipo de cambio altera la parrilla sin editar código.
