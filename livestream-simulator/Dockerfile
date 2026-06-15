FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KOLTRUST_DATASET_ROOT=/workspace/realtime-kol-trust/dataset

WORKDIR /workspace

COPY realtime-kol-trust/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

COPY livestream-simulator ./livestream-simulator
COPY koltrust_common ./koltrust_common

WORKDIR /workspace/livestream-simulator

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
