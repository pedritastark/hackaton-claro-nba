import { useState } from 'react'
import { Base } from './paginas/Base'
import { Cambiar } from './paginas/Cambiar'
import { Cliente } from './paginas/Cliente'
import { Escenarios } from './paginas/Escenarios'
import { Resumen } from './paginas/Resumen'
import { Tablero } from './paginas/Tablero'
import { Versiones } from './paginas/Versiones'
import { PAGINAS, Proveedor, useApp } from './store'
import { api, n } from './lib'
import { Banner, Boton, Cargando, ListaErrores, Titulo } from './ui'

function BarraLateral() {
  const { pagina, irA, estado, vigente } = useApp()
  return (
    <aside className="flex w-full shrink-0 flex-col bg-black p-4 text-slate-300 md:h-full md:w-64 md:p-5 print:hidden">
      <div className="mb-3 mt-1 md:mb-8">
        <div className="text-[1.35rem] font-semibold tracking-tight text-white">Orquestador NBA</div>
        <div className="mt-1 text-xs text-slate-400">Next Best Action configurable</div>
      </div>
      <div className="mb-2 ml-3 hidden text-[0.68rem] font-medium uppercase tracking-[1.4px] text-slate-500 md:block">Navegación</div>
      <nav className="flex gap-0.5 overflow-x-auto md:flex-col">
        {PAGINAS.map((p) => (
          <button key={p} onClick={() => irA(p)} aria-current={p === pagina ? 'page' : undefined}
            className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-2.5 text-left text-sm transition ${
              p === pagina ? 'bg-white font-semibold text-black' : 'text-slate-300 hover:bg-slate-800 hover:text-white'}`}>
            {p}
          </button>
        ))}
      </nav>
      <div className="mb-2 ml-3 mt-auto hidden text-[0.68rem] font-medium uppercase tracking-[1.4px] text-slate-500 md:block">Estado</div>
      <div className="hidden rounded-xl border border-slate-800 p-3.5 text-[0.8rem] leading-relaxed md:block">
        {estado?.base.existe ? (
          <>
            <span className="text-[#3ddc84]">●</span> <b className="text-white">Base activa</b><br />
            {estado.base.nombre}<br />{n(estado.base.filas)} clientes<br />
            <b className="text-white">Configuración</b><br />{vigente ? estado.configuracion : 'no válida'}
          </>
        ) : (
          <><b className="text-white">Sin base de datos</b><br />Elige una en «Base de datos».</>
        )}
      </div>
    </aside>
  )
}

function ConfiguracionInvalida() {
  const { errorInicial, recargar } = useApp()
  const [trabajando, setTrabajando] = useState(false)
  const [fallo, setFallo] = useState<string | null>(null)
  const restaurar = async () => {
    setTrabajando(true)
    try {
      await api('/api/config/restaurar-inicial', { method: 'POST' })
      await recargar('Configuración inicial restaurada.')
    } catch (e) {
      setFallo((e as Error).message)
    } finally {
      setTrabajando(false)
    }
  }
  return (
    <div className="mx-auto max-w-3xl">
      <Titulo>La configuración guardada no es válida</Titulo>
      <Banner tono="error">
        La consola no puede abrir la configuración vigente porque algún valor no cumple las reglas del reto.
        <div className="mt-2 font-semibold">Qué falla:</div>
        <ListaErrores errores={errorInicial?.detalle ?? [{ campo: 'API', mensaje: errorInicial?.mensaje ?? '' }]} />
      </Banner>
      <p className="my-3 text-sm text-slate-600">
        Puedes <b>restaurar la configuración inicial del reto</b>. Antes de reemplazarla, la actual se guarda como respaldo en la carpeta <code>respaldo/</code>.
      </p>
      <Boton primario onClick={restaurar} disabled={trabajando}>Restaurar la configuración inicial</Boton>
      {fallo && <Banner tono="error">{fallo}</Banner>}
    </div>
  )
}

function Contenido() {
  const { pagina, vigente, errorInicial, mensaje, estado } = useApp()
  if (errorInicial) return <ConfiguracionInvalida />
  if (!estado || !vigente) return <Cargando texto="Conectando con el motor..." />
  return (
    <>
      {mensaje && <Banner tono="ok">{mensaje}</Banner>}
      {pagina === 'Resumen' && <Resumen />}
      {pagina === 'Tablero' && <Tablero />}
      {pagina === 'Cambiar configuración' && <Cambiar />}
      {pagina === 'Laboratorios' && <Escenarios />}
      {pagina === 'Cliente' && <Cliente />}
      {pagina === 'Base de datos' && <Base />}
      {pagina === 'Versiones' && <Versiones />}
    </>
  )
}

export default function App() {
  return (
    <Proveedor>
      <div className="flex h-full flex-col md:flex-row print:block print:h-auto">
        <BarraLateral />
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto px-4 py-6 md:h-full md:px-10 md:py-9 print:h-auto print:overflow-visible print:p-0"><div className="mx-auto max-w-6xl"><Contenido /></div></main>
      </div>
    </Proveedor>
  )
}
