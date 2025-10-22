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

### Start the backend
source /home/xerebro/projects/xEye/xEye/.venv/bin/activate
export USE_PCA9685=1
export I2C_BUS=1
export PCA9685_ADDR=0x40
export PAN_CHANNEL=1
export TILT_CHANNEL=0
export SERVO_MIN_US=500
export SERVO_MAX_US=2500
uvicorn server.main:app --host 0.0.0.0 --port 8000 --log-level info



### Frontend

```bash
cd web
npm install
npm run dev
```
