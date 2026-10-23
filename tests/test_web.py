import unittest
from datetime import datetime

from src.config import DIR_MUESTRA
from src.direcciones import Lugar
from src.ruteo import ErrorRuteo, RuteadorLineaRecta
from src.web import Precios, crear_app

LUGARES = {
    "Oroño 1500": (-32.95124, -60.65287),
    "Pellegrini 2100": (-32.95531, -60.66241),
}


def ubicador_falso(texto, localidad, provincia):
    if texto not in LUGARES:
        raise ErrorRuteo(f"No se encontró la dirección '{texto}'")
    return LUGARES[texto]


class TestWeb(unittest.TestCase):
    def setUp(self):
        self.app_precios = Precios(DIR_MUESTRA / "precios_muestra.csv", "ROSARIO", "SANTA FE")
        app = crear_app(
            precios=self.app_precios,
            fecha_consulta=datetime(2026, 10, 22, 12, 0, 0),
            ruteador_factory=lambda: RuteadorLineaRecta(),
            ubicador=ubicador_falso,
            sugeridor=lambda texto, localidad, provincia: [
                Lugar(nombre, *coordenadas) for nombre, coordenadas in LUGARES.items()
                if texto.lower() in nombre.lower()
            ],
            describidor=lambda latitud, longitud: "Oroño 1500",
        )
        self.cliente = app.test_client()

    def test_pagina_principal(self):
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("¿Dónde cargo?", respuesta.get_data(as_text=True))

    def test_estaciones_del_producto(self):
        datos = self.cliente.get("/api/estaciones?producto=super").get_json()
        self.assertEqual(datos["franja"], "Diurno")
        self.assertEqual(len(datos["estaciones"]), 4)

    def test_recomendacion_con_destino(self):
        respuesta = self.cliente.get(
            "/api/recomendar?desde=Oroño 1500&hasta=Pellegrini 2100&producto=super&litros=30&consumo=12"
        )
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.get_json()
        self.assertEqual(datos["referencia"]["idempresa"], "9001")
        self.assertTrue(datos["estimado"])
        self.assertEqual(datos["conviene_desviarse"], datos["mejor"] is not None)
        ahorros = [o["ahorro_neto"] for o in datos["opciones"]]
        self.assertEqual(ahorros, sorted(ahorros, reverse=True))

    def test_cerca_mio_acepta_coordenadas_con_coma_decimal(self):
        respuesta = self.cliente.get("/api/recomendar?desde=Oroño 1500&litros=30,5")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.get_json()["destino"])

    def test_entradas_invalidas_dan_400_con_mensaje(self):
        casos = {
            "/api/recomendar?litros=30": "Falta desde",
            "/api/recomendar?desde=Oroño 1500&litros=muchos": "litros",
            "/api/recomendar?desde=Oroño 1500&litros=0": "litros",
            "/api/recomendar?desde=Oroño 1500&producto=kerosene": "Producto",
            "/api/recomendar?desde=Calle Falsa 123": "No se encontró",
        }
        for url, mensaje in casos.items():
            with self.subTest(url=url):
                respuesta = self.cliente.get(url)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(mensaje, respuesta.get_json()["error"])

    def test_sugerencias(self):
        datos = self.cliente.get("/api/sugerencias?q=oroño").get_json()
        self.assertEqual(datos["sugerencias"], [{"nombre": "Oroño 1500", "latitud": -32.95124, "longitud": -60.65287}])
        self.assertEqual(self.cliente.get("/api/sugerencias?q=or").get_json()["sugerencias"], [])

    def test_direccion_de_un_punto(self):
        self.assertEqual(self.cliente.get("/api/direccion?lat=-32.95&lon=-60.65").get_json()["nombre"], "Oroño 1500")
        self.assertEqual(self.cliente.get("/api/direccion?lat=abc").status_code, 400)

    def test_los_estimados_entran_solo_si_se_piden(self):
        from dataclasses import replace

        precios = self.app_precios
        reales = precios.vigentes(datetime(2026, 10, 22, 12, 0, 0))
        estimado = replace(next(p for p in reales if p.estacion.idempresa == "9006"),
                           precio=1500, estimado=True, precio_informado=1400, base_estimacion="prueba")
        precios._cache = (precios._cache[0], [p for p in reales if p.estacion.idempresa != "9006"] + [estimado])
        url = "/api/recomendar?desde=Oroño 1500&producto=super&franja=Diurno"
        sin = self.cliente.get(url).get_json()
        con = self.cliente.get(url + "&estimados=1").get_json()
        self.assertNotIn("9006", [o["idempresa"] for o in sin["opciones"]] + [sin["referencia"]["idempresa"]])
        self.assertTrue(con["mejor"]["estimado"])
        self.assertEqual(con["mejor"]["idempresa"], "9006")

    def test_estaciones_informa_que_tan_frescos_son_los_datos(self):
        datos = self.cliente.get("/api/estaciones?producto=super&franja=Diurno").get_json()
        self.assertEqual(datos["ultimo_informe"], "2026-10-18 09:05:00")
        self.assertFalse(datos["muestra"])

    def test_sin_estaciones_da_404(self):
        respuesta = self.cliente.get("/api/recomendar?desde=Oroño 1500&producto=gnc&franja=Nocturno")
        self.assertEqual(respuesta.status_code, 404)


if __name__ == "__main__":
    unittest.main()
