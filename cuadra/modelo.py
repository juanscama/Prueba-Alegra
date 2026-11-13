"""Única puerta al modelo. Cada respuesta se guarda en cache/ para repetir la corrida sin red ni clave."""

import json
import os
import threading
from hashlib import sha256
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from cuadra.config import DIR_CACHE, MODELO, RAIZ

MODOS = ("auto", "repeticion", "vivo")


class SinCache(Exception):
    """Modo repetición y la respuesta no está guardada."""


class Rechazo(Exception):
    """El modelo declinó responder o no devolvió una salida válida."""


class SinClave(ValueError):
    """Se pidió volver a llamar al modelo y no hay clave con la que hacerlo."""


class ErrorModelo(Exception):
    """La llamada al modelo falló (red, cuota, clave)."""


def _cargar_env() -> None:
    load_dotenv(RAIZ / ".env")


def hay_clave() -> bool:
    _cargar_env()
    return any(os.environ.get(v, "").strip() for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))


class Modelo:
    def __init__(self, dir_cache: Path = DIR_CACHE, modo: str = "auto", forzar: bool = False, cliente=None):
        if modo not in MODOS:
            raise ValueError(f"modo debe ser uno de {MODOS}")
        if modo == "auto":
            modo = "vivo" if hay_clave() else "repeticion"
        if forzar and cliente is None and not hay_clave():
            raise SinClave(
                "--forzar vuelve a llamar al modelo y necesita una clave: copia .env.example a .env y pon "
                "tu ANTHROPIC_API_KEY. Sin --forzar, el flujo corre desde las respuestas guardadas."
            )
        self.dir_cache = Path(dir_cache)
        self.modo = modo
        self.forzar = forzar
        self.llamadas_reales = 0
        self._cliente = cliente
        self._candado = threading.Lock()

    def _ruta(self, peticion: dict, esquema: type[BaseModel]) -> Path:
        contenido = json.dumps(
            {**peticion, "esquema": esquema.model_json_schema()}, sort_keys=True, ensure_ascii=False
        )
        clave = sha256(contenido.encode("utf-8")).hexdigest()
        return self.dir_cache / peticion["tarea"] / f"{clave[:16]}.json"

    def _cliente_real(self):
        with self._candado:
            if self._cliente is None:
                _cargar_env()
                self._cliente = anthropic.Anthropic(max_retries=4)
            return self._cliente

    def pedir(self, *, tarea: str, sistema: str, usuario: str, esquema: type[BaseModel]) -> BaseModel:
        peticion = {"modelo": MODELO, "tarea": tarea, "sistema": sistema, "usuario": usuario}
        ruta = self._ruta(peticion, esquema)
        if ruta.is_file() and not self.forzar:
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            return esquema.model_validate(guardado["respuesta"])
        if self.modo == "repeticion" or (self._cliente is None and not hay_clave()):
            raise SinCache(f"No hay respuesta guardada para la tarea «{tarea}» ni clave para pedirla")

        respuesta = self._llamar(sistema, usuario, esquema)
        with self._candado:
            self.llamadas_reales += 1
        salida = respuesta.parsed_output
        if respuesta.stop_reason == "refusal" or salida is None:
            raise Rechazo(f"El modelo declinó la tarea «{tarea}»")

        uso = getattr(respuesta, "usage", None)
        registro = {
            "peticion": peticion,
            "respuesta": salida.model_dump(mode="json"),
            "uso": {
                "tokens_entrada": getattr(uso, "input_tokens", None),
                "tokens_salida": getattr(uso, "output_tokens", None),
            },
        }
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return salida

    def _llamar(self, sistema: str, usuario: str, esquema: type[BaseModel]):
        cliente = self._cliente_real()
        try:
            # Salida estructurada validada contra el esquema. Si el modelo principal declina por una
            # salvaguarda, la API reintenta sola en el modelo de respaldo.
            return cliente.beta.messages.parse(
                model=MODELO,
                max_tokens=16000,
                system=sistema,
                messages=[{"role": "user", "content": usuario}],
                output_format=esquema,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as error:
            raise ErrorModelo(f"{type(error).__name__}: {error}") from error
        except (ValidationError, json.JSONDecodeError) as error:
            # Salida truncada o que no cumple el esquema: se trata igual que si el modelo hubiera declinado.
            raise Rechazo(f"El modelo devolvió una salida que no cumple el esquema: {error}") from error
