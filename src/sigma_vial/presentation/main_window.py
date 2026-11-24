"""Ventana SIGMA con controles generales y formularios de llegada independientes."""

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Phase, Scenario, Simulation, SimulationConfig, VehicleType
from sigma_vial.presentation.entity_items import PedestrianGraphicsItem, VehicleGraphicsItem
from sigma_vial.presentation.geometry import IntersectionGeometry
from sigma_vial.presentation.intersection_scene import IntersectionScene
from sigma_vial.presentation.intersection_view import IntersectionView


def text_label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SIGMA VIAL")
        self.resize(1580, 980)
        self.setMinimumSize(800, 600)
        from sigma_vial.presentation.dashboard_style import STYLE

        self.setStyleSheet(STYLE)
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        geometry = IntersectionGeometry()
        config = SimulationConfig(
            approach_extent=geometry.arm_extent,
            stop_line_distance=geometry.stop_distance,
            intersection_half=geometry.stop_distance,
            lane_length=2 * geometry.arm_extent,
            pedestrian_crossing_length=2 * geometry.road_half_width,
            vehicle_length=28,
        )
        from sigma_vial.infrastructure.vehicle_registry import SQLiteVehicleRegistry, registry_path

        self.registry = SQLiteVehicleRegistry(registry_path())
        self.simulation = Simulation(config=config, registry=self.registry)
        self.simulation_timer = QTimer(self)
        self.simulation_timer.setInterval(50)
        self.simulation_timer.timeout.connect(self._advance_simulation)
        self.has_started = False
        self.intersection_scene = IntersectionScene(self, geometry)
        self.intersection_view = IntersectionView(self.intersection_scene)
        self.intersection_scene.selectionChanged.connect(self._show_vehicle_details)
        self.coverage_items = []
        self._create_sensor_overlays()
        self.vehicle_items = {}
        self.pedestrian_items = {}
        outer.addWidget(self._general_controls())
        from sigma_vial.presentation.dashboard_components import DashboardBody

        self.body_content = DashboardBody()
        self.body = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.body_content)
        body = self.body
        body.setContentsMargins(12, 14, 12, 14)
        body.setSpacing(16)
        scene_card = QFrame()
        self.scene_card = scene_card
        scene_card.setObjectName("card")
        scene_layout = QVBoxLayout(scene_card)
        scene_layout.setContentsMargins(14, 12, 14, 12)
        view_bar = QHBoxLayout()
        from sigma_vial.presentation.dashboard_components import line_icon, soften_card

        soften_card(scene_card)
        road_icon = QLabel()
        road_icon.setPixmap(line_icon("road").pixmap(28, 28))
        view_bar.addWidget(road_icon)
        view_bar.addWidget(text_label("Intersección en vivo", "section"), 1)
        for title, action in (
            ("−", self.intersection_view.zoom_out),
            ("Restablecer", self.intersection_view.reset_view),
            ("+", self.intersection_view.zoom_in),
        ):
            button = QPushButton(title)
            button.clicked.connect(action)
            view_bar.addWidget(button)
        scene_layout.addLayout(view_bar)
        scene_layout.addWidget(self.intersection_view, 1)
        summary_row = QHBoxLayout()
        self.ns_summary = text_label("N–S: 0 vehículos", "summary")
        self.ew_summary = text_label("O–O: 0 vehículos", "summary")
        self.ped_summary = text_label("0 peatones", "summary")
        self.overview = text_label("", "decision")
        for label in (self.ns_summary, self.ew_summary, self.ped_summary):
            summary_row.addWidget(label, 1)
        summary_row.addWidget(self.overview, 2)
        scene_layout.addLayout(summary_row)
        body.addWidget(scene_card, 2)
        self.side_panel = self._sidebar()
        body.addWidget(self.side_panel, 1)
        self.body_scroll = self._scroll_content(self.body_content)
        self.body_scroll.setObjectName("bodyScroll")
        self.body_scroll.viewport().installEventFilter(self)
        outer.addWidget(self.body_scroll, 1)
        self.setCentralWidget(root)
        self._refresh_simulation()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "body"):
            return
        compact = self.width() < 1100
        self.body.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        self.side_panel.setMinimumHeight(760 if compact else 0)
        self.subtitle.setVisible(not compact)
        self.tabs.setMaximumHeight(320 if self.tabs.currentIndex() else 205)
        self._resize_scene_card()

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Resize
            and hasattr(self, "body_scroll")
            and watched is self.body_scroll.viewport()
        ):
            self._resize_scene_card()
        return super().eventFilter(watched, event)

    def _resize_scene_card(self) -> None:
        if self.body.direction() == QBoxLayout.Direction.TopToBottom:
            available = self.body_scroll.viewport().height() - self.body.contentsMargins().top()
            self.scene_card.setFixedHeight(max(360, available))
        else:
            self.scene_card.setMinimumHeight(0)
            self.scene_card.setMaximumHeight(16777215)

    def _highlight_camera_target(self, snapshot):
        from PySide6.QtGui import QPen

        if not hasattr(self, "camera_target"):
            self.camera_target = self.intersection_scene.addRect(
                QRectF(), QPen(QColor("#00d7ac"), 3)
            )
            self.camera_target.setZValue(30)
        identifier = snapshot.track.rsplit("-vehicle-", 1)[-1] if snapshot.track else ""
        self.camera_target_id = int(identifier) if identifier.isdigit() else None
        item = self.vehicle_items.get(self.camera_target_id)
        self.camera_target.setVisible(item is not None)
        if item is not None:
            self.camera_target.setRect(item.sceneBoundingRect().adjusted(-5, -5, 5, 5))

    def _header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 12, 22, 12)
        from sigma_vial.presentation.dashboard_components import SigmaMark

        layout.addWidget(SigmaMark())
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(text_label("SIGMA VIAL", "title"))
        brand.addWidget(text_label("SIGMA SOFTWARE SOLUTIONS", "company"))
        layout.addLayout(brand)
        self.subtitle = text_label(
            "Simulación inteligente de tráfico e identificación de placas", "subtitle"
        )
        layout.addWidget(self.subtitle, 1)
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #94a8bf; font-size: 25px;")
        layout.addStretch(1)
        layout.addWidget(self.status_dot)
        self.status_label = text_label("Vista inicial · Simulación detenida", "status")
        self.status_label.setFixedWidth(190)
        layout.addWidget(self.status_label)
        return header

    def _toggle_running(self) -> None:
        self.simulation.running = not self.simulation.running
        self.has_started = self.has_started or self.simulation.running
        if self.simulation.running:
            self.simulation_timer.start()
        else:
            self.simulation_timer.stop()
        self._refresh_simulation()

    def _advance_simulation(self) -> None:
        self.simulation.advance(0.05 * float(self.speed.currentData()))
        self._sync_entities()
        self._sync_signals()
        self._refresh_simulation()

    def _sync_signals(self) -> None:
        for indicator in self.intersection_scene.pedestrian_signals.values():
            indicator.admission = self.simulation.phase is Phase.WALK
            indicator.update()
        colors = {"Rojo": "#a6283b", "Amarillo": "#a56800", "Verde": "#17804b"}
        backgrounds = {"Rojo": "#fff0f2", "Amarillo": "#fff7df", "Verde": "#e8f8ef"}
        for access, state in self.simulation.signals.items():
            self.intersection_scene.traffic_lights[access].set_state(state)
            label = self.signal_labels[access]
            label.setText(f"●  {access.value}  ·  {state.value}")
            label.setStyleSheet(
                f"color: {colors[state.value]}; background: {backgrounds[state.value]};"
                "padding: 9px; border-radius: 6px; font-size: 14px; font-weight: 600;"
            )

    def _sync_entities(self) -> None:
        active = {vehicle.identifier for vehicle in self.simulation.vehicles}
        for identifier in self.vehicle_items.keys() - active:
            self.intersection_scene.removeItem(self.vehicle_items.pop(identifier))
        for vehicle in self.simulation.vehicles:
            item = self.vehicle_items.get(vehicle.identifier)
            if item is None:
                item = VehicleGraphicsItem(
                    vehicle.identifier, vehicle.length, vehicle.width, vehicle.kind
                )
                item.setRotation(
                    {Access.NORTH: 90, Access.SOUTH: 270, Access.EAST: 180, Access.WEST: 0}[
                        vehicle.access
                    ]
                )
                item.setZValue(15)
                self.intersection_scene.addItem(item)
                self.vehicle_items[vehicle.identifier] = item
            item.color = QColor(vehicle.color)
            item.plate = vehicle.plate
            item.setToolTip(
                f"Datos del escenario · {vehicle.plate} · {vehicle.kind.value[0]} "
                f"· {vehicle.brand} {vehicle.model}"
            )
            distance = vehicle.position
            lane = -self.intersection_scene.geometry.lane_width * (0.5 + vehicle.lane)
            extent = self.simulation.config.approach_extent
            positions = {
                Access.NORTH: (lane, -extent + distance),
                Access.SOUTH: (-lane, extent - distance),
                Access.EAST: (extent - distance, lane),
                Access.WEST: (-extent + distance, -lane),
            }
            item.setPos(*positions[vehicle.access])

        if hasattr(self, "camera_target"):
            target = self.vehicle_items.get(getattr(self, "camera_target_id", None))
            self.camera_target.setVisible(target is not None)
            if target is not None:
                self.camera_target.setRect(target.sceneBoundingRect().adjusted(-5, -5, 5, 5))
        active = {person.identifier for person in self.simulation.pedestrians}
        for identifier in self.pedestrian_items.keys() - active:
            self.intersection_scene.removeItem(self.pedestrian_items.pop(identifier))
        for person in self.simulation.pedestrians:
            item = self.pedestrian_items.get(person.identifier)
            if item is None:
                item = PedestrianGraphicsItem()
                self.intersection_scene.addItem(item)
                self.pedestrian_items[person.identifier] = item
            item.walking = person.walking
            item.update()
            item.setPos(*self._pedestrian_position(person))

    def _pedestrian_position(self, person) -> tuple[float, float]:
        geometry = self.intersection_scene.geometry
        if not person.walking:
            waiting = [
                p
                for p in self.simulation.pedestrians
                if p.crossing is person.crossing and not p.walking
            ]
            index = waiting.index(person)
            progress = -geometry.road_half_width - 8 - (index % 2) * 14
            offset = 4 + (index // 2) * 15
        else:
            progress = person.position - geometry.road_half_width
            offset = person.lane
        near = geometry.crossing_near
        if person.crossing is Access.NORTH:
            return progress, -near - offset
        if person.crossing is Access.SOUTH:
            return -progress, near + offset
        if person.crossing is Access.EAST:
            return near + offset, progress
        return -near - offset, -progress

    def _refresh_simulation(self) -> None:
        sim = self.simulation
        batch = sim.observations()
        if hasattr(self, "sensor_status"):
            lines = []
            for access, summary in batch.traffic.items():
                counts = {}
                for detection in summary.detections:
                    kind = VehicleType.__members__.get(detection.vehicle_type)
                    name = kind.value[0] if kind else "Desconocido"
                    counts[name] = counts.get(name, 0) + 1
                status = (
                    summary.status.value
                    if sim.time - summary.observed_at <= sim.sensor_timeout
                    else "Lectura vencida"
                )
                lines.append(
                    f"{access.value}: {status} "
                    f"· lectura {summary.observed_at:.1f} s · ocupación {len(summary.detections)} "
                    f"· cola {summary.queue} · paso histórico {summary.passage_count} "
                    f"· tipos {counts}"
                )
            self.sensor_status.setText(
                "Detección simulada · umbral detenido ≤ 0,5 u/s\n" + "\n".join(lines)
            )
        ns = (Access.NORTH, Access.SOUTH)
        ew = (Access.EAST, Access.WEST)
        ns_demand = sum(batch.traffic[access].demand for access in ns)
        ew_demand = sum(batch.traffic[access].demand for access in ew)
        ns_stopped = sum(batch.traffic[access].queue for access in ns)
        ew_stopped = sum(batch.traffic[access].queue for access in ew)
        crossing = sum(p.walking for p in sim.pedestrians)
        pedestrian_waits = [p.wait for p in sim.pedestrians if not p.walking]
        self.ns_summary.setText(f"N–S: {ns_demand} vehículos")
        self.ew_summary.setText(f"O–O: {ew_demand} vehículos")
        self.ped_summary.setText(f"{sim.pedestrian_waiting()} peatones esperando")
        pending = sim._pending_phase
        title = f"Próximo turno: {pending.value}" if pending else sim.phase.value
        self.overview.setText(f"{title}\n{sim.decision}")
        self.overview.setToolTip(
            f"En cola N–S: {ns_stopped} / O–O: {ew_stopped} · {crossing} peatones cruzando"
        )
        seconds = int(sim.time)
        self.clock_label.setText(
            f"Reloj simulado: {seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
        )
        self.status_dot.setStyleSheet(
            f"color: {'#12c990' if sim.running else '#f1bd54' if self.has_started else '#94a8bf'};"
            "font-size: 25px;"
        )
        self.metrics.setText(
            f"Demanda pendiente · Norte–Sur: {ns_demand} "
            f"(detenidos {ns_stopped}, aproximándose {ns_demand - ns_stopped}) · "
            f"Oriente–Occidente: {ew_demand} "
            f"(detenidos {ew_stopped}, aproximándose {ew_demand - ew_stopped})\n"
            f"Saliendo · Norte–Sur: {sim.exiting_vehicles(ns)} · "
            f"Oriente–Occidente: {sim.exiting_vehicles(ew)}\n"
            f"Mayor espera por eje · Norte–Sur: {sim.axis_wait('ns'):.1f} s · "
            f"Oriente–Occidente: {sim.axis_wait('ew'):.1f} s · "
            f"peatón: {max(pedestrian_waits, default=0):.1f} s\n"
            f"Verde transcurrido: {sim.green_elapsed:.1f} s · Motivo: {sim.decision} · "
            f"Completados: {sim.completed_vehicles}"
        )
        self._show_vehicle_details()
        self.start_button.setText(
            "Pausar" if sim.running else ("Continuar" if self.has_started else "Iniciar")
        )
        self.status_label.setText(
            "Simulación activa"
            if sim.running
            else "Simulación en pausa"
            if self.has_started
            else "Vista inicial · Simulación detenida"
        )

    def _reset_simulation(self) -> None:
        self.simulation_timer.stop()
        self.simulation.reset()
        self._set_sensor_interval(self.sensor_interval.value())
        self.has_started = False
        self._sync_signals()
        self._clear_entity_items()
        self._sync_rate_fields()
        self._refresh_simulation()
        self.camera_card.controller.reset_tracking()
        self.camera_card.reset()
        if hasattr(self, "camera_target"):
            self.camera_target.hide()

    def _clear_entity_items(self) -> None:
        for item in (*self.vehicle_items.values(), *self.pedestrian_items.values()):
            self.intersection_scene.removeItem(item)
        if hasattr(self, "camera_target"):
            self.camera_target.hide()
        self.vehicle_items.clear()
        self.pedestrian_items.clear()

    def _load_scenario(self) -> None:
        self.simulation_timer.stop()
        self._clear_entity_items()
        self.camera_card.controller.reset_tracking()
        self.simulation.load_scenario(self.scenario_combo.currentData())
        self._set_sensor_interval(self.sensor_interval.value())
        self._sync_entities()
        self._sync_signals()
        self.has_started = False
        self._sync_rate_fields()
        self.profile_combo.setCurrentIndex(4)
        self.automatic_toggle.setChecked(self.simulation.automatic_generation)
        self.vehicle_type.setCurrentIndex(
            self.vehicle_type.findData(self.simulation.selected_vehicle_type)
        )
        self.heavy_share.setValue(10)
        self._refresh_simulation()

    def _add_vehicle(self, access: Access) -> None:
        self.simulation.add_vehicle(access)
        self._sync_entities()
        self._refresh_simulation()

    def _add_pedestrian(self, access: Access) -> None:
        self.simulation.add_pedestrian(access)
        self._sync_entities()
        self._refresh_simulation()

    def _general_controls(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("controls")
        row = QHBoxLayout(bar)
        row.setContentsMargins(22, 10, 22, 10)
        self.start_button = QPushButton("Iniciar")
        self.start_button.setObjectName("primaryAction")
        self.start_button.setMinimumWidth(90)
        self.start_button.clicked.connect(self._toggle_running)
        row.addWidget(self.start_button)
        reset = QPushButton("Reiniciar")
        reset.clicked.connect(self._reset_simulation)
        row.addWidget(reset)
        row.addWidget(text_label("Velocidad"))
        self.speed = QComboBox()
        for value in (0.5, 1, 2, 4):
            self.speed.addItem(f"{value:g}×", value)
        self.speed.setCurrentIndex(1)
        row.addWidget(self.speed)
        self.clock_label = text_label("Reloj simulado: 00:00:00", "clock")
        row.addWidget(self.clock_label, 1)
        monitoring = QPushButton("Centro de monitoreo")
        monitoring.clicked.connect(self._open_monitoring)
        row.addWidget(monitoring)
        return bar

    @staticmethod
    def _scroll_content(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def _fold(self, layout, title, content):
        button = QToolButton()
        button.setText(title + "  ▸")
        button.setCheckable(True)
        button.toggled.connect(lambda checked: self._toggle_panel(button, content, checked))
        content.hide()
        layout.addWidget(button)
        layout.addWidget(content)

    @staticmethod
    def _type_combo():
        combo = QComboBox()
        combo.setMinimumContentsLength(10)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.addItem("Aleatorio", None)
        for kind in VehicleType:
            combo.addItem(kind.value[0], kind)
        return combo

    def _queue_counts(self):
        traffic = self.simulation.observations().traffic
        return tuple(
            traffic[a].queue for a in (Access.NORTH, Access.SOUTH, Access.EAST, Access.WEST)
        )

    def _sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        from sigma_vial.presentation.dashboard_components import DashboardTabs

        self.tabs = DashboardTabs()
        self.tabs.setMinimumHeight(165)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.currentChanged.connect(
            lambda index: self.tabs.setMaximumHeight(320 if index else 205)
        )
        self.tabs.addTab(self._automatic_form(), "Automático")
        self.tabs.addTab(self._manual_form(), "Agregar")
        automatic_card = QFrame()
        automatic_card.setObjectName("card")
        from sigma_vial.presentation.dashboard_components import soften_card

        soften_card(automatic_card)
        automatic_layout = QVBoxLayout(automatic_card)
        automatic_layout.setContentsMargins(12, 8, 12, 8)
        automatic_layout.addWidget(self.tabs)
        automatic_layout.addWidget(text_label("ⓘ  Los semáforos deciden automáticamente.", "muted"))
        layout.addWidget(automatic_card)
        from sigma_vial.presentation.camera_card import CameraCard
        from sigma_vial.presentation.wifi_panel import WifiPanel

        self.wifi_panel = WifiPanel(self._queue_counts)
        layout.addWidget(self.wifi_panel)
        self.camera_card = CameraCard(self)
        self.camera_card.controller.framePublished.connect(self._highlight_camera_target)
        layout.addWidget(self.camera_card, 1)
        diagnostics = QWidget()
        info_layout = QVBoxLayout(diagnostics)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)
        self.details_panel = QWidget()
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(4, 4, 4, 4)
        self.signal_labels = {}
        for access, light in self.intersection_scene.traffic_lights.items():
            label = text_label(f"● {access.value} · {light.state.value}", "signal")
            self.signal_labels[access] = label
            details_layout.addWidget(label)
        self.metrics = text_label("", "muted")
        details_layout.addWidget(self.metrics)
        self._fold(info_layout, "Detalles y semáforos", self.details_panel)
        sensor_toggle = QToolButton()
        sensor_toggle.setText("Sensores  ▸")
        sensor_toggle.setCheckable(True)
        self.sensor_panel = QWidget()
        sensor_layout = QVBoxLayout(self.sensor_panel)
        self.sensor_status = text_label("Cámaras virtuales · sin lectura", "muted")
        sensor_layout.addWidget(self.sensor_status)
        coverage = QCheckBox("Mostrar cobertura y líneas de conteo")
        coverage.toggled.connect(
            lambda checked: [item.setVisible(checked) for item in self.coverage_items]
        )
        sensor_layout.addWidget(coverage)
        self.sensor_interval = QDoubleSpinBox()
        self.sensor_interval.setRange(0.05, 1)
        self.sensor_interval.setSingleStep(0.05)
        self.sensor_interval.setValue(0.1)
        self.sensor_interval.setSuffix(" s / lectura")
        self.sensor_interval.valueChanged.connect(self._set_sensor_interval)
        sensor_layout.addWidget(self.sensor_interval)
        self.vehicle_details = text_label("Selecciona un vehículo para inspeccionarlo.", "muted")
        sensor_layout.addWidget(self.vehicle_details)
        self.sensor_panel.hide()
        sensor_toggle.toggled.connect(
            lambda checked: self._toggle_panel(sensor_toggle, self.sensor_panel, checked)
        )
        info_layout.addWidget(sensor_toggle)
        info_layout.addWidget(self.sensor_panel)

        self.demo_panel = QWidget()
        demo_layout = QVBoxLayout(self.demo_panel)
        demo_layout.setContentsMargins(4, 4, 4, 4)
        demo_layout.addWidget(
            text_label(
                "Cargar una demostración borra las entidades, reinicia el reloj "
                "y deja la simulación detenida.",
                "muted",
            )
        )
        self.scenario_combo = QComboBox()
        for scenario in tuple(Scenario)[4:]:
            self.scenario_combo.addItem(scenario.value, scenario)
        demo_layout.addWidget(self.scenario_combo)
        load = QPushButton("Cargar demostración")
        load.clicked.connect(self._load_scenario)
        demo_layout.addWidget(load)
        self._fold(info_layout, "Demostraciones y pruebas", self.demo_panel)
        info_layout.addStretch()
        for button in diagnostics.findChildren(QToolButton):
            button.setStyleSheet("padding: 5px 8px; font-size: 12px;")
        diagnostic_scroll = self._scroll_content(diagnostics)
        diagnostic_scroll.setMinimumHeight(70)
        diagnostic_scroll.setMaximumHeight(220)
        self._fold(layout, "Herramientas: detalles, sensores y pruebas", diagnostic_scroll)
        panel.setMinimumWidth(330)
        return panel

    def _automatic_form(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)
        from sigma_vial.presentation.dashboard_components import TrafficSwitch

        self.automatic_toggle = TrafficSwitch("Generar tráfico automáticamente")
        self.automatic_toggle.setChecked(self.simulation.automatic_generation)
        self.automatic_toggle.toggled.connect(self._set_automatic)
        layout.addWidget(self.automatic_toggle)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumContentsLength(12)
        self.profile_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.profile_combo.addItems(
            (
                "Equilibrado",
                "Mayor tráfico Norte–Sur",
                "Mayor tráfico Oriente–Occidente",
                "Más peatones",
                "Personalizado",
            )
        )
        form.addRow("Perfil de tráfico", self.profile_combo)
        layout.addLayout(form)
        self.advanced_panel = QWidget()
        advanced = QVBoxLayout(self.advanced_panel)
        rates_form = QFormLayout()
        rates_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form = rates_form
        self.demand_controls = {}
        for access in Access:
            rate = QDoubleSpinBox()
            rate.setRange(0, 60)
            rate.setValue(self.simulation.vehicle_rates[access])
            rate.setSuffix(" veh/min")
            rate.valueChanged.connect(
                lambda value, access=access: self._edit_vehicle_rate(access, value)
            )
            self.demand_controls[access] = rate
            form.addRow(access.value, rate)
        self.pedestrian_rate = QDoubleSpinBox()
        self.pedestrian_rate.setRange(0, 60)
        self.pedestrian_rate.setValue(self.simulation.pedestrian_rate)
        self.pedestrian_rate.setSuffix(" pers/min")
        self.pedestrian_rate.valueChanged.connect(self._edit_pedestrian_rate)
        form.addRow("Peatones", self.pedestrian_rate)
        self.vehicle_type = self._type_combo()
        self.simulation.selected_vehicle_type = None
        self.vehicle_type.currentIndexChanged.connect(
            lambda: setattr(
                self.simulation, "selected_vehicle_type", self.vehicle_type.currentData()
            )
        )
        form.addRow("Tipos", self.vehicle_type)
        self.heavy_share = QDoubleSpinBox()
        self.heavy_share.setRange(0, 100)
        self.heavy_share.setValue(10)
        self.heavy_share.setSuffix(" %")
        self.heavy_share.valueChanged.connect(self._set_mix)
        form.addRow("Buses/camiones", self.heavy_share)
        advanced.addLayout(form)
        advanced.addWidget(
            text_label(
                "Al desactivar: se congela el progreso de nuevas llegadas. "
                "Las solicitudes pendientes se incorporan cuando haya espacio, "
                "conservando su tipo. No hay recuperación masiva de llegadas al activar.",
                "muted",
            )
        )
        self._fold(layout, "Ajustes avanzados", self.advanced_panel)
        self.profile_combo.currentIndexChanged.connect(self._apply_profile)
        return self._scroll_content(content)

    def _manual_form(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.addWidget(text_label("Vehículos", "section"))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.manual_access = QComboBox()
        self.pedestrian_access = QComboBox()
        for access in Access:
            self.manual_access.addItem(access.value, access)
            self.pedestrian_access.addItem(access.value, access)
        self.manual_type = self._type_combo()
        self.manual_count = QSpinBox()
        self.manual_count.setRange(1, 100)
        form.addRow("Acceso", self.manual_access)
        form.addRow("Tipo", self.manual_type)
        form.addRow("Cantidad", self.manual_count)
        layout.addLayout(form)
        add = QPushButton("Agregar vehículos")
        add.clicked.connect(self._add_manual_vehicles)
        layout.addWidget(add)
        layout.addWidget(text_label("Peatones", "section"))
        pedestrians = QFormLayout()
        pedestrians.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.manual_pedestrian_count = QSpinBox()
        self.manual_pedestrian_count.setRange(1, 100)
        pedestrians.addRow("Paso peatonal", self.pedestrian_access)
        pedestrians.addRow("Cantidad", self.manual_pedestrian_count)
        layout.addLayout(pedestrians)
        add_pedestrians = QPushButton("Agregar peatones")
        add_pedestrians.clicked.connect(self._add_manual_pedestrians)
        layout.addWidget(add_pedestrians)
        self.manual_result = text_label(
            "Se pueden agregar entidades con generación automática encendida o apagada.", "muted"
        )
        layout.addWidget(self.manual_result)
        layout.addStretch()
        return self._scroll_content(content)

    def _set_automatic(self, enabled):
        self.simulation.automatic_generation = enabled
        self._refresh_simulation()

    def _set_mix(self, value):
        self.simulation.vehicle_mix = tuple(
            (100 - value) * weight / 90 for weight in (12, 30, 25, 15, 8)
        ) + (value * 0.4, value * 0.4, value * 0.2)

    def _edit_vehicle_rate(self, access, value):
        self.simulation.set_demand(access, value)
        self.profile_combo.setCurrentIndex(4)

    def _edit_pedestrian_rate(self, value):
        self.simulation.pedestrian_rate = value
        self.profile_combo.setCurrentIndex(4)

    def _apply_profile(self, index):
        profiles = (
            (12, 12, 12, 12, 2.4),
            (18, 18, 3, 3, 2.4),
            (3, 3, 18, 18, 2.4),
            (4, 4, 4, 4, 12),
        )
        if index >= len(profiles):
            return
        values = profiles[index]
        self.simulation.vehicle_rates = dict(zip(Access, values[:4], strict=True))
        self.simulation.pedestrian_rate = values[4]
        self._sync_rate_fields()

    def _sync_rate_fields(self):
        for access, control in self.demand_controls.items():
            control.blockSignals(True)
            control.setValue(self.simulation.vehicle_rates[access])
            control.blockSignals(False)
        self.pedestrian_rate.blockSignals(True)
        self.pedestrian_rate.setValue(self.simulation.pedestrian_rate)
        self.pedestrian_rate.blockSignals(False)

    def _add_manual_vehicles(self):
        previous = self.simulation.selected_vehicle_type
        self.simulation.selected_vehicle_type = self.manual_type.currentData()
        inserted = 0
        count = self.manual_count.value()
        try:
            for _ in range(count):
                inserted += self.simulation.add_vehicle(self.manual_access.currentData())
        finally:
            self.simulation.selected_vehicle_type = previous
        self.manual_result.setText(
            f"Vehículos: {inserted} incorporados · {count - inserted} solicitudes "
            "pendientes por falta de espacio."
        )
        self._sync_entities()
        self._refresh_simulation()

    def _add_manual_pedestrians(self):
        count = self.manual_pedestrian_count.value()
        for _ in range(count):
            self.simulation.add_pedestrian(self.pedestrian_access.currentData())
        self.manual_result.setText(
            f"Peatones: {count} incorporados en la acera · 0 solicitudes pendientes."
        )
        self._sync_entities()
        self._refresh_simulation()

    @staticmethod
    def _toggle_panel(button: QToolButton, panel: QWidget, expanded: bool) -> None:
        panel.setVisible(expanded)
        button.setText(
            button.text().replace("▸", "▾") if expanded else button.text().replace("▾", "▸")
        )

    def _set_sensor_interval(self, value):
        for camera in self.simulation.observation_source.cameras.values():
            camera.interval = value

    def _create_sensor_overlays(self):
        from PySide6.QtGui import QBrush, QColor, QPen

        from sigma_vial.presentation.geometry import rotation

        extent = self.simulation.config.approach_extent
        half_width = self.intersection_scene.geometry.road_half_width
        for access in Access:
            camera = self.simulation.observation_source.cameras[access]
            zone = self.intersection_scene.addRect(
                -half_width,
                camera.start - extent,
                half_width,
                camera.end - camera.start,
                QPen(QColor("#279db1"), 2),
                QBrush(QColor(30, 170, 190, 35)),
            )
            zone.setRotation(rotation(access))
            zone.setZValue(2)
            count_y = camera.count_line - extent
            line = self.intersection_scene.addLine(
                -half_width, count_y, 0, count_y, QPen(QColor("#dd75bd"), 3)
            )
            line.setRotation(rotation(access))
            line.setZValue(3)
            for item in (zone, line):
                item.hide()
                self.coverage_items.append(item)

    def _show_vehicle_details(self):
        if not hasattr(self, "vehicle_details"):
            return
        selected = self.intersection_scene.selectedItems()
        for vehicle in self.simulation.vehicles:
            if self.vehicle_items.get(vehicle.identifier) in selected:
                detections = [
                    d
                    for summary in self.simulation.observations().traffic.values()
                    for d in summary.detections
                ]
                camera = self.simulation.observation_source.cameras[vehicle.access]
                track_id = camera.track_for(vehicle.identifier)
                detection = next((d for d in detections if d.track_id == track_id), None)
                self.vehicle_details.setText(
                    f"Datos del escenario: {vehicle.plate} · {vehicle.kind.value[0]} "
                    f"· {vehicle.brand} · {vehicle.model}\n"
                    + (
                        f"Detección simulada: {detection.track_id} · {detection.state} "
                        f"· Lectura simulada: {detection.plate}"
                        if detection
                        else "Sin detección activa en cobertura."
                    )
                )
                return
        self.vehicle_details.setText("Selecciona un vehículo para inspeccionarlo.")

    def _open_monitoring(self):
        from sigma_vial.presentation.monitoring import MonitoringCenter

        if getattr(self, "monitoring_center", None) is None:
            self.monitoring_center = MonitoringCenter(self)
            self.monitoring_center.destroyed.connect(
                lambda: setattr(self, "monitoring_center", None)
            )
        self.monitoring_center.show()
        self.monitoring_center.raise_()

    def closeEvent(self, event):
        self.wifi_panel.disconnect_device()
        self.simulation_timer.stop()
        if self.camera_card.controller is not None:
            self.camera_card.controller.close()
        if getattr(self, "monitoring_center", None) is not None:
            self.monitoring_center.close()
        super().closeEvent(event)
