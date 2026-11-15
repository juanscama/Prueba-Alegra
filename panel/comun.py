"""Piezas compartidas por las páginas del panel: lectura de salida/, formatos, nombres legibles y estilos."""

import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # raíz del repo, para importar `cuadra` sin instalarlo

import pandas as pd
import streamlit as st

from cuadra import config



def dir_salida() -> Path:
    """Se lee en cada llamada: este módulo queda en memoria entre ejecuciones y la carpeta puede cambiar."""
    return Path(os.environ.get("CUADRA_DIR_SALIDA") or config.DIR_SALIDA)


def dir_inteligencia() -> Path:
    return dir_salida() / config.DIR_INTELIGENCIA_NOMBRE


# Colores. Azul para lo que importa, gris para el contexto y naranja solo cuando hay una segunda serie.
AZUL, NARANJA, GRIS, TINTA = "#2a78d6", "#eb6834", "#cbd5e1", "#0f172a"

NOMBRE_PASO = {
    "registro": "Se registró",
    "configuro_empresa": "Configuró su empresa",
    "creo_cliente": "Creó un cliente",
    "emitio_primera_factura": "Emitió su primera factura",
    "emitio_5_facturas": "Emitió 5 facturas",
    "pago": "Pagó",
}
NOMBRE_ATASCO = {
    "sin_configurar": "Sin configurar su empresa",
    "sin_cliente": "Sin crear un cliente",
    "sin_factura": "Sin emitir la primera factura",
}
NOMBRE_CANAL = {"organico": "Orgánico", "contador": "Contador", "pago": "Anuncios", "referido": "Referido"}
NOMBRE_SEGMENTO = {"autonomo": "autónomos", "pyme": "pymes"}
NOMBRE_TRAMO = {"reciente": "Hace poco (3 a 14 días)", "rezagado": "Hace tiempo (más de 14 días)"}

ESTILOS = """
<style>
.block-container {padding-top: 2.4rem; max-width: 1180px;}
.portada {background: linear-gradient(135deg, #0b1f3a 0%, #14315c 100%); border-radius: 18px;
          padding: 34px 38px 30px; color: #ffffff; margin-bottom: 18px;}
.portada .marca {font-size: 0.78rem; letter-spacing: 0.14em; text-transform: uppercase; color: #9ec5f4; font-weight: 600;}
.portada h1 {font-size: 2.3rem; line-height: 1.15; margin: 8px 0 12px; color: #ffffff; padding: 0;}
.portada p {font-size: 1.1rem; line-height: 1.55; color: #dbe7f7; max-width: 900px; margin: 0;}
.portada .pie {margin-top: 16px; font-size: 0.8rem; color: #9ec5f4;}
.tarjetas {display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 0 0 8px;}
.tarjetas.tres {grid-template-columns: repeat(3, 1fr);}
.tarjeta {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 20px;}
.tarjeta .cifra {font-size: 2.2rem; font-weight: 700; color: #0f172a; line-height: 1.05;}
.tarjeta .titulo {font-size: 0.97rem; font-weight: 600; color: #0f172a; margin-top: 6px;}
.tarjeta .nota {font-size: 0.86rem; color: #52514e; margin-top: 4px; line-height: 1.45;}
.tarjeta.destacada {background: #eef5fd; border-color: #b7d3f6;}
.tarjeta.destacada .cifra {color: #1c5cab;}
.capitulo {margin: 38px 0 6px;}
.capitulo .num {font-size: 0.78rem; letter-spacing: 0.12em; text-transform: uppercase; color: #2a78d6; font-weight: 700;}
.capitulo h2 {font-size: 1.7rem; margin: 2px 0 6px; padding: 0; color: #0f172a;}
.capitulo p {font-size: 1.03rem; color: #334155; line-height: 1.55; max-width: 900px; margin: 0;}
.idea {background: #f8fafc; border-left: 4px solid #2a78d6; border-radius: 0 12px 12px 0; padding: 14px 18px;
       font-size: 1.03rem; line-height: 1.55; color: #1f2937; margin: 10px 0 16px;}
.pasos {display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 10px 0 18px;}
.paso {border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px 18px; background: #ffffff;}
.paso .n {display: inline-block; width: 26px; height: 26px; border-radius: 50%; background: #2a78d6; color: #fff;
          font-size: 0.85rem; font-weight: 700; text-align: center; line-height: 26px; margin-bottom: 8px;}
.paso .t {font-weight: 700; color: #0f172a; font-size: 1rem; display: block;}
.paso .d {font-size: 0.9rem; color: #475569; margin-top: 6px; line-height: 1.45;}
.quien {display: inline-block; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.05em; border-radius: 999px;
        padding: 2px 9px; margin-top: 10px;}
.quien.ia {background: #dcf3dc; color: #0b7a0b;}
.quien.codigo {background: #e9edf2; color: #334155;}
.grupos {display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 10px 0 14px;}
.grupo {border-radius: 14px; padding: 18px 20px; border: 1px solid #e2e8f0;}
.grupo.t {background: #eef5fd; border-color: #b7d3f6;}
.grupo.c {background: #fff4ee; border-color: #f6c9b3;}
.grupo .cifra {font-size: 2rem; font-weight: 700; color: #0f172a;}
.grupo .titulo {font-weight: 600; color: #0f172a;}
.grupo .nota {font-size: 0.88rem; color: #52514e; margin-top: 4px; line-height: 1.45;}
.linea {display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 6px 0 16px;}
.hito {border-top: 3px solid #2a78d6; padding: 10px 4px 0;}
.hito .cuando {font-weight: 700; color: #0f172a;}
.hito .que {font-size: 0.92rem; color: #475569; line-height: 1.45; margin-top: 4px;}
.caja {border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px 18px; background: #ffffff;}
.caja h4 {margin: 0 0 10px; padding: 0; font-size: 1rem; color: #0f172a;}
.caja .dato {font-size: 0.94rem; color: #1f2937; margin: 5px 0; line-height: 1.45;}
.caja .dato span {color: #52514e; font-weight: 600;}
.caja.antes {background: #fff6f6; border-color: #f3c6c6;}
.caja.despues {background: #f3fbf3; border-color: #bfe3bf;}
.caja ul.lista {margin: 4px 0 8px; padding-left: 18px; font-size: 0.9rem;}
.caja ul.lista li {margin: 2px 0;}
.caja ul.lista li::marker {content: "✓  "; color: #0b7a0b;}
.caja ul.lista li.no::marker {content: "✗  "; color: #b02a2a;}
.confianza {display: grid; grid-template-columns: 1fr 1fr; gap: 12px 18px; margin: 10px 0 8px;}
.confianza div {font-size: 0.97rem; line-height: 1.5; color: #1f2937; padding-left: 26px; position: relative;}
.confianza div::before {content: "✓"; position: absolute; left: 4px; color: #0b7a0b; font-weight: 700;}
.limites div::before {content: "–"; color: #8a5a00;}
.etiqueta {display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; border-radius: 999px; padding: 2px 9px;}
.etiqueta.mal {background: #fbe1e1; color: #b02a2a;}
.etiqueta.ok {background: #dcf3dc; color: #0b7a0b;}
.etiqueta.sim {background: #fbe1e1; color: #b02a2a;}
.etiqueta.est {background: #fff1d6; color: #8a5a00;}
.correo {border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; background: #ffffff;}
.correo .cabecera {background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 12px 20px; font-size: 0.86rem; color: #52514e;}
.correo .cabecera b {color: #0f172a;}
.correo .asunto {font-size: 1.12rem; font-weight: 700; color: #0f172a; padding: 16px 20px 0;}
.correo .cuerpo {padding: 8px 20px 18px; font-size: 0.98rem; line-height: 1.6; color: #1f2937;}
.correo .cuerpo p {margin: 10px 0;}
.correo .cuerpo ol {margin: 8px 0 8px 2px; padding-left: 22px;}
.correo .cuerpo strong {color: #0b1f3a; background: #eef5fd; border-radius: 4px; padding: 0 3px;}
table.cuentas {width: 100%; border-collapse: collapse; margin: 6px 0 18px; font-size: 0.98rem;}
table.cuentas td {padding: 9px 14px; border-bottom: 1px solid #e2e8f0; color: #1f2937; line-height: 1.4;}
table.cuentas td.n {text-align: right; font-weight: 700; color: #0f172a; white-space: nowrap; width: 110px;
                    font-size: 1.05rem;}
table.cuentas td .por {display: block; font-size: 0.84rem; color: #52514e; margin-top: 2px;}
table.cuentas tr.total td {background: #0b1f3a; color: #ffffff; font-weight: 700;}
table.cuentas tr.total td.n {color: #ffffff;}
table.cuentas tr.total td .por {color: #dbe7f7;}
table.cuentas tr.grupo td {background: #f1f5f9; font-weight: 700;}
table.cuentas tr.clave td {background: #eef5fd; font-weight: 700;}
table.cuentas tr.clave td.n {color: #1c5cab;}
table.cuentas tr.sub td:first-child {padding-left: 38px;}
table.cuentas tr.sub td.n {font-weight: 600;}
.glosario {display: grid; grid-template-columns: 1fr 1fr; gap: 8px 22px; font-size: 0.92rem; line-height: 1.45;}
.glosario b {color: #0f172a;}
[data-testid="stHeaderActionElements"] {display: none;}
div[data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
button[data-baseweb="tab"] {font-size: 1rem; padding: 10px 16px;}
</style>
"""


def estilos() -> None:
    st.markdown(ESTILOS, unsafe_allow_html=True)


def leer_csv(nombre: str, carpeta: Path | None = None) -> pd.DataFrame | None:
    ruta = (carpeta or dir_salida()) / nombre
    return pd.read_csv(ruta) if ruta.is_file() else None


def leer_json(nombre: str, carpeta: Path | None = None):
    ruta = (carpeta or dir_salida()) / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def miles(numero) -> str:
    return f"{int(numero):,}".replace(",", ".")


def pct(valor: float, decimales: int = 0) -> str:
    return f"{valor * 100:.{decimales}f}%".replace(".", ",")


def decimal(texto: str) -> str:
    """Coma decimal, como se escribe en español."""
    return texto.replace(".", ",")


def bloque(contenido: str) -> None:
    st.markdown(contenido, unsafe_allow_html=True)


def capitulo(numero: str, titulo: str, bajada: str) -> None:
    bloque(f'<div class="capitulo"><div class="num">{numero}</div><h2>{titulo}</h2><p>{bajada}</p></div>')


def cuerpo_html(cuerpo: str) -> str:
    """Convierte un texto con **negritas** y listas numeradas en HTML, escapando todo lo demás."""
    partes, lista = [], []

    def cerrar_lista():
        if lista:
            partes.append("<ol>" + "".join(f"<li>{item}</li>" for item in lista) + "</ol>")
            lista.clear()

    for linea in html.escape(cuerpo).split("\n"):
        linea = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", linea.strip())
        numerada = re.match(r"^\d+\.\s+(.*)$", linea)
        if numerada:
            lista.append(numerada.group(1))
        elif linea:
            cerrar_lista()
            partes.append(f"<p>{linea}</p>")
        else:
            cerrar_lista()
    cerrar_lista()
    return "".join(partes)


def correo_html(para: str, asunto: str, cuerpo: str) -> str:
    return (
        '<div class="correo">'
        f'<div class="cabecera"><b>De:</b> El equipo de Cuadra &nbsp;·&nbsp; <b>Para:</b> {html.escape(para)}</div>'
        f'<div class="asunto">{html.escape(asunto)}</div>'
        f'<div class="cuerpo">{cuerpo_html(cuerpo)}</div>'
        "</div>"
    )


def pasos_del_articulo(texto: str) -> str:
    """La sección «Pasos» de un artículo de ayuda, sin título ni preguntas frecuentes."""
    return texto.split("## Preguntas frecuentes")[0].split("## Pasos")[-1].strip()


def enlace(pagina: str, texto: str, icono: str) -> None:
    """Enlace a otra página del panel. Si la página se abre sola (sin el menú, como en las pruebas), no se muestra."""
    from streamlit.errors import StreamlitPageNotFoundError

    try:
        st.page_link(pagina, label=texto, icon=icono)
    except StreamlitPageNotFoundError:
        pass
