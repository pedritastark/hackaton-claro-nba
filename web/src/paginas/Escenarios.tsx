import { Fragment, useEffect, useState } from 'react'
import { BarrasDivergentes, Chip } from '../graficos'
import { api, ApiError, delta, n, nombreCanal, signo } from '../lib'
import { useApp, useDatos, useTrabajo } from '../store'
import type { Config, Escenario, ResultadoEscenario } from '../types'
import { Banner, Boton, Campo, Card, Esqueleto, Seccion, Titulo } from '../ui'
import { Experimento, type EdicionExperimento } from './Experimento'
import { LABORATORIOS } from '../laboratorios'
import { Sensibilidad } from './Sensibilidad'
import type { Tablero as TableroT } from '../types'

const MAX = 4

export function Escenarios() {
  const { cargarComoBorrador, vigente: configuracion, borrador, recargar } = useApp()
  const { datos: lista, error, cargando, recargar: refrescar } = useDatos<Escenario[]>('/api/escenarios')
  const [sel, setSel] = useState<string[]>([])
  const [job, setJob] = useState<string | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const [fuente, setFuente] = useState('vigente')
  const [edicion, setEdicion] = useState<EdicionExperimento | null>(null)
  const [solicitando, setSolicitando] = useState(false)
  const [sensibilidad, setSensibilidad] = useState(false)
  const trabajo = useTrabajo<ResultadoEscenario>(job)
  const ocupado = solicitando || trabajo?.estado === 'corriendo'

  useEffect(() => {
    if (trabajo?.estado === 'listo' || trabajo?.estado === 'error') void refrescar()
  }, [trabajo?.estado, refrescar])

  const alternar = (id: string) => {
    setJob(null)
    setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < MAX ? [...s, id] : s))
  }
  const comparar = async (ids = sel) => {
    if (ocupado) return
    setSolicitando(true)
    setFallo(null); setJob(null)
    try { setJob((await api<{ trabajo: string }>('/api/escenarios/comparar', { body: { ids } })).trabajo) }
    catch (e) { setFallo((e as ApiError).message) }
    finally { setSolicitando(false) }
  }
  const duplicar = async (e: Escenario) => {
    setFallo(null)
    try {
      const r = await api<{ config: Config }>(`/api/escenarios/${encodeURIComponent(e.id)}`)
      setEdicion({ tipo: 'libre', config: r.config, nombre: `Copia de ${e.nombre}`.slice(0, 200), objetivo: e.objetivo })
    } catch (er) { setFallo((er as ApiError).message) }
  }
  const guardado = async (id: string, ejecutar: boolean) => {
    setEdicion(null); setJob(null); setSel([id])
    await refrescar()
    if (ejecutar) await comparar([id])
  }
  const cargar = async (e: Escenario) => {
    try {
      const r = await api<{ config: Config }>(`/api/escenarios/${encodeURIComponent(e.id)}`)
      cargarComoBorrador(r.config, `Escenario «${e.nombre}» cargado como borrador. Calcula su impacto y aplícalo si es lo que quieres.`, 'Cambiar configuración')
    } catch (er) { setFallo((er as ApiError).message) }
  }
  const eliminar = async (e: Escenario) => {
    if (!window.confirm(`¿Eliminar el escenario «${e.nombre}»?`)) return
    try {
      await api(`/api/escenarios/${encodeURIComponent(e.id)}`, { method: 'DELETE' })
      setSel((s) => s.filter((x) => x !== e.id)); setJob(null); await refrescar()
    } catch (er) { setFallo((er as ApiError).message) }
  }
  const aplicar = async (r: ResultadoEscenario) => {
    if (!window.confirm(`¿Aplicar «${r.nombre}» como la configuración vigente?`)) return
    try {
      const c = await api<{ config: Config }>(`/api/escenarios/${encodeURIComponent(r.id)}`)
      const ap = await api<{ version: string }>('/api/aplicar', { body: { config: c.config, etiqueta: r.nombre } })
      setJob(null); setSel([])
      await recargar(`Escenario «${r.nombre}» aplicado (versión ${ap.version}).`)
    } catch (er) { setFallo((er as ApiError).message) }
  }

  if (error) return <Banner tono="error">{error.message}</Banner>
  if (cargando && !lista) return <><Titulo>Centro de laboratorios</Titulo><Esqueleto filas={2} alto="h-28" /></>

  const res = trabajo?.parcial ?? []
  const vigente = res.find((r) => r.id === 'vigente')
  const otros = res.filter((r) => r.id !== 'vigente')
  const mejor = otros.filter((r) => r.violaciones_total === 0).sort((a, b) => b.metricas.valor_esperado - a.metricas.valor_esperado)[0]
  const canales = vigente ? Object.keys(vigente.metricas.cupo_canales) : []
  const campanas = vigente ? Object.keys(vigente.metricas.productos_por_campana) : []

  return (
    <div className="space-y-5">
      <Titulo sub="Crea experimentos, prueba alternativas y compara sus resultados antes de decidir qué aplicar.">Centro de laboratorios</Titulo>
      {fallo && <Banner tono="error">{fallo}</Banner>}

      <section className="rounded-xl bg-black p-6 text-white">
        <div className="text-xs uppercase tracking-widest text-slate-400">Espacio de experimentación</div>
        <h2 className="mt-2 text-xl font-semibold">Una pregunta, una prueba, una decisión.</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-300">Cada experimento trabaja sobre una copia. Guarda alternativas, ejecútalas sobre la base activa y contrasta su valor, cobertura y restricciones con la configuración vigente.</p>
      </section>

      {edicion ? <Experimento inicial={edicion} cerrar={() => setEdicion(null)} guardado={guardado} /> : (
        <section>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <Seccion titulo="¿Qué quieres poner a prueba?" />
            <Campo label="Punto de partida">
              <select value={fuente} onChange={(e) => setFuente(e.target.value)}>
                <option value="vigente">Configuración vigente</option>
                <option value="borrador" disabled={!borrador}>Mi borrador actual</option>
              </select>
            </Campo>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {LABORATORIOS.map((l) => (
              <Card key={l.tipo}>
                <h3 className="font-semibold">{l.nombre}</h3>
                <p className="mb-4 mt-1 text-sm text-slate-500">{l.descripcion}</p>
                <Boton pequeno disabled={ocupado} onClick={() => {
                  const config = fuente === 'borrador' ? borrador : configuracion?.config
                  if (config) setEdicion({ tipo: l.tipo, config: structuredClone(config) })
                }}>{l.tipo === 'libre' ? 'Crear prueba personalizada' : `Crear prueba de ${l.nombre.toLowerCase()}`}</Boton>
              </Card>
            ))}
          </div>
        </section>
      )}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <Seccion titulo="Sensibilidad de cupos" sub="Explora varios niveles de capacidad de un canal y observa dónde deja de crecer el valor esperado." />
          <Boton pequeno onClick={() => setSensibilidad((v) => !v)}>{sensibilidad ? 'Cerrar sensibilidad' : 'Abrir sensibilidad'}</Boton>
        </div>
        {sensibilidad && <LaboratorioSensibilidad />}
      </Card>

      <Seccion titulo="Experimentos guardados" sub="Tus escenarios anteriores también están aquí. Elige hasta cuatro alternativas para compararlas con la vigente." />

      {lista && lista.length === 0 ? (
        <Card>
          <div className="py-6 text-center">
            <div className="text-lg font-semibold">Tu primera prueba empieza arriba</div>
            <p className="mx-auto mt-1 max-w-lg text-sm text-slate-500">
              Elige un laboratorio y guarda tu experimento. También puedes traer un borrador desde «Cambiar configuración» con <b>Guardar como escenario</b>.
            </p>
          </div>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {lista?.map((e) => {
              const marcado = sel.includes(e.id)
              return (
                <Card key={e.id} className={marcado ? '!border-black' : ''}>
                  <div className="flex items-start justify-between gap-3">
                    <label className="flex cursor-pointer items-start gap-3">
                      <input type="checkbox" className="mt-1" checked={marcado} disabled={ocupado || (!marcado && sel.length >= MAX)} onChange={() => alternar(e.id)} aria-label={`Seleccionar ${e.nombre}`} />
                      <span>
                        <span className="block font-semibold">{e.nombre}</span>
                        <span className="block text-xs text-slate-500">{LABORATORIOS.find((l) => l.tipo === e.tipo)?.nombre ?? 'Prueba personalizada'}</span>
                        <span className="block text-xs text-slate-500">{new Date(e.fecha).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                      </span>
                    </label>
                  </div>
                  {e.objetivo && <p className="mt-3 text-sm text-slate-600">{e.objetivo}</p>}
                  {e.ultimo_resultado ? (
                    <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
                      <div className="flex flex-wrap gap-2"><Chip>{e.ultimo_resultado.violaciones_total === 0 ? 'Prueba válida' : 'Con violaciones'}</Chip><span className="text-xs text-slate-500">Último resultado · histórico</span></div>
                      <div className="mt-2">Valor esperado: <b>{n(e.ultimo_resultado.metricas.valor_esperado, 1)}</b></div>
                      <Delta txt={delta(e.ultimo_resultado.metricas.valor_esperado, e.ultimo_resultado.metricas_referencia.valor_esperado)} />
                      <p className="mt-1 text-xs text-slate-500">Referencia: {e.ultimo_resultado.referencia} · {e.ultimo_resultado.base.archivo} · {new Date(e.ultimo_resultado.fecha).toLocaleString('es-CO')}</p>
                    </div>
                  ) : <div className="mt-3"><Chip>Sin resultado guardado</Chip></div>}
                  <ul className="mt-3 space-y-1 text-sm text-slate-700">
                    {e.cambios.length === 0 && <li className="text-slate-500">Igual a la configuración vigente.</li>}
                    {e.cambios.slice(0, 4).map((c) => <li key={c}>· {c}</li>)}
                    {e.cambios.length > 4 && <li className="text-slate-500">· y {e.cambios.length - 4} cambios más</li>}
                  </ul>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Boton pequeno disabled={ocupado || !!edicion} onClick={() => duplicar(e)}>Duplicar prueba</Boton>
                    <Boton pequeno onClick={() => cargar(e)}>Cargar como borrador</Boton>
                    <Boton pequeno disabled={ocupado} onClick={() => eliminar(e)}>Eliminar</Boton>
                  </div>
                </Card>
              )
            })}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Boton primario disabled={sel.length === 0 || ocupado || !!edicion} onClick={() => comparar()}>
              Comparar {sel.length > 0 ? `${sel.length} ` : ''}con la configuración vigente
            </Boton>
            <span className="text-xs text-slate-500">Elige hasta {MAX}. Cada escenario tarda unos 12 segundos la primera vez.</span>
          </div>
        </>
      )}

      {solicitando && <Banner>Iniciando la comparación…</Banner>}
      {trabajo?.estado === 'error' && <Banner tono="error">{trabajo.error}</Banner>}
      {trabajo?.estado === 'corriendo' && (
        <Card>
          <div className="flex items-center justify-between text-sm"><span>Calculando {Math.min(trabajo.hecho + 1, trabajo.total)} de {trabajo.total}...</span>
            <span className="tabular-nums text-slate-500">{trabajo.hecho}/{trabajo.total}</span></div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-black transition-all" style={{ width: `${(100 * trabajo.hecho) / Math.max(1, trabajo.total)}%` }} /></div>
        </Card>
      )}

      {vigente && otros.length > 0 && (
        <>
          <Card>
            <Seccion titulo="Cambio en el valor esperado frente a la configuración vigente" sub={`Vigente: ${n(vigente.metricas.valor_esperado, 1)} · azul: sube · naranja: baja`} />
            <BarrasDivergentes formato={(v) => signo(v, 1)}
              datos={otros.map((r) => ({ nombre: r.nombre, cambio: r.metricas.valor_esperado - vigente.metricas.valor_esperado,
                antes: Math.round(vigente.metricas.valor_esperado), despues: Math.round(r.metricas.valor_esperado) }))} />
          </Card>

          <Card>
            <Seccion titulo="Comparación lado a lado" />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="w-56 pb-3 text-left text-xs font-medium text-slate-500" />
                    {res.map((r) => (
                      <th key={r.id} className="min-w-40 pb-3 pr-3 text-left align-bottom">
                        <div className="font-semibold">{r.nombre}</div>
                        <div className="mt-1 flex gap-1.5">
                          {r.id === 'vigente' && <Chip>Referencia</Chip>}
                          {mejor?.id === r.id && <Chip tono="negro">Mejor valor</Chip>}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <Fila etiqueta="Valor esperado" celdas={res.map((r) => (
                    <Fragment key={r.id}><b className="tabular-nums">{n(r.metricas.valor_esperado, 1)}</b>{r.id !== 'vigente' && <Delta txt={delta(r.metricas.valor_esperado, vigente.metricas.valor_esperado)} />}</Fragment>))} />
                  <Fila etiqueta="Clientes con acción" celdas={res.map((r) => (
                    <Fragment key={r.id}><span className="tabular-nums">{n(r.metricas.clientes_con_accion)}</span>{r.id !== 'vigente' && <Delta txt={signo(r.metricas.clientes_con_accion - vigente.metricas.clientes_con_accion, 0)} />}</Fragment>))} />
                  <Fila etiqueta="Productos asignados" celdas={res.map((r) => (
                    <Fragment key={r.id}><span className="tabular-nums">{n(r.metricas.productos_asignados)}</span>{r.id !== 'vigente' && <Delta txt={signo(r.metricas.productos_asignados - vigente.metricas.productos_asignados, 0)} />}</Fragment>))} />
                  <Fila etiqueta="Jerarquía respetada" celdas={res.map((r) => <span key={r.id} className="tabular-nums">{n(r.metricas.jerarquia_pct, 2)} %</span>)} />
                  <Fila etiqueta="Violaciones de restricciones" celdas={res.map((r) => (
                    r.violaciones_total === 0 ? <Chip key={r.id} tono="bien">✓ 0</Chip> : <Chip key={r.id} tono="mal">✕ {n(r.violaciones_total)}</Chip>))} />
                  <Separador texto="Uso de cupos" />
                  {canales.map((c) => (
                    <Fila key={c} etiqueta={nombreCanal(c)} celdas={res.map((r) => (
                      <span key={r.id} className="tabular-nums">{n(r.metricas.uso_canales[c] ?? 0)} <span className="text-slate-400">/ {n(r.metricas.cupo_canales[c] ?? 0)}</span></span>))} />
                  ))}
                  <Separador texto="Productos asignados por campaña" />
                  {campanas.map((c) => (
                    <Fila key={c} etiqueta={c} celdas={res.map((r) => <span key={r.id} className="tabular-nums">{n(r.metricas.productos_por_campana[c] ?? 0)}</span>)} />
                  ))}
                  <Separador texto="Qué cambia" />
                  <Fila etiqueta="Diferencias" celdas={res.map((r) => (
                    r.id === 'vigente' ? <span key={r.id} className="text-slate-400">—</span> : <ul key={r.id} className="space-y-1 text-xs text-slate-600">{r.cambios.slice(0, 5).map((c) => <li key={c}>{c}</li>)}</ul>))} />
                  <tr>
                    <td className="pt-4" />
                    {res.map((r) => (
                      <td key={r.id} className="pt-4 pr-3">
                        {r.id !== 'vigente' && (
                          <Boton pequeno primario disabled={r.violaciones_total > 0 || trabajo?.estado === 'corriendo'} onClick={() => aplicar(r)}>
                            {r.violaciones_total > 0 ? 'No aplicable' : 'Aplicar este escenario'}
                          </Boton>)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">La validación usa las reglas de cada experimento. Revisa también los filtros desactivados antes de aplicar. La aplicación vuelve a validar y queda registrada en el historial de versiones.</p>
          </Card>
        </>
      )}
    </div>
  )
}

function LaboratorioSensibilidad() {
  const { datos, error } = useDatos<TableroT>('/api/tablero')
  if (error) return <Banner tono="error">{error.message}</Banner>
  if (!datos) return <Esqueleto filas={1} />
  return <Sensibilidad t={datos} />
}

function Fila({ etiqueta, celdas }: { etiqueta: string; celdas: React.ReactNode[] }) {
  return (
    <tr className="border-t border-slate-100">
      <th scope="row" className="py-2.5 pr-3 text-left text-sm font-medium text-slate-600">{etiqueta}</th>
      {celdas.map((c, i) => <td key={i} className="py-2.5 pr-3 align-top">{c}</td>)}
    </tr>
  )
}
function Separador({ texto }: { texto: string }) {
  return <tr><td colSpan={9} className="pb-1 pt-5 text-xs font-medium uppercase tracking-wide text-slate-400">{texto}</td></tr>
}
function Delta({ txt }: { txt: string }) {
  const pos = txt.startsWith('+')
  const neg = txt.startsWith('−')
  return <div className={`text-xs font-medium tabular-nums ${pos ? 'text-bueno' : neg ? 'text-critico' : 'text-slate-500'}`}>{pos ? '▲ ' : neg ? '▼ ' : ''}{txt}</div>
}
