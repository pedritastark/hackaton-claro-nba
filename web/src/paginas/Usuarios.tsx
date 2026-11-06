import { useState, type FormEvent } from 'react'
import { NOMBRES_ROL, useSesion, type Usuario } from '../acceso'
import { api } from '../lib'
import { useDatos } from '../store'
import { Banner, Boton, Campo, Card, Cargando, Tabs, Titulo } from '../ui'

type Rol = { id: string; nombre: string; permisos: string[] }
type Actividad = { id: number; fecha: number; nombre: string; accion: string; recurso: string }
const ACCIONES: Record<string, string> = {
  consultar: 'Consultar resultados', 'config.editar': 'Editar configuración', 'config.aplicar': 'Aplicar configuración',
  'laboratorios.gestionar': 'Guardar, duplicar y eliminar pruebas', 'laboratorios.ejecutar': 'Ejecutar pruebas',
  'base.gestionar': 'Cambiar datos y recuperar configuración', 'usuarios.gestionar': 'Administrar usuarios', 'parrilla.exportar': 'Exportar parrilla',
}

export function Usuarios() {
  const { usuario, refrescar: refrescarSesion } = useSesion()
  const { datos, error, recargar } = useDatos<Usuario[]>('/api/usuarios')
  const { datos: roles } = useDatos<Rol[]>('/api/usuarios/roles')
  const { datos: actividad, recargar: refrescarActividad } = useDatos<Actividad[]>('/api/usuarios/actividad')
  const [fallo, setFallo] = useState<string | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const ejecutar = async (f: () => Promise<unknown>, mensaje: string) => {
    if (ocupado) return false
    setOcupado(true); setFallo(null); setMensaje(null)
    try {
      await f(); await Promise.all([recargar(), refrescarActividad(), refrescarSesion()]); setMensaje(mensaje); return true
    } catch (e) { setFallo((e as Error).message); return false }
    finally { setOcupado(false) }
  }
  const crear = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const form = e.currentTarget
    const body = Object.fromEntries(new FormData(form).entries())
    if (await ejecutar(() => api('/api/usuarios', { body }), 'Usuario creado. Ya puede iniciar sesión con su correo y contraseña.')) form.reset()
  }
  if (error) return <Banner tono="error">{error.message}</Banner>
  if (!datos || !roles) return <Cargando texto="Cargando usuarios y permisos…" />
  return <div className="space-y-5">
    <Titulo sub="Asigna el acceso de cada persona y revisa las operaciones de la consola.">Usuarios y permisos</Titulo>
    {fallo && <Banner tono="error">{fallo}</Banner>}
    {mensaje && <Banner tono="ok">{mensaje}</Banner>}
    <Tabs pestanas={['Usuarios', 'Permisos por rol', 'Actividad reciente']}>
      {(p) => p === 'Usuarios' ? <div className="space-y-4">
        <Card>
          <h2 className="mb-4 font-semibold">Crear usuario</h2>
          <form onSubmit={(e) => void crear(e)} className="space-y-4">
            <fieldset disabled={ocupado} className="grid gap-4 sm:grid-cols-2">
              <Campo label="Nombre del nuevo usuario"><input type="text" name="nombre" required maxLength={120} autoComplete="off" /></Campo>
              <Campo label="Correo del nuevo usuario"><input type="email" name="correo" required maxLength={254} autoComplete="off" /></Campo>
              <Campo label="Contraseña inicial"><input type="password" name="clave" required minLength={15} maxLength={256} autoComplete="new-password" /></Campo>
              <Campo label="Rol del nuevo usuario"><select aria-label="Rol del nuevo usuario" name="rol" defaultValue="consulta">{roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}</select></Campo>
            </fieldset>
            <p className="text-xs text-slate-500">La contraseña debe tener al menos 15 caracteres. Cada persona puede cambiarla desde Mi cuenta.</p>
            <button type="submit" disabled={ocupado} className="rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white">Crear usuario</button>
          </form>
        </Card>
        {datos.map((u) => <Editar key={`${u.id}-${u.rol}-${u.activo}-${u.nombre}`} u={u} propio={u.id === usuario.id} roles={roles} ocupado={ocupado} ejecutar={ejecutar} />)}
      </div> : p === 'Permisos por rol' ? <Card>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr><th className="p-3 text-left">Acción</th>{roles.map((r) => <th key={r.id} className="p-3 text-left">{r.nombre}</th>)}</tr></thead>
          <tbody>{Object.entries(ACCIONES).map(([k, nombre]) => <tr key={k} className="border-t border-slate-100"><th className="p-3 text-left font-medium">{nombre}</th>{roles.map((r) => <td key={r.id} className="p-3">{r.permisos.includes(k) ? 'Sí' : 'No'}</td>)}</tr>)}</tbody>
        </table></div>
      </Card> : <Card>
        <div className="mb-4"><Boton pequeno onClick={() => void refrescarActividad()}>Actualizar actividad</Boton></div>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr>{['Fecha', 'Persona', 'Acción', 'Recurso'].map((t) => <th key={t} className="p-2 text-left">{t}</th>)}</tr></thead>
          <tbody>{actividad?.map((a) => <tr key={a.id} className="border-t border-slate-100"><td className="p-2">{new Date(a.fecha * 1000).toLocaleString('es-CO')}</td><td className="p-2">{a.nombre}</td><td className="p-2">{a.accion.replaceAll('_', ' ')}</td><td className="break-all p-2 text-xs text-slate-500">{a.recurso || '—'}</td></tr>)}</tbody>
        </table></div>
        <p className="mt-4 text-xs text-slate-500">Últimas 100 operaciones. Las contraseñas y claves de sesión no se registran aquí.</p>
      </Card>}
    </Tabs>
  </div>
}

function Editar({ u, propio, roles, ocupado, ejecutar }: {
  u: Usuario; propio: boolean; roles: Rol[]; ocupado: boolean
  ejecutar: (f: () => Promise<unknown>, mensaje: string) => Promise<boolean>
}) {
  const [nombre, setNombre] = useState(u.nombre)
  const [rol, setRol] = useState(u.rol)
  const [activo, setActivo] = useState(u.activo)
  const [reset, setReset] = useState(false)
  const guardar = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    void ejecutar(() => api(`/api/usuarios/${u.id}`, { method: 'PATCH', body: { nombre, rol, activo } }), 'Usuario actualizado. Los cambios de rol o estado cierran sus sesiones abiertas.')
  }
  return <Card>
    <h2 className="font-semibold">{u.nombre}{propio ? ' · Tu cuenta' : ''}</h2>
    <p className="mb-4 text-sm text-slate-500">{u.correo} · {NOMBRES_ROL[u.rol]} · {u.activo ? 'Activo' : 'Desactivado'}</p>
    <form onSubmit={guardar} className="space-y-4" aria-label={`Editar ${u.correo}`}>
      <fieldset disabled={ocupado} className="grid items-end gap-4 sm:grid-cols-3">
        <Campo label="Nombre del usuario"><input type="text" required maxLength={120} value={nombre} onChange={(e) => setNombre(e.target.value)} /></Campo>
        <Campo label="Rol"><select aria-label="Rol" value={rol} disabled={propio} onChange={(e) => setRol(e.target.value)}>{roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}</select></Campo>
        <label className="flex items-center gap-2 py-2 text-sm"><input type="checkbox" checked={activo} disabled={propio} onChange={(e) => setActivo(e.target.checked)} />Cuenta activa</label>
      </fieldset>
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={ocupado} className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium">Guardar usuario</button>
        {!propio && <Boton disabled={ocupado} onClick={() => setReset((v) => !v)}>{reset ? 'Cancelar contraseña' : 'Restablecer contraseña'}</Boton>}
      </div>
    </form>
    {reset && <form className="mt-4 space-y-3" onSubmit={async (e) => {
      e.preventDefault()
      const nueva = String(new FormData(e.currentTarget).get('nueva'))
      if (await ejecutar(() => api(`/api/usuarios/${u.id}/clave`, { body: { nueva } }), 'Contraseña restablecida. Se cerraron todas las sesiones de esa cuenta.')) setReset(false)
    }}>
      <Campo label={`Nueva contraseña para ${u.correo}`}><input type="password" name="nueva" required minLength={15} maxLength={256} autoComplete="new-password" /></Campo>
      <button type="submit" disabled={ocupado} className="rounded-lg bg-black px-4 py-2 text-sm text-white">Confirmar nueva contraseña</button>
    </form>}
  </Card>
}
