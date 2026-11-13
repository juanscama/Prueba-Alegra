"""Etapa 8: une los correos aprobados con las personas del grupo de tratamiento."""

import pandas as pd

from cuadra.redaccion import Variante, personalizar
from cuadra.verificacion import VarianteProcesada

COLUMNAS_BANDEJA = [
    "id_contacto", "email", "nombre", "asunto", "cuerpo", "paso", "tramo", "dias_quieto",
    "variante", "fecha_entrada",
]
COLUMNAS_COLA = [
    "variante", "paso", "actividad", "tramo", "intentos", "motivos", "personas_sin_correo", "asunto", "cuerpo",
]


def _tratamiento_con_variante(asignacion: pd.DataFrame, contactos: pd.DataFrame) -> pd.DataFrame:
    personas = asignacion[asignacion.grupo == "tratamiento"].merge(
        contactos[["id_contacto", "nombre", "email", "actividad"]], on="id_contacto", how="left"
    )
    personas["variante"] = [
        Variante(p, a, t).clave for p, a, t in zip(personas.paso, personas.actividad, personas.tramo)
    ]
    return personas


def armar_bandeja(
    asignacion: pd.DataFrame, contactos: pd.DataFrame, procesadas: dict[str, VarianteProcesada]
) -> pd.DataFrame:
    personas = _tratamiento_con_variante(asignacion, contactos)
    aprobadas = {clave for clave, v in procesadas.items() if v.estado == "aprobada"}
    personas = personas[personas.variante.isin(aprobadas)].copy()
    textos = [personalizar(procesadas[v].correo, n) for v, n in zip(personas.variante, personas.nombre)]
    personas["asunto"] = [asunto for asunto, _ in textos]
    personas["cuerpo"] = [cuerpo for _, cuerpo in textos]
    # Primero quienes se atascaron hace poco: son quienes más probablemente responden.
    personas = personas.sort_values(["tramo", "dias_quieto", "id_contacto"])
    return personas[COLUMNAS_BANDEJA].reset_index(drop=True)


def armar_cola_revision(
    asignacion: pd.DataFrame, contactos: pd.DataFrame, procesadas: dict[str, VarianteProcesada]
) -> pd.DataFrame:
    afectadas = _tratamiento_con_variante(asignacion, contactos).variante.value_counts()
    filas = []
    for clave in sorted(procesadas):
        v = procesadas[clave]
        if v.estado != "revision":
            continue
        filas.append(
            {
                "variante": clave,
                "paso": v.variante.paso,
                "actividad": v.variante.actividad,
                "tramo": v.variante.tramo,
                "intentos": v.intentos,
                "motivos": " | ".join(v.motivos),
                "personas_sin_correo": int(afectadas.get(clave, 0)),
                "asunto": v.correo.asunto if v.correo else "",
                "cuerpo": v.correo.cuerpo if v.correo else "",
            }
        )
    return pd.DataFrame(filas, columns=COLUMNAS_COLA)
