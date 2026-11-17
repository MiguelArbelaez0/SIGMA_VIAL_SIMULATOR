"""Formularios independientes y programación de llegadas sin alterar el control."""

import pytest

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Scenario, Simulation, VehicleType
from sigma_vial.presentation.main_window import MainWindow


def window(qtbot):
    widget = MainWindow()
    qtbot.addWidget(widget)
    return widget


def test_tabs_preserve_world_control_and_forms(qtbot):
    w = window(qtbot)
    w._add_vehicle(Access.NORTH)
    w.manual_count.setValue(7)
    w.manual_type.setCurrentIndex(3)
    w._toggle_running()
    w._advance_simulation()
    sim = w.simulation
    before = (
        sim.time,
        sim.phase,
        sim.running,
        sim.automatic_generation,
        sim.vehicle_rates.copy(),
        len(sim.vehicles),
    )
    for _ in range(3):
        w.tabs.setCurrentIndex(1)
        w.tabs.setCurrentIndex(0)
    assert before == (
        sim.time,
        sim.phase,
        sim.running,
        sim.automatic_generation,
        sim.vehicle_rates,
        len(sim.vehicles),
    )
    assert w.manual_count.value() == 7
    assert w.manual_type.currentIndex() == 3


@pytest.mark.parametrize("profile", (0, 1, 2, 3))
def test_profile_only_changes_future_rates_and_fields(qtbot, profile):
    w = window(qtbot)
    w._add_vehicle(Access.NORTH)
    w._add_pedestrian(Access.WEST)
    w._toggle_running()
    w._advance_simulation()
    vehicle = w.simulation.vehicles[0]
    before = (w.simulation.time, w.simulation.phase, vehicle.plate, vehicle.position)
    w.profile_combo.setCurrentIndex(4)
    w.profile_combo.setCurrentIndex(profile)
    assert before == (w.simulation.time, w.simulation.phase, vehicle.plate, vehicle.position)
    assert w.simulation.running
    assert len(w.simulation.vehicles) == 1
    assert len(w.simulation.pedestrians) == 1
    for access, control in w.demand_controls.items():
        assert control.value() == w.simulation.vehicle_rates[access]
    assert w.pedestrian_rate.value() == w.simulation.pedestrian_rate
    w.demand_controls[Access.EAST].setValue(29)
    assert w.simulation.vehicle_rates[Access.EAST] == 29
    assert w.profile_combo.currentText() == "Personalizado"


def test_switch_off_stops_new_schedule_but_manual_pending_and_movement_continue(qtbot):
    w = window(qtbot)
    w.automatic_toggle.setChecked(False)
    w.manual_type.setCurrentIndex(w.manual_type.findData(VehicleType.LARGE_TRUCK))
    w.manual_count.setValue(5)
    w._add_manual_vehicles()
    sim = w.simulation
    assert len(sim.vehicles) == 2
    assert sim.requested[Access.NORTH] == 3
    assert list(sim._requested_types[Access.NORTH]) == [VehicleType.LARGE_TRUCK] * 3
    assert "2 incorporados" in w.manual_result.text()
    assert "3 solicitudes" in w.manual_result.text()
    w.manual_pedestrian_count.setValue(3)
    w._add_manual_pedestrians()
    assert len(sim.pedestrians) == 3
    sim.running = True
    sim.advance(20)
    assert len(sim.plates.used) <= 5
    assert all(v.kind is VehicleType.LARGE_TRUCK for v in sim.vehicles)
    assert sim._arrival_due == dict.fromkeys(Access, 0.0)
    assert sim._pedestrian_due == 0
    assert sim.time == pytest.approx(20)
    assert all(p.crossing is Access.NORTH for p in sim.pedestrians)


def test_manual_and_automatic_sources_coexist_and_preserve_type_settings(qtbot):
    w = window(qtbot)
    w.manual_type.setCurrentIndex(w.manual_type.findData(VehicleType.MOTORCYCLE))
    w.manual_count.setValue(1)
    auto_type = w.simulation.selected_vehicle_type
    w._add_manual_vehicles()
    first = w.simulation.vehicles[0]
    assert first.kind is VehicleType.MOTORCYCLE
    assert w.simulation.selected_vehicle_type is auto_type
    w.simulation.running = True
    w.simulation.advance(12)
    assert len(w.simulation.plates.used) > 1
    assert len(w.simulation.plates.used) == w.simulation._next_id
    assert first.plate in w.simulation.plates.used
    w._reset_simulation()
    assert not w.simulation.vehicles and not w.simulation.pedestrians
    assert not any(w.simulation.requested.values())
    assert not w.simulation.plates.used
    assert w.manual_type.currentData() is VehicleType.MOTORCYCLE


def test_disable_freezes_partial_arrival_without_catchup():
    sim = Simulation()
    sim.pedestrian_rate = 0
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.vehicle_rates[Access.NORTH] = 60
    sim.running = True
    sim.advance(0.4)
    sim.automatic_generation = False
    sim.advance(30)
    assert sim._arrival_due[Access.NORTH] == pytest.approx(0.4)
    assert not sim.vehicles
    sim.automatic_generation = True
    sim.advance(0.7)
    assert len(sim.plates.used) == 1


def test_demonstrations_do_not_inherit_previous_configuration():
    for scenario in Scenario:
        modified = Simulation()
        modified.vehicle_rates = dict.fromkeys(Access, 59.0)
        modified.pedestrian_rate = 55
        modified.automatic_generation = False
        modified.selected_vehicle_type = VehicleType.LARGE_TRUCK
        modified.vehicle_mix = (1, 1, 1, 1, 1, 1, 1, 100)
        fresh = Simulation()
        for sim in (modified, fresh):
            sim.load_scenario(scenario)
        assert modified.vehicle_rates == fresh.vehicle_rates
        assert modified.pedestrian_rate == fresh.pedestrian_rate
        assert modified.vehicle_mix == fresh.vehicle_mix
        assert modified.selected_vehicle_type == fresh.selected_vehicle_type
        assert modified.automatic_generation == fresh.automatic_generation
        assert not modified.running and modified.time == 0


@pytest.mark.parametrize("size", ((1500, 1000), (800, 600)))
def test_controls_visible_outside_tab_scroll(qtbot, size):
    w = window(qtbot)
    w.resize(*size)
    w.show()
    qtbot.waitUntil(w.isVisible)
    for index in (0, 1):
        w.tabs.setCurrentIndex(index)
        scroll = w.tabs.currentWidget()
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        for control in (w.start_button, w.speed, w.status_label):
            assert control.isVisible()
            rect = control.rect()
            assert w.rect().contains(control.mapTo(w, rect.topLeft()))
            assert w.rect().contains(control.mapTo(w, rect.bottomRight()))
        assert scroll.horizontalScrollBar().maximum() == 0
    assert w.width() == size[0] and w.height() == size[1]


def test_demo_replaces_graphics_when_new_session_reuses_entity_id(qtbot):
    w = window(qtbot)
    w.manual_type.setCurrentIndex(w.manual_type.findData(VehicleType.LARGE_TRUCK))
    w._add_manual_vehicles()
    assert w.vehicle_items[1].kind is VehicleType.LARGE_TRUCK
    w.scenario_combo.setCurrentIndex(w.scenario_combo.findData(Scenario.BLOCKED_EXIT))
    w._load_scenario()
    assert w.simulation.vehicles[0].kind is VehicleType.COMPACT
    assert w.vehicle_items[1].kind is VehicleType.COMPACT
    assert w.demand_controls[Access.NORTH].value() == 0
    assert not w.simulation.running
