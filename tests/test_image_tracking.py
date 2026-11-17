"""Regresiones de seguimiento de imagen sin acceso al estado del simulador."""

from concurrent.futures import Future

import pytest

from sigma_vial.domain.image_tracking import ImageCalibration, ImageDetection, ImageTracker
from sigma_vial.domain.scenario import Access
from sigma_vial.infrastructure.image_vision import traffic_from_tracks


def detection(x=40, y=40):
    return ImageDetection((x - 10, y - 10, x + 10, y + 10), "automóvil", 0.8)


def test_track_confirmation_stopped_wait_and_no_plate_dependency():
    tracker = ImageTracker()
    first = tracker.update([detection()], 0, 100)[0]
    assert first.state == "detectado"
    tracker.update([detection()], 1, 100)
    assert first.state == "confirmado"
    assert first.speed == 0 and first.wait == 1
    summary = traffic_from_tracks(tracker, Access.NORTH, 1, 100)
    assert summary.queue == 1 and summary.demand == 1
    assert summary.detections[0].plate is None
    assert summary.detections[0].plate_source == "Sin lectura"
    assert summary.detections[0].confidence == 0.8


@pytest.mark.parametrize("direction,positions", [(1, (20, 40, 70, 80)), (-1, (80, 70, 40, 20))])
def test_passage_count_once_per_track_and_direction(direction, positions):
    tracker = ImageTracker(ImageCalibration(line_y=0.5, direction=direction))
    for i, y in enumerate(positions):
        tracker.update([detection(y=y)], i * 0.2, 100)
    assert tracker.passage_count == 1
    assert len(tracker.tracks) == 1
    tracker.update([detection(y=positions[-1])], 1, 100)
    assert tracker.passage_count == 1


def test_wrong_direction_does_not_increment_count():
    tracker = ImageTracker(ImageCalibration(line_y=0.5, direction=-1))
    tracker.update([detection(y=30)], 0, 100)
    tracker.update([detection(y=70)], 0.2, 100)
    assert tracker.passage_count == 0


def test_occlusion_lost_recovery_expiry_and_new_identity():
    tracker = ImageTracker()
    track = tracker.update([detection()], 0, 100)[0]
    tracker.update([], 0.5, 100)
    assert track.state == "perdido"
    assert not traffic_from_tracks(tracker, Access.NORTH, 0.5, 100).detections
    tracker.update([detection()], 1, 100)
    assert track.state == "confirmado" and len(tracker.tracks) == 1
    tracker.update([], 3, 100)
    assert track.state == "finalizado"
    tracker.update([detection()], 3.2, 100)
    assert len(tracker.tracks) == 2


def test_association_does_not_assign_two_vehicles_to_one_track():
    tracker = ImageTracker()
    tracker.update([detection(20), detection(80)], 0, 100)
    tracker.update([detection(25), detection(75)], 0.2, 100)
    assert len(tracker.tracks) == 2
    assert all(track.hits == 2 for track in tracker.tracks.values())


def test_repeated_or_out_of_order_time_does_not_advance_and_history_is_bounded():
    tracker = ImageTracker()
    track = tracker.update([detection()], 0, 100)[0]
    tracker.update([detection(y=80)], 0, 100)
    assert track.hits == 1
    for i in range(1, 200):
        tracker.update([detection()], i * 0.1, 100)
    assert len(track.history) == 128
    assert track.first_seen == 0
    assert track.last_seen == pytest.approx(19.9)


def test_real_image_detector_and_frozen_frame_queue():
    pytest.importorskip("cv2")
    from sigma_vial.infrastructure.image_vision import ImageFrame, LocalVideoSource, YoloXDetector

    source = LocalVideoSource("assets/vision/traffic-demo.mp4")
    frame = source.read(4)
    detector = YoloXDetector("assets/vision/yolox.onnx")
    detections = detector.detect(frame)
    assert any(d.category == "automóvil" for d in detections)
    assert all(0 <= d.confidence <= 1 for d in detections)
    tracker = ImageTracker()
    tracker.update(detections, 0, frame.pixels.shape[0])
    tracker.update(detector.detect(ImageFrame(frame.pixels, 1)), 1, frame.pixels.shape[0])
    assert traffic_from_tracks(tracker, Access.NORTH, 1, frame.pixels.shape[1]).queue >= 1
    source.close()


def test_monitor_simulation_is_labelled_and_worker_queue_is_bounded(qtbot):
    from sigma_vial.presentation.main_window import MainWindow
    from sigma_vial.presentation.monitoring import MonitoringCenter

    window = MainWindow()
    qtbot.addWidget(window)
    window.simulation.automatic_generation = False
    window._add_vehicle(Access.NORTH)
    window.simulation.running = True
    window.simulation.advance(0.2)
    monitor = MonitoringCenter(window)
    qtbot.addWidget(monitor)
    monitor.timer.stop()
    monitor.refresh()
    assert "Percepción simulada" in monitor.status.text()
    assert len(monitor.simulated_tracks[Access.NORTH]) == 1
    assert "edad" in monitor.captions[Access.NORTH].text()
    assert all(
        track.detection.confidence is None
        for track in monitor.simulated_tracks[Access.NORTH].values()
    )
    monitor.expand(Access.NORTH)
    assert monitor.expanded[-1].isVisible()
    monitor.mode.setCurrentIndex(1)
    pending = Future()
    monitor.future = pending
    for _ in range(10):
        monitor.refresh()
    assert monitor.future is pending
    pending.set_result(None)
    monitor.refresh()
    assert not monitor.running_video
    monitor.close()


def test_short_model_category_noise_does_not_create_new_identity():
    tracker = ImageTracker()
    track = tracker.update([detection()], 0, 100)[0]
    noisy = ImageDetection(detection().box, "camión", 0.45)
    tracker.update([noisy], 0.2, 100)
    tracker.update([detection()], 0.4, 100)
    assert len(tracker.tracks) == 1
    assert track.hits == 3
    assert track.detection.category == "automóvil"
