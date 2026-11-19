"""Enlace USB de solo observación del semáforo Norte."""

from PySide6.QtCore import QIODevice, QTimer
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
from PySide6.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QPushButton

from sigma_vial.domain.scenario import SignalState


class PortSelector(QComboBox):
    def refresh(self):
        selected = self.currentText()
        ports = [info.portName() for info in QSerialPortInfo.availablePorts()]
        self.clear()
        self.addItems(ports)
        if selected in ports:
            self.setCurrentText(selected)
        elif "COM3" in ports:
            self.setCurrentText("COM3")

    def showPopup(self):
        self.refresh()
        super().showPopup()


class Esp32Panel(QGroupBox):
    def __init__(self, north_state, port_factory=QSerialPort):
        super().__init__("ESP32")
        self.north_state = north_state
        self.port_factory = port_factory
        self.port = None
        self.ready = False
        self.last_state = None
        self.confirmations = 0
        self.ports = PortSelector()
        self.ports.refresh()
        self.button = QPushButton("Conectar")
        self.button.clicked.connect(self.toggle)
        self.status = QLabel("Desconectado")
        self.status.setWordWrap(True)
        self.command = QLabel("—")
        self.reply = QLabel("—")
        grid = QGridLayout(self)
        grid.addWidget(self.ports, 0, 0)
        grid.addWidget(self.button, 0, 1)
        grid.addWidget(self.status, 1, 0, 1, 2)
        grid.addWidget(QLabel("Última orden"), 2, 0)
        grid.addWidget(self.command, 2, 1)
        grid.addWidget(QLabel("Última respuesta"), 3, 0)
        grid.addWidget(self.reply, 3, 1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timeout)

    def toggle(self):
        if self.port is not None:
            self.disconnect_port()
            return
        name = self.ports.currentText()
        if not name:
            self.status.setText("Selecciona un puerto USB.")
            return
        port = self.port_factory(self)
        self.port = port
        self.command.setText("—")
        self.reply.setText("—")
        port.setPortName(name)
        port.setBaudRate(115200)
        if not port.open(QIODevice.OpenModeFlag.ReadWrite):
            self.disconnect_port(f"{name}: {port.errorString()}. Cierra el monitor con Ctrl + C.")
            return
        port.clear()
        port.readyRead.connect(self.receive)
        port.errorOccurred.connect(self.serial_error)
        self.attempts = 0
        self.buffer = bytearray()
        self.pending = False
        self.ports.setEnabled(False)
        self.button.setText("Desconectar")
        self.status.setText("Esperando PONG…")
        self.timer.start(1500)

    def serial_error(self, error):
        if self.sender() is self.port and error != QSerialPort.SerialPortError.NoError:
            self.disconnect_port(f"Error USB: {self.port.errorString()}")

    def disconnect_port(self, message="Desconectado"):
        self.timer.stop()
        port, self.port = self.port, None
        self.ready = False
        self.last_state = None
        if port is not None:
            port.close()
            port.deleteLater()
        self.ports.setEnabled(True)
        self.button.setText("Conectar")
        self.status.setText(message)

    def send(self, command):
        port = self.port
        data = (command + "\n").encode("ascii")
        if port.write(data) != len(data) or self.port is None:
            self.disconnect_port("Error de escritura USB")
            return
        self.command.setText(command)
        self.timer.start(1500)

    def timeout(self):
        if self.port is None:
            return
        if self.ready:
            self.disconnect_port("Sin confirmación · vuelve a conectar")
        elif self.attempts >= 3:
            self.disconnect_port("Sin PONG · comprueba el firmware y vuelve a conectar")
        else:
            self.attempts += 1
            self.send("PING")

    def receive(self):
        port = self.sender()
        if port is not self.port:
            return
        self.buffer.extend(bytes(port.readAll()))
        while b"\n" in self.buffer and self.port is port:
            line, _, self.buffer = self.buffer.partition(b"\n")
            response = line.rstrip(b"\r").decode("ascii", errors="replace")
            if response == "PONG" and not self.ready and self.attempts:
                self.timer.stop()
                self.ready = True
                self.status.setText("Conectado")
                self.reply.setText(response)
                self.observe(self.north_state())
            elif response == "OK NORTE ROJO" and self.ready and self.pending:
                self.timer.stop()
                self.pending = False
                self.confirmations += 1
                self.reply.setText(f"{response} · #{self.confirmations}")
            elif response and response != "OK NORTE ROJO":
                self.reply.setText(response[:80])
        if len(self.buffer) > 1024:
            self.disconnect_port("Respuesta USB demasiado larga")

    def observe(self, state):
        if not self.ready or state is self.last_state:
            return
        self.last_state = state
        if state is SignalState.RED:
            if self.pending:
                self.disconnect_port("Sin confirmación · vuelve a conectar")
                return
            self.pending = True
            self.send("NORTE ROJO")
