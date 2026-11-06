import { useState } from 'react'
import { useSesion } from '../acceso'
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, CONTEXTO, DATO, n, nombreCanal, signo } from '../lib'
import { useTrabajo } from '../store'
import type { PuntoSensibilidad, Tablero as TableroT } from '../types'
import { Banner, Boton } from '../ui'

const EJE = { fontSize: 12, fill: '#4f4f4f' }
const TIP = { borderRadius: 10, border: '1px solid #e4e4e4', boxShadow: 'none' }

export function Sensibilidad({ t }: { t: TableroT }) {
  const { puede } = useSesion()
  const [canal, setCanal] = useState(() => [...t.cupos].sort((a, b) => (t.precios_sombra[b.canal] ?? 0) - (t.precios_sombra[a.canal] ?? 0))[0].canal)
  const [job, setJob] = useState<string | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const trabajo = useTrabajo<PuntoSensibilidad>(job)
  const calcular = async () => {
    setFallo(null)
    try { setJob((await api<{ trabajo: string }>('/api/sensibilidad', { body: { canal } })).trabajo) } catch (e) { setFallo((e as Error).message) }
  }
  const info = t.cupos.find((c) => c.canal === canal)!
  const precio = t.precios_sombra[canal] ?? 0
  const v0 = t.metricas.valor_esperado
  const puntos = [...(trabajo?.parcial ?? [])].sort((a, b) => a.cupo - b.cupo)
  const datos = puntos.map((p) => ({ cupo: p.cupo, real: p.valor, lineal: v0 + precio * (p.cupo - info.cupo) }))
  const nombre = nombreCanal(canal)
  const ult = puntos[puntos.length - 1]
  const prim = puntos[0]
  const listo = trabajo?.estado === 'listo' && ult && prim
  const dMas = listo ? ult.valor - v0 : 0
  const dMenos = listo ? prim.valor - v0 : 0
  return (
    <div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-48">
          <label className="mb-1.5 block text-sm font-medium text-slate-800" htmlFor="canal-sens">Canal</label>
          <select id="canal-sens" value={canal} onChange={(e) => { setCanal(e.target.value); setJob(null) }}>
            {t.cupos.map((c) => <option key={c.canal} value={c.canal}>{c.nombre}</option>)}
          </select>
        </div>
        <Boton primario onClick={calcular} disabled={!puede('laboratorios.ejecutar') || trabajo?.estado === 'corriendo'}>Calcular la curva</Boton>
        <span className="pb-2 text-xs text-slate-500">Recalcula el reparto con la mitad, tres cuartos, uno y medio y el doble del cupo (unos 12 s por punto).</span>
      </div>
      {fallo && <Banner tono="error">{fallo}</Banner>}
      {trabajo?.estado === 'error' && <Banner tono="error">{trabajo.error}</Banner>}
      {trabajo?.estado === 'corriendo' && (
        <div className="mt-4">
          <div className="flex justify-between text-sm"><span>Calculando punto {Math.min(trabajo.hecho + 1, trabajo.total)} de {trabajo.total}...</span><span className="tabular-nums text-slate-500">{trabajo.hecho}/{trabajo.total}</span></div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-black transition-all" style={{ width: `${(100 * trabajo.hecho) / Math.max(1, trabajo.total)}%` }} /></div>
        </div>
      )}
      {datos.length > 1 && (
        <div className="mt-4">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={datos} margin={{ left: 8, right: 24, top: 18, bottom: 4 }}>
              <XAxis type="number" dataKey="cupo" domain={['dataMin', 'dataMax']} tick={EJE} tickFormatter={(v) => n(Number(v))} tickLine={false} axisLine={{ stroke: '#cfcfcf' }} />
              <YAxis domain={['dataMin - 3', 'dataMax + 3']} tick={EJE} tickFormatter={(v) => n(Number(v))} width={64} tickLine={false} axisLine={false} />
              <ReferenceLine x={info.cupo} stroke="#0a0a0a" strokeDasharray="4 4" label={{ value: 'Hoy', position: 'top', fontSize: 12, fill: '#0a0a0a' }} />
              <Tooltip contentStyle={TIP} labelFormatter={(v) => `Cupo de ${nombre}: ${n(Number(v))}`}
                formatter={(v, k) => [n(Number(v), 1), k === 'real' ? 'Valor esperado (reparto recalculado)' : 'Estimación con el precio sombra']} />
              {precio > 0 && <Line type="linear" dataKey="lineal" stroke={CONTEXTO} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />}
              <Line type="linear" dataKey="real" stroke={DATO} strokeWidth={2.5} dot={{ r: 4, fill: DATO, stroke: '#fff', strokeWidth: 2 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap justify-center gap-5 text-sm">
            <span className="flex items-center gap-1.5"><span className="h-0.5 w-5" style={{ background: DATO, height: 3 }} />Valor esperado con el cupo recalculado</span>
            {precio > 0 && <span className="flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: CONTEXTO }} />Estimación lineal con el precio sombra</span>}
          </div>
        </div>
      )}
      {listo && (
        <div className="mt-4 space-y-1.5 rounded-xl bg-slate-50 p-4 text-sm">
          {dMas < 0.05
            ? <p><b>Ampliar el cupo de {nombre} no cambia el valor esperado:</b> el canal no está lleno ({n(info.usado)} de {n(info.cupo)} cupos usados).</p>
            : <p>Llevar {nombre} de {n(info.cupo)} a {n(ult.cupo)} cupos suma <b>{signo(dMas, 1)}</b> de valor esperado ({signo((100 * dMas) / v0, 2)} %).
              {precio * (ult.cupo - info.cupo) > dMas * 1.1 ? ` El precio sombra anticipaba ${signo(precio * (ult.cupo - info.cupo), 1)}: sobreestima porque cada cupo adicional rinde menos.` : ' Coincide con el precio sombra.'}</p>}
          {dMenos < -0.05 && <p>Reducirlo a {n(prim.cupo)} cuesta <b>{signo(dMenos, 1)}</b> ({signo((100 * dMenos) / v0, 2)} %).</p>}
        </div>
      )}
    </div>
  )
}

