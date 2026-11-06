import { useState } from 'react'
import { useSesion } from '../acceso'
import { api, n } from '../lib'
import { useApp, useDatos } from '../store'
import type { InfoBase } from '../types'
import { Banner, Boton, Campo, Card, Cargando, Metric, Seccion, Tabs, TablaLectura, Titulo } from '../ui'

export function Base() {
  const { puede } = useSesion()
  const { recargar } = useApp()
  const { datos: b, cargando, error } = useDatos<InfoBase>('/api/base')
  const [ruta, setRuta] = useState('')
  const [sel, setSel] = useState('')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const ejecutar = async (f: () => Promise<unknown>) => {
    setFallo(null)
    setOcupado(true)
    try { await f(); await recargar('Base de datos actualizada.') } catch (e) { setFallo((e as Error).message) } finally { setOcupado(false) }
  }

  if (error) return <Banner tono="error">{error.message}</Banner>
  if (cargando || !b) return <Cargando texto="Leyendo la base..." />
  const elegido = sel || b.disponibles[0] || ''

  return (
    <div className="space-y-4">
      <Titulo sub="Elige de dónde se leen los clientes. Cualquier columna de la base puede usarse en las reglas.">Base de datos</Titulo>
      <p className="text-sm"><b>Archivo activo:</b> <code>{b.ruta}</code></p>
      {!b.existe && <Banner tono="error">El archivo activo no existe. Elige otro.</Banner>}
      {fallo && <Banner tono="error">{fallo}</Banner>}

      {puede('base.gestionar') && <Card>
        <Tabs pestanas={['Elegir un archivo', 'Escribir una ruta', 'Subir un archivo']}>
          {(p) => p === 'Elegir un archivo' ? (
            b.disponibles.length ? (
              <div className="flex items-end gap-3">
                <div className="flex-1"><Campo label="Archivos CSV disponibles en data/">
                  <select value={elegido} onChange={(e) => setSel(e.target.value)}>{b.disponibles.map((d) => <option key={d}>{d}</option>)}</select>
                </Campo></div>
                <Boton primario disabled={ocupado} onClick={() => ejecutar(() => api('/api/base/ruta', { body: { ruta: elegido } }))}>Usar este archivo</Boton>
              </div>
            ) : <Banner>No hay archivos CSV en la carpeta data/.</Banner>
          ) : p === 'Escribir una ruta' ? (
            <div className="flex items-end gap-3">
              <div className="flex-1"><Campo label="Ruta del CSV"><input type="text" value={ruta} placeholder={b.ruta} onChange={(e) => setRuta(e.target.value)} /></Campo></div>
              <Boton primario disabled={ocupado || !ruta} onClick={() => ejecutar(() => api('/api/base/ruta', { body: { ruta } }))}>Usar esta ruta</Boton>
            </div>
          ) : (
            <div className="flex items-end gap-3">
              <div className="flex-1"><Campo label="Sube una base (puede traer columnas nuevas)">
                <input type="file" accept=".csv" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
              </Campo></div>
              <Boton primario disabled={ocupado || !archivo} onClick={() => ejecutar(() => { const f = new FormData(); f.append('archivo', archivo as File); return api('/api/base/subir', { form: f }) })}>Cargar y usar</Boton>
            </div>
          )}
        </Tabs>
      </Card>}

      {b.existe && b.perfil && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Metric label="Clientes" valor={n(b.filas ?? 0)} />
            <Metric label="Columnas" valor={String(b.columnas)} />
            <Metric label="Id únicos" valor={b.ids_unicos ? 'sí' : 'no'} />
          </div>
          {b.faltan?.length
            ? <Banner tono="error">Faltan columnas que la configuración vigente necesita: {b.faltan.join(', ')}</Banner>
            : <Banner tono="ok">La base trae todas las columnas que usa la configuración vigente.</Banner>}
          {b.calidad && (
            <Card>
              <Seccion titulo="Calidad de los datos" sub="Chequeos que importan al motor" />
              <ul className="divide-y divide-slate-100">
                {b.calidad.map((c) => (
                  <li key={c.titulo} className="flex items-start gap-3 py-2.5 text-sm">
                    <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${c.ok ? 'bg-bueno' : 'bg-critico'}`} aria-label={c.ok ? 'Correcto' : 'Con problemas'}>{c.ok ? '✓' : '!'}</span>
                    <span><b>{c.titulo}.</b> <span className="text-slate-600">{c.detalle}</span></span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <Seccion titulo="Vista previa" sub="Primeras 50 filas" />
            <div className="max-h-72 overflow-auto text-xs">
              <TablaLectura columnas={Object.keys(b.vista_previa?.[0] ?? {})} filas={(b.vista_previa ?? []).map((f) => Object.values(f).map((v) => (v === null ? '' : String(v))))} />
            </div>
          </Card>
          <Card>
            <Seccion titulo="Columnas" />
            <div className="max-h-80 overflow-auto">
              <TablaLectura columnas={['columna', 'tipo', 'vacíos', 'mínimo', 'máximo', 'usada en la configuración']}
                filas={b.perfil.map((p) => [p.columna, p.tipo, p.vacios, p.min === null ? '' : n(p.min, p.min % 1 ? 3 : 0), p.max === null ? '' : n(p.max, p.max % 1 ? 3 : 0), p.usada ? 'sí' : ''])} />
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
