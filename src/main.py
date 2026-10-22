"""Punto de entrada por consola de Nafteando.

Uso:
    python -m src.main inspeccionar data/muestra/precios_muestra.csv
    python -m src.main limpiar data/muestra/precios_rosario_real.csv
    python -m src.main vigentes data/muestra/precios_rosario_real.csv --producto super
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import CAMPOS_PRECIO, CIUDAD_POR_DEFECTO, DIR_SALIDAS
from src.fuentes import ErrorFuente, fuente_para
from src.modelos import HORARIOS, PRODUCTOS
from src.pipeline import (
    FORMATO_FECHA,
    ErrorEsquema,
    armar_precios,
    filtrar_ciudad,
    guardar_csv,
    limpiar_precios,
    precios_vigentes,
    resumen_motivos,
)

CAMPOS_VIGENTES = [
    "idempresa", "empresa", "bandera", "direccion", "latitud", "longitud",
    "producto", "horario", "precio", "vigente_desde",
]


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


def pesos(valor):
    """1890.5 -> '$1.890,50'"""
    return "$" + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def vigentes(registros, fecha_consulta, localidad, provincia, producto, franja, carpeta_salida):
    validos, rechazos = limpiar_precios(registros, fecha_consulta)
    precios = filtrar_ciudad(armar_precios(validos), localidad, provincia)
    seleccion = [
        p for p in precios_vigentes(precios, fecha_consulta)
        if (producto is None or p.producto == producto) and (franja is None or p.horario == franja)
    ]

    ruta = carpeta_salida / "precios_vigentes.csv"
    guardar_csv(
        [{
            "idempresa": p.estacion.idempresa,
            "empresa": p.estacion.empresa,
            "bandera": p.estacion.bandera,
            "direccion": p.estacion.direccion,
            "latitud": p.estacion.latitud,
            "longitud": p.estacion.longitud,
            "producto": p.producto,
            "horario": p.horario,
            "precio": p.precio,
            "vigente_desde": p.vigente_desde,
        } for p in seleccion],
        ruta,
        CAMPOS_VIGENTES,
    )
    guardar_csv(rechazos, carpeta_salida / "rechazos.csv", ["fila", "motivo"] + CAMPOS_PRECIO)

    print(f"Precios vigentes en {localidad}, {provincia} al {fecha_consulta:%d/%m/%Y %H:%M}")
    print(f"({len(rechazos)} filas rechazadas en la limpieza, ver {carpeta_salida / 'rechazos.csv'})")
    if not seleccion:
        print("\nNo hay precios vigentes para esa búsqueda.")
        return

    grupo = None
    for p in seleccion:
        if (p.producto, p.horario) != grupo:
            grupo = (p.producto, p.horario)
            print(f"\n{p.producto} · {p.horario}")
        print(f"  {pesos(p.precio):>11}  desde {p.vigente_desde:%d/%m}  {p.estacion}")
    print(f"\nGuardado en {ruta}")


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

    p_vigentes = comandos.add_parser(
        "vigentes", help="precio vigente de cada estación de la ciudad, del más barato al más caro"
    )
    p_vigentes.add_argument("ruta", help="archivo .csv o .json")
    p_vigentes.add_argument("--fecha-consulta", type=fecha_argumento, default=None,
                            help="momento de la consulta, 'AAAA-MM-DD HH:MM:SS' (ahora por defecto)")
    p_vigentes.add_argument("--producto", choices=PRODUCTOS, help="solo este producto")
    p_vigentes.add_argument("--franja", choices=HORARIOS, help="solo esta franja horaria")
    p_vigentes.add_argument("--localidad", default=CIUDAD_POR_DEFECTO[0])
    p_vigentes.add_argument("--provincia", default=CIUDAD_POR_DEFECTO[1])
    p_vigentes.add_argument("--salida", type=Path, default=DIR_SALIDAS,
                            help="carpeta de salida (outputs/ por defecto)")
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

    fecha_consulta = args.fecha_consulta or datetime.now()
    try:
        if args.comando == "limpiar":
            limpiar(registros, fecha_consulta, args.salida)
        elif args.comando == "vigentes":
            vigentes(registros, fecha_consulta, args.localidad, args.provincia,
                     args.producto, args.franja, args.salida)
    except ErrorEsquema as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
