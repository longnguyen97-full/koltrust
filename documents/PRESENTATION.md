# Báo Cáo Thuyết Trình: KOLTrust Big Data Pipeline

## 1. Tổng Quan Đề Tài

KOLTrust là hệ thống dữ liệu phục vụ đánh giá độ tin cậy của KOL/creator dựa trên dữ liệu mạng xã hội và dữ liệu livestream. Bài toán đặt ra là từ các tín hiệu rời rạc như lượt xem, lượt thích, bình luận, sentiment, tần suất đăng tải và hành vi tăng trưởng bất thường, hệ thống cần tạo ra một chỉ số tổng hợp để hỗ trợ nhận diện KOL đáng tin cậy, cần theo dõi hoặc có rủi ro.

Project được thiết kế theo tư duy production data pipeline:

- Data sources từ YouTube, TikTok và livestream simulator.
- Ingestion layer để crawl và đưa dữ liệu vào raw lake.
- Data lake local để lưu raw data.
- Batch ETL theo medallion architecture: bronze, silver, gold.
- Data quality gate bằng Pandera.
- Orchestration bằng Airflow DAG.
- Object storage/data lake local bằng MinIO.
- Monitoring bằng Prometheus/Grafana.
- Serving layer cho API, dashboard và realtime replay.
- Streaming pipeline bằng Kafka, Spark Streaming và Cassandra.
- Rule/ML baseline để tạo trust score.

## 2. Bài Toán Nghiệp Vụ

Đánh giá KOL không nên chỉ dựa vào follower hoặc view. Một KOL có thể có tương tác cao nhưng vẫn rủi ro nếu:

- Engagement tăng bất thường.
- Comment có dấu hiệu spam hoặc bot.
- Sentiment của cộng đồng giảm.
- Tỷ lệ like/comment/share không tự nhiên.
- Nội dung có dấu hiệu quảng cáo thiếu minh bạch.

Hệ thống gom nhiều tín hiệu thành các metric:

- `engagement_rate`
- `sentiment_score`
- `activity_score`
- `is_suspicious`
- `trust_score`
- `trust_label`

Kết quả phục vụ phân loại KOL theo nhóm `trusted`, `watch` hoặc `risky`.

## 3. Kiến Trúc Pipeline Tổng Thể

```text
Data Sources
    |
    v
Ingestion Layer
    |
    v
Raw Data Lake
    |
    v
Batch ETL / Medallion Processing
    |
    |-- Bronze Layer
    |-- Silver Layer
    |-- Gold Layer
    |-- Data Quality Gate
    v
Serving Layer
    |
    |-- API
    |-- Dashboard
    |-- Offline Scoring
    `-- Realtime Replay
            |
            v
        Kafka / Spark Streaming / Cassandra
```

Luồng này mô phỏng cách hệ thống dữ liệu production thường tổ chức: dữ liệu được thu thập, lưu raw, xử lý qua các tầng chất lượng tăng dần, kiểm tra chất lượng, rồi publish sang serving layer.

## 4. Data Sources Và Ingestion

Nguồn dữ liệu:

| Nguồn | Vai trò |
| --- | --- |
| YouTube | Channel, video, public stats, comments |
| TikTok | Creator, video, engagement stats |
| Livestream simulator | Realtime events để demo stream processing |

Seed list được chuẩn bị thủ công:

```text
data-pipeline/data/input/vn_channels.txt
data-pipeline/data/input/tiktok_usernames.txt
```

Lệnh crawl YouTube:

```powershell
uv run --directory data-pipeline python crawl_raw_data.py --channel-list data/input/vn_channels.txt --max-videos 10 --max-comments 50
```

Lệnh crawl TikTok:

```powershell
uv run --directory data-pipeline python crawl_tiktok_data.py --username-list data/input/tiktok_usernames.txt --max-videos 20
```

Raw output:

```text
data-pipeline/data/raw/
```

## 5. Data Lake Và Medallion Architecture

Processed dataset nằm tại:

```text
data-pipeline/data/processed/
|-- bronze/
|-- silver/
|-- gold/
`-- serving/
```

### Bronze Layer

Bronze giữ dữ liệu đã làm sạch cơ bản nhưng vẫn tách theo datasource:

- YouTube channels/videos.
- TikTok creators/videos.
- Deduplicate theo ID.
- Loại record thiếu dữ liệu quan trọng.

### Silver Layer

Silver hợp nhất dữ liệu và enrich:

- Unified influencer features.
- Comment sentiment.
- Engagement metrics.
- Schema chung cho YouTube/TikTok.

### Gold Layer

Gold phục vụ analytics và scoring:

- Engagement features.
- Suspicious engagement.
- Creator trust scores.

### Serving Layer

Serving là dữ liệu đã sẵn sàng cho runtime:

```text
data-pipeline/data/processed/serving/kol_events.jsonl
realtime-kol-trust/dataset/
```

## 6. Batch Pipeline

Lệnh chạy batch ETL:

```powershell
uv run python -m build-dataset
```

Pipeline thực hiện:

1. Đọc raw data.
2. Build bronze tables.
3. Build silver unified features và comment sentiment.
4. Build gold features và trust scores.
5. Export serving events.
6. Sync dataset sang runtime layer.

## 7. Data Quality Với Pandera

Project có data quality gate bằng Pandera:

```powershell
uv run python -m validate-data
```

Các bảng được validate:

- `silver/unified/vietnam_influencer_features.csv`
- `silver/comments/vietnam_comments_sentiment.csv`
- `gold/features/trust_scores.csv`
- `serving/kol_events.jsonl`

Các rule kiểm tra chính:

- Cột bắt buộc phải tồn tại.
- Kiểu dữ liệu phải đúng.
- Score nằm trong khoảng hợp lệ.
- Count không âm.
- Platform và sentiment thuộc tập giá trị hợp lệ.
- JSONL parse được từng dòng và có key bắt buộc.

Report được ghi ra:

```text
data-pipeline/data/processed/quality_report.json
```

Trong production, bước này nên là quality gate bắt buộc trước khi publish dataset sang serving layer.

## 8. Orchestration Với Airflow

Project có Airflow DAG:

```text
airflow/dags/koltrust_pipeline_dag.py
```

DAG mô tả flow:

```text
build_dataset -> validate_data -> process_sample
```

Airflow chịu trách nhiệm:

- Schedule job theo ngày/giờ.
- Retry khi task fail.
- Theo dõi trạng thái từng task.
- Lưu lịch sử chạy pipeline.
- Gửi alert khi job fail hoặc data quality fail.

Trong phạm vi đồ án, Airflow chạy chung trong Docker Compose stack. Demo local vẫn có thể chạy bằng CLI khi không muốn bật Docker.

Chạy Airflow:

```powershell
docker compose --project-directory realtime-kol-trust up --build
```

Mở:

```text
http://localhost:8081
```

## 8.1. Object Storage Với MinIO

Project dùng local filesystem làm data lake mặc định, đồng thời có MinIO để mô phỏng object storage kiểu S3 trong production.

Chạy MinIO:

```powershell
docker compose --project-directory realtime-kol-trust up --build
```

Publish processed data lên MinIO:

```powershell
uv run python -m publish-minio
```

Bucket mặc định:

```text
koltrust-raw
koltrust-processed
koltrust-serving
```

MinIO giúp trình bày rõ hướng nâng cấp từ local data lake sang object storage production.

## 9. Realtime Event Pipeline

Livestream simulator sinh các event:

- `view`
- `like`
- `share`
- `purchase`
- `comment`

Luồng realtime:

```text
Livestream Simulator
    |
    v
kol_events.jsonl / API export
    |
    v
Kafka replay producer
    |
    v
Kafka topic
    |
    v
Spark Streaming
    |
    v
Cassandra
```

Simulator giúp demo các tình huống:

- Livestream bình thường.
- Livestream viral.
- Bot attack.
- Trust drop do sentiment xấu.

## 10. Scoring Và ML Baseline

Hệ thống dùng rule-based scoring và ML baseline.

Nhóm feature chính:

| Nhóm | Ý nghĩa |
| --- | --- |
| Engagement | Mức độ tương tác |
| Sentiment | Phản ứng cộng đồng |
| Activity | Tần suất hoạt động |
| Suspicious signals | Dấu hiệu bất thường |
| Profile reputation | Uy tín nền của KOL |

Output:

```text
realtime-kol-trust/data/processed/trust_scores.json
```

## 11. Serving Layer: API Và Dashboard

Chạy API:

```powershell
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
```

Mở:

```text
http://localhost:8000/docs
```

Chạy dashboard:

```powershell
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

Mở:

```text
http://localhost:8501
```

Dashboard hiển thị:

- Trust score.
- Risk label.
- Engagement.
- Sentiment.
- Bot probability.
- Suspicious events.

## 12. Monitoring Và Alerting

Hiện trạng:

- Crawler có file log.
- API có endpoint `/alerts`.
- API có endpoint `/metrics` cho Prometheus.
- Docker Compose chạy Prometheus/Grafana chung trong stack mặc định.
- Dashboard hiển thị một số metric vận hành và business metric.
- Spark có checkpoint khi chạy streaming.

Chưa production-grade:

- Chưa có Alertmanager gửi email/Slack.
- Chưa có log aggregation.
- Chưa có SLA/SLO tracking.
- Grafana hiện mới có datasource, chưa có dashboard JSON hoàn chỉnh.

Đề xuất production:

- Prometheus cho metrics.
- Grafana cho dashboard hệ thống.
- Alertmanager cho cảnh báo.
- ELK/OpenSearch cho log.
- Airflow callbacks cho task failure.

## 13. Security Và Governance

Hiện trạng:

- API keys đọc từ environment hoặc `.env`, không hard-code.
- Comment và author identifier có thể hash trong release build.
- Dataset chỉ dùng public fields.
- Có data dictionary, manifest và dataset stats.

Chưa production-grade:

- Chưa có auth cho FastAPI.
- Chưa có secret manager.
- Chưa có data catalog/lineage.
- Chưa có RBAC.
- Chưa có audit log.
- Chưa có retention policy.

Đề xuất production:

- Vault hoặc cloud secret manager.
- OAuth2/JWT/API Gateway.
- Apache Atlas hoặc DataHub cho catalog/lineage.
- RBAC theo vai trò.
- Audit log cho truy cập dữ liệu.
- Data retention và masking policy.

## 14. Kịch Bản Demo

Kiểm tra môi trường:

```powershell
uv run python -m doctor
```

Build dataset:

```powershell
uv run python -m build-dataset
```

Validate data:

```powershell
uv run python -m validate-data
```

Publish lên MinIO:

```powershell
uv run python -m publish-minio
```

Offline scoring:

```powershell
uv run python -m process-sample
```

Chạy simulator:

```powershell
uv run --directory livestream-simulator python -m uvicorn app.main:app --reload --port 8010
```

Kéo event từ simulator:

```powershell
uv run python -m pull-simulator-sample --kol-id yt_finance_04 --limit 500
```

Chạy API/dashboard:

```powershell
uv run --directory realtime-kol-trust python -m uvicorn backend.fastapi.main:app --reload --port 8000
uv run --directory realtime-kol-trust python -m streamlit run dashboard/streamlit/app.py
```

## 15. Nếu Dùng Bộ Công Cụ Apache Chuẩn Hơn

Nếu xây một project Big Data production dựa nhiều trên Apache ecosystem, có thể dùng:

| Nhu cầu | Apache tool phù hợp |
| --- | --- |
| Distributed storage | HDFS hoặc Ozone |
| Batch processing | Spark |
| Stream processing | Flink hoặc Spark Structured Streaming |
| Message broker | Kafka |
| Workflow scheduler | Airflow |
| Table format/lakehouse | Iceberg, Hudi hoặc Delta Lake |
| SQL query engine | Hive, Trino/Presto |
| NoSQL serving store | Cassandra hoặc HBase |
| Metadata/catalog/lineage | Atlas |
| Authorization/governance | Ranger |
| Log/event collection | NiFi hoặc Flume |
| Search/log analytics | Solr hoặc OpenSearch ecosystem |
| Monitoring | Ambari cũ, hoặc Prometheus/Grafana ngoài Apache |

Với project hiện tại, bản đồ án dùng local filesystem làm mặc định và bổ sung MinIO để mô phỏng object storage. Nếu nâng cấp tiếp, có thể chuyển dữ liệu sang Parquet/Iceberg để gần lakehouse production hơn.

## 16. Kết Luận

KOLTrust mô phỏng một pipeline Big Data end-to-end: từ datasource, ingestion, raw lake, medallion ETL, data quality gate, serving layer, realtime replay, streaming processing đến API/dashboard.

Điểm quan trọng là hệ thống không chỉ crawl dữ liệu, mà còn tổ chức dữ liệu thành pipeline có kiểm soát, có validate, có orchestration mẫu và có định hướng monitoring/governance để tiến gần hơn tới production.
