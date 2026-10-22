# Nafteando

**¿Vale la pena desviarme para cargar más barato?**

Trabajo práctico 2 de Programación Orientada a Datos — Licenciatura en
Ciencia de Datos, UCA, 2026.
Autor: Gonzalo Bonadeo.

## Problema

Los choferes de Uber, Cabify o DiDi, los remiseros y los repartidores cargan
combustible varias veces por semana, y es su principal costo. Hay
herramientas que muestran dónde está más barato, pero no responden lo que
importa en la calle: **¿conviene desviarse hasta ahí?** El desvío gasta
nafta y tiempo, y para un chofer el tiempo es plata.

## Usuario

Un chofer que está trabajando, abre la web en el celular y en unos segundos
quiere saber a qué estación ir, o si le conviene cargar en la que tiene
enfrente.

## Solución

Nafteando cruza los precios oficiales de la Secretaría de Energía con la
distancia real del desvío (OSRM) y calcula el **ahorro neto** de cada
estación:

```
ahorro_neto = (precio_referencia − precio_estación) × litros
            − (km_desvío / consumo_km_por_litro) × precio_estación
            − (minutos_desvío / 60) × valor_hora        (opcional)
```

- `precio_referencia`: precio de la estación más cercana sobre el recorrido,
  o sea, donde cargaría sin usar la app.
- `km_desvío = distancia(A → estación → B) − distancia(A → B)`.
  En el modo "cerca mío" el desvío es ida y vuelta desde donde está.

Cada producto se compara solo con su mismo producto. Si ninguna estación da
ahorro neto positivo, la respuesta es **"no te desvíes"**.

## Operaciones previstas

| Comando | Qué hace | Estado |
|---|---|---|
| `inspeccionar` | Resume un CSV o JSON de precios: registros, campos, vacíos y tipos | listo |
| `limpiar` | Valida y limpia los precios, y guarda las filas rechazadas con su motivo | listo |
| `vigentes` | Precio vigente por estación y producto | pendiente |
| `recomendar` | Estaciones ordenadas por ahorro neto para un recorrido | pendiente |
| `actualizar` | Descarga el archivo de precios vigentes | pendiente |

## Ejemplo de resultado (objetivo de la v1)

```
Recorrido: Bv. Oroño 1500 → Av. Alberdi 1100 · nafta súper · 30 L · 12 km/L
Referencia: Servicentro Pellegrini (sobre el recorrido) a $1925/L

1. Rondeau GNC (PUMA)      $1870/L  desvío 0,8 km  ahorro neto $1525
2. Mendoza Oeste (YPF)     $1880/L  desvío 3,1 km  ahorro neto  $864
→ Conviene ir a Rondeau GNC: ahorrás $1525 en 30 litros.
```

Se lee así: cargando en Rondeau en vez de en la estación de referencia
ahorra $1650 en el surtidor, pero el desvío consume unos $125 de nafta; lo
que queda es lo que gana el chofer.

## Alcance de la v1

Entra:

- Rosario, Santa Fe, como ciudad por defecto (configurable).
- Nafta súper, nafta premium, gasoil, gasoil premium y GNC.
- Desvío calculado con OSRM y, si no responde, estimado en línea recta.
- Uso por consola y como web mobile first.

Queda afuera:

- Descuentos por tarjeta o por la app de la petrolera.
- Tiempo de espera en la estación y tránsito en tiempo real.
- Recorridos con varias paradas.
- Estaciones que no actualizan su precio: se excluyen, no se inventa uno.

## Datos

Fuente: *Precios en Surtidor – Resolución 314/2016*, Secretaría de Energía
de la Nación, licencia CC-BY-4.0. Cada fila es el precio que informa una
estación para un producto y una franja horaria, vigente desde
`fecha_vigencia`. Detalle de variables, muestra y limitaciones en
[data/README.md](data/README.md).

## Estructura

```
tp2-bonadeo/
├── data/
│   ├── README.md            fuente, variables y limitaciones
│   └── muestra/             muestra ficticia (CSV y JSON) y muestra real
├── outputs/                 salidas generadas (no se versionan)
├── src/
│   ├── config.py            rutas y valores por defecto
│   ├── fuentes.py           lectura de CSV y JSON
│   ├── pipeline.py          validación y limpieza
│   └── main.py              comandos de consola
├── tests/
│   ├── fixtures/            archivos rotos para probar errores
│   ├── test_fuentes.py
│   └── test_pipeline.py
├── requirements.txt
└── README.md
```

## Instalación

Requiere Python 3.10 o superior.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

## Uso

```
python -m src.main inspeccionar data/muestra/precios_muestra.csv
python -m src.main inspeccionar data/muestra/precios_muestra.json -n 5
python -m src.main limpiar data/muestra/precios_rosario_real.csv --fecha-consulta "2026-10-22 12:00:00"
```

`limpiar` guarda `outputs/precios_limpios.csv` y `outputs/rechazos.csv`
(cada fila rechazada con su número y el motivo) y muestra un resumen:

```
Fecha de consulta: 2026-10-22 12:00:00
Leídos: 15  Válidos: 10  Rechazados: 5

Motivos de rechazo:
      2  coordenadas en (0, 0)
      1  duplicado
      1  precio no positivo
      1  vigencia de más de 60 días
```

Sin `--fecha-consulta` se toma el momento actual. Como las muestras son de
octubre de 2026, para reproducir estos números hay que pasar esa fecha; si
no, con el tiempo todos los precios de la muestra quedan viejos.

Si el archivo no existe, está mal formado o le faltan columnas, el comando
muestra el motivo y termina con código de salida 2.

## Decisiones de limpieza

Cada fila se valida por separado y, si tiene problemas, se rechaza con
todos sus motivos juntos. Los umbrales están en `src/config.py`.

| Regla | Motivo del rechazo | Por qué |
|---|---|---|
| Campos obligatorios vacíos | `falta precio`, `falta latitud`... | Sin precio, fecha o ubicación no se puede recomendar nada |
| CUIT con formato `NN-NNNNNNNN-N` (expresión regular) y dígito verificador correcto | `CUIT inválido` | Detecta CUIT mal cargados. Si el cálculo da 10, el CUIT se considera inválido: la AFIP nunca asigna uno así |
| `fecha_vigencia` con formato `AAAA-MM-DD HH:MM:SS` (expresión regular) y que exista en el calendario | `fecha con formato inválido`, `fecha inexistente` | La regex sola acepta `2026-02-30` |
| Vigencia de hasta 60 días antes de la consulta | `vigencia de más de 60 días` | Ver abajo |
| Precio numérico y mayor que 0 | `precio no numérico`, `precio no positivo` | |
| Precio entre 0,5 y 1,5 veces la mediana de su producto (si hay al menos 5 precios) | `precio fuera de rango` | Atrapa errores de carga como un gasoil a $250. Se usa la mediana y no un rango fijo para no tener que actualizarlo con la inflación |
| Coordenadas distintas de (0, 0) y dentro de la provincia | `coordenadas en (0, 0)`, `coordenadas fuera de SANTA FE` | Para provincias sin límites cargados se controla que caigan en Argentina |
| Producto conocido | `producto desconocido` | El nombre se normaliza (minúsculas, sin tildes, espacios simples) y se lleva a 5 categorías |
| Franja `Diurno` o `Nocturno` | `franja horaria desconocida` | |
| Sin filas repetidas | `duplicado de la fila N` | Misma estación, producto, franja, precio y vigencia. Se queda la primera |

**Productos.** Las 5 categorías son `super`, `premium`, `gasoil`,
`gasoil premium` y `gnc`. El "Gas Oil Grado 3" es el gasoil premium y se
compara aparte del grado 2, porque no es el mismo producto.

**Umbral de 60 días.** El 22/10/2026, de las 95 estaciones de Rosario solo
16 habían informado precios en los últimos 60 días; la mayoría seguía con
precios de mediados de 2025, un 40 % más baratos que los actuales. Las
vigencias recientes llegan hasta los 29 días y después hay un salto, así
que 60 días deja margen para una estación que actualiza una vez por mes
sin aceptar precios que ya no existen.

La misma estación puede tener más de un precio válido para un producto
(uno viejo y uno nuevo). Elegir el vigente es el paso siguiente.

## Pruebas

```
python -m unittest discover -s tests -v
```

## Hoja de ruta

1. Estructura y lectura de CSV y JSON.
2. Validación y limpieza: CUIT con dígito verificador, fechas, rangos,
   duplicados, productos normalizados y archivo de rechazos.
3. Precio vigente por estación y producto, con las clases del dominio.
4. Cálculo del desvío y del ahorro neto, y comando `recomendar`.
5. Web app mobile first en Flask con mapa.
6. Descarga automática de precios y deploy.
