import shutil
from pathlib import Path

import pandas as pd
import pytest

from cuadra.config import DIR_DATOS
from cuadra.ingesta import ErrorDatos, cargar


def copiar_datos(destino: Path) -> Path:
    for nombre in ("crm_contactos.csv", "eventos_producto.csv", "pagos.csv"):
        shutil.copy(DIR_DATOS / nombre, destino / nombre)
    return destino


def reescribir(destino: Path, nombre: str, cambio) -> Path:
    copiar_datos(destino)
    tabla = pd.read_csv(destino / nombre)
    cambio(tabla).to_csv(destino / nombre, index=False)
    return destino


def quitar_columna(columna):
    return lambda d: reescribir(d, "crm_contactos.csv", lambda t: t.drop(columns=[columna]))


def duplicar_id(id_contacto):
    return lambda d: reescribir(
        d, "crm_contactos.csv", lambda t: pd.concat([t, t[t.id_contacto == id_contacto]])
    )


def fila_de_evento(id_contacto, evento, fecha="2026-08-01"):
    return pd.DataFrame([{"id_contacto": id_contacto, "evento": evento, "fecha": fecha}])


def evento_huerfano(id_contacto):
    return lambda d: reescribir(
        d, "eventos_producto.csv", lambda t: pd.concat([t, fila_de_evento(id_contacto, "registro")])
    )


def evento_desconocido(evento):
    return lambda d: reescribir(
        d, "eventos_producto.csv", lambda t: pd.concat([t, fila_de_evento("C00001", evento)])
    )


def paso_sin_anterior(id_contacto, evento):
    # Deja a la persona solo con su registro y le añade un paso que se salta los intermedios.
    def cambio(t):
        t = t[(t.id_contacto != id_contacto) | (t.evento == "registro")]
        return pd.concat([t, fila_de_evento(id_contacto, evento, "2026-10-30")])

    return lambda d: reescribir(d, "eventos_producto.csv", cambio)


def test_carga_real(datos):
    assert len(datos.contactos) == 1500 and datos.contactos.id_contacto.is_unique
    assert len(datos.eventos) == 4284 and len(datos.pagos) == 205


def test_fechas_son_fechas(datos):
    import datetime

    assert isinstance(datos.contactos.fecha_registro.iloc[0], datetime.date)
    assert isinstance(datos.eventos.fecha.iloc[0], datetime.date)
    assert isinstance(datos.pagos.fecha_pago.iloc[0], datetime.date)


def test_ignora_archivos_de_macos_y_bom(tmp_path):
    copiar_datos(tmp_path)
    (tmp_path / "._pagos.csv").write_bytes(b"\x00\x05\x16\x07basura")
    texto = (tmp_path / "pagos.csv").read_text(encoding="utf-8")
    (tmp_path / "pagos.csv").write_text(texto, encoding="utf-8-sig")
    assert len(cargar(tmp_path).pagos) == 205


def test_falta_un_archivo(tmp_path):
    copiar_datos(tmp_path)
    (tmp_path / "pagos.csv").unlink()
    with pytest.raises(ErrorDatos, match="pagos.csv"):
        cargar(tmp_path)


@pytest.mark.parametrize(
    "romper, texto",
    [
        (quitar_columna("canal"), "canal"),
        (duplicar_id("C00001"), "C00001"),
        (evento_huerfano("C99999"), "C99999"),
        (evento_desconocido("bailo"), "bailo"),
        (paso_sin_anterior("C00003", "creo_cliente"), "C00003"),
    ],
    ids=["sin_columna", "id_duplicado", "evento_huerfano", "evento_desconocido", "paso_sin_anterior"],
)
def test_rechaza_datos_rotos(tmp_path, romper, texto):
    with pytest.raises(ErrorDatos, match=texto):
        cargar(romper(tmp_path))
