"""Contrato del registro de vehículos ficticios, independiente de Qt y SQLite."""

from dataclasses import dataclass
from typing import Protocol

COLORS = ("#e66b4e", "#3d87cb", "#e5b84f", "#54a582", "#a574c8")


@dataclass(frozen=True)
class RegisteredVehicle:
    plate: str
    vehicle_type: str
    brand: str
    model: str
    color: str
    length: float
    width: float


class VehicleRegistry(Protocol):
    def reserve(self, vehicle: RegisteredVehicle) -> bool: ...

    def find(self, plate: str) -> RegisteredVehicle | None: ...
