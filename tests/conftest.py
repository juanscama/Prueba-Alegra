import pytest

from cuadra.ingesta import cargar


@pytest.fixture(scope="session")
def datos():
    return cargar()


@pytest.fixture
def base_de_prueba():
    """Base vigente escrita a mano: lo mínimo para probar redacción y verificación sin modelo."""
    from cuadra.conocimiento import ArticuloVigente, BaseVigente, FuncionRestringida

    return BaseVigente(
        articulos=[
            ArticuloVigente(
                archivo="01-crear-tu-primera-factura.md",
                titulo="Crear tu primera factura",
                vigente=True,
                frases_obsoletas=[],
                texto_vigente=(
                    "Revisa el NIF en **Configuración > Empresa**. Entra en **Ventas > Facturas**, pulsa "
                    "**Nueva factura** y, si hay un error, usa **Más acciones > Rectificar**."
                ),
                notas_que_lo_cambian=[],
            ),
            ArticuloVigente(
                archivo="04-enviar-una-factura-por-correo.md",
                titulo="Enviar una factura por correo",
                vigente=False,
                frases_obsoletas=["Más acciones > Enviar por correo"],
                texto_vigente="Entra en **Ventas > Facturas**, abre la factura y pulsa **Enviar**.",
                notas_que_lo_cambian=["nota-2-nuevo-envio-de-facturas.md"],
            ),
        ],
        funciones_restringidas=[
            FuncionRestringida(
                nombre="Facturas recurrentes",
                plan="Pro",
                limites=["No se puede pausar una recurrente"],
                palabras_clave=["recurrente", "recurrentes"],
            )
        ],
        rutas_validas=["configuración > empresa", "más acciones > rectificar", "ventas > facturas"],
        rutas_obsoletas=["más acciones > enviar por correo"],
    )


class ModeloFalsoConocimiento:
    """Responde como lo haría el modelo: corrige la ayuda 04 y deja vigentes las demás."""

    def pedir(self, *, tarea, sistema, usuario, esquema):
        from cuadra.conocimiento import ArticuloVigente, FuncionRestringida, Restricciones

        if tarea == "conocimiento_restricciones":
            return Restricciones(
                funciones=[
                    FuncionRestringida(
                        nombre="Facturas recurrentes", plan="Pro",
                        limites=["No se puede pausar"], palabras_clave=["recurrente", "recurrentes"],
                    )
                ]
            )
        if "04-enviar-una-factura-por-correo.md" in usuario:
            return ArticuloVigente(
                archivo="da igual", titulo="Enviar una factura por correo", vigente=False,
                frases_obsoletas=["Pulsa **Más acciones > Enviar por correo**."],
                texto_vigente="Entra en **Ventas > Facturas**, abre la factura y pulsa **Enviar**.",
                notas_que_lo_cambian=["nota-2-nuevo-envio-de-facturas.md"],
            )
        return ArticuloVigente(
            archivo="da igual", titulo="Sin cambios", vigente=True, frases_obsoletas=[],
            texto_vigente="texto que el código debe ignorar", notas_que_lo_cambian=[],
        )


@pytest.fixture
def modelo_falso_conocimiento():
    return ModeloFalsoConocimiento()


class ModeloEspia:
    """Guarda lo último que se le pidió y devuelve siempre el mismo correo."""

    def __init__(self):
        self.ultimo_usuario = self.ultimo_sistema = self.ultima_tarea = None

    def pedir(self, *, tarea, sistema, usuario, esquema):
        from cuadra.redaccion import Correo

        self.ultima_tarea, self.ultimo_sistema, self.ultimo_usuario = tarea, sistema, usuario
        return Correo(
            asunto="Tu primer cliente en Cuadra",
            cuerpo="Hola, {nombre}. Entra en **Ventas > Facturas** y pulsa **Nueva factura**.",
            paso_siguiente="Crear cliente",
            ruta_menu="Ventas > Facturas",
            articulo_fuente="01-crear-tu-primera-factura.md",
        )


@pytest.fixture
def modelo_espia():
    return ModeloEspia()


class ModeloGuion:
    """Devuelve, en orden, los correos y veredictos que se le dan. Sirve para probar reintentos."""

    def __init__(self, correos, veredictos=None, error=None):
        self.correos, self.veredictos, self.error = list(correos), list(veredictos or []), error
        self.usuarios_de_redaccion = []
        self.llamadas_reales = 0

    def pedir(self, *, tarea, sistema, usuario, esquema):
        from cuadra.verificacion import Veredicto

        if self.error:
            raise self.error
        if tarea == "redaccion":
            self.usuarios_de_redaccion.append(usuario)
            return self.correos.pop(0)
        if self.veredictos:
            return self.veredictos.pop(0)
        return Veredicto(respaldado=True, responde_al_paso=True, tono_adecuado=True, un_solo_paso=True, motivos=[])
