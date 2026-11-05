# Diccionario de datos y formatos

Fuente oficial: `docs/oficial/diccionario_datos_y_formatos.pdf` (Hackatón NBA — Diccionario de datos y formatos, 7 págs.).
Datos oficiales: `data/oficial/clientes.csv` (100.000 filas, 45 columnas; sintéticos según el propio PDF).
`data/clientes.csv` es la base sintética que generamos antes de recibir la oficial (`scripts/generar_clientes.py`); ya no se usa.

## clientes.csv
Una fila por cliente. Las columnas tipo lista separan sus valores con `|` y quedan vacías si no hubo contactos.

| Grupo | Variables |
|---|---|
| Identificación | `id_cliente` (CL000001 a CL100000) |
| Perfil | `region` (Bogotá, Antioquia, Valle, Costa Caribe, Eje Cafetero, Santanderes, Centro, Sur), `estrato` 1–6, `edad` 18–80, `antiguedad_meses` 1–240, `tipo_linea` (Postpago/Prepago) |
| Servicios | `plan_datos_gb` (999 = ilimitado), `consumo_datos_pct`, `arpu_movil`, `tiene_hogar`, `arpu_hogar`, `tiene_netflix`, `tiene_amazon_prime`, `tiene_win`, `cantidad_ott` (0–3) |
| Riesgo | `calificacion_riesgo` (E, A, B, C, P: de mejor a peor), `en_mora`, `dias_mora` (0, 15, 30, 45, 60, 90) |
| Uso digital | `usa_redes_sociales`, `usa_banca_digital`, `compras_digitales` |
| Equipo | `edad_equipo_meses` 0–84, `gama_equipo` (Baja/Media/Alta) |
| Experiencia | `quejas_90d` 0–6, `riesgo_churn` 0–1 |
| Contactabilidad | `tiene_correo`, `autoriza_sms`, `autoriza_correo`, `autoriza_whatsapp` |
| Historial de contactos | `contactos_mes` 0–8, `contactos_semana_actual` 0–3, `contactos_asesor_mes`, `contactos_sms_mes`, `contactos_correo_mes`, `contactos_whatsapp_mes`, `canales_contactados_mes` (lista), `productos_ofertados_mes` (lista: TER, VCH, OTT), `dias_ultimo_contacto` 0–180 |
| Score de producto | `score_terminales` (TER), `score_venta_cruzada_hogar` (VCH), `score_upgrade_ott` (OTT) |
| Score de canal | `score_canal_asesor`, `score_canal_sms`, `score_canal_correo`, `score_canal_whatsapp` |

## Configuración (campos que debe conservar cualquier formato)
- **campanas**: `id`, `nombre`, `producto` (se compara con `productos_ofertados_mes`), `objetivo` (agrupa campañas para reglas), `columna_score`, `valor_negocio` (0–1), `canales_permitidos`, `vigencia_inicio`/`vigencia_fin`, `activa`.
- **reglas**: `id`, `nombre`, `tipo` (elegibilidad | canal), `alcance.nivel` (**global, campana, producto, objetivo o canal**), `alcance.valores`, `condicion.atributo` (cualquier columna), `condicion.operador` (`== != < <= > >= en no_en contiene`), `condicion.valor` (`$producto` = producto de la campaña evaluada), `accion` (excluir), `activa`.
- **parametros**: `priorizacion.modo` (ponderado | jerarquia_estricta), `priorizacion.jerarquia`, `priorizacion.pesos` (3 decimales que **suman 1**: 0,6 / 0,2 / 0,2), `priorizacion.umbral_score_producto` (0,35), `priorizacion.desempate` (score_producto, valor_negocio), `canal.criterio` (score_canal | orden_preferencia), `canal.orden_preferencia`, `canal.umbral_score_canal` (0,25), `canal.capacidad_por_corrida` (asesor 2.500, whatsapp 15.000, correo 30.000, sms 40.000), `politica_contacto.canales_por_cliente` (1), `politica_contacto.max_contactos_semana` (3), `politica_contacto.max_productos_por_canal` (asesor 1, resto 2).

Nuestra implementación usa YAML en `config/` (permitido por el PDF) con estos mismos campos. Extensiones propias: `priorizacion.alpha`, `peso_modelo`, `peso_valor` (ver INFORME). La configuración inicial del reto está en `config_inicial/`.

## Parrilla de salida
CSV con una fila por cliente (incluidos los que no reciben acción), mismo formato de `casos_ejemplo_parrilla_esperada.csv`:

| Columna | Descripción |
|---|---|
| `id_cliente` | Identificador |
| `estado` | `asignado` o `sin_accion` |
| `canal` | Canal elegido; vacío si no hay acción |
| `campana_1` | Campaña de mayor puntaje que va por ese canal |
| `campana_2` | Segunda campaña, si el tope del canal lo permite; vacío si no |
| `razon` | Por qué se decidió así (reglas que excluyeron, tope o cupo alcanzado, canal elegido); texto libre pero entendible sin abrir el código |
