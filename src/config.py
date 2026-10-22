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

# --- Recomendación ---

URL_OSRM = "https://router.project-osrm.org"
URL_NOMINATIM = "https://nominatim.openstreetmap.org"
# Nominatim y OSRM piden identificar la aplicación.
USER_AGENT = "nafteando-tp2 (github.com/Gxnza48/tp2-bonadeo)"

# Respaldo cuando OSRM no responde: en ciudad, el recorrido por calle es
# alrededor de un 30 % más largo que la línea recta.
FACTOR_RODEO = 1.3
VELOCIDAD_PROMEDIO_KMH = 25

# Solo se calcula el desvío de las estaciones a menos de esta distancia
# (en línea recta) del origen o del destino, para no consultar OSRM por
# estaciones que nunca van a convenir.
RADIO_BUSQUEDA_KM = 6

# Centro aproximado de cada ciudad (lat, lon). Las direcciones se buscan
# solo en un recuadro de MARGEN_BUSQUEDA_GRADOS alrededor (unos 13 km),
# porque si no "Córdoba 1500" puede aparecer en Funes.
CENTROS_CIUDAD = {
    ("ROSARIO", "SANTA FE"): (-32.9468, -60.6393),
}
MARGEN_BUSQUEDA_GRADOS = 0.12

# Franja nocturna (de las 22 a las 6). El dataset no la define; es un
# supuesto de la app.
HORA_INICIO_NOCTURNO = 22
HORA_FIN_NOCTURNO = 6
