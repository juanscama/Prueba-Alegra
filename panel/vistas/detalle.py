"""Detalle técnico: el análisis completo de Growth (de `cuadra analizar`) y las pruebas del experimento.

Lee salida/ y salida/inteligencia/. No recalcula nada.
"""

import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt
import pandas as pd
import streamlit as st

from cuadra import config
from cuadra.intervenciones import CANALES

import comun  # noqa: E402

DIR = Path(os.environ.get("CUADRA_DIR_SALIDA") or config.DIR_SALIDA) / config.DIR_INTELIGENCIA_NOMBRE
AZUL, NARANJA, GRIS, TINTA = "#2a78d6", "#eb6834", "#cbd5e1", "#0f172a"

NOMBRE_ETAPA = {
    "registro": "Se registró", "configuro_empresa": "Configuró su empresa", "creo_cliente": "Creó un cliente",
    "emitio_primera_factura": "Primera factura", "pago": "Pagó (tras facturar)",
}
NOMBRE_PASO = {"sin_configurar": "Sin configurar empresa", "sin_cliente": "Sin crear cliente", "sin_factura": "Sin primera factura"}
NOMBRE_CANAL = {"organico": "Orgánico", "contador": "Contador", "pago": "Anuncios", "referido": "Referido"}
NOMBRE_SEGMENTO = {"autonomo": "Autónomos", "pyme": "Pymes"}
SELLOS = {
    "dato": ("DATO DEL CASO", "#e9edf2", "#334155"),
    "calculado": ("CALCULADO", "#dcebfc", "#1c5cab"),
    "estimacion": ("ESTIMACIÓN", "#fff1d6", "#8a5a00"),
    "hipotesis": ("HIPÓTESIS", "#efe4fb", "#6b2fb3"),
    "simulado": ("SIMULADO", "#fbe1e1", "#b02a2a"),
    "ia": ("REDACTADO POR IA", "#dcf3dc", "#0b7a0b"),
    "recomendacion": ("RECOMENDACIÓN", "#e0f2f1", "#0f6b63"),
    "hecho": ("HECHO", "#dcebfc", "#1c5cab"),
}

comun.estilos()
st.markdown(
    """<style>
.block-container {padding-top: 2.2rem; max-width: 1240px;}
.sello {display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:0.06em;border-radius:999px;padding:2px 9px;margin-right:6px;vertical-align:middle;}
.guia {display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:2px 0 16px;}
.guia div {border:1px solid #e2e8f0;border-radius:12px;padding:12px 14px;background:#f8fafc;font-size:0.9rem;line-height:1.45;color:#1f2937;}
.guia b {display:block;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#52514e;margin-bottom:4px;}
.punto {border-left:3px solid #cbd5e1;padding:6px 12px;margin:6px 0;font-size:0.97rem;line-height:1.5;}
.punto small {color:#64748b;}
.cifras {display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:4px 0 16px;}
.cifra {border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;background:#fff;}
.cifra .v {font-size:1.9rem;font-weight:700;color:#0f172a;line-height:1.1;}
.cifra .t {font-size:0.86rem;color:#52514e;margin-top:4px;line-height:1.35;}
.leyenda {font-size:0.85rem;color:#52514e;margin:0 0 14px;}
div[data-baseweb="tab-list"] {gap:4px;flex-wrap:wrap;}
</style>""",
    unsafe_allow_html=True,
)


def leer_csv(nombre):
    ruta = DIR / nombre
    return pd.read_csv(ruta) if ruta.is_file() else None


def leer_json(nombre):
    ruta = DIR / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def sello(tipo: str) -> str:
    texto, fondo, color = SELLOS[tipo]
    return f'<span class="sello" style="background:{fondo};color:{color}">{texto}</span>'


def pct(x, d=0) -> str:
    return f"{x * 100:.{d}f}%".replace(".", ",")


def guia(que: str, importa: str, decision: str) -> None:
    st.markdown(
        f'<div class="guia"><div><b>Qué vemos</b>{que}</div><div><b>Por qué importa</b>{importa}</div>'
        f"<div><b>Qué decisión permite</b>{decision}</div></div>",
        unsafe_allow_html=True,
    )


def cifras(items) -> None:
    celdas = "".join(f'<div class="cifra"><div class="v">{v}</div><div class="t">{s} {t}</div></div>' for v, t, s in items)
    st.markdown(f'<div class="cifras">{celdas}</div>', unsafe_allow_html=True)


def barras(tabla, y, x, etiqueta, formato=".0%", color=AZUL, dominio=None):
    base = alt.Chart(tabla).encode(
        y=alt.Y(f"{y}:N", sort=None, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=12)),
        x=alt.X(f"{x}:Q", title=None, axis=None, scale=alt.Scale(domain=dominio) if dominio else alt.Undefined),
        tooltip=[alt.Tooltip(f"{y}:N"), alt.Tooltip(f"{x}:Q", format=formato)],
    )
    grafico = base.mark_bar(color=color, cornerRadiusEnd=4, size=20) + base.mark_text(
        align="left", dx=6, color=TINTA, fontSize=12
    ).encode(text=f"{etiqueta}:N")
    st.altair_chart(grafico.properties(height=alt.Step(34)).configure_view(strokeWidth=0), width="stretch")


st.title("Detalle técnico")
st.markdown(
    '<p class="leyenda">El análisis completo detrás del resumen, para quien quiera revisar cada cifra. Cada una '
    f"lleva una etiqueta que dice de dónde sale: {sello('dato')}{sello('calculado')}{sello('estimacion')}"
    f"{sello('hipotesis')}{sello('simulado')}{sello('ia')}</p>",
    unsafe_allow_html=True,
)
with st.expander("Glosario: los términos técnicos de esta página, en palabras simples"):
    st.markdown(
        """<div class="glosario">
<div><b>Embudo:</b> los pasos de registrarse a facturar y cuánta gente llega a cada uno.</div>
<div><b>Conversión:</b> qué parte de la gente pasa de un paso al siguiente.</div>
<div><b>Cohorte:</b> el grupo de personas que se registró en la misma semana o mes.</div>
<div><b>Cohorte madura:</b> la que ya tuvo tiempo de avanzar, para no contar como perdido a quien aún está a tiempo.</div>
<div><b>Tratamiento:</b> el grupo que recibe el correo.</div>
<div><b>Control:</b> el grupo que no recibe nada y sirve de comparación.</div>
<div><b>Prueba A/A:</b> repetir el sorteo sobre meses en que nadie recibió nada. Si los grupos salen distintos, el sorteo está mal.</div>
<div><b>Valor p:</b> qué tan probable es ver esa diferencia por pura casualidad. Cuanto más bajo, menos probable.</div>
<div><b>Margen de error (IC 95%):</b> el rango donde casi seguro está el efecto real.</div>
<div><b>Efecto mínimo detectable:</b> la mejora más pequeña que el experimento puede distinguir de la casualidad.</div>
<div><b>Diferencia estandarizada (SMD):</b> cuánto se parecen los dos grupos en una característica. Menos de 0,1 es parecido.</div>
<div><b>Post-estratificación:</b> comparar dentro de cada subgrupo para corregir diferencias que dejó el azar.</div>
<div><b>Hash:</b> una fórmula que asigna siempre el mismo grupo a la misma persona, para poder repetir el sorteo.</div>
<div><b>Instrumentación:</b> los eventos que el producto debería registrar para entender por qué la gente se frena.</div>
</div>""",
        unsafe_allow_html=True,
    )

resumen = leer_json("resumen.json")
if resumen is None:
    st.warning("Todavía no hay análisis. Corre `uv run cuadra correr` y después `uv run cuadra analizar`.")
    st.stop()

pestanas = st.tabs(
    [
        "1 · Informe de la IA", "2 · Embudo", "3 · Comportamiento", "4 · Prioridades",
        "5 · Otros canales", "6 · Experimento", "7 · Negocio", "8 · Calidad y límites",
    ]
)
informe = leer_json("informe_ejecutivo.json") or {}
hechos = {h["id"]: h for h in (leer_json("hechos.json") or [])}


def mostrar_puntos(clave: str) -> None:
    for punto in (informe.get("informe") or {}).get(clave, []):
        fuentes = ", ".join(punto["fuentes"])
        st.markdown(
            f'<div class="punto">{sello(punto["tipo"] if punto["tipo"] != "hecho" else "hecho")}'
            f'{html.escape(punto["texto"])} <small>· fuentes: {html.escape(fuentes)}</small></div>',
            unsafe_allow_html=True,
        )


# 1 · Resumen ejecutivo ---------------------------------------------------------------------------------
with pestanas[0]:
    guia(
        "Un informe que Claude redacta a partir de cifras ya calculadas por Python.",
        "Cada número se comprueba contra los hechos: si Claude escribe uno que no está, el informe se rechaza.",
        "Qué investigar primero y qué experimento lanzar después del correo.",
    )
    estado = informe.get("estado", "sin_informe")
    if estado == "verificado":
        st.success("Informe verificado: todas sus cifras están en los hechos calculados y todas sus fuentes existen.")
    elif estado == "no_verificado":
        st.error("Informe NO verificado: " + "; ".join(informe.get("motivos", [])))
    else:
        st.info("No hay informe: corre `cuadra analizar` con clave o con el caché incluido.")
    if informe.get("informe"):
        st.markdown(sello("ia"), unsafe_allow_html=True)
        izquierda, derecha = st.columns(2)
        preguntas = [
            ("donde_se_pierde", "¿Dónde se pierde más gente?"), ("quien_tiene_dificultades", "¿Qué usuarios tienen más dificultades?"),
            ("mayor_oportunidad", "¿Qué problemas son la mayor oportunidad?"), ("investigar_primero", "¿Qué debería investigar primero Growth?"),
        ]
        for i, (clave, titulo) in enumerate(preguntas):
            with (izquierda if i % 2 == 0 else derecha):
                st.markdown(f"#### {titulo}")
                mostrar_puntos(clave)
        st.divider()
        for clave, titulo in [
            ("que_encontramos", "1. Qué encontramos"), ("que_significa", "2. Qué significa para el negocio"),
            ("evidencia", "3. Qué evidencia lo respalda"), ("hipotesis", "4. Qué hipótesis proponemos"),
            ("experimento", "5. Qué experimento recomendamos"), ("datos_adicionales", "6. Qué datos adicionales necesitamos"),
        ]:
            with st.expander(titulo, expanded=clave == "que_encontramos"):
                mostrar_puntos(clave)
    with st.expander("Los hechos que recibió Claude (todo lo que puede citar)"):
        st.dataframe(pd.DataFrame(list(hechos.values())), hide_index=True, width="stretch")

# 2 · Embudo --------------------------------------------------------------------------------------------
with pestanas[1]:
    guia(
        f"El camino de registro a pago, con abandono por etapa. Solo cohortes maduras: registradas hasta el "
        f"{resumen['fecha_madurez']}, para no contar como pérdida a quien todavía está a tiempo.",
        "Dice dónde se va la gente y en qué grupo la caída es anormal comparada con los demás.",
        "En qué etapa y en qué grupo concentrar el siguiente experimento.",
    )
    etapas = leer_csv("embudo_etapas.csv")
    cifras(
        [
            (f"{resumen['maduras']:,}".replace(",", "."), "personas en cohortes maduras", sello("calculado")),
            (str(resumen["perdidos_en_esa_etapa"]), "se pierden al crear el primer cliente, la etapa con más pérdidas", sello("calculado")),
            (pct(resumen["pct_factura_autonomo"]), f"de los autónomos llega a facturar, frente al {pct(resumen['pct_factura_pyme'])} de las pymes", sello("calculado")),
            (f"{resumen['mayor_oportunidad_personas_extra']:.0f}", "personas más crearían un cliente si orgánico × autónomo convirtiera como el resto", sello("estimacion")),
        ]
    )
    izquierda, derecha = st.columns(2)
    if etapas is not None:
        with izquierda:
            st.markdown(f"**Cuántos llegan a cada etapa** {sello('calculado')}", unsafe_allow_html=True)
            etapas["Etapa"] = etapas.etapa.map(NOMBRE_ETAPA)
            etapas["etiqueta"] = [
                f"{n}  ·  pierde {pct(a)} de la anterior" if i else f"{n}"
                for i, (n, a) in enumerate(zip(etapas.llegan, etapas.abandono))
            ]
            barras(etapas, "Etapa", "llegan", "etiqueta", formato="d", dominio=[0, etapas.llegan.max() * 1.9])
            st.caption("El pago llega hasta 30 días después de facturar: en cohortes recientes esta etapa sale baja. La pestaña Negocio usa la tasa corregida.")
    oportunidades = leer_csv("oportunidades.csv")
    if oportunidades is not None:
        with derecha:
            st.markdown(f"**Cuellos de botella: personas que faltan frente al resto** {sello('estimacion')}", unsafe_allow_html=True)
            top = oportunidades.head(6).copy()
            top["Dónde"] = [
                f"{NOMBRE_CANAL.get(c, c)} · {NOMBRE_SEGMENTO.get(s, s).lower()} → {NOMBRE_ETAPA[e].lower()}"
                for c, s, e in zip(top.canal, top.segmento, top.etapa)
            ]
            top["etiqueta"] = [f"{p:.0f} personas  ·  {pct(c)} vs {pct(r)}" for p, c, r in zip(top.personas_extra, top.conversion, top.referencia_resto)]
            barras(top, "Dónde", "personas_extra", "etiqueta", formato=".0f", color=NARANJA, dominio=[0, top.personas_extra.max() * 2.6])
            st.caption("Supuesto: el grupo convertiría como la mediana de los demás en esa etapa. Mide tamaño de la brecha, no lo que se puede ganar.")
    segmento = leer_csv("embudo_por_segmento.csv")
    canal = leer_csv("embudo_por_canal.csv")
    mes = leer_csv("embudo_por_mes.csv")
    a, b, c = st.columns(3)
    for columna, tabla, campo, nombres, titulo in [
        (a, segmento, "segmento", NOMBRE_SEGMENTO, "Autónomos frente a pymes"),
        (b, canal, "canal", NOMBRE_CANAL, "Por canal de llegada"),
        (c, mes, "mes_registro", {}, "Por mes de registro"),
    ]:
        if tabla is not None:
            with columna:
                st.markdown(f"**{titulo}** · conversión desde la etapa anterior {sello('calculado')}", unsafe_allow_html=True)
                ancha = tabla[tabla.etapa != "registro"].pivot(index=campo, columns="etapa", values="conv_desde_anterior")
                ancha = ancha[[e for e in NOMBRE_ETAPA if e in ancha.columns]].rename(columns=NOMBRE_ETAPA)
                ancha.index = [nombres.get(i, i) for i in ancha.index]
                st.dataframe(ancha.map(pct), width="stretch")
    st.caption("Por mes, la conversión es estable: el problema no es de una campaña o un mes concreto.")

# 3 · Comportamiento ------------------------------------------------------------------------------------
with pestanas[2]:
    guia(
        "Cómo avanzan las personas con los 5 pasos que registra el producto: secuencias, tiempos y cohortes.",
        "Los eventos no tienen clics, sesiones ni errores: se puede ver dónde se paran, no por qué.",
        "Qué eventos instrumentar para poder explicar la fuga (lista al final).",
    )
    secuencias = leer_csv("secuencias.csv")
    detenidos = leer_csv("donde_se_detiene.csv")
    tiempos = leer_csv("tiempo_a_primera_factura.csv")
    ritmo = leer_csv("ritmo_activados_vs_no.csv")
    cohortes = leer_csv("cohortes_semanales.csv")
    izquierda, derecha = st.columns(2)
    if secuencias is not None:
        with izquierda:
            st.markdown(f"**Secuencias de pasos** {sello('calculado')}", unsafe_allow_html=True)
            st.dataframe(secuencias[["secuencia", "personas"]], hide_index=True, width="stretch")
            st.caption(
                f"Todas las secuencias siguen el orden del producto ({'sí' if secuencias.respeta_orden.all() else 'no'}). "
                "Quien activa da siempre exactamente 3 pasos antes: el número de acciones no distingue a nadie."
            )
    if detenidos is not None:
        with derecha:
            st.markdown(f"**Dónde se detiene quien no factura** {sello('calculado')}", unsafe_allow_html=True)
            detenidos["Último paso"] = detenidos.ultimo_paso.map(NOMBRE_ETAPA)
            detenidos["etiqueta"] = [f"{p}  ·  {pct(x)}" for p, x in zip(detenidos.personas, detenidos.pct)]
            barras(detenidos, "Último paso", "personas", "etiqueta", formato="d", dominio=[0, detenidos.personas.max() * 1.8])
    izquierda, derecha = st.columns(2)
    if tiempos is not None:
        with izquierda:
            st.markdown(f"**Días del registro a la primera factura** {sello('calculado')}", unsafe_allow_html=True)
            st.altair_chart(
                alt.Chart(tiempos).mark_bar(color=AZUL, cornerRadiusEnd=3).encode(
                    x=alt.X("dias:O", title="días", axis=alt.Axis(labelAngle=0)), y=alt.Y("personas:Q", title=None),
                    tooltip=["dias", "personas", alt.Tooltip("pct_acumulado:Q", format=".0%", title="acumulado")],
                ).properties(height=220),
                width="stretch",
            )
            st.caption("Nadie tarda más de 8 días. Pasada una semana sin facturar, lo normal es no hacerlo nunca.")
    if ritmo is not None:
        with derecha:
            st.markdown(f"**Ritmo de quien facturó frente a quien no** {sello('calculado')}", unsafe_allow_html=True)
            vista = ritmo.copy()
            vista["pct_mismo_dia"] = vista.pct_mismo_dia.map(pct)
            st.dataframe(vista.rename(columns={"mediana_dias": "mediana de días", "pct_mismo_dia": "mismo día"}), hide_index=True, width="stretch")
            st.caption("Entre quienes crearon un cliente, el ritmo de los pasos previos es casi igual: la velocidad no anticipa quién factura. Es una asociación, no una causa.")
    if cohortes is not None:
        st.markdown(f"**Cohortes semanales: qué parte factura en 14 días** {sello('calculado')}", unsafe_allow_html=True)
        st.altair_chart(
            alt.Chart(cohortes).mark_line(point=True, color=AZUL).encode(
                x=alt.X("semana:T", title="semana de registro"),
                y=alt.Y("pct_factura_14d:Q", title=None, axis=alt.Axis(format=".0%"), scale=alt.Scale(domain=[0, 0.6])),
                tooltip=["semana", "registrados", alt.Tooltip("pct_factura_14d:Q", format=".0%")],
            ).properties(height=220),
            width="stretch",
        )
    st.subheader("Instrumentación recomendada")
    st.markdown(
        "Lo que Cuadra debería empezar a registrar para entender **por qué** se frenan. Nada de esto existe en los datos actuales."
    )
    instrumentacion = leer_csv("instrumentacion_recomendada.csv")
    if instrumentacion is not None:
        st.dataframe(
            instrumentacion.rename(columns={"nombre": "Evento", "descripcion": "Descripción", "propiedades": "Propiedades",
                                            "momento": "Cuándo se captura", "pregunta": "Pregunta de negocio"}),
            hide_index=True, width="stretch",
        )

# 4 · Priorización --------------------------------------------------------------------------------------
with pestanas[3]:
    guia(
        "Cada persona atascada con prioridad alta, media o baja según reglas a la vista: cuánto le falta, hace cuánto se paró y si es la fuga principal.",
        "Ordena el trabajo cuando no se puede atender a todos por igual (revisión, soporte, siguientes canales).",
        "A quién mirar primero. No decide quién recibe correo: eso lo fijó el reparto del experimento.",
    )
    st.warning(
        "Prioridad no es efecto. Que alguien esté cerca de facturar no significa que el contacto le cambie el "
        "resultado. Eso solo lo dirá el experimento, comparando tratamiento y control dentro de cada nivel. "
        "No hay modelo predictivo: entre los atascados solo hubo 5 casos que facturaron solos, demasiado pocos "
        "para entrenar y calibrar uno."
    )
    prioridad = leer_csv("priorizacion.csv")
    if prioridad is not None:
        conteo = prioridad.prioridad.value_counts()
        cifras(
            [
                (str(conteo.get("alta", 0)), "prioridad alta (4 o más puntos)", sello("calculado")),
                (str(conteo.get("media", 0)), "prioridad media (3 puntos)", sello("calculado")),
                (str(conteo.get("baja", 0)), "prioridad baja (2 o menos)", sello("calculado")),
                (str(len(prioridad)), "personas atascadas en total", sello("dato")),
            ]
        )
        st.markdown(
            "**Reglas** · Le falta un solo paso: +3 · le faltan dos: +2 · le faltan tres: +1 · "
            "se paró hace 3 a 14 días: +1 (hipótesis: aún recuerda el producto) · es orgánico × autónomo sin cliente: +1"
        )
        filtro = st.selectbox("Prioridad", ["alta", "media", "baja"])
        parte = prioridad[prioridad.prioridad == filtro]
        st.dataframe(
            parte[["id_contacto", "grupo", "paso", "dias_quieto", "canal", "segmento", "puntos"]].assign(
                paso=lambda t: t.paso.map(NOMBRE_PASO)
            ),
            hide_index=True, width="stretch", height=240,
        )
        elegido = st.selectbox("Ver un caso", parte.id_contacto.tolist()[:200])
        caso = parte[parte.id_contacto == elegido].iloc[0]
        st.markdown(
            f"""**{caso.id_contacto}** · {NOMBRE_PASO[caso.paso]} · {caso.dias_quieto} días quieto · grupo {caso.grupo}

- **Por qué esta prioridad:** {caso.motivos}
- **Qué le falta:** {caso.accion_faltante}
- **Qué podría ayudar** {sello('hipotesis')}: {caso.intervencion_sugerida}
- **Evidencia:** {caso.evidencia}""",
            unsafe_allow_html=True,
        )
        st.caption("La tabla muestra identificadores, no nombres ni correos.")

# 5 · Intervenciones ------------------------------------------------------------------------------------
with pestanas[4]:
    guia(
        "Una intervención por bloqueo y canal: correo, mensaje en la app, guía, checklist, notificación y WhatsApp (prototipo).",
        "El bloqueo decide el mensaje; el código decide quién puede recibirlo. Claude solo redacta.",
        "Qué probar en el siguiente experimento, con contenido ya verificado.",
    )
    plan = leer_csv("plan_intervenciones.csv")
    if plan is not None:
        estados = plan.pivot_table(index="canal", columns="estado", values="id_contacto", aggfunc="count", fill_value=0)
        estados.index = [CANALES[c]["nombre"] for c in estados.index]
        estados.columns = [c.capitalize() for c in estados.columns]
        st.markdown(f"**Quién puede recibir qué, según las reglas del código** {sello('calculado')}", unsafe_allow_html=True)
        st.dataframe(estados, width="stretch")
        st.caption(
            "Activo: solo el correo, que es el tratamiento del experimento en curso. Propuesto: canales listos para el "
            "siguiente experimento (activarlos ahora cambiaría el tratamiento a mitad de medición). Bloqueado: control "
            "(nunca recibe nada) y WhatsApp (el CRM no registra consentimiento). Frecuencia máxima: 1 contacto por semana."
        )
    contenidos = leer_json("contenidos_por_canal.json") or []
    if contenidos:
        st.markdown(f"**Vista previa del contenido** {sello('ia')} · envío simulado, nada sale de aquí", unsafe_allow_html=True)
        a, b = st.columns(2)
        paso = a.selectbox("Bloqueo", list(NOMBRE_PASO), format_func=NOMBRE_PASO.get)
        canales = [c["canal"] for c in contenidos if c["paso"] == paso]
        nombres_canal = {"in_app": "Mensaje en la app", "guia": "Guía contextual", "checklist": "Checklist", "notificacion": "Notificación", "whatsapp": "WhatsApp (prototipo)"}
        canal_elegido = b.selectbox("Canal", canales, format_func=nombres_canal.get)
        fila = next(c for c in contenidos if c["paso"] == paso and c["canal"] == canal_elegido)
        if fila["estado"] == "aprobado":
            st.success(f"Pasó la verificación (rutas válidas, sin instrucciones obsoletas, sin precios ni enlaces, largo del canal). Intentos: {fila['intentos']}.")
        else:
            st.error("En revisión humana: " + "; ".join(fila["motivos"]))
        if canal_elegido == "whatsapp":
            st.warning("Prototipo: bloqueado para todos mientras no exista un consentimiento registrado.")
        contenido = fila.get("contenido")
        if contenido:
            pasos = "".join(f"<li>{html.escape(p).replace('**', '')}</li>" for p in contenido["pasos"])
            st.markdown(
                f"""<div style="border:1px solid #e2e8f0;border-radius:14px;padding:16px 20px;max-width:560px;background:#fff">
<div style="font-weight:700;font-size:1.05rem;color:#0f172a">{html.escape(contenido['titulo'])}</div>
<div style="margin:8px 0;color:#1f2937;line-height:1.55">{html.escape(contenido['cuerpo']).replace('**', '')}</div>
{f'<ol style="margin:6px 0 10px 0;padding-left:20px">{pasos}</ol>' if pasos else ''}
<span style="display:inline-block;background:#2a78d6;color:#fff;border-radius:8px;padding:6px 14px;font-weight:600">{html.escape(contenido['boton'])}</span>
<div style="font-size:0.78rem;color:#64748b;margin-top:10px">Fuente: {html.escape(contenido['articulo_fuente'])}</div></div>""",
                unsafe_allow_html=True,
            )

# 6 · Experimento ---------------------------------------------------------------------------------------
with pestanas[5]:
    salud = leer_json("salud_experimento.json")
    guia(
        "La salud del experimento original: tamaños, reparto, reproducibilidad, equilibrio y la regla de decisión.",
        "Si el reparto está mal, cualquier resultado posterior es engañoso. Se comprueba antes de mirar resultados.",
        "Confiar en el resultado cuando llegue, y saber cómo leerlo.",
    )
    if salud:
        m = salud["metrica_primaria"]
        st.markdown(f"**Métrica primaria:** {m['nombre']}. {m['definicion']} Unidad: {m['unidad']}. **Criterio:** {m['criterio']}")
        reproducible = salud["reproducibilidad"]
        cifras(
            [
                (f"{salud['tamanos']['tratamiento']} / {salud['tamanos']['control']}", "tratamiento / control", sello("calculado")),
                ("sí" if not salud["descuadre"]["alerta"] else "NO", f"reparto dentro de lo esperado (p = {salud['descuadre']['valor_p']:.2f})".replace(".", ","), sello("calculado")),
                (f"{reproducible['coinciden']}/{reproducible['personas']}", "grupos que se recalculan igual con el hash", sello("calculado")),
                (str(len(salud["problemas"])), "problemas de asignación (duplicados, control contaminado, no elegibles)", sello("calculado")),
            ]
        )
        for problema in salud["problemas"]:
            st.error(problema)
        balance = leer_csv("balance.csv")
        if balance is not None:
            st.markdown(f"**Equilibrio entre grupos (diferencia estandarizada)** {sello('calculado')}", unsafe_allow_html=True)
            balance["Característica"] = balance.caracteristica + " = " + balance.valor.astype(str)
            balance["Estado"] = balance.equilibrado.map({True: "Equilibrado", False: "Desequilibrado (|SMD| ≥ 0,1)"})
            st.altair_chart(
                alt.Chart(balance).mark_bar(size=16).encode(
                    y=alt.Y("Característica:N", sort=None, title=None, axis=alt.Axis(labelLimit=260)),
                    x=alt.X("smd:Q", title="SMD (tratamiento − control)", scale=alt.Scale(domain=[-0.3, 0.3])),
                    color=alt.Color("Estado:N", scale=alt.Scale(domain=["Equilibrado", "Desequilibrado (|SMD| ≥ 0,1)"], range=[GRIS, NARANJA]), legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=["Característica", alt.Tooltip("pct_t:Q", format=".3f"), alt.Tooltip("pct_c:Q", format=".3f"), alt.Tooltip("smd:Q", format=".3f")],
                ).properties(height=alt.Step(22)),
                width="stretch",
            )
            if not salud["balance_todo_equilibrado"]:
                st.info(
                    "Por azar, el control tiene más personas sin configurar la empresa. No se toca el reparto (hacerlo "
                    "invalidaría el experimento): se corrige en el análisis, comparando dentro de cada paso y ponderando "
                    "(post-estratificación). La medición por estrato ya existe en `cuadra medir`."
                )
        st.subheader("Resultado observado hasta hoy")
        st.markdown(salud["explicacion_observado"])
        if salud.get("simulado"):
            st.subheader("Demostración con datos simulados")
            st.warning("SIMULADO · Cifras inventadas para mostrar cómo se leerá el resultado. No hay ganador.")
            sim = salud["simulado"]
            st.markdown(sim["explicacion"])
            ajuste = sim["ajustado"]
            st.markdown(
                f"Diferencia ajustada por paso {sello('simulado')}: {ajuste['diferencia_ajustada'] * 100:+.1f} puntos "
                f"(IC 95%: {ajuste['ic95'][0] * 100:+.1f} a {ajuste['ic95'][1] * 100:+.1f}).".replace(".", ","),
                unsafe_allow_html=True,
            )

# 6 · Experimento (continuación): pruebas de confianza del reparto, del flujo original ----------------------
with pestanas[5]:
    st.subheader("¿Se puede confiar en la comparación?")
    flujo = comun.leer_json("resumen.json") or {}
    base_natural, minimo = flujo.get("tasa_base_estimada"), flujo.get("efecto_minimo_detectable")
    aa = comun.leer_json("prueba_aa.json")
    columnas = st.columns(3)
    with columnas[0]:
        natural = "sin historia" if base_natural is None else comun.pct(base_natural, 2)
        comun.bloque(
            f"""<div class="caja"><h4>Sin correo, casi nadie factura</h4><div class="dato"><b>{natural}</b> de los
            atascados factura solo en 14 días ({flujo.get('base_convertidos', 0)} de
            {comun.miles(flujo.get('base_observaciones', 0))} observaciones en {flujo.get('base_cortes', 0)} fechas
            pasadas).</div></div>"""
        )
    with columnas[1]:
        detectable = "no calculable" if minimo is None else comun.decimal(f"{minimo * 100:.1f} puntos")
        comun.bloque(
            f"""<div class="caja"><h4>Efecto mínimo detectable</h4><div class="dato">Con estos grupos, una mejora de
            <b>{detectable}</b> o más se distingue del azar 8 de cada 10 veces (potencia del 80%).</div></div>"""
        )
    with columnas[2]:
        if aa:
            tasas = f"{comun.pct(aa['tasa_t'], 1)} contra {comun.pct(aa['tasa_c'], 1)}"
            valor_p = comun.decimal(f"{aa['valor_p']:.2f}")
            comun.bloque(
                f"""<div class="caja"><h4>Prueba A/A del reparto</h4><div class="dato">El mismo reparto sobre julio y
                agosto, cuando nadie recibió nada: {tasas} (p = {valor_p}).</div></div>"""
            )
    if aa:
        if aa["valor_p"] > config.UMBRAL_AA:
            st.caption(
                "Sin intervención no debería haber diferencia entre los grupos, y la que se ve es la esperable por "
                "azar. Esta prueba ya sirvió una vez: la primera semilla del reparto daba aquí 8,8 puntos de "
                "diferencia (p = 0,01) porque, por azar, dejaba menos autónomos de canal orgánico en un grupo. Se "
                f"cambió con una regla fija, la primera candidata con p > {comun.decimal(str(config.UMBRAL_AA))}, "
                "cubierta por una prueba automática. Límite: compara a todos los registrados de esos meses, no solo "
                "a los atascados."
            )
        else:
            st.warning(
                "La prueba A/A muestra una diferencia que no debería existir entre dos grupos que no recibieron "
                "nada. Antes de enviar, hay que cambiar la semilla del reparto con la regla de `cuadra/config.py`."
            )
    simulado_flujo = comun.leer_json("SIMULADO_resultado_experimento.json")
    if simulado_flujo:
        ic = simulado_flujo["ic95"]
        st.markdown(
            f"**Lectura simulada del flujo** {sello('simulado')}: diferencia de "
            f"{comun.decimal(f'{simulado_flujo['diferencia'] * 100:+.1f}')} puntos, margen de error (IC 95%) de "
            f"{comun.decimal(f'{ic[0] * 100:+.1f}')} a {comun.decimal(f'{ic[1] * 100:+.1f}')} puntos. Regla: si todo el "
            f"margen queda sobre cero, se extiende. Decisión: **{simulado_flujo['decision']}**.",
            unsafe_allow_html=True,
        )
    por_estrato = comun.leer_csv("SIMULADO_resultado_por_estrato.csv")
    if por_estrato is not None:
        with st.expander("Ver el resultado simulado por paso y antigüedad"):
            tabla = por_estrato[["dimension", "valor", "n_t", "conv_t", "n_c", "conv_c", "diferencia", "valor_p"]].copy()
            tabla["diferencia"] = tabla.diferencia.map(lambda d: comun.decimal(f"{d * 100:+.1f} puntos"))
            tabla["valor_p"] = tabla.valor_p.map(lambda p: comun.decimal(f"{p:.3f}"))
            tabla.columns = ["Dimensión", "Valor", "Reciben", "Facturaron", "No reciben", "Facturaron ", "Diferencia", "p"]
            st.dataframe(tabla, hide_index=True, width="stretch")
    equilibrio = comun.leer_csv("equilibrio.csv")
    if equilibrio is not None:
        with st.expander("Ver si los dos grupos se parecen (debe haber cerca del 50% de cada tipo en cada uno)"):
            tabla = equilibrio.assign(
                dimension=equilibrio.dimension.str.capitalize(),
                pct_tratamiento=equilibrio.pct_tratamiento.map(comun.pct),
            )
            tabla.columns = ["Dimensión", "Valor", "Reciben correo", "No reciben", "% que recibe"]
            st.dataframe(tabla, hide_index=True, width="stretch")
    tiempos_pasos = comun.leer_csv("tiempos_entre_pasos.csv")
    if tiempos_pasos is not None:
        with st.expander("Ver los días que pasan entre un paso y el siguiente"):
            tabla = tiempos_pasos.assign(
                desde=tiempos_pasos.desde.map(comun.NOMBRE_PASO), hasta=tiempos_pasos.hasta.map(comun.NOMBRE_PASO)
            )
            tabla.columns = ["Desde", "Hasta", "Personas", "Mediana (días)", "Percentil 90", "Máximo"]
            st.dataframe(tabla, hide_index=True, width="stretch")

# 7 · Negocio -------------------------------------------------------------------------------------------
with pestanas[6]:
    guia(
        "Cómo se conecta la activación con el pago, y escenarios de lo que valdría mejorarla.",
        "Pone tamaño a la oportunidad, separando lo observado de lo supuesto.",
        "Qué hipótesis priorizar y cuánto esfuerzo justifica cada una.",
    )
    conv = leer_csv("conversiones_negocio.csv")
    if conv is not None:
        total = conv[conv.dimension == "total"].iloc[0]
        cifras(
            [
                (pct(total.registro_a_factura), "de los registrados llega a la primera factura", sello("calculado")),
                (pct(total.factura_a_pago), "de quienes facturan termina pagando (cohortes con 45 días para pagar)", sello("calculado")),
                (str(resumen["pagadores_sin_factura"]), "pagadores no han facturado nunca", sello("dato")),
                ("asociación", "facturar y pagar van juntos; no está probado que uno cause el otro", sello("hipotesis")),
            ]
        )
        vista = conv[conv.dimension != "total"].copy()
        vista["valor"] = [NOMBRE_SEGMENTO.get(v, NOMBRE_CANAL.get(v, v)) for v in vista.valor]
        vista["registro → factura"] = vista.registro_a_factura.map(pct)
        vista["factura → pago"] = vista.factura_a_pago.map(pct)
        st.dataframe(vista[["dimension", "valor", "n_maduras", "registro → factura", "factura → pago"]], hide_index=True, width="stretch")
    escenarios = leer_csv("escenarios.csv")
    if escenarios is not None:
        st.markdown(f"**Escenarios** {sello('estimacion')} · si el correo funcionara para los 912 atascados", unsafe_allow_html=True)
        vista = pd.DataFrame(
            {
                "Efecto supuesto": escenarios.efecto_supuesto_pp.map(lambda x: f"+{x:.1f} puntos".replace(".", ",")),
                "Facturas adicionales": escenarios.facturas_adicionales.round(0).astype(int),
                "Pagos adicionales": escenarios.pagos_adicionales.round(0).astype(int),
                "Ingreso mensual adicional": escenarios.ingreso_mensual_adicional_eur.map(lambda x: f"{x:.0f} €"),
            }
        )
        st.dataframe(vista, hide_index=True, width="stretch")
        st.caption(
            "Supuestos: el efecto vale para todos los atascados; la tasa de pago tras facturar es la observada; el ingreso es la "
            "media de los planes pagados. El efecto del medio es el mínimo que el experimento puede detectar. No son ingresos reales."
        )
    hipotesis = leer_json("hipotesis.json") or []
    if hipotesis:
        st.markdown(f"**Hipótesis priorizadas** {sello('hipotesis')}", unsafe_allow_html=True)
        for h in hipotesis:
            with st.expander(f"{h['id']} · {h['hipotesis']}", expanded=h["id"] == "H1"):
                st.markdown(
                    f"- **Evidencia:** {h['evidencia']}\n- **Tamaño:** {h['tamano']}\n- **Confianza:** {h['confianza']}\n"
                    f"- **Experimento:** {h['experimento']}\n- **Dato que falta:** {h['dato_faltante']}"
                )

# 8 · Calidad y límites ---------------------------------------------------------------------------------
with pestanas[7]:
    guia(
        "Qué controles tiene cada pieza y qué no cubre este análisis.",
        "Un evaluador tiene que poder confiar en cada cifra o saber exactamente cuándo no.",
        "Qué falta para pasar de diagnóstico a decisiones con datos propios.",
    )
    st.markdown(
        """**Controles**
- Las cifras las calcula Python; Claude solo redacta. Cada número del informe se compara con los hechos y, si no está, se rechaza.
- Solo se usan datos conocidos el 31 de octubre de 2026; las tasas se calculan en cohortes con tiempo suficiente para convertir o pagar.
- El experimento original no se modifica: el análisis lee la asignación y comprueba que se recalcula igual.
- El control nunca recibe nada, por ningún canal. Nada se envía de verdad.
- Las tablas muestran identificadores, no nombres ni correos. La clave de API no se guarda en ningún archivo de salida.
- Corre sin clave: las respuestas de Claude quedan en `cache/`.

**Límites**
- Los eventos no explican por qué se frena la gente: no hay sesiones, clics ni errores (ver Instrumentación recomendada).
- No hay resultados observados del experimento: todo lo de resultados es demostración simulada.
- La prioridad ordena la atención; no estima el efecto incremental del contacto.
- Sin consentimiento en el CRM, WhatsApp queda bloqueado.
- Las oportunidades y escenarios son estimaciones bajo supuestos explícitos, no ganancias."""
    )
