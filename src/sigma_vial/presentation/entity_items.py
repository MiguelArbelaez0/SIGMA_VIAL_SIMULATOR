"""Vehículos y peatones vectoriales, ligeros y persistentes en la escena."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget


class VehicleGraphicsItem(QGraphicsObject):
    COLORS = ("#e66b4e", "#3d87cb", "#e5b84f", "#54a582", "#a574c8")

    def __init__(self, color_index: int) -> None:
        super().__init__()
        self.color = QColor(self.COLORS[color_index % len(self.COLORS)])
        self.setZValue(15)

    def boundingRect(self) -> QRectF:
        return QRectF(-15, -9, 30, 18)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#26374a"), 1.2))
        painter.setBrush(self.color)
        painter.drawRoundedRect(QRectF(-14, -8, 28, 16), 5, 5)
        painter.setPen(QPen(QColor("#d8edfa"), 0.8))
        painter.setBrush(QColor("#b9d9e9"))
        painter.drawRoundedRect(QRectF(-7, -6, 13, 12), 3, 3)
        painter.setPen(QPen(QColor("#fff1bd"), 1.6))
        painter.drawPoint(12, -4)
        painter.drawPoint(12, 4)
        painter.setPen(QPen(QColor("#f4f7fa"), 1.2))
        painter.drawPoint(-12, -4)
        painter.drawPoint(-12, 4)


class PedestrianGraphicsItem(QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
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
        painter.setBrush(QColor("#7043aa"))
        painter.drawRoundedRect(QRectF(-4, 0, 8, 6), 2, 2)
        painter.drawLine(-2, 5, -4, 7)
        painter.drawLine(2, 5, 4, 7)
