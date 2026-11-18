"""Tarjeta de cámara: presenta eventos del monitoreo existente, sin inferir placas."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from sigma_vial.domain.scenario import Access
from sigma_vial.presentation.dashboard_components import ImageLabel, line_icon, soften_card
from sigma_vial.presentation.monitoring import MonitoringCenter


class CameraCard(QFrame):
    def __init__(self, owner):
        super().__init__()
        self.setObjectName("card")
        soften_card(self)
        self.controller = MonitoringCenter(owner, embedded=True)
        self.controller.mode.setCurrentIndex(3)
        self.controller.destroyed.connect(lambda: setattr(self, "controller", None))
        self.current_track = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)
        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(line_icon("camera").pixmap(28, 28))
        header.addWidget(icon)
        title = QLabel("Cámara")
        title.setObjectName("section")
        header.addWidget(title)
        self.camera = QComboBox()
        self.camera.setAccessibleName("Seleccionar cámara")
        self.camera.addItems([a.value for a in Access])
        self.camera.currentIndexChanged.connect(self.controller.plate_access.setCurrentIndex)
        header.addWidget(self.camera, 1)
        self.provenance = QLabel("Imagen sintética")
        self.provenance.setObjectName("badge")
        header.addWidget(self.provenance)
        layout.addLayout(header)
        self.picture = ImageLabel(150)
        layout.addWidget(self.picture, 1)
        read_row = QHBoxLayout()
        self.crop = ImageLabel(65)
        self.crop.setMaximumHeight(85)
        self.crop.setStyleSheet("background: #eef3f8; border-radius: 7px;")
        read_row.addWidget(self.crop, 1)
        texts = QVBoxLayout()
        self.reading = QLabel("Placa leída por OCR: —")
        self.reading.setWordWrap(True)
        self.reading.setObjectName("reading")
        self.confirmation = QLabel("Sin lectura")
        self.confirmation.setWordWrap(True)
        self.confirmation.setObjectName("confirmation")
        texts.addWidget(self.reading)
        texts.addWidget(self.confirmation)
        read_row.addLayout(texts, 2)
        layout.addLayout(read_row)
        self.record = QLabel("Sin ficha · esperando texto OCR confirmado")
        self.record.setWordWrap(True)
        self.record.setObjectName("record")
        layout.addWidget(self.record)
        self.observation = QLabel("Recorte por geometría · cámara sintética")
        self.observation.setWordWrap(True)
        self.observation.setObjectName("muted")
        layout.addWidget(self.observation)
        source_controls = QHBoxLayout()
        load = QPushButton("Abrir recorte…")
        load.clicked.connect(self.controller.load_plate_image)
        source_controls.addWidget(load)
        live = QPushButton("Cámara sintética")
        live.clicked.connect(self.controller.use_synthetic_camera)
        source_controls.addWidget(live)
        layout.addLayout(source_controls)
        self.controller.framePublished.connect(self.show_frame)
        self.controller.readingPublished.connect(self.show_reading)
        self.controller.readingFailed.connect(self.show_error)
        self.controller.sessionReset.connect(self.reset)

    def set_reading_state(self, state):
        if self.confirmation.property("state") != state:
            self.confirmation.setProperty("state", state)
            self.confirmation.style().unpolish(self.confirmation)
            self.confirmation.style().polish(self.confirmation)

    def reset(self):
        self.current_track = None
        self.set_reading_state("neutral")
        self.reading.setText("Placa leída por OCR: —")
        self.confirmation.setText("Sin lectura")
        self.record.setText("Sin ficha · esperando texto OCR confirmado")
        self.record.setToolTip("")
        self.picture.set_image(None)
        self.crop.set_image(None)

    def show_frame(self, snapshot):
        key = (snapshot.camera, snapshot.track)
        if key != self.current_track:
            self.reset()
            self.current_track = key
        image = snapshot.image.copy()
        if snapshot.plate_rect is not None:
            painter = QPainter(image)
            painter.setPen(QPen(QColor("#00d9ad"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(snapshot.plate_rect.adjusted(-5, -5, 5, 5))
            painter.end()
        self.picture.set_image(image)
        self.crop.set_image(snapshot.crop())
        imported = snapshot.camera == "imagen-importada"
        self.provenance.setText("Imagen importada" if imported else "Imagen sintética")
        self.camera.setEnabled(not imported)
        self.observation.setText(
            f"{snapshot.track or 'Sin vehículo en cobertura'} · {snapshot.timestamp:.1f} s · "
            + ("Recorte aportado por usuario" if imported else "Recorte por geometría")
        )
        if snapshot.track is None:
            self.confirmation.setText("Sin vehículo · Sin lectura")

    def show_reading(self, reading, result, snapshot):
        self.current_track = (snapshot.camera, snapshot.track)
        evidence = result.evidence
        self.set_reading_state(
            "confirmed" if evidence.confirmed else "pending" if evidence.provisional else "neutral"
        )
        self.reading.setText(
            f"Placa leída por OCR: {evidence.confirmed}"
            if evidence.confirmed
            else f"Provisional: {evidence.provisional or '—'}"
        )
        self.confirmation.setText(
            "✓  Lectura confirmada"
            if evidence.confirmed
            else f"{reading.status} · {evidence.hits}/3 observaciones"
        )
        if result.event and result.event.record:
            row = result.event.record
            color = {
                "#e66b4e": "Coral",
                "#3d87cb": "Azul",
                "#e5b84f": "Amarillo",
                "#54a582": "Verde",
                "#a574c8": "Violeta",
            }.get(row.color, row.color)
            self.record.setText(f"{row.brand} · {row.model} · {color}\nFicha del registro local")
            self.record.setToolTip(
                f"{row.plate} · {row.vehicle_type} · {row.length:g} × {row.width:g} u"
            )
        elif result.event:
            self.record.setToolTip("")
            self.record.setText(result.event.message)
        else:
            self.record.setToolTip("")
            self.record.setText("Sin ficha · esperando texto OCR confirmado")

    def show_error(self, message):
        self.set_reading_state("error")
        self.confirmation.setText("Sin lectura · OCR no disponible")
        self.confirmation.setToolTip(message)
        self.reading.setText("Placa leída por OCR: —")
        self.record.setToolTip("")
        self.record.setText("Sin ficha · no se consulta sin lectura confirmada")
