"""Panel local: muestra lo que dejó la última corrida en salida/. No recalcula nada, salvo la redacción en vivo."""

import json
import os
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from cuadra import config
from cuadra.conocimiento import BaseVigente
from cuadra.modelo import Modelo, hay_clave
from cuadra.redaccion import Variante, personalizar
from cuadra.verificacion import ETIQUETAS, procesar

DIR = Path(os.environ.get("CUADRA_DIR_SALIDA") or config.DIR_SALIDA)

# Paleta: un solo tono para magnitudes, gris para el contexto y un segundo tono solo donde hay dos series.
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#c3c2b7"

NOMBRE_PASO = {
    "registro": "Se registró",
    "configuro_empresa": "Configuró su empresa",
    "creo_cliente": "Creó un cliente",
    "emitio_primera_factura": "Emitió su primera factura",
    "emitio_5_facturas": "Emitió 5 facturas",
    "pago": "Pagó",
}
NOMBRE_ATASCO = {
    "sin_configurar": "Sin configurar la empresa",
    "sin_cliente": "Sin crear un cliente",
    "sin_factura": "Sin emitir la primera factura",
}

st.set_page_config(page_title="Cuadra · De registrarse a facturar", layout="wide")


def leer_csv(nombre: str) -> pd.DataFrame | None:
    ruta = DIR / nombre
    return pd.read_csv(ruta) if ruta.is_file() else None


def leer_json(nombre: str):
    ruta = DIR / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def pct(valor: float) -> str:
    return f"{valor:.0%}"


def como_markdown(cuerpo: str) -> str:
    """Conserva los saltos de línea del correo al mostrarlo."""
    return cuerpo.replace("\n", "  \n")


resumen = leer_json("resumen.json")
st.title("Cuadra · De registrarse a facturar")

if resumen is None:
    st.warning(
        "Todavía no hay resultados que mostrar. Ejecuta `uv run cuadra correr` en la carpeta del "
        "proyecto y vuelve a abrir el panel."
    )
    st.stop()

st.caption(
    f"Corrida del {resumen['fecha']} · modelo {resumen['modelo']} · modo {resumen['modo']} · "
    f"{resumen['llamadas_reales']} llamadas reales en esta corrida"
)
cifras = st.columns(5)
cifras[0].metric("Personas sin primera factura", resumen["personas_sin_facturar"])
cifras[1].metric("Elegibles para escribirles", resumen["elegibles"])
cifras[2].metric("Correos en la bandeja", resumen["correos_en_bandeja"])
cifras[3].metric(
    "Variantes aprobadas",
    f"{resumen['variantes_aprobadas']} de {resumen['variantes_aprobadas'] + resumen['variantes_en_revision']}",
)
cifras[4].metric("Variantes en revisión humana", resumen["variantes_en_revision"])

tab_diagnostico, tab_base, tab_mensajes, tab_experimento, tab_limites = st.tabs(
    ["Diagnóstico", "Base vigente", "Mensajes", "Experimento", "Qué no cubre"]
)

# ---------------------------------------------------------------------------------------------------
with tab_diagnostico:
    diagnostico = (DIR / "diagnostico.md").read_text(encoding="utf-8") if (DIR / "diagnostico.md").is_file() else ""
    if "## Hallazgo principal" in diagnostico:
        hallazgo = diagnostico.split("## Hallazgo principal")[1].split("## ")[0].strip()
        st.subheader("Dónde se pierde la gente")
        st.markdown(hallazgo)

    embudo = leer_csv("embudo.csv")
    cruce = leer_csv("embudo_por_canal_segmento.csv")
    izquierda, derecha = st.columns(2)

    if embudo is not None:
        with izquierda:
            st.markdown("**Embudo: de 1500 registrados, cuántos llegan a cada paso**")
            embudo["Paso"] = embudo.paso.map(NOMBRE_PASO)
            embudo["etiqueta"] = [f"{c}  ({p:.0%})" for c, p in zip(embudo.contactos, embudo.pct_registro)]
            base = alt.Chart(embudo).encode(
                y=alt.Y("Paso:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
                x=alt.X("contactos:Q", title="Personas", scale=alt.Scale(domain=[0, 1800])),
                tooltip=[alt.Tooltip("Paso:N"), alt.Tooltip("contactos:Q", title="Personas"),
                         alt.Tooltip("pct_registro:Q", title="Del registro", format=".0%")],
            )
            st.altair_chart(
                base.mark_bar(color=AZUL, cornerRadiusEnd=4, size=22)
                + base.mark_text(align="left", dx=6, color="#52514e").encode(text="etiqueta:N"),
                use_container_width=True,
            )

    if cruce is not None:
        with derecha:
            st.markdown("**De quienes configuran su empresa, qué parte crea un cliente**")
            cruce["Grupo"] = cruce.canal + " · " + cruce.segmento
            cruce = cruce.sort_values("pct_config_a_cliente")
            peor = cruce.Grupo.iloc[0]
            cruce["Destacado"] = cruce.Grupo.map(lambda g: "La fuga" if g == peor else "Resto")
            cruce["etiqueta"] = [f"{p:.0%}  (n = {n})" for p, n in zip(cruce.pct_config_a_cliente, cruce.n)]
            base = alt.Chart(cruce).encode(
                y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)),
                x=alt.X("pct_config_a_cliente:Q", title="Pasa de configurar a crear cliente",
                        axis=alt.Axis(format=".0%"), scale=alt.Scale(domain=[0, 1.15])),
                tooltip=[alt.Tooltip("Grupo:N"), alt.Tooltip("n:Q", title="Registrados"),
                         alt.Tooltip("pct_config_a_cliente:Q", title="Configura → cliente", format=".0%"),
                         alt.Tooltip("pct_emitio_primera_factura:Q", title="Llega a facturar", format=".0%")],
            )
            barras = base.mark_bar(cornerRadiusEnd=4, size=22).encode(
                color=alt.Color(
                    "Destacado:N", title=None,
                    scale=alt.Scale(domain=["La fuga", "Resto"], range=[AZUL, GRIS]),
                    legend=alt.Legend(orient="bottom"),
                )
            )
            st.altair_chart(
                barras + base.mark_text(align="left", dx=6, color="#52514e").encode(text="etiqueta:N"),
                use_container_width=True,
            )

    tiempos = leer_csv("tiempos_entre_pasos.csv")
    if tiempos is not None:
        st.markdown("**Días entre un paso y el siguiente** (entre quienes dieron los dos)")
        tabla = tiempos.assign(desde=tiempos.desde.map(NOMBRE_PASO), hasta=tiempos.hasta.map(NOMBRE_PASO))
        tabla.columns = ["Desde", "Hasta", "Personas", "Mediana", "Percentil 90", "Máximo"]
        st.dataframe(tabla, hide_index=True, use_container_width=True)
        st.caption(
            "Quien avanza lo hace en pocos días. Por eso el flujo considera atascada a una persona que lleva "
            f"{config.DIAS_ATASCADO} días o más sin dar un paso, y no le escribe antes."
        )
    if cruce is not None:
        with st.expander("Ver la tabla completa por canal y segmento"):
            tabla = cruce[["canal", "segmento", "n", "pct_configuro_empresa", "pct_creo_cliente",
                           "pct_emitio_primera_factura", "pct_pago", "pct_config_a_cliente"]].copy()
            for columna in tabla.columns[3:]:
                tabla[columna] = tabla[columna].map(pct)
            tabla.columns = ["Canal", "Segmento", "Registrados", "Configura", "Crea cliente", "Factura", "Paga",
                             "Configura → cliente"]
            st.dataframe(tabla, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------------------------------
base_json = leer_json("base_vigente.json")
base_vigente = BaseVigente.model_validate(base_json) if base_json else None

with tab_base:
    if base_vigente is None:
        st.info("Esta corrida no pudo construir la base vigente (sin caché y sin clave).")
    else:
        st.subheader("Lo que el Centro de Ayuda dice hoy")
        st.markdown(
            "Claude compara cada artículo de ayuda con las notas de cambios de la semana. Los correos solo "
            "pueden usar el texto vigente; una instrucción obsoleta hace que la verificación rechace el correo."
        )
        for articulo in base_vigente.articulos:
            estado = "Vigente" if articulo.vigente else "Desactualizado · corregido"
            with st.expander(f"{articulo.archivo} — {estado}", expanded=not articulo.vigente):
                if articulo.vigente:
                    st.markdown(articulo.texto_vigente)
                    continue
                st.markdown(f"Cambiado por: {', '.join(articulo.notas_que_lo_cambian)}")
                antes, despues = st.columns(2)
                with antes:
                    st.markdown("**Frases del artículo que ya no son ciertas**")
                    for frase in articulo.frases_obsoletas:
                        st.markdown(f"- ~~{frase.replace('**', '')}~~")
                with despues:
                    st.markdown("**Texto vigente**")
                    st.markdown(articulo.texto_vigente)
        st.markdown("**Funciones que no están en todos los planes** (los correos no las mencionan)")
        for funcion in base_vigente.funciones_restringidas:
            st.markdown(f"- {funcion.nombre}: solo plan {funcion.plan}. Límites: {'; '.join(funcion.limites)}")
        columnas = st.columns(2)
        columnas[0].markdown("**Rutas de menú válidas**\n\n" + "\n".join(f"- {r}" for r in base_vigente.rutas_validas))
        columnas[1].markdown(
            "**Rutas de menú obsoletas**\n\n" + "\n".join(f"- ~~{r}~~" for r in base_vigente.rutas_obsoletas)
        )

# ---------------------------------------------------------------------------------------------------
bandeja = leer_csv("bandeja_salida.csv")
variantes = {
    Variante(**v["variante"]).clave: v for v in (leer_json("variantes.json") or [])
}

with tab_mensajes:
    if bandeja is None or bandeja.empty:
        st.info("La bandeja de salida está vacía en esta corrida. Revisa la cola de revisión más abajo.")
    else:
        st.subheader("Bandeja de salida")
        bandeja["actividad"] = bandeja.variante.str.split("|").str[1]
        filtros = st.columns(3)
        paso = filtros[0].selectbox("Paso", ["Todos"] + sorted(bandeja.paso.unique()))
        actividad = filtros[1].selectbox("Oficio", ["Todos"] + sorted(bandeja.actividad.unique()))
        tramo = filtros[2].selectbox("Antigüedad", ["Todos"] + sorted(bandeja.tramo.unique()))
        vista = bandeja
        if paso != "Todos":
            vista = vista[vista.paso == paso]
        if actividad != "Todos":
            vista = vista[vista.actividad == actividad]
        if tramo != "Todos":
            vista = vista[vista.tramo == tramo]
        st.caption(f"{len(vista)} correos con estos filtros, de {len(bandeja)} en la bandeja.")

        if vista.empty:
            st.info("Nadie del grupo que recibe correo cumple estos filtros.")
        else:
            opciones = {
                f"{f.id_contacto} · {f.nombre} · {f.actividad} · {f.paso} · {f.dias_quieto} días quieta": i
                for i, f in vista.iterrows()
            }
            fila = bandeja.loc[opciones[st.selectbox("Persona", list(opciones))]]
            izquierda, derecha = st.columns([3, 2])
            with izquierda:
                with st.container(border=True):
                    st.caption(f"Para: {fila.email}")
                    st.markdown(f"**{fila.asunto}**")
                    st.markdown(como_markdown(fila.cuerpo))
            with derecha:
                st.markdown("**Por qué recibe este correo**")
                st.markdown(
                    f"- Situación: {NOMBRE_ATASCO[fila.paso]}\n"
                    f"- Lleva {fila.dias_quieto} días sin dar un paso ({fila.tramo})\n"
                    f"- Oficio: {fila.actividad}\n"
                    f"- Grupo: tratamiento"
                )
                procesada = variantes.get(fila.variante)
                if procesada:
                    st.markdown("**Verificación de esta variante**")
                    st.markdown(f"- Reglas fijas: pasa las 8\n- Intentos de redacción: {procesada['intentos']}")
                    veredicto = procesada.get("veredicto")
                    if veredicto:
                        for campo, etiqueta in ETIQUETAS.items():
                            st.markdown(f"- Juez, «{campo}»: {'cumple' if veredicto[campo] else 'no cumple: ' + etiqueta}")

            if hay_clave() and base_vigente is not None:
                st.divider()
                st.markdown("**Redactar esta variante en vivo**")
                st.caption(
                    "Llama a Claude ahora, sin usar las respuestas guardadas, y pasa el resultado por la misma "
                    "verificación. No modifica la bandeja ni el caché del repositorio."
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
                        with st.container(border=True):
                            st.markdown(f"**{asunto}**")
                            st.markdown(como_markdown(cuerpo))

    st.subheader("Cola de revisión humana")
    cola = leer_csv("cola_revision.csv")
    if cola is None or cola.empty:
        st.markdown("Vacía: ninguna variante falló la verificación dos veces en esta corrida.")
    else:
        st.markdown(
            f"{len(cola)} variantes no pasaron la verificación. Sus {int(cola.personas_sin_correo.sum())} "
            "destinatarios no reciben correo hasta que una persona las revise."
        )
        st.dataframe(cola, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------------------------------
with tab_experimento:
    st.subheader("Cómo sabríamos si funcionó")
    st.markdown(
        "Cada persona elegible cae en **tratamiento** (recibe correo) o **control** (no recibe) según un "
        "hash de su identificador: el reparto es al azar, siempre el mismo y no depende de quién lo corra. "
        f"A los {config.VENTANA_DIAS} días se compara qué parte de cada grupo emitió su primera factura. "
        "Se cuenta a todos los asignados, abran el correo o no."
    )
    cifras = st.columns(4)
    cifras[0].metric("Tratamiento", resumen["tratamiento"])
    cifras[1].metric("Control", resumen["control"])
    cifras[2].metric("Conversión natural estimada", pct(resumen["tasa_base_estimada"]))
    cifras[3].metric("Efecto mínimo detectable", f"{resumen['efecto_minimo_detectable'] * 100:.1f} puntos")
    st.caption(
        "Conversión natural: entre quienes llevaban 3 días o más quietos, del 0% al 3% facturó en los 14 días "
        "siguientes (cinco fechas de corte históricas). Con estos tamaños, una mejora menor que el efecto "
        "mínimo detectable no se distinguiría del azar."
    )
    st.markdown(
        "**Regla de decisión, escrita antes de mirar resultados:** si el intervalo de confianza del 95% de la "
        "diferencia queda entero por encima de cero, el flujo se extiende a todos. Si no, se itera el mensaje "
        "por paso y antigüedad."
    )

    equilibrio = leer_csv("equilibrio.csv")
    if equilibrio is not None:
        st.markdown("**¿Los dos grupos se parecen?**")
        largo = equilibrio.melt(
            id_vars=["dimension", "valor"], value_vars=["tratamiento", "control"],
            var_name="Grupo", value_name="Personas",
        )
        largo["Grupo"] = largo.Grupo.str.capitalize()
        largo["Dimensión"] = largo.dimension.str.capitalize()
        grafico = (
            alt.Chart(largo)
            .mark_bar(cornerRadiusEnd=3, size=9)
            .encode(
                y=alt.Y("valor:N", title=None, sort=None),
                yOffset=alt.YOffset("Grupo:N", sort=["Tratamiento", "Control"]),
                x=alt.X("Personas:Q", title="Personas"),
                color=alt.Color("Grupo:N", title=None, sort=["Tratamiento", "Control"],
                                scale=alt.Scale(domain=["Tratamiento", "Control"], range=[AZUL, NARANJA]),
                                legend=alt.Legend(orient="bottom")),
                tooltip=["Dimensión:N", alt.Tooltip("valor:N", title="Valor"), "Grupo:N", "Personas:Q"],
            )
            .properties(height=alt.Step(26))
            .facet(row=alt.Row("Dimensión:N", title=None, header=alt.Header(labelAngle=0, labelAlign="left")))
            .resolve_scale(y="independent")
        )
        st.altair_chart(grafico, use_container_width=True)
        with st.expander("Ver la tabla"):
            tabla = equilibrio.assign(pct_tratamiento=equilibrio.pct_tratamiento.map(pct))
            tabla.columns = ["Dimensión", "Valor", "Tratamiento", "Control", "% en tratamiento"]
            st.dataframe(tabla, hide_index=True, use_container_width=True)

    aa = leer_json("prueba_aa.json")
    if aa:
        st.markdown("**Prueba A/A: el mismo reparto sobre julio y agosto, cuando nadie recibió correo**")
        st.markdown(
            f"Grupo «tratamiento»: {aa['conv_t']} de {aa['n_t']} facturaron ({aa['tasa_t']:.1%}). "
            f"Grupo «control»: {aa['conv_c']} de {aa['n_c']} ({aa['tasa_c']:.1%}). "
            f"Diferencia: {aa['diferencia'] * 100:+.1f} puntos, p = {aa['valor_p']:.2f}. "
            "Sin intervención no debe haber diferencia, y no la hay."
        )
        st.caption(
            "La primera semilla que probé sí daba diferencia aquí (p = 0,01): por azar había dejado menos "
            "autónomos de canal orgánico en un grupo. La cambié con una regla fija antes de enviar nada: la "
            f"primera candidata con p > {config.UMBRAL_AA}. Esa regla está en una prueba automática."
        )

    simulado = leer_json("SIMULADO_resultado_experimento.json")
    st.markdown("**Así se leería el resultado**")
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
        cifras = st.columns(4)
        cifras[0].metric("Tratamiento (simulado)", pct(simulado["tasa_t"]), f"{simulado['conv_t']} de {simulado['n_t']}", delta_color="off")
        cifras[1].metric("Control (simulado)", pct(simulado["tasa_c"]), f"{simulado['conv_c']} de {simulado['n_c']}", delta_color="off")
        cifras[2].metric(
            "Diferencia (simulada)", f"{simulado['diferencia'] * 100:+.1f} puntos",
            f"IC 95%: {simulado['ic95'][0] * 100:+.1f} a {simulado['ic95'][1] * 100:+.1f}", delta_color="off",
        )
        cifras[3].metric("Decisión según la regla", simulado["decision"])
        por_estrato = leer_csv("SIMULADO_resultado_por_estrato.csv")
        if por_estrato is not None:
            with st.expander("Ver el resultado simulado por paso y antigüedad"):
                tabla = por_estrato[["dimension", "valor", "n_t", "conv_t", "n_c", "conv_c", "diferencia", "valor_p"]].copy()
                tabla["diferencia"] = tabla.diferencia.map(lambda d: f"{d * 100:+.1f} puntos")
                tabla["valor_p"] = tabla.valor_p.map(lambda p: f"{p:.3f}")
                tabla.columns = ["Dimensión", "Valor", "Tratamiento", "Facturaron", "Control", "Facturaron ", "Diferencia", "p"]
                st.dataframe(tabla, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------------------------------
with tab_limites:
    st.subheader("Qué no cubre este flujo")
    st.markdown(
        """
- **No envía correos.** Las direcciones del caso son ficticias. La salida es una bandeja lista para cargar en
  una herramienta de envío; tampoco mide aperturas ni clics.
- **No prueba por qué se atascan los autónomos de canal orgánico al crear su primer cliente.** Los datos
  muestran dónde y a quién, no el motivo. Hipótesis a investigar: no saben qué datos fiscales pedir a su cliente.
- **El efecto es desconocido.** El resultado que muestra la pestaña Experimento es simulado. La respuesta real
  llega 14 días después del primer envío.
- **Los datos son sintéticos.** Que casi nadie avance solo después de 3 días puede ser un artefacto del caso.
- **Sin consentimiento ni enlace de baja.** En producción son obligatorios antes de escribir a nadie.
- **Un solo canal y un solo mensaje por persona.** Sin recordatorios, sin avisos dentro del producto.
- **La priorización es simple:** primero quienes se atascaron hace menos días. No hay modelo predictivo.
- **Ocho personas pagaron sin haber facturado nunca.** Quedan fuera del flujo y listadas en
  `salida/pagadores_sin_factura.csv` para que alguien las mire.
"""
    )
