"""Ver la automatización: corre el flujo completo desde un botón y lo cuenta paso a paso, sin saber de código.

Corre en una carpeta temporal y en modo repetición (respuestas de Claude guardadas en cache/): no gasta nada
y no toca salida/, que es lo que muestran las demás páginas.
"""

import html
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from comun import (  # noqa: E402
    AZUL, NARANJA, NOMBRE_ATASCO, TINTA, bloque, correo_html, cuerpo_html, decimal, estilos, leer_json, miles,
    pasos_del_articulo, pct,
)
from cuadra import config, flujo  # noqa: E402
from cuadra.conocimiento import BaseVigente  # noqa: E402
from cuadra.redaccion import Correo  # noqa: E402
from cuadra.verificacion import verificar_reglas  # noqa: E402
from cuadra.medicion import medir  # noqa: E402
from cuadra.simulador import simular_eventos  # noqa: E402

PAUSA = float(os.environ.get("CUADRA_PAUSA_DEMO", "0.9"))  # segundos entre pasos: el flujo real tarda menos de un segundo, y así se puede seguir con la vista

# Lo que avisa el flujo (cuadra/flujo.py) y cómo se cuenta a alguien que no programa.
PASOS = [
    ("1/8", "Lee los datos", "Abre lo que se exportó hoy del CRM, del producto y de los pagos.", "codigo"),
    ("2/8", "Mira dónde se pierde la gente", "Cuenta cuántas personas llegan a cada paso hasta facturar.", "codigo"),
    ("3/8", "Encuentra a los atascados", f"Busca a quien lleva {config.DIAS_ATASCADO} días o más sin avanzar.", "codigo"),
    ("4/8", "Sortea los dos grupos", "Al azar: la mitad recibirá correo y la otra mitad servirá de comparación.", "codigo"),
    ("5/8", "Revisa el Centro de Ayuda", "Compara los artículos de ayuda con los cambios recientes del producto.", "ia"),
    ("6/8", "Escribe y revisa las plantillas", "Una plantilla de correo por paso pendiente, oficio y antigüedad. Otra IA la revisa.", "ia"),
    ("8/8", "Deja la bandeja lista", "Asigna a cada persona del grupo con correo el suyo, con su nombre.", "codigo"),
]
QUIEN = {"ia": '<span class="quien ia">LO HACE LA IA</span>', "codigo": '<span class="quien codigo">LO HACE EL PROGRAMA</span>'}
EFECTOS = {"No ayuda nada": 0.0, "Ayuda un poco": 0.03, "Ayuda mucho": 0.08}

# Correos con trampa para probar el candado. Se pasan por las reglas reales (cuadra/verificacion.py), sin IA.
_FIRMA = "\n\nUn saludo,\nEl equipo de Cuadra"
TRAMPAS = {
    "Usa la instrucción vieja del artículo 04": (
        "Hola, {nombre}:\n\nYa tienes tu primera factura. Para mandársela a tu cliente:\n\n"
        "1. Entra en **Ventas > Facturas** y abre la factura.\n2. Pulsa **Más acciones > Enviar por correo**." + _FIRMA
    ),
    "Ofrece una función que solo tiene el plan Pro": (
        "Hola, {nombre}:\n\nSi cobras siempre lo mismo, crea una factura recurrente y Cuadra la emitirá sola cada "
        "mes.\n\n1. Entra en **Ventas > Facturas** y elige la opción de factura recurrente." + _FIRMA
    ),
    "Inventa un botón que no existe": (
        "Hola, {nombre}:\n\nCrear tu primer cliente lleva un minuto.\n\n1. Entra en **Contactos > Nuevo cliente**."
        "\n2. Escribe su nombre y su NIF." + _FIRMA
    ),
    "Correo correcto, con la ayuda al día": (
        "Hola, {nombre}:\n\nTu primera factura está a un paso.\n\n1. Entra en **Ventas > Facturas**.\n"
        "2. Pulsa **Nueva factura** y rellena los datos de tu cliente." + _FIRMA
    ),
}
REGLA = {"R3": "Regla 3 · el botón no existe en la ayuda actual", "R4": "Regla 4 · instrucción vieja",
         "R5": "Regla 5 · función que la persona no tiene"}

estilos()
bloque(
    """<style>
.tiempo {border-left: 3px solid #e2e8f0; margin: 0 0 0 12px; padding: 0 0 0 22px;}
.etapa {position: relative; padding: 4px 0 16px;}
.etapa::before {content: ""; position: absolute; left: -32px; top: 6px; width: 16px; height: 16px; border-radius: 50%;
                background: #2a78d6; border: 3px solid #fff; box-shadow: 0 0 0 2px #2a78d6;}
.etapa.espera::before {background: #fff; box-shadow: 0 0 0 2px #cbd5e1;}
.etapa.espera .t, .etapa.espera .d {color: #94a3b8;}
.etapa .t {font-weight: 700; color: #0f172a; font-size: 1.02rem;}
.etapa .d {font-size: 0.92rem; color: #475569; margin-top: 2px;}
.etapa .r {font-size: 0.97rem; color: #0b3d7a; background: #eef5fd; border-radius: 8px; padding: 6px 10px;
           margin-top: 6px; display: inline-block;}
.etapa .quien {margin: 0 0 0 8px; vertical-align: middle;}
</style>"""
)

st.title("Ver la automatización")
st.markdown(
    "Pulsa el botón y mira el flujo trabajar de principio a fin, paso a paso. Usa las respuestas de la IA ya "
    "guardadas, así que **no cuesta nada** y siempre da el mismo resultado. No cambia lo que muestran las demás páginas."
)


def resultado_de(clave: str, carpeta: Path, resumen: dict) -> str:
    """La frase con el resultado real de cada paso, leída de lo que acaba de escribir el flujo."""
    if clave == "1/8":
        contactos = pd.read_csv(config.DIR_DATOS / "crm_contactos.csv")
        eventos = pd.read_csv(config.DIR_DATOS / "eventos_producto.csv")
        pagos = pd.read_csv(config.DIR_DATOS / "pagos.csv")
        return (f"{miles(len(contactos))} personas registradas, {miles(len(eventos))} acciones dentro del producto y "
                f"{miles(len(pagos))} pagos.")
    if clave == "2/8":
        embudo = pd.read_csv(carpeta / "embudo.csv").set_index("paso")
        return (f"Solo {round(embudo.pct_registro['emitio_primera_factura'] * 100)} de cada 100 llegan a emitir "
                "su primera factura.")
    if clave == "3/8":
        return f"{miles(resumen['elegibles'])} personas atascadas a las que vale la pena escribir."
    if clave == "4/8":
        return f"{miles(resumen['tratamiento'])} recibirán correo y {miles(resumen['control'])} no recibirán nada."
    if clave == "5/8":
        ruta = carpeta / "base_vigente.json"
        if not ruta.is_file():
            return "No se pudo revisar la ayuda: faltan las respuestas guardadas."
        articulos = json.loads(ruta.read_text(encoding="utf-8"))["articulos"]
        viejos = sum(1 for a in articulos if not a["vigente"])
        return (f"{len(articulos)} artículos revisados; {viejos} tenía{'n' if viejos != 1 else ''} instrucciones que ya "
                "no son ciertas y se corrigi" + ("eron." if viejos != 1 else "ó."))
    if clave == "6/8":
        total = resumen["variantes_aprobadas"] + resumen["variantes_en_revision"]
        revision = resumen["variantes_en_revision"]
        extra = "ninguna tuvo que pasar a revisión humana." if revision == 0 else f"{revision} esperan revisión humana."
        return f"{total} plantillas escritas; {resumen['variantes_aprobadas']} aprobadas y {extra}"
    return (f"{miles(resumen['correos_en_bandeja'])} correos listos para enviar, uno por persona: cada uno sale de "
                "su plantilla, con su nombre.")


def linea_de_tiempo(hechos: dict[str, str], actual: str | None = None) -> str:
    etapas = ""
    for clave, titulo, descripcion, quien in PASOS:
        hecho = clave in hechos
        clase = "etapa" if hecho or clave == actual else "etapa espera"
        resultado = f'<div class="r">{html.escape(hechos[clave])}</div>' if hecho else ""
        if clave == actual and not hecho:
            resultado = '<div class="r">Trabajando…</div>'
        etapas += (f'<div class="{clase}"><span class="t">{titulo}</span>{QUIEN[quien]}'
                   f'<div class="d">{descripcion}</div>{resultado}</div>')
    return f'<div class="tiempo">{etapas}</div>'


def seccion_ayuda() -> None:
    """El paso 5 por dentro: el hallazgo del artículo 04 y cómo se evita que un correo mande a un botón viejo."""
    datos = leer_json("base_vigente.json")
    if datos is None:
        return
    base = BaseVigente(**datos)
    viejos = [a for a in base.articulos if not a.vigente]
    st.divider()
    st.markdown("#### El paso 5 por dentro: que ningún correo mande a alguien a un botón que ya no existe")
    st.markdown(
        f"Los correos copian las instrucciones de los **{len(base.articulos)} artículos de ayuda** de Cuadra. Pero "
        "el producto cambia cada semana y el equipo lo avisa en **notas de cambios**, sin actualizar siempre la "
        "ayuda. Si un correo copia una instrucción vieja, la persona busca un botón que ya se movió, se frustra y "
        "abandona: justo lo contrario de lo que se busca."
    )
    for articulo in viejos:
        original = (config.DIR_AYUDAS / articulo.archivo).read_text(encoding="utf-8")
        notas = ", ".join(n.split("-")[1] for n in articulo.notas_que_lo_cambian)
        st.markdown(
            f"**Lo que encontró la IA:** el artículo «{articulo.titulo}» quedó viejo por la nota de cambios {notas}, "
            f"de esta semana. Tenía **{len(articulo.frases_obsoletas)} frases** que ya no son ciertas."
        )
        antes, despues = st.columns(2, gap="medium")
        with antes:
            bloque(f'<div class="caja antes"><h4>Antes: lo que decía la ayuda</h4>'
                   f'<div class="dato">{cuerpo_html(pasos_del_articulo(original))}</div></div>')
        with despues:
            bloque(f'<div class="caja despues"><h4>Después: corregido por la IA según la nota</h4>'
                   f'<div class="dato">{cuerpo_html(pasos_del_articulo(articulo.texto_vigente))}</div></div>')
        with st.expander(f"Las {len(articulo.frases_obsoletas)} frases que la IA marcó como viejas, copiadas tal cual"):
            for frase in articulo.frases_obsoletas:
                st.markdown(f"- ~~{frase.replace('**', '')}~~")
    restringidas = ", ".join(f"«{f.nombre}» (solo plan {f.plan})" for f in base.funciones_restringidas)
    vigentes = len(base.articulos) - len(viejos)
    st.markdown(
        f"Los otros {vigentes} artículos siguen siendo ciertos. De las notas también sacó las funciones que no todos "
        f"tienen: {restringidas or 'ninguna'}."
    )

    st.markdown("**Cómo evita equivocarse en este paso**")
    obsoletas = ", ".join(f"«{r}»" for r in base.rutas_obsoletas) or "ninguno"
    bloque(
        f"""<div class="pasos">
<div class="paso"><span class="n">1</span><span class="t">Lee y cita</span>
  <div class="d">La IA lee cada artículo junto a las notas. Si algo cambió, tiene que <b>copiar tal cual</b> la frase
  vieja y reescribir solo esa frase. No puede inventar lo que la nota no dice.</div>
  <span class="quien ia">LO HACE LA IA</span></div>
<div class="paso"><span class="n">2</span><span class="t">Lo que está bien no se toca</span>
  <div class="d">Si la IA dice que un artículo sigue vigente, el programa guarda el original <b>letra por letra</b>.
  La IA no puede cambiarlo por descuido.</div>
  <span class="quien codigo">LO HACE EL PROGRAMA</span></div>
<div class="paso"><span class="n">3</span><span class="t">Lista de botones</span>
  <div class="d">El programa compara antes y después y saca qué botones existen y cuáles desaparecieron:
  {html.escape(obsoletas)}.</div>
  <span class="quien codigo">LO HACE EL PROGRAMA</span></div>
<div class="paso"><span class="n">4</span><span class="t">El candado</span>
  <div class="d">Quien escribe los correos solo recibe la ayuda corregida. Y si un correo nombra un botón que no
  existe, usa una frase vieja u ofrece algo del plan Pro, <b>se rechaza</b>.</div>
  <span class="quien codigo">LO HACE EL PROGRAMA</span></div>
</div>"""
    )

    st.markdown("**Pruébalo tú:** elige un correo con trampa y pásalo por el candado. Son las mismas reglas que "
                "revisaron los correos de verdad.")
    eleccion = st.radio("Correo de prueba", list(TRAMPAS), horizontal=True, label_visibility="collapsed", key="trampa")
    cuerpo = TRAMPAS[eleccion]
    correo = Correo(asunto="Tu factura en Cuadra", cuerpo=cuerpo, paso_siguiente="-", ruta_menu="Ventas > Facturas",
                    articulo_fuente="-")
    motivos = verificar_reglas(correo, base)
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        bloque(correo_html("persona@correo.example", correo.asunto, cuerpo.replace("{nombre}", "Lucía")))
    with derecha:
        if motivos:
            lineas = "".join(
                f'<div class="dato"><b>{REGLA.get(m.split(":")[0], m.split(":")[0])}</b><br>'
                f'{html.escape(m.split(":", 1)[1].strip().replace("**", ""))}</div>' for m in motivos
            )
            bloque(f'<div class="caja antes"><h4><span class="etiqueta mal">RECHAZADO</span> &nbsp;No sale</h4>'
                   f'{lineas}<div class="dato" style="color:#52514e">Se le devuelve a la IA con el motivo para que lo '
                   "corrija. Si falla dos veces, lo revisa una persona.</div></div>")
        else:
            bloque('<div class="caja despues"><h4><span class="etiqueta ok">APROBADO</span> &nbsp;Pasa el candado</h4>'
                   '<div class="dato">Todos los botones existen en la ayuda actual y no hay frases viejas ni '
                   "funciones de pago. Ahora lo lee una segunda IA antes de salir.</div></div>")
    st.caption(
        "Con honestidad: hoy ningún correo necesitaba el artículo de enviar facturas, porque todos tratan de "
        "configurar la empresa, crear un cliente o emitir la primera factura. El candado protege los correos que "
        "se escriban mañana sin que nadie tenga que acordarse de revisar la ayuda a mano."
    )


if st.button("▶  Correr el flujo ahora", type="primary"):
    carpeta = Path(tempfile.mkdtemp(prefix="cuadra_demo_"))
    lienzo = st.empty()
    lienzo.markdown(linea_de_tiempo({}), unsafe_allow_html=True)
    vistos: list[str] = []

    def avisar(mensaje: str) -> None:
        clave = mensaje.split(" ")[0]
        if clave in {p[0] for p in PASOS}:
            vistos.append(clave)
            lienzo.markdown(linea_de_tiempo({}, actual=clave) if len(vistos) == 1 else
                            linea_de_tiempo({c: "Listo." for c in vistos[:-1]}, actual=clave), unsafe_allow_html=True)
            time.sleep(PAUSA)

    inicio = time.perf_counter()
    resumen = flujo.correr(modo="repeticion", dir_salida=carpeta, avisar=avisar)
    hechos = {clave: resultado_de(clave, carpeta, resumen) for clave, *_ in PASOS}
    lienzo.markdown(linea_de_tiempo(hechos), unsafe_allow_html=True)
    st.session_state["demo"] = {"carpeta": str(carpeta), "resumen": resumen, "hechos": hechos}
    st.session_state.pop("demo_medicion", None)
    st.rerun()

demo = st.session_state.get("demo")
if demo:
    carpeta, resumen = Path(demo["carpeta"]), demo["resumen"]
    bloque(linea_de_tiempo(demo["hechos"]))
    st.success(
        f"Listo. El flujo encontró a {miles(resumen['elegibles'])} personas atascadas y dejó "
        f"{miles(resumen['correos_en_bandeja'])} correos listos para enviar."
    )

    bandeja = pd.read_csv(carpeta / "bandeja_salida.csv")
    st.markdown("#### Tres de los correos que acaba de preparar")
    muestra = pd.concat([bandeja[bandeja.paso == p].head(1) for p in ["sin_configurar", "sin_cliente", "sin_factura"]])
    columnas = st.columns(len(muestra)) if len(muestra) else []
    for columna, (_, fila) in zip(columnas, muestra.iterrows()):
        with columna:
            st.caption(f"{fila.nombre} · {NOMBRE_ATASCO.get(fila.paso, fila.paso).lower()}")
            bloque(correo_html(fila.email, fila.asunto, fila.cuerpo))

    para_excel = pd.DataFrame(
        {
            "Nombre": bandeja.nombre, "Correo": bandeja.email, "Asunto": bandeja.asunto, "Mensaje": bandeja.cuerpo,
            "En qué paso se quedó": bandeja.paso.map(NOMBRE_ATASCO), "Días sin avanzar": bandeja.dias_quieto,
        }
    )
    st.download_button(
        "Descargar los correos (se abre en Excel)",
        para_excel.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="cuadra_correos_listos.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    seccion_ayuda()

    # --- Avanzar 14 días ------------------------------------------------------------------------------------
    st.divider()
    st.markdown(f"#### ¿Y si avanzamos {config.VENTANA_DIAS} días?")
    st.markdown(
        f"Todavía no se ha enviado nada, así que no hay resultado real. Aquí puedes **inventar** cuánto ayuda el "
        f"correo y ver cómo el flujo decidiría, pasados {config.VENTANA_DIAS} días, si vale la pena enviarlo a todos."
    )
    eleccion = st.radio("En esta simulación, el correo…", list(EFECTOS), index=2, horizontal=True, key="efecto")
    if st.button(f"⏩  Avanzar {config.VENTANA_DIAS} días (simulado)"):
        asignacion = pd.read_csv(carpeta / "asignacion_experimento.csv")
        with st.spinner("Contando quién emitió su primera factura en cada grupo…"):
            time.sleep(PAUSA)
            resultado, _ = medir(asignacion, simular_eventos(asignacion, efecto=EFECTOS[eleccion]))
        st.session_state["demo_medicion"] = {"eleccion": eleccion, **resultado.como_dict()}

    medicion = st.session_state.get("demo_medicion")
    if medicion:
        st.warning(
            f"SIMULADO · Resultado inventado con la opción «{medicion['eleccion']}». Sirve para ver cómo se decide, "
            "no es un resultado del flujo."
        )
        izquierda, derecha = st.columns([3, 2], gap="large")
        with izquierda:
            tabla = pd.DataFrame(
                {
                    "Grupo": ["Recibió correo", "No recibió"],
                    "tasa": [medicion["tasa_t"], medicion["tasa_c"]],
                    "etiqueta": [
                        f"{pct(medicion['tasa_t'], 1)}  ·  {medicion['conv_t']} de {medicion['n_t']}",
                        f"{pct(medicion['tasa_c'], 1)}  ·  {medicion['conv_c']} de {medicion['n_c']}",
                    ],
                }
            )
            base = alt.Chart(tabla).encode(
                y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelFontSize=13)),
                x=alt.X("tasa:Q", title=None, axis=None,
                        scale=alt.Scale(domain=[0, max(medicion["tasa_t"], medicion["tasa_c"], 0.01) * 1.7])),
            )
            st.markdown("**Qué parte emitió su primera factura**")
            st.altair_chart(
                (
                    base.mark_bar(cornerRadiusEnd=4, size=30).encode(
                        color=alt.Color("Grupo:N", legend=None, sort=None,
                                        scale=alt.Scale(domain=["Recibió correo", "No recibió"], range=[AZUL, NARANJA]))
                    )
                    + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
                ).properties(height=alt.Step(56)).configure_view(strokeWidth=0),
                width="stretch",
            )
        with derecha:
            diferencia = medicion["diferencia"] * 100
            if medicion["decision"] == "extender":
                veredicto = ("<b>Enviar el correo a todos.</b> La diferencia es tan grande que no puede ser "
                             "casualidad.")
            else:
                veredicto = ("<b>No extenderlo todavía: reescribir el mensaje.</b> La diferencia es tan pequeña que "
                             "podría ser casualidad.")
            bloque(
                f"""<div class="caja"><h4>Decisión del flujo</h4>
                <div class="dato">El grupo con correo facturó <b>{decimal(f'{diferencia:+.1f}')} puntos</b> respecto al
                grupo sin correo.</div><div class="dato">{veredicto}</div>
                <div class="dato" style="color:#52514e">La regla se fijó antes de mirar los resultados, para que nadie
                pueda acomodarla después.</div></div>"""
            )
else:
    seccion_ayuda()
