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
    AZUL, NARANJA, NOMBRE_ATASCO, TINTA, bloque, correo_html, decimal, estilos, miles, pct,
)
from cuadra import config, flujo  # noqa: E402
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
    ("6/8", "Escribe y revisa los correos", "Un correo por paso pendiente, oficio y antigüedad. Otra IA lo revisa.", "ia"),
    ("8/8", "Deja la bandeja lista", "Asigna a cada persona del grupo con correo el suyo, con su nombre.", "codigo"),
]
QUIEN = {"ia": '<span class="quien ia">LO HACE LA IA</span>', "codigo": '<span class="quien codigo">LO HACE EL PROGRAMA</span>'}
EFECTOS = {"No ayuda nada": 0.0, "Ayuda un poco": 0.03, "Ayuda mucho": 0.08}

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
        extra = "ninguno tuvo que pasar a revisión humana." if revision == 0 else f"{revision} esperan revisión humana."
        return f"{total} correos escritos; {resumen['variantes_aprobadas']} aprobados y {extra}"
    return f"{miles(resumen['correos_en_bandeja'])} correos listos para enviar, uno por persona."


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

    # --- Avanzar 14 días ------------------------------------------------------------------------------------
    st.divider()
    st.markdown(f"#### ¿Y si avanzamos {config.VENTANA_DIAS} días?")
    st.markdown(
        f"Todavía no se ha enviado nada, así que no hay resultado real. Aquí puedes **inventar** cuánto ayuda el "
        f"correo y ver cómo el flujo decidiría, pasados {config.VENTANA_DIAS} días, si vale la pena enviarlo a todos."
    )
    eleccion = st.radio("En esta simulación, el correo…", list(EFECTOS), index=2, horizontal=True)
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
