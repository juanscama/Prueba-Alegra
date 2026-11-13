"""El caché versionado basta para reproducir la corrida real, sin clave y sin red."""

import pandas as pd
import pytest

from cuadra import flujo
from cuadra.conocimiento import BaseVigente


@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    salida = tmp_path_factory.mktemp("salida")
    return flujo.correr(modo="repeticion", dir_salida=salida), salida


def test_corrida_real_en_repeticion(corrida):
    r, salida = corrida
    assert r["llamadas_reales"] == 0 and r["modo"] == "repeticion"
    assert r["variantes_aprobadas"] + r["variantes_en_revision"] == 108
    assert r["variantes_aprobadas"] == 108 and r["variantes_en_revision"] == 0
    assert r["correos_en_bandeja"] + r["personas_sin_correo_por_revision"] == r["tratamiento"]


def test_ningun_correo_real_lleva_instrucciones_viejas_ni_funciones_pro(corrida):
    _, salida = corrida
    b = pd.read_csv(salida / "bandeja_salida.csv")
    assert len(b) > 400
    assert not b.cuerpo.str.contains("{nombre}", regex=False).any()
    assert not b.asunto.str.contains("{nombre}", regex=False).any()
    assert not b.cuerpo.str.contains("Más acciones > Enviar", case=False, regex=False).any()
    assert not b.cuerpo.str.contains("recurrente", case=False).any()
    assert b.cuerpo.str.len().max() <= 900 + b.nombre.str.len().max()


def test_cada_correo_real_nombra_a_su_destinatario(corrida):
    _, salida = corrida
    b = pd.read_csv(salida / "bandeja_salida.csv")
    assert all(nombre in cuerpo for nombre, cuerpo in zip(b.nombre, b.cuerpo))


def test_base_real(corrida):
    _, salida = corrida
    base = BaseVigente.model_validate_json((salida / "base_vigente.json").read_text(encoding="utf-8"))
    assert [a.archivo for a in base.articulos if not a.vigente] == ["04-enviar-una-factura-por-correo.md"]
    assert any(f.plan == "Pro" for f in base.funciones_restringidas)
    assert "más acciones > enviar por correo" in base.rutas_obsoletas
    assert "más acciones > rectificar" in base.rutas_validas
