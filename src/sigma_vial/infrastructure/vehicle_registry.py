"""Registro SQLite persistente de datos sintéticos; fuera del repositorio."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from sigma_vial.domain.registration import RegisteredVehicle


def registry_path() -> Path:
    override = os.environ.get("SIGMA_VIAL_REGISTRY")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    return base / "SIGMA SOFTWARE SOLUTIONS" / "SIGMA VIAL" / "vehicles.sqlite3"


class SQLiteVehicleRegistry:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS vehicles (
                plate TEXT PRIMARY KEY NOT NULL,
                vehicle_type TEXT NOT NULL, brand TEXT NOT NULL, model TEXT NOT NULL,
                color TEXT NOT NULL, length REAL NOT NULL CHECK(length > 0),
                width REAL NOT NULL CHECK(width > 0)
            )""")

    def _connect(self):
        # Each operation owns its connection; usable from a future identification worker.
        return closing_connection(self.path)

    def reserve(self, vehicle: RegisteredVehicle) -> bool:
        from dataclasses import astuple

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(plate) DO NOTHING",
                astuple(vehicle),
            )
            return cursor.rowcount == 1

    def find(self, plate: str) -> RegisteredVehicle | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plate, vehicle_type, brand, model, color, length, width "
                "FROM vehicles WHERE plate = ? COLLATE BINARY",
                (plate,),
            ).fetchone()
        return RegisteredVehicle(*row) if row else None


@contextmanager
def closing_connection(path):
    connection = sqlite3.connect(path, timeout=10)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
