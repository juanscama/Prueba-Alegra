import pytest

from cuadra.modelo import ErrorModelo, Rechazo, SinCache
from cuadra.redaccion import Correo, Variante
from cuadra.verificacion import Veredicto, procesar, verificar_reglas
from tests.conftest import ModeloGuion

BUENO = Correo(
    asunto="Tu primer cliente en Cuadra",
    cuerpo="Hola, {nombre}. Entra en **Ventas > Facturas**, pulsa **Nueva factura** y crea tu cliente.",
    paso_siguiente="Crear cliente",
    ruta_menu="Ventas > Facturas",
    articulo_fuente="01-crear-tu-primera-factura.md",
)
VARIANTE = Variante("sin_cliente", "peluquería", "reciente")


def con(**cambios) -> Correo:
    return BUENO.model_copy(update=cambios)


MALO = con(cuerpo="Hola, {nombre}. Pulsa **Más acciones > Enviar por correo**.")
VEREDICTO_MALO = Veredicto(
    respaldado=False, responde_al_paso=True, tono_adecuado=True, un_solo_paso=True,
    motivos=["Promete algo que el artículo no dice"],
)


def test_bueno_pasa(base_de_prueba):
    assert verificar_reglas(BUENO, base_de_prueba) == []


@pytest.mark.parametrize(
    "cuerpo, codigo",
    [
        ("Hola, {nombre}. Pulsa **Más acciones > Enviar por correo**.", "R4"),
        ("Hola, {nombre}. Pulsa más acciones › enviar por correo.", "R4"),
        ("Hola, {nombre}. Activa las facturas recurrentes.", "R5"),
        ("Hola, {nombre}. Tienes un 20% de descuento.", "R6"),
        ("Hola, {nombre}. Es gratis durante un mes.", "R6"),
        ("Hola. Entra en **Ventas > Facturas**.", "R1"),
        ("Hola, {nombre}. Otra vez, {nombre}.", "R1"),
        ("Hola, {nombre} de {empresa}.", "R2"),
        ("Hola, {nombre}. Entra en **Ventas > Presupuestos**.", "R3"),
        ("Hola, {nombre}. Entra en Ventas > Facturas, sin negrita.", "R3"),
        ("Hola, {nombre}. " + "x" * 900, "R7"),
        ("Hola, {nombre}. Mira https://cuadra.example/ayuda.", "R8"),
    ],
)
def test_defectos_sembrados(base_de_prueba, cuerpo, codigo):
    motivos = verificar_reglas(con(cuerpo=cuerpo), base_de_prueba)
    assert any(m.startswith(codigo) for m in motivos), motivos


def test_asunto_largo(base_de_prueba):
    assert any(m.startswith("R7") for m in verificar_reglas(con(asunto="x" * 61), base_de_prueba))


def test_ruta_menu_inexistente(base_de_prueba):
    assert any(m.startswith("R3") for m in verificar_reglas(con(ruta_menu="Ventas > Presupuestos"), base_de_prueba))


def test_ruta_con_otra_tipografia_pasa(base_de_prueba):
    correo = con(cuerpo="Hola, {nombre}. Entra en **Ventas›Facturas**.", ruta_menu="ventas  >  facturas")
    assert verificar_reglas(correo, base_de_prueba) == []


def test_aprobada_al_primer_intento(base_de_prueba):
    r = procesar(VARIANTE, base_de_prueba, ModeloGuion([BUENO]), "autonomo")
    assert (r.estado, r.intentos, r.motivos) == ("aprobada", 1, [])
    assert r.correo == BUENO and r.veredicto.respaldado


def test_reintento_recupera_y_lleva_el_motivo(base_de_prueba):
    modelo = ModeloGuion([MALO, BUENO])
    r = procesar(VARIANTE, base_de_prueba, modelo, "autonomo")
    assert (r.estado, r.intentos) == ("aprobada", 2) and r.correo == BUENO
    assert "R4" in modelo.usuarios_de_redaccion[1]


def test_reintento_y_revision(base_de_prueba):
    r = procesar(VARIANTE, base_de_prueba, ModeloGuion([MALO, MALO]), "autonomo")
    assert (r.estado, r.intentos) == ("revision", 2)
    assert r.correo == MALO and any(m.startswith("R4") for m in r.motivos)


def test_el_juez_tambien_rechaza(base_de_prueba):
    modelo = ModeloGuion([BUENO, BUENO], veredictos=[VEREDICTO_MALO, VEREDICTO_MALO])
    r = procesar(VARIANTE, base_de_prueba, modelo, "autonomo")
    assert r.estado == "revision" and any("Promete algo" in m for m in r.motivos)
    assert "Promete algo" in modelo.usuarios_de_redaccion[1]


@pytest.mark.parametrize(
    "error, texto",
    [(SinCache("x"), "sin caché y sin clave"), (Rechazo("x"), "el modelo declinó"), (ErrorModelo("cuota"), "cuota")],
)
def test_fallos_del_modelo_van_a_revision(base_de_prueba, error, texto):
    r = procesar(VARIANTE, base_de_prueba, ModeloGuion([], error=error), "autonomo")
    assert r.estado == "revision" and r.correo is None and texto in r.motivos[0]
