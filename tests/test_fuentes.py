import unittest
from pathlib import Path

from src.config import CAMPOS_PRECIO, DIR_MUESTRA
from src.fuentes import ErrorFuente, FuenteCSV, FuenteJSON, fuente_para

FIXTURES = Path(__file__).parent / "fixtures"
MUESTRA_CSV = DIR_MUESTRA / "precios_muestra.csv"
MUESTRA_JSON = DIR_MUESTRA / "precios_muestra.json"


class TestLecturaNormal(unittest.TestCase):
    def test_csv_trae_todas_las_filas_y_columnas(self):
        registros = FuenteCSV().cargar(MUESTRA_CSV)
        self.assertEqual(len(registros), 15)
        self.assertEqual(list(registros[0]), CAMPOS_PRECIO)

    def test_csv_devuelve_texto(self):
        primero = FuenteCSV().cargar(MUESTRA_CSV)[0]
        self.assertEqual(primero["precio"], "1890")
        self.assertEqual(primero["empresa"], "ESTACIÓN OROÑO S.R.L.")

    def test_json_trae_todas_las_filas(self):
        registros = FuenteJSON().cargar(MUESTRA_JSON)
        self.assertEqual(len(registros), 15)
        self.assertEqual(registros[0]["precio"], "1890")


class TestEntradasInvalidas(unittest.TestCase):
    def test_archivo_inexistente(self):
        with self.assertRaisesRegex(ErrorFuente, "No existe"):
            FuenteCSV().cargar(FIXTURES / "no_existe.csv")

    def test_archivo_vacio(self):
        with self.assertRaisesRegex(ErrorFuente, "vacío"):
            FuenteCSV().cargar(FIXTURES / "vacio.csv")

    def test_fila_con_columnas_de_mas_indica_la_linea(self):
        with self.assertRaisesRegex(ErrorFuente, "línea 3"):
            FuenteCSV().cargar(FIXTURES / "columnas_de_mas.csv")

    def test_json_mal_formado(self):
        with self.assertRaisesRegex(ErrorFuente, "mal formado"):
            FuenteJSON().cargar(FIXTURES / "roto.json")

    def test_json_que_no_es_lista(self):
        with self.assertRaisesRegex(ErrorFuente, "lista de objetos"):
            FuenteJSON().cargar(FIXTURES / "objeto_suelto.json")

    def test_extension_no_soportada(self):
        with self.assertRaisesRegex(ErrorFuente, "no soportado"):
            fuente_para("precios.xlsx")


class TestPropiedades(unittest.TestCase):
    def test_csv_y_json_dan_lo_mismo(self):
        desde_csv = fuente_para(MUESTRA_CSV).cargar(MUESTRA_CSV)
        desde_json = fuente_para(MUESTRA_JSON).cargar(MUESTRA_JSON)
        self.assertEqual(desde_csv, desde_json)


if __name__ == "__main__":
    unittest.main()
