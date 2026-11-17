import shutil
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from sigma_vial.domain.plate_reading import OCRReading, PlateConsensus
from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Simulation
from sigma_vial.infrastructure.plate_ocr import TesseractPlateReader, tesseract_executable
from sigma_vial.presentation.plate_camera import image_png, rear_camera


def test_consensus_requires_distinct_times_resets_errors_and_is_bounded():
    consensus = PlateConsensus(max_tracks=2)
    for timestamp in (0, 0.1):
        assert not consensus.observe(
            "one", OCRReading(timestamp, "ABC123", 90, "Legible")
        ).confirmed
    assert not consensus.observe("one", OCRReading(0.1, "ABC123", 90, "Legible")).confirmed
    assert consensus.observe("one", OCRReading(0.2, "ABC123", 90, "Legible")).confirmed == "ABC123"
    assert not consensus.observe("one", OCRReading(0.3, "XYZ987", 90, "Legible")).confirmed
    assert not consensus.observe("one", OCRReading(0.4)).confirmed
    for track in ("two", "three"):
        consensus.observe(track, OCRReading(1, "ABC12D", 90, "Legible"))
    assert len(consensus.tracks) == 2
    consensus.observe("new", OCRReading(20))
    assert len(consensus.tracks) == 1


def test_real_ocr_only_reads_pixels_even_if_internal_plate_differs(qapp):
    exe = tesseract_executable()
    if not Path(exe).is_file() and not shutil.which(exe):
        pytest.skip("Tesseract externo no instalado; evaluación real pendiente en este host")
    sim = Simulation()
    sim.add_vehicle(Access.NORTH)
    vehicle = sim.vehicles[0]
    vehicle.plate = "ABC123"
    picture = rear_camera(vehicle, 0)
    vehicle.plate = "XYZ987"
    reader = TesseractPlateReader()
    assert reader.read(image_png(picture.crop()), 0).text == "ABC123"
    second = rear_camera(vehicle, 0.1)
    assert reader.read(image_png(second.crop()), 0.1).text == "XYZ987"
    blank = QImage(250, 65, QImage.Format.Format_RGB888)
    blank.fill(QColor("white"))
    assert reader.read(image_png(blank), 0.2).text == ""
    assert reader.read(b"", 0.3).status == "Sin lectura"
    assert reader.read(image_png(rear_camera(None, 0.4).image), 0.4).text == ""
