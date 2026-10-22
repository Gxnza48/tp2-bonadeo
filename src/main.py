"""Punto de entrada por consola de Nafteando.

Uso:
    python -m src.main inspeccionar data/muestra/precios_muestra.csv
    python -m src.main limpiar data/muestra/precios_rosario_real.csv
    python -m src.main vigentes data/muestra/precios_rosario_real.csv --producto super
    python -m src.main recomendar data/muestra/precios_rosario_real.csv --desde "Oroño 1500" --hasta "Pellegrini 3000"
    python -m src.main actualizar
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from src.config import ARCHIVO_VIGENTES, CAMPOS_PRECIO, CIUDAD_POR_DEFECTO, DIR_SALIDAS
from src.descarga import ErrorDescarga, descargar_precios
from src.fuentes import ErrorFuente, fuente_para
from src.modelos import HORARIOS, PRODUCTOS, Recorrido
from src.pipeline import (
    FORMATO_FECHA,
    ErrorEsquema,
    guardar_csv,
    limpiar_precios,
    procesar,
    resumen_motivos,
)
from src.recomendador import SinEstaciones, franja_para, recomendar
from src.ruteo import ErrorRuteo, RuteadorLineaRecta, RuteadorOSRM, ubicar

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
    texto = "$" + f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return "-" + texto if valor < 0 else texto


def vigentes(registros, fecha_consulta, localidad, provincia, producto, franja, carpeta_salida):
    todos, rechazos = procesar(registros, fecha_consulta, localidad, provincia)
    seleccion = [
        p for p in todos
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


def mostrar_recomendacion(rec):
    recorrido = rec.recorrido
    modo = "cerca mío (ida y vuelta)" if recorrido.cerca_mio else "con destino"
    detalle = (f"{recorrido.producto} {rec.franja.lower()} · {recorrido.litros:g} L · "
               f"{recorrido.consumo_km_por_litro:g} km/L")
    if recorrido.valor_hora:
        detalle += f" · hora a {pesos(recorrido.valor_hora)}"
    print(f"Recorrido {modo} · {detalle}")
    ref = rec.referencia.precio
    print(f"Referencia (la de menor desvío): {ref.estacion} a {pesos(ref.precio)}\n")

    print(f"   {'precio':>10}  {'desvío':>8}  {'minutos':>7}  {'ahorro neto':>12}  estación")
    for numero, opcion in enumerate(rec.opciones, start=1):
        print(f"{numero:>2} {pesos(opcion.precio.precio):>10}  {opcion.km_desvio:>5.1f} km  "
              f"{opcion.minutos_desvio:>7.0f}  {pesos(opcion.ahorro_neto):>12}  {opcion.precio.estacion}")

    print()
    if rec.conviene_desviarse:
        mejor = rec.mejor
        print(f"-> Conviene ir a {mejor.precio.estacion.nombre}: ahorrás {pesos(mejor.ahorro_neto)}.")
        cuenta = (f"   {pesos(mejor.ahorro_surtidor)} menos en el surtidor, "
                  f"{pesos(mejor.costo_combustible_desvio)} de combustible en el desvío")
        if mejor.costo_tiempo:
            cuenta += f" y {pesos(mejor.costo_tiempo)} de tu tiempo"
        print(cuenta + ".")
    else:
        print(f"-> No te desvíes: cargá en {ref.estacion.nombre}.")
    if rec.aviso:
        print(f"\nAviso: {rec.aviso}.")
    elif rec.estimado:
        print("\nDistancias estimadas en línea recta.")


def guardar_recomendacion(rec, ruta):
    filas = []
    for opcion in [rec.referencia] + rec.opciones:
        estacion = opcion.precio.estacion
        filas.append({
            "referencia": opcion is rec.referencia,
            "idempresa": estacion.idempresa,
            "estacion": estacion.nombre,
            "direccion": estacion.direccion,
            "precio": opcion.precio.precio,
            "km_desvio": round(opcion.km_desvio, 3),
            "minutos_desvio": round(opcion.minutos_desvio, 1),
            "ahorro_surtidor": round(opcion.ahorro_surtidor, 2),
            "costo_combustible_desvio": round(opcion.costo_combustible_desvio, 2),
            "costo_tiempo": round(opcion.costo_tiempo, 2),
            "ahorro_neto": round(opcion.ahorro_neto, 2),
            "estimado": opcion.estimado,
        })
    guardar_csv(filas, ruta, list(filas[0]))


def ejecutar_recomendar(registros, fecha_consulta, args):
    vigentes_ciudad, _ = procesar(registros, fecha_consulta, args.localidad, args.provincia)
    origen = ubicar(args.desde, args.localidad, args.provincia)
    destino = ubicar(args.hasta, args.localidad, args.provincia) if args.hasta else None
    recorrido = Recorrido(origen, destino, args.producto, args.litros, args.consumo, args.valor_hora)
    ruteador = RuteadorLineaRecta() if args.sin_osrm else RuteadorOSRM()
    franja = args.franja or franja_para(fecha_consulta)

    rec = recomendar(vigentes_ciudad, recorrido, ruteador, franja)
    mostrar_recomendacion(rec)
    ruta = args.salida / "recomendacion.csv"
    guardar_recomendacion(rec, ruta)
    print(f"\nDetalle en {ruta}")


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

    p_recomendar = comandos.add_parser(
        "recomendar", help="¿a qué estación conviene ir? ordena por ahorro neto"
    )
    p_recomendar.add_argument("ruta", help="archivo .csv o .json")
    p_recomendar.add_argument("--desde", required=True, help="dirección o 'lat,lon' de partida")
    p_recomendar.add_argument("--hasta", help="dirección o 'lat,lon' de destino (sin esto: cerca mío)")
    p_recomendar.add_argument("--producto", choices=PRODUCTOS, default="super")
    p_recomendar.add_argument("--litros", type=float, default=30)
    p_recomendar.add_argument("--consumo", type=float, default=12, help="km por litro (12 por defecto)")
    p_recomendar.add_argument("--valor-hora", type=float, default=0,
                              help="cuánto vale tu hora, para sumar el costo del tiempo (0 por defecto)")
    p_recomendar.add_argument("--franja", choices=HORARIOS, help="por defecto, según la hora de la consulta")
    p_recomendar.add_argument("--sin-osrm", action="store_true",
                              help="estimar en línea recta sin consultar OSRM")
    p_recomendar.add_argument("--fecha-consulta", type=fecha_argumento, default=None,
                              help="momento de la consulta, 'AAAA-MM-DD HH:MM:SS' (ahora por defecto)")
    p_recomendar.add_argument("--localidad", default=CIUDAD_POR_DEFECTO[0])
    p_recomendar.add_argument("--provincia", default=CIUDAD_POR_DEFECTO[1])
    p_recomendar.add_argument("--salida", type=Path, default=DIR_SALIDAS,
                              help="carpeta de salida (outputs/ por defecto)")

    p_actualizar = comandos.add_parser("actualizar", help="descarga el archivo oficial de precios vigentes")
    p_actualizar.add_argument("--destino", type=Path, default=ARCHIVO_VIGENTES,
                              help="dónde guardarlo (data/raw/precios_vigentes.csv por defecto)")
    return parser


def actualizar(destino):
    print("Descargando precios vigentes de la Secretaría de Energía...")
    try:
        cantidad = descargar_precios(destino)
    except ErrorDescarga as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(f"Listo: {cantidad} registros en {destino}")
    return 0


def main(argumentos=None):
    args = crear_parser().parse_args(argumentos)
    if args.comando == "actualizar":
        return actualizar(args.destino)

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
        elif args.comando == "recomendar":
            ejecutar_recomendar(registros, fecha_consulta, args)
    except (ErrorEsquema, ErrorRuteo, SinEstaciones, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
