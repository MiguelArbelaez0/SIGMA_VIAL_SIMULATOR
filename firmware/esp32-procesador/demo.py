"""Demostración USB para la terminal de PlatformIO (pySerial)."""

import argparse
import sys
import time

import serial

DEMO = (
    ("PING", "PONG"),
    ("TRAFICO 4 2 7 1", "OK NS=6 EO=8 TOTAL=14 MAYOR=EO"),
    ("TRAFICO 3 2 4 1", "OK NS=5 EO=5 TOTAL=10 MAYOR=EMPATE"),
    ("TRAFICO 0 0 0 0", "OK NS=0 EO=0 TOTAL=0 MAYOR=SIN_DEMANDA"),
    ("TRAFICO 1 2 3", "ERROR se requieren cuatro valores"),
    ("TRAFICO 1 x 3 4", "ERROR se requiere un entero decimal de 0 a 9999"),
    ("TRAFICO 10000 0 0 0", "ERROR valor fuera de rango 0 a 9999"),
    ("X" * 65, "ERROR linea invalida o mayor de 64 bytes"),
    ("TRAFICO 9999 9999 0 1", "OK NS=19998 EO=1 TOTAL=19999 MAYOR=NS"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3", help="Puerto USB (predeterminado COM3)")
    args = parser.parse_args()
    try:
        with serial.Serial(args.port, 115200, timeout=2, write_timeout=2) as port:
            time.sleep(2)
            port.reset_input_buffer()
            for index, (command, expected) in enumerate(DEMO):
                print(f"PC envía: {command}")
                ending = b"\r\n" if index % 2 else b"\n"
                port.write(command.encode("ascii") + ending)
                data = port.read_until(b"\n", size=256)
                if not data.endswith(b"\n"):
                    raise RuntimeError("Tiempo de espera agotado o respuesta incompleta")
                reply = data.rstrip(b"\r\n").decode("ascii")
                print(f"ESP32 responde: {reply}")
                if reply != expected:
                    raise RuntimeError(f"Respuesta esperada: {expected}")
    except (serial.SerialException, RuntimeError, UnicodeError) as error:
        print(f"{args.port}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
