# server/pantilt.py
# New provider for Raspberry Pi 5 using lgpio (software PWM 50Hz)
import threading, time, math
try:
    import lgpio  # apt: python3-lgpio
except Exception as e:
    lgpio = None

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
        # center 1500us, �90� ? 500..2500us (adjust if your horns need different travel)
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

    def set_absolute(self, pan_deg: float, tilt_deg: float):
        with self._lock:
            self.pan_deg  = float(max(self.pan_lim[0], min(self.pan_lim[1], pan_deg)))
            self.tilt_deg = float(max(self.tilt_lim[0], min(self.tilt_lim[1], tilt_deg)))

    def set_relative(self, dpan: float, dtilt: float):
        with self._lock:
            self.pan_deg  = float(max(self.pan_lim[0], min(self.pan_lim[1], self.pan_deg  + dpan)))
            self.tilt_deg = float(max(self.tilt_lim[0], min(self.tilt_lim[1], self.tilt_deg + dtilt)))

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
