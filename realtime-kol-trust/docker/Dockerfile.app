FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY realtime-kol-trust/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY realtime-kol-trust .
COPY koltrust_common ./koltrust_common

CMD ["python", "-m", "backend.fastapi.main"]
