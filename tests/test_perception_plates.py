"""Contrato de percepción, fallos y placas sintéticas reproducibles."""

import re

import pytest

from sigma_vial.domain.perception import (
    ObservationBatch,
    SensorStatus,
    TrafficSummary,
    VirtualCamera,
)
from sigma_vial.domain.plates import PlateService
from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Phase, Simulation, Vehicle, VehicleType


def test_plate_service_session_uniqueness_and_seed():
    first, second = PlateService(42), PlateService(42)
    plates = [first.issue(i % 2 == 0) for i in range(5000)]
    assert len(set(plates)) == 5000
    assert plates == [second.issue(i % 2 == 0) for i in range(5000)]
    for i, plate in enumerate(plates):
        assert re.fullmatch(r"[A-Z]{3}[0-9]{2}[A-Z]" if i % 2 == 0 else r"[A-Z]{3}[0-9]{3}", plate)


@pytest.mark.parametrize("kind", tuple(VehicleType))
def test_manual_automatic_plates_stable_and_reproducible(kind):
    histories = []
    for _ in range(2):
        sim = Simulation(seed=71)
        sim.selected_vehicle_type = kind
        sim.add_vehicle(Access.NORTH)
        first = sim.vehicles[0]
        plate = first.plate
        sim.running = True
        sim.advance(20)
        assert first.plate == plate
        plates = [v.plate for v in sim.vehicles]
        assert all(plates)
        pattern = (
            r"[A-Z]{3}[0-9]{2}[A-Z]" if kind is VehicleType.MOTORCYCLE else r"[A-Z]{3}[0-9]{3}"
        )
        assert all(re.fullmatch(pattern, plate) for plate in plates)
        assert len(plates) == len(set(plates))
        assert all(p in sim.plates.used for p in plates)
        assert plate in sim.plates.used
        histories.append((plate, plates))
    assert histories[0] == histories[1]


def test_camera_coverage_tracks_count_and_expiry():
    camera = VirtualCamera(Access.NORTH, end=270, count_line=250)
    car = Vehicle(4, Access.NORTH, 0, position=200)
    outside = Vehicle(5, Access.NORTH, 1, position=300)
    other = Vehicle(6, Access.EAST, 0, position=100)
    result = camera.read(0, [car, outside, other])
    assert len(result.detections) == 1
    track = result.detections[0].track_id
    assert track != str(car.identifier)
    assert result.queue == result.demand == 1
    assert result.lane_demand == {0: 1, 1: 0}
    car.position = 260
    car.inside = True
    result = camera.read(1, [car])
    assert result.detections[0].track_id == track
    assert result.passage_count == 1
    assert result.demand == 0
    assert camera.read(2, [car]).passage_count == 1
    assert not camera.read(3, []).detections
    assert camera.read(4, []).passage_count == 1


@pytest.mark.parametrize("kind", tuple(VehicleType))
def test_sensor_classification_without_readable_plate(kind):
    camera = VirtualCamera(Access.SOUTH)
    car = Vehicle(1, Access.SOUTH, 1, kind=kind, plate="")
    result = camera.read(0, [car])
    assert result.demand == 1
    assert result.detections[0].vehicle_type == kind.name
    assert result.detections[0].provenance == "Simulada"
    assert result.detections[0].plate_source == "Lectura simulada"


@pytest.mark.parametrize("failure", (SensorStatus.DISCONNECTED, SensorStatus.NO_DATA))
def test_sensor_disconnect_recovery_and_clock_pause(failure):
    sim = Simulation()
    sim.add_vehicle(Access.NORTH)
    sim.vehicles[0].position = sim.observation_source.cameras[Access.NORTH].start
    sim.running = True
    sim.advance(2)
    camera = sim.observation_source.cameras[Access.EAST]
    camera.status = failure
    sim.advance(10)
    assert sim.phase is Phase.CLEARANCE
    sim.running = False
    before = sim.observations()
    sim.advance(5)
    assert sim.observations() == before
    camera.status = SensorStatus.AVAILABLE
    sim.running = True
    sim.advance(3)
    assert sim.phase is not Phase.CLEARANCE
    sim.reset()
    assert sim.time == 0
    assert not sim.plates.used
    assert all(c.last_result is None for c in sim.observation_source.cameras.values())


class FixedSource:
    def __init__(self, batch):
        self.batch = batch

    def read(self, time, vehicles, pedestrians):
        return self.batch


def test_controller_uses_contract_not_hidden_world_and_rejects_stale():
    sim = Simulation()
    traffic = {a: TrafficSummary(a, 0, SensorStatus.AVAILABLE) for a in Access}
    batch = ObservationBatch(traffic, (), 0)
    sim.observation_source = FixedSource(batch)
    sim.add_vehicle(Access.NORTH)
    sim.running = True
    sim.advance(0.2)
    assert sim.phase is Phase.IDLE
    sim.phase = Phase.NS_GREEN
    sim.advance(5)
    assert sim.phase in (Phase.NS_YELLOW, Phase.CLEARANCE)
    assert "Respaldo" in sim.decision


def test_sampling_interval_holds_last_reading_until_next_sample():
    camera = VirtualCamera(Access.NORTH, interval=0.5)
    car = Vehicle(1, Access.NORTH, 0)
    initial = camera.read(0, [car])
    assert camera.read(0.2, []) is initial
    assert not camera.read(0.5, []).detections


def test_scenarios_share_session_plate_service():
    from sigma_vial.domain.simulation import Scenario

    for scenario in Scenario:
        sim = Simulation(seed=29)
        sim.load_scenario(scenario)
        initial = {v.plate for v in sim.vehicles}
        assert len(initial) == len(sim.vehicles)
        sim.running = True
        sim.advance(30)
        assert initial <= sim.plates.used
        assert len({v.plate for v in sim.vehicles}) == len(sim.vehicles)


def test_contract_detection_can_request_phase_without_any_world_vehicle():
    from sigma_vial.domain.perception import Detection

    sim = Simulation()
    detection = Detection(
        "external-track",
        "external-camera",
        Access.EAST,
        0,
        "COMPACT",
        200,
        0,
        "detenido",
        0,
        15,
        None,
    )
    traffic = {a: TrafficSummary(a, 0, SensorStatus.AVAILABLE) for a in Access}
    traffic[Access.EAST] = TrafficSummary(Access.EAST, 0, SensorStatus.AVAILABLE, (detection,))
    sim.observation_source = FixedSource(ObservationBatch(traffic, (), 0))
    sim.running = True
    sim.advance(0.1)
    assert sim.phase is Phase.EW_GREEN
    assert not sim.vehicles


def test_missing_camera_holds_red_without_crashing_summary():
    sim = Simulation()
    sim.observation_source = FixedSource(ObservationBatch({}, (), 0))
    sim.running = True
    sim.advance(0.1)
    assert sim.phase is Phase.IDLE
    assert sim.axis_demand("ns") == 0
    assert sim.axis_wait("ew") == 0
    assert "Respaldo" in sim.decision
