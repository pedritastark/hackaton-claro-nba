import { useState } from 'react'
import { useSesion } from '../acceso'
import { api, n } from '../lib'
import { useApp, useDatos } from '../store'
import type { Config, Version } from '../types'
import { Banner, Boton, Card, Cargando, Titulo } from '../ui'

export function Versiones() {
  const { puede } = useSesion()
  const { cargarComoBorrador } = useApp()
  const { datos, error, cargando } = useDatos<Version[]>('/api/versiones')
  const [fallo, setFallo] = useState<string | null>(null)

  const restaurar = async (v: Version) => {
    try {
      const r = await api<{ config: Config }>(`/api/versiones/${encodeURIComponent(v.version)}`)
      cargarComoBorrador(r.config, 'Versión restaurada como borrador. Calcula su impacto abajo y aplícala si es lo que quieres.', 'Cambiar configuración')
    } catch (e) {
      setFallo((e as Error).message)
    }
  }

  return (
    <div className="space-y-3">
      <Titulo>Historial de versiones</Titulo>
      {cargando && <Cargando texto="Cargando versiones..." />}
      {error && <Banner tono="error">{error.message}</Banner>}
      {fallo && <Banner tono="error">{fallo}</Banner>}
      {datos && datos.length === 0 && <Banner>Aún no se ha aplicado ningún cambio desde la consola.</Banner>}
      {datos?.map((v) => (
        <Card key={v.version}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-semibold">{v.etiqueta}</div>
              <code className="text-xs text-slate-500">{v.version}</code>
            </div>
            <div className="text-sm text-slate-600">
              Valor {n(v.metricas.valor_esperado ?? 0, 1)} · {n(v.metricas.clientes_con_accion ?? 0)} clientes · jerarquía {v.metricas.jerarquia_pct ?? 0} %
            </div>
            {puede('config.editar') && <Boton onClick={() => restaurar(v)}>Restaurar</Boton>}
          </div>
        </Card>
      ))}
      <p className="text-xs text-slate-500">«Restaurar» carga esa versión como borrador: revisa su impacto en «Cambiar configuración» y aplícala.</p>
    </div>
  )
}
