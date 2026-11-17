"""Centro de monitoreo: cuatro cámaras simuladas y laboratorio de visión por píxeles."""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sigma_vial.domain.catalog import VehicleType
from sigma_vial.domain.image_tracking import (
    ImageCalibration,
    ImageDetection,
    ImageTrack,
    ImageTracker,
)
from sigma_vial.domain.scenario import Access
from sigma_vial.presentation.geometry import from_north, rotation


class CameraView(QGraphicsView):
    def __init__(self, title):
        self.canvas = QGraphicsScene()
        super().__init__(self.canvas)
        self.title = title
        self.setMinimumSize(130, 100)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.tracks = []
        self.canvas.selectionChanged.connect(self.selection_changed)
        self.on_select = None

    def show_frame(self, picture, tracks, line_y, caption, direction=1, coverage_fraction=1):
        selected = next(
            (item.data(0) for item in self.canvas.selectedItems() if item.data(0)), None
        )
        self.canvas.blockSignals(True)
        self.canvas.clear()
        self.canvas.addPixmap(QPixmap.fromImage(picture))
        width, height = picture.width(), picture.height()
        self.canvas.setSceneRect(0, 0, width, height)
        self.canvas.addRect(
            1, 1, width - 2, height * coverage_fraction - 2, QPen(QColor("#20bfa9"), 2)
        )
        self.canvas.addLine(
            width / 2, 0, width / 2, height, QPen(QColor("#e9eef4"), 2, Qt.PenStyle.DashLine)
        )
        self.canvas.addLine(0, line_y * height, width, line_y * height, QPen(QColor("#eb70d8"), 3))
        count_label = self.canvas.addText(
            "↓ Conteo / sentido +" if direction > 0 else "↑ Conteo / sentido −"
        )
        count_label.setPos(4, line_y * height)
        count_label.setFlag(count_label.GraphicsItemFlag.ItemIgnoresTransformations)
        count_label.setDefaultTextColor(QColor("#ffffff"))
        for track in tracks:
            if track.state == "finalizado":
                continue
            x1, y1, x2, y2 = track.detection.box
            color = QColor("#e5a24e" if track.state == "perdido" else "#27eea4")
            item = self.canvas.addRect(x1, y1, x2 - x1, y2 - y1, QPen(color, 2))
            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable)
            item.setData(0, track.identifier)
            item.setSelected(track.identifier == selected)
            confidence = (
                "" if track.detection.confidence is None else f" {track.detection.confidence:.2f}"
            )
            motion = track.movement
            short_id = (
                "T" + track.identifier.rsplit("track-", 1)[-1]
                if track.identifier.startswith("virtual-")
                else track.identifier
            )
            label = self.canvas.addText(
                f"{short_id} {track.detection.category}{confidence}\n{track.state} · {motion}"
            )
            label.setFlag(label.GraphicsItemFlag.ItemIgnoresTransformations)
            label.setToolTip(track.identifier)
            label.setDefaultTextColor(color)
            label.setPos(x1, max(0, y1 - 22))
            if track.identifier == selected:
                path = QPainterPath()
                for index, (_, x, y) in enumerate(track.history):
                    if index == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)
                self.canvas.addPath(path, QPen(QColor("#fff064"), 3))
        self.setToolTip(caption)
        self.tracks = tracks
        self.canvas.blockSignals(False)
        self.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def selection_changed(self):
        selected = next(
            (item.data(0) for item in self.canvas.selectedItems() if item.data(0)), None
        )
        if self.on_select:
            track = next((t for t in self.tracks if t.identifier == selected), None)
            if track:
                self.on_select(track)


class MonitoringCenter(QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.generation = 0
        self.submitted_generation = -1
        self.setWindowTitle("SIGMA VIAL · Centro de monitoreo")
        self.resize(1150, 850)
        self.setStyleSheet(
            "QDialog, QLabel { background: #edf2f8; color: #20334d; } "
            "QGraphicsView { background: #10243d; }"
        )
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sigma-vision")
        self.future = None
        self.source = None
        self.detector = None
        self.pixel_tracker = ImageTracker()
        self.simulated_tracks = {a: {} for a in Access}
        self.session_token = id(owner.simulation.plates)
        self.selected_track = None
        self.frame_age = time.monotonic()
        self.running_video = False
        self.error = ""
        self.expanded = []
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(
            (
                "Percepción simulada",
                "Video local · píxeles",
                "Captura del simulador · prueba de píxeles",
            )
        )
        self.mode.currentIndexChanged.connect(self.change_mode)
        controls.addWidget(self.mode)
        load = QPushButton("Abrir video local")
        load.clicked.connect(self.load_video)
        controls.addWidget(load)
        sample = QPushButton("Video de demostración")
        sample.clicked.connect(self.open_demo)
        controls.addWidget(sample)
        model = QPushButton("Seleccionar modelo ONNX")
        model.clicked.connect(self.load_model)
        controls.addWidget(model)
        self.model_path = str(Path(__file__).resolve().parents[3] / "assets/vision/yolox.onnx")
        layout.addLayout(controls)
        calibration = QHBoxLayout()
        calibration.addWidget(QLabel("Calibración de imagen: línea de conteo"))
        self.line = QDoubleSpinBox()
        self.line.setRange(5, 95)
        self.line.setValue(65)
        self.line.setSuffix(" % alto")
        self.line.valueChanged.connect(self.reset_tracking)
        calibration.addWidget(self.line)
        self.direction = QComboBox()
        self.direction.addItems(("↓ Sentido +", "↑ Sentido −"))
        self.direction.currentIndexChanged.connect(self.reset_tracking)
        calibration.addWidget(self.direction)
        self.reset_button = QPushButton("Reiniciar seguimiento / video")
        self.reset_button.clicked.connect(self.reset_video)
        calibration.addWidget(self.reset_button)
        layout.addLayout(calibration)
        self.status = QLabel(
            "Percepción simulada · recuadros derivados del escenario, no del modelo."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        splitter = QSplitter(Qt.Orientation.Vertical)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        self.views = {}
        self.captions = {}
        for i, access in enumerate(Access):
            container = QWidget()
            box = QVBoxLayout(container)
            title = QLabel(f"virtual-{access.name.lower()} · {access.value}")
            title.setWordWrap(True)
            box.addWidget(title)
            self.captions[access] = title
            view = CameraView(access.value)
            view.on_select = self.describe
            self.views[access] = view
            box.addWidget(view)
            expand = QPushButton("Ampliar " + access.value)
            expand.clicked.connect(lambda checked=False, a=access: self.expand(a))
            box.addWidget(expand)
            grid.addWidget(container, i // 2, i % 2)
        splitter.addWidget(grid_widget)
        self.detail = QLabel(
            "Selecciona un recuadro: trayectoria, primera/última "
            "observación y estado. Placas reales: Sin lectura "
            "(sin OCR)."
        )
        self.detail.setWordWrap(True)
        splitter.addWidget(self.detail)
        splitter.setSizes([650, 70])
        layout.addWidget(splitter)
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh)
        self.timer.timeout.connect(
            lambda: self.describe(self.selected_track) if self.selected_track else None
        )
        self.timer.start()
        self.video_start = time.monotonic()

    def reset_tracking(self):
        self.generation += 1
        self.selected_track = None
        self.pixel_tracker = ImageTracker(
            ImageCalibration(
                line_y=self.line.value() / 100,
                direction=1 if self.direction.currentIndex() == 0 else -1,
            )
        )

    def reset_video(self):
        self.error = ""
        self.video_start = time.monotonic()
        self.running_video = self.source is not None
        self.reset_tracking()

    def change_mode(self):
        self.error = ""
        for access, view in self.views.items():
            view.canvas.clear()
            self.captions[access].setText(
                "Sin fuente de imagen asignada" if self.mode.currentIndex() else access.value
            )
        if self.future is not None and not self.future.done():
            self.status.setText("Cambio pendiente hasta terminar el fotograma en curso.")
        self.reset_tracking()

    def load_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Modelo YOLOX ONNX", "", "Modelo (*.onnx)")
        if path:
            if self.future is not None and not self.future.done():
                self.status.setText("Modelo ocupado; espera al fotograma actual.")
                return
            self.model_path = path
            self.detector = None

    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Video local · no responde a los semáforos",
            "",
            "Video (*.mp4 *.avi *.webm *.mov);;Todos (*)",
        )
        if path:
            self.open_video(path)

    def open_demo(self):
        self.direction.setCurrentIndex(1)
        self.line.setValue(65)
        self.open_video(str(Path(__file__).resolve().parents[3] / "assets/vision/traffic-demo.mp4"))

    def open_video(self, path):
        if self.future is not None and not self.future.done():
            self.status.setText("Espera al fotograma actual para cambiar el archivo.")
            return
        try:
            from sigma_vial.infrastructure.image_vision import LocalVideoSource

            self.running_video = False
            if self.source:
                self.source.close()
            self.source = None
            self.source = LocalVideoSource(path)
            self.mode.setCurrentIndex(1)
            self.reset_video()
        except Exception as exc:
            self.error = str(exc)
            self.status.setText(f"Video no disponible: {exc}")

    def render_access(self, access):
        # Capture pixels on the GUI thread. No detector receives scene/world references.

        x1, y1 = from_north(access, -116, -430)
        x2, y2 = from_north(access, 0, -130)
        source = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        picture = QImage(
            int(source.width() * 2), int(source.height() * 2), QImage.Format.Format_RGB888
        )
        picture.fill(QColor("#344353"))
        painter = QPainter(picture)
        self.owner.intersection_scene.render(
            painter,
            QRectF(0, 0, picture.width(), picture.height()),
            source,
            Qt.AspectRatioMode.IgnoreAspectRatio,
        )
        painter.end()
        return picture.transformed(QTransform().rotate(-rotation(access)))

    def simulated(self):
        sim = self.owner.simulation
        if self.session_token != id(sim.plates):
            self.simulated_tracks = {a: {} for a in Access}
            self.session_token = id(sim.plates)
        batch = sim.observations()
        for access, summary in batch.traffic.items():
            picture = self.render_access(access)
            tracks = self.simulated_tracks[access]
            camera = sim.observation_source.cameras[access]
            for d in summary.detections:
                # Bounding geometry is known scenario data ONLY in simulated mode.
                v = next(
                    (v for v in sim.vehicles if camera.track_for(v.identifier) == d.track_id), None
                )
                if not v:
                    continue
                x = (116 - 29 - 58 * d.lane) * 2
                y = d.position * 2
                detection = ImageDetection(
                    (x - v.width, y - v.length, x + v.width, y + v.length),
                    VehicleType[d.vehicle_type].value[0],
                    None,
                )
                if d.track_id not in tracks:
                    tracks[d.track_id] = ImageTrack(
                        d.track_id,
                        detection,
                        d.observed_at,
                        d.observed_at,
                        history=[(d.observed_at, x, y)],
                    )
                track = tracks[d.track_id]
                if d.observed_at > track.last_seen:
                    track.hits += 1
                    track.last_seen = d.observed_at
                    track.history.append((d.observed_at, x, y))
                    track.history[:] = track.history[-128:]
                track.detection = detection
                track.movement = d.state
                track.speed = d.speed
                track.wait = d.wait
                track.state = "confirmado" if track.hits >= 2 else "detectado"
            tracks = {k: t for k, t in tracks.items() if sim.time - t.last_seen <= 10}
            self.simulated_tracks[access] = tracks
            for track in tracks.values():
                if sim.time - track.last_seen > 0.2:
                    track.state = "finalizado" if sim.time - track.last_seen > 1.5 else "perdido"
            text = (
                f"{camera.identifier} · {summary.status.value} · "
                f"edad {sim.time - summary.observed_at:.1f} s · pasos "
                f"{summary.passage_count} · Percepción simulada"
            )
            self.captions[access].setText(text)
            self.views[access].show_frame(
                picture, list(tracks.values()), 250 / 300, text, coverage_fraction=270 / 300
            )
        self.status.setText(
            "Percepción simulada · imágenes del plano; recuadros "
            "y tipo conocidos del escenario. Velocidad en unidades "
            "simuladas; placa: Lectura simulada en el plano "
            "general."
        )

    def process_pixels(self, frame):
        from sigma_vial.infrastructure.image_vision import YoloXDetector

        if self.detector is None:
            self.detector = YoloXDetector(self.model_path)
        return frame, self.detector.detect(frame)

    def process_video(self, timestamp):
        frame = self.source.read(timestamp)
        return self.process_pixels(frame) if frame else None

    def refresh(self):
        mode = self.mode.currentIndex()
        token = id(self.owner.simulation.plates)
        if token != self.session_token:
            self.session_token = token
            self.simulated_tracks = {a: {} for a in Access}
            self.reset_tracking()
        if self.future is not None and self.future.done():
            try:
                result = self.future.result()
                if self.submitted_generation != self.generation:
                    result = "obsolete"
                if not isinstance(result, str) and result and mode == self.submitted_mode:
                    frame, detections = result
                    height, width = frame.pixels.shape[:2]
                    tracks = self.pixel_tracker.update(detections, frame.timestamp, height)
                    import cv2

                    rgb = cv2.cvtColor(frame.pixels, cv2.COLOR_BGR2RGB)
                    picture = QImage(
                        rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888
                    ).copy()
                    self.views[Access.NORTH].show_frame(
                        picture,
                        tracks,
                        self.line.value() / 100,
                        "Visión por píxeles",
                        direction=1 if self.direction.currentIndex() == 0 else -1,
                    )
                    self.frame_age = (
                        self.video_start + frame.timestamp if mode == 1 else time.monotonic()
                    )
                    self.captions[Access.NORTH].setText(
                        f"video/píxeles · imagen {frame.timestamp:.2f} s "
                        f"· pasos {self.pixel_tracker.passage_count}"
                    )
                    from sigma_vial.infrastructure.image_vision import traffic_from_tracks

                    summary = traffic_from_tracks(
                        self.pixel_tracker, Access.NORTH, frame.timestamp, width
                    )
                    queue_count = summary.queue
                    self.status.setText(
                        f"Visión por píxeles · {len(detections)} detecciones "
                        f"· velocidad px/s · placas: Sin lectura. Video local "
                        f"no reacciona a los semáforos; no está conectado "
                        f"al controlador. Cola: {queue_count}; "
                        f"ocupación: {len(summary.detections)}; "
                        f"carriles: división de imagen de demostración, requiere "
                        f"calibración real."
                    )
                elif result is None:
                    self.pixel_tracker.update([], self.pixel_tracker.last_time + 2, 1)
                    self.views[Access.NORTH].canvas.clear()
                    self.views[Access.NORTH].canvas.addText("Sin datos · fin de video")
                    self.captions[Access.NORTH].setText("Fin de video · detecciones finalizadas")
                    self.running_video = False
                    self.status.setText(
                        "Fin de video / sin imagen. Última imagen no válida como demanda actual."
                    )
            except Exception as exc:
                self.running_video = False
                self.error = str(exc)
                self.status.setText(f"Visión no disponible: {exc}")
            self.future = None
        if mode == 0:
            self.simulated()
            return
        if mode == 1 and self.running_video:
            self.captions[Access.NORTH].setText(
                f"Video local · imagen {self.pixel_tracker.last_time:.1f} s · "
                f"edad {time.monotonic() - self.frame_age:.1f} s · "
                f"pasos {self.pixel_tracker.passage_count}"
            )
        if self.future is not None:
            return  # one in-flight frame, no growing queue
        if self.error:
            return
        if mode == 1:
            if self.running_video:
                self.submitted_generation = self.generation
                self.submitted_mode = mode
                self.future = self.executor.submit(
                    self.process_video, time.monotonic() - self.video_start
                )
        else:
            try:
                import cv2
                import numpy as np

                from sigma_vial.infrastructure.image_vision import ImageFrame

                image = self.render_access(Access.NORTH)
                pixels = (
                    np.frombuffer(image.bits(), np.uint8)
                    .reshape(image.height(), image.bytesPerLine())[:, : image.width() * 3]
                    .reshape(image.height(), image.width(), 3)
                    .copy()
                )
                self.submitted_generation = self.generation
                self.submitted_mode = mode
                self.future = self.executor.submit(
                    self.process_pixels,
                    ImageFrame(cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR), self.owner.simulation.time),
                )
            except Exception as exc:
                self.error = str(exc)
                self.status.setText(f"Captura no disponible: {exc}")
        if mode == 1 and self.source is None and not self.error:
            self.status.setText(
                "Abre un video local. El video grabado no responde a los semáforos."
            )

    def describe(self, track):
        self.selected_track = track
        self.detail.setText(
            f"Observado: {track.identifier} · {track.detection.category} "
            f"· {track.state} · primera {track.first_seen:.2f} "
            f"s / última {track.last_seen:.2f} s · {len(track.history)} "
            f"puntos de trayectoria · velocidad {track.speed:.1f} "
            f"en unidades de la fuente · placa: Sin lectura en "
            f"píxeles. Datos del escenario y Lectura simulada "
            f"disponibles solo en la selección del plano."
        )

    def expand(self, access):
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.finished.connect(lambda: self.expanded.remove(dialog))
        dialog.setWindowTitle(self.views[access].title)
        dialog.resize(700, 750)
        layout = QVBoxLayout(dialog)
        view = QGraphicsView(self.views[access].canvas)
        layout.addWidget(view)
        view.fitInView(view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.expanded.append(dialog)
        dialog.show()

    def closeEvent(self, event):
        self.generation += 1
        self.timer.stop()
        for dialog in list(self.expanded):
            dialog.close()
        source = self.source
        if self.future is not None and not self.future.done():
            if source:
                self.future.add_done_callback(lambda future: source.close())
        elif source:
            source.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
