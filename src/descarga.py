"""Descarga del archivo oficial de precios vigentes."""

import os
import time
from pathlib import Path

import requests

from src.config import URL_PRECIOS_VIGENTES, USER_AGENT
from src.fuentes import ErrorFuente, FuenteCSV
from src.pipeline import ErrorEsquema, validar_esquema


class ErrorDescarga(Exception):
    """No se pudo bajar el archivo o lo que llegó no es el dataset esperado."""


def descargar_precios(destino, url=URL_PRECIOS_VIGENTES, cliente=requests, timeout=(10, 60)):
    """Baja el CSV a `destino` y devuelve cuántos registros trae.

    Primero se guarda en un archivo temporal y se controla que tenga las
    columnas esperadas; recién ahí reemplaza al anterior, así una descarga
    cortada o una página de error no pisan datos buenos. El timeout es
    (conexión, lectura): si el servidor ni contesta, se abandona rápido.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".descargando")

    try:
        respuesta = cliente.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        respuesta.raise_for_status()
        temporal.write_bytes(respuesta.content)
        registros = FuenteCSV().cargar(temporal)
        validar_esquema(registros)
    except requests.RequestException as error:
        temporal.unlink(missing_ok=True)
        raise ErrorDescarga(f"No se pudo descargar {url}: {error}") from error
    except (ErrorFuente, ErrorEsquema) as error:
        temporal.unlink(missing_ok=True)
        raise ErrorDescarga(f"El archivo descargado no es el esperado: {error}") from error

    os.replace(temporal, destino)
    return len(registros)


def antiguedad_minutos(ruta):
    """Minutos desde la última modificación del archivo (None si no existe)."""
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    return (time.time() - ruta.stat().st_mtime) / 60
