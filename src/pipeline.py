"""Validación, limpieza y transformación de los precios en surtidor.

Recibe los registros tal como los devuelve fuentes.py (todo texto) y los
separa en válidos, ya con sus tipos, y rechazados, con el motivo de cada
rechazo. Ninguna fila se pierde: cada una termina en una de las dos listas.
Después los válidos se pasan a objetos del dominio para quedarse con el
precio vigente de cada estación.
"""

import csv
import re
import unicodedata
from datetime import datetime, timedelta
from statistics import median

from src.config import (
    CAMPOS_PRECIO,
    DIAS_MAXIMOS_VIGENCIA,
    FACTOR_MAXIMO_PRECIO,
    FACTOR_MINIMO_PRECIO,
    LIMITES_ARGENTINA,
    LIMITES_PROVINCIA,
    MINIMO_PARA_MEDIANA,
)
from src.modelos import HORARIOS, Estacion, PrecioEstacion

PATRON_CUIT = re.compile(r"^(\d{2})-(\d{8})-(\d)$")
PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

PATRON_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

# Nombre del producto ya normalizado (minúsculas, sin tildes, espacios
# simples) -> categoría que usa la app. El gasoil grado 3 es el premium y
# se compara aparte: no es el mismo producto que el grado 2.
NOMBRES_PRODUCTO = {
    "nafta (super) entre 92 y 95 ron": "super",
    "nafta (premium) de mas de 95 ron": "premium",
    "gas oil grado 2": "gasoil",
    "gas oil grado 3": "gasoil premium",
    "gnc": "gnc",
}

CAMPOS_OBLIGATORIOS = (
    "idempresa", "cuit", "localidad", "provincia", "producto",
    "tipohorario", "precio", "fecha_vigencia", "latitud", "longitud",
)


class ErrorEsquema(Exception):
    """Al archivo le faltan columnas que la aplicación necesita."""


def normalizar_texto(texto):
    """Minúsculas, sin tildes y con un solo espacio entre palabras."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def normalizar_campos(registro):
    """Deja solo los campos que se usan, con nombres y valores sin espacios de más."""
    limpio = {clave.strip().lower(): valor.strip() for clave, valor in registro.items()}
    return {campo: limpio.get(campo, "") for campo in CAMPOS_PRECIO}


def validar_esquema(registros):
    campos = {clave.strip().lower() for clave in registros[0]}
    faltantes = [c for c in CAMPOS_PRECIO if c not in campos]
    if faltantes:
        raise ErrorEsquema(f"Faltan columnas: {', '.join(faltantes)}")


def cuit_valido(cuit):
    """Formato NN-NNNNNNNN-N y dígito verificador correcto.

    Se multiplican los 10 primeros dígitos por los pesos y se toma
    11 - (suma % 11). Si da 11 el dígito es 0; si da 10 el CUIT es
    inválido (en ese caso la AFIP cambia el prefijo, así que un CUIT
    real nunca termina así).
    """
    coincidencia = PATRON_CUIT.match(cuit)
    if not coincidencia:
        return False
    digitos = coincidencia.group(1) + coincidencia.group(2)
    suma = sum(int(d) * peso for d, peso in zip(digitos, PESOS_CUIT))
    esperado = 11 - suma % 11
    if esperado == 11:
        esperado = 0
    elif esperado == 10:
        return False
    return esperado == int(coincidencia.group(3))


def leer_fecha(texto):
    """Devuelve el datetime o un texto con el problema."""
    if not PATRON_FECHA.match(texto):
        return f"fecha con formato inválido: {texto}"
    try:
        return datetime.strptime(texto, FORMATO_FECHA)
    except ValueError:
        # El formato está bien pero la fecha no existe (ej. 2026-02-30).
        return f"fecha inexistente: {texto}"


def leer_numero(texto):
    try:
        return float(texto)
    except ValueError:
        return None


def categoria_producto(nombre):
    return NOMBRES_PRODUCTO.get(normalizar_texto(nombre))


def problema_coordenadas(latitud, longitud, provincia):
    if latitud == 0 and longitud == 0:
        return "coordenadas en (0, 0)"
    lat_min, lat_max, lon_min, lon_max = LIMITES_PROVINCIA.get(provincia, LIMITES_ARGENTINA)
    if not (lat_min <= latitud <= lat_max and lon_min <= longitud <= lon_max):
        return f"coordenadas fuera de {provincia or 'Argentina'}"
    return None


def validar_registro(registro, fecha_consulta):
    """Devuelve (precio, motivos). Si hay motivos, precio es None."""
    motivos = [f"falta {campo}" for campo in CAMPOS_OBLIGATORIOS if not registro[campo]]
    if motivos:
        return None, motivos

    if not cuit_valido(registro["cuit"]):
        motivos.append(f"CUIT inválido: {registro['cuit']}")

    producto = categoria_producto(registro["producto"])
    if producto is None:
        motivos.append(f"producto desconocido: {registro['producto']}")

    horario = registro["tipohorario"].capitalize()
    if horario not in HORARIOS:
        motivos.append(f"franja horaria desconocida: {registro['tipohorario']}")

    precio = leer_numero(registro["precio"])
    if precio is None:
        motivos.append(f"precio no numérico: {registro['precio']}")
    elif precio <= 0:
        motivos.append(f"precio no positivo: {registro['precio']}")

    fecha = leer_fecha(registro["fecha_vigencia"])
    if isinstance(fecha, str):
        motivos.append(fecha)
    elif fecha_consulta - fecha > timedelta(days=DIAS_MAXIMOS_VIGENCIA):
        motivos.append(f"vigencia de más de {DIAS_MAXIMOS_VIGENCIA} días")

    latitud = leer_numero(registro["latitud"])
    longitud = leer_numero(registro["longitud"])
    if latitud is None or longitud is None:
        motivos.append("coordenadas no numéricas")
    else:
        problema = problema_coordenadas(latitud, longitud, registro["provincia"].upper())
        if problema:
            motivos.append(problema)

    if motivos:
        return None, motivos

    return {
        **registro,
        "producto": producto,
        "tipohorario": horario,
        "precio": precio,
        "fecha_vigencia": fecha,
        "latitud": latitud,
        "longitud": longitud,
    }, []


def rechazo(numero_fila, registro, motivos):
    return {"fila": numero_fila, "motivo": " | ".join(motivos), **registro}


def limpiar_precios(registros, fecha_consulta=None):
    """Valida, saca duplicados y precios fuera de rango.

    Devuelve (validos, rechazos). Cada rechazo lleva el número de fila
    (1 es el primer registro, sin contar el encabezado) y el motivo.
    """
    if not registros:
        return [], []
    validar_esquema(registros)
    fecha_consulta = fecha_consulta or datetime.now()

    candidatos, rechazos = [], []
    vistos = {}
    for numero_fila, original in enumerate(registros, start=1):
        registro = normalizar_campos(original)
        precio, motivos = validar_registro(registro, fecha_consulta)
        if motivos:
            rechazos.append(rechazo(numero_fila, registro, motivos))
            continue

        clave = (precio["idempresa"], precio["producto"], precio["tipohorario"],
                 precio["precio"], precio["fecha_vigencia"])
        if clave in vistos:
            rechazos.append(rechazo(numero_fila, registro, [f"duplicado de la fila {vistos[clave]}"]))
            continue
        vistos[clave] = numero_fila
        candidatos.append((numero_fila, registro, precio))

    medianas = medianas_por_producto(precio for _, _, precio in candidatos)
    validos = []
    for numero_fila, registro, precio in candidatos:
        mediana = medianas.get(precio["producto"])
        if mediana and not (FACTOR_MINIMO_PRECIO * mediana <= precio["precio"] <= FACTOR_MAXIMO_PRECIO * mediana):
            motivo = f"precio fuera de rango: {precio['precio']:g} (mediana {mediana:g})"
            rechazos.append(rechazo(numero_fila, registro, [motivo]))
        else:
            validos.append(precio)

    rechazos.sort(key=lambda r: r["fila"])
    return validos, rechazos


def medianas_por_producto(precios):
    por_producto = {}
    for precio in precios:
        por_producto.setdefault(precio["producto"], []).append(precio["precio"])
    return {
        producto: median(valores)
        for producto, valores in por_producto.items()
        if len(valores) >= MINIMO_PARA_MEDIANA
    }


def resumen_motivos(rechazos):
    """Cuenta los rechazos por tipo de motivo (sin el detalle del valor)."""
    conteo = {}
    for fila in rechazos:
        for motivo in fila["motivo"].split(" | "):
            tipo = motivo.split(":")[0]
            if tipo.startswith("duplicado"):
                tipo = "duplicado"
            conteo[tipo] = conteo.get(tipo, 0) + 1
    return dict(sorted(conteo.items(), key=lambda par: -par[1]))


def guardar_csv(filas, ruta, campos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)


def armar_precios(validos):
    """Pasa los registros limpios a objetos PrecioEstacion.

    Todas las filas de una estación comparten el mismo objeto Estacion,
    armado con los datos de la primera fila en que aparece.
    """
    estaciones = {}
    precios = []
    for fila in validos:
        estacion = estaciones.get(fila["idempresa"])
        if estacion is None:
            estacion = Estacion(
                idempresa=fila["idempresa"],
                cuit=fila["cuit"],
                empresa=fila["empresa"],
                direccion=fila["direccion"],
                localidad=fila["localidad"],
                provincia=fila["provincia"],
                bandera=fila["empresabandera"],
                latitud=fila["latitud"],
                longitud=fila["longitud"],
            )
            estaciones[fila["idempresa"]] = estacion
        precios.append(PrecioEstacion(
            estacion=estacion,
            producto=fila["producto"],
            horario=fila["tipohorario"],
            precio=fila["precio"],
            vigente_desde=fila["fecha_vigencia"],
        ))
    return precios


def filtrar_ciudad(precios, localidad, provincia):
    localidad, provincia = normalizar_texto(localidad), normalizar_texto(provincia)
    return [
        p for p in precios
        if normalizar_texto(p.estacion.localidad) == localidad
        and normalizar_texto(p.estacion.provincia) == provincia
    ]


def precios_vigentes(precios, fecha_consulta):
    """El precio que rige en cada estación, producto y franja.

    Es el más reciente que no supera el momento de la consulta: los que
    empiezan a regir después todavía no se cobran. Si dos tienen la misma
    vigencia se queda el más caro, para no prometer un ahorro que quizás
    no existe.
    """
    vigentes = {}
    for precio in precios:
        if not precio.rige_en(fecha_consulta):
            continue
        actual = vigentes.get(precio.clave)
        if actual is None or (precio.vigente_desde, precio.precio) > (actual.vigente_desde, actual.precio):
            vigentes[precio.clave] = precio
    return sorted(
        vigentes.values(),
        key=lambda p: (p.producto, p.horario, p.precio, p.estacion.idempresa),
    )


def procesar(registros, fecha_consulta, localidad, provincia):
    """Todo el flujo: limpia, arma los objetos, filtra la ciudad y elige vigentes.

    Devuelve (vigentes, rechazos).
    """
    validos, rechazos = limpiar_precios(registros, fecha_consulta)
    precios = filtrar_ciudad(armar_precios(validos), localidad, provincia)
    return precios_vigentes(precios, fecha_consulta), rechazos
