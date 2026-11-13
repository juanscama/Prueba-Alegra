from datetime import date

import pytest

from cuadra.estado import calcular_estado
from cuadra.experimento import asignar, efecto_minimo_detectable, equilibrio, grupo


def test_determinista(datos):
    a = asignar(calcular_estado(datos))
    b = asignar(calcular_estado(datos))
    assert a.grupo.tolist() == b.grupo.tolist()
    assert grupo("C00001") == grupo("C00001")
    assert grupo("C00001") in ("tratamiento", "control")


def test_el_grupo_no_cambia_con_la_fecha(datos):
    antes = asignar(calcular_estado(datos, date(2026, 10, 20)), date(2026, 10, 20)).set_index("id_contacto").grupo
    hoy = asignar(calcular_estado(datos)).set_index("id_contacto").grupo
    comunes = antes.index.intersection(hoy.index)
    assert len(comunes) > 500 and (antes[comunes] == hoy[comunes]).all()


def test_la_semilla_cambia_el_reparto():
    ids = [f"C{i:05d}" for i in range(200)]
    assert [grupo(i, "a") for i in ids] != [grupo(i, "b") for i in ids]


def test_proporcion_extrema():
    assert grupo("C00001", proporcion=1.0) == "tratamiento"
    assert grupo("C00001", proporcion=0.0) == "control"


def test_tamano_y_reparto(datos):
    a = asignar(calcular_estado(datos))
    assert len(a) == 912 and 0.45 <= (a.grupo == "tratamiento").mean() <= 0.55
    assert (a.fecha_entrada == date(2026, 10, 31)).all()
    assert a.elegible.all()


@pytest.mark.parametrize("por", ["paso", "tramo", "canal", "segmento"])
def test_equilibrio(datos, por):
    a = asignar(calcular_estado(datos))
    eq = equilibrio(a, datos.contactos, por)
    assert eq.pct_tratamiento.between(0.40, 0.60).all()
    assert eq.tratamiento.sum() + eq.control.sum() == 912


def test_efecto_minimo():
    assert efecto_minimo_detectable(456, 456, 0.02) == pytest.approx(0.026, abs=0.001)
