"""Componentes ligeros del tablero; imágenes ajustadas y marca vectorial local."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsDropShadowEffect,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QWidget,
)


class SigmaMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(58, 54)
        self.setAccessibleName("Símbolo SIGMA vectorial")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        path = QPainterPath(QPointF(8, 5))
        for x, y in (
            (47, 5),
            (47, 13),
            (25, 13),
            (39, 26),
            (23, 43),
            (34, 43),
            (28, 51),
            (6, 51),
            (6, 44),
            (25, 26),
            (8, 12),
        ):
            path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setBrush(QColor("#00cfad"))
        painter.drawRoundedRect(QRectF(34, 43, 20, 8), 3, 3)


class ImageLabel(QLabel):
    def __init__(self, minimum_height=100):
        super().__init__()
        self._image = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(minimum_height)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #182e49; border-radius: 9px;")

    def sizeHint(self):
        return QSize(300, 180)

    def set_image(self, image):
        self._image = image
        self._fit()

    def _fit(self):
        if self._image is not None and not self._image.isNull():
            self.setPixmap(
                QPixmap.fromImage(self._image).scaled(
                    self.contentsRect().size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


class DashboardBody(QWidget):
    def hasHeightForWidth(self):
        # Card content wraps within its assigned height; it must not enlarge the
        # scroll surface according to an image QLabel's previous pixmap size.
        return False

    def heightForWidth(self, width):
        return -1


class TrafficSwitch(QCheckBox):
    def sizeHint(self):
        return QSize(250, 36)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#04bc9b" if self.isChecked() else "#a8b7c9"))
        y = (self.height() - 24) / 2
        painter.drawRoundedRect(QRectF(2, y, 52, 24), 12, 12)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRectF(31 if self.isChecked() else 5, y + 3, 18, 18))
        painter.setPen(QColor("#0e213f"))
        painter.drawText(
            QRectF(66, 0, self.width() - 66, self.height()),
            Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )
        if self.hasFocus():
            painter.setPen(QPen(QColor("#073c87"), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, -1, -1), 5, 5)


def line_icon(name, color="#0e213f"):
    picture = QPixmap(28, 28)
    picture.fill(Qt.GlobalColor.transparent)
    painter = QPainter(picture)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    if name == "camera":
        painter.drawRoundedRect(QRectF(3, 8, 22, 16), 3, 3)
        painter.drawEllipse(QRectF(9, 11, 10, 10))
        painter.drawLine(8, 8, 10, 4)
        painter.drawLine(10, 4, 17, 4)
        painter.drawLine(17, 4, 19, 8)
    else:
        for x in (10, 18):
            painter.drawLine(x, 2, x, 9)
            painter.drawLine(x, 19, x, 26)
        for y in (10, 18):
            painter.drawLine(2, y, 9, y)
            painter.drawLine(19, y, 26, y)
    painter.end()
    return QIcon(picture)


def soften_card(widget):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(10)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(21, 47, 81, 24))
    widget.setGraphicsEffect(shadow)


class DashboardTabs(QTabWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.tabBar().setFixedWidth(self.width())
