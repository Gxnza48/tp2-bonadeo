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

- `precio_referencia`: precio de la estación con menos desvío, o sea,
  donde cargaría sin usar la app.
- `km_desvío = distancia(A → estación → B) − distancia(A → B)`.
  En el modo "cerca mío" el desvío es ida y vuelta desde donde está.
  Las distancias y los minutos son por calle, con OSRM.

Cada producto se compara solo con su mismo producto. Si ninguna estación da
ahorro neto positivo, la respuesta es **"no te desvíes"**.

## Funcionalidades

Por consola (`python -m src.main <comando>`):

| Comando | Qué hace |
|---|---|
| `actualizar` | Descarga el archivo oficial de precios vigentes a `data/raw/` |
| `inspeccionar` | Resume un CSV o JSON de precios: registros, campos, vacíos y tipos |
| `limpiar` | Valida y limpia los precios, y guarda las filas rechazadas con su motivo |
| `vigentes` | Precio vigente de cada estación de la ciudad, del más barato al más caro |
| `recomendar` | Estaciones ordenadas por ahorro neto para un recorrido, y el veredicto |

Y una web para el celular con lo mismo que `recomendar`, más el mapa y la
ubicación del GPS (ver [Web](#web)).

## Ejemplo de resultado

Con la muestra real, saliendo de Av. Pellegrini 1500 hacia Av. Ovidio
Lagos 4000, para cargar 30 litros de súper con un auto que hace 12 km/L:

```
python -m src.main recomendar data/muestra/precios_rosario_real.csv --desde "Av. Pellegrini 1500" --hasta "Av. Ovidio Lagos 4000" --fecha-consulta "2026-10-22 12:00:00"

Recorrido con destino · super diurno · 30 L · 12 km/L
Referencia (la de menor desvío): CRISTOFARO HERMANOS SRL (SHELL C.A.P.S.A.), OVIDIO LAGOS 4502 a $2.254,00

       precio    desvío  minutos   ahorro neto  estación
 1  $2.212,00    2.1 km        4       $873,40  BRIBAL AGRO SRL (PUMA), PUEYRREDON 1089
 2  $2.212,00    9.1 km       14      -$416,81  REFINERIA BAHIA BLANCA S.A.U. (PUMA), AVELLANEDA 519
 3  $2.254,00    7.3 km       13    -$1.365,21  VETVEL SA (SHELL C.A.P.S.A.), Monteagudo 224

-> Conviene ir a BRIBAL AGRO SRL (PUMA): ahorrás $873,40.
   $1.260,00 menos en el surtidor, $386,60 de combustible en el desvío.
```

Se lee así: sin la app cargaría en la Shell de Ovidio Lagos, que le queda
de paso, a $2.254. La PUMA de Pueyrredón cobra $42 menos por litro: en 30
litros son $1.260, pero llegar hasta ahí le agrega 2,1 km, que gastan
$386,60 de nafta. Lo que gana de verdad son $873,40. La otra PUMA tiene el
mismo precio pero el desvío de 9,1 km se come todo el ahorro, así que
aparece con ahorro negativo.

Si ninguna da ahorro positivo, la respuesta es "No te desvíes: cargá en
<la referencia>". El detalle de cada estación queda en
`outputs/recomendacion.csv`.

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
│   ├── modelos.py           clases del dominio (Estacion, PrecioEstacion,
│   │                        Recorrido, OpcionCarga, RecomendacionCarga)
│   ├── pipeline.py          validación, limpieza y precio vigente
│   ├── ruteo.py             distancias (OSRM o línea recta) y direcciones
│   ├── recomendador.py      desvío y ahorro neto
│   ├── main.py              comandos de consola
│   ├── descarga.py          descarga del archivo oficial
│   ├── web.py               web app (Flask): página y API
│   ├── templates/index.html
│   └── static/              estilos y JavaScript del mapa
├── api/index.py             entrada para Vercel
├── tests/
│   ├── fixtures/            archivos rotos para probar errores
│   ├── test_fuentes.py
│   ├── test_pipeline.py
│   ├── test_vigentes.py
│   ├── test_recomendador.py
│   ├── test_web.py
│   └── test_descarga.py
├── requirements.txt
├── vercel.json
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

Para trabajar con los precios del momento, primero:

```
python -m src.main actualizar
```

Eso guarda el archivo completo (unos 9 MB, todo el país) en
`data/raw/precios_vigentes.csv`, que no se versiona. Después se usa como
cualquier otro archivo, sin `--fecha-consulta`:

```
python -m src.main recomendar data/raw/precios_vigentes.csv --desde "Oroño 1500" --hasta "Pellegrini 3000"
```

Con las muestras versionadas, para reproducir los ejemplos de este README:

```
python -m src.main inspeccionar data/muestra/precios_muestra.csv
python -m src.main inspeccionar data/muestra/precios_muestra.json -n 5
python -m src.main limpiar data/muestra/precios_rosario_real.csv --fecha-consulta "2026-10-22 12:00:00"
python -m src.main vigentes data/muestra/precios_muestra.csv --fecha-consulta "2026-10-22 12:00:00" --producto super --franja Diurno
python -m src.main recomendar data/muestra/precios_rosario_real.csv --desde "Av. Pellegrini 1500" --hasta "Av. Ovidio Lagos 4000" --fecha-consulta "2026-10-22 12:00:00"
python -m src.main recomendar data/muestra/precios_muestra.csv --desde=-32.951,-60.653 --sin-osrm --fecha-consulta "2026-10-22 12:00:00"
```

Opciones de `recomendar`:

| Opción | Qué es | Por defecto |
|---|---|---|
| `--desde` | Dirección o `lat,lon` de partida | obligatoria |
| `--hasta` | Dirección o `lat,lon` de destino; sin esto es modo "cerca mío" | — |
| `--producto` | `super`, `premium`, `gasoil`, `gasoil premium` o `gnc` | `super` |
| `--litros` | Litros a cargar | 30 |
| `--consumo` | Kilómetros por litro del auto | 12 |
| `--valor-hora` | Cuánto vale una hora del chofer, para sumar el costo del tiempo | 0 |
| `--franja` | `Diurno` o `Nocturno` | según la hora de la consulta |
| `--sin-osrm` | Estimar en línea recta, sin internet | — |

Si las coordenadas empiezan con `-` hay que escribirlas con `=`
(`--desde=-32.951,-60.653`), porque si no `argparse` las toma como otra
opción.

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

`vigentes` limpia el archivo, se queda con la ciudad (Rosario por
defecto; se cambia con `--localidad` y `--provincia`) y muestra el precio
que rige en cada estación. Lo guarda en `outputs/precios_vigentes.csv`:

```
Precios vigentes en ROSARIO, SANTA FE al 22/10/2026 12:00
(5 filas rechazadas en la limpieza, ver outputs/rechazos.csv)

super · Diurno
    $1.870,00  desde 05/10  RONDEAU GNC S.R.L. (PUMA), Av. Rondeau 3200
    $1.880,00  desde 18/10  MENDOZA OESTE S.A. (YPF), Mendoza 7000
    $1.890,00  desde 15/10  ESTACIÓN OROÑO S.R.L. (YPF), Bv. Oroño 1500
    $1.925,00  desde 12/10  SERVICENTRO PELLEGRINI S.A. (SHELL C.A.P.S.A.), Av. Pellegrini 2100
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

## Precio vigente

Después de limpiar, cada fila pasa a un objeto `PrecioEstacion`, que
conoce su `Estacion`, y para cada estación, producto y franja se elige
**el precio más reciente que ya rige en el momento de la consulta**:

- Un precio con vigencia posterior a la consulta todavía no se cobra y se
  ignora. En la muestra, Oroño tiene súper a $1.790 desde el 10/09 y a
  $1.890 desde el 15/10: consultando el 01/10 rige el primero; el 22/10, el
  segundo.
- Si dos precios tienen la misma vigencia, se queda el más caro, para no
  prometerle al chofer un ahorro que quizás no existe.
- Diurno y Nocturno se tratan como precios distintos, igual que cada
  producto.

## Web

```
flask --app src.web run
```

y abrir http://127.0.0.1:5000 en el navegador (en el celular, con las
herramientas de desarrollador en modo móvil, o desde la misma red con
`--host 0.0.0.0`).

La página está pensada para el celular: el chofer elige "Cerca mío" o
"Tengo destino", toca **Mi ubicación** para usar el GPS del teléfono, elige
el combustible y toca **¿Dónde cargo?**. Arriba aparece el veredicto
("Andá a ...: ahorrás $N" o "No te desvíes"), la cuenta desglosada y un
botón **Cómo llegar** que abre la navegación. Abajo, el mapa con la salida,
el destino, la referencia (naranja) y la estación que conviene (verde).
Litros, consumo y valor de la hora se recuerdan en el navegador.

La web no repite lógica: `src/web.py` lee los parámetros, llama a las
mismas funciones que la consola y devuelve JSON.

| Ruta | Qué devuelve |
|---|---|
| `GET /` | La página |
| `GET /api/estaciones?producto=super` | Precios vigentes del producto en la franja actual, para el mapa |
| `GET /api/recomendar?desde=...&hasta=...&producto=...&litros=...&consumo=...&valor_hora=...` | La recomendación; 400 con el motivo si un dato está mal, 404 si no hay estaciones cerca |

Variables de entorno opcionales:

- `NAFTEANDO_DATOS`: archivo de precios. Si no se define, la web usa
  `data/raw/precios_vigentes.csv` si existe, o la muestra real.
- `NAFTEANDO_DESCARGAR=1`: baja el archivo oficial a la carpeta temporal y
  lo renueva cada hora. Si la descarga falla, sigue con el último archivo o
  con la muestra, lo avisa en la página y no vuelve a intentar hasta dentro
  de una hora, para no hacer esperar cada pedido.

Cuando la web usa la muestra real, calcula los precios vigentes al
22/10/2026 (el día en que se bajó) y lo avisa: si no, pasados 60 días todos
sus precios quedarían vencidos y no mostraría ninguna estación.
- `NAFTEANDO_FECHA_CONSULTA`: fija el "ahora", por ejemplo
  `2026-10-22 12:00:00`, para mostrar la muestra cuando sus precios ya
  quedaron viejos.

## Cómo se calcula la recomendación

1. Se limpian los precios y se toma el vigente de cada estación de la
   ciudad (ver arriba).
2. Se quedan las estaciones del producto y la franja pedidos a menos de
   6 km en línea recta del origen o del destino. Más lejos no tiene sentido
   consultar el desvío.
3. Para cada una se pide a OSRM la ruta pasando por la estación. Si OSRM
   no responde, se avisa y se estima en línea recta × 1,3 (las calles no
   van en línea recta) a 25 km/h; el resultado queda marcado como
   estimación.
4. La **referencia** es la estación con menos desvío. El desvío de las
   demás se mide contra el de la referencia, porque ese tramo lo haría igual
   para cargar.
5. Se calcula el ahorro neto de cada una y se ordenan de mayor a menor; con
   el mismo ahorro va primero la más cercana. Si la primera no tiene ahorro
   positivo, conviene no desviarse.

Supuestos: la franja nocturna va de 22 a 6 (el dataset no lo dice) y el
costo del desvío se calcula con el precio de la estación a la que se va.
Las direcciones se buscan con Nominatim dentro de un recuadro alrededor de
la ciudad.

Todas las estaciones se resuelven con una sola consulta al servicio
`table` de OSRM (las distancias desde el origen y desde cada estación
hasta cada estación y el destino), en lugar de una consulta por estación.
Con 9 estaciones bajó de unos 16 segundos a 3, que es lo que importa para
alguien que está manejando.

## Interpretación

- El **ahorro neto** es plata en el bolsillo del chofer en esta carga:
  lo que ahorra en el surtidor menos lo que gasta en llegar. Si es
  negativo, el desvío cuesta más de lo que ahorra.
- Cuando no hay una estación de paso, la referencia es la más cercana, y
  el desvío de las demás se cuenta a partir de ella: la pregunta es "¿vale
  la pena ir a otra en vez de a la más cercana?".
- En una ciudad los precios de una misma bandera suelen ser iguales, así
  que las diferencias aparecen entre banderas (en la muestra, $42 por litro
  entre PUMA y Shell). Con 30 litros, $42 por litro son $1.260: un desvío
  de 2 km se paga solo; uno de 9 km, no.
- Sin `valor_hora` la cuenta solo mira el combustible. Para un chofer que
  cobra por hora, sumar su tiempo cambia la respuesta en desvíos largos.
- Si aparece "distancias estimadas en línea recta", los números son
  aproximados: OSRM no respondió.

## Limitaciones

- **Precios informados por las estaciones.** Si una estación no actualiza,
  queda afuera (vigencia de más de 60 días), aunque quizás sea la más
  barata. En Rosario, el 22/10/2026, solo 16 de 95 estaciones tenían
  precios recientes.
- **Sin descuentos** por app de la petrolera, tarjetas o clubes de
  beneficios, que pueden dar vuelta la recomendación.
- **Sin tránsito real ni espera en la estación.** La duración es la de OSRM
  sin tránsito.
- **El costo del desvío usa un consumo fijo** por kilómetro; en ciudad, con
  frenadas, puede ser mayor.
- **Un solo destino.** No contempla recorridos con varias paradas.
- **Coordenadas**: algunas estaciones tienen coordenadas que no
  corresponden a su dirección y no siempre se detectan.
- **La web publicada no tiene precios del día**: el servidor oficial no
  responde desde Vercel (ver [Deploy](#deploy-en-vercel)).
- **Servicios públicos de OSRM y Nominatim**: son gratuitos y con uso
  limitado; para mucho tráfico habría que tener servidores propios.

Más detalle sobre los datos en [data/README.md](data/README.md).

## Pruebas

```
python -m unittest discover -s tests -v
```

97 pruebas, ninguna necesita internet: OSRM, Nominatim y la descarga se
reemplazan por clientes falsos. Cubren casos normales, entradas inválidas
(archivos rotos, CUIT y fechas mal escritos, parámetros sin sentido) y
propiedades del resultado: leer CSV o JSON da lo mismo, ninguna fila se
pierde en la limpieza, una estación sobre el recorrido tiene desvío 0, con
precios iguales gana la más cercana y con ahorro negativo la respuesta es
no desviarse.

## Deploy en Vercel

Publicada en https://tp2-bonadeo.vercel.app.

`api/index.py` expone la app de Flask; Vercel la detecta y le pasa todas
las rutas. `vercel.json` la corre en San Pablo (`gru1`), la región más
cercana a Rosario, con hasta 30 segundos por pedido. No hace falta definir
variables de entorno:

```
vercel deploy --prod
```

La idea era que en Vercel la app bajara los precios a la carpeta temporal
cada hora (`NAFTEANDO_DESCARGAR=1`). **Pero el servidor de la Secretaría de
Energía (`datos.energia.gob.ar`) no acepta conexiones desde Vercel**: se
probó desde Estados Unidos y desde San Pablo, y en los dos casos la conexión
no llega a abrirse; desde una conexión argentina responde bien. Por eso la
versión publicada usa la muestra real del 22/10/2026 y lo avisa en la
página. Para tener precios del día hay que correr la app desde Argentina:
`python -m src.main actualizar` y después la consola o
`flask --app src.web run`.
