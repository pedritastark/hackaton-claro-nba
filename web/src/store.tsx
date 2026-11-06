import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from './lib'
import type { Config, ErrorCampo, Estado, InfoConfig, Revision, Trabajo } from './types'

export const PAGINAS = ['Resumen', 'Tablero', 'Cambiar configuración', 'Laboratorios', 'Cliente', 'Base de datos', 'Versiones', 'Usuarios y permisos', 'Mi cuenta'] as const
export type Pagina = (typeof PAGINAS)[number]

type Ctx = {
  cacheDatos: Map<string, unknown>
  estado: Estado | null
  vigente: InfoConfig | null
  borrador: Config | null
  setBorrador: (f: Config | ((c: Config) => Config)) => void
  revision: Revision | null
  pagina: Pagina
  irA: (p: Pagina, cliente?: string) => void
  clienteSel: string
  setClienteSel: (c: string) => void
  mensaje: string | null
  setMensaje: (m: string | null) => void
  epoca: number
  recargar: (mensaje?: string) => Promise<void>
  cargarComoBorrador: (cfg: Config, mensaje: string, pagina?: Pagina) => void
  errorInicial: { mensaje: string; detalle: ErrorCampo[] } | null
}

const AppCtx = createContext<Ctx | null>(null)
export const useApp = () => {
  const c = useContext(AppCtx)
  if (!c) throw new Error('useApp fuera del proveedor')
  return c
}

export function Proveedor({ children }: { children: ReactNode }) {
  const cacheDatos = useRef(new Map<string, unknown>()).current
  const [estado, setEstado] = useState<Estado | null>(null)
  const [vigente, setVigente] = useState<InfoConfig | null>(null)
  const [borrador, setBorradorRaw] = useState<Config | null>(null)
  const [revision, setRevision] = useState<Revision | null>(null)
  const [pagina, setPagina] = useState<Pagina>('Resumen')
  const [clienteSel, setClienteSel] = useState('')
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [epoca, setEpoca] = useState(0)
  const [errorInicial, setErrorInicial] = useState<Ctx['errorInicial']>(null)

  const setBorrador = useCallback((f: Config | ((c: Config) => Config)) => {
    setBorradorRaw((prev) => (typeof f === 'function' ? (prev ? f(prev) : prev) : f))
  }, [])

  const recargar = useCallback(async (msg?: string) => {
    try {
      const e = await api<Estado>('/api/estado')
      setEstado(e)
      if (e.configuracion_valida) {
        const v = await api<InfoConfig>('/api/config')
        setVigente(v)
        setBorradorRaw(v.config)
        setErrorInicial(null)
      } else {
        setVigente(null)
        setErrorInicial({ mensaje: 'La configuración guardada no es válida.', detalle: e.errores ?? [] })
      }
      setEpoca((x) => x + 1)
      if (msg) setMensaje(msg)
    } catch (err) {
      const a = err as ApiError
      setErrorInicial({ mensaje: a.message ?? 'No se pudo conectar con la API.', detalle: a.detalle ?? [] })
    }
  }, [])

  useEffect(() => { void recargar() }, [recargar])

  // Revisa el borrador con la API (validez, controles directos, frases) con un pequeno retraso al escribir
  const turno = useRef(0)
  useEffect(() => {
    if (!borrador) return
    const mio = ++turno.current
    const t = setTimeout(async () => {
      try {
        const r = await api<Revision>('/api/config/revisar', { body: { config: borrador } })
        if (mio === turno.current) setRevision(r)
      } catch { /* la API caida se nota en el tablero */ }
    }, 300)
    return () => clearTimeout(t)
  }, [borrador])

  const irA = useCallback((p: Pagina, cliente?: string) => {
    if (cliente) setClienteSel(cliente)
    setMensaje(null)
    setPagina(p)
  }, [])

  const cargarComoBorrador = useCallback((cfg: Config, msg: string, p?: Pagina) => {
    setBorradorRaw(cfg)
    setMensaje(msg)
    if (p) setPagina(p)
  }, [])

  const valor = useMemo<Ctx>(() => ({
    cacheDatos,
    estado, vigente, borrador, setBorrador, revision, pagina, irA, clienteSel, setClienteSel, mensaje, setMensaje,
    epoca, recargar, cargarComoBorrador, errorInicial,
  }), [cacheDatos, estado, vigente, borrador, setBorrador, revision, pagina, irA, clienteSel, mensaje, epoca, recargar, cargarComoBorrador, errorInicial])

  return <AppCtx.Provider value={valor}>{children}</AppCtx.Provider>
}

// Datos de la API con cache por epoca: cambiar de seccion no repite el calculo; aplicar un cambio lo invalida.
export function useDatos<T>(url: string | null) {
  const { epoca, cacheDatos: cache } = useApp()
  const clave = `${epoca}|${url}`
  const [datos, setDatos] = useState<T | null>((cache.get(clave) as T) ?? null)
  const [error, setError] = useState<ApiError | null>(null)
  const [cargando, setCargando] = useState(false)

  const cargar = useCallback(async (forzar = false) => {
    if (!url) return
    if (!forzar && cache.has(clave)) { setDatos(cache.get(clave) as T); return }
    setCargando(true)
    setError(null)
    try {
      const d = await api<T>(url)
      cache.set(clave, d)
      setDatos(d)
    } catch (e) {
      setError(e as ApiError)
    } finally {
      setCargando(false)
    }
  }, [url, clave, cache])

  useEffect(() => { void cargar() }, [cargar])
  const recargar = useCallback(() => cargar(true), [cargar])
  return { datos, error, cargando, recargar }
}

// Sigue un trabajo en segundo plano de la API (el motor tarda unos 12 s por corrida) y entrega los resultados parciales.
export function useTrabajo<T>(id: string | null): Trabajo<T> | null {
  const [t, setT] = useState<Trabajo<T> | null>(null)
  useEffect(() => {
    if (!id) { setT(null); return }
    let vivo = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const sondear = async () => {
      try {
        const r = await api<Trabajo<T>>(`/api/trabajos/${id}`)
        if (!vivo) return
        setT(r)
        if (r.estado === 'corriendo') timer = setTimeout(sondear, 1200)
      } catch (e) {
        if (vivo) setT({ estado: 'error', hecho: 0, total: 0, parcial: [], resultado: null, error: (e as Error).message })
      }
    }
    void sondear()
    return () => { vivo = false; if (timer) clearTimeout(timer) }
  }, [id])
  return t
}
