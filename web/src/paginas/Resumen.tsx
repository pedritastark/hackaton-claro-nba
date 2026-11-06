import { Chip, Numero } from '../graficos'
import { delta, n, nombreCanal, signo } from '../lib'
import { useApp, useDatos } from '../store'
import type { Tablero } from '../types'
import { Banner, Boton, Card, Esqueleto } from '../ui'

type Hallazgo = { cifra: string; texto: string }

// Frases generadas de los datos de la corrida: nada de esto esta escrito a mano.
function hallazgos(t: Tablero): Hallazgo[] {
  const out: Hallazgo[] = []
  const totalProd = t.composicion.reduce((s, x) => s + x.productos, 0)
  const porCampana = t.campanas.map((c) => ({ c, v: t.composicion.filter((x) => x.campana === c).reduce((s, x) => s + x.productos, 0) }))
  const lider = porCampana.sort((a, b) => b.v - a.v)[0]
  if (lider && totalProd) out.push({ cifra: `${n((100 * lider.v) / totalProd)} %`, texto: `de los productos asignados son «${lider.c}»` })

  const topCanal = [...t.cupos].sort((a, b) => b.usado - a.usado)[0]
  if (topCanal && t.metricas.clientes_con_accion)
    out.push({ cifra: `${n((100 * topCanal.usado) / t.metricas.clientes_con_accion)} %`, texto: `de los clientes con acción se contactan por ${topCanal.nombre}` })

  let mayor = { perdida: 0, motivo: '' }
  t.embudo.forEach((e, i) => {
    const sig = t.embudo[i + 1]
    if (sig && e.cantidad - sig.cantidad > mayor.perdida) mayor = { perdida: e.cantidad - sig.cantidad, motivo: sig.motivo }
  })
  if (mayor.perdida) out.push({ cifra: n(mayor.perdida), texto: `clientes se pierden en la etapa más exigente: ${mayor.motivo}` })

  const regla = [...t.reglas].sort((a, b) => b.clientes - a.clientes)[0]
  if (regla) out.push({ cifra: n(regla.clientes), texto: `clientes que deja fuera la regla que más excluye: «${regla.regla}»` })

  const mejor = Object.entries(t.precios_sombra).sort((a, b) => b[1] - a[1])[0]
  if (mejor && mejor[1] > 0)
    out.push({ cifra: `+${n(100 * mejor[1], 1)}`, texto: `de valor esperado por cada 100 cupos adicionales de ${nombreCanal(mejor[0])}, el canal más valioso` })
  return out.slice(0, 4)
}

export function Resumen() {
  const { irA } = useApp()
  const { datos: t, error, cargando } = useDatos<Tablero>('/api/tablero')

  if (error) return <Banner tono="error">{error.message}</Banner>
  if (cargando || !t) {
    return (
      <div>
        <div className="esqueleto h-72" />
        <div className="mt-4 grid gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="esqueleto h-28" />)}</div>
        <div className="mt-4"><Esqueleto filas={1} alto="h-40" /></div>
        <p className="mt-3 text-sm text-slate-500">Calculando la parrilla con los 100.000 clientes; la primera vez tarda unos segundos.</p>
      </div>
    )
  }

  const m = t.metricas
  const b = t.baseline
  const ok = t.estado.violaciones_total === 0
  const maxV = Math.max(m.valor_esperado, b.valor_esperado)
  const etapas = t.embudo
  const caso = t.casos[0]

  return (
    <div className="space-y-5">
      {/* Portada */}
      <section className="grid gap-8 rounded-2xl bg-black p-8 text-white md:grid-cols-5">
        <div className="md:col-span-3">
          <div className="text-sm text-slate-400">Valor esperado de la parrilla · {t.estado.configuracion}</div>
          <div className="mt-2 text-[4.25rem] font-semibold leading-none tracking-tight"><Numero valor={m.valor_esperado} dec={1} /></div>
          <div className="mt-3 text-lg font-medium text-[#6fb1ff]">
            {delta(m.valor_esperado, b.valor_esperado)} <span className="font-normal text-slate-300">frente a la línea base del reto</span>
          </div>
          <div className="mt-6 space-y-2.5">
            {([['Motor', m.valor_esperado, '#ffffff'], ['Línea base', b.valor_esperado, '#6b6b6b']] as const).map(([et, v, color]) => (
              <div key={et} className="grid grid-cols-[84px_1fr_72px] items-center gap-3 text-sm">
                <span className="text-slate-300">{et}</span>
                <div className="h-2.5 overflow-hidden rounded-full bg-[#1f1f1f]"><div className="h-full rounded-full" style={{ width: `${(100 * v) / maxV}%`, background: color }} /></div>
                <span className="text-right tabular-nums">{n(v, 1)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-5 md:col-span-2 md:border-l md:border-[#262626] md:pl-8">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-400">Restricciones del reto</div>
            <div className="mt-1 flex items-baseline gap-2 text-3xl font-semibold tracking-tight">
              <span>{n(t.estado.violaciones_total)}</span><span className="text-base font-normal text-slate-300">violaciones</span>
              <span className={`ml-1 text-xl ${ok ? 'text-[#3ddc84]' : 'text-[#ff6b5a]'}`}>{ok ? '✓' : '!'}</span>
            </div>
          </div>
          <div>
            <div className="text-sm text-slate-400">Reparto de cupos</div>
            <div className="mt-1 text-lg font-semibold leading-snug">{t.optimalidad.titulo}</div>
            <p className="mt-1 text-sm leading-relaxed text-slate-400">{t.optimalidad.texto}</p>
          </div>
          <div>
            <div className="text-sm text-slate-400">Clientes con acción</div>
            <div className="mt-1 text-3xl font-semibold tracking-tight"><Numero valor={m.clientes_con_accion} />
              <span className="ml-2 text-base font-normal text-slate-300">de {n(t.total)}</span></div>
          </div>
        </div>
      </section>

      {/* De la base a la parrilla */}
      <section>
        <h2 className="mb-3 text-lg font-semibold tracking-tight">De la base a la parrilla</h2>
        <div className="grid gap-3 md:grid-cols-4">
          {[
            { paso: '1', titulo: 'Base de clientes', cifra: etapas[0].cantidad, nota: 'Todos los clientes de la corrida' },
            { paso: '2', titulo: 'Con campaña elegible', cifra: etapas[2]?.cantidad ?? 0, nota: 'Pasan el tope semanal y las reglas de negocio' },
            { paso: '3', titulo: 'Con canal habilitado', cifra: etapas[3]?.cantidad ?? 0, nota: 'Autorizan un canal y es probable que respondan' },
            { paso: '4', titulo: 'Con acción asignada', cifra: etapas[4]?.cantidad ?? 0, nota: 'Reciben un cupo tras el reparto óptimo' },
          ].map((p, i, a) => (
            <Card key={p.paso} className={i === a.length - 1 ? '!border-black' : ''}>
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Paso {p.paso}</span>{i < a.length - 1 && <span aria-hidden>→</span>}
              </div>
              <div className="mt-1 text-sm font-medium">{p.titulo}</div>
              <div className="mt-2 text-3xl font-semibold tracking-tight"><Numero valor={p.cifra} /></div>
              <div className="mt-1 text-xs text-slate-500">{p.nota}</div>
            </Card>
          ))}
        </div>
      </section>

      {/* Hallazgos */}
      <section>
        <h2 className="mb-3 text-lg font-semibold tracking-tight">Lo que dicen los datos</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {hallazgos(t).map((h) => (
            <Card key={h.texto}>
              <div className="flex items-start gap-4">
                <div className="min-w-24 text-3xl font-semibold tracking-tight text-dato tabular-nums">{h.cifra}</div>
                <p className="pt-1 text-sm leading-relaxed text-slate-700">{h.texto}</p>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Explicabilidad */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="max-w-xl">
            <div className="flex items-center gap-2"><h2 className="text-lg font-semibold tracking-tight">Cada decisión se explica</h2><Chip>Explicabilidad</Chip></div>
            <p className="mt-1 text-sm text-slate-500">
              Para cada cliente la parrilla guarda por qué se le ofreció algo y por qué se descartó el resto, con la regla exacta que lo decidió.
              {' '}{signo(t.estado.mejora_pct, 1)} % de valor sobre la línea base, sin una sola violación de las restricciones.
            </p>
          </div>
          <div className="flex gap-2 print:hidden">
            {caso && <Boton primario onClick={() => irA('Cliente', caso.id)}>Ver una decisión explicada</Boton>}
            <Boton onClick={() => irA('Tablero')}>Ir al tablero</Boton>
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap gap-2 pb-2 print:hidden">
        <a href="/api/parrilla.csv" download="parrilla.csv" className="rounded-lg bg-slate-100 px-5 py-2.5 text-sm font-medium text-black hover:bg-slate-200">Descargar parrilla.csv</a>
        <Boton onClick={() => window.print()}>Imprimir o guardar como PDF</Boton>
      </div>
    </div>
  )
}
