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


@pytest.mark.parametrize("detect", [False, True])
def test_usb_camera_handles_fragmented_frame_and_closes(monkeypatch, detect):
    from PySide6 import QtSerialPort

    from sigma_vial.infrastructure.usb_camera import NorthCalibration, camera_jpegs

    token = NorthCalibration() if detect else None

    class Port:
        def __init__(self):
            self.requests = []
            self.chunks = iter(
                [
                    b"boot\r\nSV",
                    b"J2\x04",
                    b"\x00\x00\x00\xffab",
                    b"cd",
                    b"SVJ2\x04\x00\x00\x00\x03abcd",
                ]
                if detect
                else [b"boot\r\nSV", b"J1\x04", b"\x00\x00\x00ab", b"cd"]
            )
            self.closed = False

        def setPortName(self, name):
            assert name == "COM4"

        def setBaudRate(self, rate):
            assert rate == 460800

        def open(self, mode):
            return True

        def clear(self):
            pass

        def write(self, request):
            self.requests.append(request)
            return len(request)

        def waitForBytesWritten(self, timeout):
            return True

        def bytesAvailable(self):
            return 1

        def readAll(self):
            return next(self.chunks)

        def close(self):
            self.closed = True

    port = Port()
    monkeypatch.setattr(QtSerialPort, "QSerialPort", lambda: port)
    frames = camera_jpegs(camera_url(" com4 "), Event(), lambda: token)
    assert next(frames) == (b"abcd", token, None)
    if detect:
        assert next(frames) == (b"abcd", token, 3)
        assert port.requests == [token.command(), b"N"]
    else:
        assert port.requests == [b"J"]
    frames.close()
    assert port.closed
