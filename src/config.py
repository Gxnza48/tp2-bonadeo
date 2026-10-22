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

# --- Reglas de limpieza (justificadas en el README) ---

# Un precio con vigencia más vieja que esto se descarta: la estación dejó
# de informar y el precio ya no es el real.
DIAS_MAXIMOS_VIGENCIA = 60

# Un precio se considera fuera de rango si se aleja de la mediana de su
# producto más allá de estos factores. Solo se aplica si hay suficientes
# precios del producto como para que la mediana diga algo.
FACTOR_MINIMO_PRECIO = 0.5
FACTOR_MAXIMO_PRECIO = 1.5
MINIMO_PARA_MEDIANA = 5

# Límites aproximados (lat_min, lat_max, lon_min, lon_max).
LIMITES_ARGENTINA = (-55.1, -21.7, -73.6, -53.6)
LIMITES_PROVINCIA = {
    "SANTA FE": (-34.5, -28.0, -63.0, -58.8),
}
