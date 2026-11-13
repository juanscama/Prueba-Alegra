from datetime import date

import pandas as pd

from cuadra.estado import calcular_estado, pagadores_sin_factura
from cuadra.ingesta import Datos


def test_conteos_al_31_de_octubre(datos):
    e = calcular_estado(datos)
    assert len(e) == 944
    assert e.paso.value_counts().to_dict() == {"sin_cliente": 427, "sin_configurar": 292, "sin_factura": 225}
    assert e.tramo.value_counts().to_dict() == {"rezagado": 824, "reciente": 88, "en_ventana": 32}
    assert e.elegible.sum() == 912
    assert len(e[(e.paso == "sin_cliente") & (e.tramo == "reciente")]) == 48


def test_pagadores_sin_factura(datos):
    assert pagadores_sin_factura(datos) == [
        "C00014", "C00108", "C00265", "C00625", "C00629", "C00981", "C01006", "C01443",
    ]


def test_otra_fecha_no_ve_el_futuro(datos):
    corte = date(2026, 9, 15)
    e = calcular_estado(datos, corte)
    registro = datos.contactos.set_index("id_contacto").fecha_registro
    assert (registro[e.id_contacto] <= corte).all()
    assert (e.dias_quieto >= 0).all()
    # Quien facturó después del corte todavía estaba atascado ese día.
    facturo_despues = datos.eventos[
        (datos.eventos.evento == "emitio_primera_factura") & (datos.eventos.fecha > corte)
    ].id_contacto
    registrados = registro[registro <= corte].index
    assert set(facturo_despues) & set(registrados) <= set(e.id_contacto)


def _datos_minimos(dias_quieto: list[int], hoy: date) -> Datos:
    ids = [f"X{i}" for i in range(len(dias_quieto))]
    fechas = [hoy - pd.Timedelta(days=d).to_pytimedelta() for d in dias_quieto]
    contactos = pd.DataFrame(
        {
            "id_contacto": ids, "nombre": "Ana", "email": "a@correo.example", "fecha_registro": fechas,
            "canal": "organico", "segmento": "autonomo", "actividad": "peluquería", "etapa_crm": "registrado",
        }
    )
    eventos = pd.DataFrame({"id_contacto": ids, "evento": "registro", "fecha": fechas})
    pagos = pd.DataFrame(columns=["id_contacto", "fecha_pago", "plan", "importe_eur_mes"])
    return Datos(contactos, eventos, pagos)


def test_limites_de_tramo():
    hoy = date(2026, 10, 31)
    e = calcular_estado(_datos_minimos([2, 3, 14, 15], hoy), hoy)
    assert e.tramo.tolist() == ["en_ventana", "reciente", "reciente", "rezagado"]
    assert e.elegible.tolist() == [False, True, True, True]
