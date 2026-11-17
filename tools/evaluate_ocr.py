"""Evaluación del motor OCR real sobre imágenes sintéticas con texto esperado."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from sigma_vial.domain.catalog import VehicleType
from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Simulation
from sigma_vial.infrastructure.plate_ocr import TesseractPlateReader, tesseract_executable
from sigma_vial.presentation.plate_camera import image_png, rear_camera


def main():
    app = QApplication.instance() or QApplication([])
    assert app
    reader = TesseractPlateReader()
    simulation = Simulation(seed=31)
    cases = []
    out = Path("docs/ocr-evaluation")
    out.mkdir(parents=True, exist_ok=True)
    for kind in VehicleType:
        simulation.vehicles.clear()
        simulation.selected_vehicle_type = kind
        simulation.add_vehicle(Access.NORTH)
        vehicle = simulation.vehicles[0]
        for position in (0, 230):
            vehicle.position = position
            camera = rear_camera(vehicle, position / 100)
            png = image_png(camera.crop())
            filename = f"{kind.name.lower()}-{position}.png"
            (out / filename).write_bytes(png)
            start = time.perf_counter()
            result = reader.read(png, camera.timestamp)
            cases.append(
                dict(
                    image=filename,
                    expected=vehicle.plate,
                    actual=result.text,
                    raw=result.raw,
                    confidence=result.confidence,
                    status=result.status,
                    exact=result.text == vehicle.plate,
                    milliseconds=round((time.perf_counter() - start) * 1000, 2),
                )
            )
    for name, image in (
        ("blank", QImage(250, 65, QImage.Format.Format_RGB888)),
        ("no-vehicle", rear_camera(None, 0).image),
    ):
        if name == "blank":
            image.fill(QColor("white"))
        png = image_png(image)
        (out / f"{name}.png").write_bytes(png)
        result = reader.read(png, 0)
        cases.append(
            dict(
                image=f"{name}.png",
                expected="",
                actual=result.text,
                raw=result.raw,
                confidence=result.confidence,
                status=result.status,
                exact=result.text == "",
            )
        )
    exe = Path(tesseract_executable())
    model = exe.parent / "tessdata/eng.traineddata"
    report = dict(
        scope="Motor real sobre recortes sintéticos. NO precisión de cámaras reales.",
        version=subprocess.run(
            [str(exe), "--version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
        exact=sum(c["exact"] for c in cases),
        total=len(cases),
        cases=cases,
    )
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
