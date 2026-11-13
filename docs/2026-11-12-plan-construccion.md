# Flujo de activación Cuadra: plan de construcción

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** un comando que lee los CSV de Cuadra, detecta a quién se le debe escribir, redacta y verifica
correos con Claude, deja una bandeja de salida con grupo de control y permite medir el resultado; más un
panel web local.

**Arquitectura:** paquete Python `cuadra` con un módulo por etapa; cada etapa recibe y devuelve
DataFrames u objetos Pydantic y `flujo.py` las encadena y escribe en `salida/`. Toda llamada al modelo
pasa por `cuadra/modelo.py`, que guarda cada respuesta en `cache/` para poder repetir la corrida sin red.
El panel solo lee `salida/`.

**Tecnología:** Python 3.12 con `uv`, pandas, pydantic, SDK `anthropic`, python-dotenv, streamlit, pytest.

**Diseño:** `docs/2026-11-12-diseno-flujo-activacion.md`

## Restricciones globales

- Python 3.12 fijado en `pyproject.toml`; entorno virtual fuera del volumen exFAT:
  `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/cuadra"` antes de cualquier `uv`.
- `.gitignore` incluye `._*`, `.env`, `__pycache__/`, `.pytest_cache/`. `git config core.fileMode false`.
- Dependencias permitidas: las de «Tecnología». Sin scipy (se usa `statistics.NormalDist`), sin
  bibliotecas de gráficos aparte de las que trae streamlit.
- Nombres de módulos, funciones, columnas y archivos en español, sin tildes en identificadores.
- Las pruebas nunca usan la red ni la clave: usan un cliente falso o el caché.
- Modelo por defecto `claude-opus-5-5`, leído de la variable `CUADRA_MODELO`. Sin sufijos de fecha.
- Valores fijos: fecha de corrida `2026-10-31`; atascado = 3 días o más sin eventos; `reciente` = 3 a 14
  días; `rezagado` = 15 o más; semilla `"cuadra-2026-10"`; reparto 0.5; ventana de medición 14 días;
  cuerpo de correo ≤ 900 caracteres; asunto ≤ 60.
- Todo dato simulado lleva `SIMULADO` en el nombre del archivo y una columna `simulado`.
- Un commit por tarea como mínimo, mensaje en español (`feat: …`, `test: …`, `docs: …`).

## Foco de revisión

Condiciones que el diseño implica y que rompen el programa con más probabilidad; cada una tiene su prueba
en la tarea indicada.

1. Hay archivos `._*.csv` de macOS en `datos/` o un CSV con BOM: la ingesta los ignora o los lee bien
   (Tarea 1).
2. Se corre con otra fecha (por ejemplo `2026-09-15`): los eventos posteriores no cuentan y quien aún no
   se había registrado no aparece (Tarea 3).
3. El modelo devuelve un cuerpo sin `{nombre}`, con otras llaves o con la ruta escrita como
   `Ventas>Facturas` o `Ventas › Facturas`: la verificación lo rechaza o lo normaliza, y nada lanza
   `KeyError` (Tareas 7 y 8).
4. No hay clave y el caché está vacío o incompleto: la corrida termina, la bandeja queda con lo que hay y
   el resumen dice cuántas variantes fueron a revisión (Tarea 8).
5. El panel se abre antes de correr el flujo o falta un archivo de `salida/`: muestra un aviso con el
   comando a ejecutar, sin traza de error (Tarea 11).

---

### Task 1: Proyecto base e ingesta

**Archivos:**
- Crear: `pyproject.toml`, `.gitignore`, `.env.example`, `cuadra/__init__.py`, `cuadra/config.py`,
  `cuadra/ingesta.py`, `tests/conftest.py`, `tests/test_ingesta.py`
- Mover: `material/datos` → `datos`, `material/ayudas` → `ayudas`, `material/notas` → `notas`,
  `material/ENUNCIADO.md` → `ENUNCIADO.md`; borrar `material/` y los `._*`.

**Interfaces — produce:**
- `config.py`: `RAIZ`, `DIR_DATOS`, `DIR_AYUDAS`, `DIR_NOTAS`, `DIR_CACHE`, `DIR_SALIDA` (Path);
  `FECHA_CORRIDA = date(2026, 10, 31)`; `DIAS_ATASCADO = 3`; `DIAS_RECIENTE_MAX = 14`;
  `SEMILLA = "cuadra-2026-10"`; `PROPORCION_TRATAMIENTO = 0.5`; `VENTANA_DIAS = 14`;
  `MODELO = os.environ.get("CUADRA_MODELO", "claude-opus-5-5")`;
  `PASOS = ["registro", "configuro_empresa", "creo_cliente", "emitio_primera_factura", "emitio_5_facturas"]`.
- `ingesta.py`: `@dataclass Datos(contactos, eventos, pagos)` (DataFrames; fechas como `datetime.date`);
  `cargar(dir_datos: Path = DIR_DATOS) -> Datos`; `class ErrorDatos(ValueError)`.
- `tests/conftest.py`: fixture `datos` (carga real, alcance de sesión).

- [ ] **Paso 1:** `git init`, `git config core.fileMode false`, mover el material, crear `pyproject.toml`
  (nombre `cuadra`, `requires-python = ">=3.12"`, script `cuadra = "cuadra.cli:main"`), `.gitignore`,
  `.env.example` con `ANTHROPIC_API_KEY=` y `CUADRA_MODELO=claude-opus-5-5`. `uv sync`.
- [ ] **Paso 2:** escribir pruebas que fallan en `tests/test_ingesta.py`:

```python
def test_carga_real(datos):
    assert len(datos.contactos) == 1500 and datos.contactos.id_contacto.is_unique
    assert len(datos.eventos) == 4284 and len(datos.pagos) == 205

def test_ignora_archivos_de_macos_y_bom(tmp_path):  # copia datos/, añade ._pagos.csv basura y BOM a pagos.csv
    assert len(cargar(tmp_path).pagos) == 205

@pytest.mark.parametrize("romper, texto", [
    (quitar_columna("canal"), "canal"),
    (duplicar_id("C00001"), "C00001"),
    (evento_huerfano("C99999"), "C99999"),
    (evento_desconocido("bailo"), "bailo"),
    (paso_sin_anterior("C00003", "creo_cliente"), "C00003"),
])
def test_rechaza_datos_rotos(tmp_path, romper, texto):
    with pytest.raises(ErrorDatos, match=texto): cargar(romper(tmp_path))
```

- [ ] **Paso 3:** `uv run pytest tests/test_ingesta.py -v` → falla por importación.
- [ ] **Paso 4:** implementar `cargar` (lectura con `encoding="utf-8-sig"`, solo los tres nombres exactos).
- [ ] **Paso 5:** `uv run pytest tests/test_ingesta.py -v` → pasa.
- [ ] **Paso 6:** commit `feat: proyecto base e ingesta validada`.

### Task 2: Diagnóstico

**Archivos:** crear `cuadra/diagnostico.py`, `tests/test_diagnostico.py`.

**Interfaces — consume:** `Datos`. **Produce:**
- `embudo(datos) -> DataFrame[paso, contactos, pct_registro]` (cinco pasos más fila `pago`).
- `embudo_por(datos, columnas: list[str]) -> DataFrame` (una fila por grupo: `n`, tasa de cada paso sobre
  registro, `pct_pago`, y `pct_config_a_cliente`). Admite `"mes_registro"` como columna derivada.
- `tiempos_entre_pasos(datos) -> DataFrame[desde, hasta, n, mediana, p90, maximo]` en días.
- `escribir_diagnostico(datos, ruta: Path) -> None` (Markdown con las tres tablas y la frase del hallazgo
  principal calculada, no escrita a mano).

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_embudo(datos):
    assert embudo(datos).contactos.tolist() == [1500, 1200, 773, 548, 263, 205]

def test_fuga_autonomo_organico(datos):
    t = embudo_por(datos, ["canal", "segmento"]).set_index(["canal", "segmento"])
    assert t.loc[("organico", "autonomo"), "n"] == 590
    assert round(t.loc[("organico", "autonomo"), "pct_config_a_cliente"], 2) == 0.42
    assert t.drop(("organico", "autonomo")).pct_config_a_cliente.min() >= 0.71

def test_tiempos(datos):
    assert tiempos_entre_pasos(datos).maximo.tolist()[:3] == [1, 3, 4]
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** commit `feat: diagnóstico del embudo`.

### Task 3: Estado de cada persona

**Archivos:** crear `cuadra/estado.py`, `tests/test_estado.py`.

**Interfaces — produce:**
- `calcular_estado(datos, fecha: date = FECHA_CORRIDA) -> DataFrame[id_contacto, paso, dias_quieto, tramo, elegible]`.
  Solo personas registradas hasta `fecha`, sin primera factura y sin pago a esa fecha; los eventos y pagos
  posteriores a `fecha` no existen. `paso` ∈ `sin_configurar | sin_cliente | sin_factura`; `tramo` ∈
  `en_ventana | reciente | rezagado`; `elegible = tramo != "en_ventana"`.
- `pagadores_sin_factura(datos, fecha: date = FECHA_CORRIDA) -> list[str]`.

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_conteos_al_31_de_octubre(datos):
    e = calcular_estado(datos)
    assert len(e) == 944
    assert e.paso.value_counts().to_dict() == {"sin_cliente": 427, "sin_configurar": 292, "sin_factura": 225}
    assert e.tramo.value_counts().to_dict() == {"rezagado": 824, "reciente": 88, "en_ventana": 32}
    assert e.elegible.sum() == 912
    assert len(e[(e.paso == "sin_cliente") & (e.tramo == "reciente")]) == 48

def test_pagadores_sin_factura(datos):
    assert pagadores_sin_factura(datos) == ["C00014", "C00108", "C00265", "C00625",
                                            "C00629", "C00981", "C01006", "C01443"]

def test_otra_fecha_no_ve_el_futuro(datos):
    e = calcular_estado(datos, date(2026, 9, 15))
    registro = datos.contactos.set_index("id_contacto").fecha_registro
    assert (registro[e.id_contacto] <= date(2026, 9, 15)).all()
    assert (e.dias_quieto >= 0).all()

def test_limites_de_tramo():  # datos mínimos fabricados: 2, 3, 14 y 15 días quieto
    assert tramos == ["en_ventana", "reciente", "reciente", "rezagado"]
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** commit `feat: estado y tramo de cada persona`.

### Task 4: Asignación al experimento

**Archivos:** crear `cuadra/experimento.py`, `tests/test_experimento.py`.

**Interfaces — produce:**
- `grupo(id_contacto: str, semilla: str = SEMILLA, proporcion: float = PROPORCION_TRATAMIENTO) -> str`:
  `int(sha256(f"{semilla}:{id_contacto}").hexdigest()[:8], 16) / 0xFFFFFFFF < proporcion` →
  `"tratamiento"`, si no `"control"`.
- `asignar(estado, fecha: date = FECHA_CORRIDA) -> DataFrame` = filas elegibles de `estado` más `grupo` y
  `fecha_entrada`.
- `equilibrio(asignacion, contactos, por: str) -> DataFrame[<por>, tratamiento, control, pct_tratamiento]`
  (`por` ∈ `paso | tramo | canal | segmento`).
- `efecto_minimo_detectable(n_t: int, n_c: int, base: float, alfa: float = 0.05, potencia: float = 0.8) -> float`
  = `(z(1-alfa/2) + z(potencia)) * sqrt(base*(1-base)*(1/n_t + 1/n_c))`.

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_determinista_y_estable_entre_fechas(datos):
    a = asignar(calcular_estado(datos)); b = asignar(calcular_estado(datos))
    assert a.grupo.tolist() == b.grupo.tolist()
    assert grupo("C00001") == grupo("C00001")

def test_tamano_y_reparto(datos):
    a = asignar(calcular_estado(datos))
    assert len(a) == 912 and 0.45 <= (a.grupo == "tratamiento").mean() <= 0.55
    assert (a.fecha_entrada == date(2026, 10, 31)).all()

def test_equilibrio_por_segmento(datos):
    eq = equilibrio(asignar(calcular_estado(datos)), datos.contactos, "segmento")
    assert eq.pct_tratamiento.between(0.40, 0.60).all()

def test_efecto_minimo():
    assert efecto_minimo_detectable(456, 456, 0.02) == pytest.approx(0.026, abs=0.001)
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** commit `feat: asignación determinista a tratamiento y control`.

### Task 5: Cliente del modelo con caché

**Archivos:** crear `cuadra/modelo.py`, `tests/test_modelo.py`.

**Interfaces — produce:**
- `class SinCache(Exception)`, `class Rechazo(Exception)`.
- `hay_clave() -> bool` (tras `load_dotenv()`: `ANTHROPIC_API_KEY` o `ANTHROPIC_AUTH_TOKEN` no vacíos).
- `class Modelo(dir_cache: Path = DIR_CACHE, modo: str = "auto", forzar: bool = False, cliente=None)`;
  `modo` ∈ `auto | repeticion | vivo`; `auto` = `vivo` si `hay_clave()`, si no `repeticion`. Atributo
  `llamadas_reales: int`.
- `Modelo.pedir(*, tarea: str, sistema: str, usuario: str, esquema: type[BaseModel]) -> BaseModel`.
  Clave = sha256 del JSON ordenado de `{modelo, tarea, sistema, usuario, esquema.model_json_schema()}`.
  Archivo `cache/<tarea>/<clave[:16]>.json` con `{"peticion": …, "respuesta": …}`, JSON indentado y
  `ensure_ascii=False`. Si existe y no `forzar`: lo devuelve validado. Si no existe: en `repeticion`
  lanza `SinCache`; en `vivo` llama, guarda y devuelve.
- Llamada real, tal cual documenta el SDK:

```python
r = self.cliente.messages.parse(
    model=MODELO, max_tokens=16000, system=sistema,
    messages=[{"role": "user", "content": usuario}], output_format=esquema,
)
if r.stop_reason == "refusal" or r.parsed_output is None: raise Rechazo(...)
```

  El cliente se crea con `anthropic.Anthropic()` solo al hacer la primera llamada real. No se envían
  `thinking`, `temperature` ni `budget_tokens`. Al implementar, comprobar si el SDK instalado acepta en
  `parse` el parámetro `output_config={"effort": "medium"}`; si lo acepta, enviarlo; si no, omitirlo.
  Lo mismo con el respaldo ante rechazos (`client.beta.messages.parse` con
  `betas=["server-side-fallback-2026-07-01"]` y `fallbacks="default"`): usarlo solo si el SDK instalado lo
  admite en `parse`; en caso contrario, `Rechazo` manda la variante a revisión.

- [ ] **Paso 1:** pruebas que fallan, con cliente falso (`SimpleNamespace` cuyo `messages.parse` cuenta
  llamadas y devuelve `parsed_output` y `stop_reason`):

```python
def test_repeticion_sin_cache_lanza(tmp_path): ...            # pytest.raises(SinCache)
def test_vivo_guarda_y_no_repite(tmp_path): ...               # dos pedir() iguales → 1 llamada, 1 archivo
def test_cambiar_usuario_cambia_clave(tmp_path): ...          # 2 archivos
def test_forzar_vuelve_a_llamar(tmp_path): ...                # 2 llamadas
def test_rechazo(tmp_path): ...                               # stop_reason="refusal" → Rechazo, sin archivo
def test_cache_legible(tmp_path): ...                         # el archivo contiene "ñ" sin escapar
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** commit `feat: cliente del modelo con caché y modo repetición`.

### Task 6: Base de conocimiento vigente

**Archivos:** crear `cuadra/conocimiento.py`, `tests/test_conocimiento.py`; ampliar `tests/conftest.py`.

**Interfaces — produce:**
- `ArticuloVigente(archivo: str, titulo: str, vigente: bool, frases_obsoletas: list[str], texto_vigente: str, notas_que_lo_cambian: list[str])`.
- `FuncionRestringida(nombre: str, plan: str, limites: list[str], palabras_clave: list[str])`.
- `BaseVigente(articulos: list[ArticuloVigente], funciones_restringidas: list[FuncionRestringida], rutas_validas: list[str], rutas_obsoletas: list[str])`.
- `normalizar_ruta(texto: str) -> str`: minúsculas, `›`/`>`/`→` a ` > ` con un espacio a cada lado, sin
  negritas ni espacios dobles.
- `extraer_rutas(texto: str) -> set[str]`: fragmentos en negrita que contienen `>`, normalizados.
- `construir_base(modelo: Modelo, dir_ayudas=DIR_AYUDAS, dir_notas=DIR_NOTAS) -> BaseVigente`: una
  llamada por artículo (`tarea="conocimiento_articulo"`, recibe el artículo y las tres notas; devuelve
  `ArticuloVigente`) y una sobre las notas (`tarea="conocimiento_restricciones"`; devuelve la lista de
  `FuncionRestringida`). `rutas_validas` = rutas de todos los `texto_vigente` y de las notas;
  `rutas_obsoletas` = rutas de los artículos originales que ya no están en las válidas. Código, no modelo.
- Fixture `base_de_prueba` en `conftest.py`, escrita a mano: ayuda 04 no vigente con frase obsoleta
  `"Más acciones > Enviar por correo"`; rutas válidas incluyen `"ventas > facturas"`,
  `"configuración > empresa"`, `"más acciones > rectificar"`; función restringida
  `nombre="Facturas recurrentes"`, `plan="Pro"`, `palabras_clave=["recurrente", "recurrentes"]`.

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_normalizar_ruta():
    assert normalizar_ruta("**Ventas>Facturas**") == normalizar_ruta("Ventas › Facturas") == "ventas > facturas"

def test_rutas_validas_y_obsoletas(modelo_falso_conocimiento):  # responde ayuda 04 corregida, resto igual
    b = construir_base(modelo_falso_conocimiento)
    assert "más acciones > enviar por correo" in b.rutas_obsoletas
    assert "más acciones > rectificar" in b.rutas_validas
    assert "ventas > facturas recurrentes > nueva recurrente" in b.rutas_validas
    assert [a.archivo for a in b.articulos if not a.vigente] == ["04-enviar-una-factura-por-correo.md"]
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar, con el prompt de sistema que pide: comparar,
  citar frases obsoletas textualmente, reescribir solo lo que la nota cambia, no inventar.
- [ ] **Paso 4:** correr → pasa. **Paso 5:** commit `feat: base de conocimiento vigente`.

### Task 7: Redacción por variante

**Archivos:** crear `cuadra/redaccion.py`, `tests/test_redaccion.py`.

**Interfaces — produce:**
- `@dataclass(frozen=True) Variante(paso: str, actividad: str, tramo: str)` con `clave -> str`
  (`"sin_cliente|peluquería|reciente"`).
- `Correo(asunto: str, cuerpo: str, paso_siguiente: str, ruta_menu: str, articulo_fuente: str)`.
- `variantes_posibles(contactos) -> list[Variante]`: 3 pasos × actividades presentes × 2 tramos
  (`reciente`, `rezagado`), ordenadas.
- `segmento_de(contactos) -> dict[str, str]` (actividad → segmento).
- `redactar(variante, base, modelo, segmento: str, motivo_rechazo: str | None = None) -> Correo`
  (`tarea="redaccion"`). El prompt fija: español de España, trato de tú, dirigido a un autónomo o una pyme
  de ese oficio, un solo paso siguiente, ruta de menú literal de la base vigente, campo `{nombre}` una vez
  en el saludo, sin precios ni promesas, sin funciones restringidas, cuerpo ≤ 900 caracteres, asunto ≤ 60.
  Objetivo por paso: `sin_configurar` → NIF y dirección fiscal en Configuración > Empresa;
  `sin_cliente` → crear el primer cliente desde Nueva factura con un ejemplo del oficio;
  `sin_factura` → emitir la primera factura, con mención al borrador. `rezagado` cambia el tono, no las
  instrucciones.
- `personalizar(correo: Correo, nombre: str) -> tuple[str, str]` (asunto, cuerpo) con
  `str.replace("{nombre}", nombre)`; nunca `str.format`.

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_108_variantes(datos):
    v = variantes_posibles(datos.contactos)
    assert len(v) == 108 and len({x.clave for x in v}) == 108

def test_segmento_de(datos):
    s = segmento_de(datos.contactos)
    assert s["peluquería"] == "autonomo" and s["restaurante"] == "pyme" and len(s) == 18

def test_personalizar_no_rompe_con_llaves():
    c = Correo(asunto="Tu primera factura", cuerpo="Hola, {nombre}. Usa {esto} tal cual.", ...)
    assert personalizar(c, "Álvaro")[1] == "Hola, Álvaro. Usa {esto} tal cual."

def test_prompt_lleva_motivo_de_rechazo(base_de_prueba, modelo_espia):
    redactar(Variante("sin_cliente", "peluquería", "reciente"), base_de_prueba, modelo_espia, "autonomo",
             motivo_rechazo="ruta inexistente")
    assert "ruta inexistente" in modelo_espia.ultimo_usuario
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** commit `feat: redacción de correos por variante`.

### Task 8: Verificación, bandeja y comando `correr`

**Archivos:** crear `cuadra/verificacion.py`, `cuadra/bandeja.py`, `cuadra/flujo.py`, `cuadra/cli.py`,
`tests/test_verificacion.py`, `tests/test_bandeja.py`, `tests/test_flujo.py`.

**Interfaces — produce:**
- `verificar_reglas(correo, base) -> list[str]` (motivos; lista vacía = pasa). Reglas, cada una con su
  código al inicio del motivo:
  `R1` el cuerpo contiene `{nombre}` exactamente una vez; `R2` no hay otras llaves `{…}`;
  `R3` toda ruta con `>` en cuerpo y `ruta_menu` (normalizada) está en `base.rutas_validas`;
  `R4` ninguna `frase_obsoleta` ni `ruta_obsoleta` aparece (comparación sin mayúsculas, rutas normalizadas);
  `R5` ninguna `palabra_clave` de función restringida; `R6` sin `€`, `%`, «descuento», «gratis»,
  «oferta», «promoción»; `R7` cuerpo ≤ 900 y asunto ≤ 60 caracteres.
- `Veredicto(respaldado: bool, responde_al_paso: bool, tono_adecuado: bool, un_solo_paso: bool, motivos: list[str])`.
- `juzgar(correo, variante, base, modelo) -> Veredicto` (`tarea="juez"`).
- `VarianteProcesada(variante: Variante, correo: Correo | None, estado: str, motivos: list[str], intentos: int)`,
  `estado` ∈ `aprobada | revision`.
- `procesar(variante, base, modelo, segmento) -> VarianteProcesada`: redacta, aplica reglas y luego juez;
  ante rechazo redacta una segunda vez con los motivos; segundo rechazo → `revision`. `SinCache` →
  `revision` con motivo `"sin caché y sin clave"`; `Rechazo` → `revision` con motivo `"el modelo declinó"`.
- `armar_bandeja(asignacion, contactos, procesadas: dict[str, VarianteProcesada]) -> DataFrame[id_contacto, email, nombre, asunto, cuerpo, paso, tramo, dias_quieto, variante, fecha_entrada]`:
  solo `tratamiento` con variante aprobada; orden `reciente` primero y luego `dias_quieto` ascendente.
- `flujo.correr(fecha=FECHA_CORRIDA, modo="auto", forzar=False, limite_variantes: int | None = None, dir_salida=DIR_SALIDA) -> dict`
  ejecuta las etapas 1 a 8 del diseño (variantes en paralelo con 4 hilos) y escribe: `diagnostico.md`,
  `estado.csv`, `asignacion_experimento.csv`, `base_vigente.json`, `variantes.json`, `bandeja_salida.csv`,
  `cola_revision.csv`, `pagadores_sin_factura.csv`, `resumen.json`. Devuelve el resumen: `fecha`, `modo`,
  `elegibles`, `tratamiento`, `control`, `variantes_aprobadas`, `variantes_en_revision`,
  `correos_en_bandeja`, `personas_sin_correo_por_revision`, `llamadas_reales`, `efecto_minimo_detectable`.
- Uso diario: `correr(..., respetar_enviados=False)`. Con `True`, excluye de la bandeja los ids presentes
  en `salida/enviados.csv` y añade al final los nuevos (`id_contacto, fecha_entrada, variante`). Por
  defecto no se usa y la corrida regenera todo.
- `cli.main()` con argparse: `cuadra correr [--fecha AAAA-MM-DD] [--modo auto|repeticion|vivo] [--forzar] [--limite-variantes N] [--respetar-enviados]`
  imprime el resumen en una tabla corta. Subcomandos `medir`, `simular` y `panel` se añaden en las
  tareas 10 y 11.

- [ ] **Paso 1:** pruebas que fallan:

```python
BUENO = Correo(asunto="Tu primer cliente en Cuadra",
               cuerpo="Hola, {nombre}. Entra en **Ventas > Facturas**, pulsa Nueva factura y crea tu cliente.",
               paso_siguiente="Crear cliente", ruta_menu="Ventas > Facturas", articulo_fuente="01-crear-tu-primera-factura.md")

def test_bueno_pasa(base_de_prueba): assert verificar_reglas(BUENO, base_de_prueba) == []

@pytest.mark.parametrize("cuerpo, codigo", [
    ("Hola, {nombre}. Pulsa **Más acciones > Enviar por correo**.", "R4"),
    ("Hola, {nombre}. Activa las facturas recurrentes.", "R5"),
    ("Hola, {nombre}. Tienes un 20% de descuento.", "R6"),
    ("Hola. Entra en **Ventas > Facturas**.", "R1"),
    ("Hola, {nombre} de {empresa}.", "R2"),
    ("Hola, {nombre}. Entra en **Ventas > Presupuestos**.", "R3"),
    ("Hola, {nombre}. " + "x" * 900, "R7"),
])
def test_defectos_sembrados(base_de_prueba, cuerpo, codigo):
    motivos = verificar_reglas(BUENO.model_copy(update={"cuerpo": cuerpo}), base_de_prueba)
    assert any(m.startswith(codigo) for m in motivos)

def test_ruta_con_otra_tipografia_pasa(base_de_prueba):   # "Ventas›Facturas"
def test_reintento_y_revision(base_de_prueba): ...         # modelo falso: malo, malo → revision, intentos == 2
def test_reintento_recupera(base_de_prueba): ...           # malo, bueno → aprobada, intentos == 2
def test_bandeja_solo_tratamiento_y_aprobadas(datos): ...  # sin "{nombre}" en ningún cuerpo; ningún id de control
def test_respetar_enviados_no_repite(datos, tmp_path): ...  # segunda corrida con la opción → bandeja vacía
def test_flujo_sin_clave_ni_cache(tmp_path, monkeypatch):  # caché vacío, sin variables de clave
    r = correr(modo="repeticion", dir_salida=tmp_path)
    assert r["elegibles"] == 912 and r["correos_en_bandeja"] == 0 and r["llamadas_reales"] == 0
    assert r["variantes_en_revision"] == 108
    assert (tmp_path / "cola_revision.csv").read_text().count("sin caché y sin clave") == 108
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** `uv run pytest -v` → todo pasa.
- [ ] **Paso 5:** `uv run cuadra correr --modo repeticion` → termina sin error e imprime 912 elegibles y
  0 correos.
- [ ] **Paso 6:** commit `feat: verificación, bandeja de salida y comando correr`.

### Task 9: Corrida real y revisión humana

Requiere la clave de API de la persona candidata en `.env` y su visto bueno al costo (diseño, apartado 8).

**Archivos:** se generan `cache/**`, `salida/**`; crear `tests/test_salida_real.py`.

- [ ] **Paso 1:** `uv run cuadra correr --modo vivo --limite-variantes 6`. Leer los 6 correos y la base
  vigente. Ajustar prompts si la redacción o el juez fallan; repetir con `--forzar` solo esas variantes.
- [ ] **Paso 2:** `uv run cuadra correr --modo vivo` (las 108). Anotar `llamadas_reales` y el costo que
  muestre la consola de Anthropic.
- [ ] **Paso 3:** escribir y pasar pruebas sobre el caché real, en modo repetición:

```python
def test_corrida_real_en_repeticion(tmp_path):
    r = correr(modo="repeticion", dir_salida=tmp_path)
    assert r["llamadas_reales"] == 0 and r["variantes_aprobadas"] + r["variantes_en_revision"] == 108
    assert r["variantes_aprobadas"] >= 100
    b = pd.read_csv(tmp_path / "bandeja_salida.csv")
    assert not b.cuerpo.str.contains("{nombre}", regex=False).any()
    assert not b.cuerpo.str.contains("Más acciones > Enviar", case=False, regex=False).any()
    assert not b.cuerpo.str.contains("recurrente", case=False).any()

def test_base_real(tmp_path):
    base = BaseVigente.model_validate_json((DIR_SALIDA / "base_vigente.json").read_text())
    assert [a.archivo for a in base.articulos if not a.vigente] == ["04-enviar-una-factura-por-correo.md"]
    assert any(f.plan == "Pro" for f in base.funciones_restringidas)
```

- [ ] **Paso 4:** revisión humana: la persona candidata lee una muestra de 10 correos de
  `salida/bandeja_salida.csv` y toda `salida/cola_revision.csv`. Corregir lo que señale.
- [ ] **Paso 5:** commit `feat: corrida real con caché de respuestas y salidas`.

### Task 10: Medición, simulador y prueba A/A

**Archivos:** crear `cuadra/medicion.py`, `cuadra/simulador.py`, `tests/test_medicion.py`; modificar
`cuadra/cli.py`.

**Interfaces — produce:**
- `ResultadoExperimento` (dataclass): `n_t, conv_t, tasa_t, n_c, conv_c, tasa_c, diferencia, ic95: tuple[float, float], valor_p, decision`
  (`"extender"` si `ic95[0] > 0`, si no `"iterar"`), `simulado: bool`.
- `comparar(n_t, conv_t, n_c, conv_c, simulado=False) -> ResultadoExperimento`: intervalo con error
  estándar no agrupado; valor p con prueba z de dos proporciones agrupada; si el error estándar es 0,
  `valor_p = 1.0` e `ic95 = (0.0, 0.0)`.
- `medir(asignacion, eventos, ventana_dias=VENTANA_DIAS) -> tuple[ResultadoExperimento, DataFrame]`:
  conversión = `emitio_primera_factura` con fecha en `(fecha_entrada, fecha_entrada + ventana]`; el
  DataFrame repite el cálculo por `paso` y por `tramo`. `simulado=True` si `eventos` trae esa columna.
- `prueba_aa(datos) -> ResultadoExperimento`: registrados en julio y agosto, grupos con `grupo()`,
  conversión = emitió primera factura.
- `simular_eventos(asignacion, efecto: float, base: float = 0.02, semilla: int = 7) -> DataFrame[id_contacto, evento, fecha, simulado]`
  con `random.Random(semilla)`: control convierte con probabilidad `base`, tratamiento con `base + efecto`,
  fecha uniforme entre 1 y 14 días tras `fecha_entrada`.
- CLI: `cuadra simular --efecto 0.08 [--semilla 7]` escribe `salida/SIMULADO_eventos_posteriores.csv`;
  `cuadra medir --eventos RUTA` escribe `salida/resultado_experimento.json` (o
  `SIMULADO_resultado_experimento.json`) e imprime tasas, diferencia, intervalo, valor p y decisión.
  `correr` añade `salida/prueba_aa.json`.

- [ ] **Paso 1:** pruebas que fallan:

```python
def test_comparar_caso_a_mano():
    r = comparar(400, 40, 400, 20)
    assert r.diferencia == pytest.approx(0.05)
    assert r.ic95 == pytest.approx((0.01366, 0.08634), abs=1e-4)
    assert r.valor_p == pytest.approx(0.00726, abs=1e-4) and r.decision == "extender"

def test_sin_diferencia_itera():   assert comparar(400, 20, 400, 20).decision == "iterar"
def test_cero_conversiones():      assert comparar(400, 0, 400, 0).valor_p == 1.0

def test_simulado_queda_marcado_y_se_recupera_el_efecto(datos):
    a = asignar(calcular_estado(datos)); ev = simular_eventos(a, efecto=0.08)
    r, por_estrato = medir(a, ev)
    assert ev.simulado.all() and r.simulado and 0.03 < r.diferencia < 0.13 and r.decision == "extender"

def test_ventana(datos): ...       # una conversión el día 15 no cuenta; el día 14 sí
def test_aa(datos):
    r = prueba_aa(datos); assert r.n_t + r.n_c == 777
```

- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** `uv run cuadra simular --efecto 0.08 && uv run cuadra medir --eventos salida/SIMULADO_eventos_posteriores.csv`
  → imprime decisión `extender` y la palabra SIMULADO.
- [ ] **Paso 6:** commit `feat: medición del experimento, simulador y prueba A/A`.

### Task 11: Panel

**Archivos:** crear `panel/app.py`, `tests/test_panel.py`; modificar `cuadra/cli.py` (`cuadra panel`
ejecuta `streamlit run panel/app.py`).

Pestañas, en este orden: **Diagnóstico** (embudo en barras; tabla canal × segmento con la celda de
autónomo orgánico resaltada; tiempos entre pasos), **Base vigente** (los cinco artículos con estado; para
los no vigentes, frases obsoletas frente a texto vigente y nota de origen; funciones restringidas),
**Mensajes** (filtros por paso, actividad y tramo; correo final de una persona elegida; reglas y veredicto
del juez; cola de revisión; botón «Redactar en vivo» visible solo si `hay_clave()`), **Experimento**
(tamaños, equilibrio, efecto mínimo detectable, prueba A/A, resultado simulado con aviso visible
«SIMULADO»), **Qué no cubre** (texto del diseño, apartado 7). El panel no calcula nada que no esté ya en
`salida/`, salvo la redacción en vivo.

- [ ] **Paso 1:** pruebas que fallan:

```python
from streamlit.testing.v1 import AppTest

def test_panel_con_salida():
    at = AppTest.from_file("panel/app.py", default_timeout=30).run()
    assert not at.exception and len(at.tabs) == 5

def test_panel_sin_salida(tmp_path, monkeypatch):
    monkeypatch.setenv("CUADRA_DIR_SALIDA", str(tmp_path))
    at = AppTest.from_file("panel/app.py", default_timeout=30).run()
    assert not at.exception and "cuadra correr" in at.warning[0].value
```

  (`config.DIR_SALIDA` pasa a leer la variable `CUADRA_DIR_SALIDA` si existe.)
- [ ] **Paso 2:** correr → falla. **Paso 3:** implementar. **Paso 4:** correr → pasa.
- [ ] **Paso 5:** abrir `uv run cuadra panel`, recorrer las cinco pestañas y capturar una imagen de cada
  una para comprobar que se leen bien.
- [ ] **Paso 6:** commit `feat: panel web`.

### Task 12: README y entrega

**Archivos:** crear `README.md`.

- [ ] **Paso 1:** `README.md` con: qué hace en tres frases; cómo correrlo (clonar, `uv sync`,
  `uv run cuadra correr`, `uv run cuadra panel`); con y sin clave; qué encontré (hallazgos 1 y 2 del
  diseño con sus cifras); cómo sabría si funcionó (métrica, grupos, regla de decisión, comandos `simular`
  y `medir`); qué no cubre; herramientas usadas (Claude Code para construir, API de Claude en el flujo);
  estructura de carpetas.
- [ ] **Paso 2:** probar el README desde cero: clonar el repositorio en una carpeta temporal fuera del
  volumen, sin `.env`, seguir los pasos al pie de la letra. `uv run pytest` pasa y `uv run cuadra correr`
  produce la misma bandeja que la versionada (`diff` sin diferencias).
- [ ] **Paso 3:** commit `docs: README`.
- [ ] **Paso 4:** con confirmación de la persona candidata: crear el repositorio remoto y subirlo.

## Orden de recorte

Si el tiempo no alcanza, se recorta en este orden: `prueba_aa` (Tarea 10), botón «Redactar en vivo»
(Tarea 11), pestañas Base vigente y Qué no cubre (pasan al README), el reintento de `procesar` y la opción `--respetar-enviados` (Tarea 8).
No se recortan el juez, el simulador ni la Tarea 12, paso 2.
