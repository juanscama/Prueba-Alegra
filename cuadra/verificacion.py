"""Etapa 7: ningún correo sale sin pasar por reglas fijas y por un juez. Lo que falla dos veces lo ve una persona."""

import re

from pydantic import BaseModel, Field

from cuadra.conocimiento import BaseVigente, extraer_rutas, normalizar_ruta
from cuadra.modelo import ErrorModelo, Rechazo, SinCache
from cuadra.redaccion import (
    ARTICULOS_POR_PASO,
    LIMITE_ASUNTO,
    LIMITE_CUERPO,
    OBJETIVO_POR_PASO,
    SEGMENTO_LEGIBLE,
    Correo,
    Variante,
    redactar,
)

_LLAVES = re.compile(r"\{[^{}]*\}")
_NEGRITA = re.compile(r"\*\*([^*]+)\*\*")
_FLECHA = re.compile(r"[>›→]")
_PROMESAS = {
    "un importe en euros": re.compile(r"€|\beuros?\b"),
    "un porcentaje": re.compile(r"%"),
    "«descuento»": re.compile(r"\bdescuentos?\b"),
    "«gratis»": re.compile(r"\bgratis\b|\bgratuit[oa]s?\b"),
    "«oferta»": re.compile(r"\bofertas?\b"),
    "«promoción»": re.compile(r"\bpromoci(?:ón|ones)\b"),
}
_ENLACE = re.compile(r"https?://|www\.")


def verificar_reglas(correo: Correo, base: BaseVigente) -> list[str]:
    """Devuelve los motivos de rechazo; lista vacía si el correo cumple todas las reglas."""
    motivos = []
    texto = f"{correo.asunto}\n{correo.cuerpo}"
    plano = normalizar_ruta(texto)

    if correo.cuerpo.count("{nombre}") != 1:
        motivos.append("R1: el cuerpo debe contener {nombre} exactamente una vez")

    otras = sorted({llave for llave in _LLAVES.findall(texto) if llave != "{nombre}"})
    if otras:
        motivos.append(f"R2: hay campos entre llaves que el sistema no rellena: {', '.join(otras)}")
    elif "{" in texto.replace("{nombre}", "") or "}" in texto.replace("{nombre}", ""):
        motivos.append("R2: hay llaves sueltas; el campo del nombre se escribe {nombre}, con una sola llave")

    validas = set(base.rutas_validas)
    rutas = extraer_rutas(correo.cuerpo) | {normalizar_ruta(correo.ruta_menu)}
    for ruta in sorted(rutas - validas):
        motivos.append(f"R3: la ruta de menú «{ruta}» no existe en la ayuda vigente")
    flechas_en_negrita = sum(len(_FLECHA.findall(f)) for f in _NEGRITA.findall(correo.cuerpo))
    if len(_FLECHA.findall(correo.cuerpo)) > flechas_en_negrita:
        motivos.append("R3: hay una ruta de menú fuera de negrita; no se puede comprobar")

    for frase in (f for a in base.articulos for f in a.frases_obsoletas):
        if normalizar_ruta(frase) in plano:
            motivos.append(f"R4: usa una instrucción obsoleta: «{frase}»")
    for ruta in base.rutas_obsoletas:
        # Los tramos de una ruta obsoleta no pueden aparecer seguidos, los una el separador que los una.
        tramos = [re.escape(tramo) for tramo in ruta.split(" > ")]
        if re.search(r"[^.\n]{1,25}?".join(tramos), plano):
            motivos.append(f"R4: manda a una ruta de menú obsoleta: «{ruta}»")

    for funcion in base.funciones_restringidas:
        for palabra in funcion.palabras_clave:
            if re.search(rf"\b{re.escape(palabra.lower())}\b", plano):
                motivos.append(
                    f"R5: menciona «{palabra}», de {funcion.nombre}, que solo está en el plan {funcion.plan}"
                )
                break

    for nombre, patron in _PROMESAS.items():
        if patron.search(plano):
            motivos.append(f"R6: contiene {nombre}; el correo no puede hablar de precios ni promociones")

    if len(correo.cuerpo) > LIMITE_CUERPO:
        motivos.append(f"R7: el cuerpo tiene {len(correo.cuerpo)} caracteres; el máximo es {LIMITE_CUERPO}")
    if len(correo.asunto) > LIMITE_ASUNTO:
        motivos.append(f"R7: el asunto tiene {len(correo.asunto)} caracteres; el máximo es {LIMITE_ASUNTO}")

    if _ENLACE.search(plano):
        motivos.append("R8: contiene un enlace; la ayuda vigente no da ninguno")

    return motivos


class Veredicto(BaseModel):
    respaldado: bool = Field(description="Todo lo que el correo afirma sobre Cuadra aparece en el material de ayuda")
    responde_al_paso: bool = Field(description="El correo pide justo el paso que le falta a esta persona")
    tono_adecuado: bool = Field(description="Tono cercano y directo, en español de España, apropiado para ese oficio")
    un_solo_paso: bool = Field(description="Pide una sola acción, sin pasos posteriores ni otras funciones")
    motivos: list[str] = Field(description="Una frase por cada criterio incumplido; vacía si cumple todos")


SISTEMA_JUEZ = """\
Revisas correos de activación de Cuadra, un software de facturación para autónomos y pymes de España,
antes de que se envíen a personas que se registraron y no han emitido su primera factura. Un correo con una
instrucción equivocada deja a esa persona buscando un botón que no existe, así que tu revisión es la última
barrera.

Recibes el correo, la situación de la persona a la que va dirigido y el material de ayuda vigente. Evalúa
cuatro criterios por separado:

- respaldado: cada afirmación sobre lo que Cuadra hace, dónde está cada cosa o qué exige el producto
  aparece en el material de ayuda. Los ejemplos del oficio de la persona (a quién o qué facturaría) son
  ilustraciones y no cuentan como afirmaciones sobre el producto. Sí incumple cualquier dato inventado:
  tiempos, precios, plazos, funciones, consejos fiscales o legales.
- responde_al_paso: la acción que pide es el paso que le falta a esa persona según su situación.
- tono_adecuado: español de España, trato de tú, cercano y directo, sin tono publicitario ni reproches.
- un_solo_paso: pide una única acción. Explicar brevemente para qué sirve no cuenta como otro paso.

Sé estricto con los hechos y razonable con el estilo: rechaza por un dato sin respaldo, no por una
preferencia de redacción. En motivos, escribe una frase concreta por cada criterio incumplido, citando el
fragmento que falla, para que quien redacta pueda corregirlo.
"""

ETIQUETAS = {
    "respaldado": "afirma algo que la ayuda vigente no respalda",
    "responde_al_paso": "no pide el paso que le falta a esta persona",
    "tono_adecuado": "el tono no es el adecuado",
    "un_solo_paso": "pide más de una acción",
}


def juzgar(correo: Correo, variante: Variante, base: BaseVigente, modelo, segmento: str) -> Veredicto:
    articulos = [a for a in base.articulos if a.archivo in ARTICULOS_POR_PASO[variante.paso]]
    material = "\n\n".join(
        f'<articulo archivo="{a.archivo}">\n{a.texto_vigente}\n</articulo>' for a in articulos
    )
    usuario = "\n".join(
        [
            "<persona>",
            f"Oficio: {variante.actividad}",
            f"Tipo de negocio: {SEGMENTO_LEGIBLE.get(segmento, segmento)}",
            f"Situación: {OBJETIVO_POR_PASO[variante.paso]}",
            "</persona>",
            "",
            "<material_de_ayuda_vigente>",
            material,
            "</material_de_ayuda_vigente>",
            "",
            "<correo>",
            f"Asunto: {correo.asunto}",
            "",
            correo.cuerpo,
            "</correo>",
        ]
    )
    return modelo.pedir(tarea="juez", sistema=SISTEMA_JUEZ, usuario=usuario, esquema=Veredicto)


def _motivos_del_juez(veredicto: Veredicto) -> list[str]:
    incumplidos = [etiqueta for campo, etiqueta in ETIQUETAS.items() if not getattr(veredicto, campo)]
    if not incumplidos:
        return []
    detalle = veredicto.motivos or incumplidos
    return [f"Juez: {motivo}" for motivo in detalle]


class VarianteProcesada(BaseModel):
    variante: Variante
    correo: Correo | None
    estado: str  # aprobada | revision
    motivos: list[str]
    intentos: int
    veredicto: Veredicto | None = None


def en_revision(variante: Variante, motivo: str, intentos: int = 0) -> VarianteProcesada:
    return VarianteProcesada(variante=variante, correo=None, estado="revision", motivos=[motivo], intentos=intentos)


def procesar(variante: Variante, base: BaseVigente, modelo, segmento: str) -> VarianteProcesada:
    """Redacta y verifica. Un rechazo da derecho a un segundo intento con los motivos; dos, a revisión humana."""
    correo, veredicto, motivos = None, None, []
    for intento in (1, 2):
        try:
            correo = redactar(variante, base, modelo, segmento, motivo_rechazo="; ".join(motivos) or None)
            veredicto = None
            motivos = verificar_reglas(correo, base)
            if not motivos:
                veredicto = juzgar(correo, variante, base, modelo, segmento)
                motivos = _motivos_del_juez(veredicto)
        except SinCache:
            return en_revision(variante, "sin caché y sin clave", intento)
        except Rechazo:
            return en_revision(variante, "el modelo declinó", intento)
        except ErrorModelo as error:
            return en_revision(variante, f"error de la API: {error}", intento)
        if not motivos:
            return VarianteProcesada(
                variante=variante, correo=correo, estado="aprobada", motivos=[], intentos=intento, veredicto=veredicto
            )
    return VarianteProcesada(
        variante=variante, correo=correo, estado="revision", motivos=motivos, intentos=2, veredicto=veredicto
    )
