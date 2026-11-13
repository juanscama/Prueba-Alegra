"""Etapa 3: en qué paso está cada persona que aún no factura y cuánto lleva quieta."""

from datetime import date

import pandas as pd

from cuadra.config import DIAS_ATASCADO, DIAS_RECIENTE_MAX, FECHA_CORRIDA
from cuadra.ingesta import Datos

# Paso en el que está la persona según el último evento que dio.
PASO_SEGUN_ULTIMO_EVENTO = {
    "registro": "sin_configurar",
    "configuro_empresa": "sin_cliente",
    "creo_cliente": "sin_factura",
}
ORDEN_EVENTOS = list(PASO_SEGUN_ULTIMO_EVENTO)


def _tramo(dias_quieto: int) -> str:
    if dias_quieto < DIAS_ATASCADO:
        return "en_ventana"
    if dias_quieto <= DIAS_RECIENTE_MAX:
        return "reciente"
    return "rezagado"


def _vista_a_fecha(datos: Datos, fecha: date):
    """Lo que se sabía ese día: sin eventos, pagos ni registros posteriores."""
    eventos = datos.eventos[datos.eventos.fecha <= fecha]
    pagadores = set(datos.pagos[datos.pagos.fecha_pago <= fecha].id_contacto)
    facturaron = set(eventos[eventos.evento == "emitio_primera_factura"].id_contacto)
    return eventos, pagadores, facturaron


def calcular_estado(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    eventos, pagadores, facturaron = _vista_a_fecha(datos, fecha)
    filas = []
    for id_contacto, propios in eventos.groupby("id_contacto", sort=True):
        if id_contacto in facturaron or id_contacto in pagadores:
            continue
        dados = set(propios.evento)
        ultimo = [e for e in ORDEN_EVENTOS if e in dados][-1]
        dias_quieto = (fecha - propios.fecha.max()).days
        tramo = _tramo(dias_quieto)
        filas.append(
            {
                "id_contacto": id_contacto,
                "paso": PASO_SEGUN_ULTIMO_EVENTO[ultimo],
                "dias_quieto": dias_quieto,
                "tramo": tramo,
                "elegible": tramo != "en_ventana",
            }
        )
    return pd.DataFrame(filas, columns=["id_contacto", "paso", "dias_quieto", "tramo", "elegible"])


def pagadores_sin_factura(datos: Datos, fecha: date = FECHA_CORRIDA) -> list[str]:
    _, pagadores, facturaron = _vista_a_fecha(datos, fecha)
    return sorted(pagadores - facturaron)
