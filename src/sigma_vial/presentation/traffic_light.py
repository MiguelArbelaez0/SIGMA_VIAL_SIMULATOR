"""Semáforo vectorial reutilizable. Recibe un estado; no decide fases ni transiciones."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from sigma_vial.domain.scenario import Access, SignalState


class TrafficLightItem(QGraphicsObject):
    def __init__(self, access: Access, state: SignalState = SignalState.RED) -> None:
        super().__init__()
        self.access = access
        self._state = state
        self.setZValue(10)
        self.setToolTip(f"{access.value}: controla sus dos carriles de entrada")

    @property
    def state(self) -> SignalState:
        return self._state

    def set_state(self, state: SignalState) -> None:
        if not isinstance(state, SignalState):
            raise TypeError("El estado debe ser un SignalState.")
        self._state = state
        self.update()

    def lamp_color(self, lamp: SignalState) -> QColor:
        if lamp is not self._state:
            return QColor("#303c4e")
        match lamp:
            case SignalState.RED:
                return QColor("#ff525b")
            case SignalState.YELLOW:
                return QColor("#ffd25a")
            case SignalState.GREEN:
                return QColor("#3de0a2")

    def boundingRect(self) -> QRectF:
        return QRectF(-60, -66, 120, 158)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#62748b"), 1.5))
        painter.setPen(QPen(QColor("#64758a"), 5))
        painter.drawLine(0, 38, 0, -58)
        painter.drawLine(-48, -58, 0, -58)
        painter.setPen(QPen(QColor("#142237"), 7))
        painter.setBrush(QColor("#f4bd32"))
        painter.drawRoundedRect(QRectF(-23, -64, 46, 106), 10, 10)
        for index, lamp in enumerate(SignalState):
            painter.setPen(QPen(QColor("#0b1422"), 2))
            painter.setBrush(self.lamp_color(lamp))
            painter.drawEllipse(QRectF(-13, -55 + index * 32, 26, 26))
            if lamp is self._state:
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(-16, -58 + index * 32, 32, 32))

        painter.setPen(QPen(QColor("#162536"), 3))
        for y in (-55, -23, 9):
            painter.drawArc(QRectF(-15, y - 3, 30, 16), 0, 180 * 16)
        painter.setPen(QColor("#20334d"))
        font = QFont("Segoe UI")
        font.setPixelSize(21)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(-60, 47, 120, 27), Qt.AlignmentFlag.AlignCenter, self.access.value)
        font.setPixelSize(17)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(QRectF(-60, 74, 120, 18), Qt.AlignmentFlag.AlignCenter, self.state.value)
