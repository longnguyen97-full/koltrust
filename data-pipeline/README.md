# Data Pipeline

Source này phụ trách datasource và batch ETL cho đồ án KOLTrust.

```text
data/
|-- input/       # seed list crawl thủ công
|-- raw/         # raw lake từ YouTube/TikTok
`-- processed/
    |-- bronze/  # cleaned tables theo datasource
    |-- silver/  # unified/comments
    |-- gold/    # features/trust scores
    `-- serving/ # export cho realtime/Kafka replay
```

## Setup

Chạy từ root repo:

```powershell
uv --version
uv sync
```

## Input

Seed list:

```text
data/input/vn_channels.txt
data/input/tiktok_usernames.txt
```

## Crawl YouTube

Theo danh sách channel:

```powershell
uv run --directory data-pipeline python crawl_raw_data.py --channel-list data/input/vn_channels.txt --max-videos 10 --max-comments 50
```

Một video:

```powershell
uv run --directory data-pipeline python crawl_raw_data.py --video-id VIDEO_ID --max-comments 50
```

Build seed channel list:

```powershell
uv run --directory data-pipeline python collect_kol_seeds.py --max-results 20 --overwrite
```

## Crawl TikTok

Một username:

```powershell
uv run --directory data-pipeline python crawl_tiktok_data.py --username USERNAME --max-videos 20
```

Danh sách username:

```powershell
uv run --directory data-pipeline python crawl_tiktok_data.py --username-list data/input/tiktok_usernames.txt --max-videos 20
```

## Build ETL

Chạy trực tiếp:

```powershell
uv run --directory data-pipeline python build_dataset.py
```

Chạy qua root CLI và sync sang realtime:

```powershell
uv run python -m build-dataset
```

Output chính:

```text
data/processed/bronze/
data/processed/silver/
data/processed/gold/
data/processed/serving/kol_events.jsonl
```
