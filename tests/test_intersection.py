"""Contrato del escenario y orientación de los elementos realmente dibujados."""

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItemGroup,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from sigma_vial.domain.scenario import Access, SignalState, initial_approaches
from sigma_vial.presentation.geometry import IntersectionGeometry, from_north
from sigma_vial.presentation.intersection_scene import IntersectionScene
from sigma_vial.presentation.traffic_light import TrafficLightItem


def test_scenario_has_four_approaches_and_sixteen_lanes() -> None:
    approaches = initial_approaches()
    assert len(approaches) == 4
    assert {approach.access for approach in approaches} == set(Access)
    assert all(a.inbound_lanes == a.outbound_lanes == 2 for a in approaches)
    assert sum(a.inbound_lanes for a in approaches) == 8
    assert sum(a.outbound_lanes for a in approaches) == 8


def test_four_red_lights_outside_roads_and_inside_scene(qapp: QApplication) -> None:
    scene = IntersectionScene()
    lights = [item for item in scene.items() if isinstance(item, TrafficLightItem)]
    assert len(lights) == 4
    assert {light.access for light in lights} == set(Access)
    h = scene.geometry.road_half_width
    extent = scene.geometry.arm_extent
    vertical_road = QRectF(-h, -extent, 2 * h, 2 * extent)
    horizontal_road = QRectF(-extent, -h, 2 * extent, 2 * h)
    for light in lights:
        assert light.state is SignalState.RED
        assert scene.traffic_lights[light.access] is light
        bounds = light.sceneBoundingRect()
        assert not bounds.intersects(vertical_road)
        assert not bounds.intersects(horizontal_road)
        assert scene.sceneRect().contains(bounds)
    assert not any(a.collidesWithItem(b) for a in lights for b in lights if a is not b)
    labels = [item for item in scene.items() if isinstance(item, QGraphicsSimpleTextItem)]
    assert {label.text() for label in labels} == {access.value.upper() for access in Access}
    for label in labels:
        assert not label.sceneBoundingRect().intersects(vertical_road)
        assert not label.sceneBoundingRect().intersects(horizontal_road)


def test_drawn_arrows_are_straight_and_keep_right(qapp: QApplication) -> None:
    scene = IntersectionScene()
    groups = [item for item in scene.items() if isinstance(item, QGraphicsItemGroup)]
    assert len(groups) == 4
    assert {group.rotation() for group in groups} == {0, 90, 180, 270}
    for group in groups:
        arrows = [item for item in group.childItems() if isinstance(item, QGraphicsPolygonItem)]
        assert len(arrows) == 4
        inbound = outbound = 0
        for arrow in arrows:
            polygon = arrow.polygon()
            tail = arrow.mapToScene((polygon[0] + polygon[1]) / 2)
            head = arrow.mapToScene(polygon[4])
            direction = head - tail
            center = arrow.mapToScene(QPointF(0, 0))
            assert (abs(direction.x()) < 0.001) != (abs(direction.y()) < 0.001)
            # Producto con el vector a la derecha (-dy, dx) en coordenadas de pantalla.
            assert center.x() * -direction.y() + center.y() * direction.x() > 0
            if QPointF.dotProduct(direction, center) < 0:
                inbound += 1
            else:
                outbound += 1
        assert inbound == outbound == 2


def test_stop_is_before_crossing_for_every_incoming_direction() -> None:
    geometry = IntersectionGeometry()
    assert geometry.road_half_width < geometry.crossing_near
    assert geometry.crossing_far < geometry.stop_distance < geometry.arrow_distance
    for access in Access:
        stop = from_north(access, -geometry.lane_width, -geometry.stop_distance)
        crossing = from_north(access, -geometry.lane_width, -geometry.crossing_far)
        direction = from_north(access, 0, 1)
        assert sum((c - s) * d for s, c, d in zip(stop, crossing, direction, strict=True)) > 0


@pytest.mark.parametrize("state", list(SignalState))
def test_light_paints_only_the_received_state(qapp: QApplication, state: SignalState) -> None:
    scene = QGraphicsScene()
    light = TrafficLightItem(Access.NORTH)
    scene.addItem(light)
    light.set_state(state)
    source = light.boundingRect()
    image = QImage(int(source.width() * 2), int(source.height() * 2), QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    scene.render(painter, QRectF(image.rect()), source)
    painter.end()
    active_colors = {
        SignalState.RED: QColor("#ff525b"),
        SignalState.YELLOW: QColor("#ffd25a"),
        SignalState.GREEN: QColor("#3de0a2"),
    }
    for index, lamp in enumerate(SignalState):
        pixel = image.pixelColor(
            int(-source.left() * 2), int((-42 + index * 32 - source.top()) * 2)
        )
        assert pixel == (active_colors[lamp] if lamp is state else QColor("#303c4e"))
    assert light.state is state
