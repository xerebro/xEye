# xEye – Raspberry Pi Camera Controller

xEye provides a minimal yet complete control surface for Raspberry Pi 5 based
camera rigs.  The stack couples a FastAPI backend with a Vite/React frontend and
includes support for MJPEG streaming, camera parameter control, snapshots and
pan/tilt servo management.

## Features

- MJPEG stream (`/api/stream.mjpg`) backed by Picamera2 with post-processing,
  graceful disconnect handling and cache-busting headers
- Snapshot endpoint (`/api/snapshot.jpg`) returning the latest JPEG frame
- Camera settings API (GET/PATCH) mapping to libcamera controls
- Pan/Tilt API supporting absolute, relative and home positioning (PCA9685 I²C or lgpio fallback)
- Health check (`/healthz`) exposing the number of active streaming clients
- React single-page frontend with joystick PTZ control and camera sliders

## Getting Started

### Prerequisites

```bash
sudo apt update
sudo apt install -y python3-pip python3-pil python3-picamera2
```

If you plan to drive servos with the PCA9685 hat/board, enable I²C and install the bus packages:

```bash
# Habilitar I2C (si no está habilitado)
sudo raspi-config nonint do_i2c 0   # o vía GUI raspi-config

# Paquetes necesarios
sudo apt update
sudo apt install -y i2c-tools python3-smbus

# Verificar que el PCA9685 responde en 0x40 (valor típico)
i2cdetect -y 1
# Deberías ver "40" en la tabla
```

For the optional software-PWM fallback (`LgpioPanTilt`), install `python3-lgpio`.

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Environment variables:

- `FRONTEND_ORIGIN` – origin allowed by CORS (default `http://localhost:5173`)
- `USE_PCA9685` – set to `1` to force the PCA9685 driver, `0` to skip it (default: try PCA9685 then fall back to lgpio)
- `I2C_BUS` – I²C bus number for the PCA9685 (default `1`)
- `PCA9685_ADDR` – PCA9685 I²C address in decimal or hex (default `0x40`)
- `PAN_CHANNEL` / `TILT_CHANNEL` – PCA9685 channel numbers for each servo (defaults `1` and `0`)
- `SERVO_HZ` – PWM frequency in Hz (default `50`)
- `SERVO_MIN_US` / `SERVO_MAX_US` – pulse width range in microseconds (defaults `500` / `2500`)
- `PAN_MIN_DEG` / `PAN_MAX_DEG` – soft pan limits in degrees (defaults `-90` / `90`)
- `TILT_MIN_DEG` / `TILT_MAX_DEG` – soft tilt limits in degrees (defaults `-30` / `30`)
- `PAN_GPIO`, `TILT_GPIO` – GPIO pins for the lgpio fallback (defaults `12` & `13`)
- `UVICORN_HOST` / `UVICORN_PORT` – override bind address and port if needed


export FRONTEND_ORIGIN="http://localhost:5173"
export USE_PCA9685=1          # opcional: fuerza el driver I²C
export I2C_BUS=1
export PCA9685_ADDR=0x40
export PAN_CHANNEL=1
export TILT_CHANNEL=0
export SERVO_MIN_US=500
export SERVO_MAX_US=2500
export UVICORN_HOST="0.0.0.0"
export UVICORN_PORT=8000

# Para el fallback lgpio (software PWM) puedes definir:
# export USE_PCA9685=0
# export PAN_GPIO=12
# export TILT_GPIO=13

# Start the backend
uvicorn server.main:app --host "$UVICORN_HOST" --port "$UVICORN_PORT"

### Frontend

```bash
cd web
npm install
npm run dev
```

Build for production using `npm run build`. The FastAPI app automatically mounts
`web/dist` (when present) as a static directory and honours the configured
`FRONTEND_ORIGIN` for CORS.

### Deployment with systemd

A sample unit is provided in `deploy/xeye.service`:

```bash
sudo cp deploy/xeye.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xeye.service
```

The unit spins up a virtual environment and then executes Uvicorn against
`server.main:app`.  Adjust the unit if you rely on additional services (for
example removing the legacy `pigpiod` helpers when only PCA9685 is used).

## Development Notes

- A mock camera provider is activated automatically when Picamera2 is
  unavailable; configure `USE_PCA9685=0` if you need to skip hardware PTZ during
  development.
- MJPEG frames reuse the last encoded JPEG to minimise CPU load; frame rate and
  resolution defaults can be tuned within `server/camera.py`.
- Camera setting PATCH requests are debounced (200 ms) and batched client-side
  to avoid overwhelming the ISP while sliders are dragged.
- Code style is standardised via Black/Ruff (Python) and ESLint/Prettier
  (frontend). Refer to `.editorconfig`, `pyproject.toml` and the configs in
  `web/` for tooling defaults.

## Quick checklist for the Raspberry Pi 5

- PCA9685 visible en el bus I²C (`i2cdetect -y 1` muestra `0x40`) o fallback lgpio configurado
- `/api/stream.mjpg` stable for >30 seconds without CPU spikes
- `/api/camera/settings` accepts manual exposure tweaks and applies them
- Joystick and keyboard shortcuts (arrows, `Space`, `R`) respect the configured
  soft limits
- Snapshot downloads are named `photo_YYYYMMDDTHHMM.jpg`

## License

MIT License. See `LICENSE` if provided.
