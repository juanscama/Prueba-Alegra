"""Línea de comandos: `cuadra correr` ejecuta el flujo completo."""

import argparse
from datetime import date

from cuadra import flujo
from cuadra.config import FECHA_CORRIDA

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
    ("efecto_minimo_detectable", "Efecto mínimo detectable"),
]


def _correr(args) -> int:
    resumen = flujo.correr(
        fecha=args.fecha,
        modo=args.modo,
        forzar=args.forzar,
        limite_variantes=args.limite_variantes,
        respetar_enviados=args.respetar_enviados,
        avisar=print,
    )
    print()
    for clave, etiqueta in ETIQUETAS:
        valor = resumen[clave]
        if clave == "efecto_minimo_detectable":
            valor = f"{valor * 100:.1f} puntos porcentuales"
        print(f"{etiqueta:<40} {valor}")
    print(f"\nResultados en {flujo.DIR_SALIDA}")
    return 0


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

    args = parser.parse_args(argv)
    return args.funcion(args)


if __name__ == "__main__":
    raise SystemExit(main())
