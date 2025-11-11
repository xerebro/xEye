from __future__ import annotations

import os

import cv2
from picamera2 import Picamera2

from detection_client import DetectionClient
from overlay import draw_detections

SERVER = os.getenv("XEYE_PROCESSOR_URL", "http://<PC_GPU_IP>:8000")
SKIP_N = int(os.getenv("DET_EVERY_N", "2"))  # enviar 1 cada N frames


def main():
    picam2 = Picamera2()
    picam2.preview_configuration.main.size = (1280, 720)
    picam2.preview_configuration.main.format = "RGB888"
    picam2.configure("preview")
    picam2.start()

    client = DetectionClient(SERVER, timeout=1.5)
    f = 0
    try:
        while True:
            frame = picam2.capture_array()  # RGB
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            if f % SKIP_N == 0:
                client.submit(bgr)
            f += 1

            det = client.get_last()
            annotated = draw_detections(bgr.copy(), det)

            cv2.imshow("xEye Preview (Pi overlay)", annotated)
            if cv2.waitKey(1) == 27:
                break
    finally:
        client.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
