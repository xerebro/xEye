"""Camera management utilities for the Raspberry Pi control backend."""
from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:  # pragma: no cover - import side effect only validated on device
    from picamera2 import Picamera2
    from libcamera import controls as libcamera_controls
except ImportError:  # pragma: no cover - allows development without hardware
    Picamera2 = None  # type: ignore
    libcamera_controls = None  # type: ignore

PICAMERA_AVAILABLE = Picamera2 is not None

from PIL import Image

logger = logging.getLogger(__name__)


JPEG_BOUNDARY = "frame"
DEFAULT_STREAM_SIZE = (640, 480)
DEFAULT_FPS = 15
DEFAULT_JPEG_QUALITY = 92

DEFAULT_SATURATION = 1.15
DEFAULT_CONTRAST = 1.05
DEFAULT_SHARPNESS = 1.10

_AWB_MODE_ATTRS: Dict[str, str] = {
    "auto": "AwbAuto",
    "incandescent": "AwbIncandescent",
    "tungsten": "AwbTungsten",
    "fluorescent": "AwbFluorescent",
    "indoor": "AwbIndoor",
    "daylight": "AwbDaylight",
    "cloudy": "AwbCloudy",
    "custom": "AwbCustom",
}


_active_frame_provider: Any | None = None


def set_active_frame_provider(provider: Any | None) -> None:
    """Record the active frame provider for helper functions."""

    global _active_frame_provider
    _active_frame_provider = provider


def get_active_frame_provider() -> Any | None:
    """Return the active frame provider if one has been started."""

    return _active_frame_provider


def _provider_for_helpers() -> Any | None:
    provider = get_active_frame_provider()
    if provider is None:
        logger.debug("No active frame provider available for camera helper")
    return provider


def apply_color_and_quality(
    saturation: Optional[float] = None,
    contrast: Optional[float] = None,
    sharpness: Optional[float] = None,
    ev: Optional[float] = None,
) -> None:
    """Apply color-related controls to the active frame provider."""

    provider = _provider_for_helpers()
    if provider is None:
        return

    patch: Dict[str, float] = {}
    if saturation is not None:
        patch["saturation"] = float(saturation)
    if contrast is not None:
        patch["contrast"] = float(contrast)
    if sharpness is not None:
        patch["sharpness"] = float(sharpness)
    if ev is not None:
        patch["ev"] = float(ev)

    if not patch:
        return

    provider.update_settings(patch)


def apply_wb_and_lowlight_combo(selection: str) -> None:
    """Toggle white balance presets and low-light bundle."""

    provider = _provider_for_helpers()
    if provider is None:
        return

    preset = (selection or "auto").lower()
    patch: Dict[str, Any] = {"awb_mode": preset}
    if preset == "low_light":
        patch["low_light"] = True
        patch["awb_enable"] = True
    else:
        patch["low_light"] = False

    provider.update_settings(patch)


def set_zoom(level: float) -> float:
    """Apply digital zoom to the active frame provider and return the clamped level."""

    provider = _provider_for_helpers()
    try:
        zoom = float(level)
    except (TypeError, ValueError):
        zoom = 1.0

    zoom = max(1.0, min(4.0, zoom))
    if provider is None:
        return zoom

    provider.update_settings({"zoom": zoom})
    try:
        current_zoom = float(getattr(provider.settings, "zoom", zoom))
    except Exception:
        current_zoom = zoom
    return current_zoom


def _resolve_awb_enum(preset: str) -> Any:
    if libcamera_controls is None:
        return None
    name = _AWB_MODE_ATTRS.get(preset.lower())
    if not name:
        return None
    return getattr(libcamera_controls.AwbModeEnum, name, None)


@dataclass
class CameraSettings:
    """Serializable camera configuration."""

    exposure_mode: str = "auto"
    exposure_time_us: int = 5000
    iso_gain: float = 2.0
    awb_enable: bool = True
    awb_mode: str = "auto"
    contrast: float = DEFAULT_CONTRAST
    saturation: float = DEFAULT_SATURATION
    sharpness: float = DEFAULT_SHARPNESS
    ev: float = 0.0
    low_light: bool = False
    zoom: float = 1.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "exposure_mode": self.exposure_mode,
            "exposure_time_us": self.exposure_time_us,
            "iso_gain": self.iso_gain,
            "awb_enable": self.awb_enable,
            "awb_mode": self.awb_mode,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "sharpness": self.sharpness,
            "ev": self.ev,
            "low_light": self.low_light,
            "zoom": self.zoom,
        }

    @classmethod
    def from_patch(cls, current: "CameraSettings", payload: Dict[str, object]) -> "CameraSettings":
        data = current.to_dict()
        for key, value in payload.items():
            if key not in data:
                raise ValueError(f"Unsupported setting: {key}")
            data[key] = value
        if "low_light" in payload and "awb_mode" not in payload:
            if bool(payload["low_light"]):
                data["awb_mode"] = "low_light"
            elif str(data.get("awb_mode", "auto")).lower() == "low_light":
                data["awb_mode"] = "auto"

        awb_mode = str(data.get("awb_mode", "auto")).lower()
        if awb_mode == "low_light":
            data["low_light"] = True
            data["awb_enable"] = True
        else:
            data["low_light"] = False

        return cls(**data)


class FrameProvider:
    """Captures JPEG frames from Picamera2 in the background."""

    def __init__(
        self,
        resolution: tuple[int, int] = DEFAULT_STREAM_SIZE,
        fps: int = DEFAULT_FPS,
        jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    ) -> None:
        if Picamera2 is None:
            raise RuntimeError("Picamera2 is not available. Install picamera2 on the Pi.")

        self._resolution = resolution
        self._fps = fps
        try:
            self._jpeg_quality = max(1, min(95, int(jpeg_quality)))
        except (TypeError, ValueError):
            self._jpeg_quality = DEFAULT_JPEG_QUALITY
        self._picam = Picamera2()
        try:
            self._picam.options["quality"] = self._jpeg_quality
        except Exception:
            logger.debug("Unable to set Picamera2 JPEG quality option", exc_info=True)
        self._settings = CameraSettings()
        self._low_light_enabled = False
        self._default_frame_limits: tuple[int, int] | None = None
        self._sensor_resolution = getattr(self._picam, "sensor_resolution", None)

        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._last_jpeg: Optional[bytes] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return

        frame_limit = (int(1e6 / self._fps), int(1e6 / self._fps))
        self._default_frame_limits = frame_limit
        stream_config = self._picam.create_video_configuration(
            main={"size": self._resolution, "format": "BGR888"},
            controls={"FrameDurationLimits": frame_limit},
        )
        self._picam.configure(stream_config)
        self._apply_controls(self._settings)
        self._picam.start()

        self._running = True
        set_active_frame_provider(self)
        self._thread = threading.Thread(target=self._capture_loop, name="FrameProvider", daemon=True)
        self._thread.start()
        logger.info("Frame provider started at %sx%s @ %sfps", *self._resolution, self._fps)

    def stop(self) -> None:
        with self._condition:
            self._running = False
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._picam.stop()
        if get_active_frame_provider() is self:
            set_active_frame_provider(None)
        logger.info("Frame provider stopped")

    def _capture_loop(self) -> None:
        target_delay = 1.0 / self._fps
        while self._running:
            start = time.monotonic()
            frame = self._picam.capture_array("main")
            image = Image.fromarray(frame)

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=self._jpeg_quality)
            jpeg = buffer.getvalue()

            with self._condition:
                self._last_jpeg = jpeg
                self._condition.notify_all()

            elapsed = time.monotonic() - start
            remaining = target_delay - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _wait_for_jpeg_locked(self, timeout: float = 1.0) -> Optional[bytes]:
        deadline = time.monotonic() + timeout
        with self._condition:
            if self._last_jpeg is not None:
                return self._last_jpeg

            while self._running and self._last_jpeg is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)

            return self._last_jpeg

    def get_latest_jpeg(self, wait: bool = True, timeout: float = 1.0) -> Optional[bytes]:
        if not wait:
            with self._condition:
                return self._last_jpeg
        return self._wait_for_jpeg_locked(timeout)

    async def wait_for_jpeg(self, timeout: float = 1.0) -> Optional[bytes]:
        return await asyncio.to_thread(self._wait_for_jpeg_locked, timeout)

    @property
    def settings(self) -> CameraSettings:
        return self._settings

    @property
    def is_running(self) -> bool:
        return self._running

    def update_settings(self, patch: Dict[str, object]) -> CameraSettings:
        new_settings = CameraSettings.from_patch(self._settings, patch)
        self._settings = new_settings
        self._apply_controls(new_settings)
        return new_settings

    # Internal utilities -------------------------------------------------
    def _apply_controls(self, settings: CameraSettings) -> None:
        controls: Dict[str, object] = {}
        if settings.exposure_mode == "auto":
            controls["AeEnable"] = True
        else:
            controls["AeEnable"] = False
            controls["ExposureTime"] = int(settings.exposure_time_us)
            controls["AnalogueGain"] = float(settings.iso_gain)

        awb_mode = str(settings.awb_mode or "auto").lower()
        low_light_selected = awb_mode == "low_light"
        awb_enable = bool(settings.awb_enable) or low_light_selected
        controls["AwbEnable"] = awb_enable
        if awb_enable:
            enum = _resolve_awb_enum("auto" if low_light_selected else awb_mode)
            if enum is not None:
                controls["AwbMode"] = enum

        try:
            self._picam.set_controls(controls)
        except Exception:  # pragma: no cover - hardware specific failure path
            logger.exception("Failed to set camera controls: %s", controls)

        self._apply_low_light(settings)
        self._apply_color_controls(settings)
        self._apply_zoom(settings.zoom)

    def _apply_low_light(self, settings: CameraSettings) -> None:
        if not PICAMERA_AVAILABLE:
            return

        awb_mode = str(settings.awb_mode or "auto").lower()
        enable = bool(awb_mode == "low_light" and settings.exposure_mode == "auto")
        if enable == self._low_light_enabled:
            return

        try:
            if enable:
                controls = {
                    "AeEnable": True,
                    "AeExposureMode": 2,
                    "FrameDurationLimits": (20000, 200000),
                    "NoiseReductionMode": 2,
                }
                self._picam.set_controls(controls)
                try:
                    if "HdrMode" in getattr(self._picam, "camera_controls", {}):
                        self._picam.set_controls({"HdrMode": 3})
                except Exception:
                    logger.debug("HDR Night mode not available", exc_info=True)
            else:
                limits = self._default_frame_limits or (int(1e6 / self._fps), int(1e6 / self._fps))
                controls = {
                    "AeExposureMode": 0,
                    "FrameDurationLimits": limits,
                    "NoiseReductionMode": 1,
                }
                if self._low_light_enabled:
                    try:
                        if "HdrMode" in getattr(self._picam, "camera_controls", {}):
                            self._picam.set_controls({"HdrMode": 0})
                    except Exception:
                        logger.debug("Failed to disable HDR mode", exc_info=True)
                self._picam.set_controls(controls)
        except Exception:  # pragma: no cover - hardware specific failure path
            logger.exception("Failed to toggle low-light controls")
        finally:
            self._low_light_enabled = enable

    def _apply_color_controls(self, settings: CameraSettings) -> None:
        if not PICAMERA_AVAILABLE:
            return

        controls: Dict[str, Any] = {
            "Saturation": float(settings.saturation),
            "Contrast": float(settings.contrast),
            "Sharpness": float(settings.sharpness),
            "ExposureValue": float(settings.ev),
        }

        try:
            self._picam.set_controls(controls)
        except Exception:  # pragma: no cover - hardware specific failure path
            logger.exception("Failed to set color controls: %s", controls)

    def _apply_zoom(self, level: float) -> None:
        if not PICAMERA_AVAILABLE:
            return

        try:
            zoom = max(1.0, min(4.0, float(level)))
        except (TypeError, ValueError):
            zoom = 1.0

        sensor_resolution = self._sensor_resolution
        if not sensor_resolution:
            try:
                sensor_resolution = tuple(self._picam.sensor_resolution)  # type: ignore[attr-defined]
                self._sensor_resolution = sensor_resolution
            except Exception:  # pragma: no cover - hardware specific failure path
                return

        sensor_w, sensor_h = sensor_resolution
        scale = 1.0 / zoom
        crop_w = max(1, int(sensor_w * scale))
        crop_h = max(1, int(sensor_h * scale))
        x = max(0, (sensor_w - crop_w) // 2)
        y = max(0, (sensor_h - crop_h) // 2)

        try:
            self._picam.set_controls({"ScalerCrop": (x, y, crop_w, crop_h)})
        except Exception:  # pragma: no cover - hardware specific failure path
            logger.exception("Failed to set zoom controls")


def format_mjpeg_frame(jpeg: bytes) -> bytes:
    header = (
        f"--{JPEG_BOUNDARY}\r\n"
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg)}\r\n\r\n"
    ).encode("ascii")
    return header + jpeg + b"\r\n"


class MockFrameProvider(FrameProvider):
    """Development stub that generates blank frames when Picamera2 is unavailable."""

    def __init__(self, resolution: tuple[int, int] = DEFAULT_STREAM_SIZE) -> None:  # type: ignore[override]
        # Bypass FrameProvider.__init__ which requires Picamera2
        self._resolution = resolution
        self._fps = DEFAULT_FPS
        self._jpeg_quality = DEFAULT_JPEG_QUALITY
        self._settings = CameraSettings()
        self._low_light_enabled = False
        self._default_frame_limits: tuple[int, int] | None = None
        self._sensor_resolution: tuple[int, int] | None = None
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._last_jpeg: Optional[bytes] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._picam = None

    def start(self) -> None:  # type: ignore[override]
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._mock_loop, daemon=True)
        self._thread.start()
        set_active_frame_provider(self)

    def stop(self) -> None:  # type: ignore[override]
        with self._condition:
            self._running = False
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if get_active_frame_provider() is self:
            set_active_frame_provider(None)
        
    def _mock_loop(self) -> None:
        from PIL import ImageDraw  # imported lazily to avoid heavy deps

        width, height = self._resolution
        while self._running:
            img = Image.new("RGB", self._resolution, (30, 30, 30))
            draw = ImageDraw.Draw(img)
            text = "Mock Camera"
            draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(0, 122, 255), width=4)
            draw.text((20, 20), text, fill=(255, 255, 255))

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self._jpeg_quality)
            jpeg = buffer.getvalue()
            with self._condition:
                self._last_jpeg = jpeg
                self._condition.notify_all()
            time.sleep(1.0 / self._fps)

    def _apply_controls(self, settings: CameraSettings) -> None:  # type: ignore[override]
        # No-op for mock implementation
        return
