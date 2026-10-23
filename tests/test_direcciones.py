import unittest

import requests

from src.direcciones import (
    ErrorDireccion,
    Geocodificador,
    GeocodificadorGeoref,
    GeocodificadorNominatim,
    GeocodificadorPhoton,
    Lugar,
    normalizar_direccion,
    sugerir,
    ubicar,
)
from src.ruteo import ErrorRuteo


class RespuestaFalsa:
    def __init__(self, datos):
        self.datos = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self.datos


class ClienteFalso:
    def __init__(self, datos=None, error=None):
        self.datos, self.error = datos, error
        self.parametros = None

    def get(self, url, params=None, **kwargs):
        self.parametros = params
        if self.error:
            raise self.error
        return RespuestaFalsa(self.datos)


class GeocodificadorFijo(Geocodificador):
    """Devuelve siempre los mismos lugares y cuenta cuántas veces lo llamaron."""

    def __init__(self, lugares=(), error=None):
        super().__init__()
        self.lugares, self.error, self.llamadas = list(lugares), error, 0

    def buscar(self, texto, localidad, provincia, maximo=5):
        self.llamadas += 1
        if self.error:
            raise self.error
        return self.lugares[:maximo]


CORDOBA_1500 = Lugar("Cordoba 1500", -32.9454, -60.6437)
ORONO_1500 = Lugar("Bv Orono 1500", -32.9523, -60.6556)


class TestNormalizar(unittest.TestCase):
    def test_saca_tildes_puntos_y_la_ene(self):
        self.assertEqual(normalizar_direccion("Bv. Oroño 1.500"), "bv orono 1500")

    def test_expande_abreviaturas(self):
        self.assertEqual(normalizar_direccion("Pte. Perón 5000"), "presidente peron 5000")
        self.assertEqual(normalizar_direccion("Mendoza esq. Oroño"), "mendoza y orono")
        self.assertEqual(normalizar_direccion("Avenida Francia 900"), "av francia 900")


class TestUbicar(unittest.TestCase):
    def test_coordenadas_escritas(self):
        self.assertEqual(ubicar("-32.95124, -60.65287", geocodificadores=[]), (-32.95124, -60.65287))

    def test_coordenadas_fuera_de_rango(self):
        with self.assertRaises(ErrorDireccion):
            ubicar("-132.9, -60.6", geocodificadores=[])

    def test_usa_el_primero_que_encuentra(self):
        primero, segundo = GeocodificadorFijo([CORDOBA_1500]), GeocodificadorFijo([ORONO_1500])
        self.assertEqual(ubicar("Córdoba 1500", geocodificadores=[primero, segundo]), CORDOBA_1500.coordenadas)
        self.assertEqual(segundo.llamadas, 0)

    def test_si_el_primero_no_encuentra_o_falla_prueba_el_siguiente(self):
        for primero in (GeocodificadorFijo([]), GeocodificadorFijo(error=requests.Timeout())):
            with self.subTest(primero=primero):
                ubicacion = ubicar("Oroño 1500", geocodificadores=[primero, GeocodificadorFijo([ORONO_1500])])
                self.assertEqual(ubicacion, ORONO_1500.coordenadas)

    def test_direccion_no_encontrada(self):
        with self.assertRaisesRegex(ErrorDireccion, "No se encontró"):
            ubicar("Calle que no existe 99999", geocodificadores=[GeocodificadorFijo([])])

    def test_es_un_error_de_ruteo_para_quien_lo_atrapa(self):
        self.assertTrue(issubclass(ErrorDireccion, ErrorRuteo))


class TestSugerir(unittest.TestCase):
    def test_junta_resultados_sin_repetir_y_en_orden(self):
        georef = GeocodificadorFijo([CORDOBA_1500])
        photon = GeocodificadorFijo([Lugar("Córdoba 1500", -32.94, -60.64), Lugar("Córdoba 501 (Centro)", -32.948, -60.63)])
        nombres = [l.nombre for l in sugerir("cordoba 1500", geocodificadores=[georef, photon])]
        self.assertEqual(nombres, ["Cordoba 1500", "Córdoba 501 (Centro)"])

    def test_descarta_lugares_que_no_nombran_la_calle(self):
        photon = GeocodificadorFijo([Lugar("Autopista Ernesto Guevara", -32.94, -60.72), CORDOBA_1500])
        self.assertEqual(sugerir("cordoba", geocodificadores=[photon]), [CORDOBA_1500])

    def test_un_servicio_caido_no_rompe_las_sugerencias(self):
        caido = GeocodificadorFijo(error=requests.ConnectionError())
        self.assertEqual(sugerir("orono 1500", geocodificadores=[caido, GeocodificadorFijo([ORONO_1500])]), [ORONO_1500])


class TestServicios(unittest.TestCase):
    def test_georef_manda_la_direccion_normalizada_y_la_ciudad(self):
        cliente = ClienteFalso({"direcciones": [
            {"nomenclatura": "BV ORONO 1500, Rosario, Santa Fe", "ubicacion": {"lat": -32.9523, "lon": -60.6556}},
            {"nomenclatura": "SIN UBICACION 1, Rosario, Santa Fe", "ubicacion": {"lat": None, "lon": None}},
        ]})
        lugares = GeocodificadorGeoref(cliente).buscar("Bv. Oroño 1500", "ROSARIO", "SANTA FE")
        self.assertEqual(cliente.parametros["direccion"], "bv orono 1500")
        self.assertEqual(cliente.parametros["localidad_censal"], "ROSARIO")
        self.assertEqual(lugares, [Lugar("Bv Orono 1500", -32.9523, -60.6556)])

    def test_nominatim_se_limita_a_la_ciudad(self):
        cliente = ClienteFalso([{"lat": "-32.9453", "lon": "-60.6444", "address": {"road": "Córdoba", "house_number": "1500"}}])
        lugares = GeocodificadorNominatim(cliente).buscar("Córdoba 1500", "ROSARIO", "SANTA FE")
        self.assertEqual(cliente.parametros["bounded"], 1)
        self.assertEqual(lugares[0].nombre, "Córdoba 1500")

    def test_nominatim_describe_un_punto(self):
        cliente = ClienteFalso({"address": {"road": "Avenida Pellegrini", "house_number": "1498"}})
        self.assertEqual(GeocodificadorNominatim(cliente).describir(-32.9562, -60.6463), "Avenida Pellegrini 1498")

    def test_photon_arma_el_nombre_con_calle_altura_y_barrio(self):
        cliente = ClienteFalso({"features": [{
            "properties": {"street": "Bulevar Oroño", "housenumber": "1500", "district": "Lourdes"},
            "geometry": {"coordinates": [-60.6556, -32.9521]},
        }]})
        lugares = GeocodificadorPhoton(cliente).buscar("orono 1500", "ROSARIO", "SANTA FE")
        self.assertEqual(lugares, [Lugar("Bulevar Oroño 1500 (Lourdes)", -32.9521, -60.6556)])
        self.assertIn("bbox", cliente.parametros)


if __name__ == "__main__":
    unittest.main()
