"""Distancias en auto: OSRM, o línea recta si no responde.

Si OSRM no responde se estima en línea recta, y el resultado queda marcado
como estimación para que la app lo avise.
"""

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from src.config import (
    FACTOR_RODEO,
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

    def via(self, origen, paradas, destino):
        """El tramo origen -> parada -> destino para cada parada."""
        return [self.ruta(origen, parada, destino) for parada in paradas]


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
        return self._con_respaldo(self._ruta, self.respaldo.ruta, *puntos)

    def via(self, origen, paradas, destino):
        if not paradas:
            return []
        return self._con_respaldo(self._tabla, self.respaldo.via, origen, paradas, destino)

    def _con_respaldo(self, consulta, respaldo, *argumentos):
        if self.falla is None:
            try:
                return consulta(*argumentos)
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
                self.falla = f"OSRM no respondió ({error.__class__.__name__})"
        return respaldo(*argumentos)

    def _pedir(self, servicio, puntos, parametros):
        # OSRM recibe longitud,latitud separados por ';'.
        coordenadas = ";".join(f"{lon},{lat}" for lat, lon in puntos)
        respuesta = self.cliente.get(
            f"{self.url}/{servicio}/v1/driving/{coordenadas}",
            params=parametros,
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()
        if datos.get("code") != "Ok":
            raise ValueError(datos.get("message", datos.get("code")))
        return datos

    def _ruta(self, *puntos):
        ruta = self._pedir("route", puntos, {"overview": "false"})["routes"][0]
        return Tramo(ruta["distance"] / 1000, ruta["duration"] / 60)

    def _tabla(self, origen, paradas, destino):
        """Todas las paradas en una sola consulta al servicio "table".

        Se piden las distancias desde el origen y desde cada parada hasta
        cada parada y el destino; de esa matriz salen los dos tramos
        (origen -> parada y parada -> destino) de cada estación.
        """
        n = len(paradas)
        puntos = [origen, destino, *paradas]
        indices_paradas = [str(i) for i in range(2, n + 2)]
        datos = self._pedir("table", puntos, {
            "sources": ";".join(["0", *indices_paradas]),
            "destinations": ";".join([*indices_paradas, "1"]),
            "annotations": "distance,duration",
        })
        metros, segundos = datos["distances"], datos["durations"]
        tramos = []
        for i in range(n):
            # Fila 0: desde el origen. Fila i + 1: desde la parada i. Columna n: el destino.
            # Si OSRM no encuentra camino devuelve None y la suma da TypeError.
            km = (metros[0][i] + metros[i + 1][n]) / 1000
            minutos = (segundos[0][i] + segundos[i + 1][n]) / 60
            tramos.append(Tramo(km, minutos))
        return tramos

