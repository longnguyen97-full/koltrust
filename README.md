# KOLTrust

KOLTrust simulates a Big Data workflow for creator trust scoring from social data and realtime livestream events.

## Main Sources

* **data-pipeline**: crawl YouTube/TikTok, run batch ETL, and build Bronze -> Silver -> Gold -> Serving datasets.
* **livestream-simulator**: generate synthetic livestream events from analysis-profile creator seeds.
* **realtime-kol-trust**: API, dashboard, Kafka, Spark, Cassandra, Airflow, MinIO, Prometheus, and Grafana.
* **koltrust_common**: small shared package for dataset path resolution.

## Setup

```bash
uv sync
uv run python -m doctor
```

## Data Collection

Input sources:

```text
data-pipeline/data/input/vn_channels.txt
data-pipeline/data/input/tiktok_usernames.txt
```

Crawl raw data:

```bash
uv run --directory data-pipeline python crawl_raw_data.py
uv run --directory data-pipeline python crawl_tiktok_data.py
```

Output:

```text
data-pipeline/data/raw/
```

## ETL & Data Quality

Build and validate the processed dataset:

```bash
uv run python -m build-dataset
uv run python -m validate-data
```

Output:

```text
data-pipeline/data/processed/bronze/
data-pipeline/data/processed/silver/
data-pipeline/data/processed/gold/
data-pipeline/data/processed/serving/
realtime-kol-trust/dataset/
```

## Model/Data Split

YouTube/TikTok processed data is split by creator:

```text
train split            -> model training
eval split             -> offline evaluation
analysis_profile split -> analysis and simulator profile seeds
```

The simulator can reuse creator names/profile fields from `analysis_profile`, but it generates fresh live metrics/events. Realtime prediction does not use the training labels as input.

## Offline Debug Commands

These commands are optional smoke tests, not the main realtime path:

```bash
uv run python -m process-sample
uv run python -m pull-simulator-sample --kol-id yt_finance_04 --limit 500
```

Main realtime flow:

```text
simulator API
-> replay-producer
-> Kafka kol_raw_events
-> Spark Streaming
-> MinIO raw/processed/serving layers
-> Cassandra serving table
-> API/dashboard
```

## Local Services

```bash
uv run --directory livestream-simulator python -m uvicorn app.main:app --reload --port 8010
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

```text
Simulator: http://localhost:8010/docs
API:       http://localhost:8000/docs
Dashboard: http://localhost:8501
```

## Full Stack Docker

Start the full stack:

```bash
docker compose --project-directory realtime-kol-trust up --build
```

Services:

* Kafka + Kafka UI
* Cassandra
* Spark Streaming
* FastAPI
* Streamlit
* Simulator + replay producer
* Airflow
* MinIO
* Prometheus
* Grafana

URLs:

```text
API:        http://localhost:8000/docs
Dashboard:  http://localhost:8501
Kafka UI:   http://localhost:8080
Airflow:    http://localhost:8081
MinIO:      http://localhost:9002
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000
```

Stop:

```bash
docker compose --project-directory realtime-kol-trust down
```

## MinIO

Publish the batch dataset:

```bash
uv run python -m publish-minio
```

Buckets:

```text
koltrust-raw
koltrust-processed
koltrust-serving
```

## Quick CLI

```bash
uv run python -m doctor
uv run python -m build-dataset
uv run python -m validate-data
uv run python -m pipeline
uv run python -m publish-minio
```

## Docs

```text
documents/SOURCE_LAYOUT.md
documents/PRESENTATION.md
documents/API_DOCS.md
documents/MONITORING.md
documents/GOVERNANCE.md
airflow/dags/koltrust_pipeline_dag.py
```
