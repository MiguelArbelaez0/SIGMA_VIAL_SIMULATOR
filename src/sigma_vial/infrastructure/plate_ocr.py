"""OCR real local: solo bytes de imagen, tiempo y configuración; sin metadatos."""

import csv
import io
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sigma_vial.domain.plate_reading import PLATE_PATTERN, OCRReading


@dataclass(frozen=True)
class OCRConfig:
    executable: str = ""
    tessdata: str = ""
    min_confidence: float = 40
    timeout: float = 4


def tesseract_executable():
    override = os.environ.get("SIGMA_VIAL_TESSERACT")
    if override:
        return override
    located = shutil.which("tesseract")
    if located:
        return located
    for base in (
        os.environ.get("PROGRAMFILES", "C:/Program Files"),
        str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SIGMA SOFTWARE SOLUTIONS"),
    ):
        candidate = Path(base) / "Tesseract-OCR/tesseract.exe"
        if candidate.is_file():
            return str(candidate)
    return "tesseract"


class TesseractPlateReader:
    def __init__(self, config: OCRConfig | None = None):
        self.config = config or OCRConfig()

    def read(self, png: bytes, timestamp: float) -> OCRReading:
        if not png:
            return OCRReading(timestamp)
        command = [
            self.config.executable or tesseract_executable(),
            "stdin",
            "stdout",
            "-l",
            "eng",
            "--oem",
            "1",
            "--psm",
            "7",
        ]
        if self.config.tessdata:
            command += ["--tessdata-dir", self.config.tessdata]
        command += ["-c", "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "tsv"]
        try:
            result = subprocess.run(
                command,
                input=png,
                capture_output=True,
                timeout=self.config.timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"OCR local no disponible: {exc}") from exc
        if result.returncode:
            raise RuntimeError(
                f"Tesseract salida {result.returncode}: "
                + result.stderr.decode("utf-8", errors="replace")[:400]
            )
        rows = csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t")
        words = [
            (r["text"].strip(), float(r["conf"]))
            for r in rows
            if r.get("level") == "5" and r.get("text", "").strip()
        ]
        raw = " ".join(word for word, _ in words)
        text = "".join(raw.upper().split())
        confidence = min((conf for _, conf in words), default=0)
        valid = bool(PLATE_PATTERN.fullmatch(text)) and confidence >= self.config.min_confidence
        return OCRReading(
            timestamp, text if valid else "", confidence, "Legible" if valid else "No legible", raw
        )
