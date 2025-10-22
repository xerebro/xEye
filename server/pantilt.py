# server/pantilt.py
# Pan/Tilt providers for Raspberry Pi setups (PCA9685 I2C + lgpio fallback)
import errno
import threading
import time
import math

try:
    import smbus
except Exception:
    smbus = None

try:
    import lgpio  # apt: python3-lgpio
except Exception as e:
    lgpio = None


MIN_STEP_DEG = 0.2
GLIDE_MS = 200


class PCA9685:
    MODE1 = 0x00
    MODE2 = 0x01
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    LED0_ON_H = 0x07
    LED0_OFF_L = 0x08
    LED0_OFF_H = 0x09

    def __init__(
        self,
        address=0x40,
        busnum=1,
        retry=5,
        retry_delay=0.003,
        debug=False,
    ):
        if smbus is None:
            raise RuntimeError("python3-smbus not installed")
        self.bus = smbus.SMBus(busnum)
        self.address = address
        self.retry = retry
        self.retry_delay = retry_delay
        self.debug = debug
        time.sleep(0.01)
        self._write(self.MODE1, 0x00)  # wake
        time.sleep(0.01)
        self._write(self.MODE2, 0x04)  # OUTDRV
        time.sleep(0.005)

    def _wbd(self, reg, val):
        for _ in range(self.retry):
            try:
                self.bus.write_byte_data(self.address, reg, int(val) & 0xFF)
                return
            except OSError as e:
                if getattr(e, "errno", None) in (errno.EAGAIN, 11):
                    time.sleep(self.retry_delay)
                    continue
                raise
            except BlockingIOError:
                time.sleep(self.retry_delay)
                continue
        raise BlockingIOError("I2C write failed after retries")

    def _rbd(self, reg):
        for _ in range(self.retry):
            try:
                return self.bus.read_byte_data(self.address, reg) & 0xFF
            except OSError as e:
                if getattr(e, "errno", None) in (errno.EAGAIN, 11):
                    time.sleep(self.retry_delay)
                    continue
                raise
            except BlockingIOError:
                time.sleep(self.retry_delay)
                continue
        raise BlockingIOError("I2C read failed after retries")

    def _write(self, reg, val):
        self._wbd(reg, val)

    def _read(self, reg):
        return self._rbd(reg)

    def setPWMFreq(self, hz):
        prescaleval = 25_000_000.0 / 4096.0 / float(hz) - 1.0
        prescale = int(math.floor(prescaleval + 0.5))
        prescale = max(3, min(255, prescale))
        oldmode = self._read(self.MODE1)
        self._write(self.MODE1, (oldmode & 0x7F) | 0x10)  # sleep
        time.sleep(0.005)
        self._write(self.PRESCALE, prescale)
        self._write(self.MODE1, oldmode)  # wake
        time.sleep(0.005)
        self._write(self.MODE1, oldmode | 0x80)  # restart
        time.sleep(0.005)

    def setPWM(self, channel, on, off):
        base = self.LED0_ON_L + 4 * int(channel)
        self._write(base + 0, on & 0xFF)
        self._write(base + 1, (on >> 8) & 0x0F)
        self._write(base + 2, off & 0xFF)
        self._write(base + 3, (off >> 8) & 0x0F)

    def setServoPulse(self, channel, pulse_us, period_us=20000):
        ticks = int(round((float(pulse_us) * 4096.0) / float(period_us)))
        ticks = max(0, min(4095, ticks))
        self.setPWM(channel, 0, ticks)


class Pca9685PanTilt:
    def __init__(
        self,
        i2c_bus=1,
        address=0x40,
        pan_ch=1,
        tilt_ch=0,
        pan_lim=(-90, 90),
        tilt_lim=(-30, 30),
        servo_hz=50,
        min_us=500,
        max_us=2500,
    ):
        self.pwm = PCA9685(address=address, busnum=i2c_bus)
        self.pwm.setPWMFreq(servo_hz)
        self.pan_ch, self.tilt_ch = int(pan_ch), int(tilt_ch)
        self.pan_lim, self.tilt_lim = pan_lim, tilt_lim
        self.min_us, self.max_us = int(min_us), int(max_us)
        self.pan_deg = 0.0
        self.tilt_deg = 0.0
        self.home()

    def _deg_to_us(self, deg: float) -> int:
        # map -90..+90 → min..max (or adjust if 0..180 fits better to your linkage)
        # Here we assume -90..+90 -> min..max
        deg = float(deg)
        span = self.max_us - self.min_us
        # normalize -90..+90 to 0..1
        t = (deg + 90.0) / 180.0
        return int(self.min_us + span * max(0.0, min(1.0, t)))

    def _clamp(self, value: float, limits: tuple[float, float]) -> float:
        return float(max(limits[0], min(limits[1], value)))

    def _write_position(self, pan: float, tilt: float) -> None:
        self.pwm.setServoPulse(self.pan_ch, self._deg_to_us(pan))
        self.pwm.setServoPulse(self.tilt_ch, self._deg_to_us(tilt))

    def set_absolute(self, pan_deg: float, tilt_deg: float):
        pan = self._clamp(pan_deg, self.pan_lim)
        tilt = self._clamp(tilt_deg, self.tilt_lim)
        self.pan_deg = pan
        self.tilt_deg = tilt
        self._write_position(self.pan_deg, self.tilt_deg)

    def _glide_to(self, pan_target: float, tilt_target: float, smooth_ms: int) -> None:
        steps = max(1, int(smooth_ms / 5))
        pan_step = (pan_target - self.pan_deg) / steps
        tilt_step = (tilt_target - self.tilt_deg) / steps

        if abs(pan_step) < MIN_STEP_DEG and abs(tilt_step) < MIN_STEP_DEG:
            self.pan_deg = pan_target
            self.tilt_deg = tilt_target
            self._write_position(self.pan_deg, self.tilt_deg)
            return

        for _ in range(steps):
            self.pan_deg += pan_step
            self.tilt_deg += tilt_step
            self._write_position(self.pan_deg, self.tilt_deg)
            time.sleep(0.005)

        self.pan_deg = pan_target
        self.tilt_deg = tilt_target
        self._write_position(self.pan_deg, self.tilt_deg)

    def move_relative(self, dpan: float, dtilt: float, smooth_ms: int = GLIDE_MS):
        target_pan = self._clamp(self.pan_deg + dpan, self.pan_lim)
        target_tilt = self._clamp(self.tilt_deg + dtilt, self.tilt_lim)
        self._glide_to(target_pan, target_tilt, smooth_ms)

    def set_relative(self, dpan: float, dtilt: float):
        self.move_relative(dpan, dtilt)

    def home(self):
        self.set_absolute(0.0, 0.0)

    def close(self):
        # Optionally stop pulses (PCA keeps last value; many setups prefer holding torque)
        pass

class LgpioPanTilt:
    """
    Software-PWM (50 Hz) Pan/Tilt for Raspberry Pi 5 via lgpio.
    Generates 20 ms frames and sets a single high pulse per frame per servo.
    Good enough for hobby servos; not jitter-free like pigpio, but works on Pi 5.
    """
    def __init__(self, pan_pin=12, tilt_pin=13, pan_lim=(-90, 90), tilt_lim=(-30, 30)):
        if lgpio is None:
            raise RuntimeError("lgpio not available. Install python3-lgpio.")
        self._h = lgpio.gpiochip_open(0)  # rp1 lives at gpiochip0
        self.pan_pin, self.tilt_pin = int(pan_pin), int(tilt_pin)
        for p in (self.pan_pin, self.tilt_pin):
            lgpio.gpio_claim_output(self._h, p)
            lgpio.gpio_write(self._h, p, 0)

        self.pan_lim = pan_lim
        self.tilt_lim = tilt_lim
        self.pan_deg = 0.0
        self.tilt_deg = 0.0

        # 50 Hz servo PWM
        self._period_s = 0.020
        self._lock = threading.Lock()
        self._running = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def _deg_to_us(self, deg: float) -> int:
        # center 1500us, ±90° ≈ 500..2500us (adjust if your horns need different travel)
        return int(1500 + (deg / 90.0) * 1000)

    def _pulse(self, pin: int, pw_us: int):
        # Raise pin for pw_us microseconds inside the 20ms frame
        if pw_us <= 0:
            return
        lgpio.gpio_write(self._h, pin, 1)
        # busy-wait short micro-sleep for better accuracy (still software)
        t_end = time.perf_counter() + pw_us / 1_000_000.0
        while time.perf_counter() < t_end:
            pass
        lgpio.gpio_write(self._h, pin, 0)

    def _loop(self):
        # single thread schedules both channels to keep pulses aligned per frame
        next_frame = time.perf_counter()
        while self._running:
            with self._lock:
                pan_us  = max(500, min(2500, self._deg_to_us(self.pan_deg)))
                tilt_us = max(500, min(2500, self._deg_to_us(self.tilt_deg)))
                pan_pin, tilt_pin = self.pan_pin, self.tilt_pin

            start = time.perf_counter()
            # Start both low, then generate pulses (sequence doesn't matter for servos)
            lgpio.gpio_write(self._h, pan_pin, 0)
            lgpio.gpio_write(self._h, tilt_pin, 0)
            # Pulse pan then tilt (or vice versa). For better overlap, you can interleave.
            self._pulse(pan_pin, pan_us)
            self._pulse(tilt_pin, tilt_us)

            # frame pacing
            next_frame += self._period_s
            sleep = next_frame - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_frame = time.perf_counter() + self._period_s  # skip ahead if lag

    def _clamp(self, value: float, limits: tuple[float, float]) -> float:
        return float(max(limits[0], min(limits[1], value)))

    def _set_position(self, pan: float, tilt: float) -> None:
        with self._lock:
            self.pan_deg = pan
            self.tilt_deg = tilt

    def set_absolute(self, pan_deg: float, tilt_deg: float):
        pan = self._clamp(pan_deg, self.pan_lim)
        tilt = self._clamp(tilt_deg, self.tilt_lim)
        self._set_position(pan, tilt)

    def _glide_to(self, pan_target: float, tilt_target: float, smooth_ms: int) -> None:
        steps = max(1, int(smooth_ms / 5))
        with self._lock:
            pan_start = self.pan_deg
            tilt_start = self.tilt_deg
        pan_step = (pan_target - pan_start) / steps
        tilt_step = (tilt_target - tilt_start) / steps

        if abs(pan_step) < MIN_STEP_DEG and abs(tilt_step) < MIN_STEP_DEG:
            self._set_position(pan_target, tilt_target)
            return

        current_pan, current_tilt = pan_start, tilt_start
        for _ in range(steps):
            current_pan += pan_step
            current_tilt += tilt_step
            self._set_position(current_pan, current_tilt)
            time.sleep(0.005)

        self._set_position(pan_target, tilt_target)

    def move_relative(self, dpan: float, dtilt: float, smooth_ms: int = GLIDE_MS):
        with self._lock:
            pan_start = self.pan_deg
            tilt_start = self.tilt_deg
        target_pan = self._clamp(pan_start + dpan, self.pan_lim)
        target_tilt = self._clamp(tilt_start + dtilt, self.tilt_lim)
        self._glide_to(target_pan, target_tilt, smooth_ms)

    def set_relative(self, dpan: float, dtilt: float):
        self.move_relative(dpan, dtilt)

    def home(self):
        self.set_absolute(0.0, 0.0)

    def close(self):
        self._running = False
        try:
            self._t.join(timeout=0.5)
        except: pass
        for p in (self.pan_pin, self.tilt_pin):
            try:
                lgpio.gpio_write(self._h, p, 0)
                lgpio.gpio_free(self._h, p)
            except: pass
        lgpio.gpiochip_close(self._h)
