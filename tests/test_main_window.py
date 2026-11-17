"""Contrato visual básico y cierre con el ciclo de eventos real de Qt."""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Scenario
from sigma_vial.presentation.main_window import MainWindow


def test_window_title_and_required_texts(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "SIGMA VIAL"
    texts = {label.text() for label in window.findChildren(QLabel)}
    assert {
        "SIGMA VIAL",
        "SIGMA SOFTWARE SOLUTIONS",
        "Vista inicial · Simulación detenida",
    } <= texts
    button_texts = {button.text() for button in window.findChildren(QPushButton)}
    assert {"+", "−", "Restablecer"} <= button_texts
    assert window.scenario_combo.currentData() is Scenario.BALANCED
    assert window.config_panel.isHidden()
    assert window.details_panel.isHidden()
    window._refresh_simulation()
    assert "Demanda pendiente" in window.metrics.text()
    assert "Verde transcurrido" in window.metrics.text()
    assert "Motivo:" in window.metrics.text()


def test_window_can_be_shown_resized_and_closed(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    window.resize(800, 600)
    qtbot.waitUntil(lambda: window.width() == 800 and window.height() == 600)
    view = window.intersection_view
    visible = view.mapToScene(view.viewport().rect()).boundingRect()
    assert visible.contains(window.intersection_scene.sceneRect())
    assert window.close()
    qtbot.waitUntil(lambda: not window.isVisible())


def test_view_controls_zoom_and_restore_full_scene(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(800, 600)
    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    view = window.intersection_view
    view.reset_view()
    initial_scale = view.transform().m11()
    buttons["+"].click()
    zoomed_scale = view.transform().m11()
    assert zoomed_scale > initial_scale
    buttons["−"].click()
    assert view.transform().m11() == pytest.approx(initial_scale)
    for _ in range(12):
        view.zoom_in()
    assert view.zoom_steps == 6
    buttons["Restablecer"].click()
    assert view.zoom_steps == 0
    assert view.transform().m11() == pytest.approx(initial_scale)
    assert (
        view.mapToScene(view.viewport().rect())
        .boundingRect()
        .contains(window.intersection_scene.sceneRect())
    )


def test_simulation_controls_use_one_timer_and_sync_scene(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._add_vehicle(Access.NORTH)
    assert len(window.vehicle_items) == 1
    window._toggle_running()
    assert window.simulation_timer.isActive()
    window._toggle_running()
    assert not window.simulation_timer.isActive()
    paused_at = window.simulation.time
    window._advance_simulation()
    assert window.simulation.time == paused_at
    window._toggle_running()
    window.speed.setCurrentIndex(3)
    window._advance_simulation()
    assert window.simulation.time == pytest.approx(paused_at + 0.2)
    window._reset_simulation()
    assert not window.simulation_timer.isActive()
    assert not window.vehicle_items and not window.pedestrian_items
    assert window.simulation.time == 0
    assert all(
        light.state.name == "RED" for light in window.intersection_scene.traffic_lights.values()
    )


def test_scenario_reload_and_manual_pedestrian_are_reflected(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._add_pedestrian(Access.WEST)
    assert len(window.pedestrian_items) == 1
    window.scenario_combo.setCurrentIndex(window.scenario_combo.findData(Scenario.TWO_PEDESTRIANS))
    window._load_scenario()
    assert not window.simulation.running
    assert window.simulation.pedestrian_waiting() == 2
    assert window.simulation.waiting(Access.SOUTH) == 1
    assert len(window.pedestrian_items) == 2
    assert len(window.vehicle_items) == 1
