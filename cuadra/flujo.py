"""El flujo de punta a punta: de los CSV a la bandeja de salida y el experimento."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

from cuadra.bandeja import armar_bandeja, armar_cola_revision
from cuadra.config import DIR_CACHE, DIR_SALIDA, FECHA_CORRIDA, MODELO
from cuadra.conocimiento import construir_base
from cuadra.diagnostico import embudo, embudo_por, escribir_diagnostico, tiempos_entre_pasos
from cuadra.estado import calcular_estado, pagadores_sin_factura
from cuadra.experimento import asignar, efecto_minimo_detectable, equilibrio
from cuadra.ingesta import cargar
from cuadra.modelo import ErrorModelo, Modelo, Rechazo, SinCache
from cuadra.redaccion import Variante, segmento_de, variantes_posibles
from cuadra.verificacion import en_revision, procesar

# Conversión natural en 14 días de quien lleva 3 o más días quieto: entre 0% y 3% en cinco cortes históricos.
TASA_BASE_ESTIMADA = 0.02
HILOS = 4


def _csv(tabla: pd.DataFrame, ruta: Path) -> None:
    tabla.to_csv(ruta, index=False, lineterminator="\n", encoding="utf-8")


def _json(objeto, ruta: Path) -> None:
    ruta.write_text(json.dumps(objeto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def correr(
    fecha: date = FECHA_CORRIDA,
    modo: str = "auto",
    forzar: bool = False,
    limite_variantes: int | None = None,
    dir_salida: Path | None = None,
    dir_cache: Path | None = None,
    respetar_enviados: bool = False,
    avisar=lambda mensaje: None,
) -> dict:
    dir_salida = Path(dir_salida or DIR_SALIDA)
    dir_salida.mkdir(parents=True, exist_ok=True)

    avisar("1/8 Leyendo y validando los datos")
    datos = cargar()

    avisar("2/8 Diagnóstico del embudo")
    escribir_diagnostico(datos, dir_salida / "diagnostico.md")
    _csv(embudo(datos), dir_salida / "embudo.csv")
    _csv(embudo_por(datos, ["canal", "segmento"]), dir_salida / "embudo_por_canal_segmento.csv")
    _csv(embudo_por(datos, ["mes_registro"]), dir_salida / "embudo_por_mes.csv")
    _csv(tiempos_entre_pasos(datos), dir_salida / "tiempos_entre_pasos.csv")

    avisar("3/8 Estado de cada persona")
    estado = calcular_estado(datos, fecha)
    _csv(estado, dir_salida / "estado.csv")
    _csv(
        pd.DataFrame({"id_contacto": pagadores_sin_factura(datos, fecha)}),
        dir_salida / "pagadores_sin_factura.csv",
    )

    avisar("4/8 Reparto en tratamiento y control")
    asignacion = asignar(estado, fecha)
    _csv(asignacion, dir_salida / "asignacion_experimento.csv")
    partes = []
    for dimension in ("paso", "tramo", "canal", "segmento"):
        parte = equilibrio(asignacion, datos.contactos, dimension).rename(columns={dimension: "valor"})
        parte.insert(0, "dimension", dimension)
        partes.append(parte)
    _csv(pd.concat(partes), dir_salida / "equilibrio.csv")
    n_t = int((asignacion.grupo == "tratamiento").sum())
    n_c = int((asignacion.grupo == "control").sum())

    avisar("5/8 Base de conocimiento vigente (ayudas contra notas de cambios)")
    modelo = Modelo(dir_cache=dir_cache or DIR_CACHE, modo=modo, forzar=forzar)
    motivo_sin_base = None
    try:
        base = construir_base(modelo)
        (dir_salida / "base_vigente.json").write_text(
            base.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    except SinCache:
        base, motivo_sin_base = None, "sin caché y sin clave"
    except Rechazo:
        base, motivo_sin_base = None, "el modelo declinó"
    except ErrorModelo as error:
        base, motivo_sin_base = None, f"error de la API: {error}"

    variantes = variantes_posibles(datos.contactos)
    segmentos = segmento_de(datos.contactos)
    sin_procesar = []
    if limite_variantes is not None:
        # Con límite, primero las variantes que llegan a más personas del grupo de tratamiento.
        actividad = datos.contactos.set_index("id_contacto").actividad
        tratamiento = asignacion[asignacion.grupo == "tratamiento"]
        alcance = pd.Series(
            [Variante(p, actividad[i], t).clave for i, p, t in zip(tratamiento.id_contacto, tratamiento.paso, tratamiento.tramo)]
        ).value_counts()
        variantes = sorted(variantes, key=lambda v: (-int(alcance.get(v.clave, 0)), v.clave))
        variantes, sin_procesar = variantes[:limite_variantes], variantes[limite_variantes:]

    avisar(f"6/8 y 7/8 Redacción y verificación de {len(variantes)} variantes")
    if base is None:
        resultados = [en_revision(v, motivo_sin_base) for v in variantes]
    else:
        with ThreadPoolExecutor(max_workers=HILOS) as hilos:
            resultados = list(hilos.map(lambda v: procesar(v, base, modelo, segmentos[v.actividad]), variantes))
    procesadas = {r.variante.clave: r for r in resultados}
    _json(
        [procesadas[clave].model_dump(mode="json") for clave in sorted(procesadas)],
        dir_salida / "variantes.json",
    )

    avisar("8/8 Bandeja de salida")
    bandeja = armar_bandeja(asignacion, datos.contactos, procesadas)
    if respetar_enviados:
        ruta_enviados = dir_salida / "enviados.csv"
        columnas = ["id_contacto", "fecha_entrada", "variante"]
        previos = pd.read_csv(ruta_enviados, dtype=str) if ruta_enviados.is_file() else pd.DataFrame(columns=columnas)
        bandeja = bandeja[~bandeja.id_contacto.isin(previos.id_contacto)].reset_index(drop=True)
        _csv(pd.concat([previos, bandeja[columnas].astype(str)]), ruta_enviados)
    _csv(bandeja, dir_salida / "bandeja_salida.csv")
    cola = armar_cola_revision(asignacion, datos.contactos, procesadas)
    _csv(cola, dir_salida / "cola_revision.csv")

    resumen = {
        "fecha": fecha.isoformat(),
        "modo": getattr(modelo, "modo", modo),
        "modelo": MODELO,
        "personas_sin_facturar": int(len(estado)),
        "en_ventana": int((~estado.elegible).sum()),
        "elegibles": int(len(asignacion)),
        "tratamiento": n_t,
        "control": n_c,
        "variantes_aprobadas": sum(r.estado == "aprobada" for r in resultados),
        "variantes_en_revision": sum(r.estado == "revision" for r in resultados),
        "variantes_sin_procesar": len(sin_procesar),
        "correos_en_bandeja": int(len(bandeja)),
        "personas_sin_correo_por_revision": int(cola.personas_sin_correo.sum()),
        "llamadas_reales": int(modelo.llamadas_reales),
        "tasa_base_estimada": TASA_BASE_ESTIMADA,
        "efecto_minimo_detectable": round(efecto_minimo_detectable(n_t, n_c, TASA_BASE_ESTIMADA), 4),
    }
    _json(resumen, dir_salida / "resumen.json")
    return resumen
