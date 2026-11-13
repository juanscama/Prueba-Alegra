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

    from cuadra import cli

    class TemporizadorInmediato:
        def __init__(self, espera, funcion, args=()):
            self.funcion, self.args = funcion, args

        def start(self):
            self.funcion(*self.args)

    lanzado = {}
    monkeypatch.setattr(subprocess, "call", lambda orden: lanzado.update(orden=orden) or 0)
    monkeypatch.setattr(cli.threading, "Timer", TemporizadorInmediato)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: lanzado.update(url=url))
    assert main(["panel"]) == 0
    assert lanzado["orden"][:5] == [sys.executable, "-m", "streamlit", "run", PANEL]
    # Sin terminal interactiva, Streamlit se queda esperando un correo en su primer arranque: modo sin cabeza.
    assert "--server.headless" in lanzado["orden"]
    assert lanzado["url"] == "http://localhost:8501"


def test_panel_no_afirma_que_la_aa_pasa_si_no_pasa(tmp_path, monkeypatch):
    import shutil

    shutil.copytree(DIR_SALIDA, tmp_path / "salida")
    ruta = tmp_path / "salida" / "prueba_aa.json"
    aa = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps({**aa, "valor_p": 0.01, "diferencia": 0.09}), encoding="utf-8")
    monkeypatch.setenv("CUADRA_DIR_SALIDA", str(tmp_path / "salida"))
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert not at.exception
    textos = " ".join(m.value for m in at.markdown)
    assert "no la hay" not in textos
    assert any("prueba A/A" in w.value for w in at.warning)
