import json

from streamlit.testing.v1 import AppTest

from cuadra.config import DIR_SALIDA, RAIZ

PANEL = str(RAIZ / "panel" / "app.py")


def test_panel_con_salida():
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Diagnóstico", "Base vigente", "Mensajes", "Experimento", "Qué no cubre"]
    resumen = json.loads((DIR_SALIDA / "resumen.json").read_text(encoding="utf-8"))
    assert any(str(resumen["correos_en_bandeja"]) in m.value for m in at.metric)


def test_panel_sin_salida(tmp_path, monkeypatch):
    monkeypatch.setenv("CUADRA_DIR_SALIDA", str(tmp_path))
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert not at.exception and "cuadra correr" in at.warning[0].value
    assert len(at.tabs) == 0


def test_panel_filtra_mensajes_por_paso():
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    paso = next(s for s in at.selectbox if s.label == "Paso")
    paso.select("sin_configurar").run()
    assert not at.exception
    persona = next(s for s in at.selectbox if s.label == "Persona")
    assert persona.options and all("sin_configurar" in opcion for opcion in persona.options)


def test_panel_avisa_de_lo_simulado():
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert any("SIMULADO" in w.value for w in at.warning)


def test_cli_panel_lanza_streamlit(monkeypatch):
    import subprocess
    import sys

    from cuadra.cli import main

    lanzado = {}
    monkeypatch.setattr(subprocess, "call", lambda orden: lanzado.update(orden=orden) or 0)
    assert main(["panel"]) == 0
    assert lanzado["orden"] == [sys.executable, "-m", "streamlit", "run", PANEL]
