"""Distancias en auto (OSRM) y ubicación de direcciones (Nominatim).

Si OSRM no responde se estima en línea recta, y el resultado queda marcado
como estimación para que la app lo avise.
"""

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from src.config import (
    CENTROS_CIUDAD,
    FACTOR_RODEO,
    MARGEN_BUSQUEDA_GRADOS,
    URL_NOMINATIM,
    URL_OSRM,
    USER_AGENT,
    VELOCIDAD_PROMEDIO_KMH,
)

PATRON_COORDENADAS = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
RADIO_TIERRA_KM = 6371.0


class ErrorRuteo(Exception):
    """No se pudo calcular una ruta o ubicar una dirección."""


@dataclass(frozen=True)
class Tramo:
    km: float
    minutos: float
    estimado: bool = False

    def __add__(self, otro):
        return Tramo(self.km + otro.km, self.minutos + otro.minutos, self.estimado or otro.estimado)

    def __sub__(self, otro):
        return Tramo(self.km - otro.km, self.minutos - otro.minutos, self.estimado or otro.estimado)


def distancia_km(a, b):
    """Distancia sobre la superficie terrestre (haversine) entre (lat, lon)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


class Ruteador(ABC):
    """Calcula un tramo en auto que pasa por los puntos (lat, lon) en orden."""

    @abstractmethod
    def ruta(self, *puntos):
        """Devuelve un Tramo."""


class RuteadorLineaRecta(Ruteador):
    """Estimación sin internet: línea recta corregida por un factor de rodeo."""

    def __init__(self, factor_rodeo=FACTOR_RODEO, velocidad_kmh=VELOCIDAD_PROMEDIO_KMH):
        self.factor_rodeo = factor_rodeo
        self.velocidad_kmh = velocidad_kmh

    def ruta(self, *puntos):
        km = sum(distancia_km(a, b) for a, b in zip(puntos, puntos[1:])) * self.factor_rodeo
        return Tramo(km, km / self.velocidad_kmh * 60, estimado=True)


class RuteadorOSRM(Ruteador):
    """Distancia y duración reales por calle, con el servidor público de OSRM.

    Si una consulta falla usa el respaldo en línea recta, y desde ese
    momento deja de intentar con OSRM para no demorar cada estación.
    """

    def __init__(self, url=URL_OSRM, timeout=5, cliente=requests, respaldo=None):
        self.url = url
        self.timeout = timeout
        self.cliente = cliente
        self.respaldo = respaldo or RuteadorLineaRecta()
        self.falla = None

    def ruta(self, *puntos):
        if self.falla is None:
            try:
                return self._consultar(puntos)
            except (requests.RequestException, ValueError, KeyError, IndexError) as error:
                self.falla = f"OSRM no respondió ({error.__class__.__name__})"
        return self.respaldo.ruta(*puntos)

    def _consultar(self, puntos):
        # OSRM recibe longitud,latitud separados por ';'.
        coordenadas = ";".join(f"{lon},{lat}" for lat, lon in puntos)
        respuesta = self.cliente.get(
            f"{self.url}/route/v1/driving/{coordenadas}",
            params={"overview": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
        if datos.get("code") != "Ok":
            raise ValueError(datos.get("message", datos.get("code")))
        ruta = datos["routes"][0]
        return Tramo(ruta["distance"] / 1000, ruta["duration"] / 60)


def ubicar(texto, localidad="ROSARIO", provincia="SANTA FE", cliente=requests):
    """Pasa 'lat,lon' o una dirección a (lat, lon).

    Las direcciones se buscan con Nominatim agregando la ciudad, porque el
    chofer escribe 'Oroño 1500' y no la dirección completa. Si se conoce el
    centro de la ciudad, la búsqueda se limita a sus alrededores.
    """
    coincidencia = PATRON_COORDENADAS.match(texto)
    if coincidencia:
        latitud, longitud = float(coincidencia.group(1)), float(coincidencia.group(2))
        if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
            raise ErrorRuteo(f"Coordenadas fuera de rango: {texto}")
        return latitud, longitud

    parametros = {"q": f"{texto}, {localidad}, {provincia}, Argentina", "format": "jsonv2", "limit": 1}
    centro = CENTROS_CIUDAD.get((localidad.upper(), provincia.upper()))
    if centro:
        lat, lon, margen = *centro, MARGEN_BUSQUEDA_GRADOS
        parametros["viewbox"] = f"{lon - margen},{lat + margen},{lon + margen},{lat - margen}"
        parametros["bounded"] = 1

    try:
        respuesta = cliente.get(
            f"{URL_NOMINATIM}/search",
            params=parametros,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        respuesta.raise_for_status()
        resultados = respuesta.json()
    except (requests.RequestException, ValueError) as error:
        raise ErrorRuteo(f"No se pudo buscar la dirección '{texto}': {error}") from error
    if not resultados:
        raise ErrorRuteo(f"No se encontró la dirección '{texto}' en {localidad.title()}")
    return float(resultados[0]["lat"]), float(resultados[0]["lon"])
