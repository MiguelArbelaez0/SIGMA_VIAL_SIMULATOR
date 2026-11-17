from sigma_vial.application.identification import IdentificationSession
from sigma_vial.domain.plate_reading import OCRReading
from sigma_vial.domain.registration import RegisteredVehicle
from sigma_vial.infrastructure.vehicle_registry import SQLiteVehicleRegistry


def test_only_confirmed_text_queries_exact_registry_and_deduplicates(tmp_path):
    registry = SQLiteVehicleRegistry(tmp_path / "registry.sqlite3")
    row = RegisteredVehicle("ABC123", "COMPACT", "SIGMA", "Prueba", "#e66b4e", 28, 16)
    registry.reserve(row)
    calls = []
    original = registry.find
    registry.find = lambda text: (calls.append(text), original(text))[1]
    identification = IdentificationSession(registry)
    for t in (0, 0.1):
        result = identification.observe("rear", "track1", OCRReading(t, "ABC123", 90, "Legible"))
        assert result.event is None
    assert not calls
    for t in (0.2, 0.3, 0.4):
        result = identification.observe("rear", "track1", OCRReading(t, "ABC123", 90, "Legible"))
        assert result.event.record == row
    assert calls == ["ABC123"] and len(identification.events) == 1
    assert result.event.message == "Ficha recuperada del registro"
    for t in (0.5, 0.6, 0.7):
        result = identification.observe("rear", "track2", OCRReading(t, "XYZ987", 90, "Legible"))
    assert result.event.record is None
    assert result.event.message == "Placa leída, vehículo no registrado"
    assert calls == ["ABC123", "XYZ987"]
    result = identification.observe("rear", "track1", OCRReading(0.8))
    assert result.event is None
    assert calls == ["ABC123", "XYZ987"]
    reset = IdentificationSession(registry)
    assert not reset.events and not reset.consensus.tracks
    assert registry.find("ABC123") == row


def test_errors_and_camera_track_isolation(tmp_path):
    identification = IdentificationSession(SQLiteVehicleRegistry(tmp_path / "registry.sqlite3"))
    for timestamp, text in enumerate(("ABC123", "XYZ987", "ABC123", "XYZ987")):
        assert (
            identification.observe("a", "same", OCRReading(timestamp, text, 90, "Legible")).event
            is None
        )
    assert identification.observe("b", "same", OCRReading(4, "XYZ987", 90, "Legible")).event is None
    assert not identification.events
