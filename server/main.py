"""FastAPI application exposing camera streaming and PTZ control."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import typing
from typing import Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .camera import FrameProvider, MockFrameProvider, PICAMERA_AVAILABLE, format_mjpeg_frame, JPEG_BOUNDARY
from .pantilt import MockPanTilt, PanTilt, PigpioPanTilt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CameraSettingsPatch(BaseModel):
    exposure_mode: Optional[Literal["auto", "manual"]] = None
    exposure_time_us: Optional[int] = Field(None, ge=100, le=1_000_000)
    iso_gain: Optional[float] = Field(None, ge=1.0, le=8.0)
    awb_enable: Optional[bool] = None
    awb_mode: Optional[Literal["auto", "incandescent", "fluorescent", "daylight", "cloudy"]] = None
    brightness: Optional[float] = Field(None, ge=-1.0, le=1.0)
    contrast: Optional[float] = Field(None, ge=0.0, le=2.0)
    saturation: Optional[float] = Field(None, ge=0.0, le=2.0)
    sharpness: Optional[float] = Field(None, ge=0.0, le=2.0)

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

_stream_clients = 0
_stream_lock: asyncio.Lock | None = None


def _get_stream_lock() -> asyncio.Lock:
    global _stream_lock
    if _stream_lock is None:
        _stream_lock = asyncio.Lock()
    return _stream_lock


@asynccontextmanager
async def _track_stream_client() -> None:
    global _stream_clients
    lock = _get_stream_lock()
    async with lock:
        _stream_clients += 1
    try:
        yield
    finally:
        async with lock:
            _stream_clients = max(0, _stream_clients - 1)


async def _stream_client_count() -> int:
    lock = _get_stream_lock()
    async with lock:
        return _stream_clients


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


@app.get("/api/stream.mjpg")
async def stream_mjpeg(request: Request) -> StreamingResponse:
    boundary = JPEG_BOUNDARY

    async def frame_iterator() -> typing.AsyncGenerator[bytes, None]:
        async with _track_stream_client():
            try:
                while frame_provider.is_running:
                    jpeg = await frame_provider.wait_for_jpeg(timeout=1.0)
                    if jpeg is None:
                        if not frame_provider.is_running:
                            break
                        continue
                    yield format_mjpeg_frame(jpeg)
                    if await request.is_disconnected():
                        break
            except asyncio.CancelledError:  # pragma: no cover - cancellation path
                logger.info("Client disconnected from MJPEG stream")
                raise

    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    return StreamingResponse(
        frame_iterator(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers=headers,
    )


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


@app.get("/healthz")
async def healthcheck() -> Dict[str, object]:
    return {"ok": True, "clients": await _stream_client_count()}


# Serve built frontend if available (mount after /api routes)
DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
