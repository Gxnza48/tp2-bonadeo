"""Lectura de registros de precios desde archivos CSV y JSON.

Todas las fuentes devuelven lo mismo: una lista de diccionarios, uno por
registro, con los valores como texto. La conversión de tipos se hace
después, en el pipeline, así no importa de qué formato vino el dato.
"""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path


class ErrorFuente(Exception):
    """El archivo no se pudo leer o no tiene la forma esperada."""


class FuenteDatos(ABC):
    """Base común: controla el archivo y delega la lectura en _leer()."""

    def cargar(self, ruta):
        ruta = Path(ruta)
        if not ruta.is_file():
            raise ErrorFuente(f"No existe el archivo: {ruta}")
        if ruta.stat().st_size == 0:
            raise ErrorFuente(f"El archivo está vacío: {ruta}")

        try:
            registros = self._leer(ruta)
        except UnicodeDecodeError as error:
            raise ErrorFuente(f"{ruta.name}: no está codificado en UTF-8") from error

        if not registros:
            raise ErrorFuente(f"{ruta.name}: no tiene registros")
        return registros

    @abstractmethod
    def _leer(self, ruta):
        """Devuelve la lista de registros del archivo."""


class FuenteCSV(FuenteDatos):
    def __init__(self, separador=","):
        self.separador = separador

    def _leer(self, ruta):
        # utf-8-sig porque el archivo oficial viene con BOM.
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            lector = csv.reader(archivo, delimiter=self.separador)
            encabezado = [columna.strip() for columna in next(lector, [])]
            if not any(encabezado):
                raise ErrorFuente(f"{ruta.name}: falta el encabezado")

            repetidas = sorted({c for c in encabezado if encabezado.count(c) > 1})
            if repetidas:
                raise ErrorFuente(
                    f"{ruta.name}: columnas repetidas en el encabezado: {', '.join(repetidas)}"
                )

            registros = []
            for fila in lector:
                if not fila:
                    continue
                if len(fila) != len(encabezado):
                    raise ErrorFuente(
                        f"{ruta.name}, línea {lector.line_num}: se esperaban "
                        f"{len(encabezado)} columnas y hay {len(fila)}"
                    )
                registros.append(dict(zip(encabezado, fila)))
        return registros


class FuenteJSON(FuenteDatos):
    def _leer(self, ruta):
        with open(ruta, encoding="utf-8") as archivo:
            try:
                datos = json.load(archivo)
            except json.JSONDecodeError as error:
                raise ErrorFuente(
                    f"{ruta.name}: JSON mal formado (línea {error.lineno}, columna {error.colno})"
                ) from error

        if not isinstance(datos, list):
            raise ErrorFuente(
                f"{ruta.name}: se esperaba una lista de objetos y llegó un {type(datos).__name__}"
            )

        registros = []
        for posicion, objeto in enumerate(datos, start=1):
            if not isinstance(objeto, dict):
                raise ErrorFuente(f"{ruta.name}: el elemento {posicion} no es un objeto")
            # Igual que en el CSV: todo como texto, y null pasa a vacío.
            registros.append(
                {campo: "" if valor is None else str(valor) for campo, valor in objeto.items()}
            )
        return registros


FUENTES = {".csv": FuenteCSV, ".json": FuenteJSON}


def fuente_para(ruta):
    """Elige la fuente según la extensión del archivo."""
    extension = Path(ruta).suffix.lower()
    if extension not in FUENTES:
        raise ErrorFuente(
            f"Formato no soportado: '{extension or 'sin extensión'}'. Se aceptan .csv y .json"
        )
    return FUENTES[extension]()
