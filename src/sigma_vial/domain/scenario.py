"""Descripción estática del escenario; sin reloj, control de fases ni dependencias Qt."""

from dataclasses import dataclass
from enum import Enum

STOP_LINE_DISTANCE = 186
ARM_EXTENT = STOP_LINE_DISTANCE + 488


class Access(Enum):
    NORTH = "Norte"
    SOUTH = "Sur"
    EAST = "Oriente"
    WEST = "Occidente"


class SignalState(Enum):
    RED = "Rojo"
    YELLOW = "Amarillo"
    GREEN = "Verde"


@dataclass(frozen=True)
class Approach:
    access: Access
    inbound_lanes: int = 2
    outbound_lanes: int = 2


def initial_approaches() -> tuple[Approach, ...]:
    """Cuatro accesos inmutables; los estados gráficos pertenecen a presentación."""
    return tuple(Approach(access) for access in Access)
