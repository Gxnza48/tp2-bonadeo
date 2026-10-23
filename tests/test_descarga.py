import logging
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

import requests

from src.config import DIR_MUESTRA
from src.descarga import ErrorDescarga, antiguedad_minutos, descargar_de_alguna, descargar_precios
from src.web import MUESTRA, Precios

CSV_BUENO = (DIR_MUESTRA / "precios_muestra.csv").read_bytes()


class RespuestaFalsa:
    def __init__(self, contenido):
        self.content = contenido

    def raise_for_status(self):
        pass


class ClienteFalso:
    def __init__(self, contenido=None, error=None):
        self.contenido, self.error = contenido, error

    def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return RespuestaFalsa(self.contenido)


class ConCarpetaTemporal(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.destino = self.carpeta / "precios.csv"

    def tearDown(self):
        shutil.rmtree(self.carpeta)


class TestDescarga(ConCarpetaTemporal):
    def test_descarga_correcta(self):
        cantidad = descargar_precios(self.destino, cliente=ClienteFalso(CSV_BUENO))
        self.assertEqual(cantidad, 15)
        self.assertEqual(self.destino.read_bytes(), CSV_BUENO)

    def test_una_pagina_de_error_no_pisa_los_datos_anteriores(self):
        self.destino.write_bytes(CSV_BUENO)
        with self.assertRaisesRegex(ErrorDescarga, "no es el esperado"):
            descargar_precios(self.destino, cliente=ClienteFalso(b"<html>Servicio no disponible</html>"))
        self.assertEqual(self.destino.read_bytes(), CSV_BUENO)
        self.assertEqual(list(self.carpeta.iterdir()), [self.destino])

    def test_sin_conexion(self):
        with self.assertRaisesRegex(ErrorDescarga, "No se pudo descargar"):
            descargar_precios(self.destino, cliente=ClienteFalso(error=requests.ConnectionError()))
        self.assertFalse(self.destino.exists())

    def test_prueba_las_urls_en_orden(self):
        class ClientePorUrl:
            def get(self, url, **kwargs):
                if "copia" in url:
                    raise requests.HTTPError("404")
                return RespuestaFalsa(CSV_BUENO)

        self.assertEqual(descargar_de_alguna(self.destino, ["https://copia", "https://oficial"], ClientePorUrl()), 15)
        with self.assertRaisesRegex(ErrorDescarga, "copia"):
            descargar_de_alguna(self.destino, ["https://copia"], ClientePorUrl())

    def test_antiguedad(self):
        self.assertIsNone(antiguedad_minutos(self.destino))
        self.destino.write_bytes(CSV_BUENO)
        hace_dos_horas = time.time() - 2 * 3600
        os.utime(self.destino, (hace_dos_horas, hace_dos_horas))
        self.assertAlmostEqual(antiguedad_minutos(self.destino), 120, delta=1)


class TestPreciosDeLaWeb(ConCarpetaTemporal):
    def setUp(self):
        super().setUp()
        # Las fallas de descarga se registran en el log; acá son a propósito.
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)
    def precios(self, descargador):
        return Precios(self.destino, "ROSARIO", "SANTA FE", descargar=True, descargador=descargador)

    def test_baja_el_archivo_si_no_esta(self):
        llamadas = []

        def descargador(ruta):
            llamadas.append(ruta)
            Path(ruta).write_bytes(CSV_BUENO)

        precios = self.precios(descargador)
        self.assertEqual(precios.archivo(), self.destino)
        precios.archivo()
        self.assertEqual(len(llamadas), 1)  # la segunda vez el archivo es reciente
        self.assertIsNone(precios.aviso)

    def test_si_falla_y_no_hay_nada_usa_la_muestra(self):
        def descargador(ruta):
            raise ErrorDescarga("sin conexión")

        precios = self.precios(descargador)
        self.assertEqual(precios.archivo(), MUESTRA)
        self.assertEqual(
            precios.aviso,
            "No se pudieron bajar los precios del día; se muestran los precios del 22/10/2026, no los de hoy",
        )

    def test_despues_de_una_falla_no_reintenta_en_cada_pedido(self):
        intentos = []

        def descargador(ruta):
            intentos.append(ruta)
            raise ErrorDescarga("sin conexión")

        precios = self.precios(descargador)
        aviso = None
        for _ in range(3):
            precios.archivo()
            aviso = aviso or precios.aviso
            self.assertEqual(precios.aviso, aviso)  # el aviso no se va alargando
        self.assertEqual(len(intentos), 1)

    def test_la_muestra_se_calcula_a_su_fecha(self):
        # Meses después, los precios de la muestra tendrían más de 60 días;
        # igual se muestran, calculados al día en que se bajó.
        precios = Precios(MUESTRA, "ROSARIO", "SANTA FE")
        self.assertGreater(len(precios.vigentes(datetime(2027, 6, 1, 12, 0, 0))), 0)
        self.assertIn("22/10/2026", precios.aviso)

    def test_si_falla_sigue_con_el_archivo_viejo(self):
        self.destino.write_bytes(CSV_BUENO)
        viejo = time.time() - 3 * 3600
        os.utime(self.destino, (viejo, viejo))

        def descargador(ruta):
            raise ErrorDescarga("sin conexión")

        precios = self.precios(descargador)
        self.assertEqual(precios.archivo(), self.destino)
        self.assertEqual(precios.aviso, "No se pudieron bajar los precios del día")


if __name__ == "__main__":
    unittest.main()
