"""Vehículos y peatones vectoriales, ligeros y persistentes en la escena."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from sigma_vial.domain.simulation import VehicleType


class VehicleGraphicsItem(QGraphicsObject):
    COLORS = ("#e66b4e", "#3d87cb", "#e5b84f", "#54a582", "#a574c8")

    def __init__(
        self,
        color_index: int,
        length: float = 28,
        width: float = 16,
        kind: VehicleType = VehicleType.COMPACT,
    ) -> None:
        super().__init__()
        self.plate = ""
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.kind = kind
        self.length, self.width = length, width
        self.color = QColor(self.COLORS[color_index % len(self.COLORS)])
        self.setZValue(15)

    def boundingRect(self) -> QRectF:
        return QRectF(-self.length / 2 - 1, -self.width / 2 - 1, self.length + 2, self.width + 2)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawRoundedRect(
            QRectF(-self.length / 2 + 2, -self.width / 2 + 3, self.length, self.width), 5, 5
        )
        painter.setPen(QPen(self.color.darker(160), 1.2))
        finish = QLinearGradient(0, -self.width / 2, 0, self.width / 2)
        finish.setColorAt(0, self.color.lighter(135))
        finish.setColorAt(0.4, self.color)
        finish.setColorAt(1, self.color.darker(130))
        painter.setBrush(finish)
        painter.drawRoundedRect(
            QRectF(-self.length / 2, -self.width / 2, self.length, self.width), 5, 5
        )
        length, width = self.length, self.width
        painter.setPen(QPen(QColor("#162536"), 2))
        for x in (-length * 0.30, length * 0.30):
            for y in (-width / 2 + 1, width / 2 - 1):
                painter.drawLine(int(x - 3), int(y), int(x + 3), int(y))
        painter.setPen(QPen(QColor("#203c53"), 0.8))
        painter.setBrush(QColor("#b9d9e9"))
        if self.kind is VehicleType.MOTORCYCLE:
            painter.setBrush(QColor("#253c56"))
            painter.drawEllipse(QRectF(-4, -3, 8, 6))
            painter.drawLine(int(length / 2 - 4), -4, int(length / 2 - 4), 4)
        elif self.kind in (VehicleType.TRUCK, VehicleType.LARGE_TRUCK):
            painter.setBrush(QColor("#b5c3cb"))
            painter.drawRoundedRect(
                QRectF(-length / 2 + 3, -width / 2 + 3, length * 0.65, width - 6), 2, 2
            )
            painter.setBrush(QColor("#b9d9e9"))
            painter.drawRect(QRectF(length * 0.32, -width / 2 + 3, 5, width - 6))
        elif self.kind is VehicleType.BUS:
            for x in range(int(-length / 2 + 6), int(length / 2 - 5), 9):
                painter.drawRect(QRectF(x, -width / 2 + 2, 6, 4))
                painter.drawRect(QRectF(x, width / 2 - 6, 6, 4))
            painter.drawRect(QRectF(length / 2 - 7, -width / 2 + 4, 4, width - 8))
        else:
            painter.drawRoundedRect(
                QRectF(-length * 0.22, -width * 0.36, length * 0.45, width * 0.72), 2, 2
            )
            if self.kind is VehicleType.VAN:
                painter.setBrush(self.color.darker(115))
                painter.drawRect(QRectF(-length * 0.35, -width * 0.32, length * 0.36, width * 0.64))
        for x, color in ((length / 2 - 2, "#fff1bd"), (-length / 2 + 2, "#ff7474")):
            painter.setPen(QPen(QColor(color), 2))
            for y in (-width * 0.3, width * 0.3):
                painter.drawPoint(int(x), int(y))
        if self.length >= 28:
            painter.setPen(QPen(QColor("#292112"), 0.5))
            painter.setBrush(QColor("#ffdb35"))
            painter.drawRect(QRectF(-self.length / 2 + 1, -4, 4, 8))
            if self.plate and painter.transform().m11() ** 2 + painter.transform().m12() ** 2 > 4:
                font = painter.font()
                font.setPixelSize(5)
                painter.setFont(font)
                painter.setPen(QColor("#000000"))
                painter.drawText(QRectF(-14, -3, 28, 6), Qt.AlignmentFlag.AlignCenter, self.plate)


class PedestrianGraphicsItem(QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self.walking = False
        self.setZValue(16)

    def boundingRect(self) -> QRectF:
        return QRectF(-6, -7, 12, 14)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#35234c"), 1))
        painter.setBrush(QColor("#f0c99c"))
        painter.drawEllipse(QRectF(-3, -6, 6, 6))
        painter.setBrush(QColor("#087f86" if self.walking else "#8936ab"))
        painter.drawRoundedRect(QRectF(-4, 0, 8, 6), 2, 2)
        painter.drawLine(-4, 1, -6, 4)
        painter.drawLine(4, 1, 6, 4)
        painter.drawLine(-2, 5, -4, 7)
        painter.drawLine(2, 5, 4, 7)


class PedestrianSignalItem(QGraphicsObject):
    """Walk permission is distinct from the clearance of people already crossing."""

    def __init__(self) -> None:
        super().__init__()
        self.admission = False
        self.setZValue(12)

    def boundingRect(self) -> QRectF:
        return QRectF(-15, -19, 30, 38)

    def paint(self, painter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#e5b432"), 2))
        painter.setBrush(QColor("#162536"))
        painter.drawRoundedRect(self.boundingRect().adjusted(1, 1, -1, -1), 4, 4)
        painter.setPen(
            QPen(
                QColor("#ecfdf5" if self.admission else "#ff934c"),
                3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        if self.admission:
            painter.drawEllipse(QRectF(-3, -12, 6, 6))
            painter.drawLine(0, -4, 0, 5)
            painter.drawLine(0, -2, -7, 3)
            painter.drawLine(0, -2, 7, 1)
            painter.drawLine(0, 5, -6, 13)
            painter.drawLine(0, 5, 6, 13)
        else:
            for x in (-6, -2, 2, 6):
                painter.drawLine(x, -10, x, 4)
            painter.drawLine(-9, -1, -6, 9)
            painter.drawLine(-6, 9, 5, 9)
            painter.drawLine(5, 9, 6, 2)
