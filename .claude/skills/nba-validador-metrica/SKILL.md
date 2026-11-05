---
name: nba-validador-metrica
description: Construir y ejecutar el validador de las 16 restricciones (R01–R16) y la métrica de valor esperado e indicador de jerarquía del orquestador NBA. Úsalo para verificar cualquier parrilla antes de dar algo por terminado.
---

# Validador y métricas (el oráculo)

El validador es **independiente del motor** (no reutiliza su lógica de elegibilidad) y lee las reglas de `config/`, no constantes propias.

## Restricciones a revisar, cliente por cliente
R01 mora · R02 TER solo E/A/B · R03 TER equipo ≥18m · R04 VCH sin Hogar · R05 OTT falta alguna · R06 no repetir ofertado en el mes · R07 <3 quejas · R08 score producto ≥0,35 · R09 autorización por canal · R10 asesor <2 llamadas/mes · R11 score canal ≥0,25 · R12 producto solo en canales permitidos · R13 un canal por cliente · R14 asesor 1 producto, digital ≤2 · R15 `contactos_semana_actual`+1 ≤3 · R16 cupo por canal (contacto = 1 cupo).

## Salida de parrilla
CSV: `id_cliente, estado (asignado|sin_accion), canal, campana_1, campana_2, razon`. `sin_accion` ⇒ canal/campañas vacíos.

## Métricas
- Valor = Σ score_producto × score_canal × valor_negocio (por producto asignado).
- Reporte: violaciones por regla, valor, clientes con acción, productos asignados, % jerarquía (clientes que recibieron el producto de mayor jerarquía entre sus elegibles).
- Referencia línea base: 0 violaciones, 10.241,5, 55.393 clientes, 70.443 productos, 99,7 %.

## Verificación mínima
Correr sobre `casos_ejemplo_*` y comparar con `casos_ejemplo_parrilla_esperada.csv`; luego pegar la salida del validador completa.
