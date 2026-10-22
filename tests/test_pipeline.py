import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.config import CAMPOS_PRECIO, DIAS_MAXIMOS_VIGENCIA, DIR_MUESTRA
from src.fuentes import fuente_para
from src.pipeline import (
    ErrorEsquema,
    categoria_producto,
    cuit_valido,
    guardar_csv,
    leer_fecha,
    limpiar_precios,
    normalizar_campos,
)

CONSULTA = datetime(2026, 10, 22, 12, 0, 0)


def registro(**cambios):
    """Un registro válido como lo devuelve fuentes.py, con los cambios pedidos."""
    base = {
        "idempresa": "9001",
        "cuit": "30-71234567-1",
        "empresa": "ESTACIÓN OROÑO S.R.L.",
        "direccion": "Bv. Oroño 1500",
        "localidad": "ROSARIO",
        "provincia": "SANTA FE",
        "producto": "Nafta (súper) entre 92 y 95 Ron",
        "tipohorario": "Diurno",
        "precio": "1890",
        "fecha_vigencia": "2026-10-15 10:00:00",
        "empresabandera": "YPF",
        "latitud": "-32.95124",
        "longitud": "-60.65287",
    }
    base.update(cambios)
    return base


def cargar(nombre):
    ruta = DIR_MUESTRA / nombre
    return fuente_para(ruta).cargar(ruta)


class TestCuit(unittest.TestCase):
    def test_cuit_con_digito_correcto(self):
        self.assertTrue(cuit_valido("30-71234567-1"))
        self.assertTrue(cuit_valido("20-23456789-7"))

    def test_resto_11_da_digito_cero(self):
        self.assertTrue(cuit_valido("30-71111117-0"))

    def test_digito_verificador_incorrecto(self):
        self.assertFalse(cuit_valido("30-71234567-2"))

    def test_resto_10_es_invalido(self):
        # 11 - (suma % 11) da 10 para estos dígitos: ningún verificador sirve.
        for digito in range(10):
            self.assertFalse(cuit_valido(f"30-71111112-{digito}"))

    def test_formato_incorrecto(self):
        for cuit in ("30712345671", "30-7123456-71", "3O-71234567-1", "30-71234567-1 x", ""):
            with self.subTest(cuit=cuit):
                self.assertFalse(cuit_valido(cuit))


class TestCampos(unittest.TestCase):
    def test_fecha_valida(self):
        self.assertEqual(leer_fecha("2026-10-15 10:00:00"), datetime(2026, 10, 15, 10, 0, 0))

    def test_fecha_con_formato_correcto_pero_inexistente(self):
        self.assertIn("inexistente", leer_fecha("2026-02-30 10:00:00"))
        self.assertIn("inexistente", leer_fecha("2026-10-15 25:00:00"))

    def test_fecha_con_otro_formato(self):
        self.assertIn("formato", leer_fecha("15/10/2026 10:00"))

    def test_variantes_de_un_producto(self):
        for nombre in ("Nafta (súper) entre 92 y 95 Ron",
                       "nafta (super) entre 92 y 95 ron",
                       "  NAFTA (SÚPER)   entre 92 y 95 RON "):
            with self.subTest(nombre=nombre):
                self.assertEqual(categoria_producto(nombre), "super")
        self.assertEqual(categoria_producto("Gas Oil Grado 3"), "gasoil premium")
        self.assertIsNone(categoria_producto("Kerosene"))

    def test_normalizar_campos_ignora_columnas_de_mas(self):
        limpio = normalizar_campos({**registro(), " Precio ": " 1890 ", "geojson": "{}"})
        self.assertEqual(list(limpio), CAMPOS_PRECIO)
        self.assertEqual(limpio["precio"], "1890")


class TestLimpieza(unittest.TestCase):
    def motivos(self, *registros):
        _, rechazos = limpiar_precios(list(registros), CONSULTA)
        return [r["motivo"] for r in rechazos]

    def test_muestra_ficticia(self):
        validos, rechazos = limpiar_precios(cargar("precios_muestra.csv"), CONSULTA)
        self.assertEqual(len(validos), 10)
        self.assertEqual(
            [(r["fila"], r["motivo"]) for r in rechazos],
            [
                (6, "duplicado de la fila 5"),
                (7, "precio no positivo: 0"),
                (11, "coordenadas en (0, 0)"),
                (12, "coordenadas en (0, 0)"),
                (13, f"vigencia de más de {DIAS_MAXIMOS_VIGENCIA} días"),
            ],
        )

    def test_valores_quedan_con_su_tipo(self):
        validos, _ = limpiar_precios([registro(tipohorario="DIURNO")], CONSULTA)
        precio = validos[0]
        self.assertEqual(precio["precio"], 1890.0)
        self.assertEqual(precio["fecha_vigencia"], datetime(2026, 10, 15, 10, 0, 0))
        self.assertEqual(precio["producto"], "super")
        self.assertEqual(precio["tipohorario"], "Diurno")

    def test_faltantes(self):
        motivos = self.motivos(registro(precio="", latitud=""))
        self.assertEqual(motivos, ["falta precio | falta latitud"])

    def test_varios_motivos_en_la_misma_fila(self):
        motivos = self.motivos(registro(cuit="30-71234567-2", precio="-5"))
        self.assertEqual(motivos, ["CUIT inválido: 30-71234567-2 | precio no positivo: -5"])

    def test_precio_no_numerico(self):
        self.assertEqual(self.motivos(registro(precio="mil")), ["precio no numérico: mil"])

    def test_coordenadas_fuera_de_la_provincia(self):
        # Coordenadas de Córdoba capital en una estación de Santa Fe.
        motivos = self.motivos(registro(latitud="-31.4167", longitud="-64.1833"))
        self.assertEqual(motivos, ["coordenadas fuera de SANTA FE"])

    def test_vigencia_en_el_limite(self):
        justo = registro(fecha_vigencia="2026-08-23 12:00:00")  # 60 días exactos
        pasado = registro(fecha_vigencia="2026-08-23 11:59:59", idempresa="9002")
        validos, rechazos = limpiar_precios([justo, pasado], CONSULTA)
        self.assertEqual([v["idempresa"] for v in validos], ["9001"])
        self.assertEqual(rechazos[0]["fila"], 2)

    def test_duplicado_aunque_el_producto_este_escrito_distinto(self):
        motivos = self.motivos(registro(), registro(producto="NAFTA (SUPER) ENTRE 92 Y 95 RON"))
        self.assertEqual(motivos, ["duplicado de la fila 1"])

    def test_misma_estacion_con_otro_precio_no_es_duplicado(self):
        validos, rechazos = limpiar_precios(
            [registro(), registro(precio="1790", fecha_vigencia="2026-09-10 09:30:00")], CONSULTA
        )
        self.assertEqual((len(validos), len(rechazos)), (2, 0))

    def test_precio_fuera_de_rango_respecto_de_la_mediana(self):
        registros = [registro(idempresa=str(9000 + i), precio=p)
                     for i, p in enumerate(["1880", "1890", "1900", "1910", "1920", "250", "3500"])]
        motivos = self.motivos(*registros)
        self.assertEqual(motivos, [
            "precio fuera de rango: 250 (mediana 1900)",
            "precio fuera de rango: 3500 (mediana 1900)",
        ])

    def test_sin_suficientes_precios_no_se_controla_el_rango(self):
        motivos = self.motivos(registro(precio="1890"), registro(idempresa="9002", precio="250"))
        self.assertEqual(motivos, [])

    def test_falta_una_columna(self):
        sin_cuit = {k: v for k, v in registro().items() if k != "cuit"}
        with self.assertRaisesRegex(ErrorEsquema, "cuit"):
            limpiar_precios([sin_cuit], CONSULTA)


class TestPropiedades(unittest.TestCase):
    def test_ninguna_fila_se_pierde(self):
        for nombre in ("precios_muestra.csv", "precios_rosario_real.csv"):
            with self.subTest(archivo=nombre):
                registros = cargar(nombre)
                validos, rechazos = limpiar_precios(registros, CONSULTA)
                self.assertEqual(len(validos) + len(rechazos), len(registros))

    def test_csv_y_json_limpian_igual(self):
        desde_csv = limpiar_precios(cargar("precios_muestra.csv"), CONSULTA)
        desde_json = limpiar_precios(cargar("precios_muestra.json"), CONSULTA)
        self.assertEqual(desde_csv, desde_json)

    def test_los_validos_cumplen_las_reglas(self):
        validos, _ = limpiar_precios(cargar("precios_rosario_real.csv"), CONSULTA)
        self.assertGreater(len(validos), 0)
        for precio in validos:
            self.assertGreater(precio["precio"], 0)
            self.assertLessEqual((CONSULTA - precio["fecha_vigencia"]).days, DIAS_MAXIMOS_VIGENCIA)
            self.assertTrue(cuit_valido(precio["cuit"]))
            self.assertIn(precio["producto"], {"super", "premium", "gasoil", "gasoil premium", "gnc"})

    def test_rechazos_se_guardan_con_su_motivo(self):
        _, rechazos = limpiar_precios(cargar("precios_muestra.csv"), CONSULTA)
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "rechazos.csv"
            guardar_csv(rechazos, ruta, ["fila", "motivo"] + CAMPOS_PRECIO)
            with open(ruta, encoding="utf-8", newline="") as archivo:
                filas = list(csv.DictReader(archivo))
        self.assertEqual(len(filas), len(rechazos))
        self.assertEqual(filas[1]["motivo"], "precio no positivo: 0")


if __name__ == "__main__":
    unittest.main()
