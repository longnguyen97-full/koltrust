from __future__ import annotations

import csv
from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
import sys
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.core.config import settings
from ml.inference.trust_model import score_event

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from koltrust_common.paths import features_path, manifest_path, serving_events_path, stats_path, trust_scores_path

try:
    from cassandra.cluster import Cluster
except Exception:
    Cluster = None


SAMPLE_PATH = serving_events_path()
DATASET_FEATURES_PATH = features_path()
DATASET_TRUST_SCORES_PATH = trust_scores_path()
DATASET_MANIFEST_PATH = manifest_path()
DATASET_STATS_PATH = stats_path()
CASSANDRA_SCORE_SELECT = """
    SELECT kol_id, event_ts, kol_name, platform, video_id, views, likes, comments,
           shares, followers, engagement_rate, sentiment_score, activity_score,
           anomaly_score, trust_score, is_suspicious, processed_at
    FROM trust_scores
"""

app = FastAPI(title="Real-Time KOL Trustworthiness API", version="0.1.0")
REQUEST_COUNT = Counter(
    "koltrust_http_requests_total",
    "Total HTTP requests received by the KOLTrust API.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "koltrust_http_request_duration_seconds",
    "HTTP request latency for the KOLTrust API.",
    ["method", "path"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def record_prometheus_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def cassandra_session():
    if Cluster is None:
        raise RuntimeError("cassandra-driver is not available in this Python environment")
    cluster = Cluster(
        settings.cassandra_host_list,
        port=settings.cassandra_port,
        connect_timeout=2,
        control_connection_timeout=2,
    )
    session = cluster.connect(settings.cassandra_keyspace)
    session.default_timeout = 2
    return cluster, session


def row_to_dict(row: Any) -> dict[str, Any]:
    data = row._asdict()
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    if "event_ts" in data and "timestamp" not in data:
        data["timestamp"] = data["event_ts"]
    if "trust_score" in data:
        score = to_float(data.get("trust_score"))
        data["trust_label"] = trust_label(score)
        data["trust_source"] = "spark_streaming"
    return data


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def trust_label(score: float) -> str:
    if score >= 70:
        return "high_trust"
    if score >= 45:
        return "medium_trust"
    return "low_trust"


def risk_profile_from_score(score: float) -> str:
    if score >= 70:
        return "trusted"
    if score >= 45:
        return "watch"
    return "risky"


def score_from_event(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("trust_score") is None:
        return score_event(event)
    score = to_float(event.get("trust_score"))
    timestamp = event.get("timestamp") or event.get("collected_at") or event.get("crawled_at")
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    views = to_float(event.get("views") or event.get("view_count"))
    likes = to_float(event.get("likes") or event.get("like_count"))
    comments = to_float(event.get("comments") or event.get("comment_count"))
    shares = to_float(event.get("shares") or event.get("share_count"))
    followers = to_float(event.get("followers") or event.get("follower_count") or event.get("subscribers") or event.get("subscriber_count"))
    return {
        "kol_id": str(event.get("kol_id") or event.get("channel_id") or event.get("creator_id") or event.get("channel") or "unknown"),
        "kol_name": str(event.get("kol_name") or event.get("channel_name") or event.get("channel_title") or event.get("creator_name") or "Unknown KOL"),
        "platform": str(event.get("platform") or event.get("source") or "youtube"),
        "video_id": str(event.get("video_id") or event.get("content_id") or ""),
        "timestamp": timestamp,
        "views": int(views),
        "likes": int(likes),
        "comments": int(comments),
        "shares": int(shares),
        "followers": int(followers),
        "engagement_rate": to_float(event.get("engagement_rate") or event.get("avg_engagement_rate")),
        "sentiment_score": to_float(event.get("sentiment_score") or event.get("avg_sentiment_score"), 0.5),
        "activity_score": to_float(event.get("activity_score") or event.get("avg_activity_score")),
        "anomaly_score": to_float(event.get("anomaly_score")),
        "trust_score": round(score, 2),
        "trust_label": event.get("trust_label") or event.get("risk_profile") or trust_label(score),
        "trust_source": event.get("trust_source") or event.get("label_source") or "processed_dataset",
        "is_suspicious": bool(to_float(event.get("is_suspicious") or event.get("suspicious_content_count"))),
    }


@lru_cache(maxsize=1)
def sample_scores() -> list[dict[str, Any]]:
    rows = []
    if SAMPLE_PATH.exists():
        for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(score_from_event(json.loads(line)))
    return rows


@lru_cache(maxsize=1)
def trust_score_records() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv_records(DATASET_TRUST_SCORES_PATH):
        score = to_float(row.get("trust_score"))
        rows.append(
            {
                "kol_id": str(row.get("creator_id") or "unknown"),
                "kol_name": row.get("creator_name") or row.get("creator_id") or "Unknown KOL",
                "platform": row.get("platform") or "unknown",
                "video_id": "",
                "timestamp": row.get("collected_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "views": int(to_float(row.get("total_views"))),
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "followers": int(to_float(row.get("follower_count"))),
                "engagement_rate": to_float(row.get("avg_engagement_rate")),
                "sentiment_score": to_float(row.get("avg_sentiment_score"), 0.5),
                "activity_score": to_float(row.get("avg_activity_score")),
                "anomaly_score": 0,
                "trust_score": round(score, 2),
                "trust_label": trust_label(score),
                "trust_source": row.get("label_source") or "processed_dataset",
                "is_suspicious": to_float(row.get("suspicious_content_count")) > 0,
            }
        )
    return rows


def local_scores(limit: int = 500) -> list[dict[str, Any]]:
    rows = trust_score_records() or sample_scores()
    if not rows:
        rows = [score_event(event) for event in dataset_events(limit=limit)]
    return rows[:limit]


def sample_events() -> list[dict[str, Any]]:
    rows = []
    if SAMPLE_PATH.exists():
        for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_records(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    max_rows = None if limit is None else max(0, limit)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append({key: (value if value != "" else None) for key, value in row.items()})
            if max_rows is not None and len(records) >= max_rows:
                break
    return records


def feature_to_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kol_id": row.get("creator_id"),
        "kol_name": row.get("creator_name"),
        "platform": row.get("platform"),
        "video_id": row.get("content_id"),
        "timestamp": row.get("publish_time") or row.get("collected_at"),
        "views": row.get("view_count"),
        "likes": row.get("like_count"),
        "comments": row.get("comment_count"),
        "shares": row.get("share_count"),
        "followers": row.get("follower_count"),
        "content_count": row.get("content_count"),
        "engagement_rate": row.get("engagement_rate"),
        "sentiment_score": row.get("sentiment_score"),
        "positive_comment_count": row.get("positive_comment_count"),
        "neutral_comment_count": row.get("neutral_comment_count"),
        "negative_comment_count": row.get("negative_comment_count"),
        "upload_frequency_7d": row.get("upload_frequency"),
        "follower_growth_rate": row.get("follower_growth_rate"),
        "activity_score": row.get("activity_score"),
        "is_suspicious": row.get("is_suspicious"),
        "text": row.get("content_title"),
    }


def dataset_events(limit: int = 500) -> list[dict[str, Any]]:
    features = read_csv_records(DATASET_FEATURES_PATH, limit=limit)
    return [feature_to_event(row) for row in features]


def kols_from_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_kol: dict[str, dict[str, Any]] = {}
    for row in rows:
        kol_id = str(row.get("kol_id") or "unknown")
        current = by_kol.get(kol_id)
        if current and str(row.get("timestamp")) <= str(current.get("timestamp")):
            continue
        score = float(row.get("trust_score") or 0)
        by_kol[kol_id] = {
            "kol_id": kol_id,
            "name": row.get("kol_name") or kol_id,
            "platform": row.get("platform") or "unknown",
            "followers": row.get("followers") or 0,
            "verified": score >= 70,
            "reputation_score": round(score / 100, 4),
            "risk_profile": risk_profile_from_score(score),
            "default_mode": "normal",
        }
    return sorted(by_kol.values(), key=lambda item: item.get("reputation_score", 0), reverse=True)


def kol_events(kol_id: str, limit: int = 500) -> list[dict[str, Any]]:
    events = [event for event in sample_events() if str(event.get("kol_id") or event.get("channel_id")) == kol_id]
    if not events:
        events = [event for event in dataset_events(limit=limit) if str(event.get("kol_id")) == kol_id]
    return events[-limit:]


def kol_metrics(kol_id: str) -> dict[str, Any]:
    rows = [row for row in sample_scores() if row["kol_id"] == kol_id]
    if not rows:
        rows = [score_event(event) for event in kol_events(kol_id, limit=200)]
    latest_row = rows[-1] if rows else {"kol_id": kol_id}
    event_count = len(kol_events(kol_id, limit=500))
    return {
        "live_id": f"realtime_{kol_id}",
        "kol_id": kol_id,
        "title": f"Realtime trust evaluation for {latest_row.get('kol_name', kol_id)}",
        "started_at": latest_row.get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timestamp": latest_row.get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "viewers": latest_row.get("views") or 0,
        "likes": latest_row.get("likes") or 0,
        "shares": latest_row.get("shares") or 0,
        "comments": latest_row.get("comments") or event_count,
        "purchases": 0,
        "engagement_rate": latest_row.get("engagement_rate") or 0,
        "sentiment_score": latest_row.get("sentiment_score") or 0.5,
        "bot_probability": latest_row.get("anomaly_score") or 0,
        "suspicious_spike": bool(latest_row.get("is_suspicious")),
        "trust_signal": latest_row.get("trust_label") or "medium_trust",
    }


def kol_feature_vector(kol_id: str) -> dict[str, Any]:
    metrics = kol_metrics(kol_id)
    return {
        "kol_id": kol_id,
        "kol_name": metrics["title"].replace("Realtime trust evaluation for ", ""),
        "platform": next((kol.get("platform") for kol in kols_from_scores(sample_scores()) if kol["kol_id"] == kol_id), "unknown"),
        "viewer_count": metrics["viewers"],
        "like_count": metrics["likes"],
        "share_count": metrics["shares"],
        "comment_count": metrics["comments"],
        "engagement_rate": metrics["engagement_rate"],
        "sentiment_score": metrics["sentiment_score"],
        "bot_probability": metrics["bot_probability"],
        "suspicious_event_ratio": metrics["bot_probability"],
        "activity_score": metrics.get("activity_score", 0),
        "is_suspicious": metrics["suspicious_spike"],
        "trust_label": metrics["trust_signal"],
        "timestamp": metrics["timestamp"],
    }


def query_cassandra(statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cluster = None
    try:
        cluster, session = cassandra_session()
        return [row_to_dict(row) for row in session.execute(statement, params)]
    except Exception:
        return []
    finally:
        if cluster:
            cluster.shutdown()


def cassandra_scores(limit: int = 500) -> list[dict[str, Any]]:
    return query_cassandra(f"{CASSANDRA_SCORE_SELECT} LIMIT %s", (limit,))


def latest_cassandra_scores(limit: int = 500) -> list[dict[str, Any]]:
    rows = cassandra_scores(limit=limit)
    by_kol: dict[str, dict[str, Any]] = {}
    for row in rows:
        kol_id = str(row.get("kol_id") or "unknown")
        current = by_kol.get(kol_id)
        row_ts = str(row.get("event_ts") or row.get("timestamp") or "")
        current_ts = str((current or {}).get("event_ts") or (current or {}).get("timestamp") or "")
        if not current or row_ts > current_ts:
            by_kol[kol_id] = row
    return sorted(by_kol.values(), key=lambda item: item.get("timestamp", ""), reverse=True)[:limit]


def cassandra_kol_scores(kol_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = query_cassandra(
        f"""
        {CASSANDRA_SCORE_SELECT}
        WHERE kol_id = %s
        LIMIT %s
        """,
        (kol_id, limit),
    )
    return sorted(rows, key=lambda item: item.get("timestamp", ""))


def score_row_to_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": f"spark_{row.get('kol_id')}_{row.get('event_ts') or row.get('timestamp')}",
        "kol_id": row.get("kol_id"),
        "kol_name": row.get("kol_name"),
        "platform": row.get("platform"),
        "event_type": "trust_score",
        "timestamp": row.get("event_ts") or row.get("timestamp"),
        "user_id": "spark_streaming",
        "value": row.get("trust_score"),
        "sentiment_score": row.get("sentiment_score"),
        "is_suspicious": bool(row.get("is_suspicious")),
        "views": row.get("views"),
        "likes": row.get("likes"),
        "comments": row.get("comments"),
        "shares": row.get("shares"),
        "followers": row.get("followers"),
        "engagement_rate": row.get("engagement_rate"),
        "anomaly_score": row.get("anomaly_score"),
        "trust_source": row.get("trust_source") or "spark_streaming",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    rows = query_cassandra("SELECT now() FROM system.local LIMIT 1")
    return {
        "status": "ok",
        "cassandra": "ok" if rows else "fallback_sample",
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/kol/latest")
def latest(limit: int = 50) -> list[dict[str, Any]]:
    rows = latest_cassandra_scores(limit=limit)
    if not rows:
        rows = local_scores(limit=limit)
    return sorted(rows, key=lambda item: item.get("trust_score", 0), reverse=True)[:limit]


@app.get("/kol/top")
def top(limit: int = 10) -> list[dict[str, Any]]:
    rows = latest_cassandra_scores(limit=500) or local_scores(limit=500)
    by_kol: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = by_kol.get(row["kol_id"])
        if not current or str(row.get("event_ts") or row.get("timestamp")) > str(current.get("event_ts") or current.get("timestamp")):
            by_kol[row["kol_id"]] = row
    return sorted(by_kol.values(), key=lambda item: item.get("trust_score", 0), reverse=True)[:limit]


@app.get("/api/kols")
def api_kols() -> list[dict[str, Any]]:
    rows = latest_cassandra_scores(limit=500) or local_scores(limit=500)
    return kols_from_scores(rows)


@app.get("/api/kols/{kol_id}/profile")
def api_kol_profile(kol_id: str) -> dict[str, Any]:
    for kol in api_kols():
        if kol["kol_id"] == kol_id:
            return kol
    return {
        "kol_id": kol_id,
        "name": kol_id,
        "platform": "unknown",
        "followers": 0,
        "verified": False,
        "reputation_score": 0,
        "risk_profile": "unknown",
        "default_mode": "normal",
    }


@app.get("/api/kols/{kol_id}/metrics")
def api_kol_metrics(kol_id: str) -> dict[str, Any]:
    rows = cassandra_kol_scores(kol_id, limit=1)
    if rows:
        row = rows[-1]
        return {
            "live_id": f"spark_{kol_id}",
            "kol_id": kol_id,
            "title": f"Realtime trust evaluation for {row.get('kol_name', kol_id)}",
            "started_at": row.get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "timestamp": row.get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "viewers": row.get("views") or 0,
            "likes": row.get("likes") or 0,
            "shares": row.get("shares") or 0,
            "comments": row.get("comments") or 0,
            "purchases": 0,
            "engagement_rate": row.get("engagement_rate") or 0,
            "sentiment_score": row.get("sentiment_score") or 0.5,
            "bot_probability": row.get("anomaly_score") or 0,
            "suspicious_spike": bool(row.get("is_suspicious")),
            "trust_signal": row.get("trust_label") or trust_label(to_float(row.get("trust_score"))),
        }
    return kol_metrics(kol_id)


@app.get("/api/kols/{kol_id}/events")
def api_kol_events(kol_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = cassandra_kol_scores(kol_id, limit=limit)
    if rows:
        return [score_row_to_event(row) for row in rows[-limit:]]
    return kol_events(kol_id, limit=limit)


@app.get("/api/kols/{kol_id}/export/features")
def api_kol_features(kol_id: str) -> dict[str, Any]:
    rows = cassandra_kol_scores(kol_id, limit=1)
    if rows:
        row = rows[-1]
        return {
            "kol_id": kol_id,
            "kol_name": row.get("kol_name"),
            "platform": row.get("platform"),
            "viewer_count": row.get("views") or 0,
            "like_count": row.get("likes") or 0,
            "share_count": row.get("shares") or 0,
            "comment_count": row.get("comments") or 0,
            "followers": row.get("followers") or 0,
            "engagement_rate": row.get("engagement_rate") or 0,
            "sentiment_score": row.get("sentiment_score") or 0.5,
            "bot_probability": row.get("anomaly_score") or 0,
            "suspicious_event_ratio": row.get("anomaly_score") or 0,
            "activity_score": row.get("activity_score") or 0,
            "is_suspicious": bool(row.get("is_suspicious")),
            "trust_score": row.get("trust_score") or 0,
            "trust_label": row.get("trust_label") or trust_label(to_float(row.get("trust_score"))),
            "timestamp": row.get("timestamp"),
            "trust_source": row.get("trust_source") or "spark_streaming",
        }
    return kol_feature_vector(kol_id)


@app.get("/api/kols/{kol_id}/export/bundle")
def api_kol_bundle(kol_id: str) -> dict[str, Any]:
    return {
        "profile": api_kol_profile(kol_id),
        "metrics": api_kol_metrics(kol_id),
        "recent_events": api_kol_events(kol_id, limit=100),
        "model_features": api_kol_features(kol_id),
    }


@app.get("/api/kols/{kol_id}/live")
def api_kol_live(kol_id: str) -> dict[str, Any]:
    return api_kol_bundle(kol_id)


@app.get("/api/kols/{kol_id}/export/kol_events.jsonl")
def api_kol_events_jsonl(kol_id: str, limit: int = 500) -> Response:
    lines = [json.dumps(event, ensure_ascii=False) for event in api_kol_events(kol_id, limit=limit)]
    body = "\n".join(lines)
    if body:
        body += "\n"
    return Response(content=body, media_type="application/x-ndjson")


@app.get("/kol/timeseries/{kol_id}")
def timeseries(kol_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = cassandra_kol_scores(kol_id, limit=limit)
    if not rows:
        rows = [row for row in sample_scores() if row["kol_id"] == kol_id]
    return rows[-limit:]


@app.get("/alerts")
def alerts(limit: int = 20) -> list[dict[str, Any]]:
    rows = [row for row in cassandra_scores(limit=500) if row.get("is_suspicious")]
    if not rows:
        rows = [row for row in sample_scores() if row["is_suspicious"]]
    return sorted(rows, key=lambda item: item.get("anomaly_score", 0), reverse=True)[:limit]


@app.get("/api/export/features")
def export_features(limit: int = 500) -> list[dict[str, Any]]:
    return read_csv_records(DATASET_FEATURES_PATH, limit=limit)


@app.get("/api/export/kol_events.jsonl")
def export_kol_events_jsonl(limit: int = 500) -> Response:
    lines = [json.dumps(event, ensure_ascii=False) for event in dataset_events(limit=limit)]
    body = "\n".join(lines)
    if body:
        body += "\n"
    return Response(content=body, media_type="application/x-ndjson")


@app.get("/api/export/bundle")
def export_bundle(limit: int = 500) -> dict[str, Any]:
    features = read_csv_records(DATASET_FEATURES_PATH, limit=limit)
    return {
        "manifest": read_json_file(DATASET_MANIFEST_PATH),
        "stats": read_json_file(DATASET_STATS_PATH),
        "features": features,
        "trust_scores": read_csv_records(DATASET_TRUST_SCORES_PATH, limit=limit),
        "kol_events": [feature_to_event(row) for row in features],
    }


@app.get("/api/kol/evaluate")
def evaluate_exported_kol_events(limit: int = 500) -> list[dict[str, Any]]:
    return [score_event(event) for event in dataset_events(limit=limit)]
