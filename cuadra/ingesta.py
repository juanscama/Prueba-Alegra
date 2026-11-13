"""Etapa 1: carga y validación de los tres CSV del caso."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cuadra.config import DIR_DATOS, PASOS

COLUMNAS = {
    "crm_contactos.csv": [
        "id_contacto", "nombre", "email", "fecha_registro", "canal", "segmento", "actividad", "etapa_crm",
    ],
    "eventos_producto.csv": ["id_contacto", "evento", "fecha"],
    "pagos.csv": ["id_contacto", "fecha_pago", "plan", "importe_eur_mes"],
}


class ErrorDatos(ValueError):
    """Los datos de entrada no cumplen lo que el flujo necesita."""


@dataclass
class Datos:
    contactos: pd.DataFrame
    eventos: pd.DataFrame
    pagos: pd.DataFrame


def _leer(dir_datos: Path, nombre: str, columnas_fecha: list[str]) -> pd.DataFrame:
    ruta = dir_datos / nombre
    if not ruta.is_file():
        raise ErrorDatos(f"Falta el archivo {nombre} en {dir_datos}")
    tabla = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    faltan = [c for c in COLUMNAS[nombre] if c not in tabla.columns]
    if faltan:
        raise ErrorDatos(f"{nombre}: faltan las columnas {', '.join(faltan)}")
    for columna in columnas_fecha:
        try:
            tabla[columna] = pd.to_datetime(tabla[columna], format="%Y-%m-%d").dt.date
        except ValueError as error:
            raise ErrorDatos(f"{nombre}: fecha no válida en {columna} ({error})") from error
    return tabla


def _ejemplos(valores) -> str:
    valores = sorted(set(valores))
    return ", ".join(valores[:5]) + (" …" if len(valores) > 5 else "")


def cargar(dir_datos: Path = DIR_DATOS) -> Datos:
    dir_datos = Path(dir_datos)
    contactos = _leer(dir_datos, "crm_contactos.csv", ["fecha_registro"])
    eventos = _leer(dir_datos, "eventos_producto.csv", ["fecha"])
    pagos = _leer(dir_datos, "pagos.csv", ["fecha_pago"])
    pagos["importe_eur_mes"] = pd.to_numeric(pagos["importe_eur_mes"])

    duplicados = contactos.id_contacto[contactos.id_contacto.duplicated()]
    if len(duplicados):
        raise ErrorDatos(f"crm_contactos.csv: ids repetidos: {_ejemplos(duplicados)}")

    conocidos = set(contactos.id_contacto)
    for nombre, tabla in (("eventos_producto.csv", eventos), ("pagos.csv", pagos)):
        huerfanos = set(tabla.id_contacto) - conocidos
        if huerfanos:
            raise ErrorDatos(f"{nombre}: ids que no están en el CRM: {_ejemplos(huerfanos)}")

    desconocidos = set(eventos.evento) - set(PASOS)
    if desconocidos:
        raise ErrorDatos(f"eventos_producto.csv: eventos desconocidos: {_ejemplos(desconocidos)}")

    # Cada paso exige que la persona haya dado el paso anterior.
    dados = eventos.groupby("id_contacto").evento.agg(set)
    for anterior, siguiente in zip(PASOS, PASOS[1:]):
        saltos = [i for i, pasos in dados.items() if siguiente in pasos and anterior not in pasos]
        if saltos:
            raise ErrorDatos(
                f"eventos_producto.csv: {siguiente} sin {anterior} en: {_ejemplos(saltos)}"
            )

    return Datos(contactos=contactos, eventos=eventos, pagos=pagos)
