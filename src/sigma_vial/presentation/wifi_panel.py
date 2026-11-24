"""Cliente TCP del ESP32. La sesión se confirma al recibir PONG."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpSocket
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton


class WifiPanel(QGroupBox):
    def __init__(self, queue_counts=None):
        super().__init__("ESP32 por Wi-Fi")
        self.address = QLineEdit()
        self.address.setPlaceholderText("IP del monitor serie")
        self.button = QPushButton("Conectar")
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
        layout.addWidget(self.address, 0, 0)
        layout.addWidget(self.button, 0, 1)
        layout.addWidget(self.status, 1, 0)
        layout.addWidget(self.sample_button, 1, 1)
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
        self.status.setText("Sin conexión")

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
        if self.socket is not None or self.retry.isActive():
            self.disconnect_device()
        else:
            self.connect_device()

    def connect_device(self):
        ip = QHostAddress(self.address.text().strip())
        if ip.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            self.status.setText("Introduce la dirección IPv4 del monitor serie.")
            return
        socket = QTcpSocket(self)
        self.socket = socket
        socket.setReadBufferSize(64)
        self.sent.hide()
        self.reply.hide()
        self.sent.clear()
        self.reply.clear()
        self.pending = None
        timer = self.timer = QTimer(socket)
        timer.setSingleShot(True)

        def finish(message):
            if self.socket is socket:
                self.disconnect_device(message)
                self.retry.start(2000)
                self.button.setText("Cancelar reconexión")
                self.address.setEnabled(False)

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
                if response.startswith("ERROR "):
                    self.status.setText("Muestra rechazada")
                else:
                    self.status.setText("Datos actuales" if self.running else "En pausa")
            elif not self.ready and response == "PONG":
                timer.stop()
                self.ready = True
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
        self.status.setText("Conectando al puerto TCP 5050…")
        self.button.setText("Desconectar")
        self.address.setEnabled(False)
        timer.start(5000)
        socket.connectToHost(ip, 5050)

    def disconnect_device(self, message=""):
        self.retry.stop()
        self.auto_timer.stop()
        self.ready = False
        self.pending = None
        socket, self.socket = self.socket, None
        if socket is not None:
            socket.abort()
            socket.deleteLater()
        self.sample_button.setEnabled(False)
        self.address.setEnabled(True)
        self.button.setText("Conectar")
        self.status.setText(f"Sin conexión · {message}" if message else "Sin conexión")
