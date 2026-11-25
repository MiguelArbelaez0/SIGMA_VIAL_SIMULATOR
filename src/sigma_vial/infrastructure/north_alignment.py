"""Localiza los carriles del simulador en una imagen de la cámara física."""

from time import monotonic


class NorthAlignment:
    # The two codes are distinct even when the camera sees the monitor at an angle.
    ids = (17, 29)
    marker_pixels = 96
    margin = 16

    def __init__(self, lane_width, stop_distance):
        import cv2
        import numpy as np

        self.dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2.aruco.ArucoDetector(self.dictionary, parameters)
        self.side = 1.4 * lane_width
        far, near = -stop_distance - 4 * lane_width, -stop_distance
        self.origins = ((-3.7 * lane_width, far), (0.25 * lane_width, near - self.side))
        self.last_pair = None
        self.last_points = None
        self.last_seen = 0.0
        self.source = np.float32(
            [
                (x + dx * self.side, y + dy * self.side)
                for x, y in self.origins
                for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))
            ]
        )
        self.lanes = np.float32([(x * lane_width, y) for x in (-1.5, -0.5) for y in (far, near)])

    def marker(self, marker_id):
        import cv2
        import numpy as np

        code = cv2.aruco.generateImageMarker(self.dictionary, marker_id, self.marker_pixels)
        return np.pad(code, self.margin, constant_values=255)

    def locate(self, pixels):
        import cv2
        import numpy as np

        corners, ids, _ = self.detector.detectMarkers(pixels)
        if ids is None:
            return None
        ids = ids.ravel().tolist()
        matches = {}
        for key in self.ids:
            # A smaller copy may appear inside the live preview of the monitor.
            choices = sorted(
                (c[0] for c, k in zip(corners, ids, strict=True) if k == key),
                key=cv2.contourArea,
                reverse=True,
            )
            if not choices:
                continue
            if len(choices) > 1 and cv2.contourArea(choices[0]) < 2.25 * cv2.contourArea(
                choices[1]
            ):
                return None
            matches[key] = choices[0]
        if len(matches) < 2:
            # Bridge a brief missed code only while the other code's four corners
            # stay in place. A new camera pose always needs both codes.
            if matches and self.last_pair and monotonic() - self.last_seen <= 1.5:
                key, corners = next(iter(matches.items()))
                shift = (corners - self.last_pair[key]) * (
                    320 / pixels.shape[1],
                    240 / pixels.shape[0],
                )
                if np.linalg.norm(shift, axis=1).max() <= 1.5:
                    return self.last_points
            return None
        observed = np.concatenate(list(matches.values()))
        transform, _ = cv2.findHomography(self.source, observed)
        if transform is None:
            return None
        fitted = cv2.perspectiveTransform(self.source[None], transform)[0]
        if np.linalg.norm(fitted - observed, axis=1).max() > 3:
            return None
        projected = cv2.perspectiveTransform(self.lanes[None], transform)[0]
        h, w = pixels.shape[:2]
        normalized = np.rint(projected * (320 / w, 240 / h))
        if (
            not np.isfinite(normalized).all()
            or not ((normalized >= 0) & (normalized < (320, 240))).all()
        ):
            return None
        if min(np.linalg.norm(normalized[i] - normalized[i + 1]) for i in (0, 2)) < 20:
            return None
        self.last_pair = matches
        self.last_seen = monotonic()
        self.last_points = tuple((int(x), int(y)) for x, y in normalized)
        return self.last_points


def same_guides(first, second):
    return (
        first is not None
        and second is not None
        and all(
            abs(x - u) <= 2 and abs(y - v) <= 2
            for (x, y), (u, v) in zip(first, second, strict=True)
        )
    )
