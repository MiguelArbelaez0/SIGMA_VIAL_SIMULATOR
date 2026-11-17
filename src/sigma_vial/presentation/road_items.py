"""Construcción vectorial de pavimento, aceras y marcas, sin lógica de tráfico."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsScene

from sigma_vial.domain.scenario import Access
from sigma_vial.presentation.geometry import IntersectionGeometry, rotation


def add_pavement(scene: QGraphicsScene, geometry: IntersectionGeometry) -> None:
    h = geometry.road_half_width
    extent = geometry.arm_extent
    sidewalk = geometry.sidewalk_width
    no_pen = QPen(Qt.PenStyle.NoPen)

    road = QPainterPath()
    road.addRect(QRectF(-h, -extent, 2 * h, 2 * extent))
    horizontal = QPainterPath()
    horizontal.addRect(QRectF(-extent, -h, 2 * extent, 2 * h))
    scene.addPath(road.united(horizontal), no_pen, QColor("#344353"))

    for access in Access:
        curb = QPainterPath()
        curb.addRect(QRectF(-h - sidewalk, -extent, sidewalk, extent - h))
        strip = QPainterPath()
        strip.addRect(QRectF(-extent, -h - sidewalk, extent - h, sidewalk))
        curbs = curb.united(strip)
        item = scene.addPath(curbs, QPen(QColor("#b0c1cf"), 2), QColor("#dce3e5"))
        item.setRotation(rotation(access))


def add_approach_markings(
    scene: QGraphicsScene, geometry: IntersectionGeometry, access: Access
) -> QGraphicsItemGroup:
    """El brazo norte es el patrón: entrada a la izquierda, salida a la derecha."""
    group = QGraphicsItemGroup()
    scene.addItem(group)
    h = geometry.road_half_width
    extent = geometry.arm_extent
    no_pen = QPen(Qt.PenStyle.NoPen)
    white = QColor("#f4f7fa")

    def line(x1: float, y1: float, x2: float, y2: float, pen: QPen) -> None:
        group.addToGroup(scene.addLine(x1, y1, x2, y2, pen))

    for x in (-3, 3):
        line(x, -extent + 43, x, -geometry.crossing_far - 4, QPen(QColor("#f0ca66"), 2))
    dashed = QPen(QColor("#bac8d8"), 2, Qt.PenStyle.DashLine)
    dashed.setDashPattern([8, 7])
    for x in (-geometry.lane_width, geometry.lane_width):
        line(x, -extent + 43, x, -geometry.stop_distance - 12, dashed)

    # Arribando desde el norte se encuentra primero la detención, después el paso.
    line(-h + 5, -geometry.stop_distance, -6, -geometry.stop_distance, QPen(white, 6))
    stripe_spacing = 15
    for index in range(int((2 * h - 12 - 8) // stripe_spacing) + 1):
        stripe = scene.addRect(
            -h + 7 + index * stripe_spacing,
            -geometry.crossing_far,
            8,
            geometry.crossing_depth,
            no_pen,
            white,
        )
        group.addToGroup(stripe)

    for x in geometry.lane_centers:
        arrow = scene.addPolygon(
            QPolygonF(
                [
                    QPointF(-4, -20),
                    QPointF(4, -20),
                    QPointF(4, 3),
                    QPointF(12, 3),
                    QPointF(0, 20),
                    QPointF(-12, 3),
                    QPointF(-4, 3),
                ]
            ),
            no_pen,
            white,
        )
        group.addToGroup(arrow)
        arrow.setPos(x, -geometry.arrow_distance)
        if x > 0:
            arrow.setRotation(180)

    group.setRotation(rotation(access))
    group.setZValue(2)
    return group


def add_access_label(scene: QGraphicsScene, geometry: IntersectionGeometry, access: Access) -> None:
    font = QFont("Segoe UI")
    font.setPixelSize(22)
    font.setBold(True)
    label = scene.addSimpleText(access.value.upper(), font)
    label.setBrush(QColor("#20334d"))
    x, y = geometry.label_position(access)
    bounds = label.boundingRect()
    label.setPos(x - bounds.width() / 2, y - bounds.height() / 2)
    label.setZValue(4)
