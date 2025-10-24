import time, torch
from ultralytics import YOLO
from . import config

class YoloEngine:
    def __init__(self):
        device = "cuda" if (config.AUTOCUDA and torch.cuda.is_available()) else "cpu"
        self.model = YOLO(config.MODEL_NAME)
        self.model.to(device)
        self.device = device
        self.fp16 = config.FP16 and (device == "cuda")
        # warmup
        _ = self.model.predict(source=[torch.zeros(1,3,config.IMGSZ,config.IMGSZ)], device=self.device, imgsz=config.IMGSZ, verbose=False)
        if self.fp16:
            try:
                for m in self.model.model.modules():
                    if hasattr(m, "half"):
                        m.half()
            except Exception:
                pass

    def infer(self, bgr):
        h, w = bgr.shape[:2]
        t0 = time.time()
        results = self.model.predict(
            source=bgr, imgsz=config.IMGSZ, conf=config.CONF_THRES, iou=config.IOU_THRES,
            device=self.device, verbose=False, half=self.fp16
        )[0]
        dt = (time.time() - t0) * 1000.0
        names = self.model.model.names if hasattr(self.model, "model") else self.model.names
        boxes = []
        if results and results.boxes is not None:
            xyxy = results.boxes.xyxy.cpu().numpy()
            cls = results.boxes.cls.cpu().numpy().astype(int)
            conf = results.boxes.conf.cpu().numpy()
            for (x1,y1,x2,y2), c, p in zip(xyxy, cls, conf):
                boxes.append({
                    "x1": float(x1/w), "y1": float(y1/h), "x2": float(x2/w), "y2": float(y2/h),
                    "cls": int(c), "conf": float(p)
                })
        return {
            "model": config.MODEL_NAME, "img_w": w, "img_h": h, "time_ms": dt,
            "boxes": boxes, "names": {int(k):v for k,v in names.items()} if isinstance(names, dict) else {i:n for i,n in enumerate(names)}
        }
