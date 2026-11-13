# Diseño: flujo de activación «de registrarse a facturar» (Cuadra)

Fecha: 2026-11-12 · Estado: pendiente de aprobación

## 1. Intención

Reto técnico de Alegra (Growth con IA). Hay que entregar, en 72 horas, un flujo con IA que corra de punta
a punta y que haga que más personas registradas en Cuadra lleguen a emitir su primera factura, más una
respuesta concreta a «cómo sabrías si funcionó». Los evaluadores lo correrán en vivo durante una sesión de
60 minutos. Lo que funciona pesa más que lo que se explica.

Las reglas del reto están en dos documentos: `material/ENUNCIADO.md` (el caso) y
`reto_growth_ai_v2.pdf` (entregables, plazo, costo cero, sesión en vivo, repositorio con historial).

El entregable 2 (video de hasta 5 minutos) lo graba la persona candidata.

## 2. Lo que dicen los datos

Fecha del caso: 31 de octubre de 2026. 1500 registrados entre julio y octubre.

| Paso | Contactos | % del registro |
|---|---|---|
| registro | 1500 | 100% |
| configuro_empresa | 1200 | 80% |
| creo_cliente | 773 | 52% |
| emitio_primera_factura | 548 | 37% |
| emitio_5_facturas | 263 | 18% |
| pago | 205 | 14% |

Hallazgos que deciden el diseño:

1. **La fuga principal es «configuró empresa pero no creó cliente»** (427 personas), y está concentrada en
   un grupo: autónomos que llegan por canal orgánico. En ese grupo solo el 42% pasa de configurar a crear
   cliente; en todos los demás cruces de canal y segmento pasa entre el 72% y el 84%. Son 590 personas y
   solo el 15% factura.
2. **Quien avanza, avanza rápido; quien no, no vuelve solo.** Registro a configuración: máximo 1 día.
   Configuración a cliente: máximo 3 días. Cliente a primera factura: máximo 4 días. Nadie emitió su
   primera factura más de 8 días después de registrarse. La conversión natural de alguien que lleva 3 o
   más días quieto es del 0,15% en los 14 días siguientes (5 de 3249 observaciones en siete fechas de corte).
3. **Facturar predice pagar.** 197 de los 205 pagadores emitieron primera factura. El pago llega entre 3 y
   30 días después de la primera factura (mediana 15).
4. **`etapa_crm` no aporta información nueva:** PQL = facturó y no pagó; cliente = pagó; registrado = resto.
5. **La caída de octubre en pago y en 5 facturas es falta de maduración de la cohorte**, no un problema.
6. **La ayuda 04 (enviar factura por correo) está desactualizada** por la nota 2 de esta semana: el botón
   Enviar ya no está en Más acciones, el asunto se puede editar, el destinatario admite un solo correo y
   el XML se puede adjuntar. La nota 3 (facturas recurrentes) es solo para plan Pro y tiene límites. La
   ayuda 01 esconde un requisito: sin NIF y dirección fiscal no se puede emitir.
7. Datos limpios: sin vacíos, sin duplicados, sin ids huérfanos, sin pasos fuera de orden. Hay 8 pagadores
   que nunca facturaron; quedan fuera del flujo y se listan aparte.

Estado al 31 de octubre de las 944 personas que no han facturado ni pagado:

| Paso en el que están | Total | Quietos < 3 días | 3 a 14 días | 15 a 45 días | > 45 días |
|---|---|---|---|---|---|
| Solo registro | 292 | 8 | 22 | 74 | 188 |
| Configuró empresa | 427 | 11 | 48 | 109 | 259 |
| Creó cliente | 225 | 13 | 18 | 62 | 132 |

## 3. Objetivos, no objetivos y antiobjetivos

**Objetivos**

- Un comando corre todo el flujo sobre los CSV y deja resultados verificables en disco.
- Un panel web local muestra el diagnóstico, la base de conocimiento vigente, los mensajes y el experimento.
- Corre sin clave de API (modo repetición con respuestas guardadas) y con clave (modo en vivo).
- Ningún mensaje contiene instrucciones desactualizadas ni funciones que el destinatario no tiene.
- La medición está construida, no solo descrita: asignación a grupo de control, cálculo de resultado y
  regla de decisión.

**No objetivos**

- Envío real de correos (las direcciones son `@correo.example`). La salida es una bandeja de salida.
- Integración con un CRM real, otros canales (WhatsApp, avisos dentro del producto), cambios en el producto.
- Modelo predictivo entrenado. La priorización usa tasas observadas, explicables en una frase.
- Grabar el video.

**Antiobjetivos** (fallos aunque técnicamente funcione)

- Un mensaje que mande a alguien a un botón que ya no existe.
- Que la demo en vivo dependa de la red o de la cuota de una API.
- Presentar datos simulados como si fueran resultados reales.
- Llamar al modelo cientos de veces para escribir el mismo mensaje.

## 4. Restricciones

- Plazo de 72 horas; entre 5 y 7 horas de trabajo real.
- Repositorio en GitHub o similar con historial de cambios: commits pequeños por etapa.
- El disco de trabajo (`/Volumes/CLICKAI`) es exFAT: no admite enlaces simbólicos y macOS crea archivos
  `._*`. El entorno virtual debe vivir fuera del volumen y `._*` va en `.gitignore`.
- Python del sistema es 3.9.6; hay `uv` instalado. El proyecto fija Python 3.12 con `uv`.
- La clave de API nunca entra al repositorio (`.env` ignorado, `.env.example` incluido).

## 5. Enfoques considerados

**Formato de entrega**

| Enfoque | A favor | En contra |
|---|---|---|
| Repositorio Python, un comando | Historial natural, corre sin cuentas, fácil de probar | Poco visual |
| Herramienta sin código (n8n) | Visual | Historial pobre, depende de un servicio en vivo |
| **Python más panel web (elegido)** | Robustez del primero y algo que mostrar en el video | 1 a 2 horas extra |

Elegido por la persona candidata.

**Acceso al modelo:** Claude por API, elegido por la persona candidata (ya tiene clave).

**Cómo se usa la IA** (decisión mía)

| Enfoque | A favor | En contra |
|---|---|---|
| Una llamada por persona | Parece más «personal» | El CRM solo trae nombre, canal, segmento y actividad: cientos de llamadas producirían el mismo texto. Imposible de revisar entero |
| **Una llamada por variante (elegido)** | Cada combinación de paso, actividad y antigüedad se redacta una vez; el nombre se inserta después. Se puede verificar el 100% y revisar a mano | Menos variedad de redacción entre personas iguales |
| Agente con herramientas | Flexible | Innecesario: el recorrido es fijo. Más costo y menos predecible |

## 6. Diseño

### 6.1 Etapas del flujo

Un comando (`cuadra correr`) ejecuta las etapas en orden. Cada etapa lee archivos y escribe archivos, así
que se puede correr y probar por separado.

1. **Ingesta y validación.** Carga los tres CSV y valida columnas, tipos, ids y orden de pasos. Si algo
   falla, se detiene con un mensaje claro.
2. **Diagnóstico.** Calcula el embudo general y por canal, segmento, actividad y mes de registro, y los
   tiempos entre pasos. Código determinista. Salida: tablas para el panel y `salida/diagnostico.md`.
3. **Estado de cada persona.** Para la fecha de corrida (por defecto 2026-10-31, configurable para simular
   otros días), cada persona sin primera factura recibe:
   - paso en el que está: `sin_configurar`, `sin_cliente` o `sin_factura`;
   - días quieta desde su último evento;
   - tramo: `en_ventana` (menos de 3 días quieta: no se le escribe, todavía puede avanzar sola),
     `reciente` (3 a 14 días) o `rezagado` (más de 14 días).
   Quedan fuera quienes ya pagaron.
4. **Asignación al experimento.** Cada persona elegible va a tratamiento o control con un hash
   determinista de su id y una semilla fija. Es un hash puro, sin balanceo por estrato: así el grupo de
   una persona no cambia aunque el flujo corra otro día. Reparto por defecto 50/50, configurable. Se
   guarda la fecha de entrada de cada persona (la de la corrida en que resultó elegible por primera vez).
   La etapa informa el tamaño de cada grupo, el equilibrio por paso, tramo, canal y segmento, y el efecto
   mínimo detectable con ese reparto. Todas las elegibles entran; no hay filtro de prioridad. La bandeja
   se ordena con los recientes primero.
5. **Base de conocimiento vigente.** El modelo compara cada artículo de ayuda con las notas de cambios y
   devuelve, de forma estructurada, si el artículo sigue vigente, qué frases quedaron obsoletas, cuál es el
   texto corregido y en qué nota se apoya. También extrae la lista de rutas de menú válidas y las funciones
   limitadas a un plan. Salida: `salida/base_vigente.json`, visible en el panel como comparación entre
   antes y después.
6. **Redacción por variante.** Para cada combinación de paso, actividad y tramo (3 × 18 × 2 = 108
   variantes; se generan todas, no solo las presentes el 31 de octubre, para que otra fecha de corrida
   también funcione sin red), el modelo redacta un correo: asunto, cuerpo con el campo
   `{nombre}`, un solo paso siguiente, la ruta de menú exacta y el artículo en que se apoya. Usa únicamente
   la base vigente. El contenido por paso:
   - `sin_configurar`: completar NIF y dirección fiscal en Configuración > Empresa, porque sin eso no se
     puede emitir.
   - `sin_cliente`: crear el primer cliente desde Nueva factura, con un ejemplo de su oficio.
   - `sin_factura`: emitir la primera factura; mención al borrador como opción sin riesgo.
   El tramo `rezagado` cambia el tono (retomar donde lo dejó), no las instrucciones. La actividad
   determina el segmento (cada oficio pertenece a uno solo), así que el segmento ya está en la variante.
   El canal no cambia el mensaje: la base de conocimiento no dice nada sobre gestores y la verificación
   rechazaría cualquier afirmación sin respaldo. El canal se usa solo para leer el resultado del
   experimento, en especial en autónomos de canal orgánico.
7. **Verificación.** Dos capas sobre cada variante:
   - reglas deterministas: toda ruta de menú citada existe en la base vigente; ninguna frase obsoleta;
     ninguna función solo Pro; sin precios, descuentos ni promesas no presentes en la base; contiene
     `{nombre}`; longitud dentro del límite; un solo paso siguiente;
   - juez con el modelo: ¿todo lo afirmado está respaldado por la base vigente?, ¿responde al paso de esa
     persona?, ¿tono adecuado para un autónomo o una pyme de España?
   Una variante rechazada se vuelve a redactar una vez con el motivo del rechazo. Si vuelve a fallar, queda
   en la cola de revisión humana y sus destinatarios no reciben mensaje en esta corrida.
8. **Bandeja de salida.** Une variantes aprobadas con las personas de tratamiento. Salida:
   `salida/bandeja_salida.csv` (id, correo, asunto, cuerpo final, paso, tramo, variante) y
   `salida/asignacion_experimento.csv` (todas las elegibles, con grupo y fecha de entrada). El caso de la
   demostración es una sola ola, la del 31 de octubre: `cuadra correr` regenera las salidas desde cero y
   da siempre el mismo resultado, de modo que la corrida en vivo de los evaluadores reproduce la bandeja
   completa. Para uso diario existe una opción que respeta un registro de enviados y no escribe dos veces
   a la misma persona; no es el modo por defecto.
9. **Medición.** Comando aparte (`cuadra medir`) que recibe una exportación posterior de eventos y calcula
   el resultado del experimento (apartado 6.3).

### 6.2 Uso del modelo

- SDK oficial `anthropic` para Python, con salidas estructuradas validadas contra un esquema.
- Modelo por defecto `claude-opus-5-5`, configurable con una variable de entorno. Es mi elección por
  calidad de redacción; el costo lo decide la persona candidata (apartado 8).
- Cada respuesta se guarda en `cache/` con una clave derivada del contenido de la petición. El caché se
  sube al repositorio. Con caché completo, el flujo corre sin clave y sin red; es el modo por defecto de
  la demo. El modo en vivo ignora el caché para las variantes que se le indiquen.
- Si falta una respuesta en el caché y no hay clave, el flujo no se detiene: esa variante va a la cola
  de revisión con el motivo «sin caché y sin clave» y el resumen de la corrida lo informa.
- El modelo no decide a quién se escribe ni calcula métricas. Eso es código.

### 6.3 Cómo sabríamos si funcionó

- **Unidad y grupos:** persona elegible; tratamiento recibe correo, control no. Análisis por intención de
  tratar.
- **Métrica principal:** porcentaje que emite su primera factura en los 14 días siguientes a su fecha
  de entrada al experimento.
- **Secundarias:** avanza al menos un paso en 7 días; paga en 45 días.
- **De protección:** bajas y quejas por correo (no existen en los datos; se nombran como pendiente).
- **Cálculo:** diferencia de proporciones con intervalo de confianza del 95% y valor p, total y por
  estrato (paso y tramo).
- **Regla de decisión escrita antes de mirar:** se extiende a todos si el intervalo de la métrica
  principal queda por encima de cero; se itera el mensaje por estrato si no.
- **Comprobaciones:** equilibrio de grupos por canal y segmento; prueba A/A sobre cohortes históricas (el
  mismo hash aplicado a julio y agosto no debe mostrar diferencia).
- **Demostración:** como no existen datos posteriores al 31 de octubre, un simulador genera una
  exportación futura con un efecto que se pasa por parámetro, y `cuadra medir` la procesa. Todo lo
  simulado va marcado como simulado en archivos y en el panel.

### 6.4 Panel

Streamlit, un comando lo abre. Cinco pestañas:

1. **Diagnóstico:** embudo, cruce de canal por segmento, tiempos entre pasos, dónde está la fuga.
2. **Base vigente:** cada artículo con su estado y, para la ayuda 04, lo obsoleto frente a lo corregido.
3. **Mensajes:** buscador por persona o variante; muestra datos de la persona, correo final y resultado de
   la verificación. Botón para redactar una variante en vivo si hay clave.
4. **Experimento:** tamaños, equilibrio, efecto mínimo detectable, prueba A/A y resultado simulado.
5. **Qué no cubre:** límites del flujo.

### 6.5 Pruebas

- Unitarias para embudo, estado, tramo y asignación (determinismo, equilibrio, estratos).
- De la verificación con mensajes defectuosos sembrados: uno con «Más acciones > Enviar por correo», uno que
  ofrece facturas recurrentes, uno con un descuento inventado. La verificación debe rechazar los tres.
- De punta a punta en modo repetición: el flujo completo corre sin red y produce los archivos esperados.

### 6.6 Estructura del repositorio

```
README.md            cómo correrlo en 3 pasos, qué hace, qué no cubre
pyproject.toml
.env.example
datos/ ayudas/ notas/  material del caso (hoy en material/, se mueve a la raíz)
cuadra/              ingesta, diagnostico, estado, experimento, conocimiento, redaccion,
                     verificacion, bandeja, medicion, simulador, cli, modelo (cliente y caché)
panel/app.py
cache/               respuestas guardadas del modelo
salida/              resultados de la última corrida (versionados para que se vean sin correr)
tests/
docs/                este diseño
```

### 6.7 Orden de recorte si el tiempo no alcanza

Imprescindible, en este orden: ingesta, diagnóstico, estado, asignación, base vigente, redacción,
verificación por reglas, bandeja, modo repetición, `cuadra medir`, README, panel con las pestañas
Diagnóstico, Mensajes y Experimento.

Se recorta, empezando por lo primero de la lista: prueba A/A, botón de redacción en vivo del panel,
pestañas Base vigente y Qué no cubre (pasan al README), reintento tras rechazo del juez, opción de
registro de enviados. El juez con el modelo y el simulador se mantienen: sin ellos no hay respuesta que
corra a «cómo sabrías si funcionó» ni control de calidad de la IA.

## 7. Qué no cubre (para el README y el video)

- No envía correos ni mide aperturas o clics.
- No prueba por qué los autónomos de canal orgánico se atascan al crear cliente; lo señala y propone
  investigarlo (hipótesis: no saben qué datos fiscales pedir a su cliente).
- Los datos son sintéticos: la conversión natural casi nula de los rezagados puede ser un artefacto.
- Sin consentimiento ni enlace de baja reales; en producción son obligatorios.
- El efecto mostrado en la demostración es simulado.

## 8. Decisiones abiertas para la persona candidata

1. **Costo del modelo.** Con redacción por variante, una corrida completa en `claude-opus-5-5` (108
   variantes, redacción más juez, más la base vigente) cuesta del orden de 2 a 4 USD una sola vez; después se repite gratis
   desde el caché. El reto dice «costo para ti: cero». Alternativa: `claude-haiku-5-5`, centavos por
   corrida, redacción algo menos fina. Por defecto queda Opus 5.5.
2. **Publicación en GitHub.** Crear el repositorio remoto y subirlo requiere su cuenta y su confirmación.

## 9. Decisiones tomadas por mí (corregibles)

- Panel con Streamlit.
- IA por variante (paso, actividad, tramo) y no por persona.
- Reparto 50/50 en la primera ola, con hash puro por id. Durante la construcción, la prueba A/A mostró que
  la primera semilla dejaba los grupos desbalanceados por azar (p = 0,01); la semilla se eligió entonces
  con una regla fija: la primera candidata con p > 0,2. Los grupos quedan en 457 y 455.
- El canal no entra en la variante del mensaje; solo en la lectura del experimento.
- Una sola ola como caso de demostración; el uso diario queda como opción.
- Sin clave y sin caché, la variante va a revisión en vez de detener el flujo.
- Orden de recorte del apartado 6.7.
- Umbral de 3 días quieto para considerar a alguien atascado (sale de los tiempos observados).
- Las facturas recurrentes no se mencionan en ningún mensaje.
- Los 8 pagadores sin factura quedan fuera y se listan aparte.
- El documento de diseño vive en `docs/` y no en `docs/superpowers/specs/`, porque los evaluadores verán
  el repositorio.

## 10. Lo que queda a quien construye

Nombres internos, esquema exacto de las salidas estructuradas, redacción de los prompts, gráficos del
panel, número de trabajadores en paralelo y formato del caché.
