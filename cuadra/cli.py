"""Línea de comandos: `cuadra correr` ejecuta el flujo completo."""

import argparse
import json
import subprocess
import sys
import threading
import webbrowser
from datetime import date

import pandas as pd

from cuadra import flujo
from cuadra.config import FECHA_CORRIDA, RAIZ
from cuadra.medicion import medir
from cuadra.modelo import SinClave
from cuadra.simulador import simular_eventos

PUERTO_PANEL = 8501

ETIQUETAS = [
    ("fecha", "Fecha de corrida"),
    ("modo", "Modo del modelo"),
    ("personas_sin_facturar", "Personas sin primera factura"),
    ("en_ventana", "  aún en ventana (no se les escribe)"),
    ("elegibles", "  elegibles para el experimento"),
    ("tratamiento", "    tratamiento (reciben correo)"),
    ("control", "    control (no reciben)"),
    ("variantes_aprobadas", "Variantes de correo aprobadas"),
    ("variantes_en_revision", "Variantes en revisión humana"),
    ("variantes_sin_procesar", "Variantes sin procesar (límite)"),
    ("correos_en_bandeja", "Correos en la bandeja de salida"),
    ("personas_sin_correo_por_revision", "Personas sin correo por revisión"),
    ("llamadas_reales", "Llamadas reales al modelo"),
    ("tasa_base_estimada", "Conversión natural de los atascados"),
    ("efecto_minimo_detectable", "Efecto mínimo detectable"),
]


def _correr(args) -> int:
    try:
        resumen = flujo.correr(
            fecha=args.fecha,
            modo=args.modo,
            forzar=args.forzar,
            limite_variantes=args.limite_variantes,
            respetar_enviados=args.respetar_enviados,
            avisar=print,
        )
    except SinClave as error:
        print(f"No se puede correr así: {error}", file=sys.stderr)
        return 2
    print()
    for clave, etiqueta in ETIQUETAS:
        valor = resumen[clave]
        if clave == "efecto_minimo_detectable":
            valor = "no calculable con estos datos" if valor is None else f"{valor * 100:.1f} puntos porcentuales"
        if clave == "tasa_base_estimada":
            valor = "sin historia suficiente" if valor is None else (
                f"{valor:.1%} ({resumen['base_convertidos']} de {resumen['base_observaciones']})"
            )
        print(f"{etiqueta:<40} {valor}")
    print(f"\nResultados en {flujo.DIR_SALIDA}")
    return 0


def _simular(args) -> int:
    asignacion = pd.read_csv(flujo.DIR_SALIDA / "asignacion_experimento.csv")
    eventos = simular_eventos(asignacion, efecto=args.efecto, semilla=args.semilla)
    ruta = flujo.DIR_SALIDA / "SIMULADO_eventos_posteriores.csv"
    eventos.to_csv(ruta, index=False, lineterminator="\n", encoding="utf-8")
    print(f"SIMULADO: {len(eventos)} primeras facturas inventadas con un efecto de {args.efecto:+.0%}.")
    print(f"No son resultados reales. Archivo: {ruta}")
    return 0


def _medir(args) -> int:
    asignacion = pd.read_csv(flujo.DIR_SALIDA / "asignacion_experimento.csv")
    resultado, por_estrato = medir(asignacion, pd.read_csv(args.eventos))
    prefijo = "SIMULADO_" if resultado.simulado else ""
    (flujo.DIR_SALIDA / f"{prefijo}resultado_experimento.json").write_text(
        json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    por_estrato.to_csv(
        flujo.DIR_SALIDA / f"{prefijo}resultado_por_estrato.csv", index=False, lineterminator="\n", encoding="utf-8"
    )
    if resultado.simulado:
        print("SIMULADO: los eventos medidos son inventados; esto demuestra el cálculo, no un resultado.\n")
    print(f"Tratamiento  {resultado.conv_t:>4} de {resultado.n_t:<4} emitieron su primera factura ({resultado.tasa_t:.1%})")
    print(f"Control      {resultado.conv_c:>4} de {resultado.n_c:<4} emitieron su primera factura ({resultado.tasa_c:.1%})")
    print(
        f"Diferencia   {resultado.diferencia * 100:+.1f} puntos "
        f"(IC 95%: {resultado.ic95[0] * 100:+.1f} a {resultado.ic95[1] * 100:+.1f}; p = {resultado.valor_p:.4f})"
    )
    regla = "el intervalo queda entero por encima de cero" if resultado.decision == "extender" else "el intervalo incluye el cero"
    print(f"Decisión     {resultado.decision}: {regla}")
    return 0


def _panel(args) -> int:
    url = f"http://localhost:{PUERTO_PANEL}"
    print(f"Panel en {url} (Ctrl+C para cerrarlo)")
    # Modo sin cabeza: en su primer arranque Streamlit pide un correo por teclado y bloquea la demo.
    # El navegador lo abrimos nosotros cuando el servidor ya está arriba.
    threading.Timer(2.5, webbrowser.open, args=[url]).start()
    return subprocess.call(
        [
            sys.executable, "-m", "streamlit", "run", str(RAIZ / "panel" / "app.py"),
            "--server.headless", "true",
            "--server.port", str(PUERTO_PANEL),
            "--browser.gatherUsageStats", "false",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cuadra", description="Flujo de activación: de registrarse a facturar")
    sub = parser.add_subparsers(dest="comando", required=True)

    correr = sub.add_parser("correr", help="Ejecuta el flujo completo y deja los resultados en salida/")
    correr.add_argument("--fecha", type=date.fromisoformat, default=FECHA_CORRIDA, help="AAAA-MM-DD; por defecto 2026-10-31")
    correr.add_argument("--modo", choices=["auto", "repeticion", "vivo"], default="auto",
                        help="auto: en vivo si hay clave, repetición desde cache/ si no")
    correr.add_argument("--forzar", action="store_true", help="Ignora el caché y vuelve a llamar al modelo")
    correr.add_argument("--limite-variantes", type=int, default=None, help="Procesa solo las N variantes con más destinatarios")
    correr.add_argument("--respetar-enviados", action="store_true", help="No vuelve a escribir a quien ya está en salida/enviados.csv")
    correr.set_defaults(funcion=_correr)

    simular = sub.add_parser("simular", help="Inventa una exportación futura de eventos para probar la medición")
    simular.add_argument("--efecto", type=float, default=0.08, help="Puntos de conversión que se le suman al tratamiento (0.08 = 8 puntos)")
    simular.add_argument("--semilla", type=int, default=7)
    simular.set_defaults(funcion=_simular)

    medicion = sub.add_parser("medir", help="Compara tratamiento y control con una exportación posterior de eventos")
    medicion.add_argument("--eventos", required=True, help="CSV con columnas id_contacto, evento, fecha")
    medicion.set_defaults(funcion=_medir)

    panel = sub.add_parser("panel", help="Abre el panel web local con los resultados de salida/")
    panel.set_defaults(funcion=_panel)

    args = parser.parse_args(argv)
    return args.funcion(args)


if __name__ == "__main__":
    raise SystemExit(main())
