from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from cuadra import modelo as modulo
from cuadra.modelo import Modelo, Rechazo, SinCache, hay_clave


class Saludo(BaseModel):
    texto: str


class ClienteFalso:
    """Imita la parte del SDK que usa Modelo: cuenta llamadas y devuelve lo que se le diga."""

    def __init__(self, texto="Buenos días, señor Muñoz", stop_reason="end_turn"):
        self.llamadas = []
        self._texto, self._stop_reason = texto, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.llamadas.append(kwargs)
        salida = None if self._stop_reason == "refusal" else kwargs["output_format"](texto=self._texto)
        return SimpleNamespace(
            parsed_output=salida,
            stop_reason=self._stop_reason,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )


PETICION = dict(tarea="saludo", sistema="Eres amable.", usuario="Saluda.", esquema=Saludo)


def archivos(tmp_path):
    return sorted(tmp_path.rglob("*.json"))


def test_repeticion_sin_cache_lanza(tmp_path):
    with pytest.raises(SinCache):
        Modelo(tmp_path, modo="repeticion").pedir(**PETICION)


def test_vivo_guarda_y_no_repite(tmp_path):
    cliente = ClienteFalso()
    m = Modelo(tmp_path, modo="vivo", cliente=cliente)
    primera, segunda = m.pedir(**PETICION), m.pedir(**PETICION)
    assert primera == segunda == Saludo(texto="Buenos días, señor Muñoz")
    assert len(cliente.llamadas) == 1 and m.llamadas_reales == 1
    assert len(archivos(tmp_path)) == 1 and archivos(tmp_path)[0].parent.name == "saludo"


def test_repeticion_lee_lo_que_vivo_guardo(tmp_path):
    Modelo(tmp_path, modo="vivo", cliente=ClienteFalso()).pedir(**PETICION)
    m = Modelo(tmp_path, modo="repeticion")
    assert m.pedir(**PETICION).texto == "Buenos días, señor Muñoz" and m.llamadas_reales == 0


def test_cambiar_usuario_cambia_clave(tmp_path):
    m = Modelo(tmp_path, modo="vivo", cliente=ClienteFalso())
    m.pedir(**PETICION)
    m.pedir(**{**PETICION, "usuario": "Saluda otra vez."})
    assert len(archivos(tmp_path)) == 2


def test_forzar_vuelve_a_llamar(tmp_path):
    cliente = ClienteFalso()
    Modelo(tmp_path, modo="vivo", cliente=cliente).pedir(**PETICION)
    Modelo(tmp_path, modo="vivo", forzar=True, cliente=cliente).pedir(**PETICION)
    assert len(cliente.llamadas) == 2 and len(archivos(tmp_path)) == 1


def test_rechazo(tmp_path):
    with pytest.raises(Rechazo):
        Modelo(tmp_path, modo="vivo", cliente=ClienteFalso(stop_reason="refusal")).pedir(**PETICION)
    assert archivos(tmp_path) == []


def test_cache_legible(tmp_path):
    Modelo(tmp_path, modo="vivo", cliente=ClienteFalso()).pedir(**PETICION)
    texto = archivos(tmp_path)[0].read_text(encoding="utf-8")
    assert "señor Muñoz" in texto and "Saluda." in texto


def test_la_peticion_usa_el_modelo_configurado_y_no_fija_muestreo(tmp_path):
    cliente = ClienteFalso()
    Modelo(tmp_path, modo="vivo", cliente=cliente).pedir(**PETICION)
    enviado = cliente.llamadas[0]
    assert enviado["model"] == modulo.MODELO and enviado["system"] == "Eres amable."
    assert enviado["messages"] == [{"role": "user", "content": "Saluda."}]
    assert not {"temperature", "top_p", "top_k", "thinking"} & set(enviado)


def test_auto_sin_clave_es_repeticion(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "hay_clave", lambda: False)
    assert Modelo(tmp_path).modo == "repeticion"


def test_auto_con_clave_es_vivo(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "hay_clave", lambda: True)
    assert Modelo(tmp_path).modo == "vivo"


def test_hay_clave_lee_el_entorno(monkeypatch):
    monkeypatch.setattr(modulo, "_cargar_env", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert hay_clave() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  ")
    assert hay_clave() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "una-clave")
    assert hay_clave() is True


def test_respuesta_invalida_es_rechazo(tmp_path):
    cliente = ClienteFalso()

    def parse_que_no_valida(**kwargs):
        Saludo.model_validate({})  # así falla el SDK cuando la salida llega truncada o no es el JSON pedido

    cliente.beta.messages.parse = parse_que_no_valida
    with pytest.raises(Rechazo):
        Modelo(tmp_path, modo="vivo", cliente=cliente).pedir(**PETICION)


def test_vivo_sin_clave_y_sin_cache_es_sincache(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "hay_clave", lambda: False)
    with pytest.raises(SinCache):
        Modelo(tmp_path, modo="vivo").pedir(**PETICION)


def test_forzar_sin_clave_avisa_al_crear(tmp_path, monkeypatch):
    monkeypatch.setattr(modulo, "hay_clave", lambda: False)
    with pytest.raises(modulo.SinClave, match="clave"):
        Modelo(tmp_path, modo="vivo", forzar=True)
