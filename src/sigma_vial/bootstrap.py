"""Composición de la ventana y propiedad del ciclo de vida de Qt."""

import sys

from PySide6.QtWidgets import QApplication

from sigma_vial.presentation.main_window import MainWindow


def main() -> int:
    """Arranca una sesión independiente; el invocador no debe tener otra QApplication."""
    if QApplication.instance() is not None:
        raise RuntimeError("La aplicación Qt ya está en ejecución.")

    app = QApplication(sys.argv)
    app.setApplicationName("SIGMA VIAL")
    app.setOrganizationName("SIGMA SOFTWARE SOLUTIONS")
    window = MainWindow()
    window.show()
    return app.exec()
