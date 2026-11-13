"""Cómo sabríamos si funcionó: compara tratamiento y control con una regla de decisión fijada de antemano."""

from dataclasses import asdict, dataclass
from datetime import timedelta
from math import sqrt
from statistics import NormalDist

import pandas as pd

from cuadra.config import SEMILLA, VENTANA_DIAS
from cuadra.experimento import grupo
from cuadra.ingesta import Datos

Z95 = NormalDist().inv_cdf(0.975)


@dataclass(frozen=True)
class ResultadoExperimento:
    n_t: int
    conv_t: int
    tasa_t: float
    n_c: int
    conv_c: int
    tasa_c: float
    diferencia: float
    ic95: tuple[float, float]
    valor_p: float
    decision: str  # extender | iterar
    simulado: bool

    def como_dict(self) -> dict:
        return {**asdict(self), "ic95": list(self.ic95)}


def comparar(n_t: int, conv_t: int, n_c: int, conv_c: int, simulado: bool = False) -> ResultadoExperimento:
    """Diferencia de proporciones (tratamiento − control), intervalo del 95% y valor p a dos colas.

    Regla escrita antes de mirar los datos: se extiende a todos solo si el intervalo entero queda por
    encima de cero. En cualquier otro caso se itera el mensaje.
    """
    tasa_t = conv_t / n_t if n_t else 0.0
    tasa_c = conv_c / n_c if n_c else 0.0
    diferencia = tasa_t - tasa_c
    ic95, valor_p = (0.0, 0.0), 1.0
    if n_t and n_c:
        error = sqrt(tasa_t * (1 - tasa_t) / n_t + tasa_c * (1 - tasa_c) / n_c)
        ic95 = (diferencia - Z95 * error, diferencia + Z95 * error)
        agrupada = (conv_t + conv_c) / (n_t + n_c)
        error_agrupado = sqrt(agrupada * (1 - agrupada) * (1 / n_t + 1 / n_c))
        if error_agrupado > 0:
            valor_p = 2 * (1 - NormalDist().cdf(abs(diferencia) / error_agrupado))
    return ResultadoExperimento(
        n_t=int(n_t), conv_t=int(conv_t), tasa_t=tasa_t, n_c=int(n_c), conv_c=int(conv_c), tasa_c=tasa_c,
        diferencia=diferencia, ic95=ic95, valor_p=valor_p,
        decision="extender" if ic95[0] > 0 else "iterar", simulado=simulado,
    )


def _como_fecha(columna: pd.Series) -> pd.Series:
    return pd.to_datetime(columna).dt.date


def _comparar_grupos(tabla: pd.DataFrame, simulado: bool) -> ResultadoExperimento:
    t, c = tabla[tabla.grupo == "tratamiento"], tabla[tabla.grupo == "control"]
    return comparar(len(t), int(t.convirtio.sum()), len(c), int(c.convirtio.sum()), simulado)


def medir(
    asignacion: pd.DataFrame, eventos: pd.DataFrame, ventana_dias: int = VENTANA_DIAS
) -> tuple[ResultadoExperimento, pd.DataFrame]:
    """Por intención de tratar: cuenta a todos los asignados, hayan abierto el correo o no."""
    simulado = "simulado" in eventos.columns and bool(eventos.simulado.astype(str).str.lower().eq("true").any())
    tabla = asignacion[["id_contacto", "paso", "tramo", "grupo"]].copy()
    tabla["fecha_entrada"] = _como_fecha(asignacion.fecha_entrada)

    facturas = eventos[eventos.evento == "emitio_primera_factura"][["id_contacto", "fecha"]].copy()
    facturas["fecha"] = _como_fecha(facturas.fecha)
    cruce = tabla.merge(facturas, on="id_contacto", how="left")
    limite = cruce.fecha_entrada.map(lambda f: f + timedelta(days=ventana_dias))
    cruce["convirtio"] = cruce.fecha.notna() & (cruce.fecha > cruce.fecha_entrada) & (cruce.fecha <= limite)
    tabla["convirtio"] = tabla.id_contacto.map(cruce.groupby("id_contacto").convirtio.any())

    filas = []
    for dimension in ("paso", "tramo"):
        for valor, parte in tabla.groupby(dimension):
            r = _comparar_grupos(parte, simulado)
            filas.append(
                {
                    "dimension": dimension, "valor": valor, "n_t": r.n_t, "conv_t": r.conv_t, "tasa_t": r.tasa_t,
                    "n_c": r.n_c, "conv_c": r.conv_c, "tasa_c": r.tasa_c, "diferencia": r.diferencia,
                    "ic95_inf": r.ic95[0], "ic95_sup": r.ic95[1], "valor_p": r.valor_p,
                }
            )
    return _comparar_grupos(tabla, simulado), pd.DataFrame(filas)


def prueba_aa(datos: Datos, semilla: str = SEMILLA) -> ResultadoExperimento:
    """Mismo reparto por hash sobre julio y agosto, donde nadie recibió nada: no debería haber diferencia."""
    cohorte = datos.contactos[datos.contactos.fecha_registro.map(lambda f: f.month in (7, 8))]
    facturaron = set(datos.eventos[datos.eventos.evento == "emitio_primera_factura"].id_contacto)
    tabla = pd.DataFrame(
        {
            "grupo": cohorte.id_contacto.map(lambda i: grupo(i, semilla)),
            "convirtio": cohorte.id_contacto.isin(facturaron),
        }
    )
    return _comparar_grupos(tabla, simulado=False)
