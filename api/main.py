"""API de la consola de negocio.  Ejecutar:  .venv/bin/uvicorn api.main:app --port 8000

El borrador de configuracion viaja como JSON (el mismo esquema de nba/config.py); la API valida, calcula y guarda."""
import hmac
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import APIRouter, Depends, FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import servicio as s
from api import acceso

@asynccontextmanager
async def _vida(_: FastAPI):
    acceso._preparar()
    threading.Thread(target=s.precalentar, daemon=True).start()   # el primer calculo corre mientras se abre la pagina
    yield


app = FastAPI(title="Orquestador NBA", version="1.0", lifespan=_vida)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


@app.middleware("http")
async def proteger_peticion(request: Request, siguiente):
    api = request.url.path.startswith("/api/")
    if api and request.method not in ("GET", "HEAD", "OPTIONS"):
        origen = request.headers.get("origin")
        permitidos = {str(request.base_url).rstrip("/"), "http://localhost:5173", "http://127.0.0.1:5173"}
        if request.headers.get("sec-fetch-site") == "cross-site" or (origen and origen not in permitidos):
            return JSONResponse(status_code=403, content={"mensaje": "Origen de la petición no permitido."})
        if request.url.path not in ("/api/auth/entrar", "/api/auth/configurar"):
            sesion = acceso.obtener_sesion(request)
            if sesion and not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode(), sesion["csrf_token"].encode()):
                return JSONResponse(status_code=403, content={"mensaje": "La sesión de esta página cambió. Recarga para continuar."})
    response = await siguiente(request)
    if api:
        response.headers["Cache-Control"] = "private, no-store"
        if request.method not in ("GET", "HEAD", "OPTIONS") and response.status_code < 400 and hasattr(request.state, "usuario"):
            # La actividad solo contiene la acción y la ruta, nunca cuerpos con claves.
            ruta = request.scope.get("route")
            if ruta and ruta.name in {"aplicar", "restaurar_inicial", "escenario_nuevo", "escenario_borrar", "escenarios_comparar", "sensibilidad", "base_ruta", "base_subir"}:
                acceso.auditar(request.state.usuario, ruta.name, request.url.path)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(s.ErrorNegocio)
async def _error_negocio(_: Request, e: s.ErrorNegocio):
    return JSONResponse(status_code=e.codigo, content={"mensaje": e.mensaje, "detalle": e.detalle})


class Borrador(BaseModel):
    config: Dict[str, Any]


class Aplicar(Borrador):
    etiqueta: str = "Ajuste de configuración"


class Llamadas(Borrador):
    valor: int


class Calificaciones(Borrador):
    campana: str
    permitidas: List[str]


class Ruta(BaseModel):
    ruta: str


privada = APIRouter(dependencies=[Depends(acceso.autorizar)])


# ---- estado y configuracion
@privada.get("/api/estado")
def estado():
    return s.estado()


@privada.get("/api/config")
def config_vigente():
    return s.info_configuracion()


@privada.post("/api/config/revisar")
def revisar(b: Borrador):
    return s.revisar_borrador(b.config)


@privada.post("/api/borrador/llamadas")
def borrador_llamadas(b: Llamadas):
    return {"config": s.fijar_llamadas(b.config, b.valor)}


@privada.post("/api/borrador/calificaciones")
def borrador_calificaciones(b: Calificaciones):
    return {"config": s.fijar_calificaciones(b.config, b.campana, b.permitidas)}


@privada.post("/api/config/restaurar-inicial")
def restaurar_inicial():
    return s.restaurar_inicial()


# ---- tablero, impacto, aplicar
@privada.get("/api/tablero")
def tablero():
    return s.tablero_vigente()


@privada.post("/api/impacto")
def impacto(b: Borrador):
    return s.impacto(b.config)


@privada.post("/api/aplicar")
def aplicar(b: Aplicar):
    return s.aplicar(b.config, b.etiqueta)


@privada.get("/api/parrilla.csv")
def parrilla():
    return Response(s.parrilla_csv(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=parrilla.csv"})


# ---- escenarios guardados, trabajos y sensibilidad
class NuevoEscenario(Borrador):
    nombre: str = Field(max_length=200)
    tipo: Literal['cupos', 'reglas', 'prioridad', 'libre'] = 'libre'
    objetivo: str = Field(default='', max_length=2000)


class Comparar(BaseModel):
    ids: List[str] = Field(min_length=1, max_length=4)


class Sensibilidad(BaseModel):
    canal: str


@privada.get("/api/escenarios")
def escenarios():
    return s.listar_escenarios()


@privada.post("/api/escenarios")
def escenario_nuevo(b: NuevoEscenario):
    return s.guardar_escenario(b.nombre, b.config, b.tipo, b.objetivo)


@privada.post("/api/escenarios/comparar")
def escenarios_comparar(b: Comparar):
    return s.comparar_escenarios(b.ids)


@privada.get("/api/escenarios/{eid}")
def escenario(eid: str):
    return {"config": s.cargar_escenario(eid)}


@privada.delete("/api/escenarios/{eid}")
def escenario_borrar(eid: str):
    return s.borrar_escenario(eid)


@privada.get("/api/trabajos/{tid}")
def trabajo(tid: str):
    return s.estado_trabajo(tid)


@privada.post("/api/sensibilidad")
def sensibilidad(b: Sensibilidad):
    return s.sensibilidad(b.canal)


# ---- versiones
@privada.get("/api/versiones")
def versiones():
    return s.listar_versiones()


@privada.get("/api/versiones/{nombre}")
def version(nombre: str):
    return {"config": s.cargar_version(nombre)}


# ---- cliente
@privada.get("/api/situaciones")
def situaciones():
    return s.situaciones()


@privada.get("/api/clientes")
def clientes(situacion: str = "", limite: int = 300):
    return s.clientes_de(situacion, min(limite, 1000))


@privada.get("/api/cliente/{cid}")
def cliente(cid: str):
    return s.cliente(cid)


# ---- base de datos
@privada.get("/api/base")
def base():
    return s.info_base()


@privada.post("/api/base/ruta")
def base_ruta(r: Ruta):
    return s.usar_ruta(r.ruta)


@privada.post("/api/base/subir")
async def base_subir(archivo: UploadFile = File(...)):
    return s.subir_base(await archivo.read())


app.include_router(acceso.router)
app.include_router(acceso.usuarios)
app.include_router(privada)


# ---- interfaz compilada (produccion): se sirve web/dist si existe
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def interfaz(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):          # una ruta de API inexistente es un 404, no la pagina
            return JSONResponse(status_code=404, content={"mensaje": "Ruta de API inexistente.", "detalle": []})
        archivo = (DIST / ruta).resolve()
        if archivo != DIST.resolve() and DIST.resolve() not in archivo.parents:
            return JSONResponse(status_code=404, content={"mensaje": "Archivo no disponible."})
        return FileResponse(archivo if ruta and archivo.is_file() else DIST / "index.html")
