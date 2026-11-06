import assert from 'node:assert/strict'
import { join } from 'node:path'
import { chromium } from 'playwright'
import { configurarInicial, iniciarSesion, servidorTemporal } from './servidor.mjs'

const entorno = await servidorTemporal()
let navegador
try {
  navegador = await chromium.launch({ executablePath: process.env.NBA_CHROMIUM || undefined })
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 1000 } })
  const p = await contexto.newPage()
  p.setDefaultTimeout(60000)
  const errores = []
  p.on('pageerror', (e) => errores.push(e.message))
  await configurarInicial(p, entorno)
  assert.equal((await contexto.cookies()).find((c) => c.name === 'nba_sesion').httpOnly, true)
  await p.getByRole('button', { name: 'Usuarios y permisos', exact: true }).click()
  for (const rol of ['editor', 'analista', 'consulta']) {
    await p.getByLabel('Nombre del nuevo usuario', { exact: true }).fill('Persona ' + rol)
    await p.getByLabel('Correo del nuevo usuario', { exact: true }).fill(rol + '@example.test')
    await p.getByLabel('Contraseña inicial', { exact: true }).fill(entorno.clave)
    await p.getByLabel('Rol del nuevo usuario', { exact: true }).selectOption(rol)
    await p.getByRole('button', { name: 'Crear usuario', exact: true }).click()
    await p.getByRole('form', { name: 'Editar ' + rol + '@example.test', exact: true }).waitFor()
  }
  await p.getByRole('tab', { name: 'Permisos por rol', exact: true }).click()
  await p.getByRole('columnheader', { name: 'Analista de pruebas', exact: true }).waitFor()
  await p.getByRole('tab', { name: 'Actividad reciente', exact: true }).click()
  await p.getByRole('cell', { name: 'crear usuario', exact: true }).first().waitFor()
  console.log('OK instalación inicial, creación de usuarios, matriz de permisos y actividad')

  const post = async (ruta, data) => {
    const s = await (await contexto.request.get(entorno.url + '/api/auth/sesion')).json()
    return contexto.request.post(entorno.url + ruta, { data, headers: { 'X-CSRF-Token': s.csrf_token } })
  }
  await p.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await iniciarSesion(p, 'analista@example.test', entorno.clave)
  assert.equal(await p.getByRole('button', { name: 'Usuarios y permisos', exact: true }).count(), 0)
  assert.equal(await p.getByRole('button', { name: 'Cambiar configuración', exact: true }).count(), 0)
  await p.getByRole('button', { name: 'Laboratorios', exact: true }).click()
  await p.getByRole('button', { name: 'Crear prueba de cupos y canales', exact: true }).click()
  await p.getByLabel('Nombre del experimento', { exact: true }).fill('Prueba del analista')
  const cupo = p.getByLabel('Cupo de WhatsApp', { exact: true })
  await cupo.fill(String(Number(await cupo.inputValue()) + 100))
  await p.getByRole('button', { name: 'Guardar y ejecutar prueba', exact: true }).click()
  await p.getByRole('heading', { name: 'Comparación lado a lado', exact: true }).waitFor({ timeout: 180000 })
  await p.getByText('Último resultado · histórico', { exact: true }).waitFor()
  assert.equal(await p.getByRole('button', { name: 'Aplicar este escenario', exact: true }).count(), 0)
  assert.equal((await post('/api/aplicar', { config: {} })).status(), 403)
  assert.equal((await post('/api/base/ruta', { ruta: '/tmp/base.csv' })).status(), 403)
  assert.equal((await contexto.request.get(entorno.url + '/api/usuarios')).status(), 403)
  console.log('OK analista ejecuta pruebas; API e interfaz impiden aplicar, cambiar datos y administrar usuarios')

  await p.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await iniciarSesion(p, 'consulta@example.test', entorno.clave)
  await p.getByRole('button', { name: 'Laboratorios', exact: true }).click()
  await p.getByText('Tu acceso es de consulta.', { exact: false }).waitFor()
  assert.equal(await p.getByRole('button', { name: /Crear prueba/ }).count(), 0)
  assert.equal(await p.getByRole('button', { name: 'Eliminar', exact: true }).count(), 0)
  assert.equal((await post('/api/escenarios', { nombre: 'Denegado', config: {} })).status(), 403)
  await p.getByRole('button', { name: 'Base de datos', exact: true }).click()
  await p.getByText('Calidad de los datos', { exact: true }).waitFor()
  assert.equal(await p.getByRole('button', { name: 'Cargar y usar', exact: true }).count(), 0)
  console.log('OK Consulta revisa resultados y datos sin acciones de escritura')

  await p.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await iniciarSesion(p, 'editor@example.test', entorno.clave)
  assert.equal(await p.getByRole('button', { name: 'Usuarios y permisos', exact: true }).count(), 0)
  await p.getByRole('button', { name: 'Laboratorios', exact: true }).click()
  await p.getByRole('button', { name: 'Cargar como borrador', exact: true }).click()
  await p.getByRole('button', { name: 'Calcular impacto del cambio', exact: true }).click()
  await p.getByText('Validador: el cambio mantiene 0 violaciones.', { exact: true }).waitFor({ timeout: 180000 })
  await p.getByRole('button', { name: 'Aplicar cambio', exact: true }).click()
  await p.getByText(/Configuración aplicada \(versión/).waitFor()
  assert.equal((await (await contexto.request.get(entorno.url + '/api/versiones')).json()).length, 1)
  console.log('OK Editor aplica una configuración válida y genera una versión')

  const extra = await navegador.newContext()
  const entrada = await extra.request.post(entorno.url + '/api/auth/entrar', { data: { correo: 'analista@example.test', clave: entorno.clave } })
  assert.equal(entrada.status(), 200)
  await p.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await iniciarSesion(p, 'admin@example.test', entorno.clave)
  await p.getByRole('button', { name: 'Usuarios y permisos', exact: true }).click()
  const editar = p.getByRole('form', { name: 'Editar analista@example.test', exact: true })
  await editar.getByRole('checkbox', { name: 'Cuenta activa', exact: true }).uncheck()
  await editar.getByRole('button', { name: 'Guardar usuario', exact: true }).click()
  await p.getByText('Usuario actualizado.', { exact: false }).waitFor()
  assert.equal((await extra.request.get(entorno.url + '/api/config')).status(), 401)
  await extra.close()
  console.log('OK desactivar una cuenta revoca las sesiones que ya estaban abiertas')

  await p.getByRole('button', { name: 'Mi cuenta', exact: true }).click()
  await p.getByLabel('Contraseña actual', { exact: true }).fill(entorno.clave)
  await p.getByLabel('Nueva contraseña', { exact: true }).fill(entorno.clave + '-nueva')
  await p.getByLabel('Confirma la nueva contraseña', { exact: true }).fill(entorno.clave + '-nueva')
  await p.getByRole('button', { name: 'Cambiar contraseña', exact: true }).click()
  await p.getByRole('heading', { name: 'Inicia sesión', exact: true }).waitFor()
  await iniciarSesion(p, 'admin@example.test', entorno.clave + '-nueva')
  assert.deepEqual(errores, [])
  console.log('OK cambio de contraseña y nuevo inicio de sesión; sin errores de navegador')
  if (process.env.NBA_E2E_OUT) {
    await p.getByRole('button', { name: 'Usuarios y permisos', exact: true }).click()
    await p.getByRole('form', { name: 'Editar consulta@example.test', exact: true }).waitFor()
    await p.screenshot({ path: join(process.env.NBA_E2E_OUT, 'usuarios-permisos.png'), fullPage: true })
  }
} finally {
  if (navegador) await navegador.close()
  await entorno.cerrar()
}
