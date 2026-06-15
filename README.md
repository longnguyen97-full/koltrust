# KOLTrust

Hệ thống KOLTrust mô phỏng quy trình đánh giá độ tin cậy của KOL/Creator từ dữ liệu mạng xã hội và sự kiện realtime.

## Thành phần chính

* **data-pipeline**: Crawl YouTube/TikTok, ETL batch, xây dựng dữ liệu Bronze → Silver → Gold → Serving.
* **livestream-simulator**: Giả lập livestream và phát sinh realtime events.
* **realtime-kol-trust**: API, Dashboard, Kafka, Spark, Cassandra, Airflow, MinIO, Prometheus, Grafana.

## Cài đặt

```bash
uv sync
uv run python -m doctor
```

## Thu thập dữ liệu

Nguồn dữ liệu:

```text
data-pipeline/data/input/vn_channels.txt
data-pipeline/data/input/tiktok_usernames.txt
```

Crawl dữ liệu:

```bash
uv run --directory data-pipeline python crawl_raw_data.py
uv run --directory data-pipeline python crawl_tiktok_data.py
```

Output:

```text
data-pipeline/data/raw/
```

## ETL & Data Quality

Xây dựng và kiểm tra dataset:

```bash
uv run python -m build-dataset
uv run python -m validate-data
```

Output:

```text
bronze/
silver/
gold/
serving/
realtime-kol-trust/dataset/
```

## Offline Scoring

Tính điểm độ tin cậy KOL:

```bash
uv run python -m process-sample
```

Pipeline đầy đủ:

```bash
uv run python -m build-dataset
uv run python -m validate-data
uv run python -m process-sample
```

## Livestream Simulator

Khởi chạy:

```bash
uv run --directory livestream-simulator python -m uvicorn app.main:app --reload --port 8010
```

Truy cập:

```text
http://localhost:8010
http://localhost:8010/docs
```

Lấy dữ liệu mẫu:

```bash
uv run python -m pull-simulator-sample --kol-id yt_finance_04 --limit 500
```

## API & Dashboard

```bash
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

```text
API:       http://localhost:8000/docs
Dashboard: http://localhost:8501
```

## Full Stack Docker

Khởi động toàn bộ hệ thống:

```bash
docker compose --project-directory realtime-kol-trust up --build
```

Bao gồm:

* Kafka + Kafka UI
* Cassandra
* Spark Streaming
* FastAPI
* Streamlit
* Airflow
* MinIO
* Prometheus
* Grafana

Các dịch vụ:

```text
API:        http://localhost:8000/docs
Dashboard:  http://localhost:8501
Kafka UI:   http://localhost:8080
Airflow:    http://localhost:8081
MinIO:      http://localhost:9001
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000
```

Dừng hệ thống:

```bash
docker compose --project-directory realtime-kol-trust down
```

## MinIO

Publish dataset:

```bash
uv run python -m publish-minio
```

Buckets:

```text
koltrust-raw
koltrust-processed
koltrust-serving
```

## CLI Nhanh

```bash
uv run python -m doctor
uv run python -m build-dataset
uv run python -m validate-data
uv run python -m process-sample
uv run python -m pipeline
uv run python -m publish-minio
```

## Tài liệu

```text
documents/PRESENTATION.md
documents/API_DOCS.md
documents/MONITORING.md
documents/GOVERNANCE.md
airflow/dags/koltrust_pipeline_dag.py
```

## Kiến trúc tổng thể
![Mô tả ảnh](documents/kien-truc-tong-the.png)