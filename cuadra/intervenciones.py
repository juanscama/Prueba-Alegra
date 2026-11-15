"""Módulo 3: intervención por bloqueo y canal. Las reglas las pone el código; Claude solo redacta.

Nada se envía: el plan queda en una bandeja simulada. El experimento en curso prueba solo el correo,
así que los demás canales se proponen para el siguiente experimento y no se activan sobre nadie.
"""

import re

import pandas as pd
from pydantic import BaseModel, Field

from cuadra.conocimiento import BaseVigente, extraer_rutas, normalizar_ruta
from cuadra.modelo import ErrorModelo, Rechazo, SinCache
from cuadra.redaccion import ARTICULOS_POR_PASO, OBJETIVO_POR_PASO
from cuadra.verificacion import _ENLACE, _PROMESAS

CANALES = {
    "correo": {"nombre": "Correo electrónico", "limite": 900},
    "in_app": {"nombre": "Mensaje dentro de la aplicación", "limite": 280},
    "guia": {"nombre": "Guía contextual", "limite": 700},
    "checklist": {"nombre": "Checklist de activación", "limite": 700},
    "notificacion": {"nombre": "Notificación de ayuda", "limite": 140},
    "whatsapp": {"nombre": "WhatsApp (prototipo)", "limite": 400},
}
CANALES_A_REDACTAR = ["in_app", "guia", "checklist", "notificacion", "whatsapp"]
CANAL_PRINCIPAL = {"sin_configurar": "checklist", "sin_cliente": "guia", "sin_factura": "in_app"}
PASOS = list(CANAL_PRINCIPAL)
MAX_CONTACTOS_POR_SEMANA = 1


def elegibilidad(persona: dict, canal: str) -> tuple[str, str]:
    """(estado, motivo). Estados: activo, propuesto, bloqueado. Regla fija en código, no en el modelo."""
    if persona.get("grupo") != "tratamiento":
        return "bloqueado", "Grupo de control: no recibe nada para no contaminar el experimento"
    if canal == "whatsapp":
        if str(persona.get("consentimiento_whatsapp", "")).lower() != "true":
            return "bloqueado", "Sin consentimiento registrado para WhatsApp (el CRM no tiene ese dato)"
        return "propuesto", "Con consentimiento; solo prototipo"
    if canal == "correo":
        if not str(persona.get("email") or "").strip():
            return "bloqueado", "Sin dirección de correo"
        return "activo", "Es el tratamiento del experimento en curso (envío simulado)"
    return "propuesto", "Para el siguiente experimento: activarlo ahora cambiaría el tratamiento a mitad de medición"


def respeta_frecuencia(historial: pd.DataFrame, id_contacto: str, fecha, dias: int = 7) -> bool:
    """Como máximo MAX_CONTACTOS_POR_SEMANA contactos por persona en los últimos `dias` días."""
    if historial is None or historial.empty:
        return True
    propios = historial[historial.id_contacto.astype(str) == str(id_contacto)]
    fechas = pd.to_datetime(propios.fecha).dt.date
    recientes = [f for f in fechas if 0 <= (fecha - f).days < dias]
    return len(recientes) < MAX_CONTACTOS_POR_SEMANA


def plan_intervenciones(priorizados: pd.DataFrame, contactos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona y canal con el estado que dicta el código."""
    emails = contactos.set_index("id_contacto").email
    filas = []
    for _, p in priorizados.iterrows():
        persona = {"grupo": p.grupo, "email": emails.get(p.id_contacto, "")}
        for canal in CANALES:
            estado, motivo = elegibilidad(persona, canal)
            filas.append(
                {
                    "id_contacto": p.id_contacto, "grupo": p.grupo, "paso": p.paso, "prioridad": p.prioridad,
                    "canal": canal, "es_principal": canal == CANAL_PRINCIPAL[p.paso],
                    "estado": estado, "motivo": motivo,
                }
            )
    return pd.DataFrame(filas)


class Contenido(BaseModel):
    titulo: str = Field(description="Título corto o primera línea")
    cuerpo: str = Field(description="Texto principal. Rutas de menú en negrita: **Ventas > Facturas**")
    pasos: list[str] = Field(description="Pasos concretos, de 0 a 4; vacío si el canal no los admite")
    boton: str = Field(description="Texto del botón o llamada a la acción, máximo 4 palabras")
    articulo_fuente: str = Field(description="Archivo del artículo de ayuda en que se apoya")


SISTEMA = """\
Escribes mensajes de activación para Cuadra, un software de facturación para autónomos y pymes de España.
Recibes el bloqueo de la persona, el canal y la ayuda vigente. Escribe en español de España, cercano y
directo, tuteando, y pide una sola acción: la que le falta.

Reglas:
- Todo lo que digas sobre Cuadra tiene que estar en el material de ayuda que recibes.
- Rutas de menú solo de la lista de rutas válidas, siempre en negrita (**Ventas > Facturas**).
- No menciones precios, planes, descuentos, porcentajes, plazos, enlaces ni funciones de planes de pago.
- No uses el nombre de la persona: el mensaje es igual para todos los que comparten bloqueo.
- Respeta el límite de caracteres del canal para el cuerpo.
"""


def _texto(c: Contenido) -> str:
    return "\n".join([c.titulo, c.cuerpo, *c.pasos, c.boton])


def verificar_contenido(contenido: Contenido, canal: str, base: BaseVigente) -> list[str]:
    motivos = []
    texto = _texto(contenido)
    plano = normalizar_ruta(texto)
    for ruta in sorted(extraer_rutas(texto) - set(base.rutas_validas)):
        motivos.append(f"la ruta «{ruta}» no existe en la ayuda vigente")
    for frase in (f for a in base.articulos for f in a.frases_obsoletas):
        if normalizar_ruta(frase) in plano:
            motivos.append(f"usa una instrucción obsoleta: «{frase}»")
    for funcion in base.funciones_restringidas:
        if any(re.search(rf"\b{re.escape(p.lower())}\b", plano) for p in funcion.palabras_clave):
            motivos.append(f"menciona {funcion.nombre}, solo del plan {funcion.plan}")
    for nombre, patron in _PROMESAS.items():
        if patron.search(plano):
            motivos.append(f"contiene {nombre}")
    if _ENLACE.search(plano):
        motivos.append("contiene un enlace")
    if "{" in texto or "}" in texto:
        motivos.append("contiene llaves: el mensaje no se personaliza")
    limite = CANALES[canal]["limite"]
    if len(contenido.cuerpo) > limite:
        motivos.append(f"el cuerpo tiene {len(contenido.cuerpo)} caracteres; el máximo del canal es {limite}")
    return motivos


def _usuario(paso: str, canal: str, base: BaseVigente, motivo: str | None) -> str:
    articulos = [a for a in base.articulos if a.archivo in ARTICULOS_POR_PASO[paso]]
    partes = [
        f"<bloqueo>{OBJETIVO_POR_PASO[paso]}</bloqueo>",
        f"<canal>{CANALES[canal]['nombre']}. Límite del cuerpo: {CANALES[canal]['limite']} caracteres.</canal>",
        "<material_de_ayuda_vigente>",
        *[f'<articulo archivo="{a.archivo}">\n{a.texto_vigente}\n</articulo>' for a in articulos],
        "</material_de_ayuda_vigente>",
        "<rutas_validas>\n" + "\n".join(base.rutas_validas) + "\n</rutas_validas>",
        "<funciones_que_no_debes_mencionar>\n"
        + "\n".join(f"- {f.nombre}" for f in base.funciones_restringidas)
        + "\n</funciones_que_no_debes_mencionar>",
    ]
    if motivo:
        partes.append(f"<revision_anterior>La versión anterior no pasó la verificación: {motivo}</revision_anterior>")
    return "\n".join(partes)


def redactar_contenidos(base: BaseVigente, modelo) -> list[dict]:
    """Un contenido por bloqueo y canal (15). Lo que falla dos veces queda en revisión humana."""
    resultados = []
    for paso in PASOS:
        for canal in CANALES_A_REDACTAR:
            fila = {"paso": paso, "canal": canal, "estado": "revision", "motivos": [], "contenido": None, "intentos": 0}
            motivo = None
            for intento in (1, 2):
                try:
                    contenido = modelo.pedir(
                        tarea="intervencion", sistema=SISTEMA, usuario=_usuario(paso, canal, base, motivo), esquema=Contenido
                    )
                except (SinCache, Rechazo, ErrorModelo) as error:
                    fila["motivos"] = [f"sin contenido: {type(error).__name__}"]
                    break
                fila["intentos"] = intento
                fila["contenido"] = contenido.model_dump()
                motivos = verificar_contenido(contenido, canal, base)
                if not motivos:
                    fila["estado"], fila["motivos"] = "aprobado", []
                    break
                fila["motivos"], motivo = motivos, "; ".join(motivos)
            resultados.append(fila)
    return resultados
