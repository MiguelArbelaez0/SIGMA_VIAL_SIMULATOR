"""Evaluación pequeña y reproducible; no equivale a validar precisión de tráfico general."""

import json
import statistics
import time
from pathlib import Path

import cv2

from sigma_vial.infrastructure.image_vision import ImageFrame, NanoDetDetector, YoloXDetector


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / max(1, area_a + area_b - intersection)


def evaluate(detector, samples):
    tp = fp = fn = 0
    durations = []
    details = []
    for image, timestamp, boxes in samples:
        start = time.perf_counter()
        detections = detector.detect(ImageFrame(image, timestamp))
        durations.append(time.perf_counter() - start)
        remaining = list(boxes)
        matched = 0
        for detection in detections:
            candidates = [(iou(detection.box, box), i) for i, box in enumerate(remaining)]
            score, index = max(candidates, default=(0, -1))
            if score >= 0.5:
                remaining.pop(index)
                matched += 1
        tp += matched
        fp += len(detections) - matched
        fn += len(remaining)
        details.append(
            {
                "time": timestamp,
                "detections": [
                    {"box": d.box, "category": d.category, "confidence": d.confidence}
                    for d in detections
                ],
                "tp": matched,
                "fp": len(detections) - matched,
                "fn": len(remaining),
            }
        )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "median_ms": round(statistics.median(durations) * 1000, 2),
        "frames": details,
    }


def main():
    labels = json.loads(Path("docs/vision-evaluation/annotations.json").read_text(encoding="utf-8"))
    capture = cv2.VideoCapture(labels["real"]["video"])
    real = []
    for sample in labels["real"]["frames"]:
        capture.set(cv2.CAP_PROP_POS_MSEC, sample["time"] * 1000)
        ok, image = capture.read()
        if not ok:
            raise RuntimeError("No se pudo leer el fotograma anotado")
        real.append((cv2.resize(image, (960, 540)), sample["time"], sample["boxes"]))
    capture.release()
    synthetic = [(cv2.imread(labels["synthetic"]["image"]), 0, labels["synthetic"]["boxes"])]
    results = {}
    for name, cls in (("nanodet", NanoDetDetector), ("yolox", YoloXDetector)):
        detector = cls(f"assets/vision/{name}.onnx")
        results[name] = {
            "real": evaluate(detector, real),
            "synthetic": evaluate(detector, synthetic),
        }
    Path("docs/vision-evaluation/results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                name: {
                    source: {key: value for key, value in result.items() if key != "frames"}
                    for source, result in sources.items()
                }
                for name, sources in results.items()
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
