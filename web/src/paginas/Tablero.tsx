import { useState } from 'react'
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EmbudoCentrado, MapaCalor, Medidor, Numero } from '../graficos'
import { CONTEXTO, DATO, delta, n, nombreCanal, SERIE, signo } from '../lib'
import { useApp, useDatos, type Pagina } from '../store'
import type { Tablero as TableroT } from '../types'
import { Banner, Boton, Card, Esqueleto, Negrita, Plegable, Seccion, TablaLectura, Titulo } from '../ui'

import { Sensibilidad } from './Sensibilidad'

const EJE = { fontSize: 12, fill: '#4f4f4f' }
const TIP = { borderRadius: 10, border: '1px solid #e4e4e4', boxShadow: 'none' }

function Franja({ t }: { t: TableroT }) {
  const e = t.estado
  const ok = e.violaciones_total === 0
  return (
    <div role="status" className={`flex items-center gap-4 rounded-xl p-5 ${ok ? 'bg-black text-white' : 'border-2 border-critico bg-white text-black'}`}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg font-bold ${ok ? 'bg-white text-black' : 'bg-critico text-white'}`}>{ok ? '✓' : '!'}</span>
      <div>
        <div className="text-lg font-semibold tracking-tight">
          {ok ? 'Parrilla válida · 0 violaciones de las restricciones' : `Parrilla con ${n(e.violaciones_total)} violaciones de las restricciones`}
        </div>
        <div className={`mt-0.5 text-sm ${ok ? 'text-slate-300' : 'text-slate-500'}`}>
          Configuración: <b className={ok ? 'text-white' : 'text-black'}>{e.configuracion}</b> · {t.optimalidad.titulo.toLowerCase()} · {signo(e.mejora_pct, 1)} % de valor esperado frente al baseline
          {!ok && ' · ' + Object.entries(e.violaciones).map(([k, v]) => `${k}: ${v}`).join(', ')}
        </div>
      </div>
    </div>
  )
}

// Indicador con barra de comparacion: la cifra actual frente a la referencia
function Kpi({ label, valor, dec = 0, sufijo = '', referencia, deltaTxt, ayuda }: {
  label: string; valor: number; dec?: number; sufijo?: string; referencia: number; deltaTxt: string; ayuda?: string
}) {
  const max = Math.max(valor, referencia, 1e-9)
  const pos = deltaTxt.startsWith('+')
  const neg = deltaTxt.startsWith('−')
  return (
    <Card>
      <div className="text-sm text-slate-500" title={ayuda}>{label}</div>
      <div className="mt-2 text-[2.25rem] font-semibold leading-none tracking-tight"><Numero valor={valor} dec={dec} sufijo={sufijo} /></div>
      <div className={`mt-2.5 text-sm font-medium tabular-nums ${pos ? 'text-bueno' : neg ? 'text-critico' : 'text-slate-500'}`}>{pos ? '▲ ' : neg ? '▼ ' : ''}{deltaTxt}</div>
      <div className="mt-3 space-y-1" aria-hidden>
        <div className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${(100 * valor) / max}%`, background: DATO }} /></div>
        <div className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${(100 * referencia) / max}%`, background: CONTEXTO }} /></div>
      </div>
    </Card>
  )
}

function Composicion({ t }: { t: TableroT }) {
  const [vista, setVista] = useState<'barras' | 'calor'>('barras')
  if (!t.composicion.length) return <p className="text-sm text-slate-500">No hay productos asignados.</p>
  const datos = t.campanas.map((c) => {
    const fila: Record<string, string | number> = { campana: c }
    t.canales.forEach((ch) => { fila[ch.id] = t.composicion.find((x) => x.campana === c && x.canal === ch.id)?.productos ?? 0 })
    fila.total = t.canales.reduce((s, ch) => s + (fila[ch.id] as number), 0)
    return fila
  })
  return (
    <div>
      <div className="mb-3 inline-flex rounded-lg bg-slate-100 p-1 text-sm" role="tablist" aria-label="Tipo de gráfico">
        {([['barras', 'Barras'], ['calor', 'Mapa de calor']] as const).map(([k, et]) => (
          <button key={k} role="tab" aria-selected={vista === k} onClick={() => setVista(k)}
            className={`rounded-md px-3.5 py-1.5 font-medium transition ${vista === k ? 'bg-white text-black shadow-sm' : 'text-slate-500 hover:text-black'}`}>{et}</button>
        ))}
      </div>
      {vista === 'calor' ? <MapaCalor composicion={t.composicion} campanas={t.campanas} canales={t.canales} /> : (
        <>
          <ResponsiveContainer width="100%" height={Math.max(150, 62 * datos.length + 30)}>
            <BarChart data={datos} layout="vertical" margin={{ left: 10, right: 50 }}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="campana" width={220} tickLine={false} axisLine={false} tick={EJE} />
              <Tooltip cursor={{ fill: '#f7f7f7' }} contentStyle={TIP} formatter={(v, nombre) => [n(Number(v)), nombreCanal(String(nombre))]} />
              {t.canales.map((ch, i) => (
                <Bar key={ch.id} dataKey={ch.id} stackId="a" fill={SERIE[i]} stroke="#fff" strokeWidth={2} barSize={30}>
                  <LabelList dataKey={ch.id} position="center" fill={i === 4 ? '#0a0a0a' : '#ffffff'} fontSize={12} fontWeight={600}
                    formatter={(v: unknown) => (Number(v) >= 2500 ? n(Number(v)) : '')} />
                  {i === t.canales.length - 1 && <LabelList dataKey="total" position="right" fontSize={12} fontWeight={600} formatter={(v: unknown) => n(Number(v))} />}
                </Bar>
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap justify-center gap-5 pt-1 text-sm text-black" aria-label="Leyenda de canales">
            {t.canales.map((ch, i) => (
              <span key={ch.id} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: SERIE[i] }} />{nombreCanal(ch.id)}</span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function GraficoReglas({ t, tipo }: { t: TableroT; tipo: string }) {
  const d = t.reglas.filter((r) => r.tipo === tipo).sort((a, b) => b.clientes - a.clientes)
  if (!d.length) return <p className="text-sm text-slate-500">Ninguna regla excluyó clientes.</p>
  return (
    <ResponsiveContainer width="100%" height={Math.max(80, 36 * d.length + 10)}>
      <BarChart data={d} layout="vertical" margin={{ right: 50 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="regla" width={310} tickLine={false} axisLine={false} tick={EJE} />
        <Tooltip cursor={{ fill: '#f7f7f7' }} contentStyle={TIP}
          formatter={(v) => [`${n(Number(v))} (${n((100 * Number(v)) / t.total, 1)} % de la base)`, 'Clientes excluidos']} />
        <Bar dataKey="clientes" fill={DATO} radius={[0, 4, 4, 0]} barSize={16}>
          <LabelList dataKey="clientes" position="right" fontSize={12} formatter={(v: unknown) => n(Number(v))} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function Tablero() {
  const { irA } = useApp()
  const { datos: t, error, cargando } = useDatos<TableroT>('/api/tablero')
  const [contra, setContra] = useState<'baseline' | 'anterior'>('baseline')

  if (error) return <Banner tono="error">{error.message}</Banner>
  if (cargando || !t) return (
    <div>
      <Titulo sub="Calculando la parrilla con los 100.000 clientes; la primera vez tarda unos segundos.">Tablero</Titulo>
      <Esqueleto filas={1} alto="h-20" />
      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="esqueleto h-40" />)}</div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2"><div className="esqueleto h-72" /><div className="esqueleto h-72" /></div>
    </div>
  )

  const m = t.metricas
  const ref = contra === 'anterior' && t.anterior ? t.anterior.metricas : t.baseline
  const nombreRef = contra === 'anterior' && t.anterior ? `«${t.anterior.etiqueta}»` : 'baseline'
  const filasComp: [string, number[]][] = [
    ['Valor esperado', [t.baseline.valor_esperado, m.valor_esperado]],
    ['Clientes con acción', [t.baseline.clientes_con_accion, m.clientes_con_accion]],
    ['Productos asignados', [t.baseline.productos_asignados, m.productos_asignados]],
    ['% jerarquía', [t.baseline.jerarquia_pct, m.jerarquia_pct]],
  ]

  return (
    <div className="space-y-5">
      <Titulo>Tablero</Titulo>
      <Franja t={t} />

      {t.anterior && (
        <div className="flex items-center gap-4 text-sm">
          <span className="font-medium">Comparar con</span>
          {([['baseline', 'Baseline'], ['anterior', `Versión anterior · ${t.anterior.etiqueta}`]] as const).map(([k, et]) => (
            <label key={k} className="flex items-center gap-1.5"><input type="radio" name="contra" checked={contra === k} onChange={() => setContra(k)} />{et}</label>
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Valor esperado" valor={m.valor_esperado} dec={1} referencia={ref.valor_esperado} deltaTxt={delta(m.valor_esperado, ref.valor_esperado)} ayuda="Suma de prob. de compra × prob. del canal × valor de negocio." />
        <Kpi label="Clientes con acción" valor={m.clientes_con_accion} referencia={ref.clientes_con_accion} deltaTxt={delta(m.clientes_con_accion, ref.clientes_con_accion, 0)} />
        <Kpi label="Productos asignados" valor={m.productos_asignados} referencia={ref.productos_asignados} deltaTxt={delta(m.productos_asignados, ref.productos_asignados, 0)} />
        <Kpi label="Jerarquía respetada" valor={m.jerarquia_pct} dec={2} sufijo=" %" referencia={ref.jerarquia_pct} deltaTxt={`${signo(m.jerarquia_pct - ref.jerarquia_pct, 2)} pp`} ayuda="% de clientes con acción que recibieron su producto elegible de mayor jerarquía." />
      </div>
      <p className="-mt-2 text-xs text-slate-500">Barra azul: motor actual. Barra gris: {nombreRef}.</p>

      {t.alertas.length > 0 && (
        <div>
          <Seccion titulo="Para revisar" />
          <div className="grid gap-2.5 md:grid-cols-2">
            {t.alertas.map((a, i) => (
              <div key={i} role="note" className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
                <span className="flex items-start gap-3"><span className="mt-0.5 text-alerta">●</span><span><Negrita texto={a.texto} /></span></span>
                {(a.cliente || a.pagina) && (
                  <Boton pequeno onClick={() => (a.cliente ? irA('Cliente', a.cliente) : irA(a.pagina as Pagina))}>{a.etiqueta_accion ?? 'Ver'}</Boton>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <Seccion titulo="Uso de cupos por canal" sub="Cuánto del cupo de cada canal se ocupó" />
          <div className="grid grid-cols-2 gap-y-6 sm:grid-cols-4">{t.cupos.map((c) => <Medidor key={c.canal} nombre={c.nombre} usado={c.usado} cupo={c.cupo} />)}</div>
          <div className="mt-5">
            {t.notas_cupo.map((x, i) => <div key={i} className="my-1.5 border-l-2 border-black pl-3 text-sm"><Negrita texto={x} /></div>)}
            <p className="mt-2 text-xs text-slate-500">Estimación del modelo, fiable para ampliaciones pequeñas.</p>
          </div>
        </Card>
        <Card>
          <Seccion titulo="¿Dónde se pierden los clientes?" sub="De la base completa a los clientes que reciben una acción" />
          <EmbudoCentrado etapas={t.embudo} />
        </Card>
      </div>

      <Card><Seccion titulo="¿Qué se ofrece y por dónde?" sub="Productos asignados por campaña y canal" /><Composicion t={t} /></Card>

      <Card>
        <Seccion titulo="¿Vale la pena ampliar un canal?" sub="Cuánto cambia el valor esperado al subir o bajar el cupo de un canal" />
        <Sensibilidad t={t} />
      </Card>

      <Card>
        <Seccion titulo="Reglas que más clientes excluyen" sub="Clientes que cada regla deja fuera de al menos una campaña o canal; un cliente puede quedar fuera por varias reglas a la vez" />
        <div className="grid gap-6 lg:grid-cols-2">
          {['Qué productos se ofrecen', 'Por qué canal'].map((tipo) => (
            <div key={tipo}><div className="mb-1 font-semibold">{tipo}</div><GraficoReglas t={t} tipo={tipo} /></div>
          ))}
        </div>
      </Card>

      <Card>
        <Seccion titulo="De la cifra al cliente" sub="Abre un caso real de cada situación para ver su explicación" />
        {t.casos.map((c) => (
          <div key={c.nombre} className="flex items-center justify-between border-b border-slate-100 py-2.5 text-sm last:border-0">
            <span className="flex-1">{c.nombre}</span>
            <span className="w-36 tabular-nums"><b>{n(c.cantidad)}</b> clientes</span>
            <Boton pequeno onClick={() => irA('Cliente', c.id)}>Ver un ejemplo</Boton>
          </div>
        ))}
      </Card>

      <Plegable titulo="Detalle de la comparación">
        <TablaLectura columnas={['', 'Baseline', 'Motor actual', 'Diferencia vs. baseline', 'Variación %']}
          filas={filasComp.map(([nom, [b, a]]) => [nom, n(b, 2), n(a, 2), signo(a - b, 2), b ? `${signo((100 * (a - b)) / b, 1)} %` : '—'])} />
        <p className="mt-2 text-xs text-slate-500">Algoritmo: <b>{t.parametros.algoritmo}</b> · α: <b>{t.parametros.alpha}</b> · peso del modelo: <b>{t.parametros.peso_modelo}</b> · peso del valor: <b>{t.parametros.peso_valor}</b>.</p>
      </Plegable>

      <div>
        <a href="/api/parrilla.csv" download="parrilla.csv" className="inline-block rounded-lg bg-slate-100 px-5 py-2.5 text-sm font-medium text-black hover:bg-slate-200">Descargar parrilla.csv (con explicaciones)</a>
        <span className="ml-3 text-xs text-slate-500">Se genera al pedirla; puede tardar unos segundos.</span>
      </div>
    </div>
  )
}
