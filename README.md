# xEye – Raspberry Pi Camera Controller

xEye provides a minimal yet complete control surface for Raspberry Pi 5 based
camera rigs.  The stack couples a FastAPI backend with a Vite/React frontend and
includes support for MJPEG streaming, camera parameter control, snapshots and
pan/tilt servo management.

## Features

- MJPEG stream (`/api/stream.mjpg`) backed by Picamera2 with post-processing
- Snapshot endpoint (`/api/snapshot.jpg`) returning the latest JPEG frame
- Camera settings API (GET/PATCH) mapping to libcamera controls
- Pan/Tilt API supporting absolute, relative and home positioning (pigpio)
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

### Frontend

```bash
cd web
npm install
npm run dev
```

Build for production using `npm run build` and copy the generated `dist/`
folder to the server directory root (`web/dist`). The backend will serve static
assets automatically when the directory exists.

## Development Notes

- A mock camera and PTZ controller are activated automatically on systems where
  Picamera2 or pigpio are unavailable.  This keeps local development usable.
- MJPEG frames reuse the last encoded JPEG to minimise CPU load; frame rate and
  resolution defaults can be tuned within `server/camera.py`.
- Refer to the project brief in the repository for full functional requirements.

## License

MIT License. See `LICENSE` if provided.
