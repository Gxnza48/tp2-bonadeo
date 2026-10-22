"""Punto de entrada por consola de Nafteando.

Uso:
    python -m src.main inspeccionar data/muestra/precios_muestra.csv
"""

import argparse
import sys

from src.config import CAMPOS_PRECIO
from src.fuentes import ErrorFuente, fuente_para


def tipo_aparente(valores):
    """'número' si todos los valores no vacíos se pueden leer como número."""
    no_vacios = [v for v in valores if v.strip()]
    if not no_vacios:
        return "-"
    try:
        for valor in no_vacios:
            float(valor)
    except ValueError:
        return "texto"
    return "número"


def inspeccionar(registros, mostrar=3):
    campos = []
    for registro in registros:
        for campo in registro:
            if campo not in campos:
                campos.append(campo)

    print(f"Registros: {len(registros)}")
    print(f"Campos: {len(campos)}\n")
    print(f"{'campo':<16}{'vacíos':>8}  tipo")
    for campo in campos:
        valores = [registro.get(campo, "") for registro in registros]
        vacios = sum(1 for v in valores if not v.strip())
        print(f"{campo:<16}{vacios:>8}  {tipo_aparente(valores)}")

    faltantes = [c for c in CAMPOS_PRECIO if c not in campos]
    de_mas = [c for c in campos if c not in CAMPOS_PRECIO]
    print()
    print("Campos esperados que faltan:", ", ".join(faltantes) or "ninguno")
    print("Campos que no se usan:", ", ".join(de_mas) or "ninguno")

    if mostrar > 0:
        print(f"\nPrimeros {min(mostrar, len(registros))} registros:")
        for registro in registros[:mostrar]:
            print(" ", registro)


def crear_parser():
    parser = argparse.ArgumentParser(
        prog="nafteando",
        description="¿Vale la pena desviarme para cargar más barato?",
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    p_inspeccionar = comandos.add_parser(
        "inspeccionar", help="resume un archivo de precios (CSV o JSON)"
    )
    p_inspeccionar.add_argument("ruta", help="archivo .csv o .json")
    p_inspeccionar.add_argument(
        "-n", "--mostrar", type=int, default=3, help="cuántos registros mostrar (3 por defecto)"
    )
    return parser


def main(argumentos=None):
    args = crear_parser().parse_args(argumentos)

    try:
        registros = fuente_para(args.ruta).cargar(args.ruta)
    except ErrorFuente as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.comando == "inspeccionar":
        inspeccionar(registros, args.mostrar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
