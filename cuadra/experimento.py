"""Etapa 4: reparto en tratamiento y control, y cuánto efecto puede detectar ese reparto."""

from datetime import date, timedelta
from hashlib import sha256
from math import sqrt
from statistics import NormalDist

import pandas as pd

from cuadra.config import FECHA_CORRIDA, PROPORCION_TRATAMIENTO, SEMILLA, VENTANA_DIAS
from cuadra.estado import calcular_estado
from cuadra.ingesta import Datos


def grupo(id_contacto: str, semilla: str = SEMILLA, proporcion: float = PROPORCION_TRATAMIENTO) -> str:
    """Hash puro del id: el grupo de una persona no depende de quién más entre ni de la fecha."""
    huella = int(sha256(f"{semilla}:{id_contacto}".encode()).hexdigest()[:8], 16)
    return "tratamiento" if huella / 0x100000000 < proporcion else "control"


def asignar(estado: pd.DataFrame, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    asignacion = estado[estado.elegible.astype(bool)].copy()
    asignacion["grupo"] = asignacion.id_contacto.map(grupo).astype(object)
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


def acumular(previa: pd.DataFrame, nueva: pd.DataFrame) -> pd.DataFrame:
    """Registro del experimento entre corridas: nadie sale de él y cada persona conserva su primera fecha.

    Quien facturó después de entrar deja de ser elegible, pero tiene que seguir en el registro: es
    justo la conversión que la medición debe contar.
    """
    previa = previa.copy()
    previa["fecha_entrada"] = pd.to_datetime(previa.fecha_entrada).dt.date
    recien_llegados = nueva[~nueva.id_contacto.isin(previa.id_contacto)]
    return pd.concat([previa, recien_llegados], ignore_index=True)[list(nueva.columns)]


def conversion_natural(
    datos: Datos, fecha: date, ventana_dias: int = VENTANA_DIAS, cada_dias: int = 15
) -> tuple[int, int, list[date]]:
    """Qué parte de los atascados facturó sola: la base contra la que se mide el efecto del correo.

    Recorre fechas de corte pasadas, toma a quienes ese día habrían sido elegibles y cuenta cuántos
    emitieron su primera factura en la ventana siguiente. Una misma persona cuenta en varios cortes.
    """
    primer_registro = datos.contactos.fecha_registro.min()
    facturas = datos.eventos[datos.eventos.evento == "emitio_primera_factura"].set_index("id_contacto").fecha
    cortes, corte = [], fecha - timedelta(days=ventana_dias)
    while corte >= primer_registro + timedelta(days=ventana_dias):
        cortes.append(corte)
        corte -= timedelta(days=cada_dias)
    convertidos = observaciones = 0
    for corte in cortes:
        estado = calcular_estado(datos, corte)
        elegibles = estado[estado.elegible.astype(bool)].id_contacto
        fechas = elegibles.map(facturas)
        limite = corte + timedelta(days=ventana_dias)
        convertidos += int(fechas.map(lambda f: pd.notna(f) and corte < f <= limite).sum())
        observaciones += len(elegibles)
    return convertidos, observaciones, sorted(cortes)


def efecto_minimo_detectable(
    n_t: int, n_c: int, base: float, alfa: float = 0.05, potencia: float = 0.8
) -> float | None:
    """Mejora mínima, en proporción, que estos grupos detectan con la potencia pedida.

    La varianza del grupo de tratamiento depende de la propia mejora, así que se busca por bisección
    el efecto cuya potencia es exactamente la pedida (aproximación normal, prueba bilateral).
    """
    if not n_t or not n_c:
        return None
    normal = NormalDist()
    z_alfa = normal.inv_cdf(1 - alfa / 2)

    def potencia_de(efecto: float) -> float:
        tasa_t = base + efecto
        conjunta = (n_t * tasa_t + n_c * base) / (n_t + n_c)
        error_nulo = sqrt(conjunta * (1 - conjunta) * (1 / n_t + 1 / n_c))
        error_real = sqrt(tasa_t * (1 - tasa_t) / n_t + base * (1 - base) / n_c)
        return 1 - normal.cdf((z_alfa * error_nulo - efecto) / error_real)

    bajo, alto = 0.0, 1.0 - base
    for _ in range(60):
        medio = (bajo + alto) / 2
        if potencia_de(medio) < potencia:
            bajo = medio
        else:
            alto = medio
    return alto
