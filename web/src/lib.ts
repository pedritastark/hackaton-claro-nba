import type { ErrorCampo } from './types'

export class ApiError extends Error {
  detalle: ErrorCampo[]
  codigo: number
  constructor(mensaje: string, detalle: ErrorCampo[], codigo: number) {
    super(mensaje)
    this.detalle = detalle
    this.codigo = codigo
  }
}

type Opciones = { method?: string; body?: unknown; form?: FormData }

export async function api<T>(url: string, o: Opciones = {}): Promise<T> {
  const r = await fetch(url, {
    method: o.method ?? (o.body || o.form ? 'POST' : 'GET'),
    headers: o.body ? { 'Content-Type': 'application/json' } : undefined,
    body: o.form ?? (o.body ? JSON.stringify(o.body) : undefined),
  })
  if (!r.ok) {
    let mensaje = `Error ${r.status}`
    let detalle: ErrorCampo[] = []
    try {
      const j = await r.json()
      mensaje = j.mensaje ?? j.detail?.toString() ?? mensaje
      detalle = j.detalle ?? []
    } catch { /* respuesta sin JSON */ }
    throw new ApiError(mensaje, detalle, r.status)
  }
  return r.json() as Promise<T>
}

// Numeros como se leen en Colombia: 10.940,0 y +698,4 / −12,0
export function n(x: number, dec = 0): string {
  const s = x.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
  return s.replace(/,/g, '_').replace('.', ',').replace(/_/g, '.')
}
export function signo(x: number, dec = 1, unidad = ''): string {
  return `${x >= 0 ? '+' : '−'}${n(Math.abs(x), dec)}${unidad}`
}
export function delta(valor: number, base: number, dec = 1): string {
  const d = valor - base
  return `${signo(d, dec)}${base ? ` (${signo((100 * d) / base, 1)} %)` : ''}`
}

// Textos <-> valores de las tablas de configuracion
export const lista = (s: string): string[] =>
  s.replace(/,/g, '|').split('|').map((x) => x.trim()).filter(Boolean)
export const valorATexto = (v: unknown): string => (Array.isArray(v) ? v.join('|') : String(v ?? ''))
export function textoAValor(txt: string, operador: string): unknown {
  if (operador === 'en' || operador === 'no_en') return txt.split('|').map((x) => x.trim()).filter(Boolean)
  const t = txt.trim()
  const f = Number(t)
  return t !== '' && Number.isFinite(f) ? f : t
}

export const NOMBRE_CANAL: Record<string, string> = { whatsapp: 'WhatsApp', sms: 'SMS', correo: 'Correo', asesor: 'Asesor' }
export const nombreCanal = (c: string) => NOMBRE_CANAL[c] ?? c.charAt(0).toUpperCase() + c.slice(1)

// Un color fijo por canal. Paleta corporativa validada (claro): separacion CVD y contraste comprobados.
export const SERIE = ['#2d6fcf', '#d1702a', '#1d9b73', '#8161be', '#c19a1b', '#c5517a']
export const DATO = '#2d6fcf'      // serie unica
export const CONTEXTO = '#cfcfcf'  // etapas de contexto (el resultado va en DATO)

// Convierte **negrita** de los textos de la API en <b>
export function negritas(t: string): { texto: string; b: boolean }[] {
  return t.split('**').map((texto, i) => ({ texto, b: i % 2 === 1 })).filter((x) => x.texto)
}
