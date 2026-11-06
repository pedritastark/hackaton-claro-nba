import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { cp, mkdtemp, rm } from 'node:fs/promises'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export async function servidorTemporal() {
  const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
  const temporal = await mkdtemp(join(tmpdir(), 'nba-e2e-'))
  const reserva = createServer().listen(0, '127.0.0.1')
  await once(reserva, 'listening')
  const puerto = reserva.address().port
  await new Promise((ok) => reserva.close(ok))
  await cp(join(raiz, 'config_inicial'), join(temporal, 'config'), { recursive: true })
  const token = randomBytes(32).toString('base64url')
  const clave = randomBytes(24).toString('base64url')
  const servidor = spawn(join(raiz, '.venv/bin/python'), ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', String(puerto)], {
    cwd: raiz,
    env: { ...process.env, NBA_CONFIG_DIR: join(temporal, 'config'), NBA_AUTH_DIR: join(temporal, 'acceso'), NBA_SETUP_TOKEN: token, NBA_COOKIE_SECURE: '0', NBA_CLIENTES: join(raiz, 'data/oficial/clientes.csv') },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let logs = ''
  servidor.stderr.on('data', (s) => { logs = (logs + s).slice(-5000) })
  const url = `http://127.0.0.1:${puerto}`
  const esperar = async (f, timeout = 180000) => {
    const inicio = Date.now()
    while (Date.now() - inicio < timeout) {
      if (servidor.exitCode !== null) throw new Error(logs)
      if (await f()) return
      await new Promise((ok) => setTimeout(ok, 500))
    }
    throw new Error('Tiempo agotado. ' + logs)
  }
  const cerrar = async () => {
    servidor.kill('SIGTERM')
    if (servidor.exitCode === null) await once(servidor, 'exit')
    await rm(temporal, { recursive: true, force: true })
  }
  try {
    await esperar(() => fetch(url + '/api/auth/sesion').then((r) => r.ok).catch(() => false), 30000)
  } catch (e) { await cerrar(); throw e }
  return { raiz, temporal, url, esperar, cerrar, token, clave }
}

export async function configurarInicial(pagina, entorno) {
  await pagina.goto(entorno.url)
  await pagina.getByLabel('Clave de instalación', { exact: true }).fill(entorno.token)
  await pagina.getByLabel('Nombre', { exact: true }).fill('Admin E2E')
  await pagina.getByLabel('Correo', { exact: true }).fill('admin@example.test')
  await pagina.getByLabel('Contraseña', { exact: true }).fill(entorno.clave)
  await pagina.getByRole('button', { name: 'Crear administrador', exact: true }).click()
  await pagina.getByRole('button', { name: 'Cerrar sesión', exact: true }).waitFor()
}

export async function iniciarSesion(pagina, correo = process.env.NBA_E2E_CORREO, clave = process.env.NBA_E2E_CLAVE) {
  if (!correo || !clave) throw new Error('Configura NBA_E2E_CORREO y NBA_E2E_CLAVE con una cuenta de pruebas autorizada.')
  await pagina.getByLabel('Correo', { exact: true }).fill(correo)
  await pagina.getByLabel('Contraseña', { exact: true }).fill(clave)
  await pagina.getByRole('button', { name: 'Entrar', exact: true }).click()
  await pagina.getByRole('button', { name: 'Cerrar sesión', exact: true }).waitFor()
}
