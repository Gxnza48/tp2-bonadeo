import unittest
from datetime import datetime

import requests

from src.modelos import Estacion, PrecioEstacion, Recorrido
from src.recomendador import (
    SinEstaciones,
    calcular_ahorro,
    desvio,
    franja_para,
    recomendar,
)
from src.ruteo import ErrorRuteo, RuteadorLineaRecta, RuteadorOSRM, Tramo, distancia_km, ubicar

# Origen y destino sobre el mismo meridiano: la línea recta entre los dos
# es exacta, así que una estación en el medio queda justo sobre el recorrido.
ORIGEN = (-33.00, -60.65)
DESTINO = (-32.90, -60.65)
SOBRE_EL_RECORRIDO = (-32.95, -60.65)

RECTA = RuteadorLineaRecta(factor_rodeo=1, velocidad_kmh=30)


def estacion(idempresa, ubicacion):
    return Estacion(idempresa, "30-71234567-1", f"ESTACION {idempresa}", f"Calle {idempresa}",
                    "ROSARIO", "SANTA FE", "YPF", *ubicacion)


def precio(idempresa, ubicacion, valor, producto="super", horario="Diurno"):
    return PrecioEstacion(estacion(idempresa, ubicacion), producto, horario, valor,
                          datetime(2026, 10, 15, 10, 0, 0))


def recorrido(**cambios):
    datos = dict(origen=ORIGEN, destino=DESTINO, producto="super", litros=30,
                 consumo_km_por_litro=12, valor_hora=0)
    datos.update(cambios)
    return Recorrido(**datos)


class TestCalculo(unittest.TestCase):
    def test_ahorro_desglosado(self):
        ahorro, combustible, tiempo = calcular_ahorro(1925, 1870, 30, 12, 0.8, 3)
        self.assertAlmostEqual(ahorro, 1650)
        self.assertAlmostEqual(combustible, 0.8 / 12 * 1870)
        self.assertEqual(tiempo, 0)

    def test_costo_del_tiempo(self):
        _, _, tiempo = calcular_ahorro(1925, 1870, 30, 12, 0.8, 6, valor_hora=3000)
        self.assertAlmostEqual(tiempo, 300)

    def test_franja_segun_la_hora(self):
        casos = {"05:59": "Nocturno", "06:00": "Diurno", "21:59": "Diurno", "22:00": "Nocturno"}
        for hora, franja in casos.items():
            with self.subTest(hora=hora):
                self.assertEqual(franja_para(datetime.fromisoformat(f"2026-10-22 {hora}")), franja)

    def test_recorrido_invalido(self):
        for cambios in ({"litros": 0}, {"consumo_km_por_litro": -1}, {"valor_hora": -5},
                        {"producto": "kerosene"}):
            with self.subTest(**cambios):
                with self.assertRaises(ValueError):
                    recorrido(**cambios)


class TestDesvio(unittest.TestCase):
    def test_estacion_sobre_el_recorrido_tiene_desvio_cero(self):
        tramo = desvio(RECTA, recorrido(), SOBRE_EL_RECORRIDO)
        self.assertAlmostEqual(tramo.km, 0, places=6)

    def test_estacion_al_costado_suma_km(self):
        al_costado = (-32.95, -60.63)  # unos 1,9 km al este
        self.assertGreater(desvio(RECTA, recorrido(), al_costado).km, 0)

    def test_cerca_mio_es_ida_y_vuelta(self):
        destino = (-32.95, -60.65)
        tramo = desvio(RECTA, recorrido(destino=None), destino)
        self.assertAlmostEqual(tramo.km, 2 * distancia_km(ORIGEN, destino))

    def test_un_grado_de_latitud_son_111_km(self):
        self.assertAlmostEqual(distancia_km((-33, -60.65), (-32, -60.65)), 111.19, places=1)


class TestRecomendar(unittest.TestCase):
    def test_conviene_la_mas_barata_si_el_desvio_es_chico(self):
        precios = [
            precio("ref", SOBRE_EL_RECORRIDO, 1925),
            precio("barata", (-32.95, -60.645), 1870),  # a 470 m del recorrido
        ]
        rec = recomendar(precios, recorrido(), RECTA, "Diurno")
        self.assertEqual(rec.referencia.precio.estacion.idempresa, "ref")
        self.assertTrue(rec.conviene_desviarse)
        self.assertEqual(rec.mejor.precio.estacion.idempresa, "barata")
        self.assertGreater(rec.mejor.ahorro_neto, 0)

    def test_la_referencia_es_la_de_menor_desvio(self):
        precios = [precio("lejos", (-32.95, -60.62), 1800), precio("encima", SOBRE_EL_RECORRIDO, 1900)]
        rec = recomendar(precios, recorrido(), RECTA, "Diurno")
        self.assertEqual(rec.referencia.precio.estacion.idempresa, "encima")
        self.assertEqual(rec.referencia.ahorro_neto, 0)

    def test_con_precios_iguales_gana_la_mas_cercana(self):
        precios = [
            precio("ref", SOBRE_EL_RECORRIDO, 1925),
            precio("lejos", (-32.95, -60.64), 1870),
            precio("cerca", (-32.95, -60.645), 1870),
        ]
        rec = recomendar(precios, recorrido(), RECTA, "Diurno")
        self.assertEqual([o.precio.estacion.idempresa for o in rec.opciones], ["cerca", "lejos"])

    def test_si_el_ahorro_es_negativo_no_te_desvies(self):
        precios = [
            precio("ref", SOBRE_EL_RECORRIDO, 1925),
            precio("lejos", (-32.95, -60.55), 1915),  # $10 menos pero 10 km de desvío
        ]
        rec = recomendar(precios, recorrido(), RECTA, "Diurno", radio_km=20)
        self.assertLess(rec.opciones[0].ahorro_neto, 0)
        self.assertFalse(rec.conviene_desviarse)
        self.assertIsNone(rec.mejor)

    def test_si_todas_son_mas_caras_no_te_desvies(self):
        precios = [precio("ref", SOBRE_EL_RECORRIDO, 1870), precio("cara", (-32.95, -60.645), 1925)]
        self.assertFalse(recomendar(precios, recorrido(), RECTA, "Diurno").conviene_desviarse)

    def test_el_tiempo_nunca_aumenta_el_ahorro(self):
        precios = [precio("ref", SOBRE_EL_RECORRIDO, 1925), precio("barata", (-32.95, -60.64), 1870)]
        sin_tiempo = recomendar(precios, recorrido(), RECTA, "Diurno").opciones[0]
        con_tiempo = recomendar(precios, recorrido(valor_hora=5000), RECTA, "Diurno").opciones[0]
        self.assertLess(con_tiempo.ahorro_neto, sin_tiempo.ahorro_neto)

    def test_solo_compara_el_mismo_producto_y_franja(self):
        precios = [
            precio("ref", SOBRE_EL_RECORRIDO, 1925),
            precio("premium", (-32.95, -60.645), 1500, producto="premium"),
            precio("nocturno", (-32.95, -60.645), 1500, horario="Nocturno"),
        ]
        rec = recomendar(precios, recorrido(), RECTA, "Diurno")
        self.assertEqual(rec.opciones, [])
        self.assertFalse(rec.conviene_desviarse)

    def test_sin_estaciones_cerca(self):
        lejos = precio("cordoba", (-31.42, -64.18), 1800)
        with self.assertRaisesRegex(SinEstaciones, "super"):
            recomendar([lejos], recorrido(), RECTA, "Diurno")

    def test_las_distancias_en_linea_recta_quedan_marcadas(self):
        precios = [precio("ref", SOBRE_EL_RECORRIDO, 1925), precio("otra", (-32.95, -60.645), 1870)]
        self.assertTrue(recomendar(precios, recorrido(), RECTA, "Diurno").estimado)


class RespuestaFalsa:
    def __init__(self, datos):
        self.datos = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self.datos


class ClienteFalso:
    def __init__(self, datos=None, error=None):
        self.datos, self.error, self.llamadas = datos, error, 0

    def get(self, *args, **kwargs):
        self.llamadas += 1
        self.ultimos_parametros = kwargs.get("params", {})
        if self.error:
            raise self.error
        return RespuestaFalsa(self.datos)


class TestOSRM(unittest.TestCase):
    def test_lee_la_respuesta(self):
        cliente = ClienteFalso({"code": "Ok", "routes": [{"distance": 8081.8, "duration": 775}]})
        tramo = RuteadorOSRM(cliente=cliente).ruta(ORIGEN, DESTINO)
        self.assertAlmostEqual(tramo.km, 8.0818)
        self.assertAlmostEqual(tramo.minutos, 775 / 60)
        self.assertFalse(tramo.estimado)

    def test_si_no_responde_estima_en_linea_recta(self):
        cliente = ClienteFalso(error=requests.ConnectionError("sin conexión"))
        ruteador = RuteadorOSRM(cliente=cliente, respaldo=RECTA)
        tramo = ruteador.ruta(ORIGEN, DESTINO)
        self.assertTrue(tramo.estimado)
        self.assertAlmostEqual(tramo.km, distancia_km(ORIGEN, DESTINO))
        self.assertIn("OSRM no respondió", ruteador.falla)
        # Después de fallar no lo vuelve a intentar.
        ruteador.ruta(ORIGEN, DESTINO)
        self.assertEqual(cliente.llamadas, 1)

    def test_respuesta_con_error_tambien_usa_el_respaldo(self):
        cliente = ClienteFalso({"code": "NoRoute", "message": "Impossible route"})
        self.assertTrue(RuteadorOSRM(cliente=cliente).ruta(ORIGEN, DESTINO).estimado)

    def test_el_aviso_llega_a_la_recomendacion(self):
        ruteador = RuteadorOSRM(cliente=ClienteFalso(error=requests.Timeout()), respaldo=RECTA)
        precios = [precio("ref", SOBRE_EL_RECORRIDO, 1925)]
        rec = recomendar(precios, recorrido(), ruteador, "Diurno")
        self.assertIn("línea recta", rec.aviso)

    def test_restar_tramos(self):
        self.assertEqual(Tramo(5, 10) - Tramo(3, 4, estimado=True), Tramo(2, 6, estimado=True))


class TestUbicar(unittest.TestCase):
    def test_coordenadas_escritas(self):
        self.assertEqual(ubicar("-32.95124, -60.65287"), (-32.95124, -60.65287))

    def test_coordenadas_fuera_de_rango(self):
        with self.assertRaises(ErrorRuteo):
            ubicar("-132.9, -60.6")

    def test_direccion_encontrada(self):
        cliente = ClienteFalso([{"lat": "-32.9498938", "lon": "-60.6556917"}])
        self.assertEqual(ubicar("Oroño 1500", cliente=cliente), (-32.9498938, -60.6556917))

    def test_la_busqueda_se_limita_a_la_ciudad(self):
        cliente = ClienteFalso([{"lat": "-32.9453", "lon": "-60.6444"}])
        ubicar("Córdoba 1500", cliente=cliente)
        self.assertEqual(cliente.ultimos_parametros["bounded"], 1)
        self.assertIn("viewbox", cliente.ultimos_parametros)

    def test_direccion_no_encontrada(self):
        with self.assertRaisesRegex(ErrorRuteo, "No se encontró"):
            ubicar("Calle que no existe 99999", cliente=ClienteFalso([]))


if __name__ == "__main__":
    unittest.main()
