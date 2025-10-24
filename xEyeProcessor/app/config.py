import os

MODEL_NAME = os.getenv("MODEL_NAME", "yolo11s.pt")
CONF_THRES = float(os.getenv("CONF_THRES", "0.35"))
IOU_THRES = float(os.getenv("IOU_THRES", "0.45"))
IMGSZ = int(os.getenv("IMGSZ", "640"))
AUTOCUDA = os.getenv("AUTOCUDA", "1") == "1"
FP16 = os.getenv("FP16", "1") == "1"
