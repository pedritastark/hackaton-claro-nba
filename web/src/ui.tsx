import { useState, type ReactNode } from 'react'
import { negritas } from './lib'
import type { ErrorCampo } from './types'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-slate-200 bg-white p-5 ${className}`}>{children}</section>
}

export function Seccion({ titulo, sub, children }: { titulo: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="mb-3">
      <h3 className="text-base font-semibold text-black">{titulo}</h3>
      {sub && <p className="mt-0.5 text-[0.82rem] text-slate-500">{sub}</p>}
      {children}
    </div>
  )
}

export function Titulo({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-[2rem] font-semibold leading-tight tracking-tight text-black">{children}</h1>
      {sub && <p className="mt-1.5 text-[0.95rem] text-slate-500">{sub}</p>}
    </div>
  )
}

export function Metric({ label, valor, delta, ayuda }: { label: string; valor: string; delta?: string; ayuda?: string }) {
  const positivo = delta?.startsWith('+')
  const negativo = delta?.startsWith('−')
  return (
    <Card>
      <div className="text-sm text-slate-500" title={ayuda}>{label}</div>
      <div className="mt-2 text-[2.25rem] font-semibold leading-none tracking-tight text-black tabular-nums">{valor}</div>
      {delta && (
        <div className={`mt-2.5 text-sm font-medium tabular-nums ${positivo ? 'text-bueno' : negativo ? 'text-critico' : 'text-slate-500'}`}>
          {positivo ? '▲ ' : negativo ? '▼ ' : ''}{delta}
        </div>
      )}
    </Card>
  )
}

type Tono = 'ok' | 'error' | 'info' | 'aviso'
const TONOS: Record<Tono, string> = {
  ok: 'border-[#bfe3cf] bg-[#effaf3] text-[#0a4d2c]',
  error: 'border-[#f3c1bb] bg-[#fdf0ee] text-[#7a1409]',
  info: 'border-slate-200 bg-slate-50 text-slate-800',
  aviso: 'border-[#efd9a0] bg-[#fff8e6] text-[#6b4a00]',
}
export function Banner({ tono = 'info', children }: { tono?: Tono; children: ReactNode }) {
  return <div role={tono === 'error' ? 'alert' : 'status'} className={`my-2 rounded-xl border px-4 py-3 text-sm ${TONOS[tono]}`}>{children}</div>
}

export function Negrita({ texto }: { texto: string }) {
  return <>{negritas(texto).map((x, i) => (x.b ? <b key={i}>{x.texto}</b> : <span key={i}>{x.texto}</span>))}</>
}

export function ListaErrores({ errores }: { errores: ErrorCampo[] }) {
  return (
    <ul className="mt-1 list-disc pl-5">
      {errores.map((e, i) => <li key={i}><b>{e.campo}</b>: {e.mensaje}</li>)}
    </ul>
  )
}

export function Cargando({ texto = 'Calculando...' }: { texto?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-slate-600" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-black" />
      <span>{texto}</span>
    </div>
  )
}

export function Boton({ children, onClick, primario = false, disabled = false, pequeno = false }: {
  children: ReactNode; onClick?: () => void; primario?: boolean; disabled?: boolean; pequeno?: boolean
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={`rounded-lg font-medium transition ${pequeno ? 'px-3 py-1.5 text-xs' : 'px-5 py-2.5 text-sm'} ${
        primario ? 'bg-black text-white hover:bg-slate-700' : 'bg-slate-100 text-black hover:bg-slate-200'}`}>
      {children}
    </button>
  )
}

export function Tabs({ pestanas, children }: { pestanas: string[]; children: (activa: string) => ReactNode }) {
  const [activa, setActiva] = useState(pestanas[0])
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1 border-b border-slate-200" role="tablist">
        {pestanas.map((p) => (
          <button key={p} role="tab" aria-selected={p === activa} onClick={() => setActiva(p)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition ${p === activa ? 'border-black text-black' : 'border-transparent text-slate-500 hover:text-black'}`}>
            {p}
          </button>
        ))}
      </div>
      {children(activa)}
    </div>
  )
}

export function Campo({ label, ayuda, children }: { label: string; ayuda?: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium text-slate-800">{label}</span>
      {children}
      {ayuda && <span className="mt-1 block text-xs text-slate-500">{ayuda}</span>}
    </label>
  )
}

export function Deslizador({ label, valor, min, max, paso, onChange, ayuda }: {
  label: string; valor: number; min: number; max: number; paso: number; onChange: (v: number) => void; ayuda?: string
}) {
  return (
    <Campo label={`${label}: ${valor}`} ayuda={ayuda}>
      <input type="range" min={min} max={max} step={paso} value={valor} onChange={(e) => onChange(Number(e.target.value))} />
    </Campo>
  )
}

export function Plegable({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <details className="my-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-black"><span className="caret inline-block text-xs text-slate-500 transition-transform">▶</span>{titulo}</summary>
      <div className="mt-3">{children}</div>
    </details>
  )
}

// Tabla simple de solo lectura
export function TablaLectura({ columnas, filas }: { columnas: string[]; filas: (string | number | ReactNode)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>{columnas.map((c) => <th key={c} className="border-b border-slate-200 px-2 py-2 text-left text-xs font-medium text-slate-500">{c}</th>)}</tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>{f.map((c, j) => <td key={j} className="border-b border-slate-100 px-2 py-2.5">{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Tabla editable: celdas segun el tipo de columna, agregar y quitar filas
export type Col<T> = {
  etiqueta: string
  tipo: 'texto' | 'numero' | 'lista' | 'check' | 'fecha' | 'seleccion'
  opciones?: string[]
  ancho?: string
  paso?: number
  min?: number
  max?: number
  leer: (f: T) => string | number | boolean | null
  escribir: (f: T, v: string | number | boolean) => T
  render?: (f: T, i: number) => ReactNode
}

export function TablaEditable<T>({ filas, columnas, onChange, nueva, textoAgregar = 'Agregar fila' }: {
  filas: T[]; columnas: Col<T>[]; onChange: (f: T[]) => void; nueva: () => T; textoAgregar?: string
}) {
  const cambiar = (i: number, c: Col<T>, v: string | number | boolean) => onChange(filas.map((f, k) => (k === i ? c.escribir(f, v) : f)))
  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-sm">
          <thead className="bg-white">
            <tr>
              {columnas.map((c) => <th key={c.etiqueta} className="px-2 py-2.5 text-left text-xs font-medium text-slate-500" style={{ minWidth: c.ancho }}>{c.etiqueta}</th>)}
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i} className="border-t border-slate-100">
                {columnas.map((c) => {
                  const v = c.leer(f)
                  return (
                    <td key={c.etiqueta} className="px-1.5 py-1.5 align-middle">
                      {c.render ? c.render(f, i)
                        : c.tipo === 'check' ? <input type="checkbox" aria-label={c.etiqueta} checked={Boolean(v)} onChange={(e) => cambiar(i, c, e.target.checked)} />
                        : c.tipo === 'seleccion' ? (
                          <select aria-label={c.etiqueta} value={String(v ?? '')} onChange={(e) => cambiar(i, c, e.target.value)}>
                            {!c.opciones?.includes(String(v ?? '')) && <option value={String(v ?? '')}>{String(v ?? '')}</option>}
                            {c.opciones?.map((o) => <option key={o} value={o}>{o}</option>)}
                          </select>
                        ) : c.tipo === 'numero' ? (
                          <input type="number" aria-label={c.etiqueta} value={Number(v ?? 0)} step={c.paso} min={c.min} max={c.max}
                            onChange={(e) => cambiar(i, c, e.target.value === '' ? 0 : Number(e.target.value))} />
                        ) : c.tipo === 'fecha' ? (
                          <input type="date" aria-label={c.etiqueta} value={String(v ?? '')} onChange={(e) => cambiar(i, c, e.target.value)} />
                        ) : (
                          <input type="text" aria-label={c.etiqueta} value={String(v ?? '')} onChange={(e) => cambiar(i, c, e.target.value)} />
                        )}
                    </td>
                  )
                })}
                <td className="px-1 text-center">
                  <button type="button" title="Quitar fila" aria-label="Quitar fila" onClick={() => onChange(filas.filter((_, k) => k !== i))}
                    className="rounded-md px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-black">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2"><Boton pequeno onClick={() => onChange([...filas, nueva()])}>+ {textoAgregar}</Boton></div>
    </div>
  )
}

export function Esqueleto({ filas = 3, alto = 'h-24' }: { filas?: number; alto?: string }) {
  return (
    <div className="grid gap-4" role="status" aria-label="Cargando">
      {Array.from({ length: filas }).map((_, i) => <div key={i} className={`esqueleto ${alto}`} />)}
    </div>
  )
}
