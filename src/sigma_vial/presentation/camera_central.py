"""Central de cámaras físicas, independiente de las observaciones del simulador."""

import json
from time import monotonic

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from sigma_vial.infrastructure.north_alignment import NorthAlignment, same_guides
from sigma_vial.infrastructure.usb_camera import NorthCalibration, com_port

SUGGESTED_URL = "http://172.20.10.2/stream"

CENTRAL_STYLE = """
QDialog#cameraCentral { background: #101d2c; }
QFrame#cameraPanel { background: #203247; border: 1px solid #64788d; border-radius: 8px; }
QLabel#cameraTitle { color: #ffffff; font-size: 18px; font-weight: 700; }
QLabel#cameraState { color: #dbe9f6; font-size: 14px; font-weight: 600; }
QCheckBox, QLabel#northHelp { color: #edf6ff; }
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
    pointPicked = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.guides = False
        self.points = NorthCalibration().points
        self.vehicles = ()
        self.picking = False
        self.setMinimumSize(120, 75)

    def display(self, image):
        self.image = image
        self.update()

    def image_rect(self):
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF(0, 0, size.width(), size.height())
        target.moveCenter(QRectF(self.rect()).center())
        return target

    def mousePressEvent(self, event):
        if self.picking and event.button() == Qt.MouseButton.LeftButton and not self.image.isNull():
            target = self.image_rect()
            pos = event.position()
            if target.contains(pos):
                x = min(319, int(320 * (pos.x() - target.left()) / target.width()))
                y = min(239, int(240 * (pos.y() - target.top()) / target.height()))
                self.pointPicked.emit(x, y)
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), "#10243d")
        if not self.image.isNull():
            target = self.image_rect()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self.image)
            for vehicle in self.vehicles:
                x1, y1, x2, y2 = vehicle.box
                sx = target.width() / self.image.width()
                sy = target.height() / self.image.height()
                box = QRectF(
                    target.left() + x1 * sx, target.top() + y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy
                )
                painter.setPen(QPen(QColor("#ffda58"), 2))
                painter.drawRect(box)
                label = painter.fontMetrics().boundingRect(vehicle.category).adjusted(-3, -2, 3, 2)
                label.moveBottomLeft(box.topLeft().toPoint())
                if label.top() < target.top():
                    label.moveTop(int(target.top()))
                painter.fillRect(label, QColor("#142b44"))
                painter.drawText(label, Qt.AlignmentFlag.AlignCenter, vehicle.category)
            if self.guides:
                painter.setPen(QPen(QColor("#00ffb4"), 2, Qt.PenStyle.DashLine))
                points = [
                    QPointF(
                        target.left() + target.width() * x / 320,
                        target.top() + target.height() * y / 240,
                    )
                    for x, y in self.points
                ]
                for index, point in enumerate(points):
                    painter.drawEllipse(point, 2, 2)
                    if index % 2:
                        painter.drawLine(points[index - 1], point)


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
        if access is Access.NORTH:
            self.recognize = QCheckBox("Identificar vehículos en el video")
            self.recognize.setEnabled(False)
            self.recognize.toggled.connect(central.toggle_recognition)
            self.recognized = QLabel()
            self.recognized.setObjectName("northHelp")
            self.recognized.setWordWrap(True)
            layout.addWidget(self.recognize)
            layout.addWidget(self.recognized)
            self.recognized.hide()
            self.detect = QCheckBox("Medir la fila con esta cámara")
            self.detect.setEnabled(False)
            self.detect.toggled.connect(central.toggle_detection)
            self.calibrate = QPushButton("Calibrar con los carriles vacíos")
            self.calibrate.clicked.connect(central.calibrate_north)
            self.mark = QPushButton("Marcar los dos carriles")
            self.mark.clicked.connect(central.mark_lanes)
            self.auto_align = QPushButton("Volver a la alineación automática")
            self.auto_align.clicked.connect(lambda: central.toggle_detection(True))
            self.video.pointPicked.connect(central.pick_point)
            self.help = QLabel()
            self.help.setObjectName("northHelp")
            self.help.setWordWrap(True)
            layout.addWidget(self.detect)
            layout.addWidget(self.help)
            actions = QHBoxLayout()
            actions.addWidget(self.mark)
            actions.addWidget(self.calibrate)
            layout.addLayout(actions)
            layout.addWidget(self.auto_align)
            self.auto_align.hide()
            self.help.hide()
            self.calibrate.hide()
            self.mark.hide()

    def status(self, text, button, configured=True):
        self.state.setText(text)
        self.state.setToolTip("")
        self.connect_button.setText(button)
        self.options.setVisible(configured)
        if text != "En vivo":
            self.video.display(QImage())


class CameraCentral(QDialog):
    openLaboratory = Signal()

    def __init__(self, owner, settings=None, *, north_scene=None, north_clear=lambda: True):
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
        self.north_token = None
        self.recognition_token = None
        self.north_frame = None
        self.north_scene = north_scene
        self.north_clear = north_clear
        self.alignment = None
        self.markers = []
        self.candidate = None
        self.stable_frames = 0
        self.missing_counts = 0
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
        if access is Access.NORTH:
            panel.recognize.setChecked(False)
            panel.recognize.setEnabled(False)
            panel.detect.setChecked(False)
            panel.detect.setEnabled(False)
        if access in self.urls:
            panel.status("Desconectada", "Conectar")
        else:
            panel.status("Sin configurar", "Configurar cámara", False)

    def toggle_recognition(self, enabled):
        panel = self.panels[Access.NORTH]
        self.recognition_token = object() if enabled else None
        stream = self.streams.get(self.urls.get(Access.NORTH))
        if stream:
            stream.recognition_token = self.recognition_token
        panel.video.vehicles = ()
        panel.video.update()
        panel.recognized.setText("Buscando vehículos en el video…")
        panel.recognized.setVisible(enabled)

    def toggle_detection(self, enabled):
        self.stop_alignment()
        panel = self.panels[Access.NORTH]
        self.north_token = self.north_frame = None
        stream = self.streams.get(self.urls.get(Access.NORTH))
        if stream is not None:
            stream.north_token = None
        panel.video.guides = enabled
        panel.video.picking = False
        if len(panel.video.points) != 4:
            panel.video.points = NorthCalibration().points
        panel.video.update()
        panel.help.setText("Mantén la cámara fija y marca los dos carriles antes de la cebra.")
        panel.help.setVisible(enabled)
        panel.calibrate.setVisible(enabled)
        panel.calibrate.setEnabled(enabled)
        panel.mark.setVisible(enabled)
        panel.auto_align.hide()
        if enabled and self.north_scene is not None:
            geometry = self.north_scene.geometry
            self.alignment = NorthAlignment(geometry.lane_width, geometry.stop_distance)
            for key, (x, y) in zip(self.alignment.ids, self.alignment.origins, strict=True):
                pixels = self.alignment.marker(key)
                h, w = pixels.shape
                image = QImage(
                    pixels.data, w, h, pixels.strides[0], QImage.Format.Format_Grayscale8
                )
                item = self.north_scene.addPixmap(QPixmap.fromImage(image))
                scale = self.alignment.side / self.alignment.marker_pixels
                margin = scale * self.alignment.margin
                item.setScale(scale)
                item.setPos(x - margin, y - margin)
                item.setZValue(100)
                self.markers.append(item)
            panel.video.guides = False
            panel.calibrate.hide()
            panel.help.setText("Apunta a las dos marcas de Norte con los carriles vacíos.")

    def stop_alignment(self):
        for item in self.markers:
            self.north_scene.removeItem(item)
        self.markers.clear()
        self.alignment = self.candidate = None
        self.stable_frames = 0
        self.missing_counts = 0

    def align_frame(self, panel, stream, frame):
        points = self.alignment.locate(frame.pixels)
        if self.north_token and same_guides(self.north_token.points, points):
            if frame.north_token is not self.north_token:
                return
            self.missing_counts = self.missing_counts + 1 if frame.north_count is None else 0
            if self.missing_counts < 3 or not self.north_clear():
                return
            self.candidate = None
        self.missing_counts = 0
        self.north_token = self.north_frame = stream.north_token = None
        panel.video.guides = False
        if points is None or not self.north_clear():
            self.candidate = None
            self.stable_frames = 0
            panel.help.setText(
                "Encuadra ambas marcas de Norte. Puedes ampliar el cruce o marcar a mano."
                if points is None
                else "Esperando que se vacíen los carriles de Norte para calibrar."
            )
            return
        if not same_guides(self.candidate, points):
            self.candidate = points
            self.stable_frames = 0
        self.stable_frames += 1
        panel.help.setText("Carriles localizados. Mantén la cámara quieta un momento.")
        if self.stable_frames >= 2:
            panel.video.points = points
            panel.video.guides = True
            self.calibrate_north()

    def mark_lanes(self):
        self.stop_alignment()
        panel = self.panels[Access.NORTH]
        stream = self.streams.get(self.urls.get(Access.NORTH))
        if stream:
            stream.north_token = None
        self.north_token = self.north_frame = None
        panel.video.guides = True
        panel.video.points = ()
        panel.video.picking = True
        panel.calibrate.show()
        panel.auto_align.setVisible(self.north_scene is not None)
        panel.calibrate.setEnabled(False)
        panel.help.setText("Carril 1: pulsa donde empieza la fila que quieres medir.")

    def pick_point(self, x, y):
        panel = self.panels[Access.NORTH]
        video = panel.video
        if not video.picking:
            return
        if len(video.points) % 2:
            px, py = video.points[-1]
            if abs(x - px) + abs(y - py) < 20:
                panel.help.setText("El tramo es muy corto. Pulsa más lejos sobre el mismo carril.")
                return
        video.points += ((x, y),)
        video.update()
        panel.help.setText(
            (
                "Carril 1: pulsa en el mismo carril, justo antes de la cebra.",
                "Carril 2: pulsa donde empieza la fila que quieres medir.",
                "Carril 2: pulsa en ese carril, justo antes de la cebra.",
                "Con los dos carriles vacíos, pulsa Calibrar.",
            )[len(video.points) - 1]
        )
        if len(video.points) == 4:
            video.picking = False
            panel.calibrate.setEnabled(True)

    def calibrate_north(self):
        stream = self.streams.get(self.urls.get(Access.NORTH))
        if stream and self.panels[Access.NORTH].detect.isChecked():
            self.north_frame = None
            self.north_token = stream.north_token = NorthCalibration(
                self.panels[Access.NORTH].video.points
            )
            self.panels[Access.NORTH].help.setText("Tomando la referencia de la vía vacía…")

    def north_observation(self):
        frame = self.north_frame
        if (
            frame is not None
            and frame.north_count is not None
            and frame.north_token is self.north_token
            and monotonic() - frame.timestamp <= 2
        ):
            return self.north_token, frame.north_count
        return None

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
        if source is Access.NORTH:
            self.panels[source].recognize.setChecked(False)
            self.panels[source].detect.setChecked(False)
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
                if access is Access.NORTH:
                    panel.recognize.setEnabled(True)
                    if self.recognition_token and frame.recognition_token is self.recognition_token:
                        panel.video.vehicles = frame.vehicles
                        panel.recognized.setText(
                            frame.recognition_error
                            or f"Vehículos reconocidos en la imagen: {len(frame.vehicles)}"
                        )
                    panel.detect.setEnabled(bool(com_port(url)))
                    if self.alignment is not None:
                        self.align_frame(panel, stream, frame)
                    if self.north_token is not None and frame.north_token is self.north_token:
                        self.north_frame = frame
                        panel.help.setText(
                            f"Vehículos detenidos en Norte: {frame.north_count}"
                            if frame.north_count is not None
                            else "Se usan las filas simuladas. Revisa el encuadre y la calibración."
                        )
            elif (
                access is Access.NORTH
                and self.north_frame
                and monotonic() - self.north_frame.timestamp > 2
            ):
                panel.help.setText("Lectura vencida. Se usan las filas simuladas.")
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
