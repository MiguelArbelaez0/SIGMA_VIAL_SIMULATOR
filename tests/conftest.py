"""Nunca usar el registro operativo durante pruebas."""

import pytest


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("SIGMA_VIAL_REGISTRY", str(tmp_path / "vehicles.sqlite3"))
