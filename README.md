# Nafteando

¿Vale la pena desviarme para cargar más barato?

Trabajo práctico 2 de Programación Orientada a Datos, Licenciatura en
Ciencia de Datos (UCA), 2026.

**Autor:** Gonzalo Bonadeo

**Web publicada:** https://tp2-bonadeo.vercel.app

## 1. Problema, usuario y solución

**Problema.** Los choferes de Uber, Cabify o DiDi, los remiseros y los
repartidores cargan combustible varias veces por semana, y es su principal
costo. Hay herramientas que muestran dónde está más barato, pero no
responden lo que importa en la calle: ¿conviene desviarse hasta ahí? El
desvío gasta nafta y tiempo, y para un chofer el tiempo es plata.

**Usuario.** Un chofer que está trabajando, abre la web en el celular y en
unos segundos quiere saber a qué estación ir, o si le conviene cargar en la
que tiene enfrente.

**Solución.** Nafteando cruza los precios oficiales de la Secretaría de
Energía con la distancia real del desvío por calle y calcula el ahorro neto
de cada estación:

```
ahorro_neto = (precio_referencia − precio_estación) × litros
            − (km_desvío / consumo_km_por_litro) × precio_estación
            − (minutos_desvío / 60) × valor_hora        (opcional)
```

- `precio_referencia`: el de la estación con menos desvío, o sea, donde
  cargaría sin usar la app.
- `km_desvío = distancia(A → estación → B) − distancia(A → B)`. En el modo
  "cerca mío" es ir hasta la estación y volver.

Cada combustible se compara solo con el mismo combustible. Si ninguna
estación da ahorro neto positivo, la respuesta es "no te desvíes".

**Alcance de la v1.** Entra: Rosario como ciudad por defecto
(configurable); nafta súper y premium, gasoil común y premium, y GNC;
precios diurnos y nocturnos; desvío por calle con OSRM; uso por consola y
web para el celular. Queda afuera: descuentos por app o tarjeta, tiempo de
espera en la estación, tránsito en tiempo real y recorridos con varias
paradas.

## 2. Funcionalidades y uso

Por consola, `python -m src.main <comando>`:

| Comando | Qué hace |
|---|---|
| `actualizar` | Descarga el archivo oficial de precios vigentes a `data/raw/` |
| `inspeccionar` | Resume un CSV o JSON: registros, campos, vacíos y tipos |
| `limpiar` | Valida y limpia los precios; guarda los válidos y las filas rechazadas con su motivo |
| `vigentes` | Precio vigente de cada estación de la ciudad, del más barato al más caro |
| `recomendar` | Estaciones ordenadas por ahorro neto para un recorrido, y el veredicto |

Opciones principales de `recomendar`: `--desde` (dirección o `lat,lon`,
obligatoria), `--hasta` (sin esto es "cerca mío"), `--producto` (`super`,
`premium`, `gasoil`, `gasoil premium` o `gnc`), `--litros` (30),
`--consumo` en km por litro (12), `--valor-hora` (0), `--franja`
(`Diurno` o `Nocturno`, por defecto según la hora) y `--sin-osrm` para
estimar en línea recta sin internet. Las coordenadas que empiezan con `-`
van con `=`: `--desde=-32.951,-60.653`.

`limpiar`, `vigentes` y `recomendar` aceptan
`--fecha-consulta "AAAA-MM-DD HH:MM:SS"` para fijar el "ahora". Las muestras son de octubre de 2026: para reproducir los
ejemplos de este README hay que pasar `--fecha-consulta "2026-10-22 12:00:00"`,
porque con el tiempo sus precios quedan viejos.

Si un archivo no existe, está mal formado o le faltan columnas, el comando
muestra el motivo y termina con código de salida 2.

**Web.** La misma lógica, pensada para el celular:

- Arriba, un mapa con el precio de cada estación (la más barata en verde) y
  cuándo fue el último precio informado en la ciudad.
- La salida y el destino se ponen escribiendo (con sugerencias de calles,
  alturas y esquinas de Rosario), con el GPS del teléfono o tocando el
  mapa; los pines se pueden arrastrar.
- Se elige Nafta, Gasoil o GNC (común o premium), el horario diurno o
  nocturno, los litros y el consumo.
- El resultado muestra el veredicto en grande, la cuenta desglosada, un
  botón para navegar hasta la estación y todas las opciones.
- Una lista con todas las estaciones de la ciudad, de la más barata a la
  más cara.

## 3. Datos

| | |
|---|---|
| Dataset | Precios en Surtidor, Resolución 314/2016 |
| Responsable | Secretaría de Energía de la Nación |
| URL | https://www.datos.gob.ar/dataset/energia-precios-surtidor---resolucion-3142016 |
| Licencia | Creative Commons Atribución 4.0 (CC-BY 4.0) |
| Fecha de consulta | 21/10/2026 (muestra real: 22/10/2026) |

**Unidad de análisis:** cada fila es el precio que informa una estación para
un producto y una franja horaria (diurna o nocturna), vigente desde
`fecha_vigencia`. Se usan 13 variables, entre ellas `cuit`, `empresa`,
`direccion`, `producto`, `tipohorario`, `precio`, `fecha_vigencia`,
`empresabandera`, `latitud` y `longitud`. El archivo completo tiene unas
36.600 filas de todo el país y se actualiza cada hora.

Muestras versionadas en `data/muestra/`:

- `precios_rosario_real.csv`: 86 filas reales de 10 estaciones de Rosario.
- `precios_muestra.csv` y `precios_muestra.json`: 15 filas ficticias con
  el mismo contenido en los dos formatos, con errores a propósito (precio
  en 0, coordenadas en (0, 0), una fila duplicada, un producto mal escrito
  y una vigencia vieja).

El diccionario de variables, el detalle de las muestras y los sesgos están
en [data/README.md](data/README.md). Para las distancias se usa OSRM y para
las direcciones Georef (del Estado nacional), Nominatim y Photon, todos
sobre datos abiertos.

## 4. Instalación y ejecución

Requiere Python 3.10 o superior.

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

Comandos con las muestras versionadas:

```
python -m src.main inspeccionar data/muestra/precios_muestra.csv
python -m src.main inspeccionar data/muestra/precios_muestra.json
python -m src.main limpiar data/muestra/precios_muestra.csv --fecha-consulta "2026-10-22 12:00:00"
python -m src.main vigentes data/muestra/precios_rosario_real.csv --producto super --fecha-consulta "2026-10-22 12:00:00"
python -m src.main recomendar data/muestra/precios_rosario_real.csv --desde "Av. Pellegrini 1500" --hasta "Av. Ovidio Lagos 4000" --fecha-consulta "2026-10-22 12:00:00"
```

Con los precios de hoy (el servidor oficial solo responde desde Argentina):

```
python -m src.main actualizar
python -m src.main recomendar data/raw/precios_vigentes.csv --desde "Córdoba 1500" --hasta "Oroño 3000"
```

Web, en http://127.0.0.1:5000:

```
flask --app src.web run
```

Pruebas:

```
python -m unittest discover -s tests -v
```

Son 121 pruebas y ninguna necesita internet: los servicios externos se
reemplazan por clientes falsos.

## 5. Organización del código

```
tp2-bonadeo/
├── src/
│   ├── main.py           comandos de consola (argparse)
│   ├── fuentes.py        lectura: FuenteDatos, FuenteCSV y FuenteJSON
│   ├── pipeline.py       validación, limpieza y precio vigente
│   ├── modelos.py        clases del dominio
│   ├── recomendador.py   desvío y ahorro neto
│   ├── ruteo.py          distancias con OSRM o en línea recta
│   ├── direcciones.py    direcciones a coordenadas (Georef, Nominatim, Photon)
│   ├── descarga.py       descarga del archivo oficial
│   ├── config.py         rutas, umbrales y valores por defecto
│   ├── web.py            web en Flask: página y API JSON
│   └── templates/, static/   HTML, estilos y JavaScript de la web
├── tests/                pruebas con unittest y archivos rotos de prueba
├── data/                 muestras versionadas y README de los datos
├── outputs/              salidas generadas (no se versionan)
├── api/index.py          entrada para Vercel
└── .github/workflows/    actualización automática de precios
```

El flujo sigue los pasos del curso:

1. **Leer** (`fuentes.py`): `FuenteDatos` es una clase base abstracta con
   `cargar(ruta)`, que controla que el archivo exista, no esté vacío y
   tenga registros; `FuenteCSV` y `FuenteJSON` implementan la lectura de
   cada formato y devuelven lo mismo, una lista de diccionarios con texto.
   `fuente_para(ruta)` elige según la extensión.
2. **Inspeccionar y validar** (`main.py inspeccionar`, `pipeline.py`):
   columnas obligatorias, formatos y rangos.
3. **Limpiar y transformar** (`pipeline.py`): tipos, normalización de
   productos, duplicados y rechazos con su motivo; después las filas pasan
   a objetos del dominio.
4. **Analizar** (`pipeline.py`, `recomendador.py`): precio vigente de cada
   estación y ahorro neto de cada opción.
5. **Comunicar**: tablas en la consola, archivos CSV en `outputs/` y la web.

Clases del dominio (`modelos.py`): `Estacion`, `PrecioEstacion`,
`Recorrido`, `OpcionCarga` y `RecomendacionCarga`. Validan sus datos al
crearse (por ejemplo, un precio no puede ser 0 ni negativo). `ruteo.py` y
`direcciones.py` usan el mismo esquema que las fuentes: una clase base
(`Ruteador`, `Geocodificador`) con varias implementaciones
intercambiables, lo que permite probar todo con versiones falsas, sin
internet.

## 6. Ejemplo de resultado

Con la muestra real, saliendo de Av. Pellegrini 1500 hacia Av. Ovidio
Lagos 4000, para cargar 30 litros de súper con un auto que hace 12 km/L:

```
Recorrido con destino · super diurno · 30 L · 12 km/L
Referencia (la de menor desvío): CRISTOFARO HERMANOS SRL (SHELL C.A.P.S.A.), OVIDIO LAGOS 4502 a $2.254,00

       precio    desvío  minutos   ahorro neto  estación
 1  $2.212,00    0.9 km        2     $1.100,90  BRIBAL AGRO SRL (PUMA), PUEYRREDON 1089
 2  $2.212,00    7.4 km       11      -$108,67  REFINERIA BAHIA BLANCA S.A.U. (PUMA), AVELLANEDA 519
 3  $2.254,00    5.9 km       11    -$1.104,76  VETVEL SA (SHELL C.A.P.S.A.), Monteagudo 224

-> Conviene ir a BRIBAL AGRO SRL (PUMA): ahorrás $1.100,90.
   $1.260,00 menos en el surtidor, $159,10 de combustible en el desvío.
```

Sin la app, el chofer cargaría en la Shell de Ovidio Lagos, que le queda de
paso, a $2.254. La Puma de Pueyrredón cobra $42 menos por litro: en 30
litros son $1.260, y llegar le agrega 0,9 km, que gastan $159,10 de nafta.
Lo que gana de verdad son $1.100,90. La otra Puma tiene el mismo precio,
pero el desvío de 7,4 km se come el ahorro. El detalle de cada opción queda
en `outputs/recomendacion.csv`. Los kilómetros salen de OSRM y pueden
variar un poco si cambia el mapa de OpenStreetMap.

Y `limpiar` con la muestra ficticia:

```
Leídos: 15  Válidos: 10  Rechazados: 5

Motivos de rechazo:
      2  coordenadas en (0, 0)
      1  duplicado
      1  precio no positivo
      1  vigencia de más de 60 días
```

## 7. Decisiones de limpieza

Cada fila se valida por separado y, si tiene problemas, se rechaza con
todos sus motivos juntos en `outputs/rechazos.csv`. Los umbrales están en
`src/config.py`.

| Regla | Por qué |
|---|---|
| Campos obligatorios no vacíos | Sin precio, fecha o ubicación no se puede recomendar |
| CUIT con la expresión regular `^(\d{2})-(\d{8})-(\d)$` y dígito verificador correcto | Detecta CUIT mal cargados. Si el cálculo da 10, el CUIT es inválido (la AFIP nunca asigna uno así) |
| `fecha_vigencia` con la expresión regular `AAAA-MM-DD HH:MM:SS` y, además, que la fecha exista (`datetime`) | La regex sola acepta `2026-02-30` |
| Vigencia de hasta 60 días | Ver abajo |
| Precio numérico y mayor que 0 | |
| Precio entre 0,5 y 1,5 veces la mediana de su producto | Atrapa errores de carga como un gasoil a $250. Se usa la mediana y no un rango fijo para no tener que cambiarlo con la inflación |
| Coordenadas distintas de (0, 0) y dentro de la provincia | Hay estaciones en (0, 0) |
| Producto conocido | Se normaliza (minúsculas, sin tildes) y se lleva a 5 categorías; el "Gas Oil Grado 3" es gasoil premium y va aparte |
| Sin filas duplicadas | Misma estación, producto, franja, precio y vigencia; queda la primera |

**Umbral de 60 días.** El 22/10/2026, de las 95 estaciones de Rosario solo
16 habían informado precios en los últimos 60 días; la mayoría seguía con
precios de 2025, un 40 % más bajos que los actuales. Las vigencias
recientes llegan hasta los 29 días y después hay un salto, así que 60 días
deja margen para una estación que actualiza una vez por mes.

**Precio vigente.** Para cada estación, producto y franja se toma el precio
más reciente que ya rige en el momento de la consulta: uno que empieza a
regir después todavía no se cobra. Si dos tienen la misma vigencia, se
queda el más caro, para no prometer un ahorro que quizás no existe.

**Estaciones que no informan.** Casi todas las YPF y Shell dejaron de
cargar sus precios: el 23/10/2026, solo 165 de las 13.138 filas de YPF del
país tenían menos de 30 días. Para que el chofer igual las vea, la web les
pone un precio estimado: la mediana de su misma bandera, producto y horario
a menos de 50 km, o si no de la provincia. Se marcan con "≈", dicen de
dónde sale la estimación y cuál fue el último precio que informaron, y
solo entran en la recomendación si el chofer lo activa. La consola no
estima: las descarta.

## 8. Interpretación

- El ahorro neto es la plata que le queda al chofer en esta carga: lo que
  ahorra en el surtidor menos lo que gasta en llegar. Si es negativo, el
  desvío cuesta más de lo que ahorra.
- La comparación es contra la estación que le queda más a mano, porque la
  pregunta es "¿vale la pena ir a otra en vez de a esa?".
- Dentro de una ciudad, una misma bandera suele cobrar lo mismo, así que
  las diferencias aparecen entre banderas: en la muestra, $42 por litro
  entre Puma y Shell. Con 30 litros, eso paga un desvío de 1 km, pero no
  uno de 7 km.
- Sin valor de la hora, la cuenta solo mira el combustible. Para un chofer
  que cobra por hora, sumar su tiempo cambia la respuesta en desvíos
  largos.

## 9. Limitaciones

- Los precios los informa cada estación. Muchas dejaron de hacerlo (casi
  todas las YPF y Shell), y su precio en la web es una estimación.
- No incluye descuentos por app, tarjeta o club de beneficios, que pueden
  cambiar cuál conviene.
- No considera tránsito real ni espera en la estación, y usa un consumo
  fijo por kilómetro.
- Un solo destino: no contempla recorridos con varias paradas.
- Algunas estaciones tienen coordenadas que no corresponden a su
  dirección, y no siempre se detectan.
- OSRM, Georef, Nominatim y Photon son servicios públicos gratuitos y con
  uso limitado. Si OSRM no responde, la distancia se estima en línea recta
  y la app lo avisa.
- El servidor oficial de precios solo responde desde Argentina (ver
  abajo).

## 10. Publicación y actualización de precios

La web está en Vercel (`api/index.py` expone la app de Flask). Como el
servidor de la Secretaría de Energía no acepta conexiones desde fuera de
Argentina (se probó desde Vercel y desde los servidores de GitHub), los
precios se actualizan así:

1. Un runner propio de GitHub Actions en una PC en Argentina corre el
   workflow `.github/workflows/actualizar-precios.yml` cada 3 horas.
2. El workflow ejecuta `python -m src.main actualizar` y sube el archivo
   como adjunto del release `datos` del repositorio, sin agregar commits.
3. La web baja ese archivo y lo renueva cada hora. Si no puede, sigue con
   el último que tenga, o con la muestra, y lo avisa en la página.

Si la PC está apagada, la web sigue con los precios de la última
actualización. Como el repositorio es público, los workflows de pull
requests externos necesitan aprobación para correr en ese runner.
