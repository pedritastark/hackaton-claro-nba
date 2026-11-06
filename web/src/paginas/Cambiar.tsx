import { useMemo, useState } from 'react'
import { api, ApiError, lista, n, nombreCanal, signo, textoAValor, valorATexto } from '../lib'
import { BarrasDivergentes } from '../graficos'
import { useApp, useDatos } from '../store'
import type { Campana, Canal, Config, Derivados, Impacto, Regla, Tablero as TableroT } from '../types'
import {
  Banner, Boton, Campo, Card, Cargando, Deslizador, ListaErrores, Metric, Plegable, Seccion, TablaEditable, TablaLectura, Tabs, Titulo,
  type Col,
} from '../ui'

const ALCANCES = ['global', 'campana', 'producto', 'objetivo', 'canal']
const clonar = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T

// ---------------------------------------------------------------- estimacion instantanea con precios sombra
type Estimacion =
  | { tipo: 'ninguno' }
  | { tipo: 'otros' }
  | { tipo: 'cupos'; dv: number; pct: number; detalle: { canal: string; d: number; v: number }[]; grande: boolean; sinEstimar: string | null }

// Solo hay estimacion rapida cuando UNICAMENTE cambian cupos: el precio sombra dice cuanto vale un cupo mas.
function estimar(b: Config, vig: Config, t: TableroT | null): Estimacion {
  const copia = clonar(b)
  for (const c of copia.canales) { const v = vig.canales.find((x) => x.id === c.id); if (v) c.cupo = v.cupo }
  if (JSON.stringify(copia) !== JSON.stringify(vig)) return { tipo: 'otros' }
  if (!t) return { tipo: 'ninguno' }
  const detalle: { canal: string; d: number; v: number }[] = []
  let sinEstimar: string | null = null
  for (const c of b.canales) {
    const v = vig.canales.find((x) => x.id === c.id)
    if (!v || c.cupo === v.cupo) continue
    const d = c.cupo - v.cupo
    const p = t.precios_sombra[c.id] ?? 0
    const usado = t.cupos.find((x) => x.canal === c.id)?.usado ?? 0
    if (p > 0 || d > 0) detalle.push({ canal: c.id, d, v: d * p })
    else if (c.cupo >= usado) detalle.push({ canal: c.id, d, v: 0 })
    else sinEstimar = nombreCanal(c.id)
  }
  if (!detalle.length && !sinEstimar) return { tipo: 'ninguno' }
  const dv = detalle.reduce((s, x) => s + x.v, 0)
  return { tipo: 'cupos', dv, pct: (100 * dv) / Math.max(1e-9, t.metricas.valor_esperado), detalle,
    grande: detalle.reduce((s, x) => s + Math.abs(x.d), 0) > 1000, sinEstimar }
}

function useEstimacion(b: Config): Estimacion {
  const { vigente } = useApp()
  const { datos: t } = useDatos<TableroT>('/api/tablero')
  return useMemo(() => (vigente ? estimar(b, vigente.config, t) : { tipo: 'ninguno' }), [b, vigente, t])
}

function TarjetaEstimacion({ est }: { est: Estimacion }) {
  if (est.tipo === 'ninguno') return null
  if (est.tipo === 'otros') {
    return <Banner>Este cambio no tiene estimación instantánea. Calcula el impacto exacto: tarda unos segundos.</Banner>
  }
  if (est.sinEstimar) {
    return <Banner tono="aviso">Reducir el cupo de {est.sinEstimar} por debajo de lo que usa hoy quita clientes de la parrilla. Calcula el impacto exacto para ver cuánto.</Banner>
  }
  const nulo = est.dv === 0
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Estimación instantánea</div>
          <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
            {nulo ? 'Sin cambio en el valor esperado' : <>≈ {signo(est.dv, 1)} <span className="text-base font-normal text-slate-500">de valor esperado ({signo(est.pct, 2)} %)</span></>}
          </div>
        </div>
        <div className="text-sm text-slate-600">
          {est.detalle.map((x) => <div key={x.canal}>{nombreCanal(x.canal)} {signo(x.d, 0)} cupos</div>)}
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {nulo ? 'Esos canales no están llenos: más cupo no cambia nada. ' : 'Se calcula con el precio sombra de cada cupo. '}
        {est.grande ? <b className="text-[#6b4a00]">Cambio grande: la estimación suele sobreestimar. </b> : 'Fiable para cambios de unos cientos de cupos. '}
        Confírmala con el cálculo exacto.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- pestanas de edicion
function Umbrales({ b, act, der, columnas }: Ctx) {
  const llamadas = async (valor: number) => {
    const r = await api<{ config: Config }>('/api/borrador/llamadas', { body: { config: b, valor } })
    act(() => r.config)
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-5 md:grid-cols-3">
        <Deslizador label="Probabilidad mínima de compra de un producto" valor={b.priorizacion.umbral_score_producto} min={0} max={1} paso={0.01}
          onChange={(v) => act((c) => { c.priorizacion.umbral_score_producto = v })} />
        <Deslizador label="Probabilidad mínima de respuesta de un canal" valor={b.asignacion.umbral_score_canal} min={0} max={1} paso={0.01}
          onChange={(v) => act((c) => { c.asignacion.umbral_score_canal = v })} />
        <Campo label="Máximo de contactos por semana">
          <input type="number" min={1} max={20} value={b.politica_contacto.max_contactos_semana}
            onChange={(e) => act((c) => { c.politica_contacto.max_contactos_semana = Number(e.target.value) })} />
        </Campo>
      </div>
      {der.tope_llamadas !== null ? (
        <div className="max-w-md">
          <Campo label="Llamar por asesor solo a clientes con menos de … llamadas de asesor en el mes"
            ayuda="Con 2, un cliente que ya recibió 2 llamadas este mes no vuelve a recibir una">
            <input type="number" min={0} max={30} value={der.tope_llamadas} onChange={(e) => void llamadas(Number(e.target.value))} />
          </Campo>
        </div>
      ) : <Banner>No hay una regla de tope de llamadas de asesor en la configuración; créala en la pestaña <b>Reglas</b>.</Banner>}
      <p className="text-xs text-slate-500">La base tiene {columnas.length} columnas disponibles para las reglas.</p>
    </div>
  )
}

function Prioridad({ b, act }: Ctx) {
  const p = b.priorizacion
  const [raw, setRaw] = useState(p.pesos)
  const suma = (x: typeof raw) => x.score_producto + x.valor_negocio + x.jerarquia
  const norm = (x: typeof raw) => { const s = suma(x); return { score_producto: x.score_producto / s, valor_negocio: x.valor_negocio / s, jerarquia: x.jerarquia / s } }
  const ceros = { score_producto: 0, valor_negocio: 0, jerarquia: 0 }
  const coincide = suma(raw) > 0
    ? Object.entries(norm(raw)).every(([k, v]) => Math.abs(v - p.pesos[k as keyof typeof p.pesos]) < 1e-9)
    : suma(p.pesos) === 0
  const mostrados = coincide ? raw : p.pesos
  const cambiarPeso = (k: keyof typeof raw, v: number) => {
    const nuevo = { ...mostrados, [k]: v }
    setRaw(nuevo)
    // con todos en cero el borrador queda invalido a proposito: la API explica el error y la vista previa se bloquea
    act((c) => { c.priorizacion.pesos = suma(nuevo) > 0 ? norm(nuevo) : ceros })
  }
  return (
    <div className="space-y-5">
      <div>
        <h4 className="mb-2 font-semibold">Balance entre valor esperado y jerarquía de negocio</h4>
        <Deslizador label="α · 0 = maximizar valor esperado · 1 = priorizar la jerarquía" valor={p.alpha} min={0} max={1} paso={0.05}
          onChange={(v) => act((c) => { c.priorizacion.alpha = v })} />
      </div>
      <div>
        <h4 className="mb-2 font-semibold">Peso del modelo frente al valor de negocio</h4>
        <div className="grid gap-5 md:grid-cols-2">
          <Deslizador label="Peso del modelo (probabilidad de compra)" valor={p.peso_modelo} min={0} max={3} paso={0.1}
            ayuda="Más de 1: se prefiere al producto que el modelo cree más probable, aunque valga menos"
            onChange={(v) => act((c) => { c.priorizacion.peso_modelo = v })} />
          <Deslizador label="Peso del valor de negocio" valor={p.peso_valor} min={0} max={3} paso={0.1}
            ayuda="Más de 1: se prefiere al producto de mayor valor, aunque sea menos probable"
            onChange={(v) => act((c) => { c.priorizacion.peso_valor = v })} />
        </div>
        <p className="mt-2 text-xs text-slate-500">1 y 1 = maximizar el valor esperado (la métrica del reto). Cualquier otro valor inclina la decisión y suele costar algo de valor esperado; la vista previa muestra cuánto. Rige para el algoritmo óptimo.</p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Campo label="Algoritmo de reparto de cupos" ayuda="óptimo: reparte los cupos con visión global; codicioso: el baseline del reto">
          <select value={b.asignacion.algoritmo} onChange={(e) => act((c) => { c.asignacion.algoritmo = e.target.value as Config['asignacion']['algoritmo'] })}>
            <option value="optimo">optimo</option><option value="codicioso">codicioso</option>
          </select>
        </Campo>
        <Campo label="Criterios de desempate entre campañas (en orden, separados por |)" ayuda="Válidos: score_producto, valor_negocio, jerarquia">
          <input type="text" value={p.desempate.join('|')} onChange={(e) => act((c) => { c.priorizacion.desempate = lista(e.target.value) })} />
        </Campo>
      </div>
      <Plegable titulo="Parámetros del baseline (suma ponderada)">
        <div className="mb-3 max-w-xs">
          <Campo label="Modo">
            <select value={p.modo} onChange={(e) => act((c) => { c.priorizacion.modo = e.target.value as Config['priorizacion']['modo'] })}>
              <option value="ponderado">ponderado</option><option value="jerarquia_estricta">jerarquia_estricta</option>
            </select>
          </Campo>
        </div>
        <p className="mb-2 text-xs text-slate-500">Los tres pesos se normalizan para que sumen 1.</p>
        <div className="grid gap-4 md:grid-cols-3">
          {([['score_producto', 'Peso score del producto'], ['valor_negocio', 'Peso valor de negocio'], ['jerarquia', 'Peso jerarquía']] as const).map(([k, et]) => (
            <Campo key={k} label={et}><input type="number" min={0} max={1} step={0.05} value={Number(mostrados[k].toFixed(4))} onChange={(e) => cambiarPeso(k, Number(e.target.value))} /></Campo>
          ))}
        </div>
        {suma(mostrados) <= 0 && <Banner tono="error">Los pesos no pueden ser todos cero (deben sumar 1).</Banner>}
      </Plegable>
      <p className="text-xs text-slate-500">El orden de la jerarquía se cambia en la pestaña <b>Campañas</b> (flechas de «Prioridad»).</p>
    </div>
  )
}

function Campanas({ b, act, der, columnas }: Ctx) {
  const scores = columnas.filter((c) => c.startsWith('score_'))
  const pos = (id: string) => b.priorizacion.jerarquia.indexOf(id)
  const mover = (id: string, d: number) => act((c) => {
    const j = c.priorizacion.jerarquia
    const i = j.indexOf(id)
    if (i < 0 || i + d < 0 || i + d >= j.length) return
    ;[j[i], j[i + d]] = [j[i + d], j[i]]
  })
  const cambiar = (nuevas: Campana[]) => act((c) => {
    const viejas = c.campanas
    let jer = [...c.priorizacion.jerarquia]
    if (nuevas.length === viejas.length) nuevas.forEach((x, i) => { if (x.id !== viejas[i].id) jer = jer.map((j) => (j === viejas[i].id ? x.id : j)) })
    else if (nuevas.length < viejas.length) jer = jer.filter((j) => nuevas.some((x) => x.id === j))
    else nuevas.forEach((x) => { if (!jer.includes(x.id)) jer.push(x.id) })
    c.campanas = nuevas
    c.priorizacion.jerarquia = jer
  })
  const calif = async (camp: string, o: string, marcada: boolean) => {
    const actuales = der.calificaciones[camp] ?? der.orden_calificaciones
    const permitidas = marcada ? [...actuales, o] : actuales.filter((x) => x !== o)
    const r = await api<{ config: Config }>('/api/borrador/calificaciones', { body: { config: b, campana: camp, permitidas } })
    act(() => r.config)
  }
  const cols: Col<Campana>[] = [
    { etiqueta: 'Activa', tipo: 'check', leer: (f) => f.activa, escribir: (f, v) => ({ ...f, activa: Boolean(v) }) },
    { etiqueta: 'Prioridad', tipo: 'texto', ancho: '90px', leer: (f) => pos(f.id), escribir: (f) => f,
      render: (f) => (
        <span className="flex items-center gap-1">
          <b className="w-5 text-center">{pos(f.id) + 1}</b>
          <button type="button" aria-label="Subir prioridad" className="rounded border border-slate-300 px-1.5 text-xs hover:bg-slate-100" onClick={() => mover(f.id, -1)}>▲</button>
          <button type="button" aria-label="Bajar prioridad" className="rounded border border-slate-300 px-1.5 text-xs hover:bg-slate-100" onClick={() => mover(f.id, 1)}>▼</button>
        </span>) },
    { etiqueta: 'Id', tipo: 'texto', ancho: '90px', leer: (f) => f.id, escribir: (f, v) => ({ ...f, id: String(v) }) },
    { etiqueta: 'Nombre', tipo: 'texto', ancho: '200px', leer: (f) => f.nombre, escribir: (f, v) => ({ ...f, nombre: String(v) }) },
    { etiqueta: 'Producto', tipo: 'texto', ancho: '80px', leer: (f) => f.producto, escribir: (f, v) => ({ ...f, producto: String(v) }) },
    { etiqueta: 'Objetivo', tipo: 'texto', ancho: '120px', leer: (f) => f.objetivo, escribir: (f, v) => ({ ...f, objetivo: String(v) }) },
    { etiqueta: 'Columna de score', tipo: 'seleccion', opciones: scores, ancho: '210px', leer: (f) => f.columna_score, escribir: (f, v) => ({ ...f, columna_score: String(v) }) },
    { etiqueta: 'Valor de negocio', tipo: 'numero', paso: 0.05, min: 0, max: 1, ancho: '90px', leer: (f) => f.valor_negocio, escribir: (f, v) => ({ ...f, valor_negocio: Number(v) }) },
    { etiqueta: 'Canales permitidos (a|b)', tipo: 'lista', ancho: '200px', leer: (f) => f.canales_permitidos.join('|'), escribir: (f, v) => ({ ...f, canales_permitidos: lista(String(v)) }) },
    { etiqueta: 'Vigencia desde', tipo: 'fecha', ancho: '140px', leer: (f) => f.vigencia_inicio ?? '', escribir: (f, v) => ({ ...f, vigencia_inicio: v === '' ? null : String(v) }) },
    { etiqueta: 'Vigencia hasta', tipo: 'fecha', ancho: '140px', leer: (f) => f.vigencia_fin ?? '', escribir: (f, v) => ({ ...f, vigencia_fin: v === '' ? null : String(v) }) },
  ]
  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-500">Agrega una fila para lanzar una campaña nueva; desmarca «activa» para pausarla sin borrarla; usa las flechas para cambiar su prioridad (1 = primera).</p>
      <TablaEditable filas={b.campanas} columnas={cols} onChange={cambiar} textoAgregar="Nueva campaña"
        nueva={() => ({ id: `C-NUEVA${b.campanas.length + 1}`, nombre: 'Campaña nueva', producto: 'NUEVO', objetivo: '', columna_score: scores[0] ?? '', valor_negocio: 0.5,
          canales_permitidos: b.canales.map((c) => c.id), vigencia_inicio: null, vigencia_fin: null, activa: true })} />
      <div>
        <h4 className="font-semibold">Calificación de riesgo permitida por campaña</h4>
        <p className="mb-2 text-sm text-slate-500">Quita las calificaciones a las que NO se debe ofrecer la campaña. Se traduce en una regla de elegibilidad.</p>
        <div className="grid gap-3 md:grid-cols-3">
          {b.campanas.map((c) => (
            <Card key={c.id}>
              <div className="mb-1.5 text-sm font-semibold">{c.id}</div>
              <div className="flex gap-3">
                {der.orden_calificaciones.map((o) => (
                  <label key={o} className="flex items-center gap-1 text-sm">
                    <input type="checkbox" checked={(der.calificaciones[c.id] ?? der.orden_calificaciones).includes(o)} onChange={(e) => void calif(c.id, o, e.target.checked)} />{o}
                  </label>
                ))}
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

function Reglas({ b, act, columnas, operadores }: Ctx) {
  const { datos: tab } = useDatos<TableroT>('/api/tablero')
  const excluye: Record<string, number> = {}
  tab?.reglas.forEach((r) => { excluye[r.codigo] = (excluye[r.codigo] ?? 0) + r.clientes })
  const [form, setForm] = useState({ nombre: 'Terminales solo a clientes sin quejas', tipo: 'elegibilidad', nivel: 'campana', alc: 'C-TER', atr: 'quejas_90d', op: '>=', val: '1' })
  const agregar = () => act((c) => {
    const ids = c.reglas.map((r) => Number(r.id.slice(1))).filter((x) => Number.isFinite(x))
    c.reglas.push({
      id: `R${String(Math.max(0, ...ids) + 1).padStart(2, '0')}`, nombre: form.nombre, tipo: form.tipo as Regla['tipo'], alcance_nivel: form.nivel as Regla['alcance_nivel'],
      alcance_valores: lista(form.alc), atributo: form.atr, operador: form.op, valor: textoAValor(form.val, form.op), accion: 'excluir', activa: true })
  })
  const cols: Col<Regla>[] = [
    { etiqueta: 'Activa', tipo: 'check', leer: (f) => f.activa, escribir: (f, v) => ({ ...f, activa: Boolean(v) }) },
    { etiqueta: 'Id', tipo: 'texto', ancho: '70px', leer: (f) => f.id, escribir: (f, v) => ({ ...f, id: String(v) }) },
    { etiqueta: 'Nombre', tipo: 'texto', ancho: '260px', leer: (f) => f.nombre, escribir: (f, v) => ({ ...f, nombre: String(v) }) },
    { etiqueta: 'Aplica a', tipo: 'seleccion', opciones: ['elegibilidad', 'canal'], ancho: '120px', leer: (f) => f.tipo, escribir: (f, v) => ({ ...f, tipo: v as Regla['tipo'] }) },
    { etiqueta: 'Alcance', tipo: 'seleccion', opciones: ALCANCES, ancho: '110px', leer: (f) => f.alcance_nivel, escribir: (f, v) => ({ ...f, alcance_nivel: v as Regla['alcance_nivel'] }) },
    { etiqueta: 'Afecta a (a|b)', tipo: 'lista', ancho: '120px', leer: (f) => f.alcance_valores.join('|'), escribir: (f, v) => ({ ...f, alcance_valores: lista(String(v)) }) },
    { etiqueta: 'Columna', tipo: 'seleccion', opciones: columnas, ancho: '200px', leer: (f) => f.atributo, escribir: (f, v) => ({ ...f, atributo: String(v) }) },
    { etiqueta: 'Operador', tipo: 'seleccion', opciones: operadores, ancho: '110px', leer: (f) => f.operador,
      escribir: (f, v) => ({ ...f, operador: String(v), valor: textoAValor(valorATexto(f.valor), String(v)) }) },
    { etiqueta: 'Valor', tipo: 'texto', ancho: '110px', leer: (f) => valorATexto(f.valor), escribir: (f, v) => ({ ...f, valor: textoAValor(String(v), f.operador) }) },
    { etiqueta: 'Excluye hoy', tipo: 'texto', ancho: '100px', leer: () => '', escribir: (f) => f,
      render: (f) => <span className="tabular-nums text-slate-600" title="Clientes que esta regla deja fuera de la parrilla actual">{excluye[f.id] ? n(excluye[f.id]) : '–'}</span> },
  ]
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">Cada regla EXCLUYE al cliente cuando su condición se cumple. Para «en»/«no_en» separa los valores con <code>|</code>; <code>$producto</code> hace referencia al producto evaluado.</p>
      <Plegable titulo="Crear una regla nueva (asistente)">
        <div className="grid gap-3 md:grid-cols-2">
          <Campo label="Nombre en lenguaje de negocio"><input type="text" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Campo>
          <Campo label="Aplica a">
            <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}><option value="elegibilidad">elegibilidad (qué productos se ofrecen)</option><option value="canal">canal (por qué canal)</option></select>
          </Campo>
          <Campo label="Alcance" ayuda="campana: por id (C-TER); producto: por código (TER); objetivo: grupo de campañas; canal: (sms)">
            <select value={form.nivel} onChange={(e) => setForm({ ...form, nivel: e.target.value })}>{ALCANCES.map((a) => <option key={a}>{a}</option>)}</select>
          </Campo>
          <Campo label="Campañas, productos, objetivos o canales afectados (separados por |; vacío si es global)"><input type="text" value={form.alc} onChange={(e) => setForm({ ...form, alc: e.target.value })} /></Campo>
          <Campo label="Columna de la base"><select value={form.atr} onChange={(e) => setForm({ ...form, atr: e.target.value })}>{columnas.map((c) => <option key={c}>{c}</option>)}</select></Campo>
          <div className="grid grid-cols-2 gap-3">
            <Campo label="Excluir si la columna…"><select value={form.op} onChange={(e) => setForm({ ...form, op: e.target.value })}>{operadores.map((o) => <option key={o}>{o}</option>)}</select></Campo>
            <Campo label="…este valor"><input type="text" value={form.val} onChange={(e) => setForm({ ...form, val: e.target.value })} /></Campo>
          </div>
        </div>
        <div className="mt-3"><Boton primario onClick={agregar}>Agregar al borrador</Boton></div>
      </Plegable>
      <TablaEditable filas={b.reglas} columnas={cols} onChange={(rs) => act((c) => { c.reglas = rs })} textoAgregar="Nueva regla"
        nueva={(): Regla => ({ id: `R${String(b.reglas.length + 1).padStart(2, '0')}`, nombre: 'Regla nueva', tipo: 'elegibilidad', alcance_nivel: 'global', alcance_valores: [],
          atributo: columnas[0] ?? '', operador: '==', valor: 1, accion: 'excluir', activa: true })} />
    </div>
  )
}

function Canales({ b, act, columnas }: Ctx) {
  const scores = columnas.filter((c) => c.startsWith('score_canal'))
  const cols: Col<Canal>[] = [
    { etiqueta: 'Id', tipo: 'texto', ancho: '110px', leer: (f) => f.id, escribir: (f, v) => ({ ...f, id: String(v) }) },
    { etiqueta: 'Columna de score', tipo: 'seleccion', opciones: scores, ancho: '220px', leer: (f) => f.columna_score, escribir: (f, v) => ({ ...f, columna_score: String(v) }) },
    { etiqueta: 'Cupo', tipo: 'numero', paso: 100, min: 0, ancho: '120px', leer: (f) => f.cupo, escribir: (f, v) => ({ ...f, cupo: Math.max(0, Math.round(Number(v))) }) },
    { etiqueta: 'Productos por contacto', tipo: 'numero', paso: 1, min: 1, ancho: '120px', leer: (f) => f.max_productos, escribir: (f, v) => ({ ...f, max_productos: Math.max(1, Math.round(Number(v))) }) },
  ]
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">Cambia cupos y productos por contacto; agrega una fila para un canal nuevo (necesita una columna <code>score_canal_...</code> en la base y quedar permitido en las campañas).</p>
      <div className="grid gap-4 md:grid-cols-2">
        <Campo label="Cómo se elige el canal de cada cliente" ayuda="score_canal: el de mayor probabilidad de respuesta; orden_preferencia: el primero de la lista que tenga cupo">
          <select value={b.asignacion.criterio_canal} onChange={(e) => act((c) => { c.asignacion.criterio_canal = e.target.value as Config['asignacion']['criterio_canal'] })}>
            <option value="score_canal">score_canal</option><option value="orden_preferencia">orden_preferencia</option>
          </select>
        </Campo>
        <Campo label="Orden de preferencia de canales (separados por |)">
          <input type="text" value={b.asignacion.orden_preferencia.join('|')} onChange={(e) => act((c) => { c.asignacion.orden_preferencia = lista(e.target.value) })} />
        </Campo>
      </div>
      <TablaEditable filas={b.canales} columnas={cols} onChange={(cs) => act((c) => { c.canales = cs })} textoAgregar="Nuevo canal"
        nueva={() => ({ id: 'nuevo', columna_score: scores[0] ?? '', cupo: 1000, max_productos: 2 })} />
    </div>
  )
}

// ---------------------------------------------------------------- vista previa y aplicar
function VistaPrevia({ b }: { b: Config }) {
  const { vigente, revision, recargar, irA, setBorrador } = useApp()
  const [res, setRes] = useState<{ clave: string; imp: Impacto } | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [etiqueta, setEtiqueta] = useState('Ajuste de configuración')
  const clave = useMemo(() => JSON.stringify(b), [b])
  const est = useEstimacion(b)
  const [nombreEsc, setNombreEsc] = useState('')
  const [guardado, setGuardado] = useState<string | null>(null)

  if (!revision) return <Cargando texto="Revisando el borrador..." />
  if (!revision.ok) return <Banner tono="error">El borrador no es válido. Corrige lo siguiente para poder calcular su impacto:<ListaErrores errores={revision.errores} /></Banner>
  if (revision.igual_a_vigente) return <Banner>El borrador es igual a la configuración vigente.</Banner>

  const calcular = async () => {
    setCargando(true); setError(null)
    try { setRes({ clave, imp: await api<Impacto>('/api/impacto', { body: { config: b } }) }) }
    catch (e) { setError(e as ApiError); setRes(null) } finally { setCargando(false) }
  }
  const guardarEscenario = async () => {
    try {
      await api('/api/escenarios', { body: { nombre: nombreEsc, config: b } })
      setGuardado(nombreEsc); setNombreEsc(''); setError(null)
    } catch (e) { setError(e as ApiError) }
  }
  const aplicar = async () => {
    try {
      const r = await api<{ version: string }>('/api/aplicar', { body: { config: b, etiqueta } })
      await recargar(`Configuración aplicada (versión ${r.version}).`)
    } catch (e) { setError(e as ApiError) }
  }
  const imp = res && res.clave === clave ? res.imp : null
  const c = imp?.comparacion
  return (
    <div id="vista-previa" className="space-y-4">
      <TarjetaEstimacion est={est} />
      <div className="flex flex-wrap items-end gap-3">
        <Boton primario onClick={calcular} disabled={cargando}>Calcular impacto del cambio</Boton>
        <div className="min-w-64 max-w-sm flex-1">
          <input type="text" aria-label="Nombre del escenario" placeholder="Nombre para guardarlo como escenario" value={nombreEsc} onChange={(e) => setNombreEsc(e.target.value)} />
        </div>
        <Boton disabled={!nombreEsc.trim()} onClick={guardarEscenario}>Guardar como escenario</Boton>
      </div>
      {guardado && <Banner tono="ok">Escenario «{guardado}» guardado. <button type="button" className="font-medium underline underline-offset-2" onClick={() => irA('Escenarios')}>Compararlo en Escenarios</button></Banner>}
      {cargando && <Cargando texto="Calculando el impacto con los 100.000 clientes..." />}
      {error && <Banner tono="error">{error.message}{error.detalle.length > 0 && <ListaErrores errores={error.detalle} />}</Banner>}
      {imp && c && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Metric label="Valor esperado" valor={n(imp.despues.valor_esperado, 1)} delta={signo(c.delta_valor, 1)} />
            <Metric label="Clientes con acción" valor={n(imp.despues.clientes_con_accion)} delta={signo(c.delta_clientes, 0)} />
            <Metric label="Productos asignados" valor={n(imp.despues.productos_asignados)} delta={signo(c.delta_productos, 0)} />
            <Metric label="% jerarquía" valor={`${n(imp.despues.jerarquia_pct, 2)} %`} delta={`${signo(c.delta_jerarquia, 2)} pp`} />
          </div>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Metric label="Clientes que ganan acción" valor={n(c.ganan_accion)} />
            <Metric label="Clientes que pierden acción" valor={n(c.pierden_accion)} />
            <Metric label="Cambian de canal" valor={n(c.cambian_canal)} />
            <Metric label="Cambian de productos" valor={n(c.cambian_productos)} />
          </div>
          {est.tipo === 'cupos' && !est.sinEstimar && (
            <p className="text-sm text-slate-600">
              La estimación instantánea era <b>≈ {signo(est.dv, 1)}</b>; el cálculo exacto dio <b>{signo(c.delta_valor, 1)}</b>.
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <Seccion titulo="Productos asignados por campaña" sub="Azul: aumenta · Naranja: disminuye" />
              <BarrasDivergentes datos={Object.entries(c.productos_por_campana).map(([k, [a, d]]) => ({ nombre: k, cambio: d - a, antes: a, despues: d }))} />
            </Card>
            <Card>
              <Seccion titulo="Uso de cupos por canal" sub="Clientes que ocupan cada canal, antes → después" />
              <BarrasDivergentes datos={Object.keys(imp.despues.cupo_canales).map((k) => ({
                nombre: nombreCanal(k), cambio: (imp.despues.uso_canales[k] ?? 0) - (imp.antes.uso_canales[k] ?? 0),
                antes: imp.antes.uso_canales[k] ?? 0, despues: imp.despues.uso_canales[k] ?? 0 }))} />
            </Card>
          </div>
          <Card>
            <Seccion titulo="Clientes que cambian de decisión" sub="Quién gana o pierde una acción con este cambio" />
            <BarrasDivergentes datos={[
              { nombre: 'Ganan una acción', cambio: c.ganan_accion },
              { nombre: 'Pierden su acción', cambio: -c.pierden_accion },
            ]} />
          </Card>
          <Plegable titulo="Ver los mismos datos como tabla">
            <div className="grid gap-4 lg:grid-cols-2">
              <TablaLectura columnas={['Campaña', 'Antes', 'Después', 'Cambio']}
                filas={Object.entries(c.productos_por_campana).map(([k, [a, d]]) => [k, n(a), n(d), signo(d - a, 0)])} />
              <TablaLectura columnas={['Canal', 'Antes', 'Después', 'Cupo']}
                filas={Object.keys(imp.despues.cupo_canales).map((k) => [nombreCanal(k), n(imp.antes.uso_canales[k] ?? 0), n(imp.despues.uso_canales[k] ?? 0), n(imp.despues.cupo_canales[k])])} />
            </div>
          </Plegable>
          <Plegable titulo="Ejemplos de clientes afectados (haz clic para ver su explicación)">
            {Object.entries(c.ejemplos).filter(([, v]) => v.length).map(([k, v]) => (
              <div key={k} className="mb-2 text-sm"><b>{k.replace(/_/g, ' ')}</b>:{' '}
                {v.slice(0, 10).map((id) => <button key={id} className="mr-2 font-medium text-black underline underline-offset-2" onClick={() => irA('Cliente', id)}>{id}</button>)}</div>
            ))}
          </Plegable>
          {imp.validacion.violaciones_total > 0
            ? <Banner tono="error">El cambio produce {imp.validacion.violaciones_total} violaciones: {JSON.stringify(imp.validacion.violaciones)}</Banner>
            : <Banner tono="ok">Validador: el cambio mantiene 0 violaciones.</Banner>}
          <div className="max-w-xl"><Campo label="Describe el cambio (queda en el historial)"><input type="text" value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)} /></Campo></div>
          <div className="flex gap-3">
            <Boton primario disabled={imp.validacion.violaciones_total > 0} onClick={aplicar}>Aplicar cambio</Boton>
            <Boton onClick={() => vigente && setBorrador(vigente.config)}>Descartar borrador</Boton>
          </div>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- pagina
type Ctx = { b: Config; act: (f: (c: Config) => Config | void) => void; der: Derivados; columnas: string[]; operadores: string[] }

export function Cambiar() {
  const { borrador, setBorrador, revision, vigente } = useApp()
  const estBarra = useEstimacion(borrador ?? (vigente?.config as Config))
  if (!borrador || !vigente) return <Cargando />
  const act: Ctx['act'] = (f) => setBorrador((c) => { const x = clonar(c); const r = f(x); return (r ?? x) as Config })
  const der = revision?.ok ? revision.derivados : vigente.derivados
  const ctx: Ctx = { b: borrador, act, der, columnas: vigente.columnas, operadores: vigente.operadores }
  return (
    <div className="space-y-4">
      <Titulo sub="Los cambios quedan en un borrador. Antes de aplicarlos puedes ver su impacto completo en la parrilla.">Cambiar la configuración</Titulo>
      <Card>
        <Tabs pestanas={['Umbrales y contacto', 'Prioridad', 'Campañas', 'Reglas', 'Canales y cupos', 'Datos nuevos']}>
          {(p) => p === 'Umbrales y contacto' ? <Umbrales {...ctx} /> : p === 'Prioridad' ? <Prioridad {...ctx} />
            : p === 'Campañas' ? <Campanas {...ctx} /> : p === 'Reglas' ? <Reglas {...ctx} /> : p === 'Canales y cupos' ? <Canales {...ctx} />
            : (
              <div className="space-y-3 text-sm">
                <p>La base tiene <b>{vigente.columnas.length} columnas</b>. Cualquier columna sirve en una regla (pestaña Reglas). Para agregar una columna nueva, carga una base ampliada en «Base de datos».</p>
                <div className="max-h-64 overflow-auto"><TablaLectura columnas={['columna']} filas={vigente.columnas.map((c) => [c])} /></div>
              </div>
            )}
        </Tabs>
      </Card>
      {revision?.ok && (
        <Plegable titulo="Reglas en lenguaje de negocio">
          <ul className="space-y-1 text-sm">{revision.frases.map((f) => <li key={f.id}>{f.activa ? '[activa] ' : '[pausada] '}{f.texto}</li>)}</ul>
        </Plegable>
      )}
      <hr className="border-slate-200" />
      <Seccion titulo="Vista previa del impacto" />
      <VistaPrevia b={borrador} />
      {revision && (!revision.ok || !revision.igual_a_vigente) && (
        <div role="status" className="sticky bottom-4 z-10 flex items-center justify-between gap-4 rounded-xl bg-black px-5 py-3.5 text-white shadow-xl">
          <span className="text-sm font-medium">{revision.ok ? 'Tienes cambios sin aplicar' : 'El borrador tiene errores por corregir'}{revision.ok && estBarra.tipo === 'cupos' && !estBarra.sinEstimar && estBarra.dv !== 0 ? ` · estimado ≈ ${signo(estBarra.dv, 1)} de valor esperado` : ''}</span>
          <span className="flex gap-2">
            <button type="button" className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-black hover:bg-slate-200"
              onClick={() => document.getElementById('vista-previa')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
              {revision.ok ? 'Ver impacto' : 'Ver errores'}
            </button>
            <button type="button" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
              onClick={() => setBorrador(vigente.config)}>Descartar</button>
          </span>
        </div>
      )}
    </div>
  )
}
