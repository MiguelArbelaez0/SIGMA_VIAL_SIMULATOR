from PySide6.QtSerialPort import QSerialPort

from sigma_vial.domain.scenario import Access, SignalState
from sigma_vial.presentation.main_window import MainWindow


class SimulatedPort(QSerialPort):
    def __init__(self, parent):
        super().__init__(parent)
        self.commands = []
        self.input = b""

    def open(self, mode):
        return True

    def clear(self):
        return True

    def write(self, data):
        self.commands.append(data)
        return len(data)

    def feed(self, data):
        self.input += data
        self.readyRead.emit()

    def readAll(self):
        data, self.input = self.input, b""
        return data


def connect(window):
    panel = window.esp32
    panel.port_factory = SimulatedPort
    panel.ports.addItem("SIM")
    panel.ports.setCurrentText("SIM")
    panel.button.click()
    panel.timeout()
    assert panel.port.commands == [b"PING\n"]
    return panel.port


def test_red_from_controller_and_usb_confirmation(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window.esp32
    port = connect(window)
    port.feed(b"PO")
    assert not panel.ready
    port.feed(b"NG\r\n")
    assert panel.ready and port.commands[-1] == b"NORTE ROJO\n"
    assert panel.reply.text() == "PONG"
    port.feed(b"OK NORTE ROJO\r\n")
    assert panel.reply.text() == "OK NORTE ROJO · #1"
    sim = window.simulation
    sim.automatic_generation = False
    sim.running = True
    sim.add_vehicle(Access.NORTH)
    for _ in range(1200):
        sim.advance(0.05)
        window._sync_signals()
        if sim.signals[Access.NORTH] is SignalState.GREEN:
            break
    assert sim.signals[Access.NORTH] is SignalState.GREEN
    assert port.commands[-1] == b"NORTE APAGADO\n"
    port.feed(b"OK NORTE APAGADO\n")
    assert panel.reply.text() == "OK NORTE APAGADO · #2"
    sim.add_vehicle(Access.EAST)
    for _ in range(1200):
        sim.advance(0.05)
        window._sync_signals()
        if sim.signals[Access.NORTH] is SignalState.RED:
            break
    assert sim.signals[Access.NORTH] is SignalState.RED
    for _ in range(10):
        window._sync_signals()
    assert port.commands == [b"PING\n", b"NORTE ROJO\n", b"NORTE APAGADO\n", b"NORTE ROJO\n"]
    port.feed(b"OK NORTE ROJO\n")
    assert panel.reply.text() == "OK NORTE ROJO · #3"


def test_usb_timeout_reconnect_and_unplug(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window.esp32
    old = connect(window)
    old.feed(b"PONG\n")
    panel.timeout()
    assert "Sin confirmación" in panel.status.text()
    port = connect(window)
    old.feed(b"OK NORTE ROJO\n")
    assert panel.reply.text() == "—"
    port.feed(b"PONG\n")
    assert port.commands[-1] == b"NORTE ROJO\n"
    port.errorOccurred.emit(QSerialPort.SerialPortError.ResourceError)
    assert panel.port is None
    window.simulation.running = True
    window._advance_simulation()
    assert window.simulation.time > 0
    silent = connect(window)
    for _ in range(3):
        panel.timeout()
    assert silent.commands == [b"PING\n"] * 3
    assert "Sin PONG" in panel.status.text()
