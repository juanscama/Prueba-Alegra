"""Valores fijos del flujo. Todo lo configurable vive aquí."""

import os
from datetime import date
from pathlib import Path

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

SEMILLA = "cuadra-2026-10"
PROPORCION_TRATAMIENTO = 0.5
VENTANA_DIAS = 14

MODELO = os.environ.get("CUADRA_MODELO") or "claude-opus-5-5"

PASOS = [
    "registro",
    "configuro_empresa",
    "creo_cliente",
    "emitio_primera_factura",
    "emitio_5_facturas",
]
