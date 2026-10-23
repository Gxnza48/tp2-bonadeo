"""Clases del dominio: estaciones de servicio y sus precios."""

from dataclasses import dataclass
from datetime import datetime

PRODUCTOS = ("super", "premium", "gasoil", "gasoil premium", "gnc")
HORARIOS = ("Diurno", "Nocturno")


@dataclass(frozen=True)
class Estacion:
    idempresa: str
    cuit: str
    empresa: str
    direccion: str
    localidad: str
    provincia: str
    bandera: str
    latitud: float
    longitud: float

    @property
    def nombre(self):
        return f"{self.empresa} ({self.bandera})" if self.bandera else self.empresa

    @property
    def bandera_corta(self):
        """'SHELL C.A.P.S.A.' -> 'Shell', 'YPF' -> 'YPF'."""
        nombre = self.bandera.replace("C.A.P.S.A.", "").replace(" S.A.", "").strip()
        return nombre if len(nombre) <= 3 else nombre.title()

    def __str__(self):
        return f"{self.nombre}, {self.direccion}"


@dataclass(frozen=True)
class PrecioEstacion:
    """Lo que cobra una estación por un producto en una franja, desde una fecha."""

    estacion: Estacion
    producto: str
    horario: str
    precio: float
    vigente_desde: datetime
    # Para las estaciones que dejaron de informar: el precio es una
    # estimación y se guarda el último que informaron y de dónde sale.
    estimado: bool = False
    precio_informado: float | None = None
    base_estimacion: str | None = None

    def __post_init__(self):
        if self.producto not in PRODUCTOS:
            raise ValueError(f"Producto desconocido: {self.producto}")
        if self.horario not in HORARIOS:
            raise ValueError(f"Franja horaria desconocida: {self.horario}")
        if self.precio <= 0:
            raise ValueError(f"El precio tiene que ser positivo y es {self.precio}")

    @property
    def clave(self):
        """Lo que identifica a un precio: puede haber uno vigente por clave."""
        return (self.estacion.idempresa, self.producto, self.horario)

    def rige_en(self, momento):
        return self.vigente_desde <= momento

    def dias_de_antiguedad(self, momento):
        return (momento - self.vigente_desde).days


@dataclass(frozen=True)
class Recorrido:
    """Lo que el chofer quiere hacer: de dónde sale, a dónde va y cuánto carga.

    Sin destino es el modo "cerca mío": el desvío es ir hasta la estación y
    volver al punto de partida.
    """

    origen: tuple
    destino: tuple | None
    producto: str
    litros: float
    consumo_km_por_litro: float
    valor_hora: float = 0

    def __post_init__(self):
        if self.producto not in PRODUCTOS:
            raise ValueError(f"Producto desconocido: {self.producto}")
        if self.litros <= 0:
            raise ValueError("Los litros a cargar tienen que ser más que 0")
        if self.consumo_km_por_litro <= 0:
            raise ValueError("El consumo (km por litro) tiene que ser más que 0")
        if self.valor_hora < 0:
            raise ValueError("El valor de la hora no puede ser negativo")

    @property
    def cerca_mio(self):
        return self.destino is None


@dataclass(frozen=True)
class OpcionCarga:
    """Una estación evaluada: cuánto se ahorra y cuánto cuesta llegar."""

    precio: PrecioEstacion
    km_desvio: float
    minutos_desvio: float
    ahorro_surtidor: float
    costo_combustible_desvio: float
    costo_tiempo: float
    estimado: bool = False

    @property
    def ahorro_neto(self):
        return self.ahorro_surtidor - self.costo_combustible_desvio - self.costo_tiempo


@dataclass(frozen=True)
class RecomendacionCarga:
    recorrido: Recorrido
    franja: str
    referencia: OpcionCarga
    opciones: list
    aviso: str | None = None

    @property
    def mejor(self):
        """La opción con más ahorro neto, si es positivo; si no, None."""
        if self.opciones and self.opciones[0].ahorro_neto > 0:
            return self.opciones[0]
        return None

    @property
    def conviene_desviarse(self):
        return self.mejor is not None

    @property
    def estimado(self):
        return self.referencia.estimado or any(o.estimado for o in self.opciones)
