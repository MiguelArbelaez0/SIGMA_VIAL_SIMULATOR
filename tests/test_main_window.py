"""Contrato visual básico y cierre con el ciclo de eventos real de Qt."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton
from pytestqt.qtbot import QtBot

from sigma_vial.presentation.main_window import MainWindow


def test_window_title_and_required_texts(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "SIGMA VIAL"
    texts = {label.text() for label in window.findChildren(QLabel)}
    assert {
        "SIGMA VIAL",
        "SIGMA SOFTWARE SOLUTIONS",
        "Vista inicial · Simulación detenida",
    } <= texts
    assert {button.text() for button in window.findChildren(QPushButton)} == {
        "Acercar",
        "Alejar",
        "Restablecer vista",
    }


def test_window_can_be_shown_resized_and_closed(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    window.resize(800, 600)
    qtbot.waitUntil(lambda: window.width() == 800 and window.height() == 600)
    view = window.intersection_view
    visible = view.mapToScene(view.viewport().rect()).boundingRect()
    assert visible.contains(window.intersection_scene.sceneRect())
    assert window.close()
    qtbot.waitUntil(lambda: not window.isVisible())


def test_view_controls_zoom_and_restore_full_scene(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)
    buttons = {button.text(): button for button in window.findChildren(QPushButton)}
    view = window.intersection_view
    initial_scale = view.transform().m11()
    qtbot.mouseClick(buttons["Acercar"], Qt.MouseButton.LeftButton)
    assert view.transform().m11() > initial_scale
    qtbot.mouseClick(buttons["Alejar"], Qt.MouseButton.LeftButton)
    assert view.transform().m11() == initial_scale
    for _ in range(12):
        view.zoom_in()
    assert view.zoom_steps == 6
    qtbot.mouseClick(buttons["Restablecer vista"], Qt.MouseButton.LeftButton)
    assert view.zoom_steps == 0
    assert view.transform().m11() == initial_scale
    assert (
        view.mapToScene(view.viewport().rect())
        .boundingRect()
        .contains(window.intersection_scene.sceneRect())
    )
