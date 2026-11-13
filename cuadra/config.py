"""Valores fijos del flujo. Todo lo configurable vive aquí."""

import os
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "datos"
DIR_AYUDAS = RAIZ / "ayudas"
DIR_NOTAS = RAIZ / "notas"
DIR_CACHE = RAIZ / "cache"
DIR_SALIDA = Path(os.environ.get("CUADRA_DIR_SALIDA") or RAIZ / "salida")

# «Hoy» según el enunciado del caso.
FECHA_CORRIDA = date(2026, 10, 31)

# Nadie tardó más de 4 días entre dos pasos; a partir de 3 días sin eventos casi nadie avanza solo.
DIAS_ATASCADO = 3
DIAS_RECIENTE_MAX = 14

# La semilla del reparto se eligió con una regla fija, antes de enviar nada: la primera candidata cuya
# prueba A/A (el mismo reparto aplicado a julio y agosto, donde nadie recibió correo) da p > UMBRAL_AA.
# La primera dejaba, por azar, menos autónomos de canal orgánico en un grupo (p = 0,01); la segunda no
# llegaba al umbral (p = 0,14).
SEMILLAS_CANDIDATAS = ["cuadra-2026-10", "cuadra-2026-10-a", "cuadra-2026-10-b", "cuadra-2026-10-c"]
UMBRAL_AA = 0.2
SEMILLA = "cuadra-2026-10-b"
PROPORCION_TRATAMIENTO = 0.5
VENTANA_DIAS = 14

MODELO_POR_DEFECTO = "claude-opus-5-5"


def modelo_configurado(ruta_env: Path = RAIZ / ".env") -> str:
    """El modelo sale de la variable CUADRA_MODELO, del archivo .env o, si no, del valor por defecto."""
    return (
        os.environ.get("CUADRA_MODELO")
        or dotenv_values(ruta_env).get("CUADRA_MODELO")
        or MODELO_POR_DEFECTO
    )


MODELO = modelo_configurado()

PASOS = [
    "registro",
    "configuro_empresa",
    "creo_cliente",
    "emitio_primera_factura",
    "emitio_5_facturas",
]
