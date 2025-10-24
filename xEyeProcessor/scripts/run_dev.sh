#!/usr/bin/env bash
set -e
export UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000 UVICORN_WORKERS=1
python -m uvicorn app.main:app --host $UVICORN_HOST --port $UVICORN_PORT --workers $UVICORN_WORKERS --reload
