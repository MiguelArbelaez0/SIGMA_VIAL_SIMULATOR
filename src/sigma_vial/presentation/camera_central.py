"""Central de cámaras físicas, independiente de las observaciones del simulador."""

import json
from time import monotonic

from PySide6.QtCore import QRectF, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sigma_vial.domain.scenario import Access
from sigma_vial.infrastructure.live_stream import LiveStream
from sigma_vial.infrastructure.usb_camera import com_port

SUGGESTED_URL = "http://172.20.10.2/stream"

CENTRAL_STYLE = """
QDialog#cameraCentral { background: #101d2c; }
QFrame#cameraPanel { background: #203247; border: 1px solid #64788d; border-radius: 8px; }
QLabel#cameraTitle { color: #ffffff; font-size: 18px; font-weight: 700; }
QLabel#cameraState { color: #dbe9f6; font-size: 14px; font-weight: 600; }
QPushButton, QToolButton {
    color: #142b44; background: #f4f7fb; border: 2px solid #acbbcc;
    border-radius: 6px; padding: 6px 12px;
}
QToolButton { padding-right: 22px; }
QPushButton:hover, QToolButton:hover, QToolButton:open {
    color: #142b44; background: #d6eafe; border-color: #7ea4c5;
}
QPushButton:focus, QToolButton:focus { border-color: #08709c; }
QToolButton::menu-indicator { subcontrol-position: right center; right: 6px; }
QMenu {
    color: #142b44; background: #f4f7fb; border: 1px solid #617890; padding: 4px;
}
QMenu::item {
    color: #142b44; background: #f4f7fb; padding: 7px 30px 7px 12px;
    border: 2px solid transparent; border-radius: 3px;
}
QMenu::item:selected { color: #102942; background: #c5e3fc; border-color: #216a98; }
QMenu::item:disabled { color: #586778; background: #e7ecf1; }
"""


def camera_url(text):
    if port := com_port(text):
        return port
    url = QUrl(text.strip(), QUrl.ParsingMode.StrictMode)
    if not url.isValid() or url.scheme() not in ("http", "https") or not url.host():
        raise ValueError("Introduce una URL completa que comience con http:// o https://.")
    if url.userInfo():
        raise ValueError("Usa una URL de video sin usuario ni contraseña.")
    url.setFragment(None)
    if url.port() == {"http": 80, "https": 443}[url.scheme()]:
        url.setPort(-1)
    if not url.path():
        url.setPath("/")
    return bytes(url.toEncoded()).decode("ascii")


class VideoDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.setMinimumSize(120, 75)

    def display(self, image):
        self.image = image
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), "#10243d")
        if not self.image.isNull():
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(0, 0, size.width(), size.height())
            target.moveCenter(QRectF(self.rect()).center())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self.image)


class CameraPanel(QFrame):
    def __init__(self, central, access):
        super().__init__()
        self.setObjectName("cameraPanel")
        self.setAccessibleName(access.value)
        title = QLabel(access.value)
        title.setObjectName("cameraTitle")
        self.video = VideoDisplay()
        self.state = QLabel()
        self.state.setObjectName("cameraState")
        self.connect_button = QPushButton()
        self.connect_button.clicked.connect(lambda: central.toggle(access))
        self.expand = QPushButton("Ampliar")
        self.expand.clicked.connect(lambda: central.focus_camera(access))
        self.options = QToolButton()
        self.options.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.options.setText("Opciones")
        self.options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.options)
        menu.addAction("Editar URL", lambda: central.configure(access))
        move = menu.addMenu("Mover a")
        for other in Access:
            if other != access:
                action = move.addAction(other.value)
                action.triggered.connect(
                    lambda checked=False, dest=other: central.move(access, dest)
                )
        menu.addAction("Quitar asignación", lambda: central.assign(access, ""))
        self.options.setMenu(menu)
        controls = QHBoxLayout()
        for widget in (self.connect_button, self.options, self.expand):
            controls.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        header = QHBoxLayout()
        header.addWidget(title, 1)
        header.addWidget(self.state)
        layout.addLayout(header)
        layout.addWidget(self.video, 1)
        layout.addLayout(controls)

    def status(self, text, button, configured=True):
        self.state.setText(text)
        self.state.setToolTip("")
        self.connect_button.setText(button)
        self.options.setVisible(configured)
        if text != "En vivo":
            self.video.display(QImage())


class CameraCentral(QDialog):
    openLaboratory = Signal()

    def __init__(self, owner, settings=None):
        super().__init__(owner)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint)
        self.setObjectName("cameraCentral")
        self.setStyleSheet(CENTRAL_STYLE)
        self.setWindowTitle("SIGMA VIAL · Central de Monitoreo")
        self.resize(1024, 700)
        self.settings = settings if settings is not None else QSettings("SIGMA VIAL", "Cámaras")
        self.urls = {}
        try:
            saved = json.loads(self.settings.value("accesos", "{}", type=str))
        except ValueError:
            saved = {}
        for access in Access:
            if isinstance(saved, dict) and isinstance(saved.get(access.name), str):
                try:
                    url = camera_url(saved[access.name])
                except ValueError:
                    continue
                if url not in self.urls.values():
                    self.urls[access] = url
        self.active = set()
        self.streams = {}
        self.panels = {}
        self.focused = None
        layout = QVBoxLayout(self)
        self.grid = QGridLayout()
        layout.addLayout(self.grid, 1)
        lab = QPushButton("Monitoreo simulado y laboratorio de visión")
        lab.clicked.connect(self.openLaboratory)
        layout.addWidget(lab)
        for index, access in enumerate(Access):
            panel = self.panels[access] = CameraPanel(self, access)
            self.grid.addWidget(panel, index // 2, index % 2)
            self.idle(access)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.refresh)
        QApplication.instance().aboutToQuit.connect(self.close)

    def idle(self, access):
        panel = self.panels[access]
        if access in self.urls:
            panel.status("Desconectada", "Conectar")
        else:
            panel.status("Sin configurar", "Configurar cámara", False)

    def save(self):
        self.settings.setValue("accesos", json.dumps({a.name: u for a, u in self.urls.items()}))

    def configure(self, access):
        text, ok = QInputDialog.getText(
            self,
            f"Configurar cámara · {access.value}",
            "URL del video o puerto USB (ej. COM4) · Aceptar para conectar",
            text=self.urls.get(access, SUGGESTED_URL),
        )
        if ok:
            try:
                self.assign(access, camera_url(text))
            except ValueError as exc:
                QMessageBox.warning(self, "Configurar cámara", str(exc))

    def assign(self, access, url):
        if url and any(a != access and u == url for a, u in self.urls.items()):
            raise ValueError("Esta URL ya tiene un acceso. Usa Opciones → Mover a.")
        self.stop(access)
        if url:
            self.urls[access] = url
            self.start(access)
        else:
            self.urls.pop(access, None)
            self.idle(access)
        self.save()

    def move(self, source, dest):
        if dest in self.urls:
            QMessageBox.information(
                self, "Mover cámara", "El acceso de destino ya tiene una cámara."
            )
            return
        running = source in self.active
        self.active.discard(source)
        self.urls[dest] = self.urls.pop(source)
        self.idle(source)
        self.idle(dest)
        if running:
            self.start(dest)
        self.save()

    def toggle(self, access):
        if access not in self.urls:
            self.configure(access)
        elif access in self.active:
            self.stop(access)
        else:
            self.start(access)

    def start(self, access):
        self.active.add(access)
        self.panels[access].status("Conectando…", "Desconectar")
        self.timer.start()

    def stop(self, access):
        self.active.discard(access)
        stream = self.streams.get(self.urls.get(access))
        if stream:
            stream.stopping.set()
        self.idle(access)

    def refresh(self):
        for url, stream in list(self.streams.items()):
            if stream.stopping.is_set() and not stream.is_alive():
                del self.streams[url]
        for access in tuple(self.active):
            url = self.urls[access]
            panel = self.panels[access]
            stream = self.streams.get(url)
            if stream is None:
                stream = self.streams[url] = LiveStream(url)
                stream.start()
            if stream.stopping.is_set():
                continue
            if not stream.is_alive() or monotonic() - stream.last_received > 5:
                self.stop(access)
                panel.status("Sin señal", "Reintentar")
                panel.state.setToolTip(stream.error)
                continue
            frame = stream.take_frame()
            if frame is not None:
                pixels = frame.pixels
                height, width = pixels.shape[:2]
                image = QImage(
                    pixels.data, width, height, pixels.strides[0], QImage.Format.Format_BGR888
                )
                panel.video.display(image.copy())
                panel.state.setText("En vivo")
                panel.state.setToolTip("")
        if not self.active and not self.streams:
            self.timer.stop()

    def focus_camera(self, access):
        self.focused = None if self.focused == access else access
        for index, (which, panel) in enumerate(self.panels.items()):
            self.grid.removeWidget(panel)
            if self.focused == which:
                self.grid.addWidget(panel, 0, 0, 2, 2)
            elif self.focused is None:
                self.grid.addWidget(panel, index // 2, index % 2)
            panel.setVisible(self.focused in (None, which))
            panel.expand.setText("Volver a la cuadrícula" if self.focused == which else "Ampliar")

    def done(self, result):
        for access in tuple(self.active):
            self.stop(access)
        if self.focused:
            self.focus_camera(self.focused)
        super().done(result)
