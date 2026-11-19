"""Pruebas deterministas del motor independiente de Qt."""

from itertools import pairwise

import pytest

from sigma_vial.domain.scenario import Access, SignalState
from sigma_vial.domain.simulation import Phase, Scenario, Simulation, SimulationConfig, Vehicle


def quiet_rates(sim: Simulation) -> Simulation:
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    return sim


def start_in_camera_range(sim: Simulation) -> None:
    """Prepara vehículos observables para las pruebas de cambio de fase."""
    for vehicle in sim.vehicles:
        vehicle.position += sim.observation_source.cameras[vehicle.access].start


def test_high_demand_vehicles_queue_cross_and_leave_on_all_four_arms() -> None:
    sim = Simulation()
    for access in Access:
        sim.set_demand(access, 60)
        sim.add_vehicle(access)
    sim.add_pedestrian(Access.NORTH)
    assert sim.config.approach_extent - sim.config.stop_line_distance == 488
    assert all(vehicle.position == 0 for vehicle in sim.vehicles)
    assert all(summary.demand == 0 for summary in sim.observations().traffic.values())

    queued = set()
    entered_on_green = set()
    completed_accesses = set()
    pedestrian = sim.pedestrians[0]
    sim.running = True
    for _ in range(1600):
        signals = sim.signals
        previous = [(vehicle, vehicle.inside) for vehicle in sim.vehicles]
        sim.advance(0.05)
        current_ids = {vehicle.identifier for vehicle in sim.vehicles}
        batch = sim.observations()
        for access, summary in batch.traffic.items():
            camera = sim.observation_source.cameras[access]
            for detection in summary.detections:
                if detection.state != "detenido":
                    continue
                lane = sim.lane_vehicles(access, detection.lane)
                for vehicle, leader in pairwise(lane):
                    if (
                        vehicle.speed <= 0.5
                        and not vehicle.inside
                        and not vehicle.exiting
                        and not leader.inside
                        and not leader.exiting
                        and camera.track_for(vehicle.identifier) == detection.track_id
                    ):
                        assert detection.plate == vehicle.plate
                        assert vehicle.position + vehicle.length / 2 < 488
                        queued.add(vehicle.identifier)
        for vehicle, was_inside in previous:
            if (
                vehicle.identifier in queued
                and vehicle.inside
                and not was_inside
                and signals[vehicle.access] is SignalState.GREEN
            ):
                entered_on_green.add(vehicle.identifier)
            if vehicle.identifier not in current_ids:
                rear = vehicle.position - vehicle.length / 2
                assert rear >= sim.config.lane_length
                if vehicle.identifier in entered_on_green:
                    completed_accesses.add(vehicle.access)
        if pedestrian in sim.pedestrians and pedestrian.walking:
            assert set(sim.signals.values()) == {SignalState.RED}
            assert not any(vehicle.inside for vehicle in sim.vehicles)
        if completed_accesses == set(Access) and pedestrian not in sim.pedestrians:
            break

    assert completed_accesses == set(Access)
    assert pedestrian not in sim.pedestrians


def test_pause_freezes_time_and_reset_restores_all_red() -> None:
    sim = Simulation(seed=7)
    sim.add_vehicle(Access.NORTH)
    sim.running = True
    sim.advance(2)
    assert abs(sim.time - 2) < 1e-9
    sim.running = False
    sim.advance(30)
    assert abs(sim.time - 2) < 1e-9
    sim.reset()
    assert sim.time == 0 and sim.phase is Phase.IDLE
    assert set(sim.signals.values()) == {SignalState.RED}


def test_vehicle_phase_never_enables_conflicting_axes() -> None:
    sim = Simulation()
    sim.load_scenario(Scenario.ALL_ACCESS)
    sim.running = True
    sim.advance(100)
    signals = sim.signals
    assert not (
        signals[Access.NORTH] is SignalState.GREEN and signals[Access.EAST] is SignalState.GREEN
    )
    assert not (
        signals[Access.SOUTH] is SignalState.GREEN and signals[Access.WEST] is SignalState.GREEN
    )
    assert sim.phase in Phase


def test_seed_reproduces_pedestrian_arrivals() -> None:
    first, second = Simulation(seed=42), Simulation(seed=42)
    for sim in (first, second):
        sim.pedestrian_rate = 60
        sim.running = True
        sim.advance(5)
    assert [(p.crossing, p.lane) for p in first.pedestrians] == [
        (p.crossing, p.lane) for p in second.pedestrians
    ]


def test_scenario_load_is_stopped_and_reproducible() -> None:
    sim = Simulation(seed=10)
    sim.load_scenario(Scenario.TWO_PEDESTRIANS)
    assert not sim.running
    assert sim.pedestrian_waiting() == 2
    assert sim.waiting(Access.SOUTH) == 1


def test_single_pedestrian_gets_service_and_admission_closes() -> None:
    sim = Simulation()
    sim.add_pedestrian(Access.NORTH)
    sim.running = True
    sim.advance(0.1)
    assert sim.phase is Phase.WALK
    sim.advance(sim.config.walk_admission + 0.1)
    assert sim.phase is Phase.WALK_CLEARANCE
    assert not any(p.walking for p in sim.pedestrians if p.wait > 0.1)


def test_continuous_pedestrian_arrivals_do_not_extend_admission() -> None:
    sim = Simulation()
    sim.pedestrian_rate = 60
    sim.add_pedestrian(Access.NORTH)
    sim.running = True
    sim.advance(sim.config.walk_admission + 0.2)
    assert sim.phase is Phase.WALK_CLEARANCE


def test_blocked_exit_holds_vehicle_before_entry_and_recovers() -> None:
    sim = Simulation(config=SimulationConfig(max_green=60))
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    sim.add_vehicle(Access.NORTH)
    sim.vehicles[0].position = sim.config.spawn_gap + 10
    sim.phase = Phase.NS_GREEN
    sim.set_exit_blocked(Access.NORTH, True)
    sim.running = True
    sim.advance(20)
    vehicle = sim.vehicles[0]
    assert not vehicle.inside
    assert vehicle.position <= sim.config.stop_position
    sim.set_exit_blocked(Access.NORTH, False)
    sim.advance(0.2)
    assert vehicle.inside


def test_yellow_clearance_waits_for_vehicles_already_inside() -> None:
    sim = Simulation()
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    sim.add_vehicle(Access.NORTH)
    start_in_camera_range(sim)
    sim.phase = Phase.NS_GREEN
    sim.running = True
    sim.advance(5)
    assert sim.vehicles[0].inside
    sim.add_vehicle(Access.EAST)
    sim.phase = Phase.NS_YELLOW
    sim.phase_time = sim.config.yellow
    sim.advance(0.1)
    assert sim.phase is Phase.CLEARANCE
    sim.advance(0.1)
    assert sim.phase is Phase.CLEARANCE
    assert any(v.inside for v in sim.vehicles)
    sim.advance(2)
    assert sim.phase is Phase.CLEARANCE
    sim.advance(2)
    assert not any(v.inside and v.access is Access.NORTH for v in sim.vehicles)
    assert not (
        any(v.inside and v.access is Access.NORTH for v in sim.vehicles)
        and any(v.inside and v.access is Access.EAST for v in sim.vehicles)
    )


def test_admission_and_vehicle_signals_are_mutually_exclusive() -> None:
    sim = Simulation()
    sim.add_pedestrian(Access.NORTH)
    sim.running = True
    sim.advance(0.1)
    assert sim.phase is Phase.WALK
    assert set(sim.signals.values()) == {SignalState.RED}
    sim.add_vehicle(Access.NORTH)
    sim.advance(0.1)
    assert not any(v.inside for v in sim.vehicles)


def test_reset_preserves_demand_settings_and_scenario_reload_is_stopped() -> None:
    sim = Simulation()
    sim.set_demand(Access.WEST, 17)
    sim.reset()
    assert sim.vehicle_rates[Access.WEST] == 17
    sim.load_scenario(Scenario.ALL_ACCESS)
    assert not sim.running and sim.time == 0
    assert all(sim.waiting(access) == 1 for access in Access)


def test_queued_vehicles_keep_safe_spacing_when_green_releases_queue() -> None:
    sim = Simulation(config=SimulationConfig(max_green=60))
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    sim.add_vehicle(Access.NORTH)
    sim.vehicles[0].position = sim.config.spawn_gap + 10
    sim.advance(0)
    sim.add_vehicle(Access.NORTH)
    sim.phase = Phase.NS_GREEN
    sim.running = True
    sim.advance(5)
    lane = sim.lane_vehicles(Access.NORTH, 0)
    assert len(lane) == 2
    assert lane[1].position - lane[0].position >= sim.config.spawn_gap


def test_full_inbound_lanes_do_not_multiply_deferred_arrivals() -> None:
    sim = Simulation()
    sim.vehicle_rates = dict.fromkeys(Access, 0.0)
    sim.pedestrian_rate = 0
    sim.add_vehicle(Access.NORTH)
    sim.add_vehicle(Access.NORTH)
    assert not sim.add_vehicle(Access.NORTH)
    assert sim.requested[Access.NORTH] == 1

    sim.phase = Phase.NS_GREEN
    sim.set_exit_blocked(Access.NORTH, True)
    sim.running = True
    sim.advance(0.5)

    assert sim.requested[Access.NORTH] == 1


@pytest.mark.parametrize("access", tuple(Access))
@pytest.mark.parametrize("step", (0.05, 0.2, 1.0))
def test_stopped_vehicle_body_remains_before_crosswalk(access: Access, step: float) -> None:
    sim = quiet_rates(Simulation(config=SimulationConfig(min_green=100, demand_persistence=100)))
    sim.add_vehicle(access)
    sim.phase = Phase.EW_GREEN if access in (Access.NORTH, Access.SOUTH) else Phase.NS_GREEN
    sim.running = True

    sim.advance(12, step=step)

    vehicle = sim.vehicles[0]
    line_position = sim.config.approach_extent - sim.config.stop_line_distance
    front_position = vehicle.position + sim.config.vehicle_length / 2
    assert not vehicle.inside
    assert vehicle.position == pytest.approx(sim.config.stop_position)
    assert line_position - front_position >= sim.config.stop_margin
    assert sim.signals[access] is SignalState.RED


def test_queued_vehicle_body_spacing_uses_length_plus_clear_gap() -> None:
    sim = quiet_rates(Simulation(config=SimulationConfig(min_green=100, demand_persistence=100)))
    sim.vehicles.append(Vehicle(1, Access.NORTH, 0, position=130))
    sim.vehicles.append(Vehicle(2, Access.NORTH, 0, position=20))
    sim.phase = Phase.EW_GREEN
    sim.running = True

    sim.advance(12, step=0.2)

    leader, follower = sim.lane_vehicles(Access.NORTH, 0)[::-1]
    body_gap = leader.position - follower.position - sim.config.vehicle_length
    assert body_gap >= sim.config.spawn_gap - sim.config.vehicle_length
    assert follower.position + sim.config.vehicle_length / 2 < (
        sim.config.approach_extent - sim.config.stop_line_distance
    )


def test_large_opposing_demand_requests_change_after_minimum_green() -> None:
    config = SimulationConfig(
        min_green=2,
        max_green=20,
        empty_interval=20,
        demand_persistence=0.2,
    )
    sim = quiet_rates(Simulation(config=config))
    sim.add_vehicle(Access.NORTH)
    for index in range(6):
        sim.vehicles.append(Vehicle(index + 2, Access.EAST, index % 2, position=index // 2 * 40))
    start_in_camera_range(sim)
    sim.phase = Phase.NS_GREEN
    sim.running = True

    sim.advance(2.3)

    assert sim.phase is Phase.NS_YELLOW
    assert "mayor demanda Oriente–Occidente" in sim.decision


def test_continuous_demand_gets_turns_on_both_axes() -> None:
    config = SimulationConfig(
        min_green=3,
        max_green=6,
        yellow=0.8,
        vehicle_clearance=0.3,
        empty_interval=1,
        demand_persistence=0.3,
        vehicle_acceleration=100,
        vehicle_speed=130,
    )
    sim = quiet_rates(Simulation(config=config))
    sim.vehicle_rates = dict.fromkeys(Access, 18.0)
    sim.running = True
    seen_green: set[Phase] = set()

    for _ in range(900):
        sim.advance(0.05)
        if sim.phase in (Phase.NS_GREEN, Phase.EW_GREEN):
            seen_green.add(sim.phase)
        signals = sim.signals
        assert not (
            signals[Access.NORTH] is SignalState.GREEN and signals[Access.EAST] is SignalState.GREEN
        )

    assert seen_green == {Phase.NS_GREEN, Phase.EW_GREEN}
    served_axes = set(sim._served)
    assert served_axes == {"ns", "ew"}


def test_similar_demand_alternates_instead_of_blocking_one_axis() -> None:
    config = SimulationConfig(
        min_green=2,
        max_green=7,
        yellow=0.5,
        vehicle_clearance=0.2,
        demand_persistence=0.2,
        vehicle_acceleration=120,
        vehicle_speed=120,
    )
    sim = quiet_rates(Simulation(config=config))
    for access in Access:
        sim.vehicles.append(Vehicle(len(sim.vehicles) + 1, access, 0, position=200, speed=70))
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True

    sim.advance(60)

    assert {"ns", "ew"} <= set(sim._served)


def test_one_opposing_vehicle_is_served_during_continuous_active_arrivals() -> None:
    config = SimulationConfig(
        min_green=2,
        max_green=6,
        yellow=0.5,
        vehicle_clearance=0.2,
        demand_persistence=0.2,
        vehicle_acceleration=100,
        vehicle_speed=120,
        max_vehicle_wait=12,
    )
    sim = quiet_rates(Simulation(config=config))
    sim.vehicle_rates[Access.NORTH] = 60
    sim.add_vehicle(Access.EAST)
    sim.vehicles[0].position = 200
    sim.vehicles[0].speed = 60
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True
    served_axes: set[str] = set()

    for _ in range(900):
        sim.advance(0.05)
        served_axes.update(sim._served)

    assert "ew" in served_axes


def test_wait_maximum_precedes_a_much_larger_active_queue() -> None:
    config = SimulationConfig(
        min_green=1,
        max_green=30,
        demand_switch_margin=100,
        demand_persistence=100,
        max_vehicle_wait=5,
    )
    sim = quiet_rates(Simulation(config=config))
    for _ in range(8):
        sim.add_vehicle(Access.NORTH)
    sim.add_vehicle(Access.EAST)
    start_in_camera_range(sim)
    sim.vehicles[-1].wait = 5
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True

    sim.advance(1.2)

    assert sim.phase is Phase.NS_YELLOW
    assert "espera máxima" in sim.decision


def test_exiting_vehicles_are_not_pending_demand_or_wait() -> None:
    sim = quiet_rates(Simulation())
    sim.vehicles.append(Vehicle(1, Access.EAST, 0, exiting=True, wait=90))

    assert sim.axis_demand("ew") == 0
    assert sim.axis_wait("ew") == 0
    assert sim.exiting_vehicles((Access.EAST, Access.WEST)) == 1


def test_exiting_active_vehicle_does_not_hold_green_against_opposing_queue() -> None:
    config = SimulationConfig(
        min_green=1,
        max_green=100,
        empty_interval=0.1,
        demand_persistence=0.1,
    )
    sim = quiet_rates(Simulation(config=config))
    sim.vehicles.append(Vehicle(1, Access.NORTH, 0, exiting=True, position=700))
    sim.add_vehicle(Access.EAST)
    start_in_camera_range(sim)
    sim.phase = Phase.NS_GREEN
    sim.phase_time = config.min_green
    sim._last_axis = "ns"
    sim._empty_time = config.empty_interval
    sim.running = True

    sim.advance(0.15)

    assert sim.phase is Phase.NS_YELLOW
    assert "carril activo sin demanda" in sim.decision


def test_active_green_can_remain_when_there_is_no_incompatible_demand() -> None:
    config = SimulationConfig(min_green=1, max_green=3)
    sim = quiet_rates(Simulation(config=config))
    sim.add_vehicle(Access.NORTH)
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True

    sim.advance(20)

    assert sim.phase is Phase.NS_GREEN


def test_arrivals_do_not_reset_elapsed_green_maximum() -> None:
    config = SimulationConfig(
        min_green=2,
        max_green=5,
        yellow=0.5,
        vehicle_clearance=0.2,
        demand_persistence=100,
        demand_switch_margin=100,
        vehicle_acceleration=1,
        vehicle_speed=5,
    )
    sim = quiet_rates(Simulation(config=config))
    for _ in range(8):
        sim.add_vehicle(Access.NORTH)
    sim.add_vehicle(Access.EAST)
    start_in_camera_range(sim)
    sim.vehicle_rates[Access.NORTH] = 60
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True

    sim.advance(5.2)

    assert sim.phase is Phase.NS_YELLOW
    assert "Verde máximo" in sim.decision
    assert sim.green_elapsed >= config.max_green


def test_yellow_then_clearance_holds_opposing_phase_until_conflict_empty() -> None:
    config = SimulationConfig(
        min_green=1,
        max_green=20,
        yellow=1,
        vehicle_clearance=0.5,
        demand_persistence=0.1,
    )
    sim = quiet_rates(Simulation(config=config))
    sim.vehicles.append(Vehicle(1, Access.NORTH, 0, position=220, speed=60))
    sim.add_vehicle(Access.EAST)
    start_in_camera_range(sim)
    sim.phase = Phase.NS_GREEN
    sim._last_axis = "ns"
    sim.running = True

    sim.advance(1.2)
    assert sim.phase is Phase.NS_YELLOW
    assert sim.signals[Access.NORTH] is SignalState.YELLOW
    assert sim.signals[Access.EAST] is SignalState.RED
    sim.advance(config.yellow + 0.1)
    assert sim.phase is Phase.CLEARANCE
    assert sim.signals[Access.EAST] is SignalState.RED
    assert any(vehicle.inside for vehicle in sim.vehicles)

    sim.advance(10)

    assert sim.phase is Phase.EW_GREEN
    assert not any(
        vehicle.inside and vehicle.access in (Access.NORTH, Access.SOUTH)
        for vehicle in sim.vehicles
    )
    assert sim.signals[Access.NORTH] is SignalState.RED
    assert sim.signals[Access.EAST] is SignalState.GREEN


def test_committed_vehicle_can_enter_during_red_clearance_before_next_phase() -> None:
    config = SimulationConfig(
        yellow=0.05,
        vehicle_clearance=0.1,
        vehicle_acceleration=100,
        vehicle_speed=100,
    )
    sim = quiet_rates(Simulation(config=config))
    committed = Vehicle(1, Access.NORTH, 0, position=200, speed=100)
    sim.vehicles.append(committed)
    sim.add_vehicle(Access.EAST)
    start_in_camera_range(sim)
    sim.phase = Phase.NS_YELLOW
    sim._last_axis = "ns"
    sim._pending_phase = Phase.EW_GREEN
    sim.running = True

    sim.advance(0.1)

    assert sim.phase is Phase.CLEARANCE
    assert committed.committed or committed.inside
    assert sim.signals[Access.EAST] is SignalState.RED

    sim.advance(10)

    assert sim.phase is Phase.EW_GREEN
    assert not committed.inside
