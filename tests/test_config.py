from cuadra.config import modelo_configurado


def test_modelo_por_defecto(tmp_path, monkeypatch):
    monkeypatch.delenv("CUADRA_MODELO", raising=False)
    assert modelo_configurado(tmp_path / "no-existe.env") == "claude-opus-5-5"


def test_modelo_desde_el_archivo_env(tmp_path, monkeypatch):
    monkeypatch.delenv("CUADRA_MODELO", raising=False)
    (tmp_path / ".env").write_text("CUADRA_MODELO=claude-haiku-5-5\n", encoding="utf-8")
    assert modelo_configurado(tmp_path / ".env") == "claude-haiku-5-5"


def test_la_variable_de_entorno_gana_al_archivo(tmp_path, monkeypatch):
    monkeypatch.setenv("CUADRA_MODELO", "claude-sonnet-5-5")
    (tmp_path / ".env").write_text("CUADRA_MODELO=claude-haiku-5-5\n", encoding="utf-8")
    assert modelo_configurado(tmp_path / ".env") == "claude-sonnet-5-5"
