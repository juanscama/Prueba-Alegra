from cuadra.config import DIR_AYUDAS
from cuadra.conocimiento import construir_base, extraer_rutas, leer_documentos, normalizar_ruta


def test_normalizar_ruta():
    assert normalizar_ruta("**Ventas>Facturas**") == normalizar_ruta("Ventas › Facturas") == "ventas > facturas"
    assert normalizar_ruta("  Más acciones  →  Rectificar ") == "más acciones > rectificar"


def test_extraer_rutas_solo_negritas_con_flecha():
    texto = "Entra en **Ventas > Facturas** y pulsa **Nueva factura**. Luego **Informes › Ventas**."
    assert extraer_rutas(texto) == {"ventas > facturas", "informes > ventas"}


def test_leer_documentos_ignora_archivos_de_macos(tmp_path):
    (tmp_path / "01-a.md").write_text("# A", encoding="utf-8")
    (tmp_path / "._01-a.md").write_bytes(b"\x00\x05basura")
    assert leer_documentos(tmp_path) == {"01-a.md": "# A"}


def test_rutas_validas_y_obsoletas(modelo_falso_conocimiento):
    b = construir_base(modelo_falso_conocimiento)
    assert "más acciones > enviar por correo" in b.rutas_obsoletas
    assert "más acciones > enviar por correo" not in b.rutas_validas
    assert "más acciones > rectificar" in b.rutas_validas
    assert "ventas > facturas recurrentes > nueva recurrente" in b.rutas_validas
    assert [a.archivo for a in b.articulos if not a.vigente] == ["04-enviar-una-factura-por-correo.md"]
    assert len(b.articulos) == 5


def test_articulo_vigente_conserva_el_texto_original(modelo_falso_conocimiento):
    b = construir_base(modelo_falso_conocimiento)
    primero = b.articulos[0]
    original = (DIR_AYUDAS / primero.archivo).read_text(encoding="utf-8").strip()
    assert primero.vigente and primero.texto_vigente == original and primero.frases_obsoletas == []


def test_funciones_restringidas(modelo_falso_conocimiento):
    b = construir_base(modelo_falso_conocimiento)
    assert [(f.nombre, f.plan) for f in b.funciones_restringidas] == [("Facturas recurrentes", "Pro")]
