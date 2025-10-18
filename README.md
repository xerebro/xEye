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
- Pan/Tilt API supporting absolute, relative and home positioning (pigpio)
- Health check (`/healthz`) exposing the number of active streaming clients
- React single-page frontend with joystick PTZ control and camera sliders

## Getting Started

### Prerequisites

```bash
sudo apt update
sudo apt install -y python3-pip python3-pil python3-picamera2 pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Environment variables:

- `FRONTEND_ORIGIN` – origin allowed by CORS (default `http://localhost:5173`)
- `PAN_GPIO`, `TILT_GPIO` – override servo GPIO pins (defaults 12 & 13)
- `UVICORN_HOST` / `UVICORN_PORT` – override bind address and port if needed


export FRONTEND_ORIGIN="http://localhost:5173"
export PAN_GPIO=12
export TILT_GPIO=13
export UVICORN_HOST="0.0.0.0"
export UVICORN_PORT=8000

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

The unit spins up a virtual environment, ensures `pigpiod` is running and then
executes Uvicorn against `server.main:app`.

## Development Notes

- A mock camera and PTZ controller are activated automatically on systems where
  Picamera2 or pigpio are unavailable.  This keeps local development usable.
- MJPEG frames reuse the last encoded JPEG to minimise CPU load; frame rate and
  resolution defaults can be tuned within `server/camera.py`.
- Camera setting PATCH requests are debounced (200 ms) and batched client-side
  to avoid overwhelming the ISP while sliders are dragged.
- Code style is standardised via Black/Ruff (Python) and ESLint/Prettier
  (frontend). Refer to `.editorconfig`, `pyproject.toml` and the configs in
  `web/` for tooling defaults.

## Quick checklist for the Raspberry Pi 5

- `pigpiod` enabled and running (`sudo systemctl status pigpiod`)
- `/api/stream.mjpg` stable for >30 seconds without CPU spikes
- `/api/camera/settings` accepts manual exposure tweaks and applies them
- Joystick and keyboard shortcuts (arrows, `Space`, `R`) respect the configured
  soft limits
- Snapshot downloads are named `photo_YYYYMMDDTHHMM.jpg`

## License

MIT License. See `LICENSE` if provided.
