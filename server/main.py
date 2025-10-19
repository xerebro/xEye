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

from .camera import (
    FrameProvider,
    MockFrameProvider,
    PICAMERA_AVAILABLE,
    format_mjpeg_frame,
    JPEG_BOUNDARY,
)
# PTZ providers (PCA9685 I2C preferred, lgpio fallback)
from .pantilt import LgpioPanTilt, Pca9685PanTilt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------
# Models
# ---------------------------

class CameraSettingsPatch(BaseModel):
    exposure_mode: Optional[Literal["auto", "manual"]] = None
    exposure_time_us: Optional[int] = Field(None, ge=100, le=1_000_000)
    iso_gain: Optional[float] = Field(None, ge=1.0, le=8.0)
    awb_enable: Optional[bool] = None
    awb_mode: Optional[
        Literal["auto", "incandescent", "fluorescent", "daylight", "cloudy"]
    ] = None
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


# ---------------------------
# Providers wiring
# ---------------------------

def create_frame_provider() -> FrameProvider | MockFrameProvider:
    """Instantiate the real Picamera2 provider if available, otherwise Mock."""
    use_mock = os.getenv("USE_MOCK_CAMERA", "0") == "1"
    if not use_mock and PICAMERA_AVAILABLE:
        try:
            provider = FrameProvider()
            provider.start()
            logger.info("Camera provider: %s", provider.__class__.__name__)
            return provider
        except Exception:  # pragma: no cover - requires hardware
            logger.exception("Picamera2 failed to initialize. Falling back to MockFrameProvider.")
    else:
        if use_mock:
            logger.warning("Using MockFrameProvider (USE_MOCK_CAMERA=1)")

    mock = MockFrameProvider()
    mock.start()
    logger.info("Camera provider: %s", mock.__class__.__name__)
    return mock


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        if raw.lower().startswith("0x"):
            return int(raw, 16)
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%s. Using %s", name, raw, default)
        return default


def _parse_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%s. Using %s", name, raw, default)
        return default


def create_pantilt_controller() -> LgpioPanTilt | Pca9685PanTilt:
    """Instantiate PTZ controller preferring PCA9685 with lgpio fallback."""

    pan_lim = (
        _parse_float("PAN_MIN_DEG", -90.0),
        _parse_float("PAN_MAX_DEG", 90.0),
    )
    tilt_lim = (
        _parse_float("TILT_MIN_DEG", -30.0),
        _parse_float("TILT_MAX_DEG", 30.0),
    )
    if pan_lim[0] >= pan_lim[1]:
        logger.warning("Invalid pan limits %s. Using defaults.", pan_lim)
        pan_lim = (-90.0, 90.0)
    if tilt_lim[0] >= tilt_lim[1]:
        logger.warning("Invalid tilt limits %s. Using defaults.", tilt_lim)
        tilt_lim = (-30.0, 30.0)

    use_pca_env = os.getenv("USE_PCA9685")
    force_pca = use_pca_env == "1"
    skip_pca = use_pca_env == "0"

    if not skip_pca:
        i2c_bus = _parse_int("I2C_BUS", 1)
        address = _parse_int("PCA9685_ADDR", 0x40)
        pan_channel = _parse_int("PAN_CHANNEL", 1)
        tilt_channel = _parse_int("TILT_CHANNEL", 0)
        servo_hz = _parse_int("SERVO_HZ", 50)
        servo_min = _parse_int("SERVO_MIN_US", 500)
        servo_max = _parse_int("SERVO_MAX_US", 2500)
        if servo_min >= servo_max:
            logger.warning(
                "Invalid servo pulse range min=%s max=%s. Using defaults.",
                servo_min,
                servo_max,
            )
            servo_min, servo_max = 500, 2500

        try:
            controller = Pca9685PanTilt(
                i2c_bus=i2c_bus,
                address=address,
                pan_ch=pan_channel,
                tilt_ch=tilt_channel,
                pan_lim=pan_lim,
                tilt_lim=tilt_lim,
                servo_hz=servo_hz,
                min_us=servo_min,
                max_us=servo_max,
            )
            logger.info(
                "PTZ provider: %s (i2c_bus=%d addr=0x%02X pan_ch=%d tilt_ch=%d)",
                controller.__class__.__name__,
                i2c_bus,
                address,
                pan_channel,
                tilt_channel,
            )
            return controller
        except Exception:
            if force_pca:
                raise
            logger.exception("Failed to initialize PCA9685 PTZ. Falling back to lgpio.")

    pan_gpio = _parse_int("PAN_GPIO", 12)
    tilt_gpio = _parse_int("TILT_GPIO", 13)
    controller = LgpioPanTilt(
        pan_pin=pan_gpio,
        tilt_pin=tilt_gpio,
        pan_lim=pan_lim,
        tilt_lim=tilt_lim,
    )
    logger.info(
        "PTZ provider: %s (pins pan=%d tilt=%d)",
        controller.__class__.__name__,
        pan_gpio,
        tilt_gpio,
    )
    return controller


frame_provider = create_frame_provider()
pantilt_controller = create_pantilt_controller()

allowed_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app = FastAPI(title="xEye Camera Controller", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Gracefully stop providers on shutdown."""
    try:
        frame_provider.stop()
    except Exception:
        logger.exception("Error stopping frame provider")
    # LgpioPanTilt exposes close(); call it if available.
    close_fn = getattr(pantilt_controller, "close", None)
    if callable(close_fn):  # pragma: no cover - hardware path
        try:
            close_fn()
        except Exception:
            logger.exception("Error closing PTZ controller")


# ---------------------------
# Camera endpoints
# ---------------------------

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


# ---------------------------
# PTZ helpers & endpoints
# ---------------------------

def _ptz_state_dict() -> Dict[str, object]:
    """Build a PTZ state dict from the active controller attributes."""
    try:
        pan = float(getattr(pantilt_controller, "pan_deg", 0.0))
        tilt = float(getattr(pantilt_controller, "tilt_deg", 0.0))
        pan_lim = tuple(getattr(pantilt_controller, "pan_lim", (-90.0, 90.0)))
        tilt_lim = tuple(getattr(pantilt_controller, "tilt_lim", (-30.0, 30.0)))
    except Exception:
        # Safe fallback if attributes are missing
        pan, tilt = 0.0, 0.0
        pan_lim, tilt_lim = (-90.0, 90.0), (-30.0, 30.0)
    return {
        "pan_deg": pan,
        "tilt_deg": tilt,
        "limits": {
            "pan": [pan_lim[0], pan_lim[1]],
            "tilt": [tilt_lim[0], tilt_lim[1]],
        },
    }


@app.get("/api/pantilt")
async def get_pantilt_state() -> Dict[str, object]:
    return _ptz_state_dict()


@app.post("/api/pantilt/absolute")
async def pantilt_absolute(request: PTZAbsolute) -> Dict[str, object]:
    # Use current angles if any field is None
    pan = request.pan_deg if request.pan_deg is not None else getattr(pantilt_controller, "pan_deg", 0.0)
    tilt = request.tilt_deg if request.tilt_deg is not None else getattr(pantilt_controller, "tilt_deg", 0.0)
    pantilt_controller.set_absolute(pan, tilt)  # LgpioPanTilt API
    return _ptz_state_dict()


@app.post("/api/pantilt/relative")
async def pantilt_relative(request: PTZRelative) -> Dict[str, object]:
    pantilt_controller.set_relative(request.dpan_deg, request.dtilt_deg)  # LgpioPanTilt API
    return _ptz_state_dict()


@app.post("/api/pantilt/home")
async def pantilt_home() -> Dict[str, object]:
    pantilt_controller.home()
    return _ptz_state_dict()


# ---------------------------
# Health
# ---------------------------

@app.get("/healthz")
async def healthcheck() -> Dict[str, object]:
    return {"ok": True, "clients": await _stream_client_count()}


# ---------------------------
# Static frontend (mount after /api routes)
# ---------------------------

DIST_DIR = Path(__file__).resolve().parents[1] / "web" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
