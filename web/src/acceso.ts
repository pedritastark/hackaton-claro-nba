import { createContext, useContext } from 'react'

export type Usuario = { id: string; nombre: string; correo: string; rol: string; activo: boolean; creado: number; permisos: string[] }
export type Sesion = { usuario: Usuario | null; csrf_token: string | null; requiere_configuracion: boolean }
export const NOMBRES_ROL: Record<string, string> = {
  administrador: 'Administrador', editor: 'Editor', analista: 'Analista de pruebas', consulta: 'Consulta',
}
export const AccesoCtx = createContext<{
  usuario: Usuario; puede: (permiso: string) => boolean; cerrar: () => Promise<void>; refrescar: () => Promise<void>
} | null>(null)
export function useSesion() {
  const contexto = useContext(AccesoCtx)
  if (!contexto) throw new Error('useSesion fuera de Acceso')
  return contexto
}
