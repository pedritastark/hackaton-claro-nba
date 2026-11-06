import { chromium } from 'playwright'
const URL = process.argv[2] ?? 'http://localhost:8001'
const OUT = process.argv[3] ?? '.'
const navegador = await chromium.launch()
const pag = await navegador.newPage({ viewport: { width: 1440, height: 900 } })
const errores = []
pag.on('pageerror', (e) => errores.push(e.message))
pag.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) errores.push(`${r.status()} ${r.url()}`) })
pag.on('dialog', (d) => d.accept())
const paso = async (n, f) => { try { await f(); console.log('OK  ', n) } catch (e) { console.log('FALLA', n, '->', e.message.split('\n')[0]); errores.push(n) } }
await pag.goto(URL)
await pag.getByText('Reparto óptimo verificado').waitFor({ timeout: 180000 })
await paso('cambiar tope de llamadas (control directo) y calcular', async () => {
  await pag.getByRole('button', { name: 'Cambiar configuración', exact: true }).click()
  await pag.getByLabel(/Llamar por asesor/).fill('3')
  await pag.getByRole('button', { name: 'Calcular impacto del cambio' }).click()
  await pag.getByText('Validador: el cambio mantiene 0 violaciones.').waitFor({ timeout: 180000 })
})
await paso('aplicar el cambio', async () => {
  await pag.getByLabel('Describe el cambio').fill('Prueba e2e llamadas 3')
  await pag.getByRole('button', { name: 'Aplicar cambio' }).click()
  await pag.getByText(/Configuración aplicada \(versión/).waitFor({ timeout: 30000 })
})
await paso('versiones lista el cambio', async () => {
  await pag.getByRole('button', { name: 'Versiones', exact: true }).click()
  await pag.getByText('Prueba e2e llamadas 3').waitFor({ timeout: 15000 })
})
await paso('tablero compara con la version anterior', async () => {
  await pag.getByRole('button', { name: 'Tablero', exact: true }).click()
  await pag.getByText('Parrilla válida').waitFor({ timeout: 180000 })
  await pag.getByText(/Versión anterior · configuración inicial del reto/).waitFor({ timeout: 5000 })
  await pag.screenshot({ path: `${OUT}/aplicado_tablero.png`, fullPage: false })
})
await paso('guardar un escenario desde el borrador', async () => {
  await pag.getByRole('button', { name: 'Cambiar configuración', exact: true }).click()
  await pag.getByRole('tab', { name: 'Canales y cupos' }).click()
  await pag.getByLabel('Cupo', { exact: true }).first().fill('15100')
  await pag.getByLabel('Nombre del escenario').fill('Escenario e2e')
  await pag.getByRole('button', { name: 'Guardar como escenario' }).click()
  await pag.getByText(/Escenario «Escenario e2e» guardado/).waitFor({ timeout: 15000 })
})
await paso('comparar el escenario con la vigente', async () => {
  await pag.getByRole('button', { name: 'Compararlo en Laboratorios' }).click()
  await pag.getByText('Escenario e2e').first().waitFor({ timeout: 15000 })
  await pag.getByLabel('Seleccionar Escenario e2e').check()
  await pag.getByRole('button', { name: /Comparar 1 con la configuración vigente/ }).click()
  await pag.getByText('Mejor valor').waitFor({ timeout: 240000 })
  await pag.getByText('Comparación lado a lado').waitFor()
  await pag.screenshot({ path: `${OUT}/escenarios_comparacion.png`, fullPage: true })
})
await paso('aplicar el escenario', async () => {
  await pag.getByRole('button', { name: 'Aplicar este escenario' }).click()
  await pag.getByText(/Escenario «Escenario e2e» aplicado/).waitFor({ timeout: 60000 })
})
await paso('curva de sensibilidad del asesor (canal lleno)', async () => {
  await pag.getByRole('button', { name: 'Tablero', exact: true }).click()
  await pag.getByText('¿Vale la pena ampliar un canal?').waitFor({ timeout: 240000 })
  await pag.locator('#canal-sens').selectOption('asesor')
  await pag.getByRole('button', { name: 'Calcular la curva' }).click()
  await pag.getByText(/Llevar Asesor de/).waitFor({ timeout: 300000 })
  await pag.locator('#canal-sens').scrollIntoViewIfNeeded()
  await pag.screenshot({ path: `${OUT}/sensibilidad_asesor.png` })
})
await paso('restaurar la inicial como borrador', async () => {
  await pag.getByRole('button', { name: 'Versiones', exact: true }).click()
  await pag.getByRole('button', { name: 'Restaurar' }).first().click()
  await pag.getByText('Versión restaurada como borrador').waitFor({ timeout: 15000 })
  await pag.getByText('Cambiar la configuración').waitFor()
})
console.log('\nERRORES:', errores.length ? errores : 'ninguno')
await navegador.close()
