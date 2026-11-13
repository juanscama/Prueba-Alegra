from cuadra.redaccion import Correo, Variante, personalizar, redactar, segmento_de, variantes_posibles

VARIANTE = Variante("sin_cliente", "peluquería", "reciente")


def test_108_variantes(datos):
    v = variantes_posibles(datos.contactos)
    assert len(v) == 108 and len({x.clave for x in v}) == 108
    assert {x.tramo for x in v} == {"reciente", "rezagado"}
    assert {x.paso for x in v} == {"sin_configurar", "sin_cliente", "sin_factura"}


def test_clave():
    assert VARIANTE.clave == "sin_cliente|peluquería|reciente"


def test_segmento_de(datos):
    s = segmento_de(datos.contactos)
    assert s["peluquería"] == "autonomo" and s["restaurante"] == "pyme" and len(s) == 18


def test_personalizar_no_rompe_con_llaves():
    c = Correo(
        asunto="{nombre}, tu primera factura", cuerpo="Hola, {nombre}. Usa {esto} tal cual.",
        paso_siguiente="x", ruta_menu="Ventas > Facturas", articulo_fuente="01-crear-tu-primera-factura.md",
    )
    assert personalizar(c, "Álvaro") == ("Álvaro, tu primera factura", "Hola, Álvaro. Usa {esto} tal cual.")


def test_el_prompt_describe_la_variante(base_de_prueba, modelo_espia):
    correo = redactar(VARIANTE, base_de_prueba, modelo_espia, "autonomo")
    assert isinstance(correo, Correo) and modelo_espia.ultima_tarea == "redaccion"
    usuario = modelo_espia.ultimo_usuario
    assert "peluquería" in usuario and "autónomo" in usuario
    assert "Crear cliente" in usuario or "crear" in usuario.lower()
    assert "ventas > facturas" in usuario            # rutas válidas
    assert "Facturas recurrentes" in usuario         # función que no debe ofrecer
    assert "Motivo del rechazo" not in usuario


def test_el_prompt_usa_el_articulo_vigente_no_el_original(base_de_prueba, modelo_espia):
    redactar(Variante("sin_factura", "restaurante", "rezagado"), base_de_prueba, modelo_espia, "pyme")
    usuario = modelo_espia.ultimo_usuario
    assert "Más acciones > Enviar por correo" not in usuario
    assert "pyme" in usuario and "restaurante" in usuario


def test_prompt_lleva_motivo_de_rechazo(base_de_prueba, modelo_espia):
    redactar(VARIANTE, base_de_prueba, modelo_espia, "autonomo", motivo_rechazo="R3 ruta inexistente")
    assert "R3 ruta inexistente" in modelo_espia.ultimo_usuario


def test_tramos_dan_prompts_distintos(base_de_prueba, modelo_espia):
    redactar(VARIANTE, base_de_prueba, modelo_espia, "autonomo")
    reciente = modelo_espia.ultimo_usuario
    redactar(Variante("sin_cliente", "peluquería", "rezagado"), base_de_prueba, modelo_espia, "autonomo")
    assert reciente != modelo_espia.ultimo_usuario
