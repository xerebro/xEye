"""Pan/Tilt servo control helpers."""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

try:  # pragma: no cover - optional dependency for development
    import pigpio
except ImportError:  # pragma: no cover - allows development without hardware
    pigpio = None  # type: ignore

logger = logging.getLogger(__name__)

PAN_LIMITS = (-90.0, 90.0)
TILT_LIMITS = (-30.0, 30.0)

PAN_GPIO = int(os.getenv("PAN_GPIO", "12"))
TILT_GPIO = int(os.getenv("TILT_GPIO", "13"))

SERVO_MIN_US = 500
SERVO_MAX_US = 2500
PAN_RANGE_DEG = PAN_LIMITS[1] - PAN_LIMITS[0]
TILT_RANGE_DEG = TILT_LIMITS[1] - TILT_LIMITS[0]
RELATIVE_MAX_STEP = 15.0


@dataclass
class PTZState:
    pan_deg: float = 0.0
    tilt_deg: float = 0.0
    limits: Tuple[Tuple[float, float], Tuple[float, float]] = (PAN_LIMITS, TILT_LIMITS)

    def to_dict(self) -> dict:
        return {
            "pan_deg": self.pan_deg,
            "tilt_deg": self.tilt_deg,
            "limits": {"pan": list(self.limits[0]), "tilt": list(self.limits[1])},
        }


class PanTilt(ABC):
    """Abstract controller for pan/tilt mechanisms."""

    def __init__(self, state: PTZState | None = None) -> None:
        self._state = state or PTZState()

    @property
    def state(self) -> PTZState:
        return self._state

    def clamp_pan(self, value: float) -> float:
        return max(self._state.limits[0][0], min(self._state.limits[0][1], value))

    def clamp_tilt(self, value: float) -> float:
        return max(self._state.limits[1][0], min(self._state.limits[1][1], value))

    def apply_absolute(self, pan_deg: float | None = None, tilt_deg: float | None = None) -> PTZState:
        if pan_deg is not None:
            self._state.pan_deg = self.clamp_pan(pan_deg)
        if tilt_deg is not None:
            self._state.tilt_deg = self.clamp_tilt(tilt_deg)
        self._apply()
        return self._state

    def apply_relative(self, dpan: float = 0.0, dtilt: float = 0.0) -> PTZState:
        dpan = max(-RELATIVE_MAX_STEP, min(RELATIVE_MAX_STEP, dpan))
        dtilt = max(-RELATIVE_MAX_STEP, min(RELATIVE_MAX_STEP, dtilt))
        return self.apply_absolute(self._state.pan_deg + dpan, self._state.tilt_deg + dtilt)

    def home(self) -> PTZState:
        return self.apply_absolute(0.0, 0.0)

    @abstractmethod
    def _apply(self) -> None:
        """Persist the current angles to the hardware."""


class PigpioPanTilt(PanTilt):
    """pigpio-backed controller."""

    def __init__(self, state: PTZState | None = None, host: str = "localhost") -> None:
        super().__init__(state)
        if pigpio is None:
            raise RuntimeError("pigpio is not available; install and enable pigpiod")
        self._pi = pigpio.pi(host)
        if not self._pi.connected:  # pragma: no cover - runtime validation
            raise RuntimeError("Failed to connect to pigpiod")
        self._configure_gpio()

    def _configure_gpio(self) -> None:
        self._pi.set_mode(PAN_GPIO, pigpio.OUTPUT)
        self._pi.set_mode(TILT_GPIO, pigpio.OUTPUT)
        self._apply()

    def _apply(self) -> None:
        self._pi.set_servo_pulsewidth(PAN_GPIO, self._deg_to_pulse(self._state.pan_deg, PAN_LIMITS))
        self._pi.set_servo_pulsewidth(TILT_GPIO, self._deg_to_pulse(self._state.tilt_deg, TILT_LIMITS))

    def close(self) -> None:
        try:
            self.home()
        except Exception:  # pragma: no cover - best effort homing
            logger.warning("Failed to home pan/tilt before shutdown", exc_info=True)
        self._pi.set_servo_pulsewidth(PAN_GPIO, 0)
        self._pi.set_servo_pulsewidth(TILT_GPIO, 0)
        self._pi.stop()

    @staticmethod
    def _deg_to_pulse(deg: float, limits: Tuple[float, float]) -> int:
        span = limits[1] - limits[0]
        normalized = (deg - limits[0]) / span
        pulse = SERVO_MIN_US + normalized * (SERVO_MAX_US - SERVO_MIN_US)
        return int(max(SERVO_MIN_US, min(SERVO_MAX_US, pulse)))


class MockPanTilt(PanTilt):
    """In-memory controller used for development and testing."""

    def _apply(self) -> None:  # pragma: no cover - no hardware interaction
        logger.debug("MockPanTilt updated: %s", self._state)
