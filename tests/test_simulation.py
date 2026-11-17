"""Pruebas deterministas del motor independiente de Qt."""

from sigma_vial.domain.scenario import Access, SignalState
from sigma_vial.domain.simulation import Phase, Scenario, Simulation, SimulationConfig


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
    sim.add_vehicle(Access.NORTH)
    sim.vehicles[0].position = sim.config.spawn_gap + 10
    sim.phase = Phase.NS_GREEN
    sim.set_exit_blocked(Access.NORTH, True)
    sim.running = True
    sim.advance(20)
    vehicle = sim.vehicles[0]
    assert not vehicle.inside
    assert vehicle.position <= sim.config.lane_length - sim.config.intersection_half
    sim.set_exit_blocked(Access.NORTH, False)
    sim.advance(0.2)
    assert vehicle.inside


def test_yellow_clearance_waits_for_vehicles_already_inside() -> None:
    sim = Simulation()
    sim.add_vehicle(Access.NORTH)
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
    assert not any(v.inside for v in sim.vehicles)


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
