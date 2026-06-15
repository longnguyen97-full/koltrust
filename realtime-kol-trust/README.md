# Realtime KOL Trust

Runtime/serving layer của đồ án:

- FastAPI đọc processed data và expose API.
- Streamlit dashboard.
- Kafka replay producer đọc `dataset/serving/kol_events.jsonl`.
- Spark Streaming ghi Cassandra.
- Airflow orchestration.
- MinIO object storage.
- Prometheus/Grafana monitoring.
- ML training/inference đọc dataset copy trong `dataset/`.

## Data Contract

Nguồn chính:

```text
../data-pipeline/data/processed
```

Bản copy runtime:

```text
dataset/
|-- bronze/
|-- silver/
|-- gold/
`-- serving/kol_events.jsonl
```

Sync từ root repo:

```powershell
uv run python -m sync-dataset
```

## Run API Local

```powershell
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
```

Mở:

```text
http://localhost:8000/docs
http://localhost:8000/metrics
```

## Run Dashboard Local

```powershell
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

Mở:

```text
http://localhost:8501
```

## Replay Kafka Events Local

```powershell
uv run --directory realtime-kol-trust python kafka/producers/replay_events.py --loop
```

## Docker Full Stack

Từ root repo, chạy toàn bộ stack:

```powershell
docker compose --project-directory realtime-kol-trust up --build
```

Stack gồm API, dashboard, Kafka, Kafka UI, Spark Streaming, Cassandra, replay producer, Airflow, MinIO, Prometheus và Grafana.

Realtime inference flow:

```text
YouTube/TikTok processed dataset
-> creator-level split
-> train split: train model
-> eval split: offline evaluation
-> analysis_profile split: batch analysis and simulator profile seed only

Simulator generated live events
-> Kafka kol_raw_events
-> Spark Streaming
-> MinIO koltrust-raw/streaming/raw_events/
-> MinIO koltrust-processed/streaming/silver/trust_scores/
-> MinIO koltrust-serving/streaming/trust_scores/
-> Cassandra kol_trust.trust_scores
-> API/dashboard
```

Cassandra only keeps the serving columns used by API/dashboard. Raw simulator payloads stay in MinIO.
Simulator risk modes are generated independently from creator identity; processed trust labels are not used as realtime inference input.

URL:

```text
API:        http://localhost:8000/docs
Dashboard:  http://localhost:8501
Kafka UI:   http://localhost:8080
Airflow:    http://localhost:8081      admin/admin
MinIO:      http://localhost:9001      minioadmin/minioadmin
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000      admin/admin
```

Dừng:

```powershell
docker compose --project-directory realtime-kol-trust down
```
