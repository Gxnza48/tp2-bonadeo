"""Cálculo del desvío y del ahorro neto de cada estación.

ahorro_neto = (precio_referencia - precio_estacion) * litros
            - (km_desvio / consumo_km_por_litro) * precio_estacion
            - (minutos_desvio / 60) * valor_hora

La referencia es la estación con menos desvío: donde el chofer cargaría
sin usar la app. El desvío de las demás se mide contra el de la referencia,
porque ese tramo lo haría igual para cargar.
"""

from src.config import HORA_FIN_NOCTURNO, HORA_INICIO_NOCTURNO, RADIO_BUSQUEDA_KM
from src.modelos import OpcionCarga, RecomendacionCarga
from src.ruteo import Tramo, distancia_km


class SinEstaciones(Exception):
    """No hay estaciones con precio vigente para el recorrido pedido."""


def franja_para(momento):
    hora = momento.hour
    if hora >= HORA_INICIO_NOCTURNO or hora < HORA_FIN_NOCTURNO:
        return "Nocturno"
    return "Diurno"


def calcular_ahorro(precio_referencia, precio_estacion, litros, consumo_km_por_litro,
                    km_desvio, minutos_desvio, valor_hora=0):
    """Devuelve (ahorro en el surtidor, costo del combustible del desvío, costo del tiempo)."""
    ahorro_surtidor = (precio_referencia - precio_estacion) * litros
    costo_combustible = km_desvio / consumo_km_por_litro * precio_estacion
    costo_tiempo = minutos_desvio / 60 * valor_hora
    return ahorro_surtidor, costo_combustible, costo_tiempo


def desvios(ruteador, recorrido, ubicaciones):
    """Lo que se agrega al recorrido por pasar por cada estación.

    Con destino: distancia(A -> estación -> B) - distancia(A -> B).
    En modo "cerca mío": ir hasta la estación y volver.
    """
    if recorrido.cerca_mio:
        return ruteador.via(recorrido.origen, ubicaciones, recorrido.origen)
    directo = ruteador.ruta(recorrido.origen, recorrido.destino)
    resultado = []
    for con_parada in ruteador.via(recorrido.origen, ubicaciones, recorrido.destino):
        extra = con_parada - directo
        # Por redondeos de la ruta puede dar apenas negativo.
        resultado.append(Tramo(max(extra.km, 0), max(extra.minutos, 0), extra.estimado))
    return resultado


def desvio(ruteador, recorrido, ubicacion):
    return desvios(ruteador, recorrido, [ubicacion])[0]


def candidatas(vigentes, recorrido, franja, radio_km=RADIO_BUSQUEDA_KM):
    """Precios del producto y la franja de estaciones cerca del origen o del destino."""
    extremos = [recorrido.origen] + ([] if recorrido.cerca_mio else [recorrido.destino])
    return [
        p for p in vigentes
        if p.producto == recorrido.producto and p.horario == franja
        and min(distancia_km(punto, (p.estacion.latitud, p.estacion.longitud)) for punto in extremos) <= radio_km
    ]


def recomendar(vigentes, recorrido, ruteador, franja, radio_km=RADIO_BUSQUEDA_KM):
    precios = candidatas(vigentes, recorrido, franja, radio_km)
    if not precios:
        raise SinEstaciones(
            f"No hay estaciones con precio vigente de {recorrido.producto} ({franja}) "
            f"a menos de {radio_km} km"
        )

    ubicaciones = [(p.estacion.latitud, p.estacion.longitud) for p in precios]
    por_estacion = list(zip(precios, desvios(ruteador, recorrido, ubicaciones)))

    # Referencia: la de menor desvío; si empatan, la más barata, para no
    # exagerar el ahorro de las demás.
    precio_ref, desvio_ref = min(por_estacion, key=lambda par: (par[1].km, par[0].precio))

    opciones = []
    referencia = None
    for precio, tramo in por_estacion:
        km = max(tramo.km - desvio_ref.km, 0)
        minutos = max(tramo.minutos - desvio_ref.minutos, 0)
        ahorro, combustible, tiempo = calcular_ahorro(
            precio_ref.precio, precio.precio, recorrido.litros, recorrido.consumo_km_por_litro,
            km, minutos, recorrido.valor_hora,
        )
        opcion = OpcionCarga(precio, km, minutos, ahorro, combustible, tiempo, tramo.estimado)
        if precio is precio_ref:
            referencia = opcion
        else:
            opciones.append(opcion)

    # Más ahorro primero; con el mismo ahorro, la más cercana.
    opciones.sort(key=lambda o: (-o.ahorro_neto, o.km_desvio))
    aviso = getattr(ruteador, "falla", None)
    if aviso:
        aviso += ": distancias estimadas en línea recta"
    return RecomendacionCarga(recorrido, franja, referencia, opciones, aviso)
