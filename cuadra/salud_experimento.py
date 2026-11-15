"""Módulo 5: salud del experimento original y explicación sencilla de sus resultados.

No toca la asignación: la lee y la comprueba. Lo observado y lo simulado se informan por separado.
"""

from math import sqrt
from statistics import NormalDist

import pandas as pd

from cuadra.config import PROPORCION_TRATAMIENTO, SEMILLA, VENTANA_DIAS
from cuadra.experimento import grupo
from cuadra.medicion import ResultadoExperimento

UMBRAL_SMD = 0.1
UMBRAL_SRM = 0.01

METRICA_PRIMARIA = {
    "nombre": "Primera factura en 14 días",
    "definicion": (
        f"Proporción de personas asignadas que emiten su primera factura en los {VENTANA_DIAS} días "
        "siguientes a su fecha de entrada (después de ese día, no el mismo día)."
    ),
    "unidad": "persona asignada (por intención de tratar: cuenta aunque no abra el correo)",
    "comparacion": "tratamiento − control, en puntos porcentuales",
    "criterio": (
        "Intervalo de confianza del 95% para la diferencia de proporciones (aproximación normal). "
        "Se extiende a todos solo si el intervalo entero queda por encima de cero; si no, se itera."
    ),
    "fijada": "antes de enviar ningún correo (ver docs/2026-11-12-diseno-flujo-activacion.md)",
}


def descuadre_de_reparto(n_t: int, n_c: int, proporcion: float = PROPORCION_TRATAMIENTO) -> dict:
    """Sample ratio mismatch: ¿el reparto se aleja de lo esperado más de lo que explica el azar?"""
    total = n_t + n_c
    if not total:
        return {"n_t": 0, "n_c": 0, "esperado_t": 0.0, "valor_p": 1.0, "alerta": False}
    esperado = total * proporcion
    z = (n_t - esperado) / sqrt(total * proporcion * (1 - proporcion))
    valor_p = 2 * (1 - NormalDist().cdf(abs(z)))
    return {"n_t": n_t, "n_c": n_c, "esperado_t": esperado, "valor_p": valor_p, "alerta": valor_p < UMBRAL_SRM}


def reproducibilidad(asignacion: pd.DataFrame, semilla: str = SEMILLA) -> dict:
    """Recalcula el grupo de cada persona con el hash y cuenta las que no coinciden con lo guardado."""
    recalculado = asignacion.id_contacto.astype(str).map(lambda i: grupo(i, semilla))
    distintos = asignacion.id_contacto[recalculado != asignacion.grupo].astype(str).tolist()
    return {"personas": int(len(asignacion)), "coinciden": int(len(asignacion) - len(distintos)), "distintos": distintos[:20]}


def problemas_de_asignacion(
    asignacion: pd.DataFrame, bandeja: pd.DataFrame, estado: pd.DataFrame | None = None
) -> list[str]:
    """Lista de problemas; vacía si no hay ninguno."""
    problemas = []
    ids = asignacion.id_contacto.astype(str)
    if ids.duplicated().any():
        problemas.append(f"Hay {int(ids.duplicated().sum())} personas repetidas en la asignación")
    grupos_raros = set(asignacion.grupo) - {"tratamiento", "control"}
    if grupos_raros:
        problemas.append(f"Grupos desconocidos: {', '.join(sorted(grupos_raros))}")
    control = set(ids[asignacion.grupo == "control"])
    en_bandeja = set(bandeja.id_contacto.astype(str)) if len(bandeja) else set()
    contaminados = control & en_bandeja
    if contaminados:
        problemas.append(f"{len(contaminados)} personas de control tienen correo en la bandeja (contaminación)")
    fuera = en_bandeja - set(ids)
    if fuera:
        problemas.append(f"{len(fuera)} personas con correo no están en la asignación")
    if estado is not None and len(estado):
        elegibles = set(estado[estado.elegible.astype(str).str.lower() == "true"].id_contacto.astype(str))
        no_elegibles = set(ids) - elegibles
        if no_elegibles:
            problemas.append(f"{len(no_elegibles)} personas asignadas no eran elegibles el día de entrada")
    return problemas


def _smd(p_t: float, p_c: float) -> float:
    var = (p_t * (1 - p_t) + p_c * (1 - p_c)) / 2
    return 0.0 if var == 0 else (p_t - p_c) / sqrt(var)


def balance(asignacion: pd.DataFrame, contactos: pd.DataFrame) -> pd.DataFrame:
    """Diferencia estandarizada (SMD) entre grupos para cada valor de cada característica previa.

    |SMD| < 0,1 se considera equilibrado. Solo usa datos conocidos el día de la asignación.
    """
    tabla = asignacion.merge(contactos[["id_contacto", "canal", "segmento"]], on="id_contacto", how="left")
    t, c = tabla[tabla.grupo == "tratamiento"], tabla[tabla.grupo == "control"]
    filas = []
    for columna in ("paso", "tramo", "canal", "segmento"):
        for valor in sorted(tabla[columna].dropna().unique()):
            p_t, p_c = float((t[columna] == valor).mean()), float((c[columna] == valor).mean())
            filas.append({"caracteristica": columna, "valor": valor, "pct_t": p_t, "pct_c": p_c, "smd": _smd(p_t, p_c)})
    media_t, media_c = t.dias_quieto.mean(), c.dias_quieto.mean()
    desviacion = sqrt((t.dias_quieto.var() + c.dias_quieto.var()) / 2) or 1.0
    filas.append(
        {"caracteristica": "dias_quieto", "valor": "media", "pct_t": float(media_t), "pct_c": float(media_c),
         "smd": float((media_t - media_c) / desviacion)}
    )
    tabla = pd.DataFrame(filas)
    tabla["equilibrado"] = tabla.smd.abs() < UMBRAL_SMD
    return tabla


def explicar(resultado: ResultadoExperimento | None) -> str:
    """Explicación para alguien sin formación en estadística. Nunca declara ganador con datos simulados."""
    if resultado is None:
        return (
            "Todavía no hay resultados observados. Los correos no se han enviado de verdad y no ha pasado la "
            f"ventana de {VENTANA_DIAS} días. Cuando llegue la exportación de eventos posterior, se compara qué "
            "parte de cada grupo emitió su primera factura."
        )
    pp = lambda x: f"{x * 100:.1f}".replace(".", ",")
    texto = (
        f"De {resultado.n_t} personas que recibieron correo, {resultado.conv_t} emitieron su primera factura "
        f"({pp(resultado.tasa_t)}%). De {resultado.n_c} que no lo recibieron, {resultado.conv_c} "
        f"({pp(resultado.tasa_c)}%). La diferencia es de {pp(resultado.diferencia)} puntos. "
        f"Con este tamaño de grupos, la diferencia real estaría, con un 95% de confianza, entre "
        f"{pp(resultado.ic95[0])} y {pp(resultado.ic95[1])} puntos. "
    )
    if resultado.simulado:
        return (
            "DEMOSTRACIÓN CON DATOS SIMULADOS: estas cifras son inventadas para mostrar cómo se leerá el "
            "resultado. No hay ganador. " + texto
        )
    if resultado.ic95[0] > 0:
        return texto + "Como todo el intervalo está por encima de cero, el correo ayuda: se extiende a todos."
    if resultado.ic95[1] < 0:
        return texto + "Todo el intervalo está por debajo de cero: el correo empeora el resultado. Se retira."
    return texto + "El intervalo incluye el cero: no se puede afirmar que el correo ayude. Se itera el mensaje."


def informe_salud(
    asignacion: pd.DataFrame, contactos: pd.DataFrame, bandeja: pd.DataFrame, estado: pd.DataFrame | None = None
) -> dict:
    n_t = int((asignacion.grupo == "tratamiento").sum())
    n_c = int((asignacion.grupo == "control").sum())
    tabla_balance = balance(asignacion, contactos)
    return {
        "metrica_primaria": METRICA_PRIMARIA,
        "tamanos": {"tratamiento": n_t, "control": n_c},
        "descuadre": descuadre_de_reparto(n_t, n_c),
        "reproducibilidad": reproducibilidad(asignacion),
        "problemas": problemas_de_asignacion(asignacion, bandeja, estado),
        "balance_max_smd": float(tabla_balance.smd.abs().max()),
        "balance_todo_equilibrado": bool(tabla_balance.equilibrado.all()),
    }


def ajuste_por_estratos(por_estrato: pd.DataFrame, dimension: str = "paso", simulado: bool = False) -> dict:
    """Diferencia ajustada por post-estratificación: media ponderada de las diferencias dentro de cada estrato.

    Corrige el desequilibrio casual de una característica previa (aquí, el paso en que estaba cada persona)
    sin tocar la asignación. Pesos: tamaño del estrato sobre el total.
    """
    partes = por_estrato[por_estrato.dimension == dimension]
    total = float((partes.n_t + partes.n_c).sum())
    if not total:
        return {"dimension": dimension, "diferencia_ajustada": 0.0, "ic95": [0.0, 0.0], "simulado": simulado}
    diferencia = varianza = 0.0
    for _, fila in partes.iterrows():
        peso = (fila.n_t + fila.n_c) / total
        diferencia += peso * (fila.tasa_t - fila.tasa_c)
        if fila.n_t and fila.n_c:
            varianza += peso**2 * (
                fila.tasa_t * (1 - fila.tasa_t) / fila.n_t + fila.tasa_c * (1 - fila.tasa_c) / fila.n_c
            )
    z = NormalDist().inv_cdf(0.975)
    error = sqrt(varianza)
    return {
        "dimension": dimension,
        "diferencia_ajustada": diferencia,
        "ic95": [diferencia - z * error, diferencia + z * error],
        "simulado": simulado,
    }
