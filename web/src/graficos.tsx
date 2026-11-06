import { useEffect, useRef, useState } from 'react'
import { Bar, BarChart, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CONTEXTO, DATO, n, nombreCanal, signo } from './lib'

// Par divergente: azul = aumenta, naranja = disminuye (ambos de la paleta validada)
export const GANA = '#2d6fcf'
export const PIERDE = '#d1702a'
const EJE = { fontSize: 12, fill: '#4f4f4f' }
const TIP = { borderRadius: 10, border: '1px solid #e4e4e4', boxShadow: 'none' }

// ---------------------------------------------------------------- numeros animados
export function useContador(objetivo: number, ms = 700) {
  const [v, setV] = useState(objetivo)
  const previo = useRef(objetivo)
  useEffect(() => {
    const quieto = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (quieto) { setV(objetivo); previo.current = objetivo; return }
    const desde = previo.current
    const t0 = performance.now()
    let id = 0
    const paso = (t: number) => {
      const k = Math.min(1, (t - t0) / ms)
      const e = 1 - Math.pow(1 - k, 3)
      setV(desde + (objetivo - desde) * e)
      if (k < 1) id = requestAnimationFrame(paso)
      else previo.current = objetivo
    }
    id = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(id)
  }, [objetivo, ms])
  return v
}

export function Numero({ valor, dec = 0, sufijo = '' }: { valor: number; dec?: number; sufijo?: string }) {
  const v = useContador(valor)
  return <span className="tabular-nums">{n(v, dec)}{sufijo}</span>
}

// ---------------------------------------------------------------- medidor circular de cupo
export function Medidor({ nombre, usado, cupo }: { nombre: string; usado: number; cupo: number }) {
  const pct = (100 * usado) / Math.max(1, cupo)
  const r = 42
  const c = 2 * Math.PI * r
  const lleno = pct >= 99.5
  return (
    <div className="flex flex-col items-center text-center" title={`${nombre}: ${n(usado)} de ${n(cupo)} cupos`}>
      <div className="relative h-28 w-28" role="img" aria-label={`${nombre}: ${n(pct, 1)} % del cupo usado`}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#f1f1f1" strokeWidth="9" />
          <circle cx="50" cy="50" r={r} fill="none" stroke={DATO} strokeWidth="9" strokeLinecap="round"
            strokeDasharray={`${(c * Math.min(100, pct)) / 100} ${c}`} style={{ transition: 'stroke-dasharray .8s ease' }} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-xl font-semibold tabular-nums tracking-tight">{n(pct)} %</div>
      </div>
      <div className="mt-2 text-sm font-semibold">{nombre}</div>
      <div className="text-xs tabular-nums text-slate-500">{n(usado)} / {n(cupo)}</div>
      {lleno && <span className="mt-1 rounded-full bg-black px-2 py-0.5 text-[0.7rem] font-medium text-white">Lleno</span>}
    </div>
  )
}

// ---------------------------------------------------------------- embudo centrado
const GRISES = ['#e4e4e4', '#d6d6d6', '#c6c6c6', '#b3b3b3']
export function EmbudoCentrado({ etapas }: { etapas: { nombre: string; cantidad: number; motivo: string }[] }) {
  const base = Math.max(1, etapas[0].cantidad)
  return (
    <div>
      {etapas.map((e, i) => {
        const pct = (100 * e.cantidad) / base
        const ultima = i === etapas.length - 1
        const sig = etapas[i + 1]
        return (
          <div key={e.nombre}>
            <div className="mb-1 mt-3 flex justify-between text-xs text-slate-500"><span>{e.nombre}</span><span className="tabular-nums">{n(pct, 1)} %</span></div>
            <div className="mx-auto flex h-10 items-center justify-center rounded-lg text-sm font-semibold tabular-nums transition-all"
              style={{ width: `${Math.max(pct, 22)}%`, background: ultima ? DATO : GRISES[Math.min(i, GRISES.length - 1)], color: ultima ? '#fff' : '#0a0a0a' }}
              title={`${e.nombre}: ${n(e.cantidad)} clientes`}>
              {n(e.cantidad)}
            </div>
            {sig && e.cantidad - sig.cantidad > 0 && (
              <div className="mt-1 text-center text-xs text-slate-500">▼ {n(e.cantidad - sig.cantidad)} · {sig.motivo}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------- mapa de calor campana x canal
export function MapaCalor({ composicion, campanas, canales }: {
  composicion: { campana: string; canal: string; productos: number }[]
  campanas: string[]; canales: { id: string; nombre: string }[]
}) {
  const val = (c: string, ch: string) => composicion.find((x) => x.campana === c && x.canal === ch)?.productos ?? 0
  const max = Math.max(1, ...composicion.map((x) => x.productos))
  const totalCol = (ch: string) => campanas.reduce((s, c) => s + val(c, ch), 0)
  const total = canales.reduce((s, ch) => s + totalCol(ch.id), 0)
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1.5 text-sm">
        <thead>
          <tr>
            <th />
            {canales.map((ch) => <th key={ch.id} className="px-2 pb-1 text-center text-xs font-medium text-slate-500">{ch.nombre}</th>)}
            <th className="px-2 pb-1 text-center text-xs font-medium text-slate-500">Total</th>
          </tr>
        </thead>
        <tbody>
          {campanas.map((c) => (
            <tr key={c}>
              <th scope="row" className="max-w-52 pr-3 text-left text-sm font-medium">{c}</th>
              {canales.map((ch) => {
                const v = val(c, ch.id)
                const a = v ? 0.1 + 0.9 * (v / max) : 0
                return (
                  <td key={ch.id} title={`${c} · ${ch.nombre}: ${n(v)} productos`} className="rounded-lg px-2 py-3 text-center font-semibold tabular-nums"
                    style={{ background: v ? `rgba(45,111,207,${a})` : '#f7f7f7', color: a > 0.5 ? '#fff' : '#0a0a0a' }}>{v ? n(v) : '–'}</td>
                )
              })}
              <td className="px-2 py-3 text-center font-semibold tabular-nums">{n(canales.reduce((s, ch) => s + val(c, ch.id), 0))}</td>
            </tr>
          ))}
          <tr>
            <th scope="row" className="pr-3 text-left text-xs font-medium text-slate-500">Total</th>
            {canales.map((ch) => <td key={ch.id} className="px-2 py-2 text-center text-sm font-semibold tabular-nums">{n(totalCol(ch.id))}</td>)}
            <td className="px-2 py-2 text-center text-sm font-semibold tabular-nums">{n(total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------- barras divergentes (antes / despues)
export type Delta = { nombre: string; cambio: number; antes?: number; despues?: number }

export function BarrasDivergentes({ datos, formato = (v: number) => signo(v, 0) }: { datos: Delta[]; formato?: (v: number) => string }) {
  const max = Math.max(1, ...datos.map((d) => Math.abs(d.cambio)))
  return (
    <ResponsiveContainer width="100%" height={Math.max(90, 48 * datos.length + 16)}>
      <BarChart data={datos} layout="vertical" margin={{ left: 4, right: 56 }}>
        <XAxis type="number" domain={[-max * 1.35, max * 1.35]} hide />
        <YAxis type="category" dataKey="nombre" width={190} tickLine={false} axisLine={false} tick={EJE} />
        <ReferenceLine x={0} stroke="#0a0a0a" />
        <Tooltip cursor={{ fill: '#f7f7f7' }} contentStyle={TIP}
          formatter={(v, _n, p) => {
            const d = p.payload as Delta
            return [d.antes !== undefined && d.despues !== undefined ? `${formato(Number(v))}  (${n(d.antes)} → ${n(d.despues)})` : formato(Number(v)), 'Cambio']
          }} />
        <Bar dataKey="cambio" barSize={20} radius={4}>
          {datos.map((d) => <Cell key={d.nombre} fill={d.cambio >= 0 ? GANA : PIERDE} />)}
          <LabelList dataKey="cambio" content={(p) => {
            const { x, y, width, height, value } = p as unknown as { x: number; y: number; width: number; height: number; value: number }
            const izq = Math.min(Number(x), Number(x) + Number(width))
            const der = Math.max(Number(x), Number(x) + Number(width))
            const neg = Number(value) < 0
            return <text x={neg ? izq - 6 : der + 6} y={Number(y) + Number(height) / 2} dy="0.35em" textAnchor={neg ? 'end' : 'start'}
              fontSize={12} fontWeight={600} fill="#0a0a0a">{formato(Number(value))}</text>
          }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------- piezas pequenas
export function Chip({ children, tono = 'neutro' }: { children: React.ReactNode; tono?: 'neutro' | 'negro' | 'mal' | 'bien' }) {
  const t = { neutro: 'bg-slate-100 text-slate-700', negro: 'bg-black text-white', mal: 'bg-[#fdf0ee] text-[#7a1409]', bien: 'bg-[#effaf3] text-[#0a4d2c]' }[tono]
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${t}`}>{children}</span>
}

export function BarraProb({ etiqueta, valor, color = DATO }: { etiqueta: string; valor: number; color?: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="text-slate-500">{etiqueta}</span><b className="tabular-nums">{n(100 * valor, 0)} %</b></div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${Math.min(100, 100 * valor)}%`, background: color }} /></div>
    </div>
  )
}

export { CONTEXTO, nombreCanal }
