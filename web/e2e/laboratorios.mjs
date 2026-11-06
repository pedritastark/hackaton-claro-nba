import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { cp, mkdtemp, readFile, rm } from 'node:fs/promises'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'

// Servidor y configuración desechables: el recorrido nunca escribe en config/.
const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const temporal = await mkdtemp(join(tmpdir(), 'nba-laboratorios-'))
const reserva = createServer().listen(0, '127.0.0.1')
await once(reserva, 'listening')
const puerto = reserva.address().port
await new Promise((ok) => reserva.close(ok))
await cp(join(raiz, 'config_inicial'), join(temporal, 'config'), { recursive: true })
const servidor = spawn(join(raiz, '.venv/bin/python'), ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', String(puerto)], {
  cwd: raiz,
  env: { ...process.env, NBA_CONFIG_DIR: join(temporal, 'config'), NBA_CLIENTES: join(raiz, 'data/oficial/clientes.csv') },
  stdio: ['ignore', 'ignore', 'pipe'],
})
let logs = ''
servidor.stderr.on('data', (s) => { logs = (logs + s).slice(-5000) })
const url = `http://127.0.0.1:${puerto}`
const esperar = async (f, timeout = 180000) => {
  const inicio = Date.now()
  while (Date.now() - inicio < timeout) {
    if (await f()) return
    await new Promise((ok) => setTimeout(ok, 500))
  }
  throw new Error('Tiempo agotado esperando al laboratorio. ' + logs)
}
let navegador
try {
  await esperar(async () => {
    if (servidor.exitCode !== null) throw new Error(logs)
    return fetch(url + '/api/estado').then((r) => r.ok).catch(() => false)
  }, 30000)
  navegador = await chromium.launch({ executablePath: process.env.NBA_CHROMIUM || undefined })
  const pagina = await navegador.newPage({ viewport: { width: 1440, height: 1000 } })
  pagina.setDefaultTimeout(60000)
  const errores = []
  pagina.on('pageerror', (e) => errores.push(e.message))
  pagina.on('console', (m) => { if (m.type() === 'error') errores.push(m.text()) })
  const configuracion = async () => (await (await fetch(url + '/api/config')).json()).config
  const listado = async () => (await (await fetch(url + '/api/escenarios')).json())
  const original = await configuracion()
  const parametros = await readFile(join(temporal, 'config/parametros.yaml'), 'utf8')
  await pagina.goto(url)
  await pagina.getByRole('button', { name: 'Laboratorios', exact: true }).click()
  await pagina.getByRole('heading', { name: 'Centro de laboratorios' }).waitFor()

  await pagina.getByRole('button', { name: 'Crear prueba de cupos y canales', exact: true }).click()
  await pagina.getByLabel('Nombre del experimento').fill('WhatsApp +100')
  await pagina.getByLabel('Objetivo de la prueba').fill('Medir la ganancia por capacidad adicional')
  const cupo = original.canales.find((c) => c.id === 'whatsapp').cupo
  await pagina.getByLabel('Cupo de WhatsApp', { exact: true }).fill(String(cupo + 100))
  await pagina.getByRole('button', { name: 'Guardar y ejecutar prueba', exact: true }).click()
  await pagina.getByRole('heading', { name: 'Comparación lado a lado' }).waitFor({ timeout: 180000 })
  await pagina.getByText('Último resultado · histórico', { exact: true }).waitFor({ timeout: 15000 })
  let pruebas = await listado()
  const primera = pruebas.find((e) => e.nombre === 'WhatsApp +100')
  assert.equal(primera.tipo, 'cupos')
  assert.equal(primera.ultimo_resultado.violaciones_total, 0)
  assert.ok(primera.ultimo_resultado.metricas.valor_esperado > primera.ultimo_resultado.metricas_referencia.valor_esperado)
  console.log('OK crear y ejecutar: 0 violaciones; valor', primera.ultimo_resultado.metricas.valor_esperado)

  await pagina.getByRole('button', { name: 'Duplicar prueba', exact: true }).click()
  await pagina.getByRole('tab', { name: 'Cupos y canales', exact: true }).click()
  assert.equal((await listado()).length, 1, 'Cambiar de pestaña no debe guardar el formulario')
  assert.equal(await pagina.getByLabel('Cupo de WhatsApp', { exact: true }).inputValue(), String(cupo + 100))
  await pagina.getByLabel('Cupo de WhatsApp', { exact: true }).fill(String(cupo + 200))
  await pagina.getByRole('button', { name: 'Guardar sin ejecutar', exact: true }).click()
  await esperar(async () => (await listado()).length === 2)
  const guardada = await (await fetch(url + '/api/escenarios/' + primera.id)).json()
  assert.equal(guardada.config.canales.find((c) => c.id === 'whatsapp').cupo, cupo + 100)
  console.log('OK duplicar y editar conserva la prueba original')

  for (const [tipo, nombre] of [['reglas', 'reglas y umbrales'], ['prioridad', 'prioridades y algoritmo']]) {
    await pagina.getByRole('button', { name: 'Crear prueba de ' + nombre, exact: true }).click()
    await pagina.getByLabel('Nombre del experimento').fill('Prueba ' + tipo)
    if (tipo === 'reglas') {
      await pagina.getByLabel('Puntaje mínimo del producto', { exact: true }).fill('0.4')
      await pagina.getByRole('checkbox', { name: /^R01/ }).uncheck()
    } else {
      await pagina.getByLabel('Peso de la jerarquía (α)', { exact: true }).fill('0.3')
      await pagina.getByLabel('Algoritmo de asignación', { exact: true }).selectOption('codicioso')
      await pagina.getByRole('button', { name: 'Bajar ' + original.priorizacion.jerarquia[0], exact: true }).click()
    }
    await pagina.getByRole('button', { name: 'Guardar sin ejecutar', exact: true }).click()
    await esperar(async () => (await listado()).some((e) => e.nombre === 'Prueba ' + tipo))
  }
  pruebas = await listado()
  const reglas = await (await fetch(url + '/api/escenarios/' + pruebas.find((e) => e.tipo === 'reglas').id)).json()
  assert.equal(reglas.config.priorizacion.umbral_score_producto, 0.4)
  assert.equal(reglas.config.reglas.find((r) => r.id === 'R01').activa, false)
  const prioridad = await (await fetch(url + '/api/escenarios/' + pruebas.find((e) => e.tipo === 'prioridad').id)).json()
  assert.equal(prioridad.config.priorizacion.alpha, 0.3)
  assert.equal(prioridad.config.asignacion.algoritmo, 'codicioso')
  assert.equal(prioridad.config.priorizacion.jerarquia[0], original.priorizacion.jerarquia[1])
  console.log('OK guardar pruebas de reglas y de prioridades')

  await pagina.reload()
  await pagina.getByRole('button', { name: 'Laboratorios', exact: true }).click()
  await pagina.getByText('Último resultado · histórico', { exact: true }).waitFor()
  await pagina.getByRole('button', { name: 'Abrir sensibilidad', exact: true }).click()
  await pagina.locator('#canal-sens').selectOption('sms', { timeout: 180000 })
  await pagina.getByRole('button', { name: 'Calcular la curva', exact: true }).click()
  await pagina.getByText(/Ampliar el cupo de SMS no cambia el valor esperado/).waitFor({ timeout: 180000 })
  console.log('OK resultado conservado tras recargar y sensibilidad de SMS')

  for (const ancho of [1440, 390]) {
    await pagina.setViewportSize({ width: ancho, height: 1000 })
    await pagina.evaluate(() => { document.querySelector('main').scrollTop = 0 })
    assert.ok(await pagina.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Desbordamiento a ${ancho}px`)
    if (process.env.NBA_E2E_OUT) await pagina.screenshot({ path: join(process.env.NBA_E2E_OUT, `laboratorios-${ancho}.png`), fullPage: true })
  }
  assert.deepEqual(await configuracion(), original)
  assert.equal(await readFile(join(temporal, 'config/parametros.yaml'), 'utf8'), parametros)
  assert.equal((await (await fetch(url + '/api/versiones')).json()).length, 0)
  assert.deepEqual(errores, [])
  console.log('OK vigente intacta, sin versiones nuevas ni errores de navegador')
} finally {
  if (navegador) await navegador.close()
  servidor.kill('SIGTERM')
  if (servidor.exitCode === null) await once(servidor, 'exit')
  await rm(temporal, { recursive: true, force: true })
}
