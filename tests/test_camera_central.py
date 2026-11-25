from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest
from PySide6.QtCore import QSettings

from sigma_vial.domain.scenario import Access
from sigma_vial.presentation.camera_central import CameraCentral, camera_url


@contextmanager
def camera_server(color):
    import cv2
    import numpy as np

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            server.connections += 1
            try:
                n = 0
                while not server.stop.wait(0.04):
                    if server.stalled.is_set():
                        continue
                    pixels = np.full((80, 120, 3), color, dtype=np.uint8)
                    pixels[:, n % 110 : n % 110 + 6] = 255
                    jpeg = cv2.imencode(".jpg", pixels)[1].tobytes()
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode()
                        + b"\r\n\r\n"
                        + jpeg
                        + b"\r\n"
                    )
                    n += 1
            except OSError:
                pass
            finally:
                server.connections -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.stop = Event()
    server.stalled = Event()
    server.connections = 0
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/stream", server
    finally:
        server.stop.set()
        server.shutdown()
        server.server_close()
        thread.join()


def test_four_camera_lifecycle(qtbot, tmp_path):
    pytest.importorskip("cv2")
    settings = QSettings(str(tmp_path / "cameras.ini"), QSettings.Format.IniFormat)
    center = CameraCentral(None, settings)
    qtbot.addWidget(center)
    center.show()
    n, s, e, w = Access
    panels = center.panels
    assert all(p.state.text() == "Sin configurar" for p in panels.values())
    with camera_server((0, 0, 215)) as (red, first), camera_server((255, 0, 0)) as (blue, second):
        center.assign(n, red)
        center.assign(s, blue)
        qtbot.waitUntil(
            lambda: all(panels[a].state.text() == "En vivo" for a in (n, s)), timeout=10000
        )
        assert panels[n].video.image.pixelColor(119, 40).red() > 180
        assert panels[s].video.image.pixelColor(119, 40).blue() > 180
        with pytest.raises(ValueError):
            center.assign(e, red)
        center.focus_camera(n)
        assert panels[s].isHidden()
        streams = center.streams.copy()
        center.showMinimized()
        qtbot.waitUntil(center.isMinimized)
        keys = [panels[a].video.image.cacheKey() for a in (n, s)]
        qtbot.waitUntil(
            lambda: all(
                panels[a].video.image.cacheKey() != k for a, k in zip((n, s), keys, strict=True)
            )
        )
        center.showNormal()
        assert center.focused == n
        assert center.streams == streams
        center.focus_camera(n)
        assert panels[s].isVisible()
        assert first.connections == second.connections == 1
        center.move(n, e)
        qtbot.waitUntil(lambda: panels[e].state.text() == "En vivo")
        assert panels[n].state.text() == panels[w].state.text() == "Sin configurar"
        first.stalled.set()
        qtbot.waitUntil(lambda: panels[e].state.text() == "Sin señal", timeout=8000)
        assert panels[e].video.image.isNull()
        old = panels[s].video.image.cacheKey()
        qtbot.waitUntil(lambda: panels[s].video.image.cacheKey() != old)
        center.stop(s)
        center.start(s)
        qtbot.waitUntil(lambda: panels[s].state.text() == "En vivo", timeout=10000)
        center.close()
        qtbot.waitUntil(lambda: second.connections == 0 and not center.streams, timeout=7000)
        center.show()
        center.start(s)
        qtbot.waitUntil(lambda: panels[s].state.text() == "En vivo", timeout=10000)
        assert second.connections == 1
        center.assign(e, "")
        center.close()
        qtbot.waitUntil(lambda: not center.streams, timeout=7000)
    restored = CameraCentral(None, settings)
    qtbot.addWidget(restored)
    assert restored.urls == {s: blue}
    assert restored.panels[s].state.text() == "Desconectada"


def test_camera_address_validation():
    assert camera_url("HTTP://EXAMPLE.COM:80/stream#test") == "http://example.com/stream"
    for value in ("", "file:///video", "http://user:pw@localhost/stream", "http://"):
        with pytest.raises(ValueError):
            camera_url(value)


def test_only_north_uses_fresh_frames_from_current_calibration(qtbot, tmp_path):
    from time import monotonic
    from types import SimpleNamespace

    from sigma_vial.infrastructure.image_vision import ImageFrame

    settings = QSettings(str(tmp_path / "north.ini"), QSettings.Format.IniFormat)
    center = CameraCentral(None, settings)
    qtbot.addWidget(center)
    n = Access.NORTH
    panel = center.panels[n]
    assert not panel.detect.isChecked() and not panel.detect.isEnabled()
    assert all(not hasattr(center.panels[a], "detect") for a in Access if a != n)
    center.urls[n] = "COM4"
    stream = center.streams["COM4"] = SimpleNamespace(north_token=None)
    panel.detect.setEnabled(True)
    panel.detect.setChecked(True)
    panel.mark.click()
    for point in [(120, 20), (121, 22)]:
        center.pick_point(*point)
    assert len(panel.video.points) == 1 and not panel.calibrate.isEnabled()
    for point in [(125, 130), (155, 20), (158, 130)]:
        center.pick_point(*point)
    panel.calibrate.click()
    token = stream.north_token
    assert token.points == panel.video.points and center.north_observation() is None
    center.north_frame = ImageFrame(None, monotonic(), token, 0)
    assert center.north_observation() == (token, 0)
    center.north_frame = ImageFrame(None, monotonic() - 3, token, 5)
    assert center.north_observation() is None
    panel.calibrate.click()
    center.north_frame = ImageFrame(None, monotonic(), token, 3)
    assert center.north_observation() is None
    panel.detect.setChecked(False)
    assert stream.north_token is None and center.north_observation() is None


def test_automatic_alignment_uses_camera_pixels_and_loses_moved_reference(qtbot, tmp_path):
    from types import SimpleNamespace

    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from sigma_vial.infrastructure.image_vision import ImageFrame
    from sigma_vial.presentation.intersection_scene import IntersectionScene

    scene = IntersectionScene()
    empty = False
    settings = QSettings(str(tmp_path / "cal.ini"), QSettings.Format.IniFormat)
    center = CameraCentral(None, settings, north_scene=scene, north_clear=lambda: empty)
    qtbot.addWidget(center)
    panel = center.panels[Access.NORTH]
    center.urls[Access.NORTH] = "COM4"
    stream = center.streams["COM4"] = SimpleNamespace(north_token=None)
    panel.detect.setEnabled(True)
    panel.detect.setChecked(True)
    assert len(center.markers) == 2
    image = QImage(640, 480, QImage.Format.Format_BGR888)
    with QPainter(image) as painter:
        scene.render(painter, QRectF(0, 0, 640, 480), QRectF(-280, -510, 480, 360))
    pixels = np.frombuffer(image.bits(), np.uint8).reshape(480, 640, 3)
    original = np.float32([(0, 0), (639, 0), (639, 479), (0, 479)])
    transform = cv2.getPerspectiveTransform(
        original, np.float32([(14, 38), (610, 10), (632, 467), (48, 432)])
    )
    frame = ImageFrame(cv2.warpPerspective(pixels, transform, (640, 480)), 1)
    expected = ((center.alignment.lanes + (280, 510)) * (4 / 3)).astype(np.float32)
    expected = cv2.perspectiveTransform(expected[None], transform)[0] / 2
    for _ in range(4):
        center.align_frame(panel, stream, frame)
    assert stream.north_token is None
    empty = True
    for _ in range(3):
        center.align_frame(panel, stream, frame)
    assert np.allclose(stream.north_token.points, expected, atol=2)
    # One briefly obscured code can validate the previous geometry. A fresh
    # calibration still requires both codes and expires if the image is blank.
    left_hidden = frame.pixels.copy()
    endpoints = cv2.perspectiveTransform(
        ((center.alignment.source[:4] + (280, 510)) * (4 / 3)).astype(np.float32)[None],
        transform,
    )[0]
    cv2.fillConvexPoly(left_hidden, endpoints.astype(np.int32), (255, 255, 255))
    assert center.alignment.locate(left_hidden) == stream.north_token.points
    center.align_frame(panel, stream, ImageFrame(np.zeros_like(pixels), 2))
    assert stream.north_token is None and center.north_observation() is None
    panel.detect.setChecked(False)
    assert not center.markers


def test_vehicle_recognition_on_local_traffic_clip():
    pytest.importorskip("cv2")
    from sigma_vial.infrastructure.image_vision import LocalVideoSource
    from sigma_vial.infrastructure.live_stream import LiveStream

    source = LocalVideoSource("assets/vision/traffic-demo.mp4")
    try:
        frame = source.read(4)
    finally:
        source.close()
    stream = LiveStream("COM4")
    stream.recognition_token = object()
    stream.publish(frame)
    result = stream.take_frame()
    assert any(v.category == "automóvil" for v in result.vehicles)
    assert result.north_count is None
    stream.recognition_token = None
    stream.publish(frame)
    assert stream.take_frame().vehicles == ()


@pytest.mark.parametrize(
    ("detect", "fast", "bad_frame"),
    [(False, False, False), (True, True, False), (True, True, True)],
)
def test_usb_camera_handles_fragmented_frame_and_closes(monkeypatch, detect, fast, bad_frame):
    from PySide6 import QtSerialPort

    from sigma_vial.infrastructure.usb_camera import NorthCalibration, camera_jpegs

    token = NorthCalibration() if detect else None

    class Port:
        def __init__(self):
            self.requests = []
            self.ack = False
            self.rates = []
            self.chunks = iter(
                ([b"SVJ2\x00\x00\x00\x00\xff"] if bad_frame else [])
                + [
                    b"boot\r\nSV",
                    b"J2\x04",
                    b"\x00\x00\x00\xffab",
                    b"cd",
                    b"SVJ2\x04\x00\x00\x00\x28abcd",
                ]
                if detect
                else [b"boot\r\nSV", b"J1\x04", b"\x00\x00\x00ab", b"cd"]
            )
            self.closed = False

        def setPortName(self, name):
            assert name == "COM4"

        def setBaudRate(self, rate):
            self.rates.append(rate)
            return True

        def open(self, mode):
            return True

        def clear(self):
            pass

        def write(self, request):
            self.requests.append(request)
            self.ack = request == b"F"
            return len(request)

        def waitForBytesWritten(self, timeout):
            return True

        def bytesAvailable(self):
            return 1

        def readAll(self):
            if self.ack:
                return b"SVF1" if fast else b""
            return next(self.chunks)

        def close(self):
            self.closed = True

    port = Port()
    monkeypatch.setattr(QtSerialPort, "QSerialPort", lambda: port)
    frames = camera_jpegs(camera_url(" com4 "), Event(), lambda: token)
    assert next(frames) == (b"abcd", token, None)
    if detect:
        assert next(frames) == (b"abcd", token, 40)
        if bad_frame:
            assert port.requests == [b"F", token.command(), token.command(), b"N"]
            assert port.rates == [460800, 921600, 460800]
        else:
            assert port.requests == [b"F", token.command(), b"F", b"N"]
            assert port.rates == [460800, 921600, 460800, 921600, 460800]
    else:
        assert port.requests == [b"F", b"J"]
    frames.close()
    assert port.closed
