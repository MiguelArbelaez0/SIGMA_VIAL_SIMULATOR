"""Contratos del tablero: proporciones, datos reales y fuente de identificación."""

from PySide6.QtWidgets import QBoxLayout

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Phase
from sigma_vial.presentation.main_window import MainWindow
from sigma_vial.presentation.plate_camera import rear_camera


def test_large_dashboard_fits_and_small_layout_stacks(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(1580, 980)
    w.show()
    qtbot.wait(100)
    assert w.body.direction() == QBoxLayout.Direction.LeftToRight
    assert 1.8 < w.scene_card.width() / w.side_panel.width() < 2.2
    assert w.body_scroll.verticalScrollBar().maximum() == 0
    assert w.advanced_panel.isHidden()
    assert [w.tabs.tabText(i) for i in range(2)] == ["Automático", "Agregar"]
    w.resize(800, 600)
    qtbot.wait(100)
    assert w.body.direction() == QBoxLayout.Direction.TopToBottom
    assert w.body_scroll.verticalScrollBar().maximum() > 0
    w.body_scroll.verticalScrollBar().setValue(w.body_scroll.verticalScrollBar().maximum())
    for widget in (w.start_button, w.clock_label, w.speed, w.status_label):
        assert w.rect().contains(widget.mapTo(w, widget.rect().bottomRight()))
    assert w.body_scroll.horizontalScrollBar().maximum() == 0


def test_summary_uses_real_demand_and_only_committed_next_phase(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w.automatic_toggle.setChecked(False)
    w._add_vehicle(Access.EAST)
    w.simulation.running = True
    w.simulation.advance(0.15)
    w._add_pedestrian(Access.NORTH)
    w._refresh_simulation()
    assert "1 vehículos" in w.ew_summary.text()
    assert "1 peatones" in w.ped_summary.text()
    assert "Próximo turno" not in w.overview.text()
    # Read-only presentation of a phase already requested by the controller.
    w.simulation._pending_phase = Phase.EW_GREEN
    w._refresh_simulation()
    assert "Próximo turno" in w.overview.text()
    assert Phase.EW_GREEN.value in w.overview.text()
    assert "00:00:00" in w.clock_label.text()


def test_camera_selection_does_not_change_world_and_does_not_invent_readings(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    w._add_vehicle(Access.EAST)
    sim = w.simulation
    before = (sim.time, sim.phase, sim.running, len(sim.vehicles), sim.vehicle_rates.copy())
    w.camera_card.camera.setCurrentIndex(2)
    assert w.camera_card.controller.plate_access.currentIndex() == 2
    assert before == (sim.time, sim.phase, sim.running, len(sim.vehicles), sim.vehicle_rates)
    frame = rear_camera(sim.vehicles[0], 0, "rear-east")
    w.camera_card.show_frame(frame)
    assert sim.vehicles[0].plate not in w.camera_card.reading.text()
    assert "Sin ficha" in w.camera_card.record.text()
    assert w.camera_card.picture._image is not None
    w._reset_simulation()
    assert "Sin lectura" in w.camera_card.confirmation.text()
    assert "Sin ficha" in w.camera_card.record.text()


def test_dynamic_updates_keep_static_scenery(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    static = set(w.intersection_scene.items())
    w._add_vehicle(Access.NORTH)
    vehicle_item = w.vehicle_items[1]
    w.simulation.running = True
    for _ in range(8):
        w._advance_simulation()
    assert static <= set(w.intersection_scene.items())
    assert w.vehicle_items[1] is vehicle_item
