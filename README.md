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

## Detección asistida por GPU

El backend puede superponer detecciones provenientes del nuevo servicio `xEyeProcessor`
(ubicado en `xEyeProcessor/`). Configure las siguientes variables de entorno en la
Raspberry Pi para habilitar el envío de frames al procesador con GPU:

- `XEYE_PROCESSOR_URL`: URL base del servicio remoto (por ejemplo `http://192.168.0.10:8000`).
- `DET_EVERY_N`: envía uno de cada *N* frames para inferencia (por defecto `2`).
- `DET_MAX_AGE_MS` *(opcional)*: tiempo máximo en milisegundos para considerar válida una detección (por defecto `500`).
- `DET_TIMEOUT` *(opcional)*: timeout de la petición HTTP en segundos (por defecto `1.5`).

También se incluye un ejemplo de cliente de cámara en `backend/run_cam_client.py` y una
unit systemd de referencia en `deploy/pi/xeye-client.service` para automatizar el arranque
en la Raspberry Pi.
