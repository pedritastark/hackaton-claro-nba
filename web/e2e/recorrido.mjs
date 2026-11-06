import { iniciarSesion } from './servidor.mjs'
import { chromium } from 'playwright'

const URL = process.argv[2] ?? 'http://localhost:8000'
const OUT = process.argv[3] ?? '.'
const navegador = await chromium.launch()
const pag = await navegador.newPage({ viewport: { width: 1440, height: 900 } })
const errores = []
pag.on('console', (m) => { if (m.type() === 'error') errores.push('console: ' + m.text()) })
pag.on('pageerror', (e) => errores.push('pageerror: ' + e.message))
pag.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) errores.push(`${r.status()} ${r.url()}`) })

const paso = async (nombre, f) => {
  try { await f(); console.log('OK  ', nombre) } catch (e) { console.log('FALLA', nombre, '->', e.message.split('\n')[0]); errores.push(nombre) }
}

await pag.goto(URL)
await iniciarSesion(pag)
await paso('Resumen (portada) carga', async () => {
  await pag.getByText('Reparto óptimo verificado').waitFor({ timeout: 180000 })
  await pag.getByText('10.940,0').first().waitFor({ timeout: 5000 })
  await pag.getByText('Lo que dicen los datos').waitFor()
  await pag.waitForTimeout(900)
  await pag.screenshot({ path: `${OUT}/00_resumen.png`, fullPage: true })
})
await paso('Tablero carga', async () => {
  await pag.getByRole('button', { name: 'Tablero', exact: true }).click()
  await pag.getByText('Parrilla válida').waitFor({ timeout: 120000 })
  await pag.getByText('10.940,0').first().waitFor({ timeout: 5000 })
  await pag.getByText('Mapa de calor').click()
  await pag.getByText('Total').first().waitFor()
  await pag.waitForTimeout(500)
  await pag.screenshot({ path: `${OUT}/01_tablero.png`, fullPage: true })
})
await paso('Cliente desde el tablero', async () => {
  await pag.getByRole('button', { name: 'Ver un ejemplo' }).first().click()
  await pag.getByText('Explicación por cliente').waitFor()
  await pag.getByText('1 · Qué productos se pueden ofrecer').waitFor({ timeout: 60000 })
  await pag.screenshot({ path: `${OUT}/02_cliente.png`, fullPage: true })
})
await paso('Buscar cliente por id', async () => {
  const caja = pag.getByPlaceholder('CL000001')
  await caja.fill('CL000001'); await caja.press('Enter')
  await pag.getByText('Cliente CL000001 · decisión').waitFor({ timeout: 30000 })
})
await paso('Ficha: datos del cliente con las reglas que los miran', async () => {
  await pag.getByText('Datos del cliente', { exact: true }).waitFor({ timeout: 15000 })
  await pag.getByText('R01', { exact: true }).first().waitFor({ timeout: 5000 })
})
await paso('Base de datos', async () => {
  await pag.getByRole('button', { name: 'Base de datos', exact: true }).click()
  await pag.getByText('La base trae todas las columnas').waitFor({ timeout: 30000 })
  await pag.getByText('Calidad de los datos').waitFor({ timeout: 15000 })
  await pag.getByText('Identificadores únicos').waitFor()
  await pag.screenshot({ path: `${OUT}/03_base.png`, fullPage: true })
})
await paso('Sensibilidad de un canal no lleno (SMS)', async () => {
  await pag.getByRole('button', { name: 'Tablero', exact: true }).click()
  await pag.getByText('¿Vale la pena ampliar un canal?').waitFor({ timeout: 120000 })
  await pag.locator('#canal-sens').selectOption('sms')
  await pag.getByRole('button', { name: 'Calcular la curva' }).click()
  await pag.getByText(/no cambia el valor esperado/).waitFor({ timeout: 180000 })
  await pag.locator('#canal-sens').scrollIntoViewIfNeeded()
  await pag.screenshot({ path: `${OUT}/10_sensibilidad_sms.png` })
})
await paso('Versiones', async () => {
  await pag.getByRole('button', { name: 'Versiones', exact: true }).click()
  await pag.getByText('Historial de versiones').waitFor()
  await pag.screenshot({ path: `${OUT}/04_versiones.png` })
})
await paso('Cambiar: pestañas y edicion', async () => {
  await pag.getByRole('button', { name: 'Cambiar configuración', exact: true }).click()
  await pag.getByText('Cambiar la configuración').waitFor()
  await pag.screenshot({ path: `${OUT}/05_cambiar_umbrales.png`, fullPage: true })
  for (const t of ['Prioridad', 'Campañas', 'Reglas', 'Canales y cupos', 'Datos nuevos']) {
    await pag.getByRole('tab', { name: t }).click()
    await pag.waitForTimeout(250)
  }
  await pag.getByRole('tab', { name: 'Campañas' }).click()
  await pag.screenshot({ path: `${OUT}/06_cambiar_campanas.png`, fullPage: true })
  await pag.getByRole('tab', { name: 'Reglas' }).click()
  await pag.screenshot({ path: `${OUT}/07_cambiar_reglas.png`, fullPage: true })
})
await paso('Reglas muestran cuantos clientes excluyen hoy', async () => {
  await pag.getByRole('tab', { name: 'Reglas' }).click()
  await pag.getByText('Excluye hoy').waitFor({ timeout: 15000 })
  await pag.getByText('Excluye hoy').scrollIntoViewIfNeeded()
  await pag.screenshot({ path: `${OUT}/07b_reglas_excluye.png` })
})
await paso('Cambiar cupo y calcular impacto', async () => {
  await pag.getByRole('tab', { name: 'Canales y cupos' }).click()
  const cupo = pag.getByLabel('Cupo').nth(1) // whatsapp (segunda fila)
  await cupo.fill('15100')
  await pag.getByText('Estimación instantánea').first().waitFor({ timeout: 15000 })
  await pag.getByText(/≈ \+6,5/).first().waitFor({ timeout: 5000 })
  await pag.getByRole('button', { name: 'Calcular impacto del cambio' }).click()
  await pag.getByText('Validador: el cambio mantiene 0 violaciones.').waitFor({ timeout: 180000 })
  await pag.getByText(/La estimación instantánea era/).waitFor({ timeout: 5000 })
  await pag.screenshot({ path: `${OUT}/08_impacto.png`, fullPage: true })
})
await paso('Borrador invalido muestra errores', async () => {
  await pag.getByRole('tab', { name: 'Prioridad' }).click()
  await pag.getByRole('button', { name: /Parámetros del baseline/ }).or(pag.getByText('Parámetros del baseline')).first().click()
  const inputs = pag.locator('details input[type=number]')
  for (let i = 0; i < 3; i++) await inputs.nth(i).fill('0')
  await pag.getByText('no pueden ser todos cero').waitFor({ timeout: 5000 })
  await pag.getByText('El borrador no es válido').waitFor({ timeout: 10000 })
  await pag.screenshot({ path: `${OUT}/09_borrador_invalido.png`, fullPage: true })
})

console.log('\nERRORES:', errores.length ? errores : 'ninguno')
await navegador.close()
