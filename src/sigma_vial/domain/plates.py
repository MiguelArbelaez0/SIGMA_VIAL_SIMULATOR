"""Placas sintéticas, únicas dentro de una sesión; no consulta registros reales."""

import random
import string


class PlateService:
    def __init__(self, seed: int):
        self._rng = random.Random(seed)
        self.used: set[str] = set()

    def issue(self, motorcycle: bool = False) -> str:
        while True:
            letters = "".join(self._rng.choices(string.ascii_uppercase, k=3))
            suffix = "".join(self._rng.choices(string.digits, k=2 if motorcycle else 3))
            if motorcycle:
                suffix += self._rng.choice(string.ascii_uppercase)
            plate = letters + suffix
            if plate not in self.used:
                self.used.add(plate)
                return plate
