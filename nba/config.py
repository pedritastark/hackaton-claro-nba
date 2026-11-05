"""Carga y validacion de la configuracion (config/*.yaml). Todo numero de negocio vive aqui."""
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator

OPERADORES = ["==", "!=", "<", "<=", ">", ">=", "en", "no_en", "contiene", "no_contiene"]


class ConfigError(ValueError):
    pass


class Campana(BaseModel):
    id: str
    nombre: str
    producto: str
    columna_score: str
    valor_negocio: float
    canales_permitidos: List[str]
    objetivo: str = ""
    vigencia_inicio: Optional[date] = None
    vigencia_fin: Optional[date] = None
    activa: bool = True


class Regla(BaseModel):
    id: str
    nombre: str
    tipo: Literal["elegibilidad", "canal"]
    alcance_nivel: Literal["global", "campana", "producto", "objetivo", "canal"] = "global"
    alcance_valores: List[str] = Field(default_factory=list)
    atributo: str
    operador: Literal[tuple(OPERADORES)]  # type: ignore
    valor: Any
    accion: Literal["excluir"] = "excluir"
    activa: bool = True


class Canal(BaseModel):
    id: str
    columna_score: str
    cupo: int = Field(ge=0)
    max_productos: int = Field(ge=1)


class Pesos(BaseModel):
    score_producto: float = 0.6
    valor_negocio: float = 0.2
    jerarquia: float = 0.2


CRITERIOS_DESEMPATE = ("score_producto", "valor_negocio", "jerarquia")


class Priorizacion(BaseModel):
    modo: Literal["ponderado", "jerarquia_estricta"] = "ponderado"
    jerarquia: List[str]
    pesos: Pesos = Pesos()
    umbral_score_producto: float = 0.35
    # criterios, en orden, para ordenar dos campanas que empatan en puntaje
    desempate: List[str] = Field(default_factory=lambda: ["score_producto", "valor_negocio"])

    @model_validator(mode="after")
    def _validar(self):
        suma = self.pesos.score_producto + self.pesos.valor_negocio + self.pesos.jerarquia
        if abs(suma - 1.0) > 1e-6:
            raise ConfigError(f"los pesos de priorizacion deben sumar 1 (suman {suma:.3f})")
        malos = [d for d in self.desempate if d not in CRITERIOS_DESEMPATE]
        if malos:
            raise ConfigError(f"criterios de desempate desconocidos {malos}; validos: {list(CRITERIOS_DESEMPATE)}")
        return self
    alpha: float = Field(0.0, ge=0, le=1)  # 0 = maximiza valor esperado; 1 = solo jerarquia
    # Algoritmo optimo: utilidad = score_producto^peso_modelo * score_canal * valor^peso_valor.
    # 1 y 1 = valor esperado puro (la metrica del reto). `pesos` (arriba) solo rige la linea base codiciosa.
    peso_modelo: float = Field(1.0, ge=0, le=5)
    peso_valor: float = Field(1.0, ge=0, le=5)


class Politica(BaseModel):
    max_contactos_semana: int = 3
    columna_contactos_semana: str = "contactos_semana_actual"
    canales_por_cliente: int = 1

    @model_validator(mode="after")
    def _un_canal(self):
        if self.canales_por_cliente != 1:
            raise ConfigError("politica_contacto.canales_por_cliente distinto de 1 no esta soportado: "
                              "el motor asigna un solo canal por cliente en cada corrida (restriccion R13)")
        return self


class Asignacion(BaseModel):
    algoritmo: Literal["optimo", "codicioso"] = "optimo"
    criterio_canal: Literal["score_canal", "orden_preferencia"] = "score_canal"
    orden_preferencia: List[str] = Field(default_factory=list)
    umbral_score_canal: float = 0.25


class Config(BaseModel):
    fecha_corrida: date
    campanas: List[Campana]
    reglas: List[Regla]
    canales: List[Canal]
    priorizacion: Priorizacion
    politica_contacto: Politica = Politica()
    asignacion: Asignacion = Asignacion()

    @model_validator(mode="after")
    def _coherencia(self):
        ids = [c.id for c in self.campanas]
        if len(set(ids)) != len(ids):
            raise ConfigError("ids de campana duplicados")
        canales = {c.id for c in self.canales}
        for c in self.campanas:
            malos = set(c.canales_permitidos) - canales
            if malos:
                raise ConfigError(f"{c.id}: canales inexistentes {sorted(malos)}")
        rids = [r.id for r in self.reglas]
        if len(set(rids)) != len(rids):
            raise ConfigError("ids de regla duplicados")
        productos = {c.producto for c in self.campanas}
        objetivos = {c.objetivo for c in self.campanas}
        for r in self.reglas:
            if r.alcance_nivel == "campana" and not set(r.alcance_valores) <= set(ids):
                raise ConfigError(f"{r.id}: campanas inexistentes {r.alcance_valores}")
            if r.alcance_nivel == "producto" and not set(r.alcance_valores) <= productos:
                raise ConfigError(f"{r.id}: productos inexistentes {r.alcance_valores}")
            if r.alcance_nivel == "objetivo" and not set(r.alcance_valores) <= objetivos:
                raise ConfigError(f"{r.id}: objetivos inexistentes {r.alcance_valores}")
            if r.alcance_nivel == "canal" and not set(r.alcance_valores) <= canales:
                raise ConfigError(f"{r.id}: canales inexistentes {r.alcance_valores}")
            if r.operador in ("en", "no_en") and not isinstance(r.valor, list):
                raise ConfigError(f"{r.id}: operador '{r.operador}' requiere lista")
        return self

    # ayudas
    @staticmethod
    def regla_aplica(r, c) -> bool:
        """Si una regla de elegibilidad aplica a la campana c, segun su alcance."""
        n = r.alcance_nivel
        if n == "global":
            return True
        if n == "campana":
            return c.id in r.alcance_valores
        if n == "producto":
            return c.producto in r.alcance_valores
        if n == "objetivo":
            return c.objetivo in r.alcance_valores
        return False

    def campanas_vigentes(self) -> List[Campana]:
        f = self.fecha_corrida
        return [c for c in self.campanas if c.activa
                and (c.vigencia_inicio is None or c.vigencia_inicio <= f)
                and (c.vigencia_fin is None or f <= c.vigencia_fin)]

    def nivel_jerarquia(self) -> Dict[str, float]:
        """1.0 para la primera campana, bajando linealmente a 0.0 para la ultima.
        Campanas nuevas no listadas van al final."""
        orden = [i for i in self.priorizacion.jerarquia if i in {c.id for c in self.campanas}]
        orden += [c.id for c in self.campanas if c.id not in orden]
        n = len(orden)
        return {cid: (1.0 if n == 1 else 1 - k / (n - 1)) for k, cid in enumerate(orden)}


def cargar(directorio="config") -> Config:
    d = Path(directorio)
    try:
        datos = {}
        for nombre in ("parametros", "campanas", "reglas"):
            datos.update(yaml.safe_load((d / f"{nombre}.yaml").read_text(encoding="utf-8")))
        return Config(**datos)
    except FileNotFoundError as e:
        raise ConfigError(f"falta archivo de configuracion: {e.filename}")


def guardar(cfg: Config, directorio="config"):
    d = Path(directorio)
    d.mkdir(parents=True, exist_ok=True)
    dump = cfg.model_dump(mode="json")
    dump["priorizacion"]["pesos"] = dict(dump["priorizacion"]["pesos"])
    params = {k: dump[k] for k in ("fecha_corrida", "canales", "priorizacion", "politica_contacto", "asignacion")}
    for nombre, datos in (("parametros", params), ("campanas", {"campanas": dump["campanas"]}),
                          ("reglas", {"reglas": dump["reglas"]})):
        (d / f"{nombre}.yaml").write_text(
            yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
