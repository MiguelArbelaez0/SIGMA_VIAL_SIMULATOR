"""Ventana inicial de la primera etapa del proyecto."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Presenta el estado real del proyecto sin controles todavía inexistentes."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SIGMA VIAL")
        self.resize(840, 520)
        self.setMinimumSize(360, 280)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.addStretch()

        title = QLabel("SIGMA VIAL")
        title_font = QFont()
        title_font.setPointSize(30)
        title_font.setBold(True)
        title.setFont(title_font)

        company = QLabel("SIGMA SOFTWARE SOLUTIONS")
        company_font = QFont()
        company_font.setPointSize(12)
        company_font.setBold(True)
        company.setFont(company_font)

        message = QLabel("Entorno listo para desarrollar la simulación.")
        message_font = QFont()
        message_font.setPointSize(12)
        message.setFont(message_font)

        for label in (title, company, message):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)

        layout.addStretch()
        self.setCentralWidget(content)
