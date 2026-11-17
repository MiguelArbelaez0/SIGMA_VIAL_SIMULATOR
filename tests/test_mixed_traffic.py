"""Regresiones de carrocerías mixtas, capacidad y protección peatonal."""

import pytest

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Phase, Simulation, SimulationConfig, Vehicle, VehicleType
from sigma_vial.presentation.main_window import MainWindow


def simulation(**kwargs):
    sim = Simulation(config=SimulationConfig(**kwargs))
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    sim.running = True
    return sim


@pytest.mark.parametrize("kind", tuple(VehicleType))
@pytest.mark.parametrize("access", tuple(Access))
def test_every_body_stops_before_line(kind, access):
    sim = simulation(min_green=100)
    sim.phase = Phase.EW_GREEN if access in (Access.NORTH, Access.SOUTH) else Phase.NS_GREEN
    vehicle = Vehicle(1, access, 0, kind=kind)
    sim.vehicles.append(vehicle)
    sim.advance(18, step=0.2)
    line = sim.config.approach_extent - sim.config.stop_line_distance
    assert vehicle.position + vehicle.length / 2 <= line - sim.config.stop_margin
    assert vehicle.speed == pytest.approx(0)


@pytest.mark.parametrize(
    "leader_type,follower_type",
    [
        (VehicleType.LARGE_TRUCK, VehicleType.MOTORCYCLE),
        (VehicleType.COMPACT, VehicleType.LARGE_TRUCK),
    ],
)
def test_mixed_queue_spacing_through_start_crossing_and_exit(leader_type, follower_type):
    sim = simulation(min_green=100)
    leader = Vehicle(1, Access.NORTH, 0, position=150, kind=leader_type)
    follower = Vehicle(2, Access.NORTH, 0, position=20, kind=follower_type)
    sim.vehicles = [leader, follower]
    sim.phase = Phase.EW_GREEN
    sim.advance(12)
    sim.phase = Phase.NS_GREEN
    for _ in range(700):
        sim.advance(0.05)
        if leader in sim.vehicles and follower in sim.vehicles:
            assert (
                leader.position - follower.position
                >= (leader.length + follower.length) / 2 + sim.config.body_gap - 1e-8
            )
    assert sim.completed_vehicles == 2


def test_long_vehicle_needs_exit_capacity_and_rear_clearance():
    sim = simulation(lane_length=650)
    vehicle = Vehicle(1, Access.NORTH, 0, kind=VehicleType.LARGE_TRUCK)
    vehicle.position = sim.config.stop_position - (vehicle.length - 28) / 2
    sim.vehicles.append(vehicle)
    sim.phase = Phase.NS_GREEN
    sim.advance(3)
    assert not vehicle.inside
    sim = simulation()
    vehicle.inside = True
    vehicle.position = sim.config.approach_extent + sim.config.intersection_half + 20
    sim.vehicles = [vehicle]
    sim.phase = Phase.CLEARANCE
    sim.phase_time = 5
    sim._pending_phase = Phase.EW_GREEN
    sim.advance(0.05)
    assert sim.phase is Phase.CLEARANCE
    sim.advance(10)
    assert not vehicle.inside
    assert sim.phase is Phase.EW_GREEN


def test_spawn_checks_both_body_lengths():
    sim = simulation()
    sim.selected_vehicle_type = VehicleType.LARGE_TRUCK
    sim.vehicles = [Vehicle(i + 1, Access.NORTH, i, position=40) for i in range(2)]
    assert not sim.add_vehicle(Access.NORTH)
    assert len(sim.vehicles) == 2


def test_drawing_dimensions_pedestrian_permissions_and_reset(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    for kind in VehicleType:
        vehicle = Vehicle(len(window.simulation.vehicles) + 1, Access.NORTH, 0, kind=kind)
        window.simulation.vehicles.append(vehicle)
    window._sync_entities()
    for vehicle in window.simulation.vehicles:
        item = window.vehicle_items[vehicle.identifier]
        assert (item.length, item.width, item.kind) == (vehicle.length, vehicle.width, vehicle.kind)
    window.simulation.phase = Phase.WALK
    window._sync_signals()
    assert all(s.admission for s in window.intersection_scene.pedestrian_signals.values())
    window.simulation.phase = Phase.WALK_CLEARANCE
    window._sync_signals()
    assert not any(s.admission for s in window.intersection_scene.pedestrian_signals.values())
    for _ in range(12):
        window._add_pedestrian(Access.NORTH)
    positions = [item.pos() for item in window.pedestrian_items.values()]
    assert len({(p.x(), p.y()) for p in positions}) == len(positions)
    window.simulation.running = False
    before = [v.position for v in window.simulation.vehicles]
    window.simulation.advance(10)
    assert before == [v.position for v in window.simulation.vehicles]
    window._reset_simulation()
    assert not window.vehicle_items and not window.pedestrian_items
