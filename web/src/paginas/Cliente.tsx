import { useState } from 'react'
import { BarraProb, Chip } from '../graficos'
import { DATO, n, nombreCanal } from '../lib'
import { useApp, useDatos } from '../store'
import type { ClienteDetalle } from '../types'
import { Banner, Campo, Card, Cargando, Plegable, Seccion, Titulo } from '../ui'

const corto = (t: string) => t.split('. La regla')[0]
const ETIQUETA_RESULTADO: Record<string, { texto: string; tono: 'negro' | 'neutro' | 'mal' }> = {
  elegido: { texto: 'Elegido', tono: 'negro' },
  alternativa: { texto: 'Alternativa', tono: 'neutro' },
  no_habilitado: { texto: 'No habilitado', tono: 'mal' },
}

function Ficha({ d }: { d: ClienteDetalle }) {
  const reg = d.registro
  const asignado = reg.estado === 'asignado'
  const canales = [...reg.canales].sort((a, b) => (b.valor ?? -1) - (a.valor ?? -1))
  const maxValor = Math.max(1e-9, ...canales.map((c) => c.valor ?? 0))

  return (
    <div className="space-y-5">
      {/* La decision */}
      <section className={`rounded-2xl p-7 ${asignado ? 'bg-black text-white' : 'border-2 border-slate-300 bg-white text-black'}`}>
        <div className={`text-sm ${asignado ? 'text-slate-400' : 'text-slate-500'}`}>Cliente {reg.id_cliente} · decisión</div>
        <div className="mt-2 text-3xl font-semibold leading-tight tracking-tight">
          {asignado ? <>Ofrecer {reg.productos.map((p) => p.nombre).join(' + ')} por <span className="underline decoration-2 underline-offset-4">{nombreCanal(reg.canal ?? '')}</span></> : 'Sin acción para este cliente'}
        </div>
        <p className={`mt-3 max-w-3xl text-sm leading-relaxed ${asignado ? 'text-slate-300' : 'text-slate-600'}`}>{d.frase_asesor}</p>
        {asignado && (
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-black">Valor esperado {reg.valor_esperado.toFixed(3)}</span>
            {reg.cupo?.tipo === 'canal_alternativo' && <span className="rounded-full bg-[#262626] px-3 py-1 text-xs font-medium text-slate-200">Segundo mejor canal (cupo del ideal agotado)</span>}
          </div>
        )}
      </section>

      {/* Datos del cliente que miran las reglas */}
      <Card>
        <Seccion titulo="Datos del cliente" sub="Los atributos que usan las reglas y los puntajes; cada uno muestra qué regla lo mira" />
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-3 lg:grid-cols-4">
          {[...d.datos].sort((a, b) => b.reglas.length - a.reglas.length).map((x) => (
            <div key={x.columna} className="min-w-0">
              <div className="truncate text-xs text-slate-500" title={x.columna}>{x.columna}</div>
              <div className="mt-0.5 flex items-center gap-1.5">
                <b className="text-sm tabular-nums">{x.valor === null || x.valor === '' ? '—' : typeof x.valor === 'number' && !Number.isInteger(x.valor) ? x.valor.toFixed(4) : String(x.valor)}</b>
                {x.reglas.map((r) => <Chip key={r} tono="negro">{r}</Chip>)}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Recorrido */}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <Seccion titulo="1 · Qué productos se pueden ofrecer" sub="Cada campaña pasa por las reglas de negocio y el umbral de probabilidad" />
          <div className="space-y-3">
            {reg.productos.map((p) => (
              <div key={p.nombre} className="rounded-xl border border-black p-4">
                <div className="flex items-center justify-between gap-3"><b>{p.nombre}</b><Chip tono="negro">✓ Ofrecido</Chip></div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <BarraProb etiqueta="Probabilidad de compra" valor={p.prob_compra} />
                  <BarraProb etiqueta={`Probabilidad de respuesta por ${nombreCanal(reg.canal ?? '')}`} valor={p.prob_canal} />
                </div>
                <div className="mt-3 flex gap-6 text-xs text-slate-500">
                  <span>Valor de negocio <b className="text-black">{p.valor_negocio}</b></span>
                  <span>Valor esperado <b className="text-black">{p.valor_esperado.toFixed(4)}</b></span>
                </div>
              </div>
            ))}
            {reg.descartados.map((p) => (
              <div key={p.nombre} className="rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-3"><span className="font-medium text-slate-700">{p.nombre}</span><Chip tono="mal">✕ Descartado</Chip></div>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {p.motivos.map((m, i) => <Chip key={i}>{corto(m.texto)}</Chip>)}
                </div>
                <details className="mt-2.5 text-xs text-slate-500">
                  <summary className="cursor-pointer font-medium text-slate-700 underline underline-offset-2">Ver el detalle de cada regla</summary>
                  <ul className="mt-2 space-y-1.5">{p.motivos.map((m, i) => <li key={i}>{m.texto}</li>)}</ul>
                </details>
              </div>
            ))}
            {reg.productos.length === 0 && reg.descartados.length === 0 && <p className="text-sm text-slate-500">Este cliente no tiene campañas vigentes para evaluar.</p>}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <Seccion titulo="2 · Cómo responde en cada canal" sub="Valor esperado del mejor paquete en cada canal" />
          <div className="space-y-4">
            {canales.map((c) => {
              const et = ETIQUETA_RESULTADO[c.resultado] ?? { texto: c.resultado.replace(/_/g, ' '), tono: 'neutro' as const }
              return (
                <div key={c.canal} className={c.resultado === 'no_habilitado' ? 'opacity-70' : ''}>
                  <div className="flex items-center justify-between text-sm"><b>{nombreCanal(c.canal)}</b><Chip tono={et.tono}>{et.texto}</Chip></div>
                  {c.valor !== null ? (
                    <div className="mt-1.5 flex items-center gap-3">
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full" style={{ width: `${(100 * c.valor) / maxValor}%`, background: c.resultado === 'elegido' ? '#0a0a0a' : DATO }} />
                      </div>
                      <span className="w-14 text-right text-xs tabular-nums text-slate-600">{c.valor.toFixed(4)}</span>
                    </div>
                  ) : null}
                  {c.motivos.length > 0 && <p className="mt-1.5 text-xs text-slate-500">{c.motivos.map((m) => corto(m.texto)).join(' · ')}</p>}
                </div>
              )
            })}
          </div>
          {reg.cupo?.tipo === 'canal_alternativo' && (
            <div className="mt-5 rounded-xl bg-slate-50 p-3.5 text-sm">
              <b>Cupo agotado.</b> Su mejor canal era {nombreCanal(reg.cupo.canal_ideal)} (valor {reg.cupo.valor_ideal.toFixed(3)}), pero se llenó. Se asignó {nombreCanal(reg.canal ?? '')}
              {' '}(valor {reg.cupo.valor_asignado.toFixed(3)}); valor cedido: {n(reg.cupo.valor_cedido, 3)}.
            </div>
          )}
        </Card>
      </div>

      <Plegable titulo="Frase completa de la parrilla y detalle técnico">
        <p className="mb-3 text-sm">{d.frase}</p>
        <pre className="max-h-96 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(reg, null, 2)}</pre>
      </Plegable>
    </div>
  )
}

export function Cliente() {
  const { clienteSel, setClienteSel } = useApp()
  const [situacion, setSituacion] = useState('')
  const sit = useDatos<{ clave: string; cantidad: number }[]>('/api/situaciones')
  const lista = useDatos<string[]>(`/api/clientes?situacion=${encodeURIComponent(situacion)}&limite=300`)
  const [editado, setEditado] = useState<string | null>(null)
  const texto = editado ?? clienteSel
  const confirmar = () => { if (editado !== null && editado.trim()) setClienteSel(editado.trim()); setEditado(null) }
  const cid = clienteSel || lista.datos?.[0] || ''
  const det = useDatos<ClienteDetalle>(cid ? `/api/cliente/${encodeURIComponent(cid)}` : null)

  return (
    <div className="space-y-4">
      <Titulo sub="Por qué el motor tomó esa decisión, en lenguaje de negocio.">Explicación por cliente</Titulo>
      <Card>
        <div className="grid gap-4 md:grid-cols-3">
          <Campo label="Ver un ejemplo de">
            <select value={situacion} onChange={(e) => { setSituacion(e.target.value); setClienteSel('') }}>
              <option value="">(buscar por id)</option>
              {sit.datos?.map((s) => <option key={s.clave} value={s.clave}>{s.clave} ({n(s.cantidad)})</option>)}
            </select>
          </Campo>
          <Campo label="Clientes de esa situación">
            <select value={cid} onChange={(e) => setClienteSel(e.target.value)} disabled={!lista.datos?.length}>
              {lista.datos?.map((id) => <option key={id} value={id}>{id}</option>)}
              {cid && !lista.datos?.includes(cid) && <option value={cid}>{cid}</option>}
            </select>
          </Campo>
          <Campo label="Id del cliente">
            <input type="text" value={texto} onChange={(e) => setEditado(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') confirmar() }} onBlur={confirmar} placeholder="CL000001" />
          </Campo>
        </div>
      </Card>

      {det.cargando && !det.datos && <Cargando texto="Cargando la explicación..." />}
      {det.error && <Banner tono="aviso">{det.error.message}</Banner>}
      {det.datos && <Ficha d={det.datos} />}
    </div>
  )
}
