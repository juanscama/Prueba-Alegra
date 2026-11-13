from cuadra.bandeja import armar_bandeja, armar_cola_revision
from cuadra.estado import calcular_estado
from cuadra.experimento import asignar
from cuadra.redaccion import Correo, variantes_posibles
from cuadra.verificacion import VarianteProcesada

CORREO = Correo(
    asunto="Tu siguiente paso, {nombre}",
    cuerpo="Hola, {nombre}. Entra en **Ventas > Facturas**.",
    paso_siguiente="x", ruta_menu="Ventas > Facturas", articulo_fuente="01-crear-tu-primera-factura.md",
)
EN_REVISION = "sin_cliente|peluquería|rezagado"


def procesadas_de_prueba(datos):
    resultado = {}
    for v in variantes_posibles(datos.contactos):
        aprobada = v.clave != EN_REVISION
        resultado[v.clave] = VarianteProcesada(
            variante=v, correo=CORREO, estado="aprobada" if aprobada else "revision",
            motivos=[] if aprobada else ["R3: ruta que no existe"], intentos=1 if aprobada else 2,
        )
    return resultado


def test_bandeja_solo_tratamiento_y_aprobadas(datos):
    asignacion = asignar(calcular_estado(datos))
    b = armar_bandeja(asignacion, datos.contactos, procesadas_de_prueba(datos))
    tratamiento = asignacion[asignacion.grupo == "tratamiento"]
    control = set(asignacion[asignacion.grupo == "control"].id_contacto)
    assert not set(b.id_contacto) & control
    assert b.id_contacto.is_unique and (b.variante != EN_REVISION).all()
    actividad = datos.contactos.set_index("id_contacto").actividad
    en_revision = tratamiento[
        (tratamiento.paso == "sin_cliente") & (tratamiento.tramo == "rezagado")
        & (tratamiento.id_contacto.map(actividad) == "peluquería")
    ]
    assert len(en_revision) > 0 and len(b) == len(tratamiento) - len(en_revision)


def test_bandeja_personaliza_y_ordena(datos):
    b = armar_bandeja(asignar(calcular_estado(datos)), datos.contactos, procesadas_de_prueba(datos))
    assert not b.cuerpo.str.contains("{nombre}", regex=False).any()
    assert not b.asunto.str.contains("{nombre}", regex=False).any()
    fila = b.iloc[0]
    assert fila.nombre in fila.cuerpo and fila.email.endswith("@correo.example")
    assert b.tramo.tolist() == sorted(b.tramo.tolist())            # «reciente» antes que «rezagado»
    recientes = b[b.tramo == "reciente"].dias_quieto.tolist()
    assert recientes == sorted(recientes)
    assert list(b.columns) == [
        "id_contacto", "email", "nombre", "asunto", "cuerpo", "paso", "tramo", "dias_quieto",
        "variante", "fecha_entrada",
    ]


def test_cola_de_revision_cuenta_personas(datos):
    asignacion = asignar(calcular_estado(datos))
    cola = armar_cola_revision(asignacion, datos.contactos, procesadas_de_prueba(datos))
    assert cola.variante.tolist() == [EN_REVISION]
    assert cola.personas_sin_correo.iloc[0] > 0 and "R3" in cola.motivos.iloc[0]
