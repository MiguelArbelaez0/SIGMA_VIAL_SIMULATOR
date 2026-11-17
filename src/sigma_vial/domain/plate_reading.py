"""Confirmación temporal de texto OCR, sin acceso al mundo ni al registro."""

import re
from dataclasses import dataclass

PLATE_PATTERN = re.compile(r"(?:[A-Z]{3}[0-9]{3}|[A-Z]{3}[0-9]{2}[A-Z])\Z")


@dataclass(frozen=True)
class OCRReading:
    timestamp: float
    text: str = ""
    confidence: float = 0
    status: str = "Sin lectura"
    raw: str = ""


@dataclass
class PlateEvidence:
    provisional: str = ""
    confirmed: str = ""
    hits: int = 0
    last_seen: float = -1
    status: str = "Sin lectura"


class PlateConsensus:
    def __init__(self, required=3, retention=10.0, max_tracks=256):
        self.required = required
        self.retention = retention
        self.max_tracks = max_tracks
        self.tracks: dict[str, PlateEvidence] = {}

    def observe(self, track: str, reading: OCRReading) -> PlateEvidence:
        self.tracks = {
            k: v
            for k, v in self.tracks.items()
            if reading.timestamp - v.last_seen <= self.retention
        }
        if track not in self.tracks and len(self.tracks) >= self.max_tracks:
            del self.tracks[min(self.tracks, key=lambda k: self.tracks[k].last_seen)]
        evidence = self.tracks.setdefault(track, PlateEvidence())
        if reading.timestamp <= evidence.last_seen:
            return evidence
        evidence.last_seen = reading.timestamp
        evidence.status = reading.status
        if reading.status != "Legible" or not PLATE_PATTERN.fullmatch(reading.text):
            evidence.hits = 0
            evidence.provisional = ""
            evidence.confirmed = ""
            return evidence
        if evidence.provisional == reading.text:
            evidence.hits += 1
        else:
            evidence.provisional = reading.text
            evidence.hits = 1
            evidence.confirmed = ""
        if evidence.hits >= self.required:
            evidence.confirmed = reading.text
        return evidence
