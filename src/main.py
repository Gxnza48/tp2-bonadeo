"""Punto de entrada por consola de Nafteando.

Uso:
    python -m src.main inspeccionar data/muestra/precios_muestra.csv
    python -m src.main limpiar data/muestra/precios_rosario_real.csv
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import CAMPOS_PRECIO, DIR_SALIDAS
from src.fuentes import ErrorFuente, fuente_para
from src.pipeline import (
    FORMATO_FECHA,
    ErrorEsquema,
    guardar_csv,
    limpiar_precios,
    resumen_motivos,
)


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


def limpiar(registros, fecha_consulta, carpeta_salida):
    validos, rechazos = limpiar_precios(registros, fecha_consulta)

    ruta_validos = carpeta_salida / "precios_limpios.csv"
    ruta_rechazos = carpeta_salida / "rechazos.csv"
    guardar_csv(validos, ruta_validos, CAMPOS_PRECIO)
    guardar_csv(rechazos, ruta_rechazos, ["fila", "motivo"] + CAMPOS_PRECIO)

    print(f"Fecha de consulta: {fecha_consulta:{FORMATO_FECHA}}")
    print(f"Leídos: {len(registros)}  Válidos: {len(validos)}  Rechazados: {len(rechazos)}")
    if rechazos:
        print("\nMotivos de rechazo:")
        for motivo, cantidad in resumen_motivos(rechazos).items():
            print(f"  {cantidad:>5}  {motivo}")
    print(f"\nVálidos en {ruta_validos}")
    print(f"Rechazos en {ruta_rechazos}")


def fecha_argumento(texto):
    try:
        return datetime.strptime(texto, FORMATO_FECHA)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{texto}' no es una fecha válida con formato AAAA-MM-DD HH:MM:SS"
        ) from None


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

    p_limpiar = comandos.add_parser(
        "limpiar", help="valida y limpia los precios, y guarda los rechazos con su motivo"
    )
    p_limpiar.add_argument("ruta", help="archivo .csv o .json")
    p_limpiar.add_argument(
        "--fecha-consulta",
        type=fecha_argumento,
        default=None,
        help="momento de la consulta, 'AAAA-MM-DD HH:MM:SS' (ahora por defecto)",
    )
    p_limpiar.add_argument(
        "--salida", type=Path, default=DIR_SALIDAS, help="carpeta de salida (outputs/ por defecto)"
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
    elif args.comando == "limpiar":
        try:
            limpiar(registros, args.fecha_consulta or datetime.now(), args.salida)
        except ErrorEsquema as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
