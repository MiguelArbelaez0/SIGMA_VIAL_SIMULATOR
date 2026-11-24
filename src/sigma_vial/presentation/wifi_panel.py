"""Cliente TCP del ESP32. La sesión se confirma al recibir PONG."""

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpSocket
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton


class WifiPanel(QGroupBox):
    def __init__(self):
        super().__init__("ESP32 por Wi-Fi")
        self.address = QLineEdit()
        self.address.setPlaceholderText("IP del monitor serie")
        self.button = QPushButton("Conectar")
        self.status = QLabel("Desconectado")
        self.status.setWordWrap(True)
        layout = QGridLayout(self)
        layout.addWidget(self.address, 0, 0)
        layout.addWidget(self.button, 0, 1)
        layout.addWidget(self.status, 1, 0, 1, 2)
        self.button.clicked.connect(self.toggle)
        self.address.returnPressed.connect(self.toggle)
        self.socket = None

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
        timer = QTimer(socket)
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
            if bytes(socket.readLine()) in (b"PONG\n", b"PONG\r\n"):
                timer.stop()
                self.status.setText("Conectado · PONG recibido")
            else:
                finish("Respuesta TCP inesperada")

        socket.connected.connect(lambda: socket.write(b"PING\n"))
        socket.readyRead.connect(receive)
        socket.errorOccurred.connect(lambda _: finish(socket.errorString()))
        socket.disconnected.connect(lambda: finish("Desconectado"))
        timer.timeout.connect(lambda: finish("Tiempo de espera agotado sin PONG"))
        self.status.setText("Esperando PONG…")
        self.button.setText("Desconectar")
        self.address.setEnabled(False)
        timer.start(5000)
        socket.connectToHost(ip, 5050)

    def disconnect_device(self, message="Desconectado"):
        socket, self.socket = self.socket, None
        if socket is not None:
            socket.abort()
            socket.deleteLater()
        self.address.setEnabled(True)
        self.button.setText("Conectar")
        self.status.setText(message)
