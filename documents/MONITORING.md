# Monitoring Và Alerting

## Hiện Trạng

Project hiện có monitoring ở mức đồ án nhưng đã có nền tảng để chạy local:

- Crawler ghi log file trong `data-pipeline/logs/`.
- FastAPI có endpoint `/alerts` để trả về các KOL/event suspicious.
- FastAPI expose `/metrics` theo format Prometheus.
- Docker Compose chạy Prometheus và Grafana chung trong stack mặc định.
- Streamlit dashboard có các metric trực quan: API status, số KOL, số events, suspicious events, trust score, sentiment, bot probability.
- Spark Streaming có checkpoint directory để phục hồi state khi chạy Docker stack.

## Phần Còn Thiếu So Với Production

Chưa có các thành phần production-grade:

- Chưa có alert manager gửi email/Slack/Telegram.
- Chưa có log aggregation bằng ELK/OpenSearch.
- Chưa có structured run log cho từng ETL job.
- Chưa có SLA/SLO tracking cho crawl và batch jobs.
- Grafana hiện mới provision datasource, chưa có dashboard JSON hoàn chỉnh.

## Đề Xuất Production

Nếu nâng cấp lên production, nên bổ sung:

- Prometheus để scrape metrics từ API, crawler, Spark job.
- Grafana để dashboard hạ tầng và pipeline.
- Alertmanager để gửi cảnh báo khi job fail, data quality fail hoặc suspicious spike quá cao.
- OpenSearch/Elasticsearch + Fluent Bit để gom log.
- Airflow task callbacks để báo lỗi ETL.
- Data quality report từ Pandera lưu theo từng run.

## Metrics Nên Theo Dõi

| Nhóm | Metrics |
| --- | --- |
| Ingestion | số record crawl, số request lỗi, rate limit, thời gian crawl |
| Data quality | số dòng fail schema, missing columns, null rate, duplicate rate |
| Batch ETL | thời gian chạy, số row từng tầng, số record bị loại |
| Streaming | Kafka lag, Spark processed rows/sec, checkpoint age |
| API | request latency, error rate, uptime |
| Business | số KOL risky, suspicious event ratio, trust score distribution |
