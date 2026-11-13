"""Etapa 5: qué dice hoy el Centro de Ayuda, una vez cruzado con las notas de cambios de la semana."""

import re
from pathlib import Path

from pydantic import BaseModel, Field

from cuadra.config import DIR_AYUDAS, DIR_NOTAS


class ArticuloVigente(BaseModel):
    archivo: str
    titulo: str
    vigente: bool = Field(description="False si alguna nota de cambios contradice o deja obsoleta alguna frase")
    frases_obsoletas: list[str] = Field(description="Frases del artículo original que ya no son ciertas, citadas textualmente")
    texto_vigente: str = Field(description="El artículo completo en Markdown, corregido solo donde una nota lo cambia")
    notas_que_lo_cambian: list[str] = Field(description="Nombres de archivo de las notas en que se apoya la corrección")


class FuncionRestringida(BaseModel):
    nombre: str
    plan: str = Field(description="Plan que da acceso a la función")
    limites: list[str] = Field(description="Lo que la nota dice que todavía no se puede hacer")
    palabras_clave: list[str] = Field(description="Palabras en minúsculas que delatan que un texto habla de esta función")


class Restricciones(BaseModel):
    funciones: list[FuncionRestringida]


class BaseVigente(BaseModel):
    articulos: list[ArticuloVigente]
    funciones_restringidas: list[FuncionRestringida]
    rutas_validas: list[str]
    rutas_obsoletas: list[str]


SISTEMA_ARTICULO = """\
Mantienes al día el Centro de Ayuda de Cuadra, un software de facturación para autónomos y pymes de España.
Recibes un artículo de ayuda y las notas de cambios del producto publicadas esta semana.

Tu tarea es decidir si el artículo sigue siendo cierto y, si no, corregirlo.

- Compara cada instrucción del artículo con las notas. Una nota solo afecta al artículo si cambia algo que
  el artículo afirma: la ubicación de un botón, lo que un campo admite, una respuesta de las preguntas
  frecuentes. Una función nueva sobre otro tema no vuelve obsoleto el artículo.
- Si nada cambia, marca el artículo como vigente, deja la lista de frases obsoletas vacía y devuelve el
  texto tal cual.
- Si algo cambia, cita en frases_obsoletas cada frase original afectada, copiada literalmente, y devuelve
  en texto_vigente el artículo completo con esas frases reescritas según la nota. No toques lo demás.
- Usa solo lo que dicen el artículo y las notas. Si una nota no aclara un detalle, no lo inventes.
- Conserva el formato Markdown y las negritas de botones y rutas de menú, escritas como «Menú > Opción».
"""

SISTEMA_RESTRICCIONES = """\
Lees las notas de cambios de esta semana de Cuadra, un software de facturación para autónomos y pymes de
España. Otro equipo escribirá correos a personas que acaban de registrarse y que todavía no tienen ningún
plan de pago.

Devuelve las funciones mencionadas en las notas que no están disponibles en todos los planes. Para cada
una: su nombre, el plan que la incluye, los límites que la nota declara y unas pocas palabras clave en
minúsculas (singular y plural) con las que se detectaría que un correo habla de ella. Si una función está
en todos los planes, no la incluyas.
"""

# Las comillas españolas «…» no son flechas: » queda fuera a propósito.
_FLECHAS = re.compile(r"\s*(?:>|›|→)\s*")
_NEGRITA = re.compile(r"\*\*([^*]+)\*\*")
_SEPARADORES_EN_NEGRITA = re.compile(r"\s*[/»]\s*")


def normalizar_ruta(texto: str) -> str:
    texto = texto.replace("*", "").strip().lower()
    texto = _FLECHAS.sub(" > ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _es_ruta(fragmento: str) -> bool:
    """Dentro de una negrita también cuentan como separador «/» y «»» (si no cierra unas comillas)."""
    return bool(_FLECHAS.search(fragmento)) or "/" in fragmento or ("»" in fragmento and "«" not in fragmento)


def extraer_rutas(texto: str) -> set[str]:
    """Rutas de menú: fragmentos en negrita con un separador, como **Ventas > Facturas**."""
    return {
        normalizar_ruta(_SEPARADORES_EN_NEGRITA.sub(" > ", fragmento))
        for fragmento in _NEGRITA.findall(texto)
        if _es_ruta(fragmento.strip())
    }


def leer_documentos(directorio: Path) -> dict[str, str]:
    return {
        ruta.name: ruta.read_text(encoding="utf-8").strip()
        for ruta in sorted(Path(directorio).glob("*.md"))
        if not ruta.name.startswith(".")
    }


def _bloque_notas(notas: dict[str, str]) -> str:
    return "\n\n".join(f'<nota archivo="{nombre}">\n{texto}\n</nota>' for nombre, texto in notas.items())


def construir_base(modelo, dir_ayudas: Path = DIR_AYUDAS, dir_notas: Path = DIR_NOTAS) -> BaseVigente:
    ayudas, notas = leer_documentos(dir_ayudas), leer_documentos(dir_notas)
    bloque_notas = _bloque_notas(notas)

    articulos = []
    for archivo, original in ayudas.items():
        revision = modelo.pedir(
            tarea="conocimiento_articulo",
            sistema=SISTEMA_ARTICULO,
            usuario=f'<articulo archivo="{archivo}">\n{original}\n</articulo>\n\n{bloque_notas}',
            esquema=ArticuloVigente,
        )
        cambios = {"archivo": archivo}
        if revision.vigente:
            # Un artículo vigente se conserva byte a byte: el modelo no puede alterarlo por descuido.
            cambios.update(texto_vigente=original, frases_obsoletas=[], notas_que_lo_cambian=[])
        articulos.append(revision.model_copy(update=cambios))

    restricciones = modelo.pedir(
        tarea="conocimiento_restricciones",
        sistema=SISTEMA_RESTRICCIONES,
        usuario=bloque_notas,
        esquema=Restricciones,
    )

    validas = set()
    for articulo in articulos:
        validas |= extraer_rutas(articulo.texto_vigente)
    for texto in notas.values():
        validas |= extraer_rutas(texto)
    originales = set()
    for texto in ayudas.values():
        originales |= extraer_rutas(texto)

    return BaseVigente(
        articulos=articulos,
        funciones_restringidas=restricciones.funciones,
        rutas_validas=sorted(validas),
        rutas_obsoletas=sorted(originales - validas),
    )
