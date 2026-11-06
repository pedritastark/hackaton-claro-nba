"""Pruebas de acceso con SQLite temporal: no modifican usuarios ni config reales."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api import acceso, servicio
from api.main import app

CLAVE = 'Pruebas-de-acceso-2026!'


@pytest.fixture
def sitio(tmp_path, monkeypatch):
    monkeypatch.setenv('NBA_AUTH_DIR', str(tmp_path / 'acceso'))
    monkeypatch.setenv('NBA_CONFIG_DIR', str(Path(__file__).resolve().parent.parent / 'config_inicial'))
    monkeypatch.delenv('NBA_SETUP_TOKEN', raising=False)
    monkeypatch.delenv('NBA_COOKIE_SECURE', raising=False)
    c = TestClient(app)
    yield c
    c.close()


def instalar(c):
    estado = c.get('/api/auth/sesion').json()
    assert estado['requiere_configuracion'] and estado['usuario'] is None
    token = (acceso.carpeta() / 'clave-inicial.txt').read_text().strip()
    r = c.post('/api/auth/configurar', json={'token': token, 'nombre': 'Admin', 'correo': 'admin@example.test', 'clave': CLAVE})
    assert r.status_code == 200, r.text
    c.headers['X-CSRF-Token'] = r.json()['csrf_token']
    return r


def cuenta(c, rol, correo=None):
    r = c.post('/api/usuarios', json={'nombre': rol, 'correo': correo or rol + '@example.test', 'clave': CLAVE, 'rol': rol})
    assert r.status_code == 200, r.text
    return r.json()


def entrar(c, correo, clave=CLAVE):
    r = c.post('/api/auth/entrar', json={'correo': correo, 'clave': clave})
    assert r.status_code == 200, r.text
    c.headers['X-CSRF-Token'] = r.json()['csrf_token']
    return r


@pytest.mark.parametrize('ruta,metodo', [
    ('/api/estado', 'get'), ('/api/config', 'get'), ('/api/escenarios', 'get'), ('/api/usuarios', 'get'),
    ('/api/usuarios/roles', 'get'), ('/api/usuarios/actividad', 'get'), ('/api/parrilla.csv', 'get'),
    ('/api/aplicar', 'post'), ('/api/base/subir', 'post'), ('/api/config/restaurar-inicial', 'post'),
])
def test_api_requiere_sesion(sitio, ruta, metodo):
    r = getattr(sitio, metodo)(ruta, **({'json': {}} if metodo == 'post' else {}))
    assert r.status_code == 401


def test_instalacion_hash_cookie_y_cierre(sitio):
    sitio.get('/api/auth/sesion')
    assert sitio.post('/api/auth/configurar', json={'token': 'incorrecta', 'nombre': 'Admin', 'correo': 'admin@example.test', 'clave': CLAVE}).status_code == 403
    r = instalar(sitio)
    assert r.json()['usuario']['rol'] == 'administrador'
    cookie = r.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie and 'path=/api' in cookie
    assert not (acceso.carpeta() / 'clave-inicial.txt').exists()
    with acceso.db() as con:
        u = con.execute('SELECT * FROM usuarios').fetchone()
        s = con.execute('SELECT * FROM sesiones').fetchone()
        assert u['clave'].startswith('scrypt$') and CLAVE not in u['clave']
        assert s['token'] != sitio.cookies.get(acceso.COOKIE)
    assert 'clave' not in str(sitio.get('/api/usuarios').json())
    utilizada = json.loads(r.request.content)['token']
    assert sitio.post('/api/auth/configurar', json={'token': utilizada, 'nombre': 'Otra', 'correo': 'otro@example.test', 'clave': CLAVE}).status_code == 403
    robada = sitio.cookies.get(acceso.COOKIE)
    assert sitio.post('/api/auth/salir').status_code == 200
    sitio.cookies.set(acceso.COOKIE, robada)
    assert sitio.get('/api/config').status_code == 401


def test_csrf_y_origen(sitio):
    instalar(sitio)
    token = sitio.headers.pop('X-CSRF-Token')
    assert sitio.post('/api/usuarios', json={}).status_code == 403
    assert sitio.post('/api/usuarios', json={}, headers={b'X-CSRF-Token': b'\xff'}).status_code == 403
    sitio.headers['X-CSRF-Token'] = token
    assert sitio.post('/api/usuarios', json={}, headers={'Origin': 'https://ajeno.example'}).status_code == 403
    assert sitio.post('/api/usuarios', json={}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert sitio.post('/api/auth/entrar', json={'correo': 'admin@example.test', 'clave': CLAVE}, headers={'Origin': 'https://ajeno.example'}).status_code == 403
    assert sitio.get('/api/usuarios').status_code == 200


@pytest.mark.parametrize('rol,editar,ejecutar,datos,exportar', [
    ('administrador', True, True, True, True), ('editor', True, True, False, True),
    ('analista', False, True, False, True), ('consulta', False, False, False, False),
])
def test_permisos_directos_por_rol(sitio, monkeypatch, rol, editar, ejecutar, datos, exportar):
    instalar(sitio)
    cuenta(sitio, rol)
    entrar(sitio, rol + '@example.test')
    monkeypatch.setattr(servicio, 'info_configuracion', lambda: {'lectura': True})
    monkeypatch.setattr(servicio, 'aplicar', lambda *a: {'version': 'permitida'})
    monkeypatch.setattr(servicio, 'guardar_escenario', lambda *a: {'id': 'prueba'})
    monkeypatch.setattr(servicio, 'sensibilidad', lambda *a: {'trabajo': 'prueba'})
    monkeypatch.setattr(servicio, 'usar_ruta', lambda *a: {'ok': True})
    monkeypatch.setattr(servicio, 'restaurar_inicial', lambda: {'ok': True})
    monkeypatch.setattr(servicio, 'parrilla_csv', lambda: 'id_cliente\n')
    assert sitio.get('/api/config').status_code == 200
    assert sitio.post('/api/aplicar', json={'config': {}}).status_code == (200 if editar else 403)
    assert sitio.post('/api/escenarios', json={'nombre': 'Prueba', 'config': {}}).status_code == (200 if ejecutar else 403)
    assert sitio.post('/api/sensibilidad', json={'canal': 'sms'}).status_code == (200 if ejecutar else 403)
    assert sitio.post('/api/base/ruta', json={'ruta': 'ruta.csv'}).status_code == (200 if datos else 403)
    assert sitio.post('/api/config/restaurar-inicial').status_code == (200 if datos else 403)
    assert sitio.get('/api/parrilla.csv').status_code == (200 if exportar else 403)
    for ruta in ('/api/usuarios', '/api/usuarios/roles', '/api/usuarios/actividad'):
        assert sitio.get(ruta).status_code == (200 if rol == 'administrador' else 403)
    if rol != 'administrador':
        assert sitio.post('/api/usuarios', json={'nombre': 'Elevado', 'correo': 'elevado@example.test', 'clave': CLAVE, 'rol': 'administrador'}).status_code == 403


def test_revocacion_por_rol_estado_y_clave(sitio):
    instalar(sitio)
    u = cuenta(sitio, 'editor')
    con_editor = TestClient(app)
    entrar(con_editor, u['correo'])
    assert sitio.patch('/api/usuarios/' + u['id'], json={'nombre': u['nombre'], 'rol': 'consulta', 'activo': True}).status_code == 200
    assert con_editor.get('/api/config').status_code == 401
    entrar(con_editor, u['correo'])
    assert con_editor.post('/api/aplicar', json={'config': {}}).status_code == 403
    assert sitio.post('/api/usuarios/' + u['id'] + '/clave', json={'nueva': 'Nueva-clave-de-prueba-2026'}).status_code == 200
    assert con_editor.get('/api/config').status_code == 401
    entrar(con_editor, u['correo'], 'Nueva-clave-de-prueba-2026')
    assert sitio.patch('/api/usuarios/' + u['id'], json={'nombre': u['nombre'], 'rol': 'consulta', 'activo': False}).status_code == 200
    assert con_editor.get('/api/config').status_code == 401
    assert con_editor.post('/api/auth/entrar', json={'correo': u['correo'], 'clave': 'Nueva-clave-de-prueba-2026'}).status_code == 401
    con_editor.close()


def test_cambiar_clave_revoca_todas_las_sesiones(sitio):
    instalar(sitio)
    otra = TestClient(app)
    entrar(otra, 'admin@example.test')
    assert sitio.post('/api/auth/clave', json={'actual': 'incorrecta', 'nueva': 'Nueva-clave-segura-2026'}).status_code == 403
    assert sitio.post('/api/auth/clave', json={'actual': CLAVE, 'nueva': 'Nueva-clave-segura-2026'}).status_code == 200
    assert sitio.get('/api/usuarios').status_code == 401 and otra.get('/api/usuarios').status_code == 401
    assert sitio.post('/api/auth/entrar', json={'correo': 'admin@example.test', 'clave': CLAVE}).status_code == 401
    entrar(sitio, 'admin@example.test', 'Nueva-clave-segura-2026')
    otra.close()


def test_administrador_correo_y_caducidad(sitio):
    instalar(sitio)
    propio = sitio.get('/api/auth/sesion').json()['usuario']
    assert sitio.patch('/api/usuarios/' + propio['id'], json={'nombre': 'Admin', 'rol': 'consulta', 'activo': True}).status_code == 409
    assert sitio.patch('/api/usuarios/' + propio['id'], json={'nombre': 'Admin', 'rol': 'administrador', 'activo': False}).status_code == 409
    assert sitio.post('/api/usuarios', json={'nombre': 'Dup', 'correo': ' ADMIN@EXAMPLE.TEST ', 'clave': CLAVE}).status_code == 409
    assert sitio.post('/api/usuarios', json={'nombre': 'X', 'correo': 'no-es-correo', 'clave': CLAVE}).status_code == 422
    with acceso.db() as con:
        con.execute('UPDATE sesiones SET vence=0')
    assert sitio.get('/api/usuarios').status_code == 401
    assert sitio.get('/api/auth/sesion').json()['usuario'] is None


def test_limite_intentos_y_no_filtrar_usuario(sitio):
    instalar(sitio)
    for _ in range(10):
        r = sitio.post('/api/auth/entrar', json={'correo': 'admin@example.test', 'clave': 'incorrecta'})
        assert r.status_code == 401
    assert sitio.post('/api/auth/entrar', json={'correo': 'admin@example.test', 'clave': CLAVE}).status_code == 429
    r = sitio.post('/api/auth/entrar', json={'correo': 'noexiste@example.test', 'clave': 'incorrecta'})
    assert r.status_code == 401 and r.json()['detail'] == 'Correo o contraseña incorrectos.'


def test_ruta_nueva_denegada_por_defecto_y_estaticos(sitio):
    instalar(sitio)
    def sin_permiso():
        return {'dato': 'privado'}
    ruta = APIRoute('/api/sin-permiso', sin_permiso, dependencies=[Depends(acceso.autorizar)])
    app.router.routes.insert(0, ruta)
    try:
        assert sitio.get('/api/sin-permiso').status_code == 403
    finally:
        app.router.routes.remove(ruta)
    assert sitio.get('/api/no-existe').status_code == 404
    assert sitio.get('/..%2F..%2Fvar%2Facceso%2Fusuarios.sqlite3').status_code == 404
    for ruta in app.routes:
        if isinstance(ruta, APIRoute) and ruta.path.startswith('/api/') and not ruta.path.startswith(('/api/auth/', '/api/usuarios')):
            assert ruta.name in acceso.PERMISOS_RUTAS
            assert any(d.dependency == acceso.autorizar for d in ruta.dependencies)


def test_csrf_vinculado_a_la_sesion_y_cookie_secure(sitio):
    instalar(sitio)
    otra = TestClient(app, base_url='https://testserver')
    r = entrar(otra, 'admin@example.test')
    assert 'secure' in r.headers['set-cookie'].lower()
    assert otra.post('/api/auth/salir', headers={'X-CSRF-Token': sitio.headers['X-CSRF-Token']}).status_code == 403
    assert otra.post('/api/auth/salir').status_code == 200
    otra.close()
    # Una nueva sesión no reutiliza el identificador del inicio de sesión anterior.
    anterior = sitio.cookies.get(acceso.COOKIE)
    entrar(sitio, 'admin@example.test')
    assert sitio.cookies.get(acceso.COOKIE) != anterior
    with acceso.db() as con:
        assert con.execute('SELECT 1 FROM sesiones WHERE token=?', (acceso._digest(anterior),)).fetchone() is None


def test_instalacion_concurrente_solo_crea_un_administrador(sitio):
    sitio.get('/api/auth/sesion')
    token = (acceso.carpeta() / 'clave-inicial.txt').read_text().strip()
    # No se inicia el lifespan del motor para esta prueba de concurrencia.
    def intentar_sin_motor(i):
        c = TestClient(app)
        try:
            return c.post('/api/auth/configurar', json={'token': token, 'nombre': 'Admin', 'correo': f'admin{i}@example.test', 'clave': CLAVE}).status_code
        finally:
            c.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(intentar_sin_motor, (1, 2)))
    assert resultados.count(200) == 1
    assert all(r in (200, 403, 409) for r in resultados)
    with acceso.db() as con:
        assert con.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0] == 1


def test_sesiones_persisten_y_la_actividad_no_guarda_secretos(sitio):
    instalar(sitio)
    cuenta(sitio, 'consulta')
    acceso._inicializadas.clear()  # Simula una nueva instancia de la aplicación con la misma base.
    assert sitio.get('/api/usuarios').status_code == 200
    assert not (acceso.carpeta() / 'clave-inicial.txt').exists()
    registros = sitio.get('/api/usuarios/actividad').json()
    assert any(a['accion'] == 'crear_usuario' and a['nombre'] == 'Admin' for a in registros)
    assert CLAVE not in str(registros) and sitio.cookies.get(acceso.COOKIE) not in str(registros)


def test_no_hay_elevacion_mediante_payload_y_claves_cortas(sitio):
    instalar(sitio)
    assert sitio.post('/api/usuarios', json={'nombre': 'Corta', 'correo': 'corta@example.test', 'clave': 'corta'}).status_code == 422
    cuenta(sitio, 'consulta')
    r = sitio.post('/api/auth/entrar', json={'correo': 'consulta@example.test', 'clave': CLAVE, 'rol': 'administrador', 'permisos': ['usuarios.gestionar']})
    assert r.status_code == 200 and r.json()['usuario']['rol'] == 'consulta'
    assert sitio.get('/api/usuarios', headers={'X-Role': 'administrador'}).status_code == 403
