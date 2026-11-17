"""Contratos sin Qt y adaptador de lectura de entidades; no procesa imágenes."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from sigma_vial.domain.scenario import Access


class SensorStatus(Enum):
    AVAILABLE = "Disponible"
    NO_DATA = "Sin datos"
    DISCONNECTED = "Desconectada"


@dataclass(frozen=True)
class Detection:
    track_id: str
    camera_id: str
    access: Access
    lane: int
    vehicle_type: str
    position: float
    speed: float
    state: str
    observed_at: float
    wait: float
    plate: str | None = None
    plate_source: str = "Lectura simulada"
    provenance: str = "Simulada"
    confidence: float | None = None


@dataclass(frozen=True)
class TrafficSummary:
    access: Access
    observed_at: float
    status: SensorStatus
    detections: tuple[Detection, ...] = ()
    passage_count: int = 0

    @property
    def demand(self):
        return sum(d.state != "saliendo" for d in self.detections)

    @property
    def queue(self):
        return sum(d.state == "detenido" for d in self.detections)

    @property
    def lane_demand(self):
        return {
            lane: sum(d.lane == lane and d.state != "saliendo" for d in self.detections)
            for lane in (0, 1)
        }

    @property
    def max_wait(self):
        return max((d.wait for d in self.detections if d.state != "saliendo"), default=0)


@dataclass(frozen=True)
class ObservationBatch:
    traffic: dict[Access, TrafficSummary]
    pedestrian_waits: tuple[float, ...]
    observed_at: float


class ObservationSource(Protocol):
    def read(self, time: float, vehicles: list, pedestrians: list) -> ObservationBatch: ...


@dataclass
class VirtualCamera:
    access: Access
    start: float = 0
    end: float = 270
    count_line: float = 250
    lanes: tuple[int, ...] = (0, 1)
    interval: float = 0.1
    status: SensorStatus = SensorStatus.AVAILABLE
    last_result: TrafficSummary | None = None
    _previous: dict[int, float] = field(default_factory=dict)
    _counted: set[int] = field(default_factory=set)
    _tracks: dict[int, str] = field(default_factory=dict)
    _next_track: int = 0

    @property
    def identifier(self):
        return f"virtual-{self.access.name.lower()}"

    def track_for(self, world_identifier: int) -> str | None:
        return self._tracks.get(world_identifier)

    def read(self, time, vehicles):
        if self.status is not SensorStatus.AVAILABLE:
            return TrafficSummary(
                self.access, self.last_result.observed_at if self.last_result else 0, self.status
            )
        if (
            self.last_result is not None
            and time - self.last_result.observed_at < self.interval - 1e-9
        ):
            return self.last_result
        detected = []
        for v in vehicles:
            if v.access is not self.access or v.lane not in self.lanes:
                continue
            previous = self._previous.get(v.identifier)
            if previous is not None and previous < self.count_line <= v.position:
                self._counted.add(v.identifier)
            self._previous[v.identifier] = v.position
            if not self.start <= v.position <= self.end:
                continue
            if v.identifier not in self._tracks:
                self._next_track += 1
                self._tracks[v.identifier] = f"{self.identifier}-track-{self._next_track}"
            state = (
                "saliendo"
                if v.inside or v.exiting
                else "detenido"
                if v.speed <= 0.5
                else "aproximándose"
            )
            detected.append(
                Detection(
                    self._tracks[v.identifier],
                    self.identifier,
                    self.access,
                    v.lane,
                    v.kind.name,
                    v.position,
                    v.speed,
                    state,
                    time,
                    v.wait,
                    v.plate,
                )
            )
        self.last_result = TrafficSummary(
            self.access, time, self.status, tuple(detected), len(self._counted)
        )
        return self.last_result


@dataclass
class SimulatedObservationSource:
    cameras: dict[Access, VirtualCamera] = field(
        default_factory=lambda: {a: VirtualCamera(a) for a in Access}
    )

    def read(self, time, vehicles, pedestrians):
        return ObservationBatch(
            {a: camera.read(time, vehicles) for a, camera in self.cameras.items()},
            tuple(p.wait for p in pedestrians if not p.walking),
            time,
        )
