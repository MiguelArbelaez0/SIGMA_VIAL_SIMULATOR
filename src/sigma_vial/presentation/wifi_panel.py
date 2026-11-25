"""Cliente TCP del ESP32. La sesión se confirma al recibir PONG."""

import re
import sys

from PySide6.QtCore import QIODevice, QProcess, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpSocket
from PySide6.QtSerialPort import QSerialPort
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolTip,
)

from sigma_vial.infrastructure.usb_camera import com_port

PRESENTATION_SSID = "SIGMA-VIAL-Prueba-cf98"


def wlan_ssids(output):
    return {
        name.strip()
        for name in re.findall(rb"(?m)^[ \t]*SSID(?: \d+)?[ \t]*:[ \t]*([^\r\n]*)", output)
    }


def demand_text(response):
    match = re.fullmatch(
        r"OK NS=(\d+) EO=(\d+) TOTAL=(\d+) MAYOR=(NS|EO|EMPATE|SIN_DEMANDA)", response
    )
    if not match:
        return ""
    ns, eo, total, axis = match.groups()
    if axis == "SIN_DEMANDA":
        return "No hay vehículos esperando en el cruce."
    count = int(eo if axis == "EO" else ns)
    vehicles = "vehículo" if count == 1 else "vehículos"
    if axis == "EMPATE":
        return f"Empate: {count} {vehicles} en cada eje ({total} en total)."
    name = "Norte y Sur" if axis == "NS" else "Oriente y Occidente"
    return f"Hay más vehículos esperando entre {name}: {count} de {total} en total."


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
        self.sample_button = QPushButton("Consultar vehículos en espera")
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
        self.wifi_settings = QPushButton("Abrir Wi-Fi de Windows")
        self.wifi_settings.hide()
        self.wifi_settings.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("ms-settings:network-wifi"))
        )
        layout = QGridLayout(self)
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.hide()
        self.counts = QLabel()
        self.counts.setWordWrap(True)
        self.counts.hide()
        self.details = QCheckBox("Ver mensajes técnicos")
        self.details.hide()
        self.details.toggled.connect(self.sent.setVisible)
        self.details.toggled.connect(self.reply.setVisible)
        layout.addWidget(self.status, 0, 0)
        layout.addWidget(self.change_address, 0, 1)
        layout.addWidget(self.address, 1, 0)
        layout.addWidget(self.sample_button, 1, 1)
        layout.addWidget(self.result, 2, 0, 1, 2)
        layout.addWidget(self.counts, 3, 0, 1, 2)
        layout.addWidget(self.details, 4, 0, 1, 2)
        layout.addWidget(self.sent, 5, 0, 1, 2)
        layout.addWidget(self.reply, 6, 0, 1, 2)
        layout.addWidget(self.wifi_settings, 7, 0, 1, 2)
        self.button.clicked.connect(self.toggle)
        self.address.returnPressed.connect(self.toggle)
        self.socket = None
        self.running = False
        self.ready = False
        self.pending = None
        self.wlan = QProcess(self)
        self.wlan.finished.connect(self._wlan_finished)
        self.check_network = False
        self.auto_timer = QTimer(self)
        self.auto_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.auto_timer.setInterval(1000)
        self.auto_timer.timeout.connect(self.send_sample)
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.timeout.connect(self.connect_device)

    def edit_address(self):
        dialog = QInputDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle("Cambiar dirección del ESP32")
        dialog.setLabelText("Puerto USB (ej. COM3) o dirección IPv4 del procesador")
        dialog.setTextValue(self.address.text())
        dialog.textValueSelected.connect(self.apply_address)
        dialog.open()

    def apply_address(self, text):
        ip = QHostAddress(text.strip())
        port = com_port(text)
        if not port and ip.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            self.change_address.setToolTip("Introduce un puerto COM o una dirección IPv4 válida.")
            QToolTip.showText(
                self.change_address.mapToGlobal(self.change_address.rect().center()),
                self.change_address.toolTip(),
                self.change_address,
            )
            return
        self.change_address.setToolTip("")
        address = port or ip.toString()
        if address == self.address.text() and self.socket is not None:
            return
        self.disconnect_device()
        self.address.setText(address)
        self.toggle()

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
            self.check_network = (
                sys.platform == "win32" and self.address.text().strip() == "192.168.4.1"
            )
            self.connect_device()

    def _wlan_finished(self, code, exit_status):
        args = self.wlan.arguments()
        names = wlan_ssids(bytes(self.wlan.readAllStandardOutput()))
        if code or not self.check_network or self.ready:
            return
        if args == ["wlan", "show", "interfaces"] and names == {b"Estudiantes-CEIPA"}:
            self.check_network = False
            self.wlan.start("netsh", ["wlan", "connect", f"name={PRESENTATION_SSID}"])

    def connect_device(self):
        ip = QHostAddress(self.address.text().strip())
        port = com_port(self.address.text())
        if not port and ip.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            self.status.setText("Introduce la dirección IPv4 del monitor serie.")
            self.address.show()
            return
        socket = QSerialPort(self) if port else QTcpSocket(self)
        self.socket = socket
        self.address.hide()
        socket.setReadBufferSize(64)
        self.pending = None
        timer = self.timer = QTimer(socket)
        timer.setSingleShot(True)

        def finish(message):
            if self.socket is socket:
                check_network = self.check_network
                self.disconnect_device(message)
                self.check_network = check_network
                if check_network and self.wlan.state() == QProcess.ProcessState.NotRunning:
                    self.wlan.start("netsh", ["wlan", "show", "interfaces"])
                self.button.setText("Reintentar")
                self.retry.start(4000)

        def receive():
            if self.socket is not socket:
                return
            if not socket.canReadLine():
                if socket.bytesAvailable() >= 64:
                    finish("Respuesta TCP demasiado larga")
                return
            response = bytes(socket.readLine()).rstrip(b"\r\n").decode("ascii", errors="replace")
            if port:
                # El puerto serie también publica diagnósticos del punto de acceso.
                while response != "PONG" and not response.startswith(("OK ", "ERROR ")):
                    if not socket.canReadLine():
                        return
                    response = bytes(socket.readLine()).strip().decode("ascii", errors="replace")
            if self.pending is not None and response.startswith(("OK ", "ERROR ")):
                timer.stop()
                self.sent.setText(f"PC envía (N, S, E, O): {self.pending}")
                self.reply.setText(f"ESP32 responde: {response}")
                n, s, e, o = self.pending.split()[1:]
                self.counts.setText(
                    "Vehículos en espera por acceso\n"
                    f"Norte: {n}   Sur: {s}   Oriente: {e}   Occidente: {o}"
                )
                self.details.show()
                self.pending = None
                self.sample_button.setEnabled(True)
                summary = demand_text(response)
                self.result.setText(summary)
                self.result.setVisible(bool(summary))
                self.counts.setVisible(bool(summary))
                if not summary:
                    self.status.setText("La placa no pudo interpretar estos conteos.")
                else:
                    self.status.setText("Datos actuales" if self.running else "En pausa")
            elif not self.ready and response == "PONG":
                timer.stop()
                self.ready = True
                self.check_network = False
                self.wifi_settings.hide()
                self.settings.setValue("ip", port or ip.toString())
                self.button.setText(f"ESP32 conectado · {port}" if port else "ESP32 conectado")
                self.button.setToolTip("Desconectar del ESP32")
                self.sent.clear()
                self.reply.clear()
                self.status.setText("Placa conectada. Esperando el primer conteo.")
                self.sample_button.setEnabled(self.queue_counts is not None)
                if self.running:
                    self.auto_timer.start()
            else:
                finish("Respuesta TCP inesperada")

        def send_ping():
            if self.socket is not socket:
                return
            self.status.setText("Esperando que responda la placa…")
            socket.write(b"PING\n")
            timer.start(5000)

        def timeout():
            if self.pending is not None:
                finish("Tiempo agotado sin respuesta a la muestra")
            elif port:
                finish(f"La placa no respondió por {port}")
            elif socket.state() == QAbstractSocket.SocketState.ConnectedState:
                finish("Se abrió la conexión, pero la placa no respondió")
            else:
                finish("Tiempo agotado al conectar al puerto TCP 5050")

        timer.timeout.connect(timeout)
        self.status.setText(
            "Reconectando · lectura desactualizada"
            if self.reply.text()
            else "Conectando al puerto TCP 5050…"
        )
        self.button.setText("Conectando…")
        self.button.setToolTip("Cancelar el intento de conexión")
        self.address.setEnabled(False)
        if port:
            self.status.setText(f"Conectando a {port} por USB…")
            socket.setPortName(port)
            socket.setBaudRate(115200)
            if not socket.open(QIODevice.OpenModeFlag.ReadWrite):
                finish(socket.errorString())
                return

            def serial_handshake():
                if self.socket is socket:
                    socket.clear()
                    socket.readyRead.connect(receive)
                    send_ping()

            socket.errorOccurred.connect(
                lambda error: (
                    finish(socket.errorString())
                    if error != QSerialPort.SerialPortError.NoError
                    else None
                )
            )
            QTimer.singleShot(1500, socket, serial_handshake)
            return
        socket.connected.connect(send_ping)
        socket.readyRead.connect(receive)
        socket.errorOccurred.connect(lambda _: finish(socket.errorString()))
        socket.disconnected.connect(lambda: finish("Desconectado"))
        timer.start(5000)
        socket.connectToHost(ip, 5050)

    def disconnect_device(self, message=""):
        self.check_network = False
        self.retry.stop()
        self.auto_timer.stop()
        self.ready = False
        self.result.hide()
        self.counts.hide()
        self.details.setChecked(False)
        self.details.hide()
        self.pending = None
        socket, self.socket = self.socket, None
        if socket is not None:
            if isinstance(socket, QSerialPort):
                socket.close()
            else:
                socket.abort()
            socket.deleteLater()
        self.sample_button.setEnabled(False)
        self.address.setEnabled(True)
        self.button.setText("Conectar al ESP32")
        self.button.setToolTip("")
        state = "Sin conexión · lectura desactualizada" if self.reply.text() else "Sin conexión"
        presentation = self.address.text().strip() == "192.168.4.1"
        self.wifi_settings.setVisible(bool(message) and presentation and sys.platform == "win32")
        if message:
            if port := com_port(self.address.text()):
                self.status.setText(f"{state}. {port}: {message}. Reintento automático.")
                return
            network_hint = (
                "Alimenta el ESP32 por USB y selecciona SIGMA-VIAL-Prueba-cf98 en el Wi-Fi del PC"
                if presentation
                else "Comprueba que el PC pueda llegar a la IP del ESP32"
            )
            endpoint = f"{self.address.text().strip()}:5050"
            state = f"{state}. {network_hint}. Reintento automático. {endpoint} · {message}"
        self.status.setText(state)
