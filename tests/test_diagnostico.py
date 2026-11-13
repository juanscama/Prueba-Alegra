from cuadra.diagnostico import embudo, embudo_por, escribir_diagnostico, tiempos_entre_pasos


def test_embudo(datos):
    e = embudo(datos)
    assert e.contactos.tolist() == [1500, 1200, 773, 548, 263, 205]
    assert e.paso.tolist()[-1] == "pago"
    assert e.pct_registro.iloc[0] == 1.0


def test_fuga_autonomo_organico(datos):
    t = embudo_por(datos, ["canal", "segmento"]).set_index(["canal", "segmento"])
    assert t.loc[("organico", "autonomo"), "n"] == 590
    assert round(t.loc[("organico", "autonomo"), "pct_config_a_cliente"], 2) == 0.42
    assert t.drop(("organico", "autonomo")).pct_config_a_cliente.min() >= 0.71


def test_embudo_por_mes_de_registro(datos):
    t = embudo_por(datos, ["mes_registro"])
    assert t.mes_registro.tolist() == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert t.n.sum() == 1500


def test_tiempos(datos):
    t = tiempos_entre_pasos(datos)
    assert t.maximo.tolist()[:3] == [1, 3, 4]
    assert t.n.tolist() == [1200, 773, 548, 263]


def test_escribir_diagnostico_calcula_el_hallazgo(datos, tmp_path):
    ruta = tmp_path / "diagnostico.md"
    escribir_diagnostico(datos, ruta)
    texto = ruta.read_text(encoding="utf-8")
    assert "organico" in texto and "autonomo" in texto and "42%" in texto and "590" in texto
