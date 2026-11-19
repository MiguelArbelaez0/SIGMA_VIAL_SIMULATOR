"""Construcción vectorial de pavimento, aceras y marcas, sin lógica de tráfico."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsScene

from sigma_vial.domain.scenario import Access
from sigma_vial.presentation.geometry import IntersectionGeometry, rotation


def add_pavement(scene: QGraphicsScene, geometry: IntersectionGeometry) -> None:
    h = geometry.road_half_width
    extent = geometry.arm_extent
    sidewalk = geometry.sidewalk_width
    no_pen = QPen(Qt.PenStyle.NoPen)

    add_landscape(scene, geometry)
    texture = QImage(64, 64, QImage.Format.Format_RGB32)
    texture.fill(QColor("#4b5058"))
    import random

    rng = random.Random(17)
    for _ in range(1200):
        gray = rng.randrange(63, 90)
        texture.setPixelColor(
            rng.randrange(64), rng.randrange(64), QColor(gray, gray + 2, gray + 5)
        )
    road = QPainterPath()
    road.addRect(QRectF(-h, -extent, 2 * h, 2 * extent))
    horizontal = QPainterPath()
    horizontal.addRect(QRectF(-extent, -h, 2 * extent, 2 * h))
    scene.addPath(road.united(horizontal), no_pen, QBrush(QPixmap.fromImage(texture)))

    tile = QImage(32, 32, QImage.Format.Format_RGB32)
    tile.fill(QColor("#c5c6c4"))
    paint = QPainter(tile)
    paint.setPen(QPen(QColor("#a8aba9"), 1))
    paint.drawRect(0, 0, 31, 31)
    paint.drawLine(1, 1, 30, 1)
    paint.end()
    for access in Access:
        curb = QPainterPath()
        curb.addRect(QRectF(-h - sidewalk, -extent, sidewalk, extent - h))
        strip = QPainterPath()
        strip.addRect(QRectF(-extent, -h - sidewalk, extent - h, sidewalk))
        curbs = curb.united(strip)
        item = scene.addPath(curbs, QPen(QColor("#b0c1cf"), 2), QBrush(QPixmap.fromImage(tile)))
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
        line(x, -extent, x, -geometry.crossing_far - 4, QPen(QColor("#f0ca66"), 2))
    dashed = QPen(QColor("#bac8d8"), 2, Qt.PenStyle.DashLine)
    dashed.setDashPattern([8, 7])
    for x in (-geometry.lane_width, geometry.lane_width):
        line(x, -extent, x, -geometry.stop_distance - 12, dashed)

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
    label.setBrush(QColor("#ffffff"))
    x, y = geometry.label_position(access)
    bounds = label.boundingRect()
    label.setPos(x - bounds.width() / 2, y - bounds.height() / 2)
    plate = scene.addRect(
        label.boundingRect().adjusted(-12, -3, 12, 3), QPen(QColor("#f5f7fc"), 2), QColor("#102d51")
    )
    plate.setPos(label.pos())
    plate.setZValue(3)
    label.setZValue(4)


def add_landscape(scene, geometry):
    """Capa estática pintada una vez: césped, sombras, arbolado y jardineras."""
    import random

    extent = geometry.arm_extent + geometry.scene_margin
    size = int(2 * extent)
    picture = QImage(size, size, QImage.Format.Format_RGB32)
    picture.fill(QColor("#6e8651"))
    painter = QPainter(picture)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rng = random.Random(54)
    for _ in range(12000):
        x, y = rng.randrange(size), rng.randrange(size)
        painter.setPen(
            QColor(rng.randrange(86, 121), rng.randrange(119, 150), rng.randrange(52, 79))
        )
        painter.drawPoint(x, y)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for _ in range(15):
                x, y = extent + sx * rng.uniform(205, 470), extent + sy * rng.uniform(215, 470)
                radius = rng.uniform(22, 39)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 32, 14, 65))
                painter.drawEllipse(QRectF(x - radius + 8, y - radius + 11, radius * 2, radius * 2))
                for _ in range(10):
                    dx, dy = (
                        rng.uniform(-radius * 0.6, radius * 0.6),
                        rng.uniform(-radius * 0.6, radius * 0.6),
                    )
                    r = rng.uniform(radius * 0.35, radius * 0.7)
                    gradient = QRadialGradient(x + dx - r * 0.3, y + dy - r * 0.3, r * 1.4)
                    gradient.setColorAt(0, QColor("#9bb855"))
                    gradient.setColorAt(0.45, QColor("#517732"))
                    gradient.setColorAt(1, QColor("#254f2e"))
                    painter.setBrush(gradient)
                    painter.drawEllipse(QRectF(x + dx - r, y + dy - r, 2 * r, 2 * r))
            for index in range(32):
                x = extent + sx * (180 + index * 8)
                y = extent + sy * 179
                painter.setBrush(QColor("#345e39"))
                painter.drawEllipse(QRectF(x - 6, y - 8, 12, 16))
                painter.setBrush(QColor("#eedbb8" if index % 3 else "#e6a6bb"))
                painter.drawEllipse(QRectF(x - 1, y - 3, 3, 3))
    painter.end()
    item = scene.addPixmap(QPixmap.fromImage(picture))
    item.setPos(-extent, -extent)
    item.setZValue(-5)
