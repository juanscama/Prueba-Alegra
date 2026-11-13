import json

from streamlit.testing.v1 import AppTest

from cuadra.config import DIR_SALIDA, RAIZ

PANEL = str(RAIZ / "panel" / "app.py")


def test_panel_con_salida():
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == [
        "1 · El problema", "2 · La ayuda al día", "3 · Los correos", "4 · ¿Funcionó?", "5 · Límites",
    ]
    resumen = json.loads((DIR_SALIDA / "resumen.json").read_text(encoding="utf-8"))
    portada = next(m.value for m in at.markdown if 'class="portada"' in m.value)
    assert f">{resumen['correos_en_bandeja']}<" in portada and "correos listos para enviar" in portada
    assert f">{resumen['control']}<" in portada and f"{resumen['elegibles']} personas" in portada


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
    assert persona.options and all("Sin configurar su empresa" in opcion for opcion in persona.options)


def test_panel_muestra_el_correo_como_correo_y_escapa_html():
    import importlib.util

    at = AppTest.from_file(PANEL, default_timeout=60).run()
    correo = next(m.value for m in at.markdown if 'class="correo"' in m.value)
    assert "El equipo de Cuadra" in correo and "<strong>" in correo and "**" not in correo
    # La función que arma el correo no deja pasar HTML que venga en el texto.
    fuente = (RAIZ / "panel" / "app.py").read_text(encoding="utf-8")
    funciones = fuente.split("def cuerpo_html")[1].split("def correo_html")[0]
    espacio = {}
    exec("import html, re\ndef cuerpo_html" + funciones, espacio)
    salida = espacio["cuerpo_html"]("Hola <script>x</script>\n\n1. Entra en **Ventas > Facturas**\n2. Pulsa")
    assert "<script>" not in salida and "&lt;script&gt;" in salida
    assert "<ol><li>Entra en <strong>Ventas &gt; Facturas</strong></li><li>Pulsa</li></ol>" in salida


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
    monkeypatch.setattr(subprocess, "call", lambda orden, cwd=None: lanzado.update(orden=orden, cwd=cwd) or 0)
    monkeypatch.setattr(cli.threading, "Timer", TemporizadorInmediato)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: lanzado.update(url=url))
    assert main(["panel"]) == 0
    assert lanzado["orden"][:5] == [sys.executable, "-m", "streamlit", "run", PANEL]
    # Sin terminal interactiva, Streamlit se queda esperando un correo en su primer arranque: modo sin cabeza.
    assert "--server.headless" in lanzado["orden"]
    assert lanzado["url"] == "http://localhost:8501"
    assert lanzado["cwd"] == RAIZ  # para que Streamlit encuentre el tema en .streamlit/config.toml


def test_panel_no_afirma_que_la_aa_pasa_si_no_pasa(tmp_path, monkeypatch):
    import shutil

    shutil.copytree(DIR_SALIDA, tmp_path / "salida")
    ruta = tmp_path / "salida" / "prueba_aa.json"
    aa = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps({**aa, "valor_p": 0.01, "diferencia": 0.09}), encoding="utf-8")
    monkeypatch.setenv("CUADRA_DIR_SALIDA", str(tmp_path / "salida"))
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    assert not at.exception
    textos = " ".join(m.value for m in list(at.markdown) + list(at.caption))
    assert "esperable por azar" not in textos
    assert any("prueba A/A" in w.value for w in at.warning)


def test_panel_abre_con_el_caso_de_la_fuga():
    """Al entrar, el correo de ejemplo es el de alguien que no creó su primer cliente: el caso que explica la fuga."""
    at = AppTest.from_file(PANEL, default_timeout=60).run()
    persona = next(s for s in at.selectbox if s.label == "Persona")
    assert "Sin crear un cliente" in persona.value
    porque = next(m.value for m in at.markdown if "Por qué recibe este correo" in m.value)
    assert "sin crear un cliente" in porque
