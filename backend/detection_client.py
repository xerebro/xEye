from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

try:  # pragma: no cover - optional dependency resolved on the Pi
    import cv2  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - allows import without OpenCV
    cv2 = None  # type: ignore[assignment]


@dataclass
class DetectionResult:
    boxes: list  # [{x1,y1,x2,y2,cls,conf}], normalizados
    names: dict
    ts: float
    latency_ms: float


class DetectionClient:
    def __init__(self, server_url: str, timeout: float = 1.5):
        if cv2 is None:
            raise RuntimeError("OpenCV (cv2) is required for DetectionClient")
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.sess = requests.Session()
        self.last: Optional[DetectionResult] = None
        self.q: queue.Queue = queue.Queue(maxsize=1)
        self.stop_ev = threading.Event()
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    def submit(self, bgr):
        # Encola el último frame (descarta previos si hay)
        if not self.q.empty():
            try:
                self.q.get_nowait()
            except Exception:
                pass
        try:
            self.q.put(bgr, block=False)
        except queue.Full:
            pass

    def _loop(self):
        while not self.stop_ev.is_set():
            try:
                bgr = self.q.get(timeout=0.25)
            except queue.Empty:
                continue
            # JPEG encode
            ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                continue
            files = {"image": ("frame.jpg", buf.tobytes(), "image/jpeg")}
            t0 = time.time()
            try:
                r = self.sess.post(f"{self.server_url}/v1/infer", files=files, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                self.last = DetectionResult(
                    boxes=data.get("boxes", []),
                    names=data.get("names", {}),
                    ts=time.time(),
                    latency_ms=(time.time() - t0) * 1000.0,
                )
            except Exception:
                # Mantener last anterior si falla
                continue

    def get_last(self) -> Optional[DetectionResult]:
        return self.last

    def close(self):
        self.stop_ev.set()
        self.worker.join(timeout=1.0)
        self.sess.close()
