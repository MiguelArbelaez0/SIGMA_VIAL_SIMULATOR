"""Seguimiento por recuadros de imagen; no conoce el mundo ni las placas."""

from dataclasses import dataclass, field
from math import hypot


@dataclass(frozen=True)
class ImageCalibration:
    line_y: float = 0.65
    direction: int = 1
    stopped_speed: float = 3.0
    max_missing: float = 1.5
    association_distance: float = 70.0


@dataclass(frozen=True)
class ImageDetection:
    box: tuple[float, float, float, float]
    category: str
    confidence: float | None

    @property
    def center(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2, (y1 + y2) / 2)


@dataclass
class ImageTrack:
    identifier: str
    detection: ImageDetection
    first_seen: float
    last_seen: float
    hits: int = 1
    state: str = "detectado"
    movement: str = "pendiente"
    speed: float = 0
    wait: float = 0
    counted: bool = False
    history: list[tuple[float, float, float]] = field(default_factory=list)


class ImageTracker:
    def __init__(self, calibration: ImageCalibration | None = None):
        self.calibration = calibration or ImageCalibration()
        self.tracks: dict[str, ImageTrack] = {}
        self._next_id = 0
        self.max_tracks = 512
        self.passage_count = 0
        self.last_time = -1.0

    def update(self, detections: list[ImageDetection], timestamp: float, height: int):
        if timestamp <= self.last_time:
            return list(self.tracks.values())
        self.tracks = {k: t for k, t in self.tracks.items() if timestamp - t.last_seen <= 10}
        self.last_time = timestamp
        available = {
            key
            for key, t in self.tracks.items()
            if t.state != "finalizado" and timestamp - t.last_seen <= self.calibration.max_missing
        }
        for detection in sorted(detections, key=lambda d: -(d.confidence or 0))[: self.max_tracks]:
            candidates = []
            for key in available:
                previous = self.tracks[key]
                expected_x, expected_y = previous.detection.center
                if len(previous.history) >= 2:
                    t0, x0, y0 = previous.history[-2]
                    t1, x1, y1 = previous.history[-1]
                    if t1 > t0:
                        expected_x += (x1 - x0) / (t1 - t0) * (timestamp - t1)
                        expected_y += (y1 - y0) / (t1 - t0) * (timestamp - t1)
                candidates.append(
                    (hypot(detection.center[0] - expected_x, detection.center[1] - expected_y), key)
                )
            match = min(candidates, default=(float("inf"), ""))
            diagonal = hypot(
                detection.box[2] - detection.box[0], detection.box[3] - detection.box[1]
            )
            if match[0] <= max(self.calibration.association_distance, diagonal * 0.65):
                track = self.tracks[match[1]]
                available.remove(match[1])
                dt = timestamp - track.last_seen
                previous_y = track.detection.center[1]
                distance = hypot(
                    detection.center[0] - track.detection.center[0],
                    detection.center[1] - previous_y,
                )
                track.speed = distance / dt
                track.movement = (
                    "detenido" if track.speed <= self.calibration.stopped_speed else "aproximándose"
                )
                track.wait = track.wait + dt if track.speed <= self.calibration.stopped_speed else 0
                line = self.calibration.line_y * height
                crossed = (
                    previous_y < line <= detection.center[1]
                    if self.calibration.direction > 0
                    else previous_y > line >= detection.center[1]
                )
                if crossed and not track.counted:
                    track.counted = True
                    self.passage_count += 1
                track.last_seen = timestamp
                track.detection = detection
                track.hits += 1
                track.state = "confirmado"
            else:
                self._next_id += 1
                identifier = f"pixel-{self._next_id}"
                track = ImageTrack(identifier, detection, timestamp, timestamp)
                self.tracks[identifier] = track
            track.history.append((timestamp, *detection.center))
            track.history[:] = track.history[-128:]
        for track in self.tracks.values():
            if track.last_seen < timestamp:
                track.state = (
                    "finalizado"
                    if timestamp - track.last_seen > self.calibration.max_missing
                    else "perdido"
                )
        if len(self.tracks) > self.max_tracks:
            recent = sorted(self.tracks.values(), key=lambda t: t.last_seen, reverse=True)
            self.tracks = {t.identifier: t for t in recent[: self.max_tracks]}
        return list(self.tracks.values())
