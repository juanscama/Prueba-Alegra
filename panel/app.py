"""Panel local: muestra lo que dejó la última corrida en salida/. No recalcula nada, salvo la redacción en vivo."""

import html
import json
import os
import re
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from cuadra import config
from cuadra.conocimiento import BaseVigente
from cuadra.modelo import Modelo, hay_clave
from cuadra.redaccion import Variante, personalizar
from cuadra.verificacion import procesar

DIR = Path(os.environ.get("CUADRA_DIR_SALIDA") or config.DIR_SALIDA)

# Colores. Azul para lo que importa, gris para el contexto y naranja solo cuando hay una segunda serie.
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#cbd5e1"
TINTA = "#0f172a"

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
CRITERIOS_JUEZ = {
    "respaldado": "Todo lo que dice está en la ayuda vigente",
    "responde_al_paso": "Pide justo el paso que le falta",
    "tono_adecuado": "Tono cercano y directo",
    "un_solo_paso": "Pide una sola acción",
}
REGLAS = [
    "Lleva el nombre de la persona",
    "Solo usa rutas de menú que existen hoy",
    "Ninguna instrucción obsoleta",
    "No ofrece funciones de planes de pago",
    "Sin precios, descuentos ni enlaces",
    "Largo dentro del límite",
]

ESTILOS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1240px;}
.portada {background: linear-gradient(135deg, #0b1f3a 0%, #14315c 100%); border-radius: 18px;
          padding: 34px 38px 30px; color: #ffffff; margin-bottom: 18px;}
.portada .marca {font-size: 0.78rem; letter-spacing: 0.14em; text-transform: uppercase; color: #9ec5f4; font-weight: 600;}
.portada h1 {font-size: 2.35rem; line-height: 1.15; margin: 8px 0 12px; color: #ffffff; padding: 0;}
.portada p {font-size: 1.08rem; line-height: 1.55; color: #dbe7f7; max-width: 880px; margin: 0;}
.portada .pie {margin-top: 16px; font-size: 0.8rem; color: #9ec5f4;}
.tarjetas {display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 0 0 18px;}
.tarjeta {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 20px;}
.tarjeta .cifra {font-size: 2.3rem; font-weight: 700; color: #0f172a; line-height: 1.05;}
.tarjeta .titulo {font-size: 0.95rem; font-weight: 600; color: #0f172a; margin-top: 6px;}
.tarjeta .nota {font-size: 0.84rem; color: #52514e; margin-top: 4px; line-height: 1.4;}
.tarjeta.destacada {background: #eef5fd; border-color: #b7d3f6;}
.tarjeta.destacada .cifra {color: #1c5cab;}
.pasos {display: grid; grid-template-columns: repeat(5, 1fr); gap: 0; margin: 4px 0 22px; border: 1px solid #e2e8f0;
        border-radius: 14px; overflow: hidden; background: #f8fafc;}
.paso {padding: 14px 16px 15px; border-right: 1px solid #e2e8f0; position: relative;}
.paso:last-child {border-right: none;}
.paso .n {display: inline-block; width: 22px; height: 22px; border-radius: 50%; background: #2a78d6; color: #fff;
          font-size: 0.78rem; font-weight: 700; text-align: center; line-height: 22px; margin-right: 6px;}
.paso .t {font-weight: 600; color: #0f172a; font-size: 0.92rem;}
.paso .d {font-size: 0.82rem; color: #52514e; margin-top: 6px; line-height: 1.4;}
.paso .ia {display: inline-block; margin-top: 7px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em;
           color: #1c5cab; background: #dcebfc; border-radius: 999px; padding: 2px 9px;}
.paso .codigo {display: inline-block; margin-top: 7px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em;
               color: #52514e; background: #e9edf2; border-radius: 999px; padding: 2px 9px;}
.idea {border-left: 4px solid #2a78d6; background: #eef5fd; border-radius: 0 12px 12px 0; padding: 14px 18px;
       font-size: 1.02rem; line-height: 1.55; color: #0f172a; margin: 4px 0 18px;}
.idea b {color: #1c5cab;}
.correo {border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; background: #ffffff;}
.correo .cabecera {background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 12px 20px; font-size: 0.86rem; color: #52514e;}
.correo .cabecera b {color: #0f172a;}
.correo .asunto {font-size: 1.12rem; font-weight: 700; color: #0f172a; padding: 16px 20px 0;}
.correo .cuerpo {padding: 8px 20px 18px; font-size: 0.98rem; line-height: 1.6; color: #1f2937;}
.correo .cuerpo p {margin: 10px 0;}
.correo .cuerpo ol {margin: 8px 0 8px 2px; padding-left: 22px;}
.correo .cuerpo strong {color: #0b1f3a; background: #eef5fd; border-radius: 4px; padding: 0 3px;}
.lista {list-style: none; padding: 0; margin: 6px 0 14px;}
.lista li {padding: 5px 0 5px 26px; position: relative; font-size: 0.93rem; color: #1f2937; line-height: 1.4;}
.lista li::before {content: "✓"; position: absolute; left: 0; top: 4px; width: 18px; height: 18px; border-radius: 50%;
                   background: #dcf3dc; color: #0b7a0b; font-size: 0.72rem; font-weight: 700; text-align: center; line-height: 18px;}
.lista li.no::before {content: "✕"; background: #fbe1e1; color: #b02a2a;}
.dato {font-size: 0.93rem; color: #1f2937; padding: 3px 0; line-height: 1.5;}
.dato span {color: #52514e;}
.caja {border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px 18px; background: #ffffff; height: 100%;}
.caja h4 {margin: 0 0 8px; padding: 0; font-size: 0.82rem; letter-spacing: 0.08em; text-transform: uppercase; color: #52514e;}
.caja.antes {background: #fdf3f3; border-color: #f3cfcf;}
.caja.despues {background: #f1faf1; border-color: #c9e8c9;}
.caja.antes li {text-decoration: line-through; color: #8a2f2f; margin-bottom: 6px;}
.caja ol {padding-left: 20px; margin: 6px 0;} .caja p {margin: 6px 0;}
.grupos {display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 6px 0 14px;}
.grupo {border-radius: 14px; padding: 18px 22px; border: 1px solid #e2e8f0;}
.grupo .cifra {font-size: 2.4rem; font-weight: 700; line-height: 1.05;}
.grupo .titulo {font-weight: 600; margin-top: 4px; color: #0f172a;}
.grupo .nota {font-size: 0.86rem; color: #52514e; margin-top: 4px;}
.grupo.t {background: #eef5fd; border-color: #b7d3f6;} .grupo.t .cifra {color: #1c5cab;}
.grupo.c {background: #fdf1ec; border-color: #f5cdbd;} .grupo.c .cifra {color: #b0461c;}
.linea {display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; margin: 4px 0 16px;}
.hito {border-top: 3px solid #2a78d6; padding: 10px 14px 0 0;}
.hito .cuando {font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; color: #1c5cab; font-weight: 700;}
.hito .que {font-size: 0.93rem; color: #1f2937; margin-top: 3px; line-height: 1.45;}
.etiqueta {display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; border-radius: 999px; padding: 2px 10px;}
.etiqueta.ok {background: #dcf3dc; color: #0b7a0b;} .etiqueta.mal {background: #fbe1e1; color: #b02a2a;}
div[data-baseweb="tab-list"] {gap: 6px;}
button[data-baseweb="tab"] {font-size: 1rem; padding: 10px 16px;}
</style>
"""

st.set_page_config(page_title="Cuadra · De registrarse a facturar", layout="wide")
st.markdown(ESTILOS, unsafe_allow_html=True)


def leer_csv(nombre: str) -> pd.DataFrame | None:
    ruta = DIR / nombre
    return pd.read_csv(ruta) if ruta.is_file() else None


def leer_json(nombre: str):
    ruta = DIR / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def miles(numero) -> str:
    return f"{int(numero):,}".replace(",", ".")


def pct(valor: float) -> str:
    return f"{valor:.0%}"


def decimal(texto: str) -> str:
    """Coma decimal, como se escribe en español."""
    return texto.replace(".", ",")


def bloque(contenido: str) -> None:
    st.markdown(contenido, unsafe_allow_html=True)


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


resumen = leer_json("resumen.json")

if resumen is None:
    st.title("Cuadra · De registrarse a facturar")
    st.warning(
        "Todavía no hay resultados que mostrar. Ejecuta `uv run cuadra correr` en la carpeta del "
        "proyecto y vuelve a abrir el panel."
    )
    st.stop()

embudo = leer_csv("embudo.csv")
registrados = miles(embudo.contactos.iloc[0]) if embudo is not None else ""
total_variantes = resumen["variantes_aprobadas"] + resumen["variantes_en_revision"]

# --- Portada: la historia en una frase y las cuatro cifras que la sostienen -----------------------
bloque(
    f"""
<div class="portada">
  <div class="marca">Cuadra · flujo de activación con IA</div>
  <h1>De registrarse a facturar</h1>
  <p>{miles(resumen['elegibles'])} personas se registraron en Cuadra y se quedaron a medio camino de su primera
  factura. Este flujo encuentra en qué paso se atascó cada una, le escribe el correo exacto que necesita y
  deja a la mitad sin correo, a propósito, para poder demostrar si funcionó.</p>
  <div class="pie">Corrida del {resumen['fecha']} · {resumen['modelo']} · modo {resumen['modo']} ·
  {resumen['llamadas_reales']} llamadas reales en esta corrida</div>
</div>
<div class="tarjetas">
  <div class="tarjeta"><div class="cifra">{miles(resumen['elegibles'])}</div>
    <div class="titulo">personas atascadas</div>
    <div class="nota">Llevan {config.DIAS_ATASCADO} días o más sin avanzar. Casi ninguna vuelve sola.</div></div>
  <div class="tarjeta destacada"><div class="cifra">{miles(resumen['correos_en_bandeja'])}</div>
    <div class="titulo">correos listos para enviar</div>
    <div class="nota">Uno por persona del grupo que recibe mensaje.</div></div>
  <div class="tarjeta"><div class="cifra">{resumen['variantes_aprobadas']} de {total_variantes}</div>
    <div class="titulo">correos modelo aprobados</div>
    <div class="nota">Redactados por Claude y verificados. En revisión humana: {resumen['variantes_en_revision']}.</div></div>
  <div class="tarjeta"><div class="cifra">{miles(resumen['control'])}</div>
    <div class="titulo">personas de comparación</div>
    <div class="nota">No reciben correo. Son la vara para medir el efecto.</div></div>
</div>
<div class="pasos">
  <div class="paso"><span class="n">1</span><span class="t">Lee los datos</span>
    <div class="d">{registrados} registrados: CRM, producto y pagos.</div><span class="codigo">CÓDIGO</span></div>
  <div class="paso"><span class="n">2</span><span class="t">Encuentra a los atascados</span>
    <div class="d">En qué paso se quedó cada uno y hace cuánto.</div><span class="codigo">CÓDIGO</span></div>
  <div class="paso"><span class="n">3</span><span class="t">Pone la ayuda al día</span>
    <div class="d">Claude cruza los artículos de ayuda con los cambios de la semana.</div><span class="ia">IA</span></div>
  <div class="paso"><span class="n">4</span><span class="t">Redacta y verifica</span>
    <div class="d">Un correo por paso, oficio y antigüedad. Reglas fijas y un juez.</div><span class="ia">IA</span></div>
  <div class="paso"><span class="n">5</span><span class="t">Reparte y mide</span>
    <div class="d">Mitad recibe correo, mitad no. A los {config.VENTANA_DIAS} días se compara.</div><span class="codigo">CÓDIGO</span></div>
</div>
"""
)

tab_diagnostico, tab_base, tab_mensajes, tab_experimento, tab_limites = st.tabs(
    ["1 · El problema", "2 · La ayuda al día", "3 · Los correos", "4 · ¿Funcionó?", "5 · Límites"]
)

# --- 1 · El problema ------------------------------------------------------------------------------
with tab_diagnostico:
    cruce = leer_csv("embudo_por_canal_segmento.csv")
    tiempos = leer_csv("tiempos_entre_pasos.csv")
    if cruce is not None:
        peor = cruce.loc[cruce.pct_config_a_cliente.idxmin()]
        resto = cruce.drop(peor.name).pct_config_a_cliente
        bloque(
            f"""<div class="idea">La gente no se pierde por igual. De <b>{miles(peor.n)}
            {NOMBRE_SEGMENTO.get(peor.segmento, peor.segmento)} que llegaron por el canal
            {NOMBRE_CANAL.get(peor.canal, peor.canal).lower()}</b>, solo el <b>{pct(peor.pct_config_a_cliente)}</b> crea su primer
            cliente después de configurar su empresa. En todos los demás grupos lo hace entre el {pct(resto.min())}
            y el {pct(resto.max())}. Ahí está la fuga.</div>"""
        )

    izquierda, derecha = st.columns(2)
    if embudo is not None:
        with izquierda:
            st.markdown(f"**De {registrados} registrados, cuántos llegan a cada paso**")
            embudo["Paso"] = embudo.paso.map(NOMBRE_PASO)
            embudo["etiqueta"] = [f"{miles(c)}  ·  {p:.0%}" for c, p in zip(embudo.contactos, embudo.pct_registro)]
            base = alt.Chart(embudo).encode(
                y=alt.Y("Paso:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=13)),
                x=alt.X("contactos:Q", title=None, scale=alt.Scale(domain=[0, 1900]), axis=None),
                tooltip=[alt.Tooltip("Paso:N"), alt.Tooltip("contactos:Q", title="Personas"),
                         alt.Tooltip("pct_registro:Q", title="Del registro", format=".0%")],
            )
            st.altair_chart(
                (
                    base.mark_bar(color=AZUL, cornerRadiusEnd=4, size=22)
                    + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
                ).properties(height=alt.Step(40)).configure_view(strokeWidth=0),
                use_container_width=True,
            )
    if cruce is not None:
        with derecha:
            st.markdown("**De quienes configuran su empresa, qué parte crea un cliente**")
            cruce["Grupo"] = [
                f"{NOMBRE_CANAL.get(c, c)} · {NOMBRE_SEGMENTO.get(s, s)}" for c, s in zip(cruce.canal, cruce.segmento)
            ]
            cruce = cruce.sort_values("pct_config_a_cliente")
            cruce["Destacado"] = ["La fuga"] + ["Resto de grupos"] * (len(cruce) - 1)
            cruce["etiqueta"] = [f"{p:.0%}  ·  {miles(n)} personas" for p, n in zip(cruce.pct_config_a_cliente, cruce.n)]
            base = alt.Chart(cruce).encode(
                y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=13)),
                x=alt.X("pct_config_a_cliente:Q", title=None, scale=alt.Scale(domain=[0, 1.3]), axis=None),
                tooltip=[alt.Tooltip("Grupo:N"), alt.Tooltip("n:Q", title="Registrados"),
                         alt.Tooltip("pct_config_a_cliente:Q", title="Configura → cliente", format=".0%"),
                         alt.Tooltip("pct_emitio_primera_factura:Q", title="Llega a facturar", format=".0%")],
            )
            barras = base.mark_bar(cornerRadiusEnd=4, size=22).encode(
                color=alt.Color(
                    "Destacado:N", title=None,
                    scale=alt.Scale(domain=["La fuga", "Resto de grupos"], range=[AZUL, GRIS]),
                    legend=alt.Legend(orient="bottom"),
                )
            )
            st.altair_chart(
                (
                    barras + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
                ).properties(height=alt.Step(40)).configure_view(strokeWidth=0),
                use_container_width=True,
            )

    if tiempos is not None:
        techo = int(tiempos.maximo.iloc[:3].sum())
        base_natural = resumen.get("tasa_base_estimada")
        natural = ""
        if base_natural is not None:
            natural = (
                f"De quienes llevan {config.DIAS_ATASCADO} días o más quietos, solo el "
                f"<b>{decimal(f'{base_natural:.2%}')}</b> factura por su cuenta en las dos semanas siguientes."
            )
        bloque(
            f"""<div class="idea">Quien avanza, avanza rápido: <b>nadie emitió su primera factura más de {techo}
            días después de registrarse</b>. {natural} Por eso el flujo escribe a partir del tercer día quieto, y
            no antes.</div>"""
        )
        with st.expander("Ver los días que pasan entre un paso y el siguiente"):
            tabla = tiempos.assign(desde=tiempos.desde.map(NOMBRE_PASO), hasta=tiempos.hasta.map(NOMBRE_PASO))
            tabla.columns = ["Desde", "Hasta", "Personas", "Mediana (días)", "Percentil 90", "Máximo"]
            st.dataframe(tabla, hide_index=True, use_container_width=True)
    if cruce is not None:
        with st.expander("Ver la tabla completa por canal y segmento"):
            tabla = cruce[["canal", "segmento", "n", "pct_configuro_empresa", "pct_creo_cliente",
                           "pct_emitio_primera_factura", "pct_pago", "pct_config_a_cliente"]].copy()
            for columna in tabla.columns[3:]:
                tabla[columna] = tabla[columna].map(pct)
            tabla.columns = ["Canal", "Segmento", "Registrados", "Configura", "Crea cliente", "Factura", "Paga",
                             "Configura → cliente"]
            st.dataframe(tabla, hide_index=True, use_container_width=True)

# --- 2 · La ayuda al día --------------------------------------------------------------------------
base_json = leer_json("base_vigente.json")
base_vigente = BaseVigente.model_validate(base_json) if base_json else None

with tab_base:
    if base_vigente is None:
        st.info("Esta corrida no pudo construir la base vigente (sin caché y sin clave).")
    else:
        viejos = [a for a in base_vigente.articulos if not a.vigente]
        plural = "s" if len(viejos) != 1 else ""
        bloque(
            f"""<div class="idea">Los correos solo pueden repetir instrucciones que hoy son ciertas. Claude comparó
            los {len(base_vigente.articulos)} artículos del Centro de Ayuda con las notas de cambios de esta semana
            y encontró <b>{len(viejos)} desactualizado{plural}</b>. Un correo que usara la versión vieja mandaría a
            la gente a un botón que ya no está ahí.</div>"""
        )
        for articulo in viejos:
            st.markdown(f"#### {articulo.titulo}")
            bloque(
                '<span class="etiqueta mal">DESACTUALIZADO</span> &nbsp; Lo cambia: '
                f"{html.escape(', '.join(articulo.notas_que_lo_cambian))}"
            )
            antes, despues = st.columns(2)
            with antes:
                frases = "".join(f"<li>{html.escape(f.replace('**', ''))}</li>" for f in articulo.frases_obsoletas)
                bloque(f'<div class="caja antes"><h4>Antes · ya no es cierto</h4><ul>{frases}</ul></div>')
            with despues:
                bloque(
                    '<div class="caja despues"><h4>Ahora · lo que usan los correos</h4>'
                    f"{cuerpo_html(pasos_del_articulo(articulo.texto_vigente))}</div>"
                )
            with st.expander("Ver el artículo corregido completo"):
                st.markdown(articulo.texto_vigente)

        st.markdown("#### Artículos que siguen vigentes")
        for articulo in base_vigente.articulos:
            if articulo.vigente:
                with st.expander(f"{articulo.titulo}  ·  vigente"):
                    st.markdown(articulo.texto_vigente)

        st.markdown("#### Lo que los correos no pueden mencionar")
        for funcion in base_vigente.funciones_restringidas:
            st.markdown(
                f"- **{funcion.nombre}**: solo está en el plan {funcion.plan}, y estas personas no tienen plan de pago."
            )
        with st.expander("Ver las rutas de menú válidas y las obsoletas"):
            columnas = st.columns(2)
            columnas[0].markdown("**Válidas hoy**\n\n" + "\n".join(f"- {r}" for r in base_vigente.rutas_validas))
            columnas[1].markdown("**Obsoletas**\n\n" + "\n".join(f"- ~~{r}~~" for r in base_vigente.rutas_obsoletas))

# --- 3 · Los correos ------------------------------------------------------------------------------
bandeja = leer_csv("bandeja_salida.csv")
variantes = {Variante(**v["variante"]).clave: v for v in (leer_json("variantes.json") or [])}

with tab_mensajes:
    if bandeja is None or bandeja.empty:
        st.info("La bandeja de salida está vacía en esta corrida. Revisa la cola de revisión más abajo.")
    else:
        bloque(
            f"""<div class="idea">Estos son los <b>{miles(len(bandeja))} correos listos para enviar</b>. Cada persona
            recibe el que corresponde al paso en que se quedó, con un ejemplo de su oficio y las instrucciones
            exactas de la ayuda vigente. Elige a alguien para ver el suyo.</div>"""
        )
        bandeja["actividad"] = bandeja.variante.str.split("|").str[1]
        filtros = st.columns(3)
        paso = filtros[0].selectbox(
            "Paso", ["Todos"] + sorted(bandeja.paso.unique()), format_func=lambda p: NOMBRE_ATASCO.get(p, p)
        )
        actividad = filtros[1].selectbox("Oficio", ["Todos"] + sorted(bandeja.actividad.unique()))
        tramo = filtros[2].selectbox(
            "Antigüedad", ["Todos"] + sorted(bandeja.tramo.unique()), format_func=lambda t: NOMBRE_TRAMO.get(t, t)
        )
        vista = bandeja
        if paso != "Todos":
            vista = vista[vista.paso == paso]
        if actividad != "Todos":
            vista = vista[vista.actividad == actividad]
        if tramo != "Todos":
            vista = vista[vista.tramo == tramo]

        if vista.empty:
            st.info("Nadie del grupo que recibe correo cumple estos filtros.")
        else:
            opciones = {
                f"{f.nombre} · {f.actividad} · {NOMBRE_ATASCO[f.paso]} · {f.dias_quieto} días sin avanzar ({f.id_contacto})": i
                for i, f in vista.iterrows()
            }
            st.caption(f"{miles(len(vista))} correos con estos filtros, de {miles(len(bandeja))} en la bandeja.")
            # Por defecto se muestra a alguien que no creó su primer cliente: es el caso que explica la fuga.
            pasos_en_vista = list(vista.paso)
            inicial = pasos_en_vista.index("sin_cliente") if "sin_cliente" in pasos_en_vista else 0
            fila = bandeja.loc[opciones[st.selectbox("Persona", list(opciones), index=inicial)]]
            izquierda, derecha = st.columns([3, 2], gap="large")
            with izquierda:
                bloque(correo_html(fila.email, fila.asunto, fila.cuerpo))
            with derecha:
                bloque(
                    f"""<div class="caja"><h4>Por qué recibe este correo</h4>
                    <div class="dato"><span>Se quedó:</span> {NOMBRE_ATASCO[fila.paso].lower()}</div>
                    <div class="dato"><span>Lleva:</span> {fila.dias_quieto} días sin dar un paso</div>
                    <div class="dato"><span>Oficio:</span> {html.escape(fila.actividad)}</div>
                    <div class="dato"><span>Grupo:</span> recibe correo (tratamiento)</div></div>"""
                )
                procesada = variantes.get(fila.variante)
                if procesada:
                    veredicto = procesada.get("veredicto") or {}
                    reglas = "".join(f"<li>{regla}</li>" for regla in REGLAS)
                    juez = "".join(
                        f'<li class="{"" if veredicto.get(campo) else "no"}">{criterio}</li>'
                        for campo, criterio in CRITERIOS_JUEZ.items()
                    )
                    intentos = (
                        "al primer intento" if procesada["intentos"] == 1 else "al segundo intento, tras una corrección"
                    )
                    bloque(
                        f"""<div style="height:12px"></div><div class="caja"><h4>Controles que pasó</h4>
                        <div class="dato"><span>Reglas fijas (código)</span></div><ul class="lista">{reglas}</ul>
                        <div class="dato"><span>Juez (Claude)</span></div><ul class="lista">{juez}</ul>
                        <div class="dato"><span>Aprobado</span> {intentos}</div></div>"""
                    )

            if hay_clave() and base_vigente is not None:
                st.divider()
                st.markdown("**Redactar este correo en vivo**")
                st.caption(
                    "Llama a Claude ahora, sin usar las respuestas guardadas, y pasa el resultado por los mismos "
                    "controles. No modifica la bandeja ni el caché del repositorio."
                )
                if st.button("Redactar en vivo"):
                    variante = Variante(**variantes[fila.variante]["variante"])
                    contactos = pd.read_csv(config.DIR_DATOS / "crm_contactos.csv")
                    segmento = contactos[contactos.actividad == variante.actividad].segmento.iloc[0]
                    with st.spinner("Claude está redactando y el juez está revisando…"):
                        modelo = Modelo(dir_cache=Path(tempfile.mkdtemp()), modo="vivo")
                        nueva = procesar(variante, base_vigente, modelo, segmento)
                    st.markdown(f"Resultado: **{nueva.estado}** en {nueva.intentos} intento(s), "
                                f"{modelo.llamadas_reales} llamadas reales.")
                    for motivo in nueva.motivos:
                        st.markdown(f"- {motivo}")
                    if nueva.correo:
                        asunto, cuerpo = personalizar(nueva.correo, fila.nombre)
                        bloque(correo_html(fila.email, asunto, cuerpo))

    st.markdown("#### Cola de revisión humana")
    cola = leer_csv("cola_revision.csv")
    if cola is None or cola.empty:
        bloque(
            '<span class="etiqueta ok">VACÍA</span> &nbsp; Ningún correo modelo falló los controles dos veces. '
            "Si alguno fallara, sus destinatarios no recibirían nada hasta que una persona lo revisara."
        )
    else:
        st.markdown(
            f"{len(cola)} correos modelo no pasaron los controles. Sus {int(cola.personas_sin_correo.sum())} "
            "destinatarios no reciben correo hasta que una persona los revise."
        )
        st.dataframe(cola, hide_index=True, use_container_width=True)

# --- 4 · ¿Funcionó? -------------------------------------------------------------------------------
with tab_experimento:
    bloque(
        f"""<div class="idea">Para saber si los correos sirven hace falta alguien con quien comparar. Por eso el
        flujo reparte a las personas al azar en dos grupos: <b>una mitad recibe el correo y la otra no</b>. Si a los
        {config.VENTANA_DIAS} días facturó más gente en el primer grupo, la diferencia es obra del correo.</div>
        <div class="grupos">
          <div class="grupo t"><div class="cifra">{miles(resumen['tratamiento'])}</div>
            <div class="titulo">reciben el correo</div><div class="nota">Grupo de tratamiento</div></div>
          <div class="grupo c"><div class="cifra">{miles(resumen['control'])}</div>
            <div class="titulo">no reciben nada</div><div class="nota">Grupo de control: la vara de medir</div></div>
        </div>
        <div class="linea">
          <div class="hito"><div class="cuando">Hoy</div><div class="que">Se reparten los grupos y sale la bandeja.</div></div>
          <div class="hito"><div class="cuando">Día {config.VENTANA_DIAS}</div><div class="que">Se cuenta quién emitió su
            primera factura en cada grupo. Cuentan todos, abran el correo o no.</div></div>
          <div class="hito"><div class="cuando">Decisión</div><div class="que">Si la mejora es clara, se extiende a
            todos. Si no, se reescribe el mensaje. La regla está fijada desde ya.</div></div>
        </div>"""
    )

    simulado = leer_json("SIMULADO_resultado_experimento.json")
    st.markdown("#### Así se leería el resultado")
    if simulado is None:
        st.markdown(
            "Todavía no hay medición. Para ver el cálculo con datos inventados:\n\n"
            "`uv run cuadra simular --efecto 0.08` y luego "
            "`uv run cuadra medir --eventos salida/SIMULADO_eventos_posteriores.csv`"
        )
    else:
        st.warning(
            "SIMULADO. No existen datos posteriores al 31 de octubre, así que estos eventos son inventados "
            "con un efecto fijado a mano. Demuestran que la medición corre; no son un resultado del flujo."
        )
        izquierda, derecha = st.columns([3, 2], gap="large")
        with izquierda:
            tasa_t, tasa_c = simulado["tasa_t"], simulado["tasa_c"]
            barras = pd.DataFrame(
                {
                    "Grupo": ["Recibe correo", "No recibe"],
                    "tasa": [tasa_t, tasa_c],
                    "etiqueta": [
                        decimal(f"{tasa_t:.1%}") + f"  ·  {simulado['conv_t']} de {simulado['n_t']}",
                        decimal(f"{tasa_c:.1%}") + f"  ·  {simulado['conv_c']} de {simulado['n_c']}",
                    ],
                }
            )
            base = alt.Chart(barras).encode(
                y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelFontSize=13)),
                x=alt.X("tasa:Q", title=None, axis=None, scale=alt.Scale(domain=[0, (max(tasa_t, tasa_c) or 1) * 1.6])),
                tooltip=["Grupo:N", alt.Tooltip("tasa:Q", title="Emitió su primera factura", format=".1%")],
            )
            st.markdown("**Emitieron su primera factura en 14 días (simulado)**")
            st.altair_chart(
                (
                    base.mark_bar(cornerRadiusEnd=4, size=26).encode(
                        color=alt.Color("Grupo:N", legend=None, sort=None,
                                        scale=alt.Scale(domain=["Recibe correo", "No recibe"], range=[AZUL, NARANJA]))
                    )
                    + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
                ).properties(height=alt.Step(46)).configure_view(strokeWidth=0),
                use_container_width=True,
            )
        with derecha:
            ic = simulado["ic95"]
            diferencia = decimal(f"{simulado['diferencia'] * 100:+.1f}")
            margen = f"de {decimal(f'{ic[0] * 100:+.1f}')} a {decimal(f'{ic[1] * 100:+.1f}')} puntos"
            bloque(
                f"""<div class="caja"><h4>Lectura (simulada)</h4>
                <div class="dato"><span>Diferencia:</span> <b>{diferencia} puntos</b></div>
                <div class="dato"><span>Margen de error (95%):</span> {margen}</div>
                <div class="dato"><span>Regla:</span> si todo el margen queda sobre cero, se extiende</div>
                <div class="dato"><span>Decisión:</span> <b>{simulado['decision']}</b></div></div>"""
            )
        por_estrato = leer_csv("SIMULADO_resultado_por_estrato.csv")
        if por_estrato is not None:
            with st.expander("Ver el resultado simulado por paso y antigüedad"):
                tabla = por_estrato[["dimension", "valor", "n_t", "conv_t", "n_c", "conv_c", "diferencia", "valor_p"]].copy()
                tabla["diferencia"] = tabla.diferencia.map(lambda d: decimal(f"{d * 100:+.1f} puntos"))
                tabla["valor_p"] = tabla.valor_p.map(lambda p: decimal(f"{p:.3f}"))
                tabla.columns = ["Dimensión", "Valor", "Reciben", "Facturaron", "No reciben", "Facturaron ", "Diferencia", "p"]
                st.dataframe(tabla, hide_index=True, use_container_width=True)

    st.markdown("#### ¿Se puede confiar en la comparación?")
    base_natural, minimo = resumen.get("tasa_base_estimada"), resumen.get("efecto_minimo_detectable")
    aa = leer_json("prueba_aa.json")
    columnas = st.columns(3)
    with columnas[0]:
        natural = "sin historia" if base_natural is None else decimal(f"{base_natural:.2%}")
        bloque(
            f"""<div class="caja"><h4>Sin correo, casi nadie factura</h4><div class="dato"><b>{natural}</b> de los
            atascados factura solo en 14 días ({resumen.get('base_convertidos', 0)} de
            {miles(resumen.get('base_observaciones', 0))} observaciones en {resumen.get('base_cortes', 0)} fechas
            pasadas).</div></div>"""
        )
    with columnas[1]:
        detectable = "no calculable" if minimo is None else decimal(f"{minimo * 100:.1f} puntos")
        bloque(
            f"""<div class="caja"><h4>Qué mejora se notaría</h4><div class="dato">Con estos grupos, una mejora de
            <b>{detectable}</b> o más se distingue del azar 8 de cada 10 veces. Una menor, probablemente no.</div></div>"""
        )
    with columnas[2]:
        if aa:
            tasas = f"{decimal(f'{aa['tasa_t']:.1%}')} contra {decimal(f'{aa['tasa_c']:.1%}')}"
            valor_p = decimal(f"{aa['valor_p']:.2f}")
            bloque(
                f"""<div class="caja"><h4>Prueba A/A del reparto</h4><div class="dato">El mismo reparto sobre julio y
                agosto, cuando nadie recibió nada: {tasas} (p = {valor_p}).</div></div>"""
            )
    if aa:
        bloque('<div style="height:10px"></div>')
        if aa["valor_p"] > config.UMBRAL_AA:
            st.caption(
                "Sin intervención no debería haber diferencia entre los grupos, y la que se ve es la esperable por "
                "azar. Esta prueba ya sirvió una vez: la primera semilla del reparto daba aquí 8,8 puntos de "
                "diferencia (p = 0,01) porque, por azar, dejaba menos autónomos de canal orgánico en un grupo. Se "
                f"cambió con una regla fija, la primera candidata con p > {decimal(str(config.UMBRAL_AA))}, "
                "cubierta por una prueba automática. Límite: compara a todos los registrados de esos meses, no solo "
                "a los atascados."
            )
        else:
            st.warning(
                "La prueba A/A muestra una diferencia que no debería existir entre dos grupos que no recibieron "
                "nada. Antes de enviar, hay que cambiar la semilla del reparto con la regla de `cuadra/config.py`."
            )

    equilibrio = leer_csv("equilibrio.csv")
    if equilibrio is not None:
        with st.expander("Ver si los dos grupos se parecen (debe haber cerca del 50% de cada tipo en cada uno)"):
            tabla = equilibrio.assign(
                dimension=equilibrio.dimension.str.capitalize(),
                pct_tratamiento=equilibrio.pct_tratamiento.map(pct),
            )
            tabla.columns = ["Dimensión", "Valor", "Reciben correo", "No reciben", "% que recibe"]
            st.dataframe(tabla, hide_index=True, use_container_width=True)

# --- 5 · Límites ----------------------------------------------------------------------------------
with tab_limites:
    bloque('<div class="idea">Lo que este flujo <b>no</b> hace, dicho sin rodeos.</div>')
    limites = [
        ("No envía correos", "Las direcciones del caso son ficticias. La salida es una bandeja lista para cargar en "
                             "una herramienta de envío; tampoco mide aperturas ni clics."),
        ("No explica el porqué", "Los datos dicen dónde se atascan los autónomos de canal orgánico, no por qué. "
                                 "Hipótesis a investigar: no saben qué datos fiscales pedirle a su cliente."),
        ("El efecto real es desconocido", "El resultado de la pestaña 4 es simulado. La respuesta de verdad llega "
                                          "14 días después del primer envío."),
        ("Los datos son sintéticos", "Que casi nadie avance solo pasado el tercer día puede ser un artefacto del caso."),
        ("Sin consentimiento ni baja", "En producción, el permiso y el enlace de baja son obligatorios antes de "
                                       "escribir a nadie."),
        ("Un canal, un mensaje", "Sin recordatorios ni avisos dentro del producto."),
        ("Ocho pagadores sin factura", "Pagaron sin haber facturado nunca. Quedan fuera del flujo y listados aparte "
                                       "para que alguien los mire."),
    ]
    columnas = st.columns(2)
    for indice, (titulo, texto) in enumerate(limites):
        with columnas[indice % 2]:
            bloque(f'<div class="caja" style="margin-bottom:14px"><h4>{titulo}</h4><div class="dato">{texto}</div></div>')
