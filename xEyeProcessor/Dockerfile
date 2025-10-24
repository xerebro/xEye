FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev git && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    pip3 install --upgrade pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

EXPOSE 8000
ENV UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000 UVICORN_WORKERS=1 \
    MODEL_NAME=yolo11s.pt CONF_THRES=0.35 IOU_THRES=0.45 IMGSZ=640 \
    AUTOCUDA=1 FP16=1

CMD ["bash", "-lc", "uvicorn app.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT} --workers ${UVICORN_WORKERS}"]
