import os
import subprocess
import sys

from sigma_vial.domain.catalog import VehicleType
from sigma_vial.domain.registration import RegisteredVehicle
from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Simulation
from sigma_vial.infrastructure.vehicle_registry import SQLiteVehicleRegistry


def test_registry_persistence_collision_and_reset(tmp_path):
    path = tmp_path / "registry.sqlite3"
    registry = SQLiteVehicleRegistry(path)
    previous = set()
    for _ in range(2):
        sim = Simulation(registry=SQLiteVehicleRegistry(path))
        for kind in VehicleType:
            sim.vehicles.clear()
            sim.selected_vehicle_type = kind
            assert sim.add_vehicle(Access.NORTH)
            vehicle = sim.vehicles[0]
            assert vehicle.plate not in previous
            previous.add(vehicle.plate)
            row = registry.find(vehicle.plate)
            assert (row.color, row.length, row.width) == (
                vehicle.color,
                vehicle.length,
                vehicle.width,
            )
            assert row.vehicle_type == kind.name
        sim.reset()
        assert all(registry.find(p) for p in previous)
        sim.add_vehicle(Access.NORTH)
        assert sim.vehicles[0].plate not in previous
        previous.add(sim.vehicles[0].plate)
    row = registry.find(next(iter(previous)))
    assert not registry.reserve(row)
    assert registry.find(row.plate.lower()) is None
    assert registry.find("' OR 1=1 --") is None
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from sigma_vial.infrastructure.vehicle_registry import SQLiteVehicleRegistry; "
            "import sys; print(SQLiteVehicleRegistry(sys.argv[1]).find(sys.argv[2]).plate)",
            str(path),
            row.plate,
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == row.plate


def test_unique_constraint_survives_separate_connections(tmp_path):
    path = tmp_path / "registry.sqlite3"
    row = RegisteredVehicle("ABC123", "COMPACT", "SIGMA", "Prueba", "#ffffff", 28, 16)
    assert SQLiteVehicleRegistry(path).reserve(row)
    assert not SQLiteVehicleRegistry(path).reserve(row)
