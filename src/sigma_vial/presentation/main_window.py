"""Ventana del escenario estático: composición visual y controles de encuadre."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsEllipseItem,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Scenario, Simulation
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
        self.simulation = Simulation()
        self.simulation_timer = QTimer(self)
        self.simulation_timer.setInterval(50)
        self.simulation_timer.timeout.connect(self._advance_simulation)
        self.has_started = False
        self.intersection_scene = IntersectionScene(self)
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
        self.metrics = text_label("Tiempo: 0.0 s", "muted")
        outer.addWidget(self.metrics)
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
        status = text_label("Vista inicial · Simulación detenida", "status")
        status.setMaximumWidth(300)
        status.setMinimumWidth(290)
        layout.addWidget(status)
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
        for access, state in self.simulation.signals.items():
            self.intersection_scene.traffic_lights[access].set_state(state)
            self.signal_labels[access].setText(f"●  {access.value}  ·  {state.value}")
        self._refresh_simulation()

    def _sync_entities(self) -> None:
        active = {vehicle.identifier for vehicle in self.simulation.vehicles}
        for identifier in self.vehicle_items.keys() - active:
            self.intersection_scene.removeItem(self.vehicle_items.pop(identifier))
        for vehicle in self.simulation.vehicles:
            item = self.vehicle_items.get(vehicle.identifier)
            if item is None:
                item = QGraphicsEllipseItem(-10, -6, 20, 12)
                item.setBrush(QBrush(QColor("#f0a93f")))
                item.setPen(Qt.PenStyle.NoPen)
                item.setRotation(
                    {Access.NORTH: 90, Access.SOUTH: 270, Access.EAST: 180, Access.WEST: 0}[
                        vehicle.access
                    ]
                )
                item.setZValue(15)
                self.intersection_scene.addItem(item)
                self.vehicle_items[vehicle.identifier] = item
            distance = min(400, vehicle.position * 0.66)
            lane = -29 if vehicle.lane == 0 else -87
            positions = {
                Access.NORTH: (lane, -430 + distance),
                Access.SOUTH: (-lane, 430 - distance),
                Access.EAST: (430 - distance, lane),
                Access.WEST: (-430 + distance, -lane),
            }
            item.setPos(*positions[vehicle.access])

        active = {person.identifier for person in self.simulation.pedestrians}
        for identifier in self.pedestrian_items.keys() - active:
            self.intersection_scene.removeItem(self.pedestrian_items.pop(identifier))
        for person in self.simulation.pedestrians:
            item = self.pedestrian_items.get(person.identifier)
            if item is None:
                item = QGraphicsEllipseItem(-5, -5, 10, 10)
                item.setBrush(QBrush(QColor("#7043aa")))
                item.setPen(Qt.PenStyle.NoPen)
                item.setZValue(16)
                self.intersection_scene.addItem(item)
                self.pedestrian_items[person.identifier] = item
            item.setPos(-116 + person.position, person.lane - 116)

    def _refresh_simulation(self) -> None:
        sim = self.simulation
        queue = " · ".join(f"{a.value}: {sim.waiting(a)}" for a in Access)
        crossing = sum(p.walking for p in sim.pedestrians)
        waits = [v.wait for v in sim.vehicles if not v.inside]
        pedestrian_waits = [p.wait for p in sim.pedestrians if not p.walking]
        self.metrics.setText(
            f"{sim.phase.value} · Fase {sim.phase_time:.1f} s · Vehículos: {queue} · "
            f"Peatones: {sim.pedestrian_waiting()} esperando / {crossing} cruzando · "
            f"Mayor espera: {max(waits, default=0):.1f}s veh / "
            f"{max(pedestrian_waits, default=0):.1f}s peat · "
            f"Carril despejado: {sim._empty_time:.1f}s · "
            f"Centro: {'salida bloqueada' if sim.blocked_exit else 'sin bloqueo informado'} · "
            f"{sim.decision} · Simulado: {sim.time:.1f} s"
        )
        self.start_button.setText(
            "Pausar" if sim.running else ("Reanudar" if self.has_started else "Iniciar")
        )

    def _reset_simulation(self) -> None:
        self.simulation_timer.stop()
        self.simulation.reset()
        self.has_started = False
        for access, state in self.simulation.signals.items():
            self.intersection_scene.traffic_lights[access].set_state(state)
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
        for access, state in self.simulation.signals.items():
            self.intersection_scene.traffic_lights[access].set_state(state)
            self.signal_labels[access].setText(f"●  {access.value}  ·  {state.value}")
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
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(11)
        layout.addWidget(text_label("Escenario", "section"))
        layout.addWidget(text_label("4 accesos"))
        layout.addWidget(text_label("2 carriles de entrada por acceso"))
        layout.addWidget(text_label("2 carriles de salida por acceso"))
        layout.addWidget(text_label("8 de entrada · 8 de salida en total", "muted"))
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)
        layout.addWidget(text_label("Semáforos vehiculares", "section"))
        self.signal_labels = {}
        for access, light in self.intersection_scene.traffic_lights.items():
            signal = text_label(f"●  {access.value}  ·  {light.state.value}", "signal")
            self.signal_labels[access] = signal
            layout.addWidget(signal)
        layout.addWidget(
            text_label("Cada semáforo controla los dos carriles de entrada de su acceso.", "muted")
        )
        layout.addWidget(text_label("Demanda (vehículos/minuto)", "section"))
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
            layout.addLayout(row)
            add_vehicle = QPushButton(f"Agregar vehículo · {access.value}")
            add_vehicle.clicked.connect(lambda checked=False, item=access: self._add_vehicle(item))
            layout.addWidget(add_vehicle)
        layout.addWidget(text_label("Peatones (personas/minuto)", "section"))
        self.pedestrian_rate = QDoubleSpinBox()
        self.pedestrian_rate.setRange(0, 60)
        self.pedestrian_rate.setValue(self.simulation.pedestrian_rate)
        self.pedestrian_rate.setSuffix(" pers/min")
        self.pedestrian_rate.valueChanged.connect(
            lambda value: setattr(self.simulation, "pedestrian_rate", value)
        )
        layout.addWidget(self.pedestrian_rate)
        for access in Access:
            button = QPushButton(f"Agregar peatón · {access.value}")
            button.clicked.connect(lambda checked=False, item=access: self._add_pedestrian(item))
            layout.addWidget(button)
        layout.addWidget(text_label("Escenarios reproducibles", "section"))
        self.scenario_combo = QComboBox()
        for scenario in Scenario:
            self.scenario_combo.addItem(scenario.value, scenario)
        layout.addWidget(self.scenario_combo)
        scenario_button = QPushButton("Cargar escenario")
        scenario_button.clicked.connect(lambda: self._load_scenario())
        layout.addWidget(scenario_button)
        controls = QHBoxLayout()
        self.start_button = QPushButton("Iniciar")
        self.start_button.clicked.connect(self._toggle_running)
        controls.addWidget(self.start_button)
        reset_button = QPushButton("Reiniciar")
        reset_button.clicked.connect(self._reset_simulation)
        controls.addWidget(reset_button)
        layout.addLayout(controls)
        self.speed = QComboBox()
        for value in (0.5, 1, 2, 4):
            self.speed.addItem(f"{value:g}×", value)
        layout.addWidget(self.speed)
        layout.addWidget(text_label("Visualización", "section"))
        for title, action in (
            ("Acercar", self.intersection_view.zoom_in),
            ("Alejar", self.intersection_view.zoom_out),
            ("Restablecer vista", self.intersection_view.reset_view),
        ):
            button = QPushButton(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(action)
            layout.addWidget(button)
        layout.addWidget(text_label("Puedes arrastrar el plano al acercar la vista.", "muted"))
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setFixedWidth(280)
        scroll.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        return scroll
