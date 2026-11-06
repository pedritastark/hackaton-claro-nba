"""API de la consola de negocio.  Ejecutar:  .venv/bin/uvicorn api.main:app --port 8000

El borrador de configuracion viaja como JSON (el mismo esquema de nba/config.py); la API valida, calcula y guarda."""
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import servicio as s

@asynccontextmanager
async def _vida(_: FastAPI):
    threading.Thread(target=s.precalentar, daemon=True).start()   # el primer calculo corre mientras se abre la pagina
    yield


app = FastAPI(title="Orquestador NBA", version="1.0", lifespan=_vida)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


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


# ---- estado y configuracion
@app.get("/api/estado")
def estado():
    return s.estado()


@app.get("/api/config")
def config_vigente():
    return s.info_configuracion()


@app.post("/api/config/revisar")
def revisar(b: Borrador):
    return s.revisar_borrador(b.config)


@app.post("/api/borrador/llamadas")
def borrador_llamadas(b: Llamadas):
    return {"config": s.fijar_llamadas(b.config, b.valor)}


@app.post("/api/borrador/calificaciones")
def borrador_calificaciones(b: Calificaciones):
    return {"config": s.fijar_calificaciones(b.config, b.campana, b.permitidas)}


@app.post("/api/config/restaurar-inicial")
def restaurar_inicial():
    return s.restaurar_inicial()


# ---- tablero, impacto, aplicar
@app.get("/api/tablero")
def tablero():
    return s.tablero_vigente()


@app.post("/api/impacto")
def impacto(b: Borrador):
    return s.impacto(b.config)


@app.post("/api/aplicar")
def aplicar(b: Aplicar):
    return s.aplicar(b.config, b.etiqueta)


@app.get("/api/parrilla.csv")
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


@app.get("/api/escenarios")
def escenarios():
    return s.listar_escenarios()


@app.post("/api/escenarios")
def escenario_nuevo(b: NuevoEscenario):
    return s.guardar_escenario(b.nombre, b.config, b.tipo, b.objetivo)


@app.post("/api/escenarios/comparar")
def escenarios_comparar(b: Comparar):
    return s.comparar_escenarios(b.ids)


@app.get("/api/escenarios/{eid}")
def escenario(eid: str):
    return {"config": s.cargar_escenario(eid)}


@app.delete("/api/escenarios/{eid}")
def escenario_borrar(eid: str):
    return s.borrar_escenario(eid)


@app.get("/api/trabajos/{tid}")
def trabajo(tid: str):
    return s.estado_trabajo(tid)


@app.post("/api/sensibilidad")
def sensibilidad(b: Sensibilidad):
    return s.sensibilidad(b.canal)


# ---- versiones
@app.get("/api/versiones")
def versiones():
    return s.listar_versiones()


@app.get("/api/versiones/{nombre}")
def version(nombre: str):
    return {"config": s.cargar_version(nombre)}


# ---- cliente
@app.get("/api/situaciones")
def situaciones():
    return s.situaciones()


@app.get("/api/clientes")
def clientes(situacion: str = "", limite: int = 300):
    return s.clientes_de(situacion, min(limite, 1000))


@app.get("/api/cliente/{cid}")
def cliente(cid: str):
    return s.cliente(cid)


# ---- base de datos
@app.get("/api/base")
def base():
    return s.info_base()


@app.post("/api/base/ruta")
def base_ruta(r: Ruta):
    return s.usar_ruta(r.ruta)


@app.post("/api/base/subir")
async def base_subir(archivo: UploadFile = File(...)):
    return s.subir_base(await archivo.read())


# ---- interfaz compilada (produccion): se sirve web/dist si existe
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def interfaz(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):          # una ruta de API inexistente es un 404, no la pagina
            return JSONResponse(status_code=404, content={"mensaje": "Ruta de API inexistente.", "detalle": []})
        archivo = DIST / ruta
        return FileResponse(archivo if ruta and archivo.is_file() else DIST / "index.html")
