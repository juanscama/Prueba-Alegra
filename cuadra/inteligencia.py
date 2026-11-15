"""`cuadra analizar`: los módulos de inteligencia de Growth sobre lo que dejó `cuadra correr`.

Lee la salida del flujo (estado, asignación, bandeja, base vigente) sin modificarla y escribe todo en
salida/inteligencia/. Corre sin clave desde cache/, como el flujo.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from cuadra import comportamiento, embudo_completo, negocio, priorizacion, salud_experimento
from cuadra.config import DIR_CACHE, DIR_INTELIGENCIA_NOMBRE, DIR_SALIDA, FECHA_CORRIDA
from cuadra.conocimiento import BaseVigente
from cuadra.informe import redactar_informe
from cuadra.ingesta import cargar
from cuadra.intervenciones import plan_intervenciones, redactar_contenidos
from cuadra.medicion import ResultadoExperimento, medir
from cuadra.modelo import Modelo

NECESARIOS = ["estado.csv", "asignacion_experimento.csv", "bandeja_salida.csv", "resumen.json"]


class FaltaSalida(FileNotFoundError):
    """No está la salida de `cuadra correr`."""


def _csv(tabla: pd.DataFrame, ruta: Path) -> None:
    tabla.to_csv(ruta, index=False, lineterminator="\n", encoding="utf-8")


def _json(objeto, ruta: Path) -> None:
    ruta.write_text(json.dumps(objeto, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _pct(x: float, decimales: int = 0) -> str:
    return f"{x * 100:.{decimales}f}%".replace(".", ",")


def _hechos(res_embudo, conv, salud, base_resumen, prioridades, esc, hip, detenidos) -> list[dict]:
    """Los hechos que recibe Claude, ya formateados como se deben citar. Cada uno marca su naturaleza."""
    total = conv[conv.dimension == "total"].iloc[0]
    hechos = [
        {"id": "F1", "tipo": "observado", "texto": f"{res_embudo['registrados']} personas registradas de julio a octubre; {res_embudo['maduras']} con al menos 14 días desde el registro (cohortes maduras)."},
        {"id": "F2", "tipo": "observado", "texto": f"La etapa con más personas perdidas es crear el primer cliente: {res_embudo['perdidos_en_esa_etapa']} personas que configuraron su empresa no lo crearon (abandono del {_pct(res_embudo['abandono_en_esa_etapa'])})."},
        {"id": "F3", "tipo": "observado", "texto": f"En orgánico × autónomo solo el {_pct(res_embudo['mayor_oportunidad_conversion'])} de quienes configuran crea un cliente; la mediana del resto de grupos es {_pct(res_embudo['mayor_oportunidad_referencia'])}."},
        {"id": "F4", "tipo": "observado", "texto": f"Llega a la primera factura el {_pct(res_embudo['pct_factura_pyme'])} de las pymes y el {_pct(res_embudo['pct_factura_autonomo'])} de los autónomos (cohortes maduras)."},
        {"id": "F5", "tipo": "observado", "texto": f"Registro a primera factura: {_pct(total.registro_a_factura)}. Primera factura a pago: {_pct(total.factura_a_pago)} (cohortes con 45 días para pagar)."},
        {"id": "F6", "tipo": "observado", "texto": f"De quienes llevan 3 días o más quietos, solo el {_pct(base_resumen['tasa_base_estimada'], 2)} factura por su cuenta en 14 días."},
        {"id": "F7", "tipo": "observado", "texto": "Nadie emitió su primera factura más de 8 días después de registrarse."},
        {"id": "F8", "tipo": "observado", "texto": f"Entre quienes no facturaron, el {_pct(detenidos.set_index('ultimo_paso').pct['configuro_empresa'])} se detuvo justo después de configurar la empresa."},
        {"id": "F9", "tipo": "observado", "texto": "Los eventos solo registran 5 pasos con su fecha; no hay sesiones, clics ni errores, así que no se sabe por qué se frenan."},
        {"id": "F10", "tipo": "observado", "texto": "Un artículo de ayuda (enviar una factura por correo) quedó desactualizado por una nota de cambios de esta semana."},
        {"id": "E1", "tipo": "experimento", "texto": f"Experimento en curso: {salud['tamanos']['tratamiento']} personas con correo y {salud['tamanos']['control']} de control. Métrica: primera factura en 14 días. Aún no hay resultados observados."},
        {"id": "E2", "tipo": "experimento", "texto": f"El reparto es reproducible ({salud['reproducibilidad']['coinciden']} de {salud['reproducibilidad']['personas']}) y sin descuadre, pero por azar el grupo de control tiene más personas sin configurar la empresa; se corrige analizando por paso."},
        {"id": "P1", "tipo": "calculado", "texto": f"Prioridad por reglas: {prioridades.get('alta', 0)} alta, {prioridades.get('media', 0)} media y {prioridades.get('baja', 0)} baja. Ordena la atención; no mide a quién le sirve más el contacto."},
    ]
    fila = esc.iloc[1]
    hechos.append(
        {"id": "S1", "tipo": "estimación bajo supuestos", "texto": f"Si el correo sumara {fila.efecto_supuesto_pp:.0f} puntos de primera factura a los {int(fila.personas_objetivo)} atascados, serían unas {fila.facturas_adicionales:.0f} facturas y {fila.pagos_adicionales:.0f} pagos más (supuesto, no resultado)."}
    )
    for h in hip:
        hechos.append({"id": h["id"], "tipo": "hipótesis", "texto": f"{h['hipotesis']} Evidencia: {h['evidencia']} Experimento: {h['experimento']}"})
    return hechos


def analizar(
    fecha: date = FECHA_CORRIDA,
    modo: str = "auto",
    forzar: bool = False,
    dir_salida: Path | None = None,
    dir_cache: Path | None = None,
    avisar=lambda mensaje: None,
) -> dict:
    dir_salida = Path(dir_salida or DIR_SALIDA)
    faltan = [n for n in NECESARIOS if not (dir_salida / n).is_file()]
    if faltan:
        raise FaltaSalida(f"Falta la salida del flujo ({', '.join(faltan)}): corre antes `cuadra correr`.")
    destino = dir_salida / DIR_INTELIGENCIA_NOMBRE
    destino.mkdir(parents=True, exist_ok=True)

    datos = cargar()
    estado = pd.read_csv(dir_salida / "estado.csv", dtype={"id_contacto": str})
    asignacion = pd.read_csv(dir_salida / "asignacion_experimento.csv", dtype={"id_contacto": str})
    bandeja = pd.read_csv(dir_salida / "bandeja_salida.csv", dtype=str)
    resumen_flujo = json.loads((dir_salida / "resumen.json").read_text(encoding="utf-8"))

    avisar("1/6 Embudo completo y oportunidades")
    personas = embudo_completo.tabla_personas(datos, fecha)
    maduras = personas[personas.madura]
    _csv(embudo_completo.embudo_etapas(maduras), destino / "embudo_etapas.csv")
    _csv(embudo_completo.embudo_por_grupo(maduras, ["segmento"]), destino / "embudo_por_segmento.csv")
    _csv(embudo_completo.embudo_por_grupo(maduras, ["canal"]), destino / "embudo_por_canal.csv")
    _csv(embudo_completo.embudo_por_grupo(maduras, ["mes_registro"]), destino / "embudo_por_mes.csv")
    _csv(embudo_completo.oportunidades(maduras), destino / "oportunidades.csv")
    res_embudo = embudo_completo.resumen_embudo(datos, fecha)

    avisar("2/6 Comportamiento y cohortes")
    detenidos = comportamiento.donde_se_detiene(datos, fecha)
    _csv(comportamiento.secuencias(datos, fecha), destino / "secuencias.csv")
    _csv(detenidos, destino / "donde_se_detiene.csv")
    _csv(comportamiento.tiempo_a_primera_factura(datos, fecha), destino / "tiempo_a_primera_factura.csv")
    _csv(comportamiento.acciones_antes_de_activar(datos, fecha), destino / "acciones_antes_de_activar.csv")
    _csv(comportamiento.ritmo_activados_vs_no(datos, fecha), destino / "ritmo_activados_vs_no.csv")
    _csv(comportamiento.cohortes_semanales(datos, fecha), destino / "cohortes_semanales.csv")
    _csv(pd.DataFrame(comportamiento.INSTRUMENTACION_RECOMENDADA), destino / "instrumentacion_recomendada.csv")

    avisar("3/6 Salud del experimento")
    salud = salud_experimento.informe_salud(asignacion, datos.contactos, bandeja, estado)
    _csv(salud_experimento.balance(asignacion, datos.contactos), destino / "balance.csv")
    observado = None
    ruta_obs = dir_salida / "eventos_posteriores.csv"
    if ruta_obs.is_file():
        resultado, estratos = medir(asignacion, pd.read_csv(ruta_obs))
        if not resultado.simulado:
            observado = {"resultado": resultado.como_dict(), "ajustado": salud_experimento.ajuste_por_estratos(estratos)}
    simulado = None
    ruta_sim = dir_salida / "SIMULADO_eventos_posteriores.csv"
    if ruta_sim.is_file():
        resultado, estratos = medir(asignacion, pd.read_csv(ruta_sim))
        simulado = {
            "resultado": resultado.como_dict(),
            "ajustado": salud_experimento.ajuste_por_estratos(estratos, simulado=True),
            "explicacion": salud_experimento.explicar(resultado),
        }
    salud["observado"] = observado
    salud["explicacion_observado"] = salud_experimento.explicar(
        ResultadoExperimento(**{**observado["resultado"], "ic95": tuple(observado["resultado"]["ic95"])}) if observado else None
    )
    salud["simulado"] = simulado
    _json(salud, destino / "salud_experimento.json")

    avisar("4/6 Priorización")
    evidencia = priorizacion.evidencia_por_paso(datos, fecha)
    priorizados = priorizacion.priorizar(estado, datos.contactos, asignacion, evidencia)
    _csv(priorizados, destino / "priorizacion.csv")
    conteo_prioridad = priorizados.prioridad.value_counts().to_dict()

    avisar("5/6 Intervenciones por canal")
    _csv(plan_intervenciones(priorizados, datos.contactos), destino / "plan_intervenciones.csv")
    modelo = Modelo(dir_cache=dir_cache or DIR_CACHE, modo=modo, forzar=forzar)
    ruta_base = dir_salida / "base_vigente.json"
    contenidos = []
    if ruta_base.is_file():
        base = BaseVigente.model_validate_json(ruta_base.read_text(encoding="utf-8"))
        contenidos = redactar_contenidos(base, modelo)
    _json(contenidos, destino / "contenidos_por_canal.json")

    avisar("6/6 Negocio e informe ejecutivo")
    conv = negocio.conversiones(datos, fecha)
    _csv(conv, destino / "conversiones_negocio.csv")
    total = conv[conv.dimension == "total"].iloc[0]
    efecto_minimo = resumen_flujo.get("efecto_minimo_detectable") or 0.02
    esc = negocio.escenarios(
        int(len(asignacion)), float(total.factura_a_pago), negocio.ingreso_medio_mensual(datos),
        [round(efecto_minimo / 2, 3), round(efecto_minimo, 3), round(efecto_minimo * 2.5, 3)],
    )
    _csv(esc, destino / "escenarios.csv")
    hip = negocio.hipotesis(res_embudo, conv, resumen_flujo.get("tasa_base_estimada"), salud)
    _json(hip, destino / "hipotesis.json")
    hechos = _hechos(res_embudo, conv, salud, resumen_flujo, conteo_prioridad, esc, hip, detenidos)
    _json(hechos, destino / "hechos.json")
    informe = redactar_informe(hechos, modelo)
    _json(informe, destino / "informe_ejecutivo.json")

    resumen = {
        "fecha": fecha.isoformat(),
        **res_embudo,
        "prioridad": conteo_prioridad,
        "contenidos_aprobados": sum(c["estado"] == "aprobado" for c in contenidos),
        "contenidos_total": len(contenidos),
        "informe": informe["estado"],
        "experimento_problemas": len(salud["problemas"]),
        "llamadas_reales": int(modelo.llamadas_reales),
    }
    _json(resumen, destino / "resumen.json")
    return resumen
