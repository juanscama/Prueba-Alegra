"""Módulo 4: cómo avanzan las personas dentro del producto, con lo que registran los eventos.

Los eventos solo traen cinco pasos con su fecha (por día). No hay clics, pantallas, sesiones ni errores,
así que este módulo no los supone: lo que falta se pide en INSTRUMENTACION_RECOMENDADA.
"""

from datetime import date, timedelta

import pandas as pd

from cuadra.config import DIAS_MADUREZ, FECHA_CORRIDA, PASOS
from cuadra.ingesta import Datos


def _fechas(datos: Datos, fecha: date) -> pd.DataFrame:
    eventos = datos.eventos[datos.eventos.fecha <= fecha]
    tabla = eventos.pivot(index="id_contacto", columns="evento", values="fecha").reindex(columns=PASOS)
    contactos = datos.contactos.set_index("id_contacto")
    tabla = tabla.join(contactos[["canal", "segmento", "fecha_registro"]], how="inner")
    tabla["madura"] = tabla.fecha_registro <= fecha - timedelta(days=DIAS_MADUREZ)
    return tabla


def secuencias(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Cuántas personas siguen cada secuencia de pasos, y si la secuencia respeta el orden del producto."""
    eventos = datos.eventos[datos.eventos.fecha <= fecha]
    orden = {p: i for i, p in enumerate(PASOS)}
    por_persona = eventos.assign(o=eventos.evento.map(orden)).sort_values(["id_contacto", "fecha", "o"])
    cadenas = por_persona.groupby("id_contacto").evento.agg(list)
    conteo = cadenas.map(" > ".join).value_counts()
    return pd.DataFrame(
        {
            "secuencia": conteo.index,
            "personas": conteo.values,
            "pasos": [s.count(">") + 1 for s in conteo.index],
            "respeta_orden": [s.split(" > ") == PASOS[: s.count(">") + 1] for s in conteo.index],
        }
    )


def donde_se_detiene(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Entre las personas maduras que no facturaron, en qué paso se detuvo su actividad."""
    tabla = _fechas(datos, fecha)
    tabla = tabla[tabla.madura & tabla.emitio_primera_factura.isna()]
    ultimo = tabla[PASOS[:3]].notna().iloc[:, ::-1].idxmax(axis=1)
    conteo = ultimo.value_counts().reindex(PASOS[:3], fill_value=0)
    return pd.DataFrame(
        {"ultimo_paso": conteo.index, "personas": conteo.values, "pct": conteo.values / max(len(tabla), 1)}
    )


def tiempo_a_primera_factura(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Distribución de días entre el registro y la primera factura."""
    tabla = _fechas(datos, fecha)
    con = tabla[tabla.emitio_primera_factura.notna()]
    dias = pd.Series([(f - r).days for f, r in zip(con.emitio_primera_factura, con.registro)])
    conteo = dias.value_counts().sort_index()
    return pd.DataFrame(
        {"dias": conteo.index.astype(int), "personas": conteo.values, "pct_acumulado": conteo.cumsum().values / len(dias)}
    )


def acciones_antes_de_activar(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Número de eventos registrados antes de la primera factura. Con un embudo lineal, siempre es el mismo."""
    tabla = _fechas(datos, fecha)
    con = tabla[tabla.emitio_primera_factura.notna()]
    acciones = con[PASOS[:3]].notna().sum(axis=1)
    conteo = acciones.value_counts().sort_index()
    return pd.DataFrame({"acciones": conteo.index.astype(int), "personas": conteo.values})


def ritmo_activados_vs_no(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Entre quienes llegaron a crear un cliente (maduras): días entre pasos de quien facturó y de quien no.

    Es una ASOCIACIÓN observada, no una causa: ir rápido puede ser síntoma de una necesidad urgente de
    facturar, no algo que el producto pueda provocar.
    """
    tabla = _fechas(datos, fecha)
    tabla = tabla[tabla.madura & tabla.creo_cliente.notna()]
    filas = []
    for activado, parte in tabla.groupby(tabla.emitio_primera_factura.notna()):
        for desde, hasta in zip(PASOS[:2], PASOS[1:3]):
            dias = pd.Series([(b - a).days for a, b in zip(parte[desde], parte[hasta])])
            filas.append(
                {
                    "grupo": "facturó" if activado else "no facturó",
                    "tramo": f"{desde} → {hasta}",
                    "n": len(dias),
                    "mediana_dias": float(dias.median()),
                    "pct_mismo_dia": float((dias == 0).mean()),
                }
            )
    return pd.DataFrame(filas)


def cohortes_semanales(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Por semana de registro: tamaño y qué parte facturó en los 14 días siguientes (solo semanas maduras)."""
    tabla = _fechas(datos, fecha)
    tabla = tabla[tabla.madura].copy()
    tabla["semana"] = tabla.fecha_registro.map(lambda f: (f - timedelta(days=f.weekday())).isoformat())
    tabla["factura_14d"] = [
        pd.notna(f) and (f - r).days <= DIAS_MADUREZ for f, r in zip(tabla.emitio_primera_factura, tabla.registro)
    ]
    tabla["configuro_mismo_dia"] = [pd.notna(c) and c == r for c, r in zip(tabla.configuro_empresa, tabla.registro)]
    grupos = tabla.groupby("semana")
    return pd.DataFrame(
        {
            "semana": list(grupos.groups),
            "registrados": grupos.size().values,
            "pct_factura_14d": grupos.factura_14d.mean().values,
            "pct_configuro_mismo_dia": grupos.configuro_mismo_dia.mean().values,
        }
    )


INSTRUMENTACION_RECOMENDADA = [
    {
        "nombre": "sesion_iniciada",
        "descripcion": "La persona entra en Cuadra.",
        "propiedades": "id_contacto, fecha_hora, dispositivo, origen (correo, directo, notificación)",
        "momento": "Al completar el inicio de sesión.",
        "pregunta": "¿Los atascados vuelven a entrar y no avanzan, o no vuelven? ¿El correo los trae de vuelta?",
    },
    {
        "nombre": "formulario_cliente_abierto",
        "descripcion": "Abre el formulario de nuevo cliente.",
        "propiedades": "id_contacto, fecha_hora, desde (factura nueva, menú Clientes)",
        "momento": "Al mostrarse el formulario.",
        "pregunta": "En la fuga principal (sin cliente), ¿no encuentran el formulario o lo abren y lo abandonan?",
    },
    {
        "nombre": "formulario_cliente_error",
        "descripcion": "Intenta guardar un cliente y la validación falla.",
        "propiedades": "id_contacto, fecha_hora, campo (NIF, dirección, correo), tipo_error",
        "momento": "Al rechazar el guardado.",
        "pregunta": "¿Qué campo frena a los autónomos (p. ej., el NIF de un cliente particular)?",
    },
    {
        "nombre": "factura_borrador_guardada",
        "descripcion": "Guarda una factura sin emitirla.",
        "propiedades": "id_contacto, fecha_hora, lineas, tiene_iva",
        "momento": "Al guardar el borrador.",
        "pregunta": "¿Quien no emite se queda en el borrador (miedo a equivocarse) o ni lo empieza?",
    },
    {
        "nombre": "ayuda_consultada",
        "descripcion": "Abre un artículo del Centro de Ayuda o una guía dentro del producto.",
        "propiedades": "id_contacto, fecha_hora, articulo, desde_pantalla",
        "momento": "Al abrir el artículo.",
        "pregunta": "¿Qué dudas aparecen antes de cada abandono? ¿La ayuda corregida reduce el abandono?",
    },
    {
        "nombre": "comunicacion_entregada / abierta / clic",
        "descripcion": "Estado de cada correo o mensaje enviado por el flujo.",
        "propiedades": "id_contacto, canal, variante, fecha_hora, estado",
        "momento": "Al recibir el aviso del proveedor de envío.",
        "pregunta": "¿El efecto (o su ausencia) viene de que no se abre o de que se abre y no convence?",
    },
    {
        "nombre": "preferencias_comunicacion",
        "descripcion": "Consentimientos por canal (correo comercial, WhatsApp, notificaciones).",
        "propiedades": "id_contacto, canal, consentimiento, fecha, origen",
        "momento": "En el registro y al cambiarlas.",
        "pregunta": "¿A quién se le puede escribir por cada canal? Sin este dato, WhatsApp no se puede usar.",
    },
]
