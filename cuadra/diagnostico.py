"""Etapa 2: embudo y tiempos entre pasos. Código determinista, sin IA."""

from pathlib import Path

import pandas as pd

from cuadra.config import PASOS
from cuadra.ingesta import Datos


def _pasos_por_persona(datos: Datos) -> pd.DataFrame:
    """Una fila por persona, una columna por paso con su fecha (NaN si no lo dio), más `pago`."""
    fechas = datos.eventos.pivot(index="id_contacto", columns="evento", values="fecha")
    fechas = fechas.reindex(columns=PASOS)
    tabla = datos.contactos.set_index("id_contacto").join(fechas)
    tabla["pago"] = tabla.index.isin(datos.pagos.id_contacto)
    tabla["mes_registro"] = tabla.fecha_registro.map(lambda f: f.strftime("%Y-%m"))
    return tabla


def embudo(datos: Datos) -> pd.DataFrame:
    tabla = _pasos_por_persona(datos)
    conteos = [int(tabla[p].notna().sum()) for p in PASOS] + [int(tabla.pago.sum())]
    return pd.DataFrame(
        {
            "paso": PASOS + ["pago"],
            "contactos": conteos,
            "pct_registro": [c / len(tabla) for c in conteos],
        }
    )


def embudo_por(datos: Datos, columnas: list[str]) -> pd.DataFrame:
    tabla = _pasos_por_persona(datos)
    filas = []
    for clave, grupo in tabla.groupby(columnas):
        clave = clave if isinstance(clave, tuple) else (clave,)
        fila = dict(zip(columnas, clave), n=len(grupo))
        for paso in PASOS[1:]:
            fila[f"pct_{paso}"] = grupo[paso].notna().mean()
        fila["pct_pago"] = grupo.pago.mean()
        configuraron = grupo.configuro_empresa.notna().sum()
        fila["pct_config_a_cliente"] = (
            grupo.creo_cliente.notna().sum() / configuraron if configuraron else float("nan")
        )
        filas.append(fila)
    return pd.DataFrame(filas)


def tiempos_entre_pasos(datos: Datos) -> pd.DataFrame:
    tabla = _pasos_por_persona(datos)
    filas = []
    for desde, hasta in zip(PASOS, PASOS[1:]):
        ambos = tabla[tabla[desde].notna() & tabla[hasta].notna()]
        dias = pd.Series([(b - a).days for a, b in zip(ambos[desde], ambos[hasta])])
        filas.append(
            {
                "desde": desde,
                "hasta": hasta,
                "n": len(dias),
                "mediana": float(dias.median()),
                "p90": float(dias.quantile(0.9)),
                "maximo": int(dias.max()),
            }
        )
    return pd.DataFrame(filas)


def _tabla_md(tabla: pd.DataFrame) -> str:
    def celda(valor, columna):
        if isinstance(valor, float) and columna.startswith("pct_"):
            return f"{valor:.0%}"
        if isinstance(valor, float):
            return f"{valor:g}"
        return str(valor)

    lineas = ["| " + " | ".join(tabla.columns) + " |", "|" + "---|" * len(tabla.columns)]
    for _, fila in tabla.iterrows():
        lineas.append("| " + " | ".join(celda(fila[c], c) for c in tabla.columns) + " |")
    return "\n".join(lineas)


def hallazgo_principal(datos: Datos) -> str:
    cruce = embudo_por(datos, ["canal", "segmento"])
    peor = cruce.loc[cruce.pct_config_a_cliente.idxmin()]
    resto = cruce.drop(peor.name).pct_config_a_cliente
    return (
        f"La mayor fuga está en {peor.canal} × {peor.segmento}: {int(peor.n)} personas, solo el "
        f"{peor.pct_config_a_cliente:.0%} pasa de configurar la empresa a crear un cliente y el "
        f"{peor.pct_emitio_primera_factura:.0%} llega a facturar. En el resto de cruces de canal y "
        f"segmento ese paso lo da entre el {resto.min():.0%} y el {resto.max():.0%}."
    )


def escribir_diagnostico(datos: Datos, ruta: Path) -> None:
    tiempos = tiempos_entre_pasos(datos)
    techo = int(tiempos.maximo.iloc[:3].sum())
    partes = [
        "# Diagnóstico del embudo",
        "",
        "## Hallazgo principal",
        "",
        hallazgo_principal(datos),
        "",
        f"Quien avanza lo hace rápido: nadie emitió su primera factura más de {techo} días después "
        "de registrarse.",
        "",
        "## Embudo general",
        "",
        _tabla_md(embudo(datos)),
        "",
        "## Por canal y segmento",
        "",
        _tabla_md(embudo_por(datos, ["canal", "segmento"])),
        "",
        "## Por mes de registro",
        "",
        _tabla_md(embudo_por(datos, ["mes_registro"])),
        "",
        "## Días entre pasos",
        "",
        _tabla_md(tiempos),
        "",
    ]
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text("\n".join(partes), encoding="utf-8")
