"""Catálogo local ampliable; metadatos conocidos, no clasificación visual real."""

from dataclasses import dataclass
from enum import Enum


class VehicleType(Enum):
    MOTORCYCLE = ("Moto", 20, 9, 115, 48, 115)
    COMPACT = ("Automóvil pequeño", 28, 16, 110, 38, 110)
    SEDAN = ("Sedán", 34, 18, 110, 36, 105)
    SUV = ("Camioneta / SUV", 39, 21, 100, 30, 100)
    VAN = ("Furgoneta", 44, 22, 95, 26, 95)
    BUS = ("Bus", 70, 25, 80, 18, 80)
    TRUCK = ("Camión pequeño", 54, 24, 85, 22, 85)
    LARGE_TRUCK = ("Camión grande", 88, 26, 75, 15, 75)


@dataclass(frozen=True)
class CatalogEntry:
    model_id: str
    kind: VehicleType
    brand: str
    model: str
    graphic_variant: str

    @property
    def length(self):
        return self.kind.value[1]

    @property
    def width(self):
        return self.kind.value[2]

    @property
    def movement(self):
        return self.kind.value[3:]


CATALOG = {
    kind: CatalogEntry(kind.name.lower(), kind, "SIGMA ficticia", kind.value[0], kind.name.lower())
    for kind in VehicleType
}
assert len({entry.model_id for entry in CATALOG.values()}) == len(CATALOG)
assert all(
    entry.length > 0 and entry.width > 0 and all(p > 0 for p in entry.movement)
    for entry in CATALOG.values()
)
