// Esquema de la configuracion (el mismo de nba/config.py) y respuestas de la API.
export type Campana = {
  id: string; nombre: string; producto: string; columna_score: string; valor_negocio: number
  canales_permitidos: string[]; objetivo: string; vigencia_inicio: string | null; vigencia_fin: string | null; activa: boolean
}
export type Regla = {
  id: string; nombre: string; tipo: 'elegibilidad' | 'canal'
  alcance_nivel: 'global' | 'campana' | 'producto' | 'objetivo' | 'canal'
  alcance_valores: string[]; atributo: string; operador: string; valor: unknown; accion: 'excluir'; activa: boolean
}
export type Canal = { id: string; columna_score: string; cupo: number; max_productos: number }
export type Config = {
  fecha_corrida: string
  campanas: Campana[]
  reglas: Regla[]
  canales: Canal[]
  priorizacion: {
    modo: 'ponderado' | 'jerarquia_estricta'
    jerarquia: string[]
    pesos: { score_producto: number; valor_negocio: number; jerarquia: number }
    umbral_score_producto: number
    desempate: string[]
    alpha: number
    peso_modelo: number
    peso_valor: number
  }
  politica_contacto: { max_contactos_semana: number; columna_contactos_semana: string; canales_por_cliente: number }
  asignacion: { algoritmo: 'optimo' | 'codicioso'; criterio_canal: 'score_canal' | 'orden_preferencia'; orden_preferencia: string[]; umbral_score_canal: number }
}

export type Derivados = {
  calificaciones: Record<string, string[]>
  orden_calificaciones: string[]
  tope_llamadas: number | null
  posicion_jerarquia: Record<string, number>
}
export type ErrorCampo = { campo: string; mensaje: string }
export type Estado = {
  base: { ruta: string; nombre: string; existe: boolean; filas: number }
  configuracion: string | null
  configuracion_valida: boolean
  errores?: ErrorCampo[]
}
export type InfoConfig = { config: Config; nombre: string; columnas: string[]; operadores: string[]; derivados: Derivados }
export type Revision =
  | { ok: false; errores: ErrorCampo[] }
  | { ok: true; config: Config; derivados: Derivados; frases: { id: string; activa: boolean; texto: string }[]; igual_a_vigente: boolean }

export type Metricas = {
  valor_esperado: number; clientes_con_accion: number; productos_asignados: number; jerarquia_pct: number
  uso_canales: Record<string, number>; cupo_canales: Record<string, number>; productos_por_campana: Record<string, number>
}
export type Tablero = {
  estado: { violaciones_total: number; violaciones: Record<string, number>; configuracion: string; algoritmo: string; mejora_pct: number }
  metricas: Metricas
  baseline: Metricas
  anterior: { etiqueta: string; metricas: Metricas } | null
  alertas: { texto: string; pagina?: string; cliente?: string; etiqueta_accion?: string }[]
  optimalidad: { estado: 'optimo' | 'optimo_configurado' | 'aproximado' | 'heuristica'; titulo: string; texto: string }
  precios_sombra: Record<string, number>
  cupos: { canal: string; nombre: string; usado: number; cupo: number }[]
  notas_cupo: string[]
  embudo: { nombre: string; cantidad: number; motivo: string }[]
  composicion: { campana: string; canal: string; productos: number }[]
  canales: { id: string; nombre: string }[]
  campanas: string[]
  reglas: { codigo: string; regla: string; tipo: string; clientes: number }[]
  total: number
  casos: { nombre: string; cantidad: number; id: string }[]
  parametros: { algoritmo: string; alpha: number; peso_modelo: number; peso_valor: number }
}
export type Impacto = {
  comparacion: {
    delta_valor: number; delta_clientes: number; delta_productos: number; delta_jerarquia: number
    ganan_accion: number; pierden_accion: number; cambian_canal: number; cambian_productos: number
    ejemplos: Record<string, string[]>; productos_por_campana: Record<string, [number, number]>
  }
  antes: Metricas
  despues: Metricas
  validacion: { violaciones_total: number; violaciones: Record<string, number> }
}
export type Version = { version: string; etiqueta: string; fecha: string; metricas: Partial<Metricas> }
export type ClienteDetalle = {
  registro: {
    id_cliente: string; estado: string; canal: string | null; valor_esperado: number
    productos: { nombre: string; prob_compra: number; prob_canal: number; valor_negocio: number; valor_esperado: number }[]
    descartados: { nombre: string; motivos: { texto: string }[] }[]
    canales: { canal: string; resultado: string; valor: number | null; motivos: { texto: string }[] }[]
    cupo: { tipo: string; canal_ideal: string; valor_ideal: number; valor_asignado: number; valor_cedido: number } | null
  }
  frase_asesor: string
  frase: string
  datos: { columna: string; valor: string | number | null; reglas: string[] }[]
}
export type InfoBase = {
  ruta: string; existe: boolean; disponibles: string[]
  filas?: number; columnas?: number; ids_unicos?: boolean; faltan?: string[]
  calidad?: { ok: boolean; titulo: string; detalle: string }[]
  perfil?: { columna: string; tipo: string; vacios: number; usada: boolean; min: number | null; max: number | null }[]
  vista_previa?: Record<string, unknown>[]
}

export type Escenario = { id: string; nombre: string; fecha: string; cambios: string[] }
export type Trabajo<T = unknown> = {
  estado: 'corriendo' | 'listo' | 'error'; hecho: number; total: number; parcial: T[]; resultado: Record<string, number | string> | null; error: string | null
}
export type ResultadoEscenario = {
  id: string; nombre: string; metricas: Metricas; violaciones_total: number; violaciones: Record<string, number>; cambios: string[]
}
export type PuntoSensibilidad = { factor: number; cupo: number; valor: number; calculado: boolean }
