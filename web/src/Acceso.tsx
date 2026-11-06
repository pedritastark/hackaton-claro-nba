import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { AccesoCtx, type Sesion } from './acceso'
import { api, ApiError, establecerCSRF } from './lib'
import { Banner, Boton, Campo, Cargando } from './ui'

export function Acceso({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const generacion = useRef(0)
  const actualizar = useCallback((s: Sesion) => { generacion.current++; establecerCSRF(s.csrf_token); setSesion(s) }, [])
  const refrescar = useCallback(async () => {
    const turno = generacion.current
    try {
      const s = await api<Sesion>('/api/auth/sesion')
      if (turno === generacion.current) { actualizar(s); setFallo(null) }
    } catch (e) { if (turno === generacion.current) setFallo((e as Error).message) }
  }, [actualizar])
  useEffect(() => {
    let vivo = true
    void api<Sesion>('/api/auth/sesion').then((s) => { if (vivo) actualizar(s) }).catch((e) => { if (vivo) setFallo((e as Error).message) })
    const renovar = () => { void refrescar() }
    window.addEventListener('focus', renovar)
    window.addEventListener('nba:sesion-caducada', renovar)
    const timer = setInterval(renovar, 60000)
    return () => {
      vivo = false
      window.removeEventListener('focus', renovar)
      window.removeEventListener('nba:sesion-caducada', renovar)
      clearInterval(timer)
    }
  }, [refrescar, actualizar])
  const cerrar = async () => {
    try { await api('/api/auth/salir', { method: 'POST' }) }
    catch (e) {
      if (!(e instanceof ApiError && e.codigo === 401)) { setFallo((e as Error).message); return }
    }
    actualizar({ usuario: null, csrf_token: null, requiere_configuracion: false })
  }
  if (!sesion) return <div className="mx-auto max-w-lg p-6">{fallo ? <><Banner tono="error">{fallo}</Banner><Boton onClick={() => void refrescar()}>Reintentar conexión</Boton></> : <Cargando texto="Comprobando acceso…" />}</div>
  if (!sesion.usuario) return <FormularioAcceso configurar={sesion.requiere_configuracion} completar={actualizar} />
  const usuario = sesion.usuario
  return <AccesoCtx.Provider value={{ usuario, puede: (permiso) => usuario.permisos.includes(permiso), cerrar, refrescar }}>
    {fallo && <Banner tono="error">{fallo}</Banner>}
    <div key={sesion.csrf_token} className="h-full">{children}</div>
  </AccesoCtx.Provider>
}

function FormularioAcceso({ configurar, completar }: { configurar: boolean; completar: (s: Sesion) => void }) {
  const [ocupado, setOcupado] = useState(false)
  const [fallo, setFallo] = useState<string | null>(null)
  const enviar = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setOcupado(true); setFallo(null)
    const campos = new FormData(e.currentTarget)
    const body = Object.fromEntries(campos.entries())
    try { completar(await api<Sesion>(configurar ? '/api/auth/configurar' : '/api/auth/entrar', { body })) }
    catch (err) { setFallo((err as Error).message) }
    finally { setOcupado(false) }
  }
  return <main className="flex min-h-full items-center justify-center bg-slate-50 p-5">
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7">
      <div className="text-sm text-slate-500">Orquestador NBA</div>
      <h1 className="mb-2 mt-2 text-2xl font-semibold">{configurar ? 'Crea el primer administrador' : 'Inicia sesión'}</h1>
      <p className="mb-6 text-sm text-slate-500">{configurar ? 'La clave de instalación está en poder del operador del servidor. Elige tus datos de acceso.' : 'Ingresa con la cuenta que te asignó el administrador.'}</p>
      <form onSubmit={(e) => void enviar(e)} className="space-y-4">
        <fieldset disabled={ocupado} className="space-y-4">
          {configurar && <>
            <Campo label="Clave de instalación"><input type="password" name="token" required autoComplete="off" maxLength={256} /></Campo>
            <Campo label="Nombre"><input type="text" name="nombre" required maxLength={120} autoComplete="name" /></Campo>
          </>}
          <Campo label="Correo"><input type="email" name="correo" required maxLength={254} autoComplete="username" /></Campo>
          <Campo label="Contraseña"><input type="password" name="clave" required minLength={configurar ? 15 : undefined} maxLength={256} autoComplete={configurar ? 'new-password' : 'current-password'} /></Campo>
          {configurar && <p className="text-xs text-slate-500">Usa una contraseña de al menos 15 caracteres.</p>}
        </fieldset>
        {fallo && <Banner tono="error">{fallo}</Banner>}
        <button type="submit" disabled={ocupado} className="w-full rounded-lg bg-black px-5 py-3 text-sm font-medium text-white">{ocupado ? 'Comprobando…' : configurar ? 'Crear administrador' : 'Entrar'}</button>
      </form>
      {!configurar && <p className="mt-5 text-xs text-slate-500">Si olvidaste tu contraseña, pide al administrador que la restablezca.</p>}
    </div>
  </main>
}
