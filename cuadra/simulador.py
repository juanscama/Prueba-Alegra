"""Genera una exportación FUTURA inventada para demostrar que la medición corre. No son resultados reales."""

import random
from datetime import timedelta

import pandas as pd

from cuadra.config import VENTANA_DIAS

COLUMNAS = ["id_contacto", "evento", "fecha", "simulado"]


def simular_eventos(
    asignacion: pd.DataFrame, efecto: float, base: float = 0.02, semilla: int = 7
) -> pd.DataFrame:
    """Control convierte con probabilidad `base`; tratamiento, con `base + efecto`."""
    azar = random.Random(semilla)
    entradas = pd.to_datetime(asignacion.fecha_entrada).dt.date
    filas = []
    for id_contacto, grupo, entrada in sorted(zip(asignacion.id_contacto, asignacion.grupo, entradas)):
        # Se sacan siempre los dos números para que cambiar el efecto no altere a quién le toca qué día.
        tirada, dia = azar.random(), azar.randint(1, VENTANA_DIAS)
        if tirada < base + (efecto if grupo == "tratamiento" else 0.0):
            filas.append(
                {
                    "id_contacto": id_contacto,
                    "evento": "emitio_primera_factura",
                    "fecha": entrada + timedelta(days=dia),
                    "simulado": True,
                }
            )
    return pd.DataFrame(filas, columns=COLUMNAS)
