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
