"""Composición de cuatro brazos y sus cuatro semáforos, con centro libre."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene, QWidget

from sigma_vial.domain.scenario import Access, initial_approaches
from sigma_vial.presentation.geometry import IntersectionGeometry
from sigma_vial.presentation.road_items import (
    add_access_label,
    add_approach_markings,
    add_pavement,
)
from sigma_vial.presentation.traffic_light import TrafficLightItem


class IntersectionScene(QGraphicsScene):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.geometry = IntersectionGeometry()
        self.approaches = initial_approaches()
        extent = self.geometry.arm_extent + self.geometry.scene_margin
        self.setSceneRect(-extent, -extent, 2 * extent, 2 * extent)
        self.setBackgroundBrush(QColor("#e7eee9"))
        add_pavement(self, self.geometry)

        self.traffic_lights: dict[Access, TrafficLightItem] = {}
        for approach in self.approaches:
            access = approach.access
            add_approach_markings(self, self.geometry, access)
            add_access_label(self, self.geometry, access)
            light = TrafficLightItem(access)
            self.addItem(light)
            light.setPos(*self.geometry.signal_position(access))
            self.traffic_lights[access] = light
