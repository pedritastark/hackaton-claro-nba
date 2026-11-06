import { useState, type FormEvent } from 'react'
import { NOMBRES_ROL, useSesion } from '../acceso'
import { api } from '../lib'
import { Banner, Campo, Card, Titulo } from '../ui'

export function Cuenta() {
  const { usuario, refrescar } = useSesion()
  const [fallo, setFallo] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const enviar = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setFallo(null)
    const campos = new FormData(e.currentTarget)
    if (campos.get('nueva') !== campos.get('confirmar')) { setFallo('Las contraseñas nuevas no coinciden.'); return }
    setOcupado(true)
    try {
      await api('/api/auth/clave', { body: { actual: campos.get('actual'), nueva: campos.get('nueva') } })
      await refrescar()
    } catch (err) { setFallo((err as Error).message); setOcupado(false) }
  }
  return <div className="max-w-xl space-y-5">
    <Titulo sub={`${usuario.correo} · ${NOMBRES_ROL[usuario.rol]}`}>Mi cuenta</Titulo>
    <Card>
      <h2 className="mb-4 font-semibold">Cambiar contraseña</h2>
      <form className="space-y-4" onSubmit={(e) => void enviar(e)}>
        <fieldset disabled={ocupado} className="space-y-4">
          <Campo label="Contraseña actual"><input type="password" name="actual" required maxLength={256} autoComplete="current-password" /></Campo>
          <Campo label="Nueva contraseña"><input type="password" name="nueva" required minLength={15} maxLength={256} autoComplete="new-password" /></Campo>
          <Campo label="Confirma la nueva contraseña"><input type="password" name="confirmar" required minLength={15} maxLength={256} autoComplete="new-password" /></Campo>
        </fieldset>
        <p className="text-sm text-slate-500">Usa al menos 15 caracteres. Al cambiarla se cierran todas tus sesiones y tendrás que volver a entrar.</p>
        {fallo && <Banner tono="error">{fallo}</Banner>}
        <button type="submit" disabled={ocupado} className="rounded-lg bg-black px-5 py-2.5 text-sm text-white">Cambiar contraseña</button>
      </form>
    </Card>
  </div>
}
