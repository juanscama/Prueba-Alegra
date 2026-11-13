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

# La semilla del reparto se eligió con una regla fija, antes de enviar nada: la primera candidata cuya
# prueba A/A (el mismo reparto aplicado a julio y agosto, donde nadie recibió correo) da p > UMBRAL_AA.
# Las dos primeras dejaban, por azar, menos autónomos de canal orgánico en un grupo que en el otro.
SEMILLAS_CANDIDATAS = ["cuadra-2026-10", "cuadra-2026-10-a", "cuadra-2026-10-b", "cuadra-2026-10-c"]
UMBRAL_AA = 0.2
SEMILLA = "cuadra-2026-10-b"
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
