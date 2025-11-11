from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from .schemas import InferResponse, HealthResponse
from .utils import decode_jpeg_to_bgr
from .yolo_engine import YoloEngine

app = FastAPI(title="xEyeProcessor", version="1.0.0")
engine = YoloEngine()

@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}

@app.post("/v1/infer", response_model=InferResponse)
async def infer(image: UploadFile = File(...)):
    if image.content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(415, detail="Use image/jpeg")
    data = await image.read()
    bgr = decode_jpeg_to_bgr(data)
    if bgr is None:
        raise HTTPException(400, detail="JPEG inválido")
    out = engine.infer(bgr)
    return JSONResponse(out)
