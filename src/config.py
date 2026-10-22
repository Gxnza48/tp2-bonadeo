"""Rutas del proyecto y valores por defecto."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "data"
DIR_MUESTRA = DIR_DATOS / "muestra"
DIR_CRUDOS = DIR_DATOS / "raw"
DIR_SALIDAS = RAIZ / "outputs"

# Columnas del dataset de la Secretaría de Energía que usa la aplicación.
# El archivo original trae otras (indice_tiempo, region, idproducto,
# idtipohorario, idempresabandera, geojson) que se ignoran.
CAMPOS_PRECIO = [
    "idempresa",
    "cuit",
    "empresa",
    "direccion",
    "localidad",
    "provincia",
    "producto",
    "tipohorario",
    "precio",
    "fecha_vigencia",
    "empresabandera",
    "latitud",
    "longitud",
]

# (localidad, provincia) tal como aparecen en el dataset.
CIUDAD_POR_DEFECTO = ("ROSARIO", "SANTA FE")
