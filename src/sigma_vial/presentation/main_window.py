"""Ventana del escenario estático: composición visual y controles de encuadre."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Scenario, Simulation, SimulationConfig
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
        self.resize(1240, 860)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QMainWindow, QWidget#root { background: #edf2f8; color: #20334d; }
            QLabel { color: #20334d; font-family: 'Segoe UI'; font-size: 14px; }
            QFrame#header { background: #11243e; border-radius: 12px; }
            QLabel#title { color: white; font-size: 27px; font-weight: 700; }
            QLabel#company { color: #a8c7ec; font-size: 12px; font-weight: 600; }
            QLabel#status { color: #d7e9ff; background: #223c5e;
                border-radius: 8px; padding: 10px; font-size: 13px; }
            QFrame#card { background: white; border: 1px solid #d6e0ec; border-radius: 12px; }
            QLabel#section { color: #1c416f; font-size: 16px; font-weight: 700; }
            QLabel#muted { color: #63758b; font-size: 12px; }
            QLabel#signal { color: #a6283b; background: #fff0f2;
                padding: 9px; border-radius: 6px; font-size: 14px; }
            QPushButton { color: #1a477f; background: #edf4ff; border: 1px solid #c5d9f3;
                padding: 9px; border-radius: 7px; font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton:hover { background: #dceaff; border-color: #659ada; }
            QPushButton:pressed { background: #c9defa; }
            QPushButton:focus { border: 2px solid #326db7; }
            QPushButton#primaryAction { color: white; background: #1768ad;
                border-color: #1768ad; font-weight: 700; }
            QPushButton#primaryAction:hover { background: #0f568f; }
            QLabel#overview { background: #edf5ff; border: 1px solid #d0e3f8;
                border-radius: 8px; padding: 11px; font-size: 13px; font-weight: 600; }
            QToolButton { color: #1a477f; background: #f5f8fc; border: 1px solid #d6e0ec;
                padding: 9px; border-radius: 7px; text-align: left; font-weight: 600; }
            QComboBox, QDoubleSpinBox { color: #20334d; background: white;
                border: 1px solid #c5d9f3; padding: 5px 8px; border-radius: 6px;
                min-height: 24px; }
            QComboBox::drop-down { border: none; width: 22px; }
            QComboBox QAbstractItemView { color: #20334d; background: white;
                selection-background-color: #dceaff; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #e4ebf4; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #9bb0cb; min-height: 32px;
                border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(16)
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
        self.simulation = Simulation(config=config)
        self.simulation_timer = QTimer(self)
        self.simulation_timer.setInterval(50)
        self.simulation_timer.timeout.connect(self._advance_simulation)
        self.has_started = False
        self.intersection_scene = IntersectionScene(self, geometry)
        self.intersection_view = IntersectionView(self.intersection_scene)
        self.vehicle_items = {}
        self.pedestrian_items = {}
        body = QHBoxLayout()
        body.setSpacing(16)
        scene_card = QFrame()
        scene_card.setObjectName("card")
        scene_layout = QVBoxLayout(scene_card)
        scene_layout.setContentsMargins(16, 16, 16, 16)
        scene_layout.addWidget(text_label("Intersección · Vista superior", "section"))
        scene_layout.addWidget(self.intersection_view, 1)
        scene_layout.addWidget(
            text_label("Movimientos rectos · Circulación por la derecha", "muted")
        )
        body.addWidget(scene_card, 1)
        body.addWidget(self._sidebar())
        outer.addLayout(body, 1)
        self.setCentralWidget(root)

    def _header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 17, 22, 17)
        brand = QVBoxLayout()
        brand.setSpacing(4)
        brand.addWidget(text_label("SIGMA VIAL", "title"))
        brand.addWidget(text_label("SIGMA SOFTWARE SOLUTIONS", "company"))
        layout.addLayout(brand, 1)
        self.status_label = text_label("Vista inicial · Simulación detenida", "status")
        self.status_label.setMaximumWidth(330)
        self.status_label.setMinimumWidth(290)
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
                item = VehicleGraphicsItem(vehicle.identifier)
                item.setRotation(
                    {Access.NORTH: 90, Access.SOUTH: 270, Access.EAST: 180, Access.WEST: 0}[
                        vehicle.access
                    ]
                )
                item.setZValue(15)
                self.intersection_scene.addItem(item)
                self.vehicle_items[vehicle.identifier] = item
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

        active = {person.identifier for person in self.simulation.pedestrians}
        for identifier in self.pedestrian_items.keys() - active:
            self.intersection_scene.removeItem(self.pedestrian_items.pop(identifier))
        for person in self.simulation.pedestrians:
            item = self.pedestrian_items.get(person.identifier)
            if item is None:
                item = PedestrianGraphicsItem()
                self.intersection_scene.addItem(item)
                self.pedestrian_items[person.identifier] = item
            item.setPos(*self._pedestrian_position(person))

    def _pedestrian_position(self, person) -> tuple[float, float]:
        geometry = self.intersection_scene.geometry
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
        queue = " · ".join(f"{a.value}: {sim.waiting(a)}" for a in Access)
        crossing = sum(p.walking for p in sim.pedestrians)
        pedestrian_waits = [p.wait for p in sim.pedestrians if not p.walking]
        self.overview.setText(
            f"{sim.phase.value}\nFase {sim.phase_time:.1f} s · Simulado {sim.time:.1f} s\n"
            f"Colas: {queue}\nPeatones: {sim.pedestrian_waiting()} esperando / "
            f"{crossing} cruzando"
        )
        ns = (Access.NORTH, Access.SOUTH)
        ew = (Access.EAST, Access.WEST)
        ns_stopped = sim.stopped_vehicles(ns)
        ns_approaching = sim.approaching_vehicles(ns)
        ew_stopped = sim.stopped_vehicles(ew)
        ew_approaching = sim.approaching_vehicles(ew)
        self.metrics.setText(
            f"Demanda pendiente · Norte–Sur: {sim.axis_demand('ns')} "
            f"(detenidos {ns_stopped}, aproximándose {ns_approaching}) · "
            f"Oriente–Occidente: {sim.axis_demand('ew')} "
            f"(detenidos {ew_stopped}, aproximándose {ew_approaching})\n"
            f"Saliendo · Norte–Sur: {sim.exiting_vehicles(ns)} · "
            f"Oriente–Occidente: {sim.exiting_vehicles(ew)}\n"
            f"Mayor espera por eje · Norte–Sur: {sim.axis_wait('ns'):.1f} s · "
            f"Oriente–Occidente: {sim.axis_wait('ew'):.1f} s · "
            f"peatón: {max(pedestrian_waits, default=0):.1f} s\n"
            f"Verde transcurrido: {sim.green_elapsed:.1f} s · Motivo: {sim.decision} · "
            f"Completados: {sim.completed_vehicles}"
        )
        self.start_button.setText(
            "Pausar" if sim.running else ("Reanudar" if self.has_started else "Iniciar")
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
        self.has_started = False
        self._sync_signals()
        for item in (*self.vehicle_items.values(), *self.pedestrian_items.values()):
            self.intersection_scene.removeItem(item)
        self.vehicle_items.clear()
        self.pedestrian_items.clear()
        for access, rate in self.demand_controls.items():
            rate.setValue(self.simulation.vehicle_rates[access])
        self.pedestrian_rate.setValue(self.simulation.pedestrian_rate)
        self._refresh_simulation()

    def _load_scenario(self) -> None:
        self.simulation_timer.stop()
        self.simulation.load_scenario(self.scenario_combo.currentData())
        self._sync_entities()
        self._sync_signals()
        self.has_started = False
        self._refresh_simulation()

    def _add_vehicle(self, access: Access) -> None:
        self.simulation.add_vehicle(access)
        self._sync_entities()
        self._refresh_simulation()

    def _add_pedestrian(self, access: Access) -> None:
        self.simulation.add_pedestrian(access)
        self._sync_entities()
        self._refresh_simulation()

    def _sidebar(self) -> QScrollArea:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(9)
        layout.addWidget(text_label("Escenario", "section"))
        layout.addWidget(text_label("4 accesos · 2 carriles por sentido", "muted"))
        primary = QHBoxLayout()
        self.start_button = QPushButton("Iniciar")
        self.start_button.setObjectName("primaryAction")
        self.start_button.clicked.connect(self._toggle_running)
        primary.addWidget(self.start_button, 2)
        reset_button = QPushButton("Reiniciar")
        reset_button.clicked.connect(self._reset_simulation)
        primary.addWidget(reset_button, 1)
        layout.addLayout(primary)
        speed_row = QHBoxLayout()
        speed_row.addWidget(text_label("Velocidad"))
        self.speed = QComboBox()
        for value in (0.5, 1, 2, 4):
            self.speed.addItem(f"{value:g}×", value)
        self.speed.setCurrentIndex(1)
        speed_row.addWidget(self.speed, 1)
        layout.addLayout(speed_row)
        self.overview = text_label("Todos los accesos en rojo · esperando demanda", "overview")
        layout.addWidget(self.overview)
        layout.addWidget(text_label("Semáforos", "section"))
        self.signal_labels = {}
        for access, light in self.intersection_scene.traffic_lights.items():
            signal = text_label(f"●  {access.value}  ·  {light.state.value}", "signal")
            self.signal_labels[access] = signal
            layout.addWidget(signal)
        layout.addWidget(text_label("Vista", "section"))
        view_row = QHBoxLayout()
        for title, action in (
            ("−", self.intersection_view.zoom_out),
            ("Restablecer", self.intersection_view.reset_view),
            ("+", self.intersection_view.zoom_in),
        ):
            button = QPushButton(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(action)
            view_row.addWidget(button)
        layout.addLayout(view_row)
        details_toggle = QToolButton()
        details_toggle.setText("Detalles y métricas  ▸")
        details_toggle.setCheckable(True)
        details_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        details_toggle.toggled.connect(
            lambda checked: self._toggle_panel(details_toggle, self.details_panel, checked)
        )
        layout.addWidget(details_toggle)
        self.details_panel = QWidget()
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setContentsMargins(6, 3, 6, 3)
        details_layout.addWidget(
            text_label("Los semáforos controlan dos carriles de entrada por acceso.", "muted")
        )
        self.metrics = text_label("Mayor espera: 0.0 s", "muted")
        details_layout.addWidget(self.metrics)
        self.details_panel.setVisible(False)
        layout.addWidget(self.details_panel)

        config_toggle = QToolButton()
        config_toggle.setText("Configuración y escenario  ▸")
        config_toggle.setCheckable(True)
        config_toggle.toggled.connect(
            lambda checked: self._toggle_panel(config_toggle, self.config_panel, checked)
        )
        layout.addWidget(config_toggle)
        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setContentsMargins(6, 3, 6, 3)
        config_layout.setSpacing(7)
        config_layout.addWidget(text_label("Escenario reproducible", "section"))
        self.scenario_combo = QComboBox()
        for scenario in Scenario:
            self.scenario_combo.addItem(scenario.value, scenario)
        config_layout.addWidget(self.scenario_combo)
        scenario_button = QPushButton("Cargar escenario")
        scenario_button.clicked.connect(self._load_scenario)
        config_layout.addWidget(scenario_button)
        config_layout.addWidget(text_label("Demanda · vehículos por minuto", "muted"))
        self.demand_controls = {}
        for access in Access:
            row = QHBoxLayout()
            row.addWidget(text_label(access.value))
            rate = QDoubleSpinBox()
            rate.setRange(0, 60)
            rate.setValue(self.simulation.vehicle_rates[access])
            rate.setSuffix(" veh/min")
            rate.valueChanged.connect(
                lambda value, item=access: self.simulation.set_demand(item, value)
            )
            self.demand_controls[access] = rate
            row.addWidget(rate)
            config_layout.addLayout(row)
            add_vehicle = QPushButton(f"Agregar vehículo · {access.value}")
            add_vehicle.clicked.connect(lambda checked=False, item=access: self._add_vehicle(item))
            config_layout.addWidget(add_vehicle)
        config_layout.addWidget(text_label("Peatones por minuto", "muted"))
        self.pedestrian_rate = QDoubleSpinBox()
        self.pedestrian_rate.setRange(0, 60)
        self.pedestrian_rate.setValue(self.simulation.pedestrian_rate)
        self.pedestrian_rate.setSuffix(" pers/min")
        self.pedestrian_rate.valueChanged.connect(
            lambda value: setattr(self.simulation, "pedestrian_rate", value)
        )
        config_layout.addWidget(self.pedestrian_rate)
        for access in Access:
            button = QPushButton(f"Agregar peatón · {access.value}")
            button.clicked.connect(lambda checked=False, item=access: self._add_pedestrian(item))
            config_layout.addWidget(button)
        self.config_panel.setVisible(False)
        layout.addWidget(self.config_panel)
        layout.addWidget(text_label("Arrastra el plano para recorrerlo con zoom.", "muted"))
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setFixedWidth(310)
        scroll.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        return scroll

    @staticmethod
    def _toggle_panel(button: QToolButton, panel: QWidget, expanded: bool) -> None:
        panel.setVisible(expanded)
        button.setText(
            button.text().replace("▸", "▾") if expanded else button.text().replace("▾", "▸")
        )
