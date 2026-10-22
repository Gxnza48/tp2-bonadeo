import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import requests

from src.config import DIR_MUESTRA
from src.descarga import ErrorDescarga, antiguedad_minutos, descargar_precios
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

    def test_antiguedad(self):
        self.assertIsNone(antiguedad_minutos(self.destino))
        self.destino.write_bytes(CSV_BUENO)
        hace_dos_horas = time.time() - 2 * 3600
        os.utime(self.destino, (hace_dos_horas, hace_dos_horas))
        self.assertAlmostEqual(antiguedad_minutos(self.destino), 120, delta=1)


class TestPreciosDeLaWeb(ConCarpetaTemporal):
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
        self.assertIn("muestra", precios.aviso)

    def test_si_falla_sigue_con_el_archivo_viejo(self):
        self.destino.write_bytes(CSV_BUENO)
        viejo = time.time() - 3 * 3600
        os.utime(self.destino, (viejo, viejo))

        def descargador(ruta):
            raise ErrorDescarga("sin conexión")

        precios = self.precios(descargador)
        self.assertEqual(precios.archivo(), self.destino)
        self.assertIn("No se pudieron actualizar", precios.aviso)


if __name__ == "__main__":
    unittest.main()
