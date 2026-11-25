"""Ruta de píxeles. Ningún detector ni tracker recibe entidades del simulador."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sigma_vial.domain.image_tracking import ImageDetection, ImageTracker
from sigma_vial.domain.perception import Detection, SensorStatus, TrafficSummary
from sigma_vial.domain.scenario import Access


@dataclass(frozen=True)
class ImageFrame:
    pixels: object
    timestamp: float
    north_token: object | None = None
    north_count: int | None = None
    recognition_token: object | None = None
    vehicles: tuple[ImageDetection, ...] = ()
    recognition_error: str = ""


class ImageSource(Protocol):
    def read(self, timestamp: float) -> ImageFrame | None: ...
    def close(self) -> None: ...


def read_next_frame(capture, timestamp):
    ok, pixels = capture.read()
    return ImageFrame(pixels, timestamp) if ok else None


class LocalVideoSource:
    def __init__(self, path: str):
        import cv2

        self.capture = cv2.VideoCapture(path)
        if not self.capture.isOpened():
            raise ValueError("No se pudo abrir el video local.")

    def read(self, timestamp):
        import cv2

        self.capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        return read_next_frame(self.capture, timestamp)

    def close(self):
        self.capture.release()


class NanoDetDetector:
    CATEGORIES = {2: "automóvil", 3: "motocicleta", 5: "bus", 7: "camión"}

    def __init__(self, model_path: str, threshold: float = 0.35):
        from sigma_vial.infrastructure.vendor.nanodet import NanoDet

        if not Path(model_path).is_file():
            raise ValueError("Falta el modelo NanoDet ONNX; selecciona el archivo del modelo.")
        self.model = NanoDet(model_path, prob_threshold=threshold)

    def detect(self, frame: ImageFrame) -> list[ImageDetection]:
        import cv2

        height, width = frame.pixels.shape[:2]
        import numpy as np

        scale = min(416 / width, 416 / height)
        resized = cv2.resize(
            cv2.cvtColor(frame.pixels, cv2.COLOR_BGR2RGB),
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
        canvas = np.zeros((416, 416, 3), dtype=np.uint8)
        top = (416 - resized.shape[0]) // 2
        left = (416 - resized.shape[1]) // 2
        canvas[top : top + resized.shape[0], left : left + resized.shape[1]] = resized
        rows = self.model.infer(canvas)
        return [
            ImageDetection(
                (
                    max(0, (float(x1) - left) / scale),
                    max(0, (float(y1) - top) / scale),
                    min(width, (float(x2) - left) / scale),
                    min(height, (float(y2) - top) / scale),
                ),
                self.CATEGORIES[int(category)],
                float(score),
            )
            for x1, y1, x2, y2, score, category in rows
            if int(category) in self.CATEGORIES
        ]


def traffic_from_tracks(tracker: ImageTracker, access: Access, timestamp: float, width: int):
    detections = []
    for track in tracker.tracks.values():
        if track.state not in ("detectado", "confirmado"):
            continue
        x, y = track.detection.center
        state = (
            "saliendo"
            if track.counted
            else "detenido"
            if track.hits >= 2 and track.speed <= tracker.calibration.stopped_speed
            else "aproximándose"
        )
        detections.append(
            Detection(
                track.identifier,
                "video-local",
                access,
                int(x >= width / 2),
                track.detection.category,
                y,
                track.speed,
                state,
                timestamp,
                track.wait,
                None,
                "Sin lectura",
                "Visión por píxeles",
                track.detection.confidence,
            )
        )
    return TrafficSummary(
        access, timestamp, SensorStatus.AVAILABLE, tuple(detections), tracker.passage_count
    )


class YoloXDetector:
    CATEGORIES = NanoDetDetector.CATEGORIES

    def __init__(self, model_path: str, threshold: float = 0.35):
        from sigma_vial.infrastructure.vendor.yolox import YoloX

        if not Path(model_path).is_file():
            raise ValueError("Falta el modelo YOLOX ONNX compatible de OpenCV Zoo.")
        self.model = YoloX(model_path, confThreshold=threshold)

    def detect(self, frame: ImageFrame) -> list[ImageDetection]:
        import cv2
        import numpy as np

        height, width = frame.pixels.shape[:2]
        scale = min(640 / width, 640 / height)
        resized = cv2.resize(
            cv2.cvtColor(frame.pixels, cv2.COLOR_BGR2RGB), (int(width * scale), int(height * scale))
        )
        canvas = np.full((640, 640, 3), 114, dtype=np.float32)
        canvas[: resized.shape[0], : resized.shape[1]] = resized
        rows = self.model.infer(canvas)
        return [
            ImageDetection(
                (
                    max(0, float(x) / scale),
                    max(0, float(y) / scale),
                    min(width, float(x + w) / scale),
                    min(height, float(y + h) / scale),
                ),
                self.CATEGORIES[int(category)],
                float(score),
            )
            for x, y, w, h, score, category in rows
            if int(category) in self.CATEGORIES
        ]
