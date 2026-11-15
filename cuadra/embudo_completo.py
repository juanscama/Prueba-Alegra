"""Módulo 1: embudo completo de registro a pago, abandono por etapa y dónde está la mayor oportunidad.

Todo es código determinista. Las tasas se calculan sobre cohortes maduras (registradas al menos
DIAS_MADUREZ días antes de la fecha de corrida) para no confundir «todavía no» con «nunca».
"""

from datetime import date, timedelta

import pandas as pd

from cuadra.config import DIAS_MADUREZ, FECHA_CORRIDA
from cuadra.ingesta import Datos

ETAPAS = ["registro", "configuro_empresa", "creo_cliente", "emitio_primera_factura", "pago"]


def tabla_personas(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Una fila por persona registrada hasta `fecha`, con lo que se sabía ese día."""
    contactos = datos.contactos[datos.contactos.fecha_registro <= fecha]
    eventos = datos.eventos[datos.eventos.fecha <= fecha]
    pagos = datos.pagos[datos.pagos.fecha_pago <= fecha]
    fechas = eventos.pivot(index="id_contacto", columns="evento", values="fecha")
    tabla = contactos.set_index("id_contacto")[["canal", "segmento", "actividad", "fecha_registro"]].copy()
    for etapa in ETAPAS[:-1]:
        tabla[etapa] = tabla.index.isin(fechas.index[fechas[etapa].notna()]) if etapa in fechas else False
    tabla["pago"] = tabla.index.isin(pagos.id_contacto)
    tabla["mes_registro"] = tabla.fecha_registro.map(lambda f: f.strftime("%Y-%m"))
    tabla["madura"] = tabla.fecha_registro <= fecha - timedelta(days=DIAS_MADUREZ)
    return tabla


def embudo_etapas(personas: pd.DataFrame) -> pd.DataFrame:
    """Llegan, conversión desde la etapa anterior, abandono y personas perdidas en cada etapa.

    La etapa «pago» cuenta solo a quien pagó después de facturar, para que el embudo sea una cadena;
    quien pagó sin facturar se informa aparte.
    """
    llegan = []
    for i, etapa in enumerate(ETAPAS):
        marca = personas[etapa]
        if etapa == "pago":
            marca = marca & personas.emitio_primera_factura
        llegan.append(int(marca.sum()) if i else len(personas))
    filas = []
    for i, etapa in enumerate(ETAPAS):
        anterior = llegan[i - 1] if i else llegan[0]
        conversion = llegan[i] / anterior if anterior else float("nan")
        filas.append(
            {
                "etapa": etapa,
                "llegan": llegan[i],
                "pct_registro": llegan[i] / llegan[0] if llegan[0] else float("nan"),
                "conv_desde_anterior": conversion if i else 1.0,
                "abandono": 1 - conversion if i else 0.0,
                "perdidos": anterior - llegan[i] if i else 0,
            }
        )
    return pd.DataFrame(filas)


def embudo_por_grupo(personas: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """El embudo por etapas para cada grupo, en formato largo (una fila por grupo y etapa)."""
    partes = []
    for clave, grupo in personas.groupby(columnas):
        clave = clave if isinstance(clave, tuple) else (clave,)
        tabla = embudo_etapas(grupo)
        for columna, valor in zip(columnas, clave):
            tabla.insert(0, columna, valor)
        partes.append(tabla)
    return pd.concat(partes, ignore_index=True)


def oportunidades(personas: pd.DataFrame, columnas: list[str] = ("canal", "segmento")) -> pd.DataFrame:
    """Cuellos de botella: grupos y etapas donde se convierte por debajo del resto.

    `personas_extra` es una ESTIMACIÓN bajo un supuesto explícito: cuántas personas más darían el paso
    si ese grupo convirtiera como la mediana de los demás grupos en esa misma etapa. No es un resultado.
    """
    columnas = list(columnas)
    largo = embudo_por_grupo(personas, columnas)
    # El pago queda fuera: llega hasta 30 días después de facturar y en cohortes de 14 días sale sesgado.
    largo = largo[~largo.etapa.isin(["registro", "pago"])].copy()
    largo["grupo"] = largo[columnas].astype(str).agg(" × ".join, axis=1)
    filas = []
    for etapa, parte in largo.groupby("etapa", sort=False):
        for _, fila in parte.iterrows():
            resto = parte[parte.grupo != fila.grupo].conv_desde_anterior
            referencia = float(resto.median())
            anterior = fila.llegan + fila.perdidos
            filas.append(
                {
                    "grupo": fila.grupo,
                    **{c: fila[c] for c in columnas},
                    "etapa": etapa,
                    "llegan_a_etapa_anterior": int(anterior),
                    "conversion": float(fila.conv_desde_anterior),
                    "referencia_resto": referencia,
                    "brecha": referencia - float(fila.conv_desde_anterior),
                    "personas_extra": max(0.0, (referencia - float(fila.conv_desde_anterior)) * anterior),
                }
            )
    tabla = pd.DataFrame(filas).sort_values("personas_extra", ascending=False).reset_index(drop=True)
    tabla["supuesto"] = "si convirtiera como la mediana de los demás grupos en esa etapa"
    return tabla


def pagadores_sin_factura(personas: pd.DataFrame) -> int:
    return int((personas.pago & ~personas.emitio_primera_factura).sum())


def resumen_embudo(datos: Datos, fecha: date = FECHA_CORRIDA) -> dict:
    """Las cifras clave que el panel y el informe ejecutivo citan. Todas salen de los datos del caso."""
    personas = tabla_personas(datos, fecha)
    maduras = personas[personas.madura]
    etapas = embudo_etapas(maduras)
    peor = etapas.iloc[1:].sort_values("perdidos", ascending=False).iloc[0]
    segmentos = embudo_por_grupo(maduras, ["segmento"])
    factura = segmentos[segmentos.etapa == "emitio_primera_factura"].set_index("segmento").pct_registro
    top = oportunidades(maduras).iloc[0]
    return {
        "registrados": int(len(personas)),
        "maduras": int(len(maduras)),
        "fecha_madurez": (fecha - timedelta(days=DIAS_MADUREZ)).isoformat(),
        "etapa_con_mas_perdidos": str(peor.etapa),
        "perdidos_en_esa_etapa": int(peor.perdidos),
        "abandono_en_esa_etapa": float(peor.abandono),
        "pct_factura_autonomo": float(factura.get("autonomo", float("nan"))),
        "pct_factura_pyme": float(factura.get("pyme", float("nan"))),
        "mayor_oportunidad_grupo": str(top.grupo),
        "mayor_oportunidad_etapa": str(top.etapa),
        "mayor_oportunidad_conversion": float(top.conversion),
        "mayor_oportunidad_referencia": float(top.referencia_resto),
        "mayor_oportunidad_personas_extra": float(top.personas_extra),
        "pagadores_sin_factura": pagadores_sin_factura(personas),
    }
