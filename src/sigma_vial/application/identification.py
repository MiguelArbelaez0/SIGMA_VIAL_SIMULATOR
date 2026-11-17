"""Consulta exacta tras confirmación OCR; no conoce entidades del simulador."""

from collections import deque
from dataclasses import dataclass

from sigma_vial.domain.plate_reading import OCRReading, PlateConsensus, PlateEvidence
from sigma_vial.domain.registration import RegisteredVehicle, VehicleRegistry


@dataclass(frozen=True)
class IdentificationEvent:
    camera: str
    track: str
    timestamp: float
    plate: str
    record: RegisteredVehicle | None

    @property
    def message(self):
        return (
            "Ficha recuperada del registro"
            if self.record
            else "Placa leída, vehículo no registrado"
        )


@dataclass(frozen=True)
class IdentificationResult:
    evidence: PlateEvidence
    event: IdentificationEvent | None
    is_new_event: bool = False


class IdentificationSession:
    def __init__(self, registry: VehicleRegistry):
        self.registry = registry
        self.consensus = PlateConsensus()
        self.events = deque(maxlen=200)
        self._resolved: dict[tuple[str, str, str], IdentificationEvent] = {}

    def observe(self, camera: str, track: str, reading: OCRReading) -> IdentificationResult:
        self._resolved = {
            key: value
            for key, value in self._resolved.items()
            if reading.timestamp - value.timestamp <= 60
        }
        # Camera participates in consensus identity; equal local IDs do not merge sources.
        evidence = self.consensus.observe(f"{camera}:{track}", reading)
        if not evidence.confirmed:
            return IdentificationResult(evidence, None)
        key = (camera, track, evidence.confirmed)
        if key in self._resolved:
            return IdentificationResult(evidence, self._resolved[key])
        record = self.registry.find(evidence.confirmed)
        event = IdentificationEvent(camera, track, reading.timestamp, evidence.confirmed, record)
        if len(self._resolved) >= 512:
            del self._resolved[next(iter(self._resolved))]
        self._resolved[key] = event
        self.events.append(event)
        return IdentificationResult(evidence, event, True)
