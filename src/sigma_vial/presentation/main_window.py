"""Ventana del escenario estático: composición visual y controles de encuadre."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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
        self.intersection_scene = IntersectionScene(self)
        self.intersection_view = IntersectionView(self.intersection_scene)
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
        outer.addWidget(text_label("Escenario virtual  /  Interfaz inicial sin tráfico", "muted"))
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
        for access, light in self.intersection_scene.traffic_lights.items():
            layout.addWidget(text_label(f"●  {access.value}  ·  {light.state.value}", "signal"))
        layout.addWidget(
            text_label("Cada semáforo controla los dos carriles de entrada de su acceso.", "muted")
        )
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
