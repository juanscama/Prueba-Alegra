from datetime import date

import pandas as pd
import pytest

from cuadra.estado import calcular_estado
from cuadra.experimento import acumular, asignar, conversion_natural, efecto_minimo_detectable, equilibrio, grupo


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


def test_efecto_minimo_caso_de_libro():
    # Fórmula clásica de tamaño de muestra para dos proporciones (alfa 0,05 bilateral, potencia 0,8):
    # pasar del 2% al 5,5% exige 461 personas por grupo. A la inversa, 461 por grupo detectan 3,5 puntos.
    assert efecto_minimo_detectable(461, 461, 0.02) == pytest.approx(0.035, abs=0.0005)


def test_efecto_minimo_crece_con_la_tasa_base():
    assert efecto_minimo_detectable(456, 456, 0.002) < efecto_minimo_detectable(456, 456, 0.02)


def test_efecto_minimo_sin_un_grupo_no_existe():
    assert efecto_minimo_detectable(0, 10, 0.02) is None
    assert efecto_minimo_detectable(10, 0, 0.02) is None


def test_asignar_sin_elegibles(datos):
    a = asignar(calcular_estado(datos, date(2026, 6, 1)), date(2026, 6, 1))
    assert len(a) == 0 and {"id_contacto", "grupo", "fecha_entrada"} <= set(a.columns)


def test_conversion_natural_sale_de_los_datos(datos):
    convertidos, observaciones, cortes = conversion_natural(datos, date(2026, 10, 31))
    assert len(cortes) >= 5 and max(cortes) <= date(2026, 10, 17)
    assert observaciones > 3000 and 0 < convertidos / observaciones < 0.01


def test_conversion_natural_sin_historia(datos):
    assert conversion_natural(datos, date(2026, 7, 5)) == (0, 0, [])


def test_acumular_conserva_la_primera_fecha_y_no_borra_a_nadie(datos):
    primera = asignar(calcular_estado(datos), date(2026, 10, 31))
    segunda = asignar(calcular_estado(datos, date(2026, 11, 10)), date(2026, 11, 10))
    previa = primera.iloc[:900]          # como si 12 personas hubieran facturado y ya no fueran elegibles hoy
    ya_facturaron = primera.iloc[900:].assign(id_contacto=[f"YA_FACTURO_{i}" for i in range(12)])
    total = acumular(pd.concat([previa, ya_facturaron]), segunda)
    assert set(ya_facturaron.id_contacto) <= set(total.id_contacto) and total.id_contacto.is_unique
    fechas = total.set_index("id_contacto").fecha_entrada.astype(str)
    assert (fechas[previa.id_contacto] == "2026-10-31").all()
    nuevos = set(segunda.id_contacto) - set(previa.id_contacto)
    assert nuevos and (fechas[list(nuevos)] == "2026-11-10").all()
