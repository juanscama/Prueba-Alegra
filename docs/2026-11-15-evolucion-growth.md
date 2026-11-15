# Evolución: capa de inteligencia de Growth

Rama `evolucion-growth`. Amplía el flujo entregado sin modificarlo: `cuadra correr`, sus salidas, el
experimento y las 134 pruebas originales quedan intactos.

## 1. Auditoría previa

**Datos disponibles**

- `eventos_producto.csv`: solo 5 eventos (registro, configuro_empresa, creo_cliente, emitio_primera_factura,
  emitio_5_facturas), con fecha por día. No hay sesiones, clics, pantallas ni errores.
- `crm_contactos.csv`: canal, segmento, actividad y etapa. No hay consentimiento ni preferencias de
  comunicación.
- `pagos.csv`: 205 pagos, plan e importe mensual (15 o 30 EUR).

**Qué ya existía:** embudo, embudo por canal, segmento y mes, tiempos entre pasos, reparto por hash,
equilibrio, prueba A/A, intervalos de confianza, efecto mínimo detectable y separación de lo simulado.

**Qué se podía construir sin datos nuevos:** todo lo de abajo, salvo lo que exige comportamiento fino
(clics, sesiones), consentimiento (WhatsApp) o resultados observados del experimento. Eso queda como
prototipo, instrumentación recomendada o demostración simulada claramente marcada.

**Riesgos atendidos**

- *Plazo:* alcance reducido (seis módulos en versión mínima) y trabajo en una rama, para que `main` siga
  siendo una entrega segura.
- *Romper lo que funciona:* módulos nuevos y separados, comando nuevo y página nueva del panel. Las pruebas del
  panel original fijan sus 5 pestañas, así que las 8 secciones van en una página aparte en lugar de
  reorganizar la existente.
- *Costo de API:* tope aprobado de 2 USD. Gasto real: unos 0,38 USD (16 llamadas), guardadas en `cache/`.

## 2. Qué se añadió

| Módulo | Archivo | Salidas en `salida/inteligencia/` |
|---|---|---|
| 1. Embudo completo | `cuadra/embudo_completo.py` | `embudo_etapas.csv`, `embudo_por_{segmento,canal,mes}.csv`, `oportunidades.csv` |
| 2. Priorización | `cuadra/priorizacion.py` | `priorizacion.csv` |
| 3. Intervenciones | `cuadra/intervenciones.py` | `plan_intervenciones.csv`, `contenidos_por_canal.json` |
| 4. Comportamiento | `cuadra/comportamiento.py` | `secuencias.csv`, `donde_se_detiene.csv`, `tiempo_a_primera_factura.csv`, `acciones_antes_de_activar.csv`, `ritmo_activados_vs_no.csv`, `cohortes_semanales.csv`, `instrumentacion_recomendada.csv` |
| 5. Salud del experimento | `cuadra/salud_experimento.py` | `salud_experimento.json`, `balance.csv` |
| 6. Negocio e informe | `cuadra/negocio.py`, `cuadra/informe.py` | `conversiones_negocio.csv`, `escenarios.csv`, `hipotesis.json`, `hechos.json`, `informe_ejecutivo.json` |
| Orquestación | `cuadra/inteligencia.py`, `cuadra/cli.py` (`analizar`) | `resumen.json` |
| Panel | `panel/pages/2_Inteligencia_de_Growth.py` | 8 secciones |
| Pruebas | `tests/test_inteligencia.py` | 31 pruebas |

Cambios en archivos existentes: `cuadra/config.py` (tres constantes nuevas al final), `cuadra/cli.py`
(subcomando `analizar`) y `README.md`.

## 3. Decisiones

- **Cohortes maduras.** Las tasas usan personas registradas al menos 14 días antes del 31 de octubre (nadie
  tardó más de 8 en facturar). La conversión de factura a pago usa 45 días, porque el pago llega hasta 30
  días después de facturar. Sin esto, la tasa de pago salía en un 38% en lugar de un 41%, y las cohortes de
  octubre parecían peores de lo que son.
- **El pago queda fuera de las oportunidades.** En cohortes de 14 días sale sesgado.
- **Las «personas que faltan» son una estimación.** Supuesto: el grupo convertiría como la mediana de los
  demás grupos en esa etapa. Mide el tamaño de la brecha, no lo que se puede ganar.
- **Priorización por reglas, sin modelo predictivo.** Entre los atascados, en siete cortes pasados, solo 5 de
  3249 facturaron solos. Con 5 casos positivos no hay modelo que entrenar ni calibrar. La prioridad ordena la
  atención y no estima el efecto del contacto: eso se sabrá comparando tratamiento y control dentro de cada
  nivel cuando haya resultados.
- **El control no recibe nada por ningún canal.** Los canales nuevos quedan como «propuestos» para el
  siguiente experimento: activarlos ahora cambiaría el tratamiento a mitad de medición. WhatsApp queda
  bloqueado porque el CRM no registra consentimiento.
- **Claude no calcula.** El informe ejecutivo recibe hechos ya formateados, con identificador y naturaleza
  (observado, estimación, hipótesis). `verificar_informe` rechaza cualquier número que no esté en los hechos y
  cualquier fuente que no exista; si falla, se pide una vez más y, si vuelve a fallar, se muestra como no
  verificado. Los 15 contenidos por canal pasan las mismas comprobaciones que los correos (rutas válidas,
  nada obsoleto, nada de planes de pago, sin precios ni enlaces) más el límite de largo de cada canal.
- **El desequilibrio del reparto no se corrige reasignando.** La prueba de balance detecta, por azar, más
  personas sin configurar la empresa en el control (34% frente a 28%, SMD 0,13). Reasignar invalidaría el
  experimento, así que se añade `ajuste_por_estratos`: la diferencia ponderada dentro de cada paso.

## 4. Verificación

- `uv run pytest`: 165 pruebas en verde (las 134 originales sin cambios y 31 nuevas).
- `cuadra analizar --modo repeticion`: 0 llamadas reales, informe verificado, 15 de 15 contenidos aprobados y
  0 problemas de asignación.
- La prueba `test_analizar_desde_cache_sin_tocar_el_experimento` comprueba que la huella SHA-256 de
  `asignacion_experimento.csv` no cambia al analizar.
- La reproducibilidad recalcula el grupo de las 912 personas con el hash: 912 de 912 coinciden.
- Sin datos posteriores: `tabla_personas`, `_fechas` y el estado filtran por la fecha de corrida, y la
  priorización solo usa el estado de ese día (`test_cohortes_maduras_y_sin_datos_futuros`).
- El panel se recorrió en el navegador. Las tablas muestran identificadores, no nombres ni correos (lo
  comprueba `test_pagina_de_inteligencia`).

## 5. Limitaciones y pendientes

- No hay resultados observados del experimento: lo de resultados es una demostración simulada.
- No se sabe por qué se frenan las personas: faltan los eventos de la instrumentación recomendada.
- Las métricas secundarias (pago a 45 días por grupo) siguen sin implementarse en `cuadra medir`.
- La regla de frecuencia (`respeta_frecuencia`) está implementada y probada, pero no hay historial real de
  contactos sobre el que aplicarla.
- En la barra lateral del panel, la página principal aparece como «app», porque Streamlit toma el nombre del
  archivo y renombrarlo rompería las pruebas originales.
- `use_container_width` sigue en el panel original y Streamlit avisa de que está obsoleto. La página nueva ya
  usa `width`.

## 6. Cómo mostrarlo en la defensa

1. Abrir el panel original y contar el flujo (problema, ayuda al día, correos, medición).
2. Pasar a **Inteligencia de Growth > Resumen ejecutivo**. Mostrar que cada punto lleva su tipo y sus
   fuentes, y abrir «Los hechos que recibió Claude».
3. **Experimento:** reparto reproducible, sin descuadre y el desequilibrio casual por paso. Explicar por qué
   no se reasigna y cómo se corrige.
4. **Priorización:** leer un caso y el aviso «prioridad no es efecto». Contar por qué no hay modelo
   predictivo (5 casos positivos).
5. **Intervenciones:** la tabla de elegibilidad (control bloqueado, WhatsApp sin consentimiento) y una vista
   previa verificada.
6. **Comportamiento > Instrumentación recomendada:** lo que pediría medir para explicar la fuga.
