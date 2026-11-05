---
name: nba-asignacion-cupos
description: Diseñar el algoritmo de asignación producto-canal-cliente del orquestador NBA para superar la línea base codiciosa (cupos escasos de asesor/WhatsApp). Úsalo al implementar o mejorar la optimización.
---

# Asignación con cupos

## Pipeline (módulos separados)
1. **Elegibilidad**: por cliente×producto, aplicar reglas y umbrales (config).
2. **Puntaje**: `peso_score*score_prod + peso_valor*valor_negocio + peso_jerarquia*nivel_jerarquia` (pesos y jerarquía de config; modo `ponderado` o `jerarquia_estricta`).
3. **Asignación** respetando cupos, 1 canal/cliente y topes de productos por canal.
4. **Explicación**: llenar `razon` con una frase por decisión (incl. motivo de exclusión: reglas que dispararon).

## Línea base (codiciosa) — a superar
Ordena clientes por puntaje y asigna el canal permitido de mayor score con cupo. Problema: agota asesor/WhatsApp con los primeros clientes.

## Ideas para mejorar (decisión del equipo)
- Valor de contacto por (cliente, canal) = Σ de sus top-k productos de score_prod×score_canal×valor; k = tope del canal.
- Cupos escasos: asignar por **ganancia marginal** (valor en canal escaso − mejor alternativa en canal abundante), no por mayor puntaje. Ordenar por esa ganancia.
- Formulación de asignación (LP/MILP con `scipy.optimize.milp`/`pulp`, o relajación lagrangiana con precio por cupo) y redondeo factible; heurística: precios por canal + iterar hasta cumplir cupos.
- Comparar 1 producto por asesor vs 2 por WhatsApp según cliente.
- Pasada final de reparación: garantizar 0 violaciones y rellenar cupos sobrantes.

## Reglas
Hiperparámetros del algoritmo también en config. Medir cada variante con `nba-validador-metrica` y registrar valor/% jerarquía/tiempo; vectorizar (100k filas).
