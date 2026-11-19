"""Vista ajustable con zoom acotado, arrastre y restablecimiento del encuadre."""

from PySide6.QtCore import QPointF, Qt
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
        self._fit_scene(QPointF())

    def zoom_in(self) -> None:
        if self._zoom_steps < 6:
            self._zoom_steps += 1
            self._fit_scene()

    def zoom_out(self) -> None:
        if self._zoom_steps > -2:
            self._zoom_steps -= 1
            self._fit_scene()

    def _fit_scene(self, center: QPointF | None = None) -> None:
        viewport = self.viewport().rect()
        if center is None:
            center = self.mapToScene(viewport.center())
        span = min(viewport.width(), viewport.height())
        # La vista inicial muestra 550 unidades a cada lado del centro en
        # el eje corto. En ventanas pequeñas se conserva la escala de los autos.
        initial_scale = min(max(span / 1100, 0.36), span / 600)
        factor = initial_scale * 1.2**self._zoom_steps
        if self._zoom_steps == -2:
            factor = min(factor, span / self.sceneRect().height())
        self.resetTransform()
        self.scale(factor, factor)
        self.centerOn(center)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_scene(QPointF() if self._zoom_steps == 0 else None)
