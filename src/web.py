"""Web app de Nafteando (Flask).

La lógica es la misma que la de consola: esta capa solo lee los
parámetros del formulario, llama al recomendador y devuelve JSON.

Para correrla:
    flask --app src.web run
"""

import os
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from src.config import CIUDAD_POR_DEFECTO, DIR_MUESTRA
from src.fuentes import ErrorFuente, fuente_para
from src.modelos import HORARIOS, PRODUCTOS, Recorrido
from src.pipeline import FORMATO_FECHA, ErrorEsquema, procesar
from src.recomendador import SinEstaciones, franja_para, recomendar
from src.ruteo import ErrorRuteo, RuteadorOSRM, ubicar

RUTA_DATOS_POR_DEFECTO = DIR_MUESTRA / "precios_rosario_real.csv"

ETIQUETAS_PRODUCTO = {
    "super": "Nafta súper",
    "premium": "Nafta premium",
    "gasoil": "Gasoil",
    "gasoil premium": "Gasoil premium",
    "gnc": "GNC",
}


class ErrorPedido(Exception):
    """Un parámetro del pedido falta o no tiene sentido."""


class Precios:
    """Carga y procesa el archivo una vez, y lo vuelve a leer si cambia."""

    def __init__(self, ruta, localidad, provincia):
        self.ruta = Path(ruta)
        self.localidad = localidad
        self.provincia = provincia
        self._cache = None

    def vigentes(self, fecha_consulta):
        firma = (self.ruta.stat().st_mtime, fecha_consulta.date(), fecha_consulta.hour)
        if self._cache is None or self._cache[0] != firma:
            registros = fuente_para(self.ruta).cargar(self.ruta)
            vigentes, _ = procesar(registros, fecha_consulta, self.localidad, self.provincia)
            self._cache = (firma, vigentes)
        return self._cache[1]


def numero(parametros, nombre, por_defecto=None):
    texto = parametros.get(nombre, "").strip().replace(",", ".")
    if not texto:
        if por_defecto is None:
            raise ErrorPedido(f"Falta {nombre}")
        return por_defecto
    try:
        return float(texto)
    except ValueError:
        raise ErrorPedido(f"{nombre} tiene que ser un número y llegó '{texto}'") from None


def opcion_a_dict(opcion):
    estacion = opcion.precio.estacion
    return {
        "idempresa": estacion.idempresa,
        "nombre": estacion.nombre,
        "direccion": estacion.direccion,
        "bandera": estacion.bandera,
        "latitud": estacion.latitud,
        "longitud": estacion.longitud,
        "precio": opcion.precio.precio,
        "vigente_desde": opcion.precio.vigente_desde.strftime(FORMATO_FECHA),
        "km_desvio": round(opcion.km_desvio, 2),
        "minutos_desvio": round(opcion.minutos_desvio, 1),
        "ahorro_surtidor": round(opcion.ahorro_surtidor, 2),
        "costo_combustible_desvio": round(opcion.costo_combustible_desvio, 2),
        "costo_tiempo": round(opcion.costo_tiempo, 2),
        "ahorro_neto": round(opcion.ahorro_neto, 2),
    }


def recomendacion_a_dict(rec):
    return {
        "conviene_desviarse": rec.conviene_desviarse,
        "franja": rec.franja,
        "referencia": opcion_a_dict(rec.referencia),
        "mejor": opcion_a_dict(rec.mejor) if rec.mejor else None,
        "opciones": [opcion_a_dict(o) for o in rec.opciones],
        "estimado": rec.estimado,
        "aviso": rec.aviso,
        "origen": rec.recorrido.origen,
        "destino": rec.recorrido.destino,
    }


def crear_app(ruta_datos=None, fecha_consulta=None, ruteador_factory=RuteadorOSRM, ubicador=ubicar):
    """Arma la app. Los parámetros permiten probarla sin internet.

    fecha_consulta fija el "ahora" (sirve para mostrar la muestra de
    octubre de 2026); si no se pasa se usa el momento de cada pedido.
    """
    app = Flask(__name__)
    localidad, provincia = CIUDAD_POR_DEFECTO
    precios = Precios(
        ruta_datos or os.environ.get("NAFTEANDO_DATOS", RUTA_DATOS_POR_DEFECTO), localidad, provincia
    )
    fecha_fija = fecha_consulta
    if fecha_fija is None and os.environ.get("NAFTEANDO_FECHA_CONSULTA"):
        fecha_fija = datetime.strptime(os.environ["NAFTEANDO_FECHA_CONSULTA"], FORMATO_FECHA)

    def ahora():
        return fecha_fija or datetime.now()

    @app.get("/")
    def inicio():
        return render_template("index.html", productos=ETIQUETAS_PRODUCTO, ciudad=localidad.title())

    @app.get("/api/estaciones")
    def estaciones():
        momento = ahora()
        producto = request.args.get("producto", "super")
        franja = request.args.get("franja") or franja_para(momento)
        if producto not in PRODUCTOS or franja not in HORARIOS:
            return jsonify(error="Producto o franja desconocidos"), 400
        vigentes = [p for p in precios.vigentes(momento) if p.producto == producto and p.horario == franja]
        return jsonify(
            franja=franja,
            estaciones=[{
                "nombre": p.estacion.nombre,
                "direccion": p.estacion.direccion,
                "latitud": p.estacion.latitud,
                "longitud": p.estacion.longitud,
                "precio": p.precio,
                "vigente_desde": p.vigente_desde.strftime(FORMATO_FECHA),
            } for p in vigentes],
        )

    @app.get("/api/recomendar")
    def api_recomendar():
        parametros = request.args
        momento = ahora()
        try:
            if not parametros.get("desde", "").strip():
                raise ErrorPedido("Falta desde dónde salís")
            producto = parametros.get("producto", "super")
            franja = parametros.get("franja") or franja_para(momento)
            if franja not in HORARIOS:
                raise ErrorPedido(f"Franja desconocida: {franja}")
            origen = ubicador(parametros["desde"], localidad, provincia)
            hasta = parametros.get("hasta", "").strip()
            destino = ubicador(hasta, localidad, provincia) if hasta else None
            recorrido = Recorrido(
                origen, destino, producto,
                litros=numero(parametros, "litros", 30),
                consumo_km_por_litro=numero(parametros, "consumo", 12),
                valor_hora=numero(parametros, "valor_hora", 0),
            )
            rec = recomendar(precios.vigentes(momento), recorrido, ruteador_factory(), franja)
        except (ErrorPedido, ErrorRuteo, ValueError) as error:
            return jsonify(error=str(error)), 400
        except SinEstaciones as error:
            return jsonify(error=str(error)), 404
        except (ErrorFuente, ErrorEsquema) as error:
            return jsonify(error=f"No se pudieron leer los precios: {error}"), 500
        return jsonify(recomendacion_a_dict(rec))

    return app


app = crear_app()

if __name__ == "__main__":
    app.run(debug=True)
