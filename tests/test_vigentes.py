import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime

from src.config import DIR_MUESTRA
from src.fuentes import fuente_para
from src.modelos import PRODUCTOS, Estacion, PrecioEstacion
from src.pipeline import (
    NOMBRES_PRODUCTO,
    armar_precios,
    filtrar_ciudad,
    limpiar_precios,
    precios_vigentes,
)

CONSULTA = datetime(2026, 10, 22, 12, 0, 0)

ORONO = Estacion("9001", "30-71234567-1", "ESTACIÓN ORONO S.R.L.", "Bv. Oroño 1500",
                 "ROSARIO", "SANTA FE", "YPF", -32.95124, -60.65287)
PELLEGRINI = Estacion("9002", "30-70987654-2", "SERVICENTRO PELLEGRINI S.A.", "Av. Pellegrini 2100",
                      "ROSARIO", "SANTA FE", "SHELL C.A.P.S.A.", -32.95531, -60.66241)


def precio(valor, desde, estacion=ORONO, producto="super", horario="Diurno"):
    return PrecioEstacion(estacion, producto, horario, valor, datetime.fromisoformat(desde))


def vigentes_de_la_muestra(fecha_consulta):
    ruta = DIR_MUESTRA / "precios_muestra.csv"
    validos, _ = limpiar_precios(fuente_para(ruta).cargar(ruta), fecha_consulta)
    return precios_vigentes(armar_precios(validos), fecha_consulta)


class TestModelos(unittest.TestCase):
    def test_nombre_de_la_estacion(self):
        self.assertEqual(ORONO.nombre, "ESTACIÓN ORONO S.R.L. (YPF)")
        self.assertEqual(str(ORONO), "ESTACIÓN ORONO S.R.L. (YPF), Bv. Oroño 1500")

    def test_precio_no_positivo(self):
        with self.assertRaisesRegex(ValueError, "positivo"):
            precio(0, "2026-10-15 10:00:00")

    def test_producto_o_franja_desconocidos(self):
        with self.assertRaisesRegex(ValueError, "Producto"):
            precio(1890, "2026-10-15 10:00:00", producto="kerosene")
        with self.assertRaisesRegex(ValueError, "Franja"):
            precio(1890, "2026-10-15 10:00:00", horario="Tarde")

    def test_no_se_puede_modificar(self):
        with self.assertRaises(FrozenInstanceError):
            precio(1890, "2026-10-15 10:00:00").precio = 1

    def test_rige_desde_su_vigencia(self):
        p = precio(1890, "2026-10-15 10:00:00")
        self.assertTrue(p.rige_en(datetime(2026, 10, 15, 10, 0, 0)))
        self.assertFalse(p.rige_en(datetime(2026, 10, 15, 9, 59, 59)))
        self.assertEqual(p.dias_de_antiguedad(CONSULTA), 7)

    def test_las_categorias_de_la_limpieza_existen_en_el_dominio(self):
        self.assertEqual(set(NOMBRES_PRODUCTO.values()), set(PRODUCTOS))


class TestArmarPrecios(unittest.TestCase):
    def test_filas_de_una_estacion_comparten_el_objeto(self):
        ruta = DIR_MUESTRA / "precios_muestra.csv"
        validos, _ = limpiar_precios(fuente_para(ruta).cargar(ruta), CONSULTA)
        precios = armar_precios(validos)
        de_orono = [p for p in precios if p.estacion.idempresa == "9001"]
        self.assertEqual(len(de_orono), 3)
        self.assertTrue(all(p.estacion is de_orono[0].estacion for p in de_orono))

    def test_filtrar_ciudad_ignora_mayusculas_y_tildes(self):
        precios = [precio(1890, "2026-10-15 10:00:00")]
        self.assertEqual(len(filtrar_ciudad(precios, "Rosario", "Santa Fé")), 1)
        self.assertEqual(filtrar_ciudad(precios, "Funes", "Santa Fe"), [])


class TestPrecioVigente(unittest.TestCase):
    def test_gana_el_mas_reciente(self):
        viejo = precio(1790, "2026-09-10 09:30:00")
        nuevo = precio(1890, "2026-10-15 10:00:00")
        self.assertEqual(precios_vigentes([nuevo, viejo], CONSULTA), [nuevo])

    def test_un_precio_futuro_todavia_no_rige(self):
        viejo = precio(1790, "2026-09-10 09:30:00")
        futuro = precio(1990, "2026-10-23 00:00:00")
        self.assertEqual(precios_vigentes([viejo, futuro], CONSULTA), [viejo])

    def test_si_todos_son_futuros_no_hay_vigente(self):
        self.assertEqual(precios_vigentes([precio(1990, "2026-11-01 00:00:00")], CONSULTA), [])

    def test_con_la_misma_vigencia_gana_el_mas_caro(self):
        barato = precio(1850, "2026-10-15 10:00:00")
        caro = precio(1890, "2026-10-15 10:00:00")
        self.assertEqual(precios_vigentes([caro, barato], CONSULTA), [caro])
        self.assertEqual(precios_vigentes([barato, caro], CONSULTA), [caro])

    def test_productos_y_franjas_no_se_mezclan(self):
        precios = [
            precio(1890, "2026-10-15 10:00:00"),
            precio(1900, "2026-10-16 10:00:00", horario="Nocturno"),
            precio(2290, "2026-10-17 10:00:00", producto="premium"),
            precio(1925, "2026-10-12 08:45:00", estacion=PELLEGRINI),
        ]
        self.assertEqual(len(precios_vigentes(precios, CONSULTA)), 4)

    def test_muestra_al_22_de_octubre(self):
        super_diurno = [p for p in vigentes_de_la_muestra(CONSULTA)
                        if p.producto == "super" and p.horario == "Diurno"]
        # Ordenados del más barato al más caro; Oroño ya con su precio nuevo.
        self.assertEqual(
            [(p.estacion.idempresa, p.precio) for p in super_diurno],
            [("9004", 1870), ("9006", 1880), ("9001", 1890), ("9002", 1925)],
        )

    def test_muestra_al_1_de_octubre(self):
        # El precio de $1890 de Oroño empieza a regir el 15/10: antes rige el de $1790.
        vigentes = vigentes_de_la_muestra(datetime(2026, 10, 1, 12, 0, 0))
        self.assertIn(("9001", "super", 1790), [(p.estacion.idempresa, p.producto, p.precio) for p in vigentes])


class TestPropiedadesVigentes(unittest.TestCase):
    def setUp(self):
        ruta = DIR_MUESTRA / "precios_rosario_real.csv"
        validos, _ = limpiar_precios(fuente_para(ruta).cargar(ruta), CONSULTA)
        self.precios = armar_precios(validos)
        self.vigentes = precios_vigentes(self.precios, CONSULTA)

    def test_un_solo_precio_por_estacion_producto_y_franja(self):
        claves = [p.clave for p in self.vigentes]
        self.assertEqual(len(claves), len(set(claves)))

    def test_ninguna_clave_queda_sin_precio(self):
        self.assertEqual({p.clave for p in self.vigentes}, {p.clave for p in self.precios})

    def test_el_vigente_es_el_mas_reciente_que_rige(self):
        for vigente in self.vigentes:
            candidatos = [p for p in self.precios if p.clave == vigente.clave and p.rige_en(CONSULTA)]
            self.assertEqual(vigente.vigente_desde, max(p.vigente_desde for p in candidatos))

    def test_ordenados_por_precio_dentro_de_cada_producto(self):
        for producto in PRODUCTOS:
            valores = [p.precio for p in self.vigentes if p.producto == producto and p.horario == "Diurno"]
            self.assertEqual(valores, sorted(valores))


if __name__ == "__main__":
    unittest.main()
