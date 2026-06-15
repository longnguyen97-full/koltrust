# Realtime KOL Trust

Runtime/serving layer cua do an:

- FastAPI expose API va metrics.
- Streamlit dashboard.
- Kafka replay producer doc simulator API va day vao `kol_raw_events`.
- Spark Streaming ghi raw/processed/serving layers vao MinIO.
- Cassandra chi luu serving columns da tinh gon cho API/dashboard.
- Airflow orchestration.
- MinIO object storage.
- Prometheus/Grafana monitoring.
- ML training/inference doc processed dataset.

## Data Contract

Nguon chinh:

```text
../data-pipeline/data/processed
```

Runtime dataset copy:

```text
dataset/
|-- bronze/
|-- silver/
|-- gold/
`-- serving/
```

Sync tu root repo:

```powershell
uv run python -m sync-dataset
```

`dataset/serving/kol_events.jsonl` chi la sample/debug file. Realtime flow chinh lay live events tu simulator API.

## Run API Local

```powershell
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000/docs
http://localhost:8000/metrics
```

## Run Dashboard Local

```powershell
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

Open:

```text
http://localhost:8501
```

## Replay Kafka Events Local

Start simulator first:

```powershell
uv run --directory livestream-simulator python -m uvicorn app.main:app --reload --port 8010
```

Then produce simulator events into Kafka:

```powershell
uv run --directory realtime-kol-trust python kafka/producers/replay_events.py --loop
```

Optional file replay for offline debug:

```powershell
uv run --directory realtime-kol-trust python kafka/producers/replay_events.py --source file --input dataset/serving/kol_events.jsonl --loop
```

## Docker Full Stack

Tu root repo, chay toan bo stack:

```powershell
docker compose --project-directory realtime-kol-trust up --build
```

Stack gom API, dashboard, Kafka, Kafka UI, Spark Streaming, Cassandra, replay producer, Airflow, MinIO, Prometheus va Grafana.

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

Simulator risk modes are generated independently from creator identity; processed trust labels are not used as realtime inference input.

URL:

```text
API:        http://localhost:8000/docs
Dashboard:  http://localhost:8501
Kafka UI:   http://localhost:8080
Airflow:    http://localhost:8081      admin/admin
MinIO:      http://localhost:9002      minioadmin/minioadmin
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000      admin/admin
```

Stop:

```powershell
docker compose --project-directory realtime-kol-trust down
```
