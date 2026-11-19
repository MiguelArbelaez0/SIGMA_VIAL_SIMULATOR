"""Dimensiones compartidas y rotaciones del brazo norte hacia los otros accesos."""

from dataclasses import dataclass

from sigma_vial.domain.scenario import ARM_EXTENT, Access


def rotation(access: Access) -> int:
    match access:
        case Access.NORTH:
            return 0
        case Access.EAST:
            return 90
        case Access.SOUTH:
            return 180
        case Access.WEST:
            return 270


def from_north(access: Access, x: float, y: float) -> tuple[float, float]:
    """Rota coordenadas en pantalla (y crece hacia abajo)."""
    match access:
        case Access.NORTH:
            return x, y
        case Access.EAST:
            return -y, x
        case Access.SOUTH:
            return -x, -y
        case Access.WEST:
            return y, -x


@dataclass(frozen=True)
class IntersectionGeometry:
    lane_width: float = 58
    arm_extent: float = ARM_EXTENT
    sidewalk_width: float = 32
    crossing_gap: float = 18
    crossing_depth: float = 36
    stop_gap: float = 16
    scene_margin: float = 66

    @property
    def road_half_width(self) -> float:
        return 2 * self.lane_width

    @property
    def crossing_near(self) -> float:
        return self.road_half_width + self.crossing_gap

    @property
    def crossing_far(self) -> float:
        return self.crossing_near + self.crossing_depth

    @property
    def stop_distance(self) -> float:
        return self.crossing_far + self.stop_gap

    @property
    def arrow_distance(self) -> float:
        return (self.stop_distance + self.arm_extent) / 2

    @property
    def lane_centers(self) -> tuple[float, ...]:
        return tuple(self.lane_width * offset for offset in (-1.5, -0.5, 0.5, 1.5))

    def signal_position(self, access: Access) -> tuple[float, float]:
        distance = self.stop_distance + self.sidewalk_width + 26
        return from_north(access, -distance, -distance)

    def label_position(self, access: Access) -> tuple[float, float]:
        return from_north(access, -self.road_half_width - self.sidewalk_width - 85, -360)
