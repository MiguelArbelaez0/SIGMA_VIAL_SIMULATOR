"""Contrato visual básico y cierre con el ciclo de eventos real de Qt."""

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from sigma_vial.presentation.main_window import MainWindow


def test_window_title_and_required_texts(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "SIGMA VIAL"
    texts = {label.text() for label in window.findChildren(QLabel)}
    assert texts == {
        "SIGMA VIAL",
        "SIGMA SOFTWARE SOLUTIONS",
        "Entorno listo para desarrollar la simulación.",
    }


def test_window_can_be_shown_resized_and_closed(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    window.resize(360, 280)
    qtbot.waitUntil(lambda: window.width() == 360 and window.height() == 280)
    assert window.close()
    qtbot.waitUntil(lambda: not window.isVisible())
