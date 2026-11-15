"""Módulo 2: prioridad alta, media o baja para cada persona atascada, con reglas transparentes.

La prioridad ordena la atención del equipo; no decide quién recibe correo (eso lo fijó el reparto del
experimento) y no estima a quién le sirve más el contacto. Esa pregunta (efecto incremental) solo la
puede responder el experimento, mirando el resultado por estrato de prioridad.

Por qué no hay un modelo predictivo: entre las personas atascadas, en siete cortes pasados solo 5 de
3249 facturaron por su cuenta. Con 5 casos positivos no se puede entrenar ni calibrar un modelo.
"""

from datetime import date

import pandas as pd

from cuadra.config import FECHA_CORRIDA
from cuadra.embudo_completo import tabla_personas
from cuadra.ingesta import Datos

PUNTOS_PASO = {"sin_factura": 3, "sin_cliente": 2, "sin_configurar": 1}
PUNTOS_TRAMO = {"reciente": 1, "rezagado": 0}
GRUPO_FUGA = ("organico", "autonomo", "sin_cliente")

ACCION_FALTANTE = {
    "sin_configurar": "Completar los datos de su empresa (NIF y dirección fiscal)",
    "sin_cliente": "Crear su primer cliente",
    "sin_factura": "Emitir su primera factura",
}
INTERVENCION_SUGERIDA = {
    "sin_configurar": "Checklist de activación con el paso «Configura tu empresa» marcado como pendiente",
    "sin_cliente": "Guía contextual para crear el primer cliente desde la factura nueva",
    "sin_factura": "Tutorial para emitir la primera factura (con la opción de guardarla como borrador)",
}


def nivel(puntos: int) -> str:
    if puntos >= 4:
        return "alta"
    if puntos == 3:
        return "media"
    return "baja"


def evidencia_por_paso(datos: Datos, fecha: date = FECHA_CORRIDA) -> dict[str, float]:
    """De las personas maduras que dieron el paso previo al atasco, qué parte terminó facturando."""
    personas = tabla_personas(datos, fecha)
    maduras = personas[personas.madura]
    resultado = {}
    for paso, columna in (("sin_configurar", "registro"), ("sin_cliente", "configuro_empresa"), ("sin_factura", "creo_cliente")):
        llegaron = maduras[maduras[columna]]
        resultado[paso] = float(llegaron.emitio_primera_factura.mean()) if len(llegaron) else float("nan")
    return resultado


def priorizar(estado: pd.DataFrame, contactos: pd.DataFrame, asignacion: pd.DataFrame, evidencia: dict[str, float]) -> pd.DataFrame:
    """Una fila por persona elegible. Solo usa datos conocidos el día de corrida (los del estado)."""
    elegibles = estado[estado.elegible.astype(str).str.lower() == "true"].copy()
    elegibles["id_contacto"] = elegibles.id_contacto.astype(str)
    tabla = elegibles.merge(contactos[["id_contacto", "canal", "segmento"]], on="id_contacto", how="left")
    grupos = asignacion.assign(id_contacto=asignacion.id_contacto.astype(str)).set_index("id_contacto").grupo
    tabla["grupo"] = tabla.id_contacto.map(grupos)
    filas = []
    for _, f in tabla.iterrows():
        puntos = PUNTOS_PASO[f.paso] + PUNTOS_TRAMO[f.tramo]
        motivos = [f"le falta {'un solo paso' if f.paso == 'sin_factura' else 'más de un paso'} para facturar (+{PUNTOS_PASO[f.paso]})"]
        if PUNTOS_TRAMO[f.tramo]:
            motivos.append(f"lleva {f.dias_quieto} días quieto: se atascó hace poco (+1, hipótesis)")
        else:
            motivos.append(f"lleva {f.dias_quieto} días quieto: hace tiempo que no vuelve (+0)")
        if (f.canal, f.segmento, f.paso) == GRUPO_FUGA:
            puntos += 1
            motivos.append("su bloqueo es el de la fuga principal: orgánico × autónomo sin cliente (+1)")
        filas.append(
            {
                "id_contacto": f.id_contacto,
                "grupo": f.grupo,
                "paso": f.paso,
                "tramo": f.tramo,
                "dias_quieto": int(f.dias_quieto),
                "canal": f.canal,
                "segmento": f.segmento,
                "puntos": puntos,
                "prioridad": nivel(puntos),
                "motivos": "; ".join(motivos),
                "accion_faltante": ACCION_FALTANTE[f.paso],
                "intervencion_sugerida": INTERVENCION_SUGERIDA[f.paso],
                "evidencia": (
                    f"Observado: de quienes llegaron a este punto (cohortes maduras), el {evidencia[f.paso]:.0%} "
                    "terminó facturando, casi todos sin pararse. Quien se queda 3 días o más quieto casi nunca "
                    "avanza solo, así que la cifra mide lo cerca que está, no su probabilidad. Que la "
                    "intervención ayude es una hipótesis que mide el experimento."
                ),
            }
        )
    orden = {"alta": 0, "media": 1, "baja": 2}
    resultado = pd.DataFrame(filas)
    if resultado.empty:
        return resultado
    return resultado.sort_values(["prioridad", "puntos", "dias_quieto"], key=lambda s: s.map(orden) if s.name == "prioridad" else s, ascending=[True, False, True]).reset_index(drop=True)
