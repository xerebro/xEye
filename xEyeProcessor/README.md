# xEyeProcessor

xEyeProcessor es un microservicio FastAPI que expone un endpoint HTTP para realizar inferencia de objetos mediante modelos YOLO ejecutándose en GPU NVIDIA. El servicio está pensado para recibir imágenes JPEG desde el cliente (por ejemplo, una Raspberry Pi) y devolver metadatos con las detecciones.

---

## 1. Requisitos previos

### Hardware
- GPU NVIDIA compatible con CUDA 12.1 (ej. RTX 30xx, RTX 40xx, etc.).
- Drivers NVIDIA instalados en el host.

### Software
- [Docker](https://docs.docker.com/engine/install/) 24+ y [Docker Compose](https://docs.docker.com/compose/install/) (v2 recomendada).
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) configurado para permitir acceso a la GPU dentro de contenedores.
- Conexión a internet (los pesos YOLO se descargan automáticamente al primer arranque).

> **Verificación rápida**: ejecuta `nvidia-smi` en el host y asegúrate de que devuelve información de tu GPU antes de continuar.

---

## 2. Estructura del proyecto

```
xEyeProcessor/
├── Dockerfile                # Imagen base (CUDA 12.1 + Python + dependencias)
├── README.md                 # Este documento
├── app/                      # Código fuente del servicio FastAPI
│   ├── main.py               # Definición de endpoints
│   ├── yolo_engine.py        # Inicialización del modelo YOLO y lógica de inferencia
│   ├── config.py             # Lectura de variables de entorno
│   ├── utils.py              # Utilidades (decodificación JPEG, etc.)
│   └── schemas.py            # Modelos pydantic para las respuestas
├── docker-compose.gpu.yml    # Orquestación para levantar el servicio con GPU
├── requirements.txt          # Dependencias de Python
├── scripts/
│   └── run_dev.sh            # Script de desarrollo con autoreload
└── tests/                    # Pruebas unitarias (placeholder)
```

---

## 3. Variables de entorno disponibles

Puedes definirlas en `docker-compose.gpu.yml`, exportarlas en la terminal o pasarlas directamente al contenedor. Todas son opcionales.

| Variable      | Descripción                                                                 | Valor por defecto |
|---------------|------------------------------------------------------------------------------|-------------------|
| `MODEL_NAME`  | Peso YOLO a utilizar (cualquier modelo soportado por `ultralytics`).         | `yolo11s.pt`      |
| `CONF_THRES`  | Umbral de confianza mínimo para reportar una detección.                      | `0.35`            |
| `IOU_THRES`   | Umbral IoU para NMS.                                                         | `0.45`            |
| `IMGSZ`       | Tamaño de la imagen para inferencia (lado más largo).                        | `640`             |
| `FP16`        | Forzar inferencia en FP16 cuando hay GPU (`1` = sí, `0` = no).               | `1`               |
| `AUTOCUDA`    | Detectar automáticamente si hay GPU disponible (`1`) o usar CPU (`0`).       | `1`               |
| `UVICORN_*`   | `UVICORN_HOST`, `UVICORN_PORT`, `UVICORN_WORKERS` para tunear el servidor.   | `0.0.0.0`, `8000`, `1` |

---

## 4. Puesta en marcha con Docker (recomendado)

1. Clona el repositorio y posicionate en la carpeta raíz:
   ```bash
   git clone <URL_DEL_REPO>
   cd xEye/xEyeProcessor
   ```
2. Construye y levanta el servicio con Compose:
   ```bash
   docker compose -f docker-compose.gpu.yml up --build -d
   ```
3. Comprueba que el contenedor está ejecutándose:
   ```bash
   docker compose -f docker-compose.gpu.yml ps
   ```
4. Verifica el endpoint de salud desde tu máquina o desde otro host en la red:
   ```bash
   curl http://<IP_DEL_HOST>:8000/health
   # {"status":"ok"}
   ```

Para detener el servicio:
```bash
docker compose -f docker-compose.gpu.yml down
```

---

## 5. Desarrollo local sin Docker

Solo recomendado si ya tienes Python 3.10+ y los drivers CUDA/cuDNN correctamente configurados en tu máquina.

```bash
cd xEyeProcessor
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
export UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000
python -m uvicorn app.main:app --host $UVICORN_HOST --port $UVICORN_PORT --reload
```

> Si no dispones de GPU, establece `AUTOCUDA=0` y `FP16=0` para forzar la ejecución en CPU (mucho más lenta, solo para pruebas básicas).

---

## 6. Endpoints de la API

| Método | Ruta        | Descripción                               |
|--------|-------------|-------------------------------------------|
| GET    | `/health`   | Comprueba que el servicio está disponible.|
| POST   | `/v1/infer` | Recibe una imagen JPEG y devuelve detecciones.

### Ejemplo `curl`
```bash
curl -X POST http://<IP_DEL_HOST>:8000/v1/infer \
  -F "image=@frame.jpg;type=image/jpeg"
```
Respuesta (ejemplo):
```json
{
  "model": "yolo11s.pt",
  "img_w": 1280,
  "img_h": 720,
  "time_ms": 14.7,
  "boxes": [
    {"x1":0.10,"y1":0.22,"x2":0.35,"y2":0.60,"cls":0,"conf":0.87}
  ],
  "names": {"0":"person","1":"bicycle","2":"car"}
}
```

Las coordenadas están normalizadas en el rango `[0.0, 1.0]` para reducir el tamaño de la respuesta.

---

## 7. Pruebas

Actualmente se incluyen pruebas de ejemplo. Puedes ejecutarlas con:
```bash
cd xEyeProcessor
pytest
```

---

## 8. Sugerencias de rendimiento
- Empieza con el modelo `yolo11s.pt` y un tamaño `IMGSZ=640`. Si tienes holgura de GPU, puedes subir a `yolo11m.pt` o mayores.
- Mantén `FP16=1` para aprovechar tensores en media precisión cuando la GPU lo soporte.
- El tiempo reportado (`time_ms`) corresponde únicamente a la inferencia, no incluye el tiempo de subida/descarga de la imagen.
- Al usar clientes remotos (como la Raspberry Pi), ajusta la frecuencia de envío (`DET_EVERY_N`) para equilibrar latencia vs. carga de red.

---

## 9. Solución de problemas

| Problema                                      | Posible solución |
|-----------------------------------------------|------------------|
| `docker compose` no detecta la GPU            | Comprueba que `nvidia-smi` funciona y que `nvidia-container-toolkit` está instalado. Reinicia el demonio de Docker tras la instalación. |
| Error `torch.cuda.is_available() == False`    | Asegúrate de ejecutar el contenedor con acceso a la GPU (`--gpus all` o la sección `deploy.resources` del compose). |
| Descarga lenta de pesos YOLO                  | Verifica tu conexión a internet. Puedes predescargar el archivo `.pt` y montarlo en `/root/.cache/ultralytics`. |
| Latencia alta en inferencia                   | Reduce `IMGSZ`, utiliza un modelo más pequeño (`yolo11n.pt`) o incrementa `DET_EVERY_N` en el cliente. |

---

## 10. Próximos pasos sugeridos
- Añadir pruebas unitarias para `app/yolo_engine.py` y utilidades auxiliares.
- Automatizar la construcción y publicación de la imagen en un registry interno.
- Documentar integración con el cliente Raspberry Pi (`backend/`).

---

¿Dudas o mejoras? Abre un issue o PR en el repositorio principal.
