"""Etapa 6: un correo por variante (paso × actividad × tramo). El nombre se inserta después."""

from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel, Field

from cuadra.conocimiento import BaseVigente

PASOS_ATASCADO = ["sin_configurar", "sin_cliente", "sin_factura"]
TRAMOS_CON_CORREO = ["reciente", "rezagado"]

LIMITE_CUERPO = 900
LIMITE_ASUNTO = 60


@dataclass(frozen=True)
class Variante:
    paso: str
    actividad: str
    tramo: str

    @property
    def clave(self) -> str:
        return f"{self.paso}|{self.actividad}|{self.tramo}"


class Correo(BaseModel):
    asunto: str = Field(description=f"Asunto del correo, como máximo {LIMITE_ASUNTO} caracteres")
    cuerpo: str = Field(description=f"Cuerpo del correo, como máximo {LIMITE_CUERPO} caracteres, con {{nombre}} en el saludo")
    paso_siguiente: str = Field(description="La única acción que se le pide a la persona, en pocas palabras")
    ruta_menu: str = Field(description="Ruta de menú por la que empieza esa acción, copiada de la lista de rutas válidas")
    articulo_fuente: str = Field(description="Nombre de archivo del artículo de ayuda en que se apoyan las instrucciones")


SISTEMA = """\
Escribes correos de activación para Cuadra, un software de facturación para autónomos y pymes de España.
Cada correo va a personas que se registraron y se quedaron a medio camino de emitir su primera factura.
El correo existe para que den el siguiente paso hoy: una persona ocupada, que no conoce el producto, tiene
que poder leerlo en medio minuto y saber exactamente dónde pulsar.

Escribes una plantilla por tipo de persona: el mismo texto llegará a todas las que comparten oficio, paso
y antigüedad, y el sistema sustituirá {nombre} por el nombre de cada una.

Cómo escribir:
- Español de España, trato de tú, tono cercano y directo, de persona a persona. Sin signos de exclamación
  encadenados ni lenguaje publicitario.
- Saluda con {nombre} una sola vez, al principio. No uses ningún otro campo entre llaves.
- Pide una sola acción: el paso que le falta a esa persona. No añadas pasos posteriores ni otras funciones.
- Da las instrucciones exactas del artículo de ayuda: mismas rutas de menú y mismos nombres de botón, en
  negrita con dos asteriscos. Las rutas de menú se escriben «Menú > Opción» y solo puedes usar las de la
  lista de rutas válidas, copiadas tal cual. Los nombres de botón van en negrita sin flecha.
- Aterriza el mensaje en su oficio con un ejemplo breve y verosímil de a quién o qué facturaría. El
  ejemplo ilustra; no describe nada que el producto haga.
- Todo lo que digas sobre Cuadra tiene que estar en el material que recibes. No menciones precios, planes,
  descuentos, plazos, tiempos («en dos minutos»), enlaces ni consejos fiscales o legales.
- No menciones las funciones restringidas a un plan: estas personas no tienen plan de pago.
- Cuerpo de 900 caracteres como máximo y asunto de 60 como máximo. Cierra con «El equipo de Cuadra».
"""

OBJETIVO_POR_PASO = {
    "sin_configurar": (
        "Se registró pero no ha completado los datos de su empresa. El paso que le falta: completar el NIF "
        "y la dirección fiscal de su empresa en la configuración, porque sin esos datos Cuadra no deja "
        "emitir facturas."
    ),
    "sin_cliente": (
        "Ya configuró su empresa pero no ha creado ningún cliente. El paso que le falta: abrir una factura "
        "nueva y crear ahí su primer cliente. Es el punto donde más gente de su perfil se queda."
    ),
    "sin_factura": (
        "Ya configuró su empresa y creó un cliente, pero no ha emitido ninguna factura. El paso que le "
        "falta: emitir la primera. Si le frena el miedo a equivocarse, puede guardarla antes como borrador."
    ),
}

TONO_POR_TRAMO = {
    "reciente": (
        "Se registró hace pocos días y lleva unos días sin avanzar. Háblale como a alguien que está a "
        "mitad de la puesta en marcha."
    ),
    "rezagado": (
        "Se registró hace semanas y no ha vuelto. Háblale como a alguien que lo dejó aparcado: su cuenta "
        "sigue como la dejó y puede retomar justo en ese punto. No le reproches el tiempo pasado."
    ),
}

ARTICULOS_POR_PASO = {
    "sin_configurar": ["01-crear-tu-primera-factura.md"],
    "sin_cliente": ["01-crear-tu-primera-factura.md"],
    "sin_factura": ["01-crear-tu-primera-factura.md", "02-configurar-el-iva-de-tus-productos.md"],
}

SEGMENTO_LEGIBLE = {"autonomo": "autónomo", "pyme": "pyme"}


def variantes_posibles(contactos: pd.DataFrame) -> list[Variante]:
    return [
        Variante(paso, actividad, tramo)
        for paso in PASOS_ATASCADO
        for actividad in sorted(contactos.actividad.unique())
        for tramo in TRAMOS_CON_CORREO
    ]


def segmento_de(contactos: pd.DataFrame) -> dict[str, str]:
    """Cada oficio pertenece a un solo segmento; si dejara de ser así, la variante necesitaría el segmento."""
    pares = contactos[["actividad", "segmento"]].drop_duplicates()
    if pares.actividad.duplicated().any():
        raise ValueError("Hay actividades en más de un segmento: la variante debe incluir el segmento")
    return dict(zip(pares.actividad, pares.segmento))


def redactar(
    variante: Variante,
    base: BaseVigente,
    modelo,
    segmento: str,
    motivo_rechazo: str | None = None,
) -> Correo:
    articulos = [a for a in base.articulos if a.archivo in ARTICULOS_POR_PASO[variante.paso]]
    material = "\n\n".join(
        f'<articulo archivo="{a.archivo}">\n{a.texto_vigente}\n</articulo>' for a in articulos
    )
    restringidas = "\n".join(f"- {f.nombre} (solo plan {f.plan})" for f in base.funciones_restringidas)
    partes = [
        "<persona>",
        f"Oficio: {variante.actividad}",
        f"Tipo de negocio: {SEGMENTO_LEGIBLE.get(segmento, segmento)}",
        f"Situación: {OBJETIVO_POR_PASO[variante.paso]}",
        f"Antigüedad: {TONO_POR_TRAMO[variante.tramo]}",
        "</persona>",
        "",
        "<material_de_ayuda_vigente>",
        material,
        "</material_de_ayuda_vigente>",
        "",
        "<rutas_validas>",
        "\n".join(base.rutas_validas),
        "</rutas_validas>",
        "",
        "<funciones_que_no_debes_mencionar>",
        restringidas or "(ninguna)",
        "</funciones_que_no_debes_mencionar>",
    ]
    if motivo_rechazo:
        partes += [
            "",
            "<revision_anterior>",
            "Una versión anterior de este correo no pasó la verificación. Escríbelo de nuevo corrigiendo esto.",
            f"Motivo del rechazo: {motivo_rechazo}",
            "</revision_anterior>",
        ]
    return modelo.pedir(tarea="redaccion", sistema=SISTEMA, usuario="\n".join(partes), esquema=Correo)


def personalizar(correo: Correo, nombre: str) -> tuple[str, str]:
    """Inserta el nombre con replace: un texto con otras llaves no puede romper el envío."""
    return correo.asunto.replace("{nombre}", nombre), correo.cuerpo.replace("{nombre}", nombre)
