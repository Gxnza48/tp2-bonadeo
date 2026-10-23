"""Web app de Nafteando (Flask).

La lógica es la misma que la de consola: esta capa solo lee los
parámetros del formulario, llama al recomendador y devuelve JSON.

Para correrla:
    flask --app src.web run

De dónde salen los precios:
- NAFTEANDO_DATOS, si está definida: ese archivo, tal cual.
- En Vercel o con NAFTEANDO_DESCARGAR=1: se baja a la carpeta temporal,
  primero de la copia que publica el workflow de GitHub y si no del
  servidor oficial, y se renueva cada hora.
- Si no: data/raw/precios_vigentes.csv si ya se corrió `actualizar`, o la
  muestra real versionada.
"""

import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

from src.config import (
    ARCHIVO_VIGENTES,
    CENTROS_CIUDAD,
    CIUDAD_POR_DEFECTO,
    DIR_MUESTRA,
    MINUTOS_ENTRE_DESCARGAS,
    MINUTOS_REINTENTO,
    URL_PRECIOS_PUBLICADOS,
    URL_PRECIOS_VIGENTES,
)
from src.descarga import ErrorDescarga, antiguedad_minutos, descargar_de_alguna
from src.fuentes import ErrorFuente, fuente_para
from src.modelos import HORARIOS, PRODUCTOS, Recorrido
from src.pipeline import FORMATO_FECHA, ErrorEsquema, procesar
from src.recomendador import SinEstaciones, franja_para, recomendar
from src.direcciones import GeocodificadorNominatim, sugerir, ubicar
from src.ruteo import ErrorRuteo, RuteadorOSRM

MUESTRA = DIR_MUESTRA / "precios_rosario_real.csv"
# La muestra se bajó ese día: sus precios se calculan a esa fecha, para que
# la web siga mostrando algo cuando ya tengan más de 60 días.
FECHA_MUESTRA = datetime(2026, 10, 22, 12, 0, 0)

registro = logging.getLogger(__name__)

class ErrorPedido(Exception):
    """Un parámetro del pedido falta o no tiene sentido."""


class Precios:
    """Carga y procesa el archivo una vez, y lo vuelve a leer si cambia.

    Con `descargar`, antes de leer baja el archivo oficial si no está o si
    tiene más de MINUTOS_ENTRE_DESCARGAS. Si la descarga falla sigue con el
    archivo que haya, o con la muestra, y no reintenta hasta que pasen
    MINUTOS_REINTENTO (si no, cada pedido esperaría al servidor caído).
    """

    def __init__(self, ruta, localidad, provincia, descargar=False, descargador=None, estimar=True):
        self.ruta = Path(ruta)
        self.localidad = localidad
        self.provincia = provincia
        self.descargar = descargar
        self.descargador = descargador or (
            lambda destino: descargar_de_alguna(destino, [URL_PRECIOS_PUBLICADOS, URL_PRECIOS_VIGENTES])
        )
        self.estimar = estimar
        self.aviso = None
        self.usa_muestra = False
        self._ultima_falla = None
        self._cache = None

    def _toca_descargar(self):
        if not self.descargar:
            return False
        if self._ultima_falla and (time.monotonic() - self._ultima_falla) / 60 < MINUTOS_REINTENTO:
            return False
        antiguedad = antiguedad_minutos(self.ruta)
        return antiguedad is None or antiguedad > MINUTOS_ENTRE_DESCARGAS

    def archivo(self):
        if self._toca_descargar():
            try:
                self.descargador(self.ruta)
                self._ultima_falla = None
            except ErrorDescarga as error:
                registro.warning("Falló la descarga de precios: %s", error)
                self._ultima_falla = time.monotonic()

        falla = "No se pudieron bajar los precios del día" if self._ultima_falla else None
        self.usa_muestra = not (self.ruta.exists() and self.ruta != MUESTRA)
        if not self.usa_muestra:
            self.aviso = falla
            return self.ruta
        self.aviso = (
            (falla + "; se" if falla else "Se")
            + f" muestran los precios del {FECHA_MUESTRA:%d/%m/%Y}, no los de hoy"
        )
        return MUESTRA

    def vigentes(self, fecha_consulta):
        ruta = self.archivo()
        if ruta == MUESTRA:
            fecha_consulta = FECHA_MUESTRA
        firma = (ruta, ruta.stat().st_mtime, fecha_consulta.date(), fecha_consulta.hour)
        if self._cache is None or self._cache[0] != firma:
            registros = fuente_para(ruta).cargar(ruta)
            vigentes, _ = procesar(registros, fecha_consulta, self.localidad, self.provincia, self.estimar)
            self._cache = (firma, vigentes)
        return self._cache[1]

    def ultimo_informe(self, fecha_consulta):
        """La vigencia más reciente informada en la ciudad: qué tan frescos son los datos."""
        informados = [p.vigente_desde for p in self.vigentes(fecha_consulta) if not p.estimado]
        return max(informados) if informados else None


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


def precio_a_dict(precio):
    estacion = precio.estacion
    return {
        "idempresa": estacion.idempresa,
        "nombre": estacion.nombre,
        "direccion": estacion.direccion,
        "bandera": estacion.bandera,
        "bandera_corta": estacion.bandera_corta,
        "latitud": estacion.latitud,
        "longitud": estacion.longitud,
        "precio": precio.precio,
        "vigente_desde": precio.vigente_desde.strftime(FORMATO_FECHA),
        "estimado": precio.estimado,
        "precio_informado": precio.precio_informado,
        "base_estimacion": precio.base_estimacion,
    }


def opcion_a_dict(opcion):
    return precio_a_dict(opcion.precio) | {
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


def elegir_precios(localidad, provincia):
    if os.environ.get("NAFTEANDO_DATOS"):
        return Precios(os.environ["NAFTEANDO_DATOS"], localidad, provincia)
    if os.environ.get("VERCEL") or os.environ.get("NAFTEANDO_DESCARGAR") == "1":
        # En Vercel solo se puede escribir en la carpeta temporal, y el
        # servidor oficial no responde desde ahí: solo se usa la copia.
        urls = [URL_PRECIOS_PUBLICADOS]
        if not os.environ.get("VERCEL"):
            urls.append(URL_PRECIOS_VIGENTES)
        ruta = Path(tempfile.gettempdir()) / "precios_vigentes.csv"
        return Precios(ruta, localidad, provincia, descargar=True,
                       descargador=lambda destino: descargar_de_alguna(destino, urls))
    return Precios(ARCHIVO_VIGENTES if ARCHIVO_VIGENTES.exists() else MUESTRA, localidad, provincia)


def crear_app(precios=None, fecha_consulta=None, ruteador_factory=RuteadorOSRM, ubicador=ubicar,
              sugeridor=sugerir, describidor=None):
    """Arma la app. Los parámetros permiten probarla sin internet.

    fecha_consulta fija el "ahora" (sirve para mostrar la muestra de
    octubre de 2026); si no se pasa se usa el momento de cada pedido.
    """
    app = Flask(__name__)
    localidad, provincia = CIUDAD_POR_DEFECTO
    precios = precios or elegir_precios(localidad, provincia)
    fecha_fija = fecha_consulta
    if fecha_fija is None and os.environ.get("NAFTEANDO_FECHA_CONSULTA"):
        fecha_fija = datetime.strptime(os.environ["NAFTEANDO_FECHA_CONSULTA"], FORMATO_FECHA)

    describidor = describidor or GeocodificadorNominatim().describir
    centro = CENTROS_CIUDAD.get((localidad, provincia), (-32.9468, -60.6393))

    def ahora():
        return fecha_fija or datetime.now()

    @app.get("/")
    def inicio():
        return render_template(
            "index.html", ciudad=localidad.title(), centro=centro
        )

    @app.get("/api/sugerencias")
    def sugerencias():
        texto = request.args.get("q", "").strip()
        if len(texto) < 3:
            return jsonify(sugerencias=[])
        return jsonify(sugerencias=[
            {"nombre": lugar.nombre, "latitud": lugar.latitud, "longitud": lugar.longitud}
            for lugar in sugeridor(texto, localidad, provincia)
        ])

    @app.get("/api/direccion")
    def direccion():
        """Nombre de la calle de un punto (para cuando se usa el GPS o se toca el mapa)."""
        try:
            latitud = float(request.args["lat"])
            longitud = float(request.args["lon"])
        except (KeyError, ValueError):
            return jsonify(error="Faltan lat y lon numéricos"), 400
        try:
            nombre = describidor(latitud, longitud)
        except (requests.RequestException, ValueError, KeyError):
            nombre = None
        return jsonify(nombre=nombre)

    @app.get("/api/estaciones")
    def estaciones():
        momento = ahora()
        producto = request.args.get("producto", "super")
        franja = request.args.get("franja") or franja_para(momento)
        if producto not in PRODUCTOS or franja not in HORARIOS:
            return jsonify(error="Producto o franja desconocidos"), 400
        vigentes = [p for p in precios.vigentes(momento) if p.producto == producto and p.horario == franja]
        ultimo = precios.ultimo_informe(momento)
        return jsonify(
            franja=franja,
            aviso_datos=precios.aviso,
            muestra=precios.usa_muestra,
            ultimo_informe=ultimo.strftime(FORMATO_FECHA) if ultimo else None,
            estaciones=[precio_a_dict(p) for p in vigentes],
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
            # Los precios estimados entran solo si el chofer lo pide.
            candidatos = [
                p for p in precios.vigentes(momento)
                if not p.estimado or parametros.get("estimados") == "1"
            ]
            rec = recomendar(candidatos, recorrido, ruteador_factory(), franja)
        except (ErrorPedido, ErrorRuteo, ValueError) as error:
            return jsonify(error=str(error)), 400
        except SinEstaciones as error:
            return jsonify(error=str(error), aviso_datos=precios.aviso), 404
        except (ErrorFuente, ErrorEsquema) as error:
            return jsonify(error=f"No se pudieron leer los precios: {error}"), 500
        return jsonify(recomendacion_a_dict(rec) | {"aviso_datos": precios.aviso})

    return app


app = crear_app()

if __name__ == "__main__":
    app.run(debug=True)
