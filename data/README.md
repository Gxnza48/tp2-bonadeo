# Datos

## Fuente principal: precios en surtidor

| | |
|---|---|
| Dataset | Precios en Surtidor – Resolución 314/2016 |
| Responsable | Secretaría de Energía de la Nación (Subsecretaría de Hidrocarburos) |
| URL | https://www.datos.gob.ar/dataset/energia-precios-surtidor---resolucion-3142016 |
| Portal original | http://datos.energia.gob.ar/dataset/precios-en-surtidor |
| Licencia | Creative Commons Attribution 4.0 (CC-BY-4.0) |
| Formato | CSV (UTF-8 con BOM, separado por comas) |
| Actualización | Cada hora |
| Fecha de consulta | 21/10/2026 (la muestra real, 22/10/2026) |

El portal publica dos archivos: **precios vigentes** (el que usa la app) y
**precios históricos**. El 21/10/2026 el de vigentes tenía 36.649 filas en
todo el país, 782 de ellas en Rosario.

Las estaciones cargan sus precios en la Secretaría por obligación de la
Resolución 314/2016; el dataset es lo que informa cada estación, no un
relevamiento independiente.

### Unidad de análisis

Cada fila es **el precio que informa una estación para un producto y una
franja horaria (Diurno o Nocturno), vigente desde `fecha_vigencia`**.
Una misma estación aparece en varias filas: una por producto y franja.

### Variables que se usan

| Variable | Tipo | Descripción |
|---|---|---|
| `idempresa` | texto | Identificador de la estación en el registro de la Secretaría |
| `cuit` | texto | CUIT del operador, formato `NN-NNNNNNNN-N` |
| `empresa` | texto | Razón social del operador |
| `direccion` | texto | Calle y número de la estación |
| `localidad` | texto | Localidad, en mayúsculas (ej. `ROSARIO`) |
| `provincia` | texto | Provincia, en mayúsculas (ej. `SANTA FE`) |
| `producto` | texto | Combustible (ver valores abajo) |
| `tipohorario` | texto | `Diurno` o `Nocturno` |
| `precio` | número | Precio por litro (por m³ en GNC), en pesos |
| `fecha_vigencia` | fecha y hora | Desde cuándo rige el precio, `AAAA-MM-DD HH:MM:SS` |
| `empresabandera` | texto | Bandera de la estación (YPF, SHELL C.A.P.S.A., AXION, PUMA, BLANCA...) |
| `latitud` | número | Latitud en grados decimales (WGS84) |
| `longitud` | número | Longitud en grados decimales (WGS84) |

El archivo trae además `indice_tiempo`, `region`, `idproducto`,
`idtipohorario`, `idempresabandera` y `geojson`, que se ignoran.

Valores de `producto` en el archivo de vigentes:

- `Nafta (súper) entre 92 y 95 Ron`
- `Nafta (premium) de más de 95 Ron`
- `Gas Oil Grado 2`
- `Gas Oil Grado 3`
- `GNC`

## Muestras versionadas (`muestra/`)

### Muestra real: `precios_rosario_real.csv`

86 filas reales del archivo de precios vigentes, descargado el 22/10/2026,
de 10 estaciones de Rosario. Tiene todas las columnas originales, sin
modificar. Se eligieron estaciones con precios recientes, otras con
precios de distintas antigüedades y otras que no actualizan desde
2025, para que la limpieza tenga los tres casos.

Con `--fecha-consulta "2026-10-22 12:00:00"` quedan 56 filas válidas y 30
rechazadas, todas por vigencia vieja.

### Muestra ficticia: `precios_muestra.csv` y `precios_muestra.json`

Los dos archivos tienen el mismo contenido:
15 filas de **6 estaciones ficticias** de Rosario, con las mismas columnas
que el dataset real. Los nombres, CUIT y direcciones son inventados; los
precios están en el orden de magnitud de octubre de 2026.

Sirven para probar la lectura sin depender de internet, y traen a propósito
los problemas que la limpieza tiene que resolver:

| Caso | Dónde |
|---|---|
| La misma estación con un precio viejo y uno vigente | 9001, súper |
| Precio en 0 | 9003, súper |
| Coordenadas en (0, 0) | 9005, todas sus filas |
| Fila duplicada | 9002, gasoil |
| Producto escrito distinto (minúsculas y sin tilde) | 9004, súper |
| Vigencia de más de un año | 9006, GNC |

La descarga completa se hace con `python -m src.main actualizar` y queda en
`data/raw/precios_vigentes.csv`, que no se versiona.

## Ruteo: OSRM

Para la distancia y la duración del desvío se usa el servidor público de
[OSRM](https://project-osrm.org/) sobre datos de OpenStreetMap (licencia
ODbL, © colaboradores de OpenStreetMap). No necesita clave. Si no responde,
la app estima en línea recta y marca el resultado como estimación. Para
pasar direcciones a coordenadas se usa Nominatim, también de OpenStreetMap,
limitando la búsqueda a los alrededores de la ciudad. Los dos servidores
públicos piden un uso moderado (Nominatim, como máximo una consulta por
segundo) y que la aplicación se identifique; la app manda un User-Agent
propio.

## Limitaciones y sesgos

- **El precio lo informa la estación.** Si una estación no actualiza, el
  dataset muestra un precio viejo. Hay vigencias de años anteriores (en
  Rosario aparecen precios de GNC de 2023), por eso se descartan las
  vigencias demasiado viejas en lugar de suponer un precio.
- **No incluye descuentos** por app de la petrolera, tarjeta o club de
  beneficios, que para un chofer pueden cambiar cuál conviene.
- **Coordenadas con errores**: algunas estaciones tienen (0, 0) o puntos
  fuera de su provincia; esas filas se rechazan.
- **Cobertura despareja**: no todas las estaciones informan todos los
  productos; el GNC tiene bastantes menos filas que las naftas.
- **Muchas estaciones dejaron de informar.** El 22/10/2026, de 95
  estaciones de Rosario solo 16 tenían precios de los últimos 60 días; el
  resto seguía con precios de 2025. La recomendación solo puede elegir entre
  las que informan, lo que deja afuera a estaciones que quizás son más
  baratas.
- **Coordenadas que no corresponden a la localidad**: hay estaciones con
  localidad ROSARIO y coordenadas a más de 100 km, todavía dentro de Santa
  Fe. El control por provincia no las detecta.
- **Gas Oil Grado 3** es el gasoil premium y se compara aparte del Grado 2.
