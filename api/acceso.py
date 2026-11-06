"""Identidad local y permisos de la consola. Los secretos nunca forman parte de config/."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
COOKIE = "nba_sesion"
DURACION = 8 * 60 * 60
ROLES = {
    "administrador": {"nombre": "Administrador", "permisos": ["consultar", "config.editar", "config.aplicar", "laboratorios.gestionar", "laboratorios.ejecutar", "base.gestionar", "usuarios.gestionar", "parrilla.exportar"]},
    "editor": {"nombre": "Editor", "permisos": ["consultar", "config.editar", "config.aplicar", "laboratorios.gestionar", "laboratorios.ejecutar", "parrilla.exportar"]},
    "analista": {"nombre": "Analista de pruebas", "permisos": ["consultar", "laboratorios.gestionar", "laboratorios.ejecutar", "parrilla.exportar"]},
    "consulta": {"nombre": "Consulta", "permisos": ["consultar"]},
}
Rol = Literal["administrador", "editor", "analista", "consulta"]
# Una ruta nueva de negocio debe declarar su permiso aquí antes de estar disponible.
PERMISOS_RUTAS = dict.fromkeys([
    "estado", "config_vigente", "revisar", "tablero", "escenarios", "escenario", "trabajo",
    "versiones", "version", "situaciones", "clientes", "cliente", "base",
], "consultar")
PERMISOS_RUTAS.update({
    "borrador_llamadas": "config.editar", "borrador_calificaciones": "config.editar",
    "restaurar_inicial": "base.gestionar", "impacto": "laboratorios.ejecutar", "aplicar": "config.aplicar",
    "parrilla": "parrilla.exportar", "escenario_nuevo": "laboratorios.gestionar",
    "escenario_borrar": "laboratorios.gestionar", "escenarios_comparar": "laboratorios.ejecutar",
    "sensibilidad": "laboratorios.ejecutar", "simulacion_cliente": "laboratorios.ejecutar",
    "base_ruta": "base.gestionar", "base_subir": "base.gestionar",
})
_candado = threading.Lock()
_inicializadas = set()


def carpeta():
    return Path(os.environ.get("NBA_AUTH_DIR", str(ROOT / "var" / "acceso"))).resolve()


def _digest(valor):
    return hashlib.sha256(valor.encode()).hexdigest()


def _preparar():
    directorio = carpeta()
    archivo = directorio / "usuarios.sqlite3"
    with _candado:
        if archivo in _inicializadas and archivo.exists():
            return archivo
        directorio.mkdir(mode=0o700, parents=True, exist_ok=True)
        con = sqlite3.connect(str(archivo), timeout=15)
        try:
            con.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS usuarios (
                    id TEXT PRIMARY KEY, nombre TEXT NOT NULL, correo TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    clave TEXT NOT NULL, rol TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1,
                    creado REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sesiones (
                    token TEXT PRIMARY KEY, usuario TEXT NOT NULL, csrf TEXT NOT NULL, vence REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intentos (clave TEXT PRIMARY KEY, cantidad INTEGER NOT NULL, inicio REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS actividad (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha REAL NOT NULL, usuario TEXT,
                    nombre TEXT NOT NULL, accion TEXT NOT NULL, recurso TEXT NOT NULL);
            """)
            con.execute("BEGIN IMMEDIATE")
            if not con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
                existente = con.execute("SELECT valor FROM ajustes WHERE clave='instalacion'").fetchone()
                if not existente:
                    token = os.environ.get("NBA_SETUP_TOKEN") or secrets.token_urlsafe(32)
                    if len(token) < 24:
                        raise RuntimeError("NBA_SETUP_TOKEN debe tener al menos 24 caracteres.")
                    clave = directorio / "clave-inicial.txt"
                    # Solo el operador local puede leer la clave; nunca se sirve por HTTP.
                    fd = os.open(str(clave), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w") as f:
                        f.write(token + "\n")
                    con.execute("INSERT INTO ajustes VALUES ('instalacion', ?)", (_digest(token),))
            con.commit()
        finally:
            con.close()
        archivo.chmod(0o600)
        _inicializadas.add(archivo)
    return archivo


@contextmanager
def db():
    con = sqlite3.connect(str(_preparar()), timeout=15)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def hash_clave(clave, salt=None):
    salt = salt or secrets.token_hex(16)
    valor = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64 * 1024 * 1024).hex()
    return "scrypt$" + salt + "$" + valor


@lru_cache(maxsize=1)
def _clave_ficticia():
    return hash_clave("Comprobacion constante de acceso", "0" * 32)


def comprobar_clave(clave, guardada):
    try:
        algoritmo, salt, _ = guardada.split("$")
        return algoritmo == "scrypt" and hmac.compare_digest(hash_clave(clave, salt), guardada)
    except (ValueError, TypeError):
        return False


def publico(u):
    return {"id": u["id"], "nombre": u["nombre"], "correo": u["correo"], "rol": u["rol"],
            "activo": bool(u["activo"]), "creado": u["creado"], "permisos": ROLES[u["rol"]]["permisos"]}


def registrar(con, usuario, accion, recurso=""):
    con.execute("INSERT INTO actividad (fecha, usuario, nombre, accion, recurso) VALUES (?, ?, ?, ?, ?)",
                (time.time(), usuario["id"], usuario["nombre"], accion, recurso))


def auditar(usuario, accion, recurso=""):
    with db() as con:
        registrar(con, usuario, accion, recurso)


def _limitar(con, clave, limite):
    ahora = time.time()
    con.execute("DELETE FROM intentos WHERE inicio < ?", (ahora - 900,))
    con.execute("INSERT INTO intentos VALUES (?, 1, ?) ON CONFLICT(clave) DO UPDATE SET cantidad=cantidad+1", (clave, ahora))
    fila = con.execute("SELECT cantidad FROM intentos WHERE clave=?", (clave,)).fetchone()
    return fila[0] <= limite


def limitar(request, cuenta):
    ip = request.client.host if request.client else "local"
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        permitido_ip = _limitar(con, "ip:" + _digest(ip), 60)
        permitido_cuenta = _limitar(con, "cuenta:" + _digest(cuenta.lower()), 10)
    if not permitido_ip or not permitido_cuenta:
        raise HTTPException(429, "Demasiados intentos. Inténtalo de nuevo dentro de 15 minutos.", headers={"Retry-After": "900"})


def obtener_sesion(request):
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        return None
    with db() as con:
        fila = con.execute("SELECT u.*, s.csrf FROM sesiones s JOIN usuarios u ON s.usuario=u.id WHERE s.token=? AND s.vence>? AND u.activo=1", (_digest(token), time.time())).fetchone()
    if fila is None:
        return None
    return {"usuario": publico(fila), "csrf_token": fila["csrf"]}


def actual(request: Request):
    sesion = obtener_sesion(request)
    if sesion is None:
        raise HTTPException(401, "Inicia sesión para continuar.")
    request.state.usuario = sesion["usuario"]
    return sesion["usuario"]


def administrador(usuario=Depends(actual)):
    if "usuarios.gestionar" not in usuario["permisos"]:
        raise HTTPException(403, "Tu rol no permite administrar usuarios.")
    return usuario


def autorizar(request: Request, usuario=Depends(actual)):
    permiso = PERMISOS_RUTAS.get(request.scope["route"].name)
    if not permiso or permiso not in usuario["permisos"]:
        raise HTTPException(403, "Tu rol no permite realizar esta acción.")
    return usuario


def nueva_sesion(con, usuario, request, response):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    anterior = request.cookies.get(COOKIE)
    if anterior:
        con.execute("DELETE FROM sesiones WHERE token=?", (_digest(anterior),))
    con.execute("DELETE FROM sesiones WHERE vence<=?", (time.time(),))
    con.execute("INSERT INTO sesiones VALUES (?, ?, ?, ?)", (_digest(token), usuario["id"], csrf, time.time() + DURACION))
    response.set_cookie(COOKIE, token, max_age=DURACION, httponly=True, samesite="strict", path="/api",
                        secure=os.environ.get("NBA_COOKIE_SECURE") == "1" or request.url.scheme == "https")
    return {"usuario": publico(usuario), "csrf_token": csrf, "requiere_configuracion": False}


class Credenciales(BaseModel):
    correo: str = Field(max_length=254)
    clave: str = Field(max_length=256)


class NuevoUsuario(Credenciales):
    nombre: str = Field(min_length=1, max_length=120)
    rol: Rol = "consulta"
    clave: str = Field(min_length=15, max_length=256)


class Instalacion(NuevoUsuario):
    token: str = Field(max_length=256)


class EditarUsuario(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    rol: Rol
    activo: bool


class CambiarClave(BaseModel):
    actual: str = Field(max_length=256)
    nueva: str = Field(min_length=15, max_length=256)


class RestablecerClave(BaseModel):
    nueva: str = Field(min_length=15, max_length=256)


def _datos_usuario(b):
    correo = b.correo.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", correo) or not b.nombre.strip():
        raise HTTPException(422, "Escribe un nombre y un correo válidos.")
    return correo, b.nombre.strip()


router = APIRouter(prefix="/api/auth", tags=["Acceso"])
usuarios = APIRouter(prefix="/api/usuarios", tags=["Usuarios"], dependencies=[Depends(administrador)])


@router.get("/sesion")
def sesion(request: Request):
    with db() as con:
        configurar = not bool(con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone())
    return {"requiere_configuracion": configurar, "usuario": None, "csrf_token": None, **(obtener_sesion(request) or {})}


@router.post("/configurar")
def configurar(b: Instalacion, request: Request, response: Response):
    limitar(request, "instalacion")
    correo, nombre = _datos_usuario(b)
    with db() as con:
        guardado = con.execute("SELECT valor FROM ajustes WHERE clave='instalacion'").fetchone()
        if not guardado or not hmac.compare_digest(guardado[0], _digest(b.token)):
            raise HTTPException(403, "La clave de instalación no es válida o ya fue utilizada.")
    clave = hash_clave(b.clave)
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            raise HTTPException(409, "El administrador inicial ya fue creado.")
        uid = uuid.uuid4().hex
        con.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, 'administrador', 1, ?)", (uid, nombre, correo, clave, time.time()))
        con.execute("DELETE FROM ajustes WHERE clave='instalacion'")
        u = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        registrar(con, u, "administrador_inicial")
        resultado = nueva_sesion(con, u, request, response)
    (carpeta() / "clave-inicial.txt").unlink(missing_ok=True)
    return resultado


@router.post("/entrar")
def entrar(b: Credenciales, request: Request, response: Response):
    correo = b.correo.strip().lower()
    limitar(request, correo)
    with db() as con:
        u = con.execute("SELECT * FROM usuarios WHERE correo=?", (correo,)).fetchone()
    coincide = comprobar_clave(b.clave, u["clave"] if u else _clave_ficticia())
    if not coincide or not u or not u["activo"]:
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    with db() as con:
        # Volver a leer evita iniciar una sesión si se revocó la cuenta durante el hash.
        con.execute("BEGIN IMMEDIATE")
        vigente = con.execute("SELECT * FROM usuarios WHERE id=? AND activo=1 AND clave=?", (u["id"], u["clave"])).fetchone()
        if not vigente:
            raise HTTPException(401, "Correo o contraseña incorrectos.")
        con.execute("DELETE FROM intentos WHERE clave=?", ("cuenta:" + _digest(correo),))
        registrar(con, vigente, "inicio_sesion")
        return nueva_sesion(con, vigente, request, response)


@router.post("/salir")
def salir(request: Request, response: Response, usuario=Depends(actual)):
    with db() as con:
        con.execute("DELETE FROM sesiones WHERE token=?", (_digest(request.cookies.get(COOKIE, "")),))
        registrar(con, usuario, "cierre_sesion")
    response.delete_cookie(COOKIE, path="/api", httponly=True, samesite="strict")
    return {"ok": True}


@router.post("/clave")
def cambiar_clave(b: CambiarClave, request: Request, usuario=Depends(actual)):
    limitar(request, "clave:" + usuario["id"])
    with db() as con:
        u = con.execute("SELECT * FROM usuarios WHERE id=?", (usuario["id"],)).fetchone()
    if not comprobar_clave(b.actual, u["clave"]):
        raise HTTPException(403, "La contraseña actual no es correcta.")
    nueva = hash_clave(b.nueva)
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        cambio = con.execute("UPDATE usuarios SET clave=? WHERE id=? AND clave=?", (nueva, usuario["id"], u["clave"]))
        if cambio.rowcount != 1:
            raise HTTPException(409, "La cuenta cambió. Inicia sesión de nuevo.")
        con.execute("DELETE FROM sesiones WHERE usuario=?", (usuario["id"],))
        registrar(con, usuario, "cambio_clave")
    return {"ok": True}


@usuarios.get("")
def listar_usuarios():
    with db() as con:
        return [publico(u) for u in con.execute("SELECT * FROM usuarios ORDER BY creado")]


@usuarios.get("/roles")
def roles():
    return [{"id": k, **v} for k, v in ROLES.items()]


@usuarios.get("/actividad")
def actividad():
    with db() as con:
        return [dict(f) for f in con.execute("SELECT * FROM actividad ORDER BY id DESC LIMIT 100")]


@usuarios.post("")
def crear_usuario(b: NuevoUsuario, actor=Depends(administrador)):
    correo, nombre = _datos_usuario(b)
    clave = hash_clave(b.clave)
    with db() as con:
        uid = uuid.uuid4().hex
        try:
            con.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, 1, ?)", (uid, nombre, correo, clave, b.rol, time.time()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Ya existe una cuenta con ese correo.")
        registrar(con, actor, "crear_usuario", uid)
        return publico(con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone())


@usuarios.patch("/{uid}")
def editar_usuario(uid: str, b: EditarUsuario, actor=Depends(administrador)):
    if not b.nombre.strip():
        raise HTTPException(422, "Escribe un nombre válido.")
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        u = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not u:
            raise HTTPException(404, "No existe ese usuario.")
        if uid == actor["id"] and (not b.activo or b.rol != u["rol"]):
            raise HTTPException(409, "No puedes quitarte tu propio acceso de administrador.")
        if u["activo"] and u["rol"] == "administrador" and (not b.activo or b.rol != "administrador"):
            total = con.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1 AND rol='administrador'").fetchone()[0]
            if total <= 1:
                raise HTTPException(409, "Debe quedar al menos un administrador activo.")
        con.execute("UPDATE usuarios SET nombre=?, rol=?, activo=? WHERE id=?", (b.nombre.strip(), b.rol, int(b.activo), uid))
        if b.rol != u["rol"] or b.activo != bool(u["activo"]):
            con.execute("DELETE FROM sesiones WHERE usuario=?", (uid,))
        registrar(con, actor, "editar_usuario", uid)
        return publico(con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone())


@usuarios.post("/{uid}/clave")
def restablecer_clave(uid: str, b: RestablecerClave, actor=Depends(administrador)):
    if uid == actor["id"]:
        raise HTTPException(409, "Cambia tu contraseña desde Mi cuenta usando tu contraseña actual.")
    clave = hash_clave(b.nueva)
    with db() as con:
        cambio = con.execute("UPDATE usuarios SET clave=? WHERE id=?", (clave, uid))
        if cambio.rowcount != 1:
            raise HTTPException(404, "No existe ese usuario.")
        con.execute("DELETE FROM sesiones WHERE usuario=?", (uid,))
        registrar(con, actor, "restablecer_clave", uid)
    return {"ok": True}
