"""Cámara trasera sintética. Solo el renderizador conoce la placa del mundo."""

from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen

from sigma_vial.domain.catalog import VehicleType


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


def rear_camera(
    vehicle, timestamp: float, camera="virtual-rear", *, coverage_start: float = 0
) -> PlateCameraFrame:
    image = QImage(640, 360, QImage.Format.Format_RGB888)
    image.fill(QColor("#20334d"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    road = QLinearGradient(0, 0, 0, 360)
    road.setColorAt(0, QColor("#7c8996"))
    road.setColorAt(0.3, QColor("#555d65"))
    road.setColorAt(1, QColor("#343b43"))
    painter.fillRect(image.rect(), road)
    painter.setPen(QPen(QColor("#dbe0e4"), 5))
    painter.drawLine(180, 0, 35, 360)
    painter.drawLine(470, 0, 620, 360)
    painter.setPen(QColor("white"))
    painter.drawText(12, 24, "CÁMARA TRASERA SINTÉTICA")
    rect = None
    track = None
    if vehicle is not None:
        # Pose and scale follow travel along the approach, independent of map zoom.
        scale = 0.75 + 0.25 * min(1, max(0, (vehicle.position - coverage_start) / 270))
        kind = vehicle.kind
        body_width, body_height = {
            VehicleType.MOTORCYCLE: (300, 210),
            VehicleType.COMPACT: (420, 215),
            VehicleType.SEDAN: (450, 215),
            VehicleType.SUV: (465, 230),
            VehicleType.VAN: (470, 240),
            VehicleType.BUS: (500, 260),
            VehicleType.TRUCK: (490, 250),
            VehicleType.LARGE_TRUCK: (510, 255),
        }[kind]
        width, height = body_width * scale, body_height * scale
        left, top = (640 - width) / 2, 85 + (1 - scale) * 30
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 85))
        painter.drawEllipse(QRectF(left - 25, top + height - 20, width + 50, 40))
        painter.setBrush(QColor("#151c25"))
        for x in (left + 10, left + width - 38):
            painter.drawRoundedRect(QRectF(x, top + height - 35, 28, 50), 8, 8)
        finish = QLinearGradient(left, top, left + width, top + height)
        color = QColor(vehicle.color)
        finish.setColorAt(0, color.lighter(145))
        finish.setColorAt(0.45, color)
        finish.setColorAt(1, color.darker(125))
        painter.setBrush(finish)
        painter.setPen(QColor("#111827"))
        painter.drawRoundedRect(QRectF(left, top, width, height), 18, 18)
        painter.setBrush(QColor("#adc8db"))
        painter.drawRoundedRect(QRectF(left + 35, top + 18, width - 70, 65 * scale), 8, 8)
        painter.setPen(QPen(QColor("#d4dce4"), 3))
        painter.drawLine(
            int(left + 20), int(top + height - 14), int(left + width - 20), int(top + height - 14)
        )
        if kind in (VehicleType.TRUCK, VehicleType.LARGE_TRUCK, VehicleType.VAN):
            painter.setPen(QPen(QColor("#adb7be"), 2))
            painter.drawLine(320, int(top + 8), 320, int(top + height - 90 * scale))
            for y in range(int(top + 15), int(top + height - 90 * scale), 12):
                painter.drawLine(int(left + 25), y, int(left + width - 25), y)
        if kind is VehicleType.BUS:
            painter.setPen(QPen(QColor("#354558"), 3))
            for x in range(int(left + 50), int(left + width - 30), 55):
                painter.drawLine(x, int(top + 20), x, int(top + 65 * scale))
        if kind is VehicleType.MOTORCYCLE:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#202c3f"))
            painter.drawEllipse(QRectF(285, top - 30, 70, 75))
        painter.setBrush(QColor("#f46660"))
        for x in (left + 12, left + width - 36):
            painter.drawRect(QRectF(x, top + height - 60, 24, 30))
        rect = QRectF(320 - 140 * scale, top + height - 80 * scale, 280 * scale, 65 * scale)
        painter.setBrush(QColor("#ffdb35"))
        painter.setPen(QColor("black"))
        rect = QRectF(rect.toRect())
        painter.drawRect(rect.adjusted(-2, -2, 2, 2))
        font = QFont("Consolas")
        font.setPixelSize(42)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        painter.drawText(
            int(rect.center().x() - metrics.horizontalAdvance(vehicle.plate) / 2),
            int(rect.center().y() + (metrics.ascent() - metrics.descent()) / 2),
            vehicle.plate,
        )
        track = f"{camera}-vehicle-{vehicle.identifier}"
    else:
        painter.drawText(190, 180, "Sin vehículo en cobertura")
    painter.end()
    return PlateCameraFrame(image, rect, timestamp, camera, track)


def image_png(image: QImage) -> bytes:
    if image.isNull():
        return b""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())
