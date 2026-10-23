"""De dirección a coordenadas, y de coordenadas a dirección.

Se prueba primero con Georef, el normalizador de direcciones del Estado
(conoce las alturas de las calles de Rosario y las esquinas, "Mendoza y
Oroño"), y si no encuentra nada, con Nominatim (OpenStreetMap). Para las
sugerencias mientras se escribe se suma Photon, porque Nominatim no permite
usarse para autocompletar.
"""

import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests

from src.config import (
    CENTROS_CIUDAD,
    MARGEN_BUSQUEDA_GRADOS,
    URL_GEOREF,
    URL_NOMINATIM,
    URL_PHOTON,
    USER_AGENT,
)
from src.pipeline import normalizar_texto
from src.ruteo import PATRON_COORDENADAS, ErrorRuteo

# Abreviaturas que escribe la gente y que Georef no reconoce.
ABREVIATURAS = {
    "pte": "presidente",
    "pres": "presidente",
    "gral": "general",
    "avda": "av",
    "avenida": "av",
    "boulevard": "bv",
    "bulevar": "bv",
    "bvard": "bv",
    "esq": "y",
    "esquina": "y",
}


class ErrorDireccion(ErrorRuteo):
    """No se pudo ubicar una dirección."""


@dataclass(frozen=True)
class Lugar:
    nombre: str
    latitud: float
    longitud: float

    @property
    def coordenadas(self):
        return self.latitud, self.longitud


def normalizar_direccion(texto):
    """'Bv. Oroño 1.500' -> 'bv orono 1500'. Georef guarda las calles sin tildes ni ñ."""
    texto = normalizar_texto(texto).replace(".", " ").replace(",", " ")
    texto = re.sub(r"(\d)\s+(\d{3})\b", r"\1\2", texto)  # "1 500" (de "1.500") -> "1500"
    return " ".join(ABREVIATURAS.get(palabra, palabra) for palabra in texto.split())


def recuadro(localidad, provincia):
    """(oeste, sur, este, norte) alrededor del centro de la ciudad, o None."""
    centro = CENTROS_CIUDAD.get((localidad.upper(), provincia.upper()))
    if not centro:
        return None
    lat, lon = centro
    m = MARGEN_BUSQUEDA_GRADOS
    return lon - m, lat - m, lon + m, lat + m


class Geocodificador(ABC):
    """Busca lugares que coincidan con un texto dentro de una ciudad."""

    def __init__(self, cliente=requests, timeout=5):
        self.cliente = cliente
        self.timeout = timeout

    def _pedir(self, url, parametros):
        respuesta = self.cliente.get(
            url, params=parametros, headers={"User-Agent": USER_AGENT}, timeout=self.timeout
        )
        respuesta.raise_for_status()
        return respuesta.json()

    @abstractmethod
    def buscar(self, texto, localidad, provincia, maximo=5):
        """Devuelve una lista de Lugar (puede estar vacía)."""


class GeocodificadorGeoref(Geocodificador):
    def buscar(self, texto, localidad, provincia, maximo=5):
        datos = self._pedir(f"{URL_GEOREF}/direcciones", {
            "direccion": normalizar_direccion(texto),
            "localidad_censal": localidad,
            "provincia": provincia,
            "max": maximo,
        })
        lugares = []
        for direccion in datos.get("direcciones", []):
            ubicacion = direccion.get("ubicacion") or {}
            if ubicacion.get("lat") is None:
                continue
            nombre = direccion["nomenclatura"].split(",")[0].title()
            lugares.append(Lugar(nombre, ubicacion["lat"], ubicacion["lon"]))
        return lugares


class GeocodificadorNominatim(Geocodificador):
    def buscar(self, texto, localidad, provincia, maximo=5):
        parametros = {
            "q": f"{texto}, {localidad}, {provincia}, Argentina",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": maximo,
        }
        caja = recuadro(localidad, provincia)
        if caja:
            oeste, sur, este, norte = caja
            parametros["viewbox"] = f"{oeste},{norte},{este},{sur}"
            parametros["bounded"] = 1
        return [
            Lugar(nombre_corto(r.get("address", {}), r.get("display_name", texto)), float(r["lat"]), float(r["lon"]))
            for r in self._pedir(f"{URL_NOMINATIM}/search", parametros)
        ]

    def describir(self, latitud, longitud):
        """La dirección más cercana a un punto, o None."""
        datos = self._pedir(f"{URL_NOMINATIM}/reverse", {
            "lat": latitud, "lon": longitud, "format": "jsonv2", "zoom": 18, "addressdetails": 1,
        })
        if "address" not in datos:
            return None
        return nombre_corto(datos["address"], datos.get("display_name"))


class GeocodificadorPhoton(Geocodificador):
    def buscar(self, texto, localidad, provincia, maximo=5):
        parametros = {"q": f"{texto}, {localidad}", "limit": maximo, "lang": "default"}
        caja = recuadro(localidad, provincia)
        if caja:
            parametros["bbox"] = ",".join(str(v) for v in caja)
        lugares = []
        for elemento in self._pedir(f"{URL_PHOTON}/api/", parametros).get("features", []):
            p = elemento["properties"]
            calle = p.get("street") or p.get("name")
            if not calle:
                continue
            nombre = f"{calle} {p['housenumber']}" if p.get("housenumber") else calle
            if p.get("district"):
                nombre += f" ({p['district']})"
            longitud, latitud = elemento["geometry"]["coordinates"]
            lugares.append(Lugar(nombre, latitud, longitud))
        return lugares


def nombre_corto(direccion, respaldo):
    """'Bulevar Oroño 1500, Rosario' en vez del display_name entero."""
    calle = direccion.get("road") or direccion.get("pedestrian") or direccion.get("amenity")
    if not calle:
        return (respaldo or "").split(",")[0]
    if direccion.get("house_number"):
        calle += f" {direccion['house_number']}"
    return calle


def coordenadas_escritas(texto):
    """(lat, lon) si el texto son coordenadas 'lat,lon'; None si no."""
    coincidencia = PATRON_COORDENADAS.match(texto)
    if not coincidencia:
        return None
    latitud, longitud = float(coincidencia.group(1)), float(coincidencia.group(2))
    if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
        raise ErrorDireccion(f"Coordenadas fuera de rango: {texto}")
    return latitud, longitud


def _consultar(geocodificador, texto, localidad, provincia, maximo):
    try:
        return geocodificador.buscar(texto, localidad, provincia, maximo)
    except (requests.RequestException, ValueError, KeyError):
        # Si un servicio falla se sigue con el siguiente.
        return []


def ubicar(texto, localidad="ROSARIO", provincia="SANTA FE", geocodificadores=None):
    """Pasa 'lat,lon' o una dirección a (lat, lon), probando los servicios en orden."""
    coordenadas = coordenadas_escritas(texto)
    if coordenadas:
        return coordenadas
    if not texto.strip():
        raise ErrorDireccion("La dirección está vacía")
    for geocodificador in geocodificadores or [GeocodificadorGeoref(), GeocodificadorNominatim()]:
        lugares = _consultar(geocodificador, texto, localidad, provincia, 1)
        if lugares:
            return lugares[0].coordenadas
    raise ErrorDireccion(f"No se encontró la dirección '{texto}' en {localidad.title()}")


def nombra_la_calle(lugar, texto):
    """True si el nombre del lugar contiene todas las palabras escritas (salvo números).

    Photon devuelve cualquier cosa que se parezca ("Autopista ..." para
    "cordoba"); así quedan solo las que de verdad nombran esa calle.
    """
    nombre = normalizar_direccion(lugar.nombre)
    palabras = [p for p in normalizar_direccion(texto).split() if not p.isdigit() and len(p) > 2]
    return all(palabra in nombre for palabra in palabras)


def sugerir(texto, localidad="ROSARIO", provincia="SANTA FE", maximo=5, geocodificadores=None):
    """Hasta `maximo` lugares para mostrar mientras se escribe, sin repetidos.

    Los servicios se consultan a la vez, para que la lista aparezca rápido;
    se muestran primero los resultados del primero (Georef).
    """
    geocodificadores = geocodificadores or [GeocodificadorGeoref(), GeocodificadorPhoton()]
    with ThreadPoolExecutor(max_workers=len(geocodificadores)) as hilos:
        respuestas = list(hilos.map(
            lambda g: _consultar(g, texto, localidad, provincia, maximo), geocodificadores
        ))
    lugares, vistos = [], set()
    for lugar in (lugar for respuesta in respuestas for lugar in respuesta):
        clave = normalizar_direccion(lugar.nombre)
        if clave not in vistos and nombra_la_calle(lugar, texto):
            vistos.add(clave)
            lugares.append(lugar)
    return lugares[:maximo]
