from datetime import date, timedelta

import pandas as pd
import pytest

from cuadra.estado import calcular_estado
from cuadra.experimento import asignar
from cuadra.medicion import comparar, medir, prueba_aa
from cuadra.simulador import simular_eventos


def test_comparar_caso_a_mano():
    r = comparar(400, 40, 400, 20)
    assert r.diferencia == pytest.approx(0.05)
    assert r.ic95 == pytest.approx((0.01366, 0.08634), abs=1e-4)
    assert r.valor_p == pytest.approx(0.00726, abs=1e-4) and r.decision == "extender"
    assert (r.tasa_t, r.tasa_c, r.simulado) == (0.1, 0.05, False)


def test_sin_diferencia_itera():
    assert comparar(400, 20, 400, 20).decision == "iterar"


def test_diferencia_negativa_itera():
    assert comparar(400, 10, 400, 30).decision == "iterar"


def test_cero_conversiones():
    r = comparar(400, 0, 400, 0)
    assert r.valor_p == 1.0 and r.ic95 == (0.0, 0.0) and r.decision == "iterar"


def test_grupo_vacio_no_divide_por_cero():
    r = comparar(0, 0, 400, 20)
    assert r.tasa_t == 0.0 and r.decision == "iterar"


def test_simulado_queda_marcado_y_se_recupera_el_efecto(datos):
    a = asignar(calcular_estado(datos))
    ev = simular_eventos(a, efecto=0.08)
    r, por_estrato = medir(a, ev)
    assert ev.simulado.all() and r.simulado
    assert set(ev.evento) == {"emitio_primera_factura"}
    assert 0.03 < r.diferencia < 0.13 and r.decision == "extender"
    assert r.n_t + r.n_c == 912
    assert set(por_estrato.dimension) == {"paso", "tramo"}
    assert por_estrato[por_estrato.dimension == "paso"].n_t.sum() == r.n_t


def test_simulador_es_reproducible(datos):
    a = asignar(calcular_estado(datos))
    assert simular_eventos(a, efecto=0.08).equals(simular_eventos(a, efecto=0.08))
    assert not simular_eventos(a, efecto=0.08).equals(simular_eventos(a, efecto=0.08, semilla=8))


def test_sin_efecto_la_diferencia_es_pequena(datos):
    a = asignar(calcular_estado(datos))
    r, _ = medir(a, simular_eventos(a, efecto=0.0))
    assert abs(r.diferencia) < 0.03


def test_ventana():
    entrada = date(2026, 10, 31)
    asignacion = pd.DataFrame(
        {
            "id_contacto": ["A", "B", "C", "D"], "paso": "sin_cliente", "tramo": "reciente",
            "grupo": ["tratamiento", "tratamiento", "tratamiento", "control"], "fecha_entrada": entrada,
        }
    )
    eventos = pd.DataFrame(
        {
            "id_contacto": ["A", "B", "C", "C", "D"],
            "evento": ["emitio_primera_factura", "emitio_primera_factura", "creo_cliente",
                       "emitio_primera_factura", "emitio_primera_factura"],
            "fecha": [entrada + timedelta(days=14), entrada + timedelta(days=15), entrada + timedelta(days=2),
                      entrada, entrada + timedelta(days=1)],
        }
    )
    r, _ = medir(asignacion, eventos)
    # A cuenta (día 14); B no (día 15); C no (su factura es del mismo día de entrada, no posterior); D sí.
    assert (r.conv_t, r.n_t, r.conv_c, r.n_c) == (1, 3, 1, 1)
    assert r.simulado is False


def test_medir_acepta_fechas_leidas_de_csv(datos, tmp_path):
    a = asignar(calcular_estado(datos))
    a.to_csv(tmp_path / "a.csv", index=False)
    simular_eventos(a, efecto=0.08).to_csv(tmp_path / "e.csv", index=False)
    directo, _ = medir(a, simular_eventos(a, efecto=0.08))
    leido, _ = medir(pd.read_csv(tmp_path / "a.csv"), pd.read_csv(tmp_path / "e.csv"))
    assert leido == directo


def test_aa(datos):
    r = prueba_aa(datos)
    assert r.n_t + r.n_c == 777 and r.simulado is False
    assert 0.3 < r.tasa_t < 0.45 and 0.3 < r.tasa_c < 0.45


def test_cli_simular_y_medir(datos, tmp_path, monkeypatch, capsys):
    from cuadra import flujo
    from cuadra.cli import main

    monkeypatch.setattr(flujo, "DIR_SALIDA", tmp_path)
    asignar(calcular_estado(datos)).to_csv(tmp_path / "asignacion_experimento.csv", index=False)
    assert main(["simular", "--efecto", "0.08"]) == 0
    ruta = tmp_path / "SIMULADO_eventos_posteriores.csv"
    assert ruta.is_file() and main(["medir", "--eventos", str(ruta)]) == 0
    impreso = capsys.readouterr().out
    assert "SIMULADO" in impreso and "extender" in impreso
    assert (tmp_path / "SIMULADO_resultado_experimento.json").is_file()
    assert not (tmp_path / "resultado_experimento.json").exists()


def test_la_semilla_configurada_pasa_la_prueba_aa(datos):
    """Regla fijada antes de enviar nada: se usa la primera semilla candidata cuya prueba A/A da p > 0,2."""
    from cuadra.config import SEMILLA, SEMILLAS_CANDIDATAS, UMBRAL_AA

    valores_p = {s: prueba_aa(datos, s).valor_p for s in SEMILLAS_CANDIDATAS}
    primera_que_pasa = next(s for s in SEMILLAS_CANDIDATAS if valores_p[s] > UMBRAL_AA)
    assert SEMILLA == primera_que_pasa
    assert prueba_aa(datos).valor_p > UMBRAL_AA
