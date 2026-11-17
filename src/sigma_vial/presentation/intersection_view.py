"""Vista ajustable con zoom acotado, arrastre y restablecimiento del encuadre."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QResizeEvent
from PySide6.QtWidgets import QFrame, QGraphicsView, QWidget

from sigma_vial.presentation.intersection_scene import IntersectionScene


class IntersectionView(QGraphicsView):
    def __init__(self, scene: IntersectionScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName("Intersección de cuatro accesos")
        self._zoom_steps = 0

    @property
    def zoom_steps(self) -> int:
        return self._zoom_steps

    def reset_view(self) -> None:
        self._zoom_steps = 0
        self._fit_scene()

    def zoom_in(self) -> None:
        if self._zoom_steps < 6:
            self._zoom_steps += 1
            self._fit_scene()

    def zoom_out(self) -> None:
        if self._zoom_steps > -2:
            self._zoom_steps -= 1
            self._fit_scene()

    def _fit_scene(self) -> None:
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        factor = 1.2**self._zoom_steps
        self.scale(factor, factor)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_scene()
