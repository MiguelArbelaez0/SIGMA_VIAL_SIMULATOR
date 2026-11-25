"""Una captura HTTP por URL. El consumidor solo recibe el fotograma más reciente."""

from threading import Event, Lock, Thread
from time import monotonic

from sigma_vial.infrastructure.image_vision import ImageFrame, read_next_frame
from sigma_vial.infrastructure.usb_camera import camera_jpegs, com_port


class LiveStream(Thread):
    def __init__(self, url):
        super().__init__(name="sigma-camera")
        self.url = url
        self.stopping = Event()
        self.lock = Lock()
        self.latest = None
        self.north_token = None
        self.error = ""
        self.last_received = monotonic()

    def take_frame(self):
        with self.lock:
            frame, self.latest = self.latest, None
            return frame

    def run(self):
        capture = None
        try:
            import cv2

            if com_port(self.url):
                import numpy as np

                for jpeg, token, count in camera_jpegs(
                    self.url, self.stopping, lambda: self.north_token
                ):
                    pixels = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                    if pixels is not None:
                        self.publish(ImageFrame(pixels, monotonic(), token, count))
                return

            capture = cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    4000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    2500,
                ],
            )
            if not capture.isOpened():
                self.error = "Comprueba la URL y la red de la cámara."
                return
            while not self.stopping.is_set():
                frame = read_next_frame(capture, monotonic())
                if frame is None:
                    break
                self.publish(frame)
        except ImportError:
            self.error = 'Instala el extra de video con pip install -e ".[vision]".'
        except Exception as exc:
            self.error = f"No se pudo leer el video ({type(exc).__name__})."
        finally:
            if capture is not None:
                capture.release()

    def publish(self, frame):
        with self.lock:
            self.latest = frame
            self.last_received = monotonic()
