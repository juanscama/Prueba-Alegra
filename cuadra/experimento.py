"""Etapa 4: reparto en tratamiento y control, y cuánto efecto puede detectar ese reparto."""

from datetime import date
from hashlib import sha256
from math import sqrt
from statistics import NormalDist

import pandas as pd

from cuadra.config import FECHA_CORRIDA, PROPORCION_TRATAMIENTO, SEMILLA


def grupo(id_contacto: str, semilla: str = SEMILLA, proporcion: float = PROPORCION_TRATAMIENTO) -> str:
    """Hash puro del id: el grupo de una persona no depende de quién más entre ni de la fecha."""
    huella = int(sha256(f"{semilla}:{id_contacto}".encode()).hexdigest()[:8], 16)
    return "tratamiento" if huella / 0x100000000 < proporcion else "control"


def asignar(estado: pd.DataFrame, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    asignacion = estado[estado.elegible].copy()
    asignacion["grupo"] = asignacion.id_contacto.map(grupo)
    asignacion["fecha_entrada"] = fecha
    return asignacion.reset_index(drop=True)


def equilibrio(asignacion: pd.DataFrame, contactos: pd.DataFrame, por: str) -> pd.DataFrame:
    tabla = asignacion
    if por not in tabla.columns:
        tabla = tabla.merge(contactos[["id_contacto", por]], on="id_contacto", how="left")
    conteo = tabla.groupby([por, "grupo"]).size().unstack(fill_value=0)
    conteo = conteo.reindex(columns=["tratamiento", "control"], fill_value=0)
    conteo["pct_tratamiento"] = conteo.tratamiento / (conteo.tratamiento + conteo.control)
    return conteo.reset_index()


def efecto_minimo_detectable(
    n_t: int, n_c: int, base: float, alfa: float = 0.05, potencia: float = 0.8
) -> float:
    """Diferencia de proporciones mínima que este tamaño de grupos detecta (aproximación normal)."""
    z = NormalDist().inv_cdf(1 - alfa / 2) + NormalDist().inv_cdf(potencia)
    return z * sqrt(base * (1 - base) * (1 / n_t + 1 / n_c))
