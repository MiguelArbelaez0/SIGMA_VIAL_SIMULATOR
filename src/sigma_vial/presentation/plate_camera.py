"""Cámara trasera sintética. Solo el renderizador conoce la placa del mundo."""

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter


@dataclass(frozen=True)
class PlateCameraFrame:
    image: QImage
    plate_rect: QRectF | None
    timestamp: float
    camera: str
    track: str | None
    provenance: str = "Imagen sintética · recorte por geometría, no detección de placa"

    def crop(self):
        return self.image.copy(self.plate_rect.toRect()) if self.plate_rect else QImage()


def rear_camera(vehicle, timestamp: float, camera="virtual-rear") -> PlateCameraFrame:
    image = QImage(640, 360, QImage.Format.Format_RGB888)
    image.fill(QColor("#20334d"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))
    painter.drawText(12, 24, "CÁMARA TRASERA SINTÉTICA")
    rect = None
    track = None
    if vehicle is not None:
        # Pose and scale follow travel along the approach, independent of map zoom.
        scale = 0.75 + 0.25 * min(1, max(0, vehicle.position / 270))
        width, height = 420 * scale, 215 * scale
        left, top = (640 - width) / 2, 85 + (1 - scale) * 30
        painter.setBrush(QColor(vehicle.color))
        painter.setPen(QColor("#111827"))
        painter.drawRoundedRect(QRectF(left, top, width, height), 18, 18)
        painter.setBrush(QColor("#adc8db"))
        painter.drawRoundedRect(QRectF(left + 35, top + 18, width - 70, 65 * scale), 8, 8)
        painter.setBrush(QColor("#f46660"))
        for x in (left + 12, left + width - 36):
            painter.drawRect(QRectF(x, top + height - 60, 24, 30))
        rect = QRectF(320 - 140 * scale, top + height - 80 * scale, 280 * scale, 65 * scale)
        painter.setBrush(QColor("#ffdb35"))
        painter.setPen(QColor("black"))
        painter.drawRect(rect)
        font = QFont("Consolas")
        font.setPixelSize(int(48 * scale))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, vehicle.plate)
        track = f"{camera}-vehicle-{vehicle.identifier}"
    else:
        painter.drawText(190, 180, "Sin vehículo en cobertura")
    painter.end()
    return PlateCameraFrame(image, rect, timestamp, camera, track)
