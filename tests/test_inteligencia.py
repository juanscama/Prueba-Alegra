"""Pruebas de los módulos de inteligencia de Growth (`cuadra analizar`)."""

import shutil
from datetime import date
from hashlib import sha256

import pandas as pd
import pytest

from cuadra import comportamiento, embudo_completo, negocio, priorizacion, salud_experimento
from cuadra.config import DIR_SALIDA
from cuadra.informe import Informe, Punto, SECCIONES, numeros, redactar_informe, verificar_informe
from cuadra.intervenciones import (
    CANALES, Contenido, elegibilidad, plan_intervenciones, redactar_contenidos, respeta_frecuencia,
    verificar_contenido,
)
from cuadra.medicion import comparar


def _asignacion():
    return pd.read_csv(DIR_SALIDA / "asignacion_experimento.csv", dtype={"id_contacto": str})


def _estado():
    return pd.read_csv(DIR_SALIDA / "estado.csv", dtype={"id_contacto": str})


# --- Módulo 1 · embudo completo ---------------------------------------------------------------------

def test_embudo_es_una_cadena_y_cuadra(datos):
    personas = embudo_completo.tabla_personas(datos)
    etapas = embudo_completo.embudo_etapas(personas[personas.madura])
    assert list(etapas.etapa) == embudo_completo.ETAPAS
    assert etapas.llegan.is_monotonic_decreasing
    for i in range(1, len(etapas)):
        assert etapas.perdidos[i] == etapas.llegan[i - 1] - etapas.llegan[i]
        assert etapas.abandono[i] == pytest.approx(1 - etapas.conv_desde_anterior[i])


def test_pago_sin_factura_no_entra_en_la_cadena(datos):
    personas = embudo_completo.tabla_personas(datos)
    etapas = embudo_completo.embudo_etapas(personas).set_index("etapa")
    assert etapas.llegan["pago"] == int((personas.pago & personas.emitio_primera_factura).sum())
    assert embudo_completo.pagadores_sin_factura(personas) == 8


def test_cohortes_maduras_y_sin_datos_futuros(datos):
    personas = embudo_completo.tabla_personas(datos, date(2026, 8, 1))
    assert personas.fecha_registro.max() <= date(2026, 8, 1)
    assert not personas[personas.madura].fecha_registro.gt(date(2026, 7, 18)).any()
    hoy = embudo_completo.tabla_personas(datos)
    # Lo que se sabía el 1 de agosto no puede incluir pasos dados después.
    assert personas.emitio_primera_factura.sum() <= hoy.loc[personas.index].emitio_primera_factura.sum()


def test_la_mayor_oportunidad_es_la_fuga_conocida(datos):
    personas = embudo_completo.tabla_personas(datos)
    tabla = embudo_completo.oportunidades(personas[personas.madura])
    assert (tabla.personas_extra >= 0).all() and "pago" not in set(tabla.etapa)
    assert tabla.iloc[0].grupo == "organico × autonomo" and tabla.iloc[0].etapa == "creo_cliente"
    resumen = embudo_completo.resumen_embudo(datos)
    assert resumen["etapa_con_mas_perdidos"] == "creo_cliente"
    assert resumen["pct_factura_pyme"] > resumen["pct_factura_autonomo"]


# --- Módulo 4 · comportamiento ----------------------------------------------------------------------

def test_secuencias_respetan_el_orden_y_las_acciones_no_distinguen(datos):
    secuencias = comportamiento.secuencias(datos)
    assert secuencias.respeta_orden.all() and secuencias.personas.sum() == 1500
    acciones = comportamiento.acciones_antes_de_activar(datos)
    assert list(acciones.acciones) == [3]


def test_donde_se_detiene_cuenta_a_todos_los_que_no_facturaron(datos):
    detenidos = comportamiento.donde_se_detiene(datos)
    personas = embudo_completo.tabla_personas(datos)
    maduras = personas[personas.madura]
    assert detenidos.personas.sum() == int((~maduras.emitio_primera_factura).sum())
    assert detenidos.pct.sum() == pytest.approx(1)


def test_tiempo_a_factura_y_cohortes(datos):
    tiempos = comportamiento.tiempo_a_primera_factura(datos)
    assert tiempos.dias.max() == 8 and tiempos.pct_acumulado.iloc[-1] == pytest.approx(1)
    cohortes = comportamiento.cohortes_semanales(datos)
    assert cohortes.registrados.sum() == 1355
    assert cohortes.pct_factura_14d.between(0, 1).all()


def test_instrumentacion_recomendada_completa():
    campos = {"nombre", "descripcion", "propiedades", "momento", "pregunta"}
    assert len(comportamiento.INSTRUMENTACION_RECOMENDADA) >= 5
    for evento in comportamiento.INSTRUMENTACION_RECOMENDADA:
        assert set(evento) == campos and all(evento.values())


# --- Módulo 5 · salud del experimento ---------------------------------------------------------------

def test_descuadre_de_reparto():
    assert not salud_experimento.descuadre_de_reparto(457, 455)["alerta"]
    assert salud_experimento.descuadre_de_reparto(600, 400)["alerta"]


def test_reproducibilidad_detecta_un_grupo_alterado():
    asignacion = _asignacion()
    assert salud_experimento.reproducibilidad(asignacion)["coinciden"] == len(asignacion)
    alterada = asignacion.copy()
    alterada.loc[0, "grupo"] = "control" if alterada.loc[0, "grupo"] == "tratamiento" else "tratamiento"
    resultado = salud_experimento.reproducibilidad(alterada)
    assert resultado["distintos"] == [alterada.loc[0, "id_contacto"]]


def test_problemas_detecta_contaminacion_del_control():
    asignacion = _asignacion()
    bandeja = pd.read_csv(DIR_SALIDA / "bandeja_salida.csv", dtype=str)
    assert salud_experimento.problemas_de_asignacion(asignacion, bandeja, _estado()) == []
    un_control = asignacion[asignacion.grupo == "control"].id_contacto.iloc[0]
    contaminada = pd.concat([bandeja, pd.DataFrame({"id_contacto": [un_control]})])
    problemas = salud_experimento.problemas_de_asignacion(asignacion, contaminada)
    assert any("contaminación" in p for p in problemas)


def test_balance_senala_el_desequilibrio_casual_por_paso(datos):
    tabla = salud_experimento.balance(_asignacion(), datos.contactos)
    paso = tabla[(tabla.caracteristica == "paso") & (tabla.valor == "sin_configurar")].iloc[0]
    assert not paso.equilibrado
    assert tabla[tabla.caracteristica == "segmento"].equilibrado.all()


def test_explicar_no_declara_ganador_con_simulados():
    simulado = comparar(457, 100, 455, 10, simulado=True)
    texto = salud_experimento.explicar(simulado)
    assert texto.startswith("DEMOSTRACIÓN") and "No hay ganador" in texto and "se extiende" not in texto
    assert "se extiende" in salud_experimento.explicar(comparar(457, 100, 455, 10))
    assert "Todavía no hay resultados" in salud_experimento.explicar(None)


def test_ajuste_por_estratos_corrige_la_mezcla():
    # Mismo efecto (+10 puntos) en cada estrato, pero mezclas distintas: la diferencia cruda engaña.
    estratos = pd.DataFrame(
        [
            {"dimension": "paso", "valor": "a", "n_t": 100, "tasa_t": 0.5, "n_c": 300, "tasa_c": 0.4},
            {"dimension": "paso", "valor": "b", "n_t": 300, "tasa_t": 0.2, "n_c": 100, "tasa_c": 0.1},
        ]
    )
    ajuste = salud_experimento.ajuste_por_estratos(estratos)
    assert ajuste["diferencia_ajustada"] == pytest.approx(0.10)
    assert ajuste["ic95"][0] < 0.10 < ajuste["ic95"][1]


# --- Módulo 2 · priorización ------------------------------------------------------------------------

def test_niveles():
    assert [priorizacion.nivel(p) for p in (5, 4, 3, 2, 1)] == ["alta", "alta", "media", "baja", "baja"]


def test_priorizar_no_toca_la_asignacion_y_explica_cada_caso(datos):
    asignacion = _asignacion()
    copia = asignacion.copy()
    tabla = priorizacion.priorizar(_estado(), datos.contactos, asignacion, priorizacion.evidencia_por_paso(datos))
    pd.testing.assert_frame_equal(asignacion, copia)
    assert len(tabla) == len(asignacion)
    grupos = asignacion.set_index("id_contacto").grupo
    assert (tabla.set_index("id_contacto").grupo == grupos.reindex(tabla.id_contacto)).all()
    assert tabla.motivos.str.len().gt(0).all() and tabla.evidencia.str.contains("hipótesis").all()
    fuga = tabla[(tabla.canal == "organico") & (tabla.segmento == "autonomo") & (tabla.paso == "sin_cliente")]
    assert fuga.motivos.str.contains("fuga principal").all()


def test_la_evidencia_solo_usa_cohortes_maduras(datos):
    evidencia = priorizacion.evidencia_por_paso(datos)
    assert evidencia["sin_configurar"] < evidencia["sin_cliente"] < evidencia["sin_factura"]


# --- Módulo 3 · intervenciones ----------------------------------------------------------------------

def test_elegibilidad_la_decide_el_codigo():
    control = {"grupo": "control", "email": "a@b.example"}
    assert all(elegibilidad(control, c)[0] == "bloqueado" for c in CANALES)
    tratamiento = {"grupo": "tratamiento", "email": "a@b.example"}
    assert elegibilidad(tratamiento, "correo")[0] == "activo"
    assert elegibilidad(tratamiento, "whatsapp")[0] == "bloqueado"
    assert elegibilidad({**tratamiento, "consentimiento_whatsapp": True}, "whatsapp")[0] == "propuesto"
    assert elegibilidad(tratamiento, "in_app")[0] == "propuesto"
    assert elegibilidad({"grupo": "tratamiento", "email": ""}, "correo")[0] == "bloqueado"


def test_plan_no_activa_nada_fuera_del_correo_del_tratamiento(datos):
    tabla = priorizacion.priorizar(_estado(), datos.contactos, _asignacion(), priorizacion.evidencia_por_paso(datos))
    plan = plan_intervenciones(tabla, datos.contactos)
    activos = plan[plan.estado == "activo"]
    assert set(activos.canal) == {"correo"} and set(activos.grupo) == {"tratamiento"}
    assert (plan[plan.grupo == "control"].estado == "bloqueado").all()


def test_frecuencia():
    historial = pd.DataFrame({"id_contacto": ["C1"], "fecha": ["2026-10-30"]})
    assert not respeta_frecuencia(historial, "C1", date(2026, 10, 31))
    assert respeta_frecuencia(historial, "C1", date(2026, 11, 8))
    assert respeta_frecuencia(historial, "C2", date(2026, 10, 31))


def _contenido(**cambios):
    datos = dict(titulo="Crea tu primer cliente", cuerpo="Entra en **Ventas > Facturas** y pulsa Nueva factura.",
                 pasos=[], boton="Empezar", articulo_fuente="01-crear-tu-primera-factura.md")
    return Contenido(**{**datos, **cambios})


def test_verificar_contenido(base_de_prueba):
    assert verificar_contenido(_contenido(), "guia", base_de_prueba) == []
    malos = {
        "ruta": _contenido(cuerpo="Entra en **Ajustes > Clientes**."),
        "obsoleta": _contenido(cuerpo="Pulsa **Más acciones > Enviar por correo**."),
        "promo": _contenido(cuerpo="Hoy con un 20% de descuento."),
        "plan": _contenido(cuerpo="Prueba las facturas recurrentes."),
        "enlace": _contenido(cuerpo="Mira https://cuadra.example"),
        "largo": _contenido(cuerpo="a" * 200),
    }
    for clave, contenido in malos.items():
        assert verificar_contenido(contenido, "notificacion", base_de_prueba), clave


class ModeloContenidos:
    def __init__(self, primero_malo=False):
        self.primero_malo, self.llamadas = primero_malo, 0

    def pedir(self, *, tarea, sistema, usuario, esquema):
        self.llamadas += 1
        if self.primero_malo and "revision_anterior" not in usuario:
            return _contenido(cuerpo="Con un 50% de descuento.")
        return _contenido()


def test_redactar_contenidos_reintenta_y_aprueba(base_de_prueba):
    modelo = ModeloContenidos(primero_malo=True)
    resultados = redactar_contenidos(base_de_prueba, modelo)
    assert len(resultados) == 15 and all(r["estado"] == "aprobado" and r["intentos"] == 2 for r in resultados)


def test_redactar_contenidos_sin_cache_queda_en_revision(base_de_prueba):
    from cuadra.modelo import SinCache

    class SinNada:
        def pedir(self, **_):
            raise SinCache("no")

    assert all(r["estado"] == "revision" for r in redactar_contenidos(base_de_prueba, SinNada()))


# --- Módulo 6 · negocio e informe -------------------------------------------------------------------

def test_escenarios_son_estimaciones_explicitas():
    tabla = negocio.escenarios(1000, 0.5, 20.0, [0.02])
    fila = tabla.iloc[0]
    assert fila.facturas_adicionales == pytest.approx(20) and fila.pagos_adicionales == pytest.approx(10)
    assert fila.ingreso_mensual_adicional_eur == pytest.approx(200) and "no resultado" in fila.tipo


def test_factura_a_pago_solo_con_cohortes_que_tuvieron_tiempo_de_pagar(datos):
    tabla = negocio.conversiones(datos)
    total = tabla[tabla.dimension == "total"].iloc[0]
    personas = embudo_completo.tabla_personas(datos)
    sesgada = personas[personas.madura & personas.emitio_primera_factura].pago.mean()
    assert total.factura_a_pago > sesgada  # con cohortes recientes la tasa sale más baja


HECHOS = [{"id": "F1", "texto": "375 personas no crearon un cliente (abandono del 35%). Base: 0,15%."}]


def _informe(texto, fuentes=("F1",)):
    punto = Punto(texto=texto, tipo="hecho", fuentes=list(fuentes))
    return Informe(**{clave: [punto] for clave, _ in SECCIONES})


def test_verificar_informe_rechaza_cifras_inventadas_y_fuentes_falsas():
    assert verificar_informe(_informe("375 personas, un 35%, solo el 0,15%"), HECHOS) == []
    assert verificar_informe(_informe("Son 400 personas"), HECHOS)
    assert verificar_informe(_informe("Un 0,2%"), HECHOS)
    assert verificar_informe(_informe("375 personas", fuentes=("F9",)), HECHOS)
    assert numeros("0,150 y 35") == {"0.15", "35"}


def test_redactar_informe_reintenta_una_vez():
    class Modelo:
        def __init__(self):
            self.usuarios = []

        def pedir(self, *, tarea, sistema, usuario, esquema):
            self.usuarios.append(usuario)
            return _informe("Son 999 personas" if len(self.usuarios) == 1 else "Son 375 personas")

    modelo = Modelo()
    resultado = redactar_informe(HECHOS, modelo)
    assert resultado["estado"] == "verificado" and resultado["intentos"] == 2
    assert "999" in modelo.usuarios[1]


# --- De punta a punta -------------------------------------------------------------------------------

def _huella(ruta):
    return sha256(ruta.read_bytes()).hexdigest()


def test_analizar_desde_cache_sin_tocar_el_experimento(tmp_path):
    from cuadra.inteligencia import analizar

    for archivo in DIR_SALIDA.iterdir():
        if archivo.is_file():
            shutil.copy(archivo, tmp_path / archivo.name)
    antes = _huella(tmp_path / "asignacion_experimento.csv")
    resumen = analizar(modo="repeticion", dir_salida=tmp_path)
    assert _huella(tmp_path / "asignacion_experimento.csv") == antes
    assert resumen["llamadas_reales"] == 0 and resumen["experimento_problemas"] == 0
    assert resumen["informe"] == "verificado" and resumen["contenidos_aprobados"] == 15
    assert (tmp_path / "inteligencia" / "priorizacion.csv").is_file()


def test_analizar_sin_salida_avisa(tmp_path):
    from cuadra.inteligencia import FaltaSalida, analizar

    with pytest.raises(FaltaSalida):
        analizar(modo="repeticion", dir_salida=tmp_path)


# --- Panel ------------------------------------------------------------------------------------------

PAGINA = str(DIR_SALIDA.parent / "panel" / "pages" / "2_Inteligencia_de_Growth.py")


def test_pagina_de_inteligencia():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(PAGINA, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == [
        "1 · Resumen ejecutivo", "2 · Embudo", "3 · Comportamiento", "4 · Priorización",
        "5 · Intervenciones", "6 · Experimento", "7 · Negocio", "8 · Calidad y límites",
    ]
    assert any("Informe verificado" in s.value for s in at.success)
    assert any("SIMULADO" in w.value and "No hay ganador" in w.value for w in at.warning)
    # Ningún correo ni nombre de persona en lo que muestra la página.
    textos = [m.value for m in at.markdown] + [str(d.value) for d in at.dataframe]
    assert not any("correo.example" in t for t in textos)


def test_pagina_sin_analisis(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("CUADRA_DIR_SALIDA", str(tmp_path))
    at = AppTest.from_file(PAGINA, default_timeout=60).run()
    assert not at.exception and "cuadra analizar" in at.warning[0].value
