"""Módulo 6: de la activación al negocio. Conversiones observadas, escenarios bajo supuestos e hipótesis.

Los escenarios NO son ingresos: multiplican supuestos explícitos por tasas observadas.
"""

from datetime import date, timedelta

import pandas as pd

from cuadra.config import DIAS_MADUREZ_PAGO, FECHA_CORRIDA
from cuadra.embudo_completo import tabla_personas
from cuadra.ingesta import Datos


def conversiones(datos: Datos, fecha: date = FECHA_CORRIDA) -> pd.DataFrame:
    """Registro → primera factura (cohortes maduras) y primera factura → pago (cohortes maduras para pagar).

    El pago llega hasta 30 días después de facturar; por eso esa tasa solo usa a quien se registró al
    menos DIAS_MADUREZ_PAGO días antes. Con cohortes recientes saldría artificialmente baja.
    """
    personas = tabla_personas(datos, fecha)
    limite_pago = fecha - timedelta(days=DIAS_MADUREZ_PAGO)
    personas["madura_pago"] = personas.fecha_registro <= limite_pago
    filas = []
    for dimension in ("total", "segmento", "canal"):
        grupos = [("todos", personas)] if dimension == "total" else list(personas.groupby(dimension))
        for valor, parte in grupos:
            maduras = parte[parte.madura]
            facturaron = parte[parte.madura_pago & parte.emitio_primera_factura]
            filas.append(
                {
                    "dimension": dimension,
                    "valor": valor,
                    "n_maduras": len(maduras),
                    "registro_a_factura": float(maduras.emitio_primera_factura.mean()) if len(maduras) else float("nan"),
                    "n_facturaron_maduras_pago": len(facturaron),
                    "factura_a_pago": float(facturaron.pago.mean()) if len(facturaron) else float("nan"),
                }
            )
    return pd.DataFrame(filas)


def ingreso_medio_mensual(datos: Datos) -> float:
    return float(datos.pagos.importe_eur_mes.mean()) if len(datos.pagos) else 0.0


def escenarios(personas_objetivo: int, factura_a_pago: float, ingreso_medio: float, efectos: list[float]) -> pd.DataFrame:
    """ESTIMACIÓN bajo supuestos: si la intervención sumara `efecto` puntos de primera factura a todos los
    atascados, cuántas facturas, pagos e ingreso mensual recurrente adicionales implicaría."""
    filas = []
    for efecto in efectos:
        facturas = personas_objetivo * efecto
        pagos = facturas * factura_a_pago
        filas.append(
            {
                "efecto_supuesto_pp": efecto * 100,
                "personas_objetivo": personas_objetivo,
                "facturas_adicionales": facturas,
                "pagos_adicionales": pagos,
                "ingreso_mensual_adicional_eur": pagos * ingreso_medio,
                "tipo": "estimación bajo supuestos, no resultado",
            }
        )
    return pd.DataFrame(filas)


def hipotesis(resumen_embudo: dict, conv: pd.DataFrame, tasa_base: float | None, salud: dict) -> list[dict]:
    """Hipótesis priorizadas por tamaño de la oportunidad y fuerza de la evidencia. Todo sale de cifras calculadas."""
    total = conv[conv.dimension == "total"].iloc[0]
    base_txt = f"{tasa_base:.2%}".replace(".", ",") if tasa_base is not None else "sin dato"
    lista = [
        {
            "id": "H1",
            "hipotesis": "Una guía para crear el primer cliente sube la activación de los autónomos de canal orgánico.",
            "evidencia": (
                f"En {resumen_embudo['mayor_oportunidad_grupo'].replace('organico', 'orgánico').replace('autonomo', 'autónomo')} solo el "
                f"{resumen_embudo['mayor_oportunidad_conversion']:.0%} de quienes configuran crea un cliente; la mediana "
                f"del resto de grupos es {resumen_embudo['mayor_oportunidad_referencia']:.0%}."
            ),
            "tamano": f"unas {resumen_embudo['mayor_oportunidad_personas_extra']:.0f} personas más en ese paso (estimación)",
            "confianza": "media: la brecha es grande y estable, pero no sabemos por qué se frenan",
            "experimento": "Guía contextual dentro de la app vs. nada, solo en ese grupo, con reparto por hash.",
            "dato_faltante": "formulario_cliente_abierto y formulario_cliente_error",
        },
        {
            "id": "H2",
            "hipotesis": "Un correo con el paso exacto que falta reactiva a quien lleva 3 días o más quieto.",
            "evidencia": f"Sin intervención, solo el {base_txt} de los atascados factura por su cuenta en 14 días.",
            "tamano": f"{salud['tamanos']['tratamiento'] + salud['tamanos']['control']} personas atascadas hoy",
            "confianza": "por medir: es el experimento en curso",
            "experimento": "En curso: 457 con correo y 455 de control, primera factura en 14 días.",
            "dato_faltante": "comunicacion_entregada / abierta / clic",
        },
        {
            "id": "H3",
            "hipotesis": "Llevar a más gente a la primera factura aumenta los pagos.",
            "evidencia": (
                f"El {total.factura_a_pago:.0%} de quienes facturan termina pagando (cohortes maduras), y casi "
                f"ningún pagador llegó a pagar sin facturar ({resumen_embudo['pagadores_sin_factura']})."
            ),
            "tamano": "condiciona el valor de todas las demás",
            "confianza": "baja como causa: facturar y pagar pueden tener la misma causa (necesitar facturar)",
            "experimento": "Medir el pago a 45 días en los grupos del experimento en curso (métrica secundaria).",
            "dato_faltante": "ninguno nuevo: basta con esperar y cruzar pagos con la asignación",
        },
        {
            "id": "H4",
            "hipotesis": "Las pymes no necesitan el mismo empujón que los autónomos.",
            "evidencia": (
                f"Llega a facturar el {resumen_embudo['pct_factura_pyme']:.0%} de las pymes frente al "
                f"{resumen_embudo['pct_factura_autonomo']:.0%} de los autónomos (cohortes maduras)."
            ),
            "tamano": "orienta dónde poner el esfuerzo",
            "confianza": "media: diferencia observada grande; la causa no se conoce",
            "experimento": "Analizar el experimento en curso por segmento antes de diseñar mensajes distintos.",
            "dato_faltante": "tamaño de la empresa y volumen de facturación esperado en el registro",
        },
    ]
    return lista
