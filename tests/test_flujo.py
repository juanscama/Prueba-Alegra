import json

import pandas as pd
import pytest

from cuadra import flujo
from cuadra.cli import main
from cuadra.conocimiento import BaseVigente
from tests.conftest import ModeloGuion
from tests.test_bandeja import CORREO

ARCHIVOS = [
    "diagnostico.md", "estado.csv", "asignacion_experimento.csv", "variantes.json",
    "bandeja_salida.csv", "cola_revision.csv", "pagadores_sin_factura.csv", "resumen.json",
]


def test_flujo_sin_clave_ni_cache(tmp_path):
    salida = tmp_path / "salida"
    r = flujo.correr(modo="repeticion", dir_salida=salida, dir_cache=tmp_path / "cache_vacio")
    assert r["elegibles"] == 912 and r["correos_en_bandeja"] == 0 and r["llamadas_reales"] == 0
    assert r["tratamiento"] + r["control"] == 912
    assert r["variantes_en_revision"] == 108 and r["variantes_aprobadas"] == 0
    assert (salida / "cola_revision.csv").read_text(encoding="utf-8").count("sin caché y sin clave") == 108
    for nombre in ARCHIVOS:
        assert (salida / nombre).is_file(), nombre
    assert json.loads((salida / "resumen.json").read_text(encoding="utf-8")) == r


@pytest.fixture
def flujo_con_modelo_falso(monkeypatch, base_de_prueba):
    """Sustituye el modelo y la base por dobles: todas las variantes salen aprobadas."""

    class ModeloInfinito(ModeloGuion):
        def pedir(self, *, tarea, **kwargs):
            if tarea == "redaccion":
                return CORREO
            return super().pedir(tarea=tarea, **kwargs)

    monkeypatch.setattr(flujo, "Modelo", lambda *a, **k: ModeloInfinito([]))
    monkeypatch.setattr(flujo, "construir_base", lambda modelo: base_de_prueba)


def test_flujo_completo_con_modelo_falso(tmp_path, flujo_con_modelo_falso):
    r = flujo.correr(dir_salida=tmp_path)
    assert r["variantes_aprobadas"] == 108 and r["correos_en_bandeja"] == r["tratamiento"]
    assert r["personas_sin_correo_por_revision"] == 0 and 0 < r["efecto_minimo_detectable"] < 0.1
    bandeja = pd.read_csv(tmp_path / "bandeja_salida.csv")
    asignacion = pd.read_csv(tmp_path / "asignacion_experimento.csv")
    assert len(bandeja) == r["tratamiento"] and len(asignacion) == 912
    assert BaseVigente.model_validate_json((tmp_path / "base_vigente.json").read_text(encoding="utf-8"))


def test_dos_corridas_dan_lo_mismo(tmp_path, flujo_con_modelo_falso):
    flujo.correr(dir_salida=tmp_path / "a")
    flujo.correr(dir_salida=tmp_path / "b")
    for nombre in ARCHIVOS:
        assert (tmp_path / "a" / nombre).read_bytes() == (tmp_path / "b" / nombre).read_bytes(), nombre


def test_limite_de_variantes(tmp_path, flujo_con_modelo_falso):
    r = flujo.correr(dir_salida=tmp_path, limite_variantes=6)
    assert r["variantes_aprobadas"] == 6 and r["variantes_sin_procesar"] == 102
    assert 0 < r["correos_en_bandeja"] < r["tratamiento"]


def test_respetar_enviados_no_repite(tmp_path, flujo_con_modelo_falso):
    primera = flujo.correr(dir_salida=tmp_path, respetar_enviados=True)
    segunda = flujo.correr(dir_salida=tmp_path, respetar_enviados=True)
    assert primera["correos_en_bandeja"] == primera["tratamiento"] and segunda["correos_en_bandeja"] == 0
    assert len(pd.read_csv(tmp_path / "enviados.csv")) == primera["tratamiento"]


def test_cli_correr_imprime_el_resumen(tmp_path, monkeypatch, capsys, flujo_con_modelo_falso):
    monkeypatch.setattr(flujo, "DIR_SALIDA", tmp_path)
    assert main(["correr", "--fecha", "2026-10-31", "--limite-variantes", "3"]) == 0
    impreso = capsys.readouterr().out
    assert "912" in impreso and "bandeja" in impreso.lower()
