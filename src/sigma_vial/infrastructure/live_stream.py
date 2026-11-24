"""Una captura HTTP por URL. El consumidor solo recibe el fotograma más reciente."""

from threading import Event, Lock, Thread
from time import monotonic

from sigma_vial.infrastructure.image_vision import read_next_frame


class LiveStream(Thread):
    def __init__(self, url):
        super().__init__(name="sigma-camera")
        self.url = url
        self.stopping = Event()
        self.lock = Lock()
        self.latest = None
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
                with self.lock:
                    self.latest = frame
                    self.last_received = monotonic()
        except ImportError:
            self.error = 'Instala el extra de video con pip install -e ".[vision]".'
        except Exception as exc:
            self.error = f"No se pudo leer el video ({type(exc).__name__})."
        finally:
            if capture is not None:
                capture.release()
