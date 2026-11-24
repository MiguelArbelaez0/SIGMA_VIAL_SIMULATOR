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
        self.status = QLabel("Desconectado")
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

    def send_sample(self):
        command = "TRAFICO " + " ".join(str(count) for count in self.queue_counts())
        self.sent.show()
        self.reply.show()
        self.sent.setText(f"PC envía (N, S, E, O): {command}")
        self.reply.setText("Esperando respuesta TCP…")
        self.sample_button.setEnabled(False)
        self.awaiting_sample = True
        self.socket.write((command + "\n").encode("ascii"))
        self.timer.start(5000)

    def toggle(self):
        if self.socket is not None:
            self.disconnect_device()
            return
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
        self.awaiting_sample = False
        timer = self.timer = QTimer(socket)
        timer.setSingleShot(True)

        def finish(message):
            if self.socket is socket:
                self.disconnect_device(message)

        def receive():
            if self.socket is not socket:
                return
            if not socket.canReadLine():
                if socket.bytesAvailable() >= 64:
                    finish("Respuesta TCP demasiado larga")
                return
            response = bytes(socket.readLine()).rstrip(b"\r\n").decode("ascii", errors="replace")
            if self.awaiting_sample and response.startswith(("OK ", "ERROR ")):
                timer.stop()
                self.awaiting_sample = False
                self.reply.setText(f"ESP32 responde: {response}")
                self.sample_button.setEnabled(True)
            elif not self.awaiting_sample and response == "PONG":
                timer.stop()
                self.status.setText("Conectado · PONG recibido")
                self.sample_button.setEnabled(self.queue_counts is not None)
            else:
                finish("Respuesta TCP inesperada")

        def send_ping():
            self.status.setText("Esperando PONG…")
            socket.write(b"PING\n")
            timer.start(5000)

        def timeout():
            if self.awaiting_sample:
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

    def disconnect_device(self, message="Desconectado"):
        socket, self.socket = self.socket, None
        if socket is not None:
            socket.abort()
            socket.deleteLater()
        self.sample_button.setEnabled(False)
        if getattr(self, "awaiting_sample", False):
            self.reply.setText("Muestra sin confirmar")
        self.address.setEnabled(True)
        self.button.setText("Conectar")
        self.status.setText(message)
