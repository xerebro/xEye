"""FastAPI application exposing camera streaming and PTZ control."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator, Dict

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .camera import FrameProvider, MockFrameProvider, PICAMERA_AVAILABLE, format_mjpeg_frame, JPEG_BOUNDARY
from .pantilt import MockPanTilt, PanTilt, PigpioPanTilt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


class CameraSettingsPatch(BaseModel):
    exposure_mode: str | None = Field(None, regex="^(auto|manual)$")
    exposure_time_us: int | None = Field(None, ge=100, le=1_000_000)
    iso_gain: float | None = Field(None, ge=1.0, le=8.0)
    awb_enable: bool | None = None
    awb_mode: str | None = Field(None, regex="^(auto|incandescent|fluorescent|daylight|cloudy)$")
    brightness: float | None = Field(None, ge=-1.0, le=1.0)
    contrast: float | None = Field(None, ge=0.0, le=2.0)
    saturation: float | None = Field(None, ge=0.0, le=2.0)
    sharpness: float | None = Field(None, ge=0.0, le=2.0)

    def to_payload(self) -> Dict[str, object]:
        return {k: v for k, v in self.model_dump(exclude_none=True).items()}


class PTZAbsolute(BaseModel):
    pan_deg: float | None = Field(None, ge=-180, le=180)
    tilt_deg: float | None = Field(None, ge=-90, le=90)


class PTZRelative(BaseModel):
    dpan_deg: float = Field(0.0, ge=-90, le=90)
    dtilt_deg: float = Field(0.0, ge=-90, le=90)


def create_frame_provider() -> FrameProvider | MockFrameProvider:
    if PICAMERA_AVAILABLE:
        try:
            provider = FrameProvider()
            provider.start()
            return provider
        except Exception:  # pragma: no cover - requires hardware
            logger.exception("Falling back to mock camera provider")
    mock = MockFrameProvider()
    mock.start()
    return mock


def create_pantilt_controller() -> PanTilt:
    try:
        controller = PigpioPanTilt()
        return controller
    except Exception:  # pragma: no cover - requires hardware
        logger.warning("Using mock pan/tilt controller (pigpio unavailable)")
        return MockPanTilt()


frame_provider = create_frame_provider()
pantilt_controller = create_pantilt_controller()

allowed_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app = FastAPI(title="xEye Camera Controller", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    frame_provider.stop()
    if isinstance(pantilt_controller, PigpioPanTilt):  # pragma: no cover - hardware path
        pantilt_controller.close()


@app.get("/api/camera/settings")
async def get_camera_settings() -> Dict[str, object]:
    return frame_provider.settings.to_dict()


@app.patch("/api/camera/settings")
async def patch_camera_settings(payload: CameraSettingsPatch) -> Dict[str, object]:
    patch = payload.to_payload()
    if not patch:
        return frame_provider.settings.to_dict()
    try:
        settings = frame_provider.update_settings(patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return settings.to_dict()


async def mjpeg_generator() -> AsyncIterator[bytes]:
    while True:
        frame = frame_provider.get_latest_jpeg(wait=True, timeout=2.0)
        if frame is None:
            await asyncio.sleep(0.1)  # type: ignore[name-defined]
            continue
        yield format_mjpeg_frame(frame)


@app.get("/api/stream.mjpg")
async def stream_mjpeg() -> StreamingResponse:
    return StreamingResponse(mjpeg_generator(), media_type=f"multipart/x-mixed-replace; boundary={JPEG_BOUNDARY}")


@app.get("/api/snapshot.jpg")
async def snapshot() -> Response:
    frame = frame_provider.get_latest_jpeg(wait=True, timeout=2.0)
    if frame is None:
        raise HTTPException(status_code=503, detail="No frame available")
    return Response(content=frame, media_type="image/jpeg")


@app.get("/api/pantilt")
async def get_pantilt_state() -> Dict[str, object]:
    return pantilt_controller.state.to_dict()


@app.post("/api/pantilt/absolute")
async def pantilt_absolute(request: PTZAbsolute) -> Dict[str, object]:
    state = pantilt_controller.apply_absolute(request.pan_deg, request.tilt_deg)
    return state.to_dict()


@app.post("/api/pantilt/relative")
async def pantilt_relative(request: PTZRelative) -> Dict[str, object]:
    state = pantilt_controller.apply_relative(request.dpan_deg, request.dtilt_deg)
    return state.to_dict()


@app.post("/api/pantilt/home")
async def pantilt_home() -> Dict[str, object]:
    state = pantilt_controller.home()
    return state.to_dict()


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str) -> FileResponse:
    """Serve the built frontend if it exists, otherwise return 404."""
    if not STATIC_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    target = STATIC_DIR / full_path
    if not target.exists():
        target = STATIC_DIR / "index.html"
    return FileResponse(target)
