"""Informe ejecutivo redactado por Claude a partir de cifras ya calculadas. Ninguna cifra puede ser inventada.

Cada número del informe tiene que aparecer en los hechos que recibe el modelo; si no, se rechaza y se pide
de nuevo una vez. Lo que sigue fallando se muestra marcado como no verificado.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from cuadra.modelo import ErrorModelo, Rechazo, SinCache

SECCIONES = [
    ("donde_se_pierde", "¿Dónde se pierde más gente?"),
    ("quien_tiene_dificultades", "¿Qué usuarios tienen más dificultades?"),
    ("mayor_oportunidad", "¿Qué problemas son la mayor oportunidad?"),
    ("investigar_primero", "¿Qué debería investigar primero Growth?"),
    ("que_encontramos", "1. Qué encontramos"),
    ("que_significa", "2. Qué significa para el negocio"),
    ("evidencia", "3. Qué evidencia lo respalda"),
    ("hipotesis", "4. Qué hipótesis proponemos"),
    ("experimento", "5. Qué experimento recomendamos"),
    ("datos_adicionales", "6. Qué datos adicionales necesitamos"),
]


class Punto(BaseModel):
    texto: str
    tipo: Literal["hecho", "hipotesis", "recomendacion"]
    fuentes: list[str] = Field(description="Ids de los hechos en que se apoya (p. ej. F3, H1)")


class Informe(BaseModel):
    donde_se_pierde: list[Punto]
    quien_tiene_dificultades: list[Punto]
    mayor_oportunidad: list[Punto]
    investigar_primero: list[Punto]
    que_encontramos: list[Punto]
    que_significa: list[Punto]
    evidencia: list[Punto]
    hipotesis: list[Punto]
    experimento: list[Punto]
    datos_adicionales: list[Punto]


SISTEMA = """\
Eres analista de Growth en Cuadra, un software de facturación para autónomos y pymes de España. Escribes un
informe ejecutivo breve para el equipo, en español de España, claro y sin jerga estadística.

Reglas estrictas:
- Usa SOLO las cifras que aparecen en los hechos, escritas igual (mismo número, mismo formato). No calcules
  cifras nuevas, no redondees de otra forma y no conviertas porcentajes. Si necesitas una cifra que no está,
  escribe la idea sin cifra.
- Cada punto lleva el tipo correcto: «hecho» si lo dicen los datos, «hipotesis» si es una explicación posible,
  «recomendacion» si es una acción. No presentes una correlación como causa.
- Las estimaciones (marcadas como tales en los hechos) se citan como estimaciones, nunca como resultados.
- No hay resultados del experimento todavía: no digas que el correo funciona ni que no funciona.
- Cada punto cita en `fuentes` los ids de los hechos que usa. De 1 a 3 puntos por sección, frases cortas.
"""

_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _normalizar(numero: str) -> str:
    numero = numero.replace(",", ".")
    if "." in numero:
        numero = numero.rstrip("0").rstrip(".")
    return numero


def numeros(texto: str) -> set[str]:
    return {_normalizar(n) for n in _NUMERO.findall(texto)}


def verificar_informe(informe: Informe, hechos: list[dict]) -> list[str]:
    """Motivos de rechazo: cifras que no están en los hechos y fuentes que no existen."""
    permitidos = numeros(json.dumps(hechos, ensure_ascii=False))
    ids = {h["id"] for h in hechos}
    motivos = []
    for clave, _ in SECCIONES:
        for punto in getattr(informe, clave):
            sobrantes = numeros(punto.texto) - permitidos
            if sobrantes:
                motivos.append(f"cifras que no están en los hechos: {', '.join(sorted(sobrantes))} («{punto.texto[:60]}…»)")
            desconocidas = set(punto.fuentes) - ids
            if desconocidas:
                motivos.append(f"fuentes inexistentes: {', '.join(sorted(desconocidas))}")
            if not punto.fuentes:
                motivos.append(f"un punto sin fuentes («{punto.texto[:60]}…»)")
    return motivos


def _usuario(hechos: list[dict], motivo: str | None) -> str:
    texto = "<hechos>\n" + json.dumps(hechos, ensure_ascii=False, indent=1) + "\n</hechos>"
    if motivo:
        texto += f"\n<revision_anterior>La versión anterior no pasó la verificación: {motivo}</revision_anterior>"
    return texto


def redactar_informe(hechos: list[dict], modelo) -> dict:
    motivo = None
    resultado = {"estado": "sin_informe", "motivos": [], "informe": None, "intentos": 0}
    for intento in (1, 2):
        try:
            informe = modelo.pedir(tarea="informe_ejecutivo", sistema=SISTEMA, usuario=_usuario(hechos, motivo), esquema=Informe)
        except (SinCache, Rechazo, ErrorModelo) as error:
            resultado["motivos"] = [f"{type(error).__name__}: {error}"]
            return resultado
        motivos = verificar_informe(informe, hechos)
        resultado.update(informe=informe.model_dump(), intentos=intento, motivos=motivos)
        if not motivos:
            resultado["estado"] = "verificado"
            return resultado
        resultado["estado"] = "no_verificado"
        motivo = "; ".join(motivos)
    return resultado
