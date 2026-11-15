"""Resumen: la historia completa en una página que se lee de arriba abajo, sin saber de datos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from comun import (  # noqa: E402
    AZUL, GRIS, NARANJA, NOMBRE_CANAL, NOMBRE_PASO, NOMBRE_SEGMENTO, TINTA,
    bloque, capitulo, correo_html, decimal, dir_inteligencia, enlace, estilos, leer_csv, leer_json, miles, pct,
)
from cuadra import config  # noqa: E402

ACCION = {
    "configuro_empresa": "configurar la empresa",
    "creo_cliente": "crear el primer cliente",
    "emitio_primera_factura": "emitir la factura",
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def fecha_larga(iso: str) -> str:
    anio, mes, dia = (int(x) for x in iso.split("-"))
    return f"{dia} de {MESES[mes - 1]} de {anio}"


estilos()
resumen = leer_json("resumen.json")

if resumen is None:
    st.title("Cuadra · De registrarse a facturar")
    st.warning(
        "Todavía no hay resultados que mostrar. Ejecuta `uv run cuadra correr` en la carpeta del "
        "proyecto y vuelve a abrir el panel."
    )
    st.stop()

embudo = leer_csv("embudo.csv")
cruce = leer_csv("embudo_por_canal_segmento.csv")
base_json = leer_json("base_vigente.json") or {}
articulos = base_json.get("articulos", [])
desactualizados = sum(1 for a in articulos if not a.get("vigente", True))
total_modelos = resumen["variantes_aprobadas"] + resumen["variantes_en_revision"]

# --- Portada --------------------------------------------------------------------------------------------
bloque(
    f"""
<div class="portada">
  <div class="marca">Cuadra · Growth con IA</div>
  <h1>De registrarse a facturar</h1>
  <p><b>{miles(resumen['elegibles'])} personas</b> se registraron en Cuadra y nunca emitieron su primera factura.
  Este proyecto detecta en qué paso se quedó cada una, le escribe con IA un correo con la instrucción exacta que
  le falta y deja a la otra mitad sin correo para poder <b>demostrar con números</b> si funcionó.</p>
  <div class="pie">Datos del caso al {fecha_larga(resumen['fecha'])} · correos redactados con Claude y revisados antes de salir</div>
</div>
<div class="tarjetas">
  <div class="tarjeta"><div class="cifra">{miles(resumen['elegibles'])}</div>
    <div class="titulo">personas atascadas</div>
    <div class="nota">Llevan {config.DIAS_ATASCADO} días o más sin avanzar hacia su primera factura.</div></div>
  <div class="tarjeta destacada"><div class="cifra">{miles(resumen['correos_en_bandeja'])}</div>
    <div class="titulo">correos listos para enviar</div>
    <div class="nota">Uno por persona, según el paso en que se quedó.</div></div>
  <div class="tarjeta"><div class="cifra">{resumen['variantes_aprobadas']} de {total_modelos}</div>
    <div class="titulo">correos aprobados</div>
    <div class="nota">Todos pasaron las reglas automáticas y una segunda revisión.</div></div>
  <div class="tarjeta"><div class="cifra">{miles(resumen['control'])}</div>
    <div class="titulo">personas de comparación</div>
    <div class="nota">No reciben nada. Sirven para medir si el correo marca la diferencia.</div></div>
</div>
"""
)

enlace("vistas/automatizacion.py", "Verlo funcionar: correr la automatización desde un botón", ":material/play_circle:")

# --- 1 · El problema ------------------------------------------------------------------------------------
capitulo(
    "1 · El problema",
    "La mayoría se registra, pero no llega a facturar",
    "Emitir la primera factura es el momento en que alguien empieza a usar Cuadra de verdad. Ahí se pierde "
    "mucha gente.",
)
if embudo is not None:
    camino = embudo[embudo.paso.isin(["registro", "configuro_empresa", "creo_cliente", "emitio_primera_factura"])].copy()
    camino = camino.reset_index(drop=True)
    perdidas = camino.contactos.shift(1) - camino.contactos
    mayor = int(perdidas.idxmax())
    de_cada_100 = round(camino.pct_registro.iloc[-1] * 100)
    bloque(
        f"""<div class="idea">De cada 100 personas que se registran, <b>solo {de_cada_100} emiten su primera
        factura</b>. El tropiezo más grande es <b>{ACCION[camino.paso[mayor]]}</b>: ahí se quedan
        {miles(perdidas[mayor])} personas.</div>"""
    )

izquierda, derecha = st.columns(2, gap="large")
if embudo is not None:
    with izquierda:
        st.markdown(f"**De {miles(camino.contactos.iloc[0])} personas registradas, cuántas llegan a cada paso**")
        camino["Paso"] = camino.paso.map(NOMBRE_PASO)
        camino["etiqueta"] = [f"{miles(c)}  ·  {pct(p)}" for c, p in zip(camino.contactos, camino.pct_registro)]
        base = alt.Chart(camino).encode(
            y=alt.Y("Paso:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=13)),
            x=alt.X("contactos:Q", title=None, scale=alt.Scale(domain=[0, camino.contactos.max() * 1.3]), axis=None),
            tooltip=[alt.Tooltip("Paso:N"), alt.Tooltip("contactos:Q", title="Personas")],
        )
        st.altair_chart(
            (
                base.mark_bar(color=AZUL, cornerRadiusEnd=4, size=26)
                + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
            ).properties(height=alt.Step(48)).configure_view(strokeWidth=0),
            width="stretch",
        )
if cruce is not None:
    with derecha:
        peor = cruce.loc[cruce.pct_config_a_cliente.idxmin()]
        llegada = {"organico": "llegaron por su cuenta", "contador": "llegaron por su contador",
                   "pago": "llegaron por anuncios", "referido": "llegaron recomendados"}
        nombre_peor = (
            f"{NOMBRE_SEGMENTO.get(peor.segmento, peor.segmento).capitalize()} que "
            f"{llegada.get(peor.canal, NOMBRE_CANAL.get(peor.canal, peor.canal))}"
        )
        resto = cruce.drop(peor.name)
        st.markdown("**Quién se queda en ese paso: de cada 10 que configuran su empresa, cuántos crean un cliente**")
        tabla = pd.DataFrame(
            {
                "Grupo": [nombre_peor, "El resto de usuarios"],
                "tasa": [peor.pct_config_a_cliente, resto.pct_config_a_cliente.median()],
            }
        )
        tabla["etiqueta"] = [f"{decimal(f'{t * 10:.1f}')} de cada 10" for t in tabla.tasa]
        base = alt.Chart(tabla).encode(
            y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13)),
            x=alt.X("tasa:Q", title=None, scale=alt.Scale(domain=[0, 1.35]), axis=None),
        )
        st.altair_chart(
            (
                base.mark_bar(cornerRadiusEnd=4, size=30).encode(
                    color=alt.Color("Grupo:N", legend=None, sort=None,
                                    scale=alt.Scale(domain=list(tabla.Grupo), range=[NARANJA, GRIS]))
                )
                + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
            ).properties(height=alt.Step(60)).configure_view(strokeWidth=0),
            width="stretch",
        )
        st.caption(
            f"Son {miles(peor.n)} personas. Los datos muestran dónde se frenan, no por qué: una hipótesis es que no "
            "saben qué datos fiscales pedirle a su cliente."
        )

# --- 2 · La solución ------------------------------------------------------------------------------------
capitulo(
    "2 · La solución",
    "Un correo a la medida de cada persona, escrito por IA y revisado",
    "El flujo corre solo, de principio a fin. La IA escribe; el programa decide a quién, revisa y mide.",
)
bloque(
    f"""
<div class="pasos">
  <div class="paso"><span class="n">1</span><span class="t">Encuentra a los atascados</span>
    <div class="d">Revisa a los {miles(embudo.contactos.iloc[0]) if embudo is not None else ''} registrados y anota en qué paso
    se quedó cada uno y hace cuántos días.</div><span class="quien codigo">LO HACE EL PROGRAMA</span></div>
  <div class="paso"><span class="n">2</span><span class="t">Pone al día las instrucciones</span>
    <div class="d">Compara los artículos de ayuda con los cambios recientes del producto. Encontró
    {desactualizados} artículo{'s' if desactualizados != 1 else ''} con pasos que ya no existen.</div>
    <span class="quien ia">LO HACE LA IA</span></div>
  <div class="paso"><span class="n">3</span><span class="t">Escribe y revisa cada correo</span>
    <div class="d">Un correo por paso pendiente, oficio y antigüedad. Reglas automáticas y una segunda IA lo
    revisan; si falla dos veces, lo ve una persona.</div><span class="quien ia">LO HACE LA IA</span></div>
  <div class="paso"><span class="n">4</span><span class="t">Reparte y mide</span>
    <div class="d">Sortea quién recibe correo y quién no. A los {config.VENTANA_DIAS} días compara cuántos
    facturaron en cada grupo.</div><span class="quien codigo">LO HACE EL PROGRAMA</span></div>
</div>
"""
)

bandeja = leer_csv("bandeja_salida.csv")
if bandeja is not None and not bandeja.empty:
    ejemplo = bandeja[bandeja.paso == "sin_cliente"]
    fila = (ejemplo if not ejemplo.empty else bandeja).iloc[0]
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.markdown(f"**Un ejemplo real de la bandeja: {fila.nombre}, que no ha creado su primer cliente**")
        bloque(correo_html(fila.email, fila.asunto, fila.cuerpo))
    with derecha:
        bloque(
            f"""<div class="caja"><h4>Por qué este correo funciona mejor que uno genérico</h4>
            <div class="dato">Le pide <b>un solo paso</b>: justo el que le falta.</div>
            <div class="dato">Usa un ejemplo de <b>su oficio</b>, no un texto para todos.</div>
            <div class="dato">Las instrucciones salen de la <b>ayuda actualizada</b>: no lo manda a un botón que ya
            no existe.</div>
            <div class="dato">No promete funciones de pago, ni precios, ni descuentos.</div></div>"""
        )
        enlace("vistas/correos.py", "Ver los correos de las demás personas", ":material/mail:")

# --- 3 · Cómo sabremos si funciona ------------------------------------------------------------------------
capitulo(
    "3 · La prueba",
    "¿Cómo sabremos si funcionó?",
    "Si solo enviamos correos, nunca sabremos si la gente habría facturado igual. Por eso el flujo compara.",
)
bloque(
    f"""
<div class="grupos">
  <div class="grupo t"><div class="cifra">{miles(resumen['tratamiento'])}</div>
    <div class="titulo">reciben el correo</div>
    <div class="nota">Elegidos por sorteo entre los atascados.</div></div>
  <div class="grupo c"><div class="cifra">{miles(resumen['control'])}</div>
    <div class="titulo">no reciben nada</div>
    <div class="nota">Son el punto de comparación: muestran qué pasa sin correo.</div></div>
</div>
<div class="linea">
  <div class="hito"><div class="cuando">Hoy</div><div class="que">Se sortean los dos grupos y la bandeja queda
    lista para enviar.</div></div>
  <div class="hito"><div class="cuando">En {config.VENTANA_DIAS} días</div><div class="que">Se cuenta quién emitió
    su primera factura en cada grupo.</div></div>
  <div class="hito"><div class="cuando">Decisión</div><div class="que">Si el grupo con correo factura claramente más,
    se envía a todos. Si no, se reescribe el mensaje. La regla está fijada desde hoy.</div></div>
</div>
"""
)

simulado = leer_json("SIMULADO_resultado_experimento.json")
base_natural = resumen.get("tasa_base_estimada")
if simulado is not None:
    st.warning(
        "SIMULADO · Todavía no se ha enviado ningún correo, así que no hay resultado real. Este ejemplo usa datos "
        "inventados solo para mostrar cómo se leerá la respuesta."
    )
    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        tasa_t, tasa_c = simulado["tasa_t"], simulado["tasa_c"]
        tabla = pd.DataFrame(
            {
                "Grupo": ["Recibe correo", "No recibe"],
                "tasa": [tasa_t, tasa_c],
                "etiqueta": [
                    f"{pct(tasa_t, 1)}  ·  {simulado['conv_t']} de {simulado['n_t']}",
                    f"{pct(tasa_c, 1)}  ·  {simulado['conv_c']} de {simulado['n_c']}",
                ],
            }
        )
        base = alt.Chart(tabla).encode(
            y=alt.Y("Grupo:N", sort=None, title=None, axis=alt.Axis(labelFontSize=13)),
            x=alt.X("tasa:Q", title=None, axis=None, scale=alt.Scale(domain=[0, max(tasa_t, tasa_c, 0.01) * 1.7])),
        )
        st.markdown(f"**Ejemplo inventado: qué parte emitió su primera factura en {config.VENTANA_DIAS} días**")
        st.altair_chart(
            (
                base.mark_bar(cornerRadiusEnd=4, size=30).encode(
                    color=alt.Color("Grupo:N", legend=None, sort=None,
                                    scale=alt.Scale(domain=["Recibe correo", "No recibe"], range=[AZUL, NARANJA]))
                )
                + base.mark_text(align="left", dx=8, color=TINTA, fontSize=13).encode(text="etiqueta:N")
            ).properties(height=alt.Step(56)).configure_view(strokeWidth=0),
            width="stretch",
        )
    with derecha:
        natural = "" if base_natural is None else (
            f"<div class='dato'>Dato real: sin correo, solo <b>{pct(base_natural, 2)}</b> de los atascados factura "
            f"por su cuenta. Casi nadie vuelve solo.</div>"
        )
        bloque(
            f"""<div class="caja"><h4>Cómo se lee</h4>
            <div class="dato">En este ejemplo, el grupo con correo factura
            <b>{decimal(f'{simulado["diferencia"] * 100:.1f}')} puntos más</b>.</div>
            <div class="dato">La diferencia es demasiado grande para ser casualidad, así que la decisión sería
            <b>enviar el correo a todos</b>.</div>{natural}</div>"""
        )

# --- 4 · Cuánto podría valer --------------------------------------------------------------------------------
escenarios = leer_csv("escenarios.csv", dir_inteligencia())
if escenarios is not None and len(escenarios) >= 3:
    capitulo(
        "4 · El valor",
        "¿Cuánto podría valer?",
        f"Tres escenarios si el correo funciona para los {miles(escenarios.personas_objetivo.iloc[0])} atascados. "
        "Son estimaciones con supuestos a la vista, no ingresos reales.",
    )
    nombres = [
        ("Prudente", "La mitad de lo que el experimento puede detectar."),
        ("Mínimo medible", "La mejora más pequeña que el experimento distingue de la casualidad."),
        ("Optimista", "Dos veces y media el mínimo medible."),
    ]
    tarjetas = ""
    for (nombre, explicacion), (_, fila) in zip(nombres, escenarios.head(3).iterrows()):
        clase = "tarjeta destacada" if nombre == "Mínimo medible" else "tarjeta"
        tarjetas += (
            f'<div class="{clase}"><div class="titulo">{nombre} · +{decimal(f"{fila.efecto_supuesto_pp:.1f}")} puntos</div>'
            f'<div class="cifra">{round(fila.facturas_adicionales)}</div>'
            f'<div class="titulo">personas más emitiendo su primera factura</div>'
            f'<div class="nota">De ellas, unas {round(fila.pagos_adicionales)} pasarían a pagar: cerca de '
            f'{round(fila.ingreso_mensual_adicional_eur)} € más al mes. {explicacion}</div></div>'
        )
    bloque(f'<div class="tarjetas tres">{tarjetas}</div>')
    st.caption(
        "Supuestos: la mejora vale para todos los atascados, la proporción que paga después de facturar es la "
        "observada en el caso y el ingreso es la media de los planes de pago. El valor real crece con cada nueva "
        "camada de registros, porque el flujo se repite cada semana."
    )

    hipotesis = leer_json("hipotesis.json", dir_inteligencia()) or []
    if hipotesis:
        bloque(
            f"""<div class="idea"><b>Siguiente paso recomendado:</b> {hipotesis[0]['hipotesis']} Es la mayor
            oportunidad que muestran los datos y se puede probar con el mismo método de comparación.</div>"""
        )

# --- 5 · Por qué confiar y qué falta ----------------------------------------------------------------------
capitulo(
    "5 · La letra pequeña",
    "Por qué se puede confiar y qué no hace todavía",
    "Lo que garantiza la calidad y los límites, dicho sin rodeos.",
)
aa = leer_json("prueba_aa.json")
aa_texto = (
    "<div>El sorteo se comprobó con datos de meses anteriores: sin correo, los dos grupos se comportan igual.</div>"
    if aa and aa["valor_p"] > config.UMBRAL_AA else ""
)
izquierda, derecha = st.columns(2, gap="large")
with izquierda:
    st.markdown("**Controles**")
    bloque(
        f"""<div class="confianza" style="grid-template-columns:1fr">
        <div>Las cifras las calcula el programa. La IA solo redacta, y si escribe un número que no existe, el texto
        se rechaza.</div>
        <div>Ningún correo sale sin pasar las reglas automáticas y una segunda revisión con IA.</div>
        <div>Las personas de comparación no reciben nada por ningún canal.</div>
        {aa_texto}
        <div>Funciona sin conexión a la IA: las respuestas quedan guardadas y el resultado se puede repetir.</div>
        </div>"""
    )
with derecha:
    st.markdown("**Límites**")
    bloque(
        """<div class="confianza limites" style="grid-template-columns:1fr">
        <div>No envía correos de verdad: las direcciones del caso son ficticias. Deja la bandeja lista.</div>
        <div>El efecto real se conocerá 14 días después del primer envío; lo de arriba es un ejemplo.</div>
        <div>Los datos dicen dónde se frena la gente, no por qué. Hace falta medir más cosas en el producto.</div>
        <div>En producción, antes de escribir a nadie, hacen falta su permiso y un enlace para darse de baja.</div>
        <div>Los datos del caso son sintéticos.</div>
        </div>"""
    )

st.divider()
columnas = st.columns(3)
with columnas[0]:
    enlace("vistas/automatizacion.py", "Correr la automatización", ":material/play_circle:")
with columnas[1]:
    enlace("vistas/correos.py", "Ver los correos, uno por uno", ":material/mail:")
with columnas[2]:
    enlace("vistas/detalle.py", "Ver el análisis completo (detalle técnico)", ":material/analytics:")
