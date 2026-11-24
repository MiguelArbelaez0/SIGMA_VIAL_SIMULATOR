"""Cliente TCP del ESP32. La sesión se confirma al recibir PONG."""

import re

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpSocket
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton


def demand_text(response):
    match = re.fullmatch(
        r"OK NS=(\d+) EO=(\d+) TOTAL=\d+ MAYOR=(NS|EO|EMPATE|SIN_DEMANDA)", response
    )
    if not match:
        return ""
    ns, eo, axis = match.groups()
    if axis == "SIN_DEMANDA":
        return "Sin demanda · ninguna cola detectada"
    count = int(eo if axis == "EO" else ns)
    vehicles = "vehículo" if count == 1 else "vehículos"
    if axis == "EMPATE":
        return f"Empate · {count} {vehicles} en cada eje"
    name = "Norte–Sur" if axis == "NS" else "Oriente–Occidente"
    return f"Mayor cola: {name} · {count} {vehicles} en ese eje"


class WifiPanel(QGroupBox):
    def __init__(self, queue_counts=None, settings=None):
        super().__init__("Procesador ESP32")
        self.settings = (
            settings if settings is not None else QSettings("SIGMA VIAL", "Procesador ESP32")
        )
        self.address = QLineEdit(self.settings.value("ip", "192.168.4.1", type=str))
        self.address.setPlaceholderText("IP del monitor serie")
        self.address.hide()
        self.button = QPushButton("Conectar al ESP32", self)
        self.change_address = QPushButton("Cambiar dirección")
        self.change_address.clicked.connect(self.edit_address)
        self.queue_counts = queue_counts
        self.sample_button = QPushButton("Enviar muestra de cola")
        self.sample_button.setEnabled(False)
        self.sample_button.clicked.connect(self.send_sample)
        self.sent = QLabel()
        self.reply = QLabel()
        for label in (self.sent, self.reply):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.hide()
        self.status = QLabel("Sin conexión")
        self.status.setWordWrap(True)
        layout = QGridLayout(self)
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.hide()
        layout.addWidget(self.status, 0, 0)
        layout.addWidget(self.change_address, 0, 1)
        layout.addWidget(self.address, 1, 0)
        layout.addWidget(self.sample_button, 1, 1)
        layout.addWidget(self.result, 2, 0, 1, 2)
        layout.addWidget(self.sent, 3, 0, 1, 2)
        layout.addWidget(self.reply, 4, 0, 1, 2)
        self.button.clicked.connect(self.toggle)
        self.address.returnPressed.connect(self.toggle)
        self.socket = None
        self.running = False
        self.ready = False
        self.pending = None
        self.auto_timer = QTimer(self)
        self.auto_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.auto_timer.setInterval(1000)
        self.auto_timer.timeout.connect(self.send_sample)
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.timeout.connect(self.connect_device)
        self.recovering = False

    def edit_address(self):
        self.disconnect_device()
        self.address.show()
        self.address.setFocus()
        self.address.selectAll()

    def set_running(self, running):
        self.running = running
        if not self.ready:
            return
        if running:
            self.status.setText("Esperando primera muestra")
            self.auto_timer.start()
        else:
            self.auto_timer.stop()
            self.status.setText(
                "En pausa" if self.reply.text() else "En pausa · esperando primera muestra"
            )

    def reset_samples(self):
        reconnect = self.socket is not None or self.retry.isActive()
        self.disconnect_device()
        self.running = False
        self.sent.clear()
        self.reply.clear()
        self.result.clear()
        self.result.hide()
        if reconnect:
            self.connect_device()

    def send_sample(self):
        if not self.ready or self.pending is not None or self.queue_counts is None:
            return
        self.pending = "TRAFICO " + " ".join(str(count) for count in self.queue_counts())
        self.sample_button.setEnabled(False)
        self.socket.write((self.pending + "\n").encode("ascii"))
        self.timer.start(5000)

    def toggle(self):
        if self.socket is not None:
            self.disconnect_device()
        else:
            self.retry.stop()
            self.connect_device()

    def connect_device(self):
        ip = QHostAddress(self.address.text().strip())
        if ip.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            self.status.setText("Introduce la dirección IPv4 del monitor serie.")
            self.address.show()
            return
        socket = QTcpSocket(self)
        self.socket = socket
        self.address.hide()
        socket.setReadBufferSize(64)
        self.pending = None
        timer = self.timer = QTimer(socket)
        timer.setSingleShot(True)

        def finish(message):
            if self.socket is socket:
                recover = self.ready or self.recovering
                self.disconnect_device(message)
                self.recovering = recover
                self.button.setText("Reintentar")
                if recover:
                    self.retry.start(4000)

        def receive():
            if self.socket is not socket:
                return
            if not socket.canReadLine():
                if socket.bytesAvailable() >= 64:
                    finish("Respuesta TCP demasiado larga")
                return
            response = bytes(socket.readLine()).rstrip(b"\r\n").decode("ascii", errors="replace")
            if self.pending is not None and response.startswith(("OK ", "ERROR ")):
                timer.stop()
                self.sent.setText(f"PC envía (N, S, E, O): {self.pending}")
                self.reply.setText(f"ESP32 responde: {response}")
                self.sent.show()
                self.reply.show()
                self.pending = None
                self.sample_button.setEnabled(True)
                summary = demand_text(response)
                self.result.setText(summary)
                self.result.setVisible(bool(summary))
                if not summary:
                    self.status.setText("Muestra rechazada")
                else:
                    self.status.setText("Datos actuales" if self.running else "En pausa")
            elif not self.ready and response == "PONG":
                timer.stop()
                self.ready = True
                self.settings.setValue("ip", ip.toString())
                self.button.setText("ESP32 conectado")
                self.button.setToolTip("Desconectar del ESP32")
                self.sent.clear()
                self.reply.clear()
                self.status.setText("Esperando primera muestra · PONG recibido")
                self.sample_button.setEnabled(self.queue_counts is not None)
                if self.running:
                    self.auto_timer.start()
            else:
                finish("Respuesta TCP inesperada")

        def send_ping():
            self.status.setText("Esperando PONG…")
            socket.write(b"PING\n")
            timer.start(5000)

        def timeout():
            if self.pending is not None:
                finish("Tiempo agotado sin respuesta a la muestra")
            elif socket.state() == QAbstractSocket.SocketState.ConnectedState:
                finish("TCP establecido, pero no llegó PONG")
            else:
                finish("Tiempo agotado al conectar al puerto TCP 5050")

        socket.connected.connect(send_ping)
        socket.readyRead.connect(receive)
        socket.errorOccurred.connect(lambda _: finish(socket.errorString()))
        socket.disconnected.connect(lambda: finish("Desconectado"))
        timer.timeout.connect(timeout)
        self.status.setText(
            "Reconectando · lectura desactualizada"
            if self.recovering
            else "Conectando al puerto TCP 5050…"
        )
        self.button.setText("Conectando…")
        self.button.setToolTip("Cancelar el intento de conexión")
        self.address.setEnabled(False)
        timer.start(5000)
        socket.connectToHost(ip, 5050)

    def disconnect_device(self, message=""):
        self.retry.stop()
        self.auto_timer.stop()
        self.ready = False
        self.recovering = False
        self.result.hide()
        self.pending = None
        socket, self.socket = self.socket, None
        if socket is not None:
            socket.abort()
            socket.deleteLater()
        self.sample_button.setEnabled(False)
        self.address.setEnabled(True)
        self.button.setText("Conectar al ESP32")
        self.button.setToolTip("")
        state = "Sin conexión · lectura desactualizada" if self.reply.text() else "Sin conexión"
        self.status.setText(
            f"{state}. Comprueba la red Wi-Fi del PC. {message}" if message else state
        )
