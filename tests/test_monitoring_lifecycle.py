from concurrent.futures import Future

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from sigma_vial.domain.image_tracking import ImageDetection, ImageTracker
from sigma_vial.domain.scenario import Access
from sigma_vial.domain.simulation import Simulation
from sigma_vial.presentation.main_window import MainWindow
from sigma_vial.presentation.monitoring import MonitoringCenter


def test_reset_discards_completed_old_result_and_accepts_new_clock(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    monitor = MonitoringCenter(window)
    monitor.timer.stop()
    monitor.mode.setCurrentIndex(2)
    old = Future()
    from types import SimpleNamespace

    old.set_result((SimpleNamespace(timestamp=50), []))
    monitor.future = old
    monitor.submitted_generation = monitor.generation
    monitor.submitted_mode = 2
    monitor.pixel_tracker.update([], 50, 100)
    monitor.reset_video()
    monitor.error = "do not submit another frame"
    monitor.refresh()
    assert monitor.pixel_tracker.last_time == -1
    monitor.pixel_tracker.update([], 0.1, 100)
    assert monitor.pixel_tracker.last_time == 0.1
    monitor.pixel_tracker.update([], 20, 100)
    window.simulation.reset()
    monitor.refresh()
    assert monitor.pixel_tracker.last_time == -1
    monitor.close()


def test_tracking_retention_and_plate_uniqueness():
    tracker = ImageTracker()
    tracker.update([ImageDetection((0, 0, 10, 10), "car", 0.9)], 0, 100)
    tracker.update([], 11, 100)
    assert not tracker.tracks
    sim = Simulation()
    sim.add_vehicle(Access.NORTH)
    plate = sim.vehicles[0].plate
    sim.observations()
    sim.vehicles.clear()
    sim.running = True
    sim.automatic_generation = False
    sim.advance(0.2)
    sim.observations()
    assert not sim.observation_source.cameras[Access.NORTH]._tracks
    assert plate in sim.plates.used


def test_closed_windows_are_deleted(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window._open_monitoring()
    monitor = window.monitoring_center
    monitor.expand(Access.NORTH)
    monitor.expanded[0].close()
    assert not monitor.expanded
    monitor.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    assert window.monitoring_center is None
    assert not window.findChildren(MonitoringCenter)
