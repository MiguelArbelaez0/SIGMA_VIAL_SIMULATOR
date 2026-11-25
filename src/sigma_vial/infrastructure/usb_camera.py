"""Video JPEG bajo demanda sobre el puente USB-UART de la cámara."""

import re
from time import monotonic


def com_port(value):
    name = value.strip().upper()
    return name if re.fullmatch(r"COM[1-9][0-9]*", name) else ""


def camera_jpegs(port_name, stopping):
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
        while not stopping.is_set():
            if port.write(b"J") != 1 or not port.waitForBytesWritten(500):
                raise OSError(port.errorString())
            data = bytearray()
            deadline = monotonic() + 2
            while not stopping.is_set():
                if monotonic() >= deadline:
                    raise TimeoutError("La cámara no completó el fotograma USB.")
                if not port.bytesAvailable():
                    port.waitForReadyRead(100)
                data.extend(bytes(port.readAll()))
                start = data.find(b"SVJ1")
                if start < 0:
                    del data[:-3]
                    continue
                del data[:start]
                if len(data) >= 8:
                    length = int.from_bytes(data[4:8], "little")
                    if not 0 < length <= 256 * 1024:
                        raise ValueError("Longitud JPEG inválida")
                    if len(data) >= 8 + length:
                        yield bytes(data[8 : 8 + length])
                        stopping.wait(0.02)
                        break
    finally:
        port.close()
