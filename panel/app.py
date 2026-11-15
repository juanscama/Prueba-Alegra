"""Panel local: muestra lo que dejó la última corrida en salida/. No recalcula nada, salvo la redacción en vivo.

Cuatro páginas, de lo simple a lo técnico: el resumen se entiende sin saber de datos, la automatización se
corre desde un botón, los correos muestran el producto y el detalle técnico guarda todo el análisis para quien quiera revisarlo.
"""

from pathlib import Path

import streamlit as st

AQUI = Path(__file__).resolve().parent

st.set_page_config(page_title="Cuadra · De registrarse a facturar", layout="wide")

navegacion = st.navigation(
    [
        st.Page(AQUI / "vistas" / "resumen.py", title="Resumen", icon=":material/home:", default=True),
        st.Page(AQUI / "vistas" / "automatizacion.py", title="Ver la automatización", icon=":material/play_circle:"),
        st.Page(AQUI / "vistas" / "correos.py", title="Los correos", icon=":material/mail:"),
        st.Page(AQUI / "vistas" / "detalle.py", title="Detalle técnico", icon=":material/analytics:"),
    ],
    position="top",
)
navegacion.run()
