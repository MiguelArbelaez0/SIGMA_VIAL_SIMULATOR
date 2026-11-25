"""Video JPEG bajo demanda sobre el puente USB-UART de la cámara."""

import re
import struct
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class NorthCalibration:
    points: tuple = ((112, 32), (112, 206), (208, 32), (208, 206))

    def command(self):
        return b"C" + struct.pack("<8H", *(v for point in self.points for v in point))


def com_port(value):
    name = value.strip().upper()
    return name if re.fullmatch(r"COM[1-9][0-9]*", name) else ""


def camera_jpegs(port_name, stopping, calibration=lambda: None):
    from PySide6.QtCore import QIODevice
    from PySide6.QtSerialPort import QSerialPort

    port = QSerialPort()
    port.setPortName(port_name)
    port.setBaudRate(460800)
    if not port.open(QIODevice.OpenModeFlag.ReadWrite):
        raise OSError(port.errorString())
    try:
        if stopping.wait(1.3):
            return
        port.clear()
        previous = None
        while not stopping.is_set():
            token = calibration()
            command = (
                b"J" if token is None else (token.command() if token is not previous else b"N")
            )
            previous = token
            magic, header = (b"SVJ1", 8) if token is None else (b"SVJ2", 9)
            if port.write(command) != len(command) or not port.waitForBytesWritten(500):
                raise OSError(port.errorString())
            data = bytearray()
            deadline = monotonic() + 2
            while not stopping.is_set():
                if monotonic() >= deadline:
                    raise TimeoutError("La cámara no completó el fotograma USB.")
                if not port.bytesAvailable():
                    port.waitForReadyRead(100)
                data.extend(bytes(port.readAll()))
                start = data.find(magic)
                if start < 0:
                    del data[:-3]
                    continue
                del data[:start]
                if len(data) >= header:
                    length = int.from_bytes(data[4:8], "little")
                    if not 0 < length <= 256 * 1024:
                        raise ValueError("Longitud JPEG inválida")
                    if len(data) >= header + length:
                        count = data[8] if token is not None and data[8] <= 32 else None
                        yield bytes(data[header : header + length]), token, count
                        stopping.wait(0.02)
                        break
    finally:
        port.close()
