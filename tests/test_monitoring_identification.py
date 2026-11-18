import shutil
from concurrent.futures import Future
from pathlib import Path

import pytest

from sigma_vial.domain.plate_reading import OCRReading
from sigma_vial.domain.scenario import Access
from sigma_vial.infrastructure.plate_ocr import tesseract_executable
from sigma_vial.presentation.main_window import MainWindow
from sigma_vial.presentation.monitoring import MonitoringCenter
from sigma_vial.presentation.plate_camera import rear_camera


def test_old_ocr_result_is_ignored_on_world_reset(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.simulation.add_vehicle(Access.NORTH)
    monitor = MonitoringCenter(window)
    monitor.timer.stop()
    monitor.mode.setCurrentIndex(3)
    old = Future()
    monitor.ocr_snapshot = rear_camera(window.simulation.vehicles[0], 50)
    monitor.ocr_submitted_generation = monitor.generation
    monitor.ocr_future = old
    window.simulation.reset()
    monitor.refresh()
    old.set_result(OCRReading(50, "ABC123", 90, "Legible"))
    monitor.refresh()
    assert not monitor.identification.consensus.tracks
    assert not monitor.identification.events
    from dataclasses import replace

    for timestamp in (0.1, 0.2, 0.3):
        fresh = Future()
        fresh.set_result(OCRReading(timestamp, "XYZ987", 90, "Legible"))
        monitor.ocr_future = fresh
        monitor.ocr_submitted_generation = monitor.generation
        monitor.ocr_snapshot = replace(monitor.ocr_snapshot, timestamp=timestamp, track="new")
        monitor.refresh()
    assert len(monitor.identification.events) == 1
    assert monitor.identification.events[0].plate == "XYZ987"
    assert monitor.identification.events[0].timestamp == 0.3
    monitor.close()


def test_visible_real_ocr_registry_unknown_and_failure_does_not_stop_traffic(qtbot):
    exe = tesseract_executable()
    if not Path(exe).is_file() and not shutil.which(exe):
        pytest.skip("Tesseract externo no instalado")
    window = MainWindow()
    qtbot.addWidget(window)
    window.simulation.automatic_generation = False
    window.simulation.add_vehicle(Access.NORTH)
    vehicle = window.simulation.vehicles[0]
    plate = vehicle.plate
    monitor = MonitoringCenter(window)
    monitor.show()
    monitor.mode.setCurrentIndex(3)
    qtbot.waitUntil(lambda: monitor.plate_events.count() == 1, timeout=10000)
    assert plate in monitor.plate_info.text()
    assert "Ficha recuperada del registro" in monitor.plate_record.text()
    qtbot.wait(500)
    assert monitor.plate_events.count() == 1
    vehicle.plate = "ABC123"  # renderer only; record remains the original synthetic plate
    monitor.set_plate_image(rear_camera(vehicle, 0).crop())
    qtbot.waitUntil(lambda: monitor.plate_events.count() == 1, timeout=10000)
    assert "Placa leída, vehículo no registrado" in monitor.plate_record.text()
    from PySide6.QtGui import QColor, QImage

    blank = QImage(250, 65, QImage.Format.Format_RGB888)
    blank.fill(QColor("white"))
    monitor.set_plate_image(blank)
    qtbot.waitUntil(lambda: "No legible" in monitor.plate_info.text(), timeout=10000)
    assert monitor.plate_events.count() == 0
    assert "Sin ficha" in monitor.plate_record.text()
    window.simulation.running = True
    window.simulation.advance(2)
    assert window.simulation.time > 1.9
    assert window.simulation.vehicles[0].position > 0
    monitor.close()


def test_ocr_worker_failure_does_not_affect_traffic_control(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.simulation.add_vehicle(Access.NORTH)
    monitor = MonitoringCenter(window)
    monitor.timer.stop()
    monitor.mode.setCurrentIndex(3)
    monitor.ocr_snapshot = rear_camera(window.simulation.vehicles[0], 0.1, "rear-north")
    monitor.ocr_submitted_generation = monitor.generation
    failed = Future()
    failed.set_exception(RuntimeError("OCR unavailable"))
    monitor.ocr_future = failed
    monitor.refresh_plate_camera()
    assert "OCR no disponible" in monitor.plate_info.text()
    assert not monitor.identification.events
    assert not monitor.identification.consensus.tracks["rear-north:rear-north-vehicle-1"].confirmed
    window.simulation.automatic_generation = False
    window.simulation.running = True
    window.simulation.advance(5)
    assert window.simulation.time > 4.9
    assert window.simulation.vehicles[0].position > 0
    monitor.close()
