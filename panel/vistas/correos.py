"""Los correos: la bandeja lista para enviar, persona por persona, y las instrucciones de ayuda que usan."""

import html
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from comun import (  # noqa: E402
    NOMBRE_ATASCO, NOMBRE_TRAMO, bloque, correo_html, cuerpo_html, estilos, leer_csv, leer_json, miles,
    pasos_del_articulo,
)
from cuadra import config  # noqa: E402
from cuadra.conocimiento import BaseVigente  # noqa: E402
from cuadra.modelo import Modelo, hay_clave  # noqa: E402
from cuadra.redaccion import Variante, personalizar  # noqa: E402
from cuadra.verificacion import procesar  # noqa: E402

CRITERIOS_REVISION = {
    "respaldado": "Todo lo que dice está en la ayuda actualizada",
    "responde_al_paso": "Pide justo el paso que le falta",
    "tono_adecuado": "Tono cercano y directo",
    "un_solo_paso": "Pide una sola acción",
}
REGLAS = [
    "Lleva el nombre de la persona",
    "Solo usa rutas de menú que existen hoy",
    "Ninguna instrucción vieja",
    "No ofrece funciones de planes de pago",
    "Sin precios, descuentos ni enlaces",
    "Largo dentro del límite",
]

estilos()
st.title("Los correos")
st.markdown(
    "Cada persona atascada del grupo que recibe correo tiene el suyo, escrito según el paso en que se quedó. "
    "Elige a alguien para ver exactamente lo que recibiría."
)

base_json = leer_json("base_vigente.json")
base_vigente = BaseVigente.model_validate(base_json) if base_json else None
bandeja = leer_csv("bandeja_salida.csv")
variantes = {Variante(**v["variante"]).clave: v for v in (leer_json("variantes.json") or [])}

tab_correos, tab_ayuda = st.tabs(["Correos listos para enviar", "Las instrucciones que usan"])

with tab_correos:
    if bandeja is None or bandeja.empty:
        st.info("La bandeja de salida está vacía en esta corrida. Revisa la cola de revisión más abajo.")
    else:
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
                    <div class="dato"><span>Grupo:</span> le tocó recibir correo en el sorteo</div></div>"""
                )
                procesada = variantes.get(fila.variante)
                if procesada:
                    veredicto = procesada.get("veredicto") or {}
                    reglas = "".join(f"<li>{regla}</li>" for regla in REGLAS)
                    revision = "".join(
                        f'<li class="{"" if veredicto.get(campo) else "no"}">{criterio}</li>'
                        for campo, criterio in CRITERIOS_REVISION.items()
                    )
                    intentos = (
                        "al primer intento" if procesada["intentos"] == 1 else "al segundo intento, tras una corrección"
                    )
                    bloque(
                        f"""<div style="height:12px"></div><div class="caja"><h4>Revisiones que pasó antes de salir</h4>
                        <div class="dato"><span>Reglas automáticas</span></div><ul class="lista">{reglas}</ul>
                        <div class="dato"><span>Segunda revisión con IA</span></div><ul class="lista">{revision}</ul>
                        <div class="dato"><span>Aprobado</span> {intentos}</div></div>"""
                    )

            if hay_clave() and base_vigente is not None:
                st.divider()
                st.markdown("**Escribir este correo de nuevo, en vivo**")
                st.caption(
                    "Le pide a Claude un correo nuevo ahora mismo y lo pasa por las mismas revisiones. No cambia la "
                    "bandeja guardada."
                )
                if st.button("Redactar en vivo"):
                    variante = Variante(**variantes[fila.variante]["variante"])
                    contactos = pd.read_csv(config.DIR_DATOS / "crm_contactos.csv")
                    segmento = contactos[contactos.actividad == variante.actividad].segmento.iloc[0]
                    with st.spinner("Claude está escribiendo y la segunda revisión lo está leyendo…"):
                        modelo = Modelo(dir_cache=Path(tempfile.mkdtemp()), modo="vivo")
                        nueva = procesar(variante, base_vigente, modelo, segmento)
                    st.markdown(f"Resultado: **{nueva.estado}** en {nueva.intentos} intento(s), "
                                f"{modelo.llamadas_reales} llamadas a la IA.")
                    for motivo in nueva.motivos:
                        st.markdown(f"- {motivo}")
                    if nueva.correo:
                        asunto, cuerpo = personalizar(nueva.correo, fila.nombre)
                        bloque(correo_html(fila.email, asunto, cuerpo))

    st.markdown("#### Correos que esperan revisión de una persona")
    cola = leer_csv("cola_revision.csv")
    if cola is None or cola.empty:
        bloque(
            '<span class="etiqueta ok">NINGUNO</span> &nbsp; Todos los correos pasaron las revisiones. Si alguno '
            "fallara dos veces, sus destinatarios no recibirían nada hasta que una persona lo revisara."
        )
    else:
        st.markdown(
            f"{len(cola)} correos no pasaron las revisiones. Sus {int(cola.personas_sin_correo.sum())} "
            "destinatarios no reciben nada hasta que una persona los revise."
        )
        st.dataframe(cola, hide_index=True, width="stretch")

with tab_ayuda:
    if base_vigente is None:
        st.info("Esta corrida no pudo revisar los artículos de ayuda (sin respuestas guardadas y sin clave).")
    else:
        viejos = [a for a in base_vigente.articulos if not a.vigente]
        plural = "s" if len(viejos) != 1 else ""
        bloque(
            f"""<div class="idea">Un correo solo sirve si sus instrucciones son ciertas hoy. La IA comparó los
            {len(base_vigente.articulos)} artículos del Centro de Ayuda con los cambios recientes del producto y
            encontró <b>{len(viejos)} desactualizado{plural}</b>. Un correo basado en la versión vieja mandaría a la
            gente a un botón que ya no está ahí.</div>"""
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

        st.markdown("#### Artículos que siguen al día")
        for articulo in base_vigente.articulos:
            if articulo.vigente:
                with st.expander(f"{articulo.titulo}  ·  al día"):
                    st.markdown(articulo.texto_vigente)

        st.markdown("#### Lo que los correos no pueden mencionar")
        for funcion in base_vigente.funciones_restringidas:
            st.markdown(
                f"- **{funcion.nombre}**: solo está en el plan {funcion.plan}, y estas personas no tienen plan de pago."
            )
        with st.expander("Ver las rutas de menú válidas y las que ya no existen"):
            columnas = st.columns(2)
            columnas[0].markdown("**Válidas hoy**\n\n" + "\n".join(f"- {r}" for r in base_vigente.rutas_validas))
            columnas[1].markdown("**Ya no existen**\n\n" + "\n".join(f"- ~~{r}~~" for r in base_vigente.rutas_obsoletas))
