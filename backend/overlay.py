import cv2


def draw_detections(bgr, det):
    if not det or not getattr(det, "boxes", None):
        return bgr
    h, w = bgr.shape[:2]
    for box in det.boxes:
        x1 = int(box["x1"] * w)
        y1 = int(box["y1"] * h)
        x2 = int(box["x2"] * w)
        y2 = int(box["y2"] * h)
        cls = box["cls"]
        conf = box["conf"]
        label = f"{det.names.get(cls, str(cls))} {conf:.2f}"
        cv2.rectangle(bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            bgr,
            label,
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return bgr
