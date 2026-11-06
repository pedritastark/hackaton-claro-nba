import { useRef, useState } from 'react'
import { api, ApiError, nombreCanal } from '../lib'
import type { Config, TipoLaboratorio } from '../types'
import { Banner, Boton, Campo, Card, ListaErrores, Seccion, Tabs } from '../ui'
import { LABORATORIOS } from '../laboratorios'

export type EdicionExperimento = { tipo: TipoLaboratorio; config: Config; nombre?: string; objetivo?: string }

export function Experimento({ inicial, cerrar, guardado }: {
  inicial: EdicionExperimento; cerrar: () => void; guardado: (id: string, ejecutar: boolean) => Promise<void>
}) {
  const [config, setConfig] = useState<Config>(() => structuredClone(inicial.config))
  const [nombre, setNombre] = useState(inicial.nombre ?? '')
  const [objetivo, setObjetivo] = useState(inicial.objetivo ?? '')
  const [ocupado, setOcupado] = useState(false)
  const [fallo, setFallo] = useState<ApiError | null>(null)
  const formulario = useRef<HTMLFormElement>(null)
  const laboratorio = LABORATORIOS.find((l) => l.tipo === inicial.tipo)!
  const cambiar = (f: (c: Config) => void) => setConfig((anterior) => {
    const copia = structuredClone(anterior)
    f(copia)
    return copia
  })
  const guardar = async (ejecutar: boolean) => {
    if (ocupado || !formulario.current?.reportValidity()) return
    setOcupado(true); setFallo(null)
    try {
      const r = await api<{ id: string }>('/api/escenarios', {
        body: { nombre, objetivo, tipo: inicial.tipo, config },
      })
      await guardado(r.id, ejecutar)
    } catch (e) { setFallo(e as ApiError); setOcupado(false) }
  }

  const controles = (tipo: string) => {
    if (tipo === 'Cupos y canales') return (
      <div className="grid gap-4 sm:grid-cols-2">
        {config.canales.map((canal, i) => (
          <Campo key={canal.id} label={`Cupo de ${nombreCanal(canal.id)}`} ayuda={`Referencia: ${inicial.config.canales[i].cupo.toLocaleString('es-CO')} contactos`}>
            <input type="number" aria-label={`Cupo de ${nombreCanal(canal.id)}`} required min={0} step={1} value={Number.isNaN(canal.cupo) ? '' : canal.cupo}
              onChange={(e) => cambiar((c) => { c.canales[i].cupo = e.target.valueAsNumber })} />
          </Campo>
        ))}
      </div>
    )
    if (tipo === 'Reglas y umbrales') return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo label="Puntaje mínimo del producto">
            <input type="number" required min={0} max={1} step="any" value={Number.isNaN(config.priorizacion.umbral_score_producto) ? '' : config.priorizacion.umbral_score_producto}
              onChange={(e) => cambiar((c) => { c.priorizacion.umbral_score_producto = e.target.valueAsNumber })} />
          </Campo>
          <Campo label="Probabilidad mínima del canal">
            <input type="number" required min={0} max={1} step="any" value={Number.isNaN(config.asignacion.umbral_score_canal) ? '' : config.asignacion.umbral_score_canal}
              onChange={(e) => cambiar((c) => { c.asignacion.umbral_score_canal = e.target.valueAsNumber })} />
          </Campo>
        </div>
        <p className="text-sm text-slate-500">Activa o desactiva reglas dentro de esta prueba. La validación se realiza con las reglas del experimento.</p>
        <div className="divide-y divide-slate-100">
          {config.reglas.map((r, i) => (
            <label key={r.id} className="flex cursor-pointer items-start gap-3 py-2.5 text-sm">
              <input type="checkbox" className="mt-0.5" checked={r.activa}
                onChange={(e) => cambiar((c) => { c.reglas[i].activa = e.target.checked })} />
              <span><b>{r.id}</b> · {r.nombre}</span>
            </label>
          ))}
        </div>
      </div>
    )
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo label="Peso de la jerarquía (α)" ayuda="0 prioriza el valor; al aumentar, favorece las campañas de mayor jerarquía.">
            <input type="number" aria-label="Peso de la jerarquía (α)" required min={0} max={1} step="any" value={Number.isNaN(config.priorizacion.alpha) ? '' : config.priorizacion.alpha}
              onChange={(e) => cambiar((c) => { c.priorizacion.alpha = e.target.valueAsNumber })} />
          </Campo>
          <Campo label="Algoritmo de asignación">
            <select aria-label="Algoritmo de asignación" value={config.asignacion.algoritmo} onChange={(e) => cambiar((c) => { c.asignacion.algoritmo = e.target.value as Config['asignacion']['algoritmo'] })}>
              <option value="optimo">Óptimo</option><option value="codicioso">Codicioso (línea base)</option>
            </select>
          </Campo>
        </div>
        <p className="text-sm text-slate-500">Orden de prioridad de las campañas. Los cambios de α modifican el objetivo optimizado; compara también el valor esperado y la jerarquía respetada.</p>
        <ol className="divide-y divide-slate-100">
          {config.priorizacion.jerarquia.map((id, i, ids) => (
            <li key={id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span>{i + 1}. {config.campanas.find((c) => c.id === id)?.nombre ?? id}</span>
              <div className="flex gap-2">
                {([-1, 1] as const).map((d) => (
                  <button key={d} type="button" aria-label={`${d < 0 ? 'Subir' : 'Bajar'} ${id}`}
                    disabled={i + d < 0 || i + d >= ids.length} className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs"
                    onClick={() => cambiar((c) => {
                      const jer = c.priorizacion.jerarquia
                      ;[jer[i], jer[i + d]] = [jer[i + d], jer[i]]
                    })}>{d < 0 ? '↑ Subir' : '↓ Bajar'}</button>
                ))}
              </div>
            </li>
          ))}
        </ol>
      </div>
    )
  }

  return (
    <Card>
      <Seccion titulo={`Nuevo experimento · ${laboratorio.nombre}`} sub="Esta copia se guarda y ejecuta sin cambiar la configuración vigente ni tu borrador de edición." />
      <form ref={formulario} onSubmit={(e) => { e.preventDefault(); void guardar(true) }} className="space-y-5">
        <fieldset disabled={ocupado} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo label="Nombre del experimento"><input type="text" required maxLength={200} value={nombre} placeholder="Ej. Más capacidad en WhatsApp" onChange={(e) => setNombre(e.target.value)} /></Campo>
            <Campo label="Objetivo de la prueba"><input type="text" maxLength={2000} value={objetivo} placeholder="¿Qué quieres comprobar?" onChange={(e) => setObjetivo(e.target.value)} /></Campo>
          </div>
          {inicial.tipo === 'libre'
            ? <Tabs pestanas={LABORATORIOS.slice(0, 3).map((l) => l.nombre)}>{controles}</Tabs>
            : controles(laboratorio.nombre)}
        </fieldset>
        {fallo && <Banner tono="error">{fallo.message}{fallo.detalle?.length > 0 && <ListaErrores errores={fallo.detalle} />}</Banner>}
        <div className="flex flex-wrap gap-2">
          <Boton primario disabled={ocupado || !nombre.trim()} onClick={() => void guardar(true)}>{ocupado ? 'Guardando…' : 'Guardar y ejecutar prueba'}</Boton>
          <Boton disabled={ocupado || !nombre.trim()} onClick={() => void guardar(false)}>Guardar sin ejecutar</Boton>
          <Boton disabled={ocupado} onClick={cerrar}>Cancelar</Boton>
        </div>
      </form>
    </Card>
  )
}
