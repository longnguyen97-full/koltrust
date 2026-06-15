from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from labeling import add_rule_labels
from sentiment import aggregate_comment_sentiment
from utils import hash_text, safe_int


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DATASET_DIR = PROCESSED_DIR
BRONZE_DIR = PROCESSED_DIR / "bronze"
SILVER_DIR = PROCESSED_DIR / "silver"
GOLD_DIR = PROCESSED_DIR / "gold"
SERVING_DIR = PROCESSED_DIR / "serving"
SPLIT_DIR = SILVER_DIR / "unified" / "splits"
PROFILE_DIR = SILVER_DIR / "profiles"
YOUTUBE_DIR = BRONZE_DIR / "youtube"
TIKTOK_DIR = BRONZE_DIR / "tiktok"
UNIFIED_DIR = SILVER_DIR / "unified"
COMMENTS_DIR = SILVER_DIR / "comments"
COMMENT_SPLIT_DIR = COMMENTS_DIR / "splits"
FEATURES_DIR = GOLD_DIR / "features"

DATASET_NAME = "Vietnam KOL Trustworthiness Dataset"
HASHTAG_RE = re.compile(r"#([^\s#,.!?;:]+)", re.UNICODE)
MOJIBAKE_MARKERS = (
    "\u00c3\u00a0",
    "\u00c3\u00a1",
    "\u00c3\u00a8",
    "\u00c3\u00a9",
    "\u00c3\u00ac",
    "\u00c3\u00ad",
    "\u00c3\u00b2",
    "\u00c3\u00b3",
    "\u00c3\u00b9",
    "\u00c3\u00ba",
    "\u00c3\u00bd",
    "\u00c4\u0091",
    "\u00c4\u0083",
    "\u00c6\u00b0",
    "\u00e1\u00ba",
    "\u00e1\u00bb",
)

CATEGORY_KEYWORDS = {
    "gaming": ("game", "gaming", "esports", "valorant", "fc online", "gamer", "gametv"),
    "music": ("music", "song", "festival", "instrumental"),
    "food": ("food", "cooking", "recipe", "cuisine", "street food"),
    "travel": ("travel", "tourism", "tour", "destination", "trip"),
    "technology": ("tech", "technology", "ai", "software", "b2b", "electronics", "mikrotik"),
    "beauty": ("makeup", "beauty", "skincare", "fashion"),
    "education": ("education", "school", "learn", "learning", "study", "master"),
    "business": ("business", "factory", "kpmg", "noventiq", "company", "official"),
    "entertainment": ("talent", "tv", "media", "show", "entertainment"),
}

YOUTUBE_CHANNEL_COLUMNS = [
    "platform",
    "channel_id",
    "channel_name",
    "category",
    "subscriber_count",
    "video_count",
    "total_view_count",
    "collected_at",
]

YOUTUBE_VIDEO_COLUMNS = [
    "platform",
    "channel_id",
    "channel_name",
    "video_id",
    "title",
    "published_at",
    "view_count",
    "like_count",
    "comment_count",
    "subscriber_count",
    "channel_video_count",
    "collected_at",
]

TIKTOK_CREATOR_COLUMNS = [
    "platform",
    "creator_id",
    "creator_name",
    "username",
    "category",
    "follower_count",
    "following_count",
    "content_count",
    "collected_at",
]

TIKTOK_VIDEO_COLUMNS = [
    "platform",
    "content_id",
    "creator_id",
    "creator_name",
    "username",
    "content_title",
    "caption",
    "hashtags",
    "publish_time",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "collected_at",
]

UNIFIED_FEATURE_COLUMNS = [
    "platform",
    "creator_id",
    "creator_name",
    "content_id",
    "content_title",
    "publish_time",
    "follower_count",
    "content_count",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "engagement_rate",
    "likes_per_view",
    "comments_per_view",
    "shares_per_view",
    "sentiment_score",
    "sentiment_label",
    "positive_comment_count",
    "neutral_comment_count",
    "negative_comment_count",
    "upload_frequency",
    "follower_growth_rate",
    "activity_score",
    "trust_score",
    "is_suspicious",
    "label_source",
    "collected_at",
]

COMMENT_SENTIMENT_COLUMNS = [
    "platform",
    "creator_id",
    "content_id",
    "comment_id",
    "parent_comment_id",
    "is_reply",
    "comment_author_display_name",
    "comment_author_channel_id",
    "comment",
    "comment_text_is_hashed",
    "like_count",
    "sentiment",
    "sentiment_score",
    "sentiment_source",
    "comment_published_at",
    "collected_at",
]

ENGAGEMENT_FEATURE_COLUMNS = [
    "platform",
    "creator_id",
    "creator_name",
    "content_id",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "engagement_rate",
    "likes_per_view",
    "comments_per_view",
    "shares_per_view",
    "upload_frequency",
    "activity_score",
    "collected_at",
]

SUSPICIOUS_ENGAGEMENT_COLUMNS = [
    "platform",
    "creator_id",
    "creator_name",
    "content_id",
    "follower_count",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "engagement_rate",
    "likes_per_view",
    "comments_per_view",
    "shares_per_view",
    "is_suspicious",
    "label_source",
    "collected_at",
]

TRUST_SCORE_COLUMNS = [
    "rank",
    "platform",
    "creator_id",
    "creator_name",
    "follower_count",
    "content_count",
    "observed_content_count",
    "total_views",
    "avg_engagement_rate",
    "avg_sentiment_score",
    "avg_activity_score",
    "trust_score",
    "suspicious_content_count",
    "label_source",
    "collected_at",
]

SIMULATOR_PROFILE_COLUMNS = [
    "platform",
    "creator_id",
    "creator_name",
    "follower_count",
    "content_count",
    "observed_content_count",
    "total_views",
    "avg_engagement_rate",
    "avg_sentiment_score",
    "avg_activity_score",
    "collected_at",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def dedupe_by_id(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get(key)
        if row_id:
            latest[str(row_id)] = row
    return list(latest.values())


def count_duplicates(rows: list[dict[str, Any]], key: str) -> int:
    counts = Counter(str(row.get(key)) for row in rows if row.get(key))
    return sum(count - 1 for count in counts.values() if count > 1)


def comments_by_video(comment_rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in comment_rows:
        video_id = row.get("video_id")
        if video_id:
            grouped.setdefault(str(video_id), []).append(row)
    return grouped


def parse_timestamp(value: Any) -> datetime | None:
    normalized = normalize_timestamp(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(str(normalized).replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        raw = int(text)
        timestamp = raw / 1000 if raw > 10_000_000_000 else raw
        try:
            return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (OSError, OverflowError, ValueError):
            return text
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_upload_frequency(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[datetime]] = {}
    for row in rows:
        creator_key = (str(row.get("platform", "")), str(row.get("creator_id", "")))
        publish_time = parse_timestamp(row.get("publish_time"))
        if creator_key[1] and publish_time:
            grouped.setdefault(creator_key, []).append(publish_time)

    frequencies: dict[tuple[str, str], float] = {}
    for creator_key, timestamps in grouped.items():
        if len(timestamps) <= 1:
            frequencies[creator_key] = float(len(timestamps))
            continue
        span_days = max((max(timestamps) - min(timestamps)).days, 1)
        frequencies[creator_key] = round((len(timestamps) / span_days) * 7, 4)

    enriched = []
    for row in rows:
        creator_key = (str(row.get("platform", "")), str(row.get("creator_id", "")))
        enriched.append({**row, "upload_frequency": frequencies.get(creator_key, 0.0)})
    return enriched


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: clean_value(row.get(column, "")) for column in columns})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            clean_row = {key: clean_value(value) for key, value in row.items()}
            handle.write(json.dumps(clean_row, ensure_ascii=False, separators=(",", ":")) + "\n")


def repair_mojibake(value: str) -> str:
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def clean_value(value: Any) -> Any:
    if isinstance(value, str):
        return repair_mojibake(value)
    return value


def clean_text(*values: Any) -> str:
    return " ".join(str(clean_value(value)).lower() for value in values if value not in (None, ""))


def infer_category(row: dict[str, Any]) -> str:
    explicit = clean_value(str(row.get("seed_keyword") or row.get("category") or "")).strip()
    if explicit and explicit.lower() != "unknown":
        return explicit.lower()
    text = clean_text(
        row.get("channel_name"),
        row.get("creator_name"),
        row.get("username"),
        row.get("content_title"),
        row.get("caption"),
        row.get("hashtags"),
    )
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "unknown"


def format_hashtags(row: dict[str, Any]) -> str:
    raw_hashtags = row.get("hashtags")
    if isinstance(raw_hashtags, list):
        hashtags = [str(tag).lstrip("#") for tag in raw_hashtags]
    elif raw_hashtags:
        hashtags = [tag.strip().lstrip("#") for tag in str(raw_hashtags).split(",")]
    else:
        caption = str(row.get("caption") or row.get("content_title") or "")
        hashtags = [match.group(1) for match in HASHTAG_RE.finditer(caption)]
    return ",".join(dict.fromkeys(tag for tag in hashtags if tag))


def build_comment_sentiment_rows(raw_comments: list[dict[str, Any]], *, anonymize: bool) -> list[dict[str, Any]]:
    rows = []
    for row in raw_comments:
        sentiment_summary = aggregate_comment_sentiment([row])
        sentiment_score = float(row.get("comment_sentiment_score") or sentiment_summary["sentiment_score"])
        sentiment = str(row.get("comment_sentiment") or sentiment_summary["sentiment_label"])
        comment_text = str(row.get("comment_text", ""))
        author_name = str(row.get("comment_author_display_name", ""))
        author_channel_id = str(row.get("comment_author_channel_id", ""))
        rows.append(
            {
                "platform": row.get("platform", "youtube"),
                "creator_id": row.get("channel_id", ""),
                "content_id": row.get("video_id", ""),
                "comment_id": row.get("comment_id", ""),
                "parent_comment_id": row.get("parent_comment_id", ""),
                "is_reply": row.get("is_reply", False),
                "comment_author_display_name": hash_text(author_name) if anonymize and author_name else author_name,
                "comment_author_channel_id": hash_text(author_channel_id) if anonymize and author_channel_id else author_channel_id,
                "comment": hash_text(comment_text) if anonymize and comment_text else clean_value(comment_text),
                "comment_text_is_hashed": True if anonymize and comment_text else row.get("comment_text_is_hashed", False),
                "like_count": safe_int(row.get("comment_like_count")),
                "sentiment": sentiment,
                "sentiment_score": round(sentiment_score, 2),
                "sentiment_source": row.get("comment_sentiment_source") or sentiment_summary["sentiment_source"],
                "comment_published_at": row.get("comment_published_at", ""),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return rows


def build_youtube_channels(raw_channels: list[dict[str, Any]], raw_seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seed_category_by_channel = {
        str(row.get("channel_id")): str(row.get("seed_keyword", ""))
        for row in raw_seeds
        if row.get("channel_id") and row.get("seed_keyword")
    }
    clean_rows = []
    for row in raw_channels:
        channel_id = row.get("channel_id")
        if not channel_id:
            continue
        row_with_seed = {**row, "seed_keyword": seed_category_by_channel.get(str(channel_id), row.get("seed_keyword", ""))}
        clean_rows.append(
            {
                "platform": "youtube",
                "channel_id": channel_id,
                "channel_name": clean_value(row.get("channel_name", "")),
                "category": infer_category(row_with_seed),
                "subscriber_count": safe_int(row.get("subscriber_count")),
                "video_count": safe_int(row.get("video_count")),
                "total_view_count": safe_int(row.get("view_count")),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return dedupe_by_id(clean_rows, "channel_id")


def build_youtube_videos(raw_videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_rows = []
    for row in raw_videos:
        video_id = row.get("video_id")
        view_count = safe_int(row.get("view_count"))
        if not video_id or view_count <= 0:
            continue
        clean_rows.append(
            {
                "platform": "youtube",
                "channel_id": row.get("channel_id", ""),
                "channel_name": clean_value(row.get("channel_name", "")),
                "video_id": video_id,
                "title": clean_value(row.get("video_title", "")),
                "published_at": normalize_timestamp(row.get("published_at", "")),
                "view_count": view_count,
                "like_count": safe_int(row.get("like_count")),
                "comment_count": safe_int(row.get("comment_count")),
                "subscriber_count": safe_int(row.get("subscriber_count")),
                "channel_video_count": safe_int(row.get("video_count")),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return dedupe_by_id(clean_rows, "video_id")


def build_unified_features(youtube_videos: list[dict[str, Any]], youtube_comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    comments_lookup = comments_by_video(youtube_comments)
    for row in youtube_videos:
        sentiment_summary = aggregate_comment_sentiment(comments_lookup.get(str(row.get("video_id")), []))
        enriched = add_rule_labels(
            {
                "views": row["view_count"],
                "likes": row["like_count"],
                "comments": row["comment_count"],
                **sentiment_summary,
            }
        )
        rows.append(
            {
                "platform": "youtube",
                "creator_id": row.get("channel_id", ""),
                "creator_name": clean_value(row.get("channel_name", "")),
                "content_id": row.get("video_id", ""),
                "content_title": clean_value(row.get("title", "")),
                "publish_time": normalize_timestamp(row.get("published_at", "")),
                "follower_count": row.get("subscriber_count", 0),
                "content_count": row.get("channel_video_count", 0),
                "view_count": row.get("view_count", 0),
                "like_count": row.get("like_count", 0),
                "comment_count": row.get("comment_count", 0),
                "share_count": 0,
                "engagement_rate": enriched["engagement_rate"],
                "likes_per_view": enriched["likes_per_view"],
                "comments_per_view": enriched["comments_per_view"],
                "shares_per_view": 0,
                "sentiment_score": enriched["sentiment_score"],
                "sentiment_label": sentiment_summary["sentiment_label"],
                "positive_comment_count": sentiment_summary["positive_comment_count"],
                "neutral_comment_count": sentiment_summary["neutral_comment_count"],
                "negative_comment_count": sentiment_summary["negative_comment_count"],
                "upload_frequency": 0.0,
                "follower_growth_rate": "",
                "activity_score": enriched["activity_score"],
                "trust_score": enriched["trust_score"],
                "is_suspicious": enriched["is_suspicious"],
                "label_source": enriched["label_source"],
                "collected_at": row.get("collected_at", ""),
            }
        )
    return rows


def build_tiktok_creators(raw_creators: list[dict[str, Any]], raw_videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    video_text_by_creator: dict[str, list[str]] = {}
    for row in raw_videos:
        creator_id = str(row.get("creator_id") or "")
        if creator_id:
            video_text_by_creator.setdefault(creator_id, []).append(
                " ".join(str(row.get(key, "")) for key in ("content_title", "caption", "hashtags"))
            )
    clean_rows = []
    for row in raw_creators:
        creator_id = row.get("creator_id") or row.get("username")
        if not creator_id:
            continue
        category_row = {
            **row,
            "content_title": " ".join(video_text_by_creator.get(str(creator_id), [])),
        }
        clean_rows.append(
            {
                "platform": "tiktok",
                "creator_id": creator_id,
                "creator_name": clean_value(row.get("creator_name", "")),
                "username": row.get("username", ""),
                "category": infer_category(category_row),
                "follower_count": safe_int(row.get("follower_count")),
                "following_count": safe_int(row.get("following_count")),
                "content_count": safe_int(row.get("content_count")),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return dedupe_by_id(clean_rows, "creator_id")


def build_tiktok_videos(raw_videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_rows = []
    for row in raw_videos:
        content_id = row.get("content_id")
        view_count = safe_int(row.get("view_count"))
        if not content_id or view_count <= 0:
            continue
        clean_rows.append(
            {
                "platform": "tiktok",
                "content_id": content_id,
                "creator_id": row.get("creator_id", ""),
                "creator_name": clean_value(row.get("creator_name", "")),
                "username": row.get("username", ""),
                "content_title": clean_value(row.get("content_title", "")),
                "caption": clean_value(row.get("caption") or row.get("content_title", "")),
                "hashtags": format_hashtags(row),
                "publish_time": normalize_timestamp(row.get("publish_time", "")),
                "view_count": view_count,
                "like_count": safe_int(row.get("like_count")),
                "comment_count": safe_int(row.get("comment_count")),
                "share_count": safe_int(row.get("share_count")),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return dedupe_by_id(clean_rows, "content_id")


def tiktok_feature_rows(tiktok_creators: list[dict[str, Any]], tiktok_videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    creators_by_id = {row["creator_id"]: row for row in tiktok_creators}
    rows = []
    for row in tiktok_videos:
        creator = creators_by_id.get(row.get("creator_id"), {})
        views = safe_int(row.get("view_count"))
        likes = safe_int(row.get("like_count"))
        comments = safe_int(row.get("comment_count"))
        shares = safe_int(row.get("share_count"))
        denominator = max(views, 1)
        engagement_rate = round((likes + comments + shares) / denominator, 6)
        activity_score = round(min((comments + shares) / 1000 * 100, 100), 2)
        engagement_score = min(engagement_rate / 0.10, 1.0) * 100
        trust_score = round(max(0, min((0.5 * engagement_score) + (0.3 * 50) + (0.2 * activity_score), 100)), 2)
        is_suspicious = 1 if engagement_rate > 0.30 or (views > 100_000 and comments < 5) else 0
        rows.append(
            {
                "platform": "tiktok",
                "creator_id": row.get("creator_id", ""),
                "creator_name": clean_value(row.get("creator_name", "")),
                "content_id": row.get("content_id", ""),
                "content_title": clean_value(row.get("content_title", "")),
                "publish_time": normalize_timestamp(row.get("publish_time", "")),
                "follower_count": creator.get("follower_count", 0),
                "content_count": creator.get("content_count", 0),
                "view_count": views,
                "like_count": likes,
                "comment_count": comments,
                "share_count": shares,
                "engagement_rate": engagement_rate,
                "likes_per_view": round(likes / denominator, 6),
                "comments_per_view": round(comments / denominator, 6),
                "shares_per_view": round(shares / denominator, 6),
                "sentiment_score": 50.0,
                "sentiment_label": "neutral",
                "positive_comment_count": 0,
                "neutral_comment_count": 0,
                "negative_comment_count": 0,
                "upload_frequency": 0.0,
                "follower_growth_rate": "",
                "activity_score": activity_score,
                "trust_score": trust_score,
                "is_suspicious": is_suspicious,
                "label_source": "rule_generated_not_ground_truth",
                "collected_at": row.get("collected_at", ""),
            }
        )
    return rows


def build_engagement_features(unified_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{column: row.get(column, "") for column in ENGAGEMENT_FEATURE_COLUMNS} for row in unified_rows]


def build_suspicious_engagement(unified_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{column: row.get(column, "") for column in SUSPICIOUS_ENGAGEMENT_COLUMNS} for row in unified_rows]


def build_creator_trust_scores(unified_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in unified_rows:
        creator_id = str(row.get("creator_id", ""))
        if creator_id:
            grouped.setdefault((str(row.get("platform", "")), creator_id), []).append(row)

    score_rows = []
    for (platform, creator_id), rows in grouped.items():
        observed_count = len(rows)
        follower_count = max(safe_int(row.get("follower_count")) for row in rows)
        content_count = max(safe_int(row.get("content_count")) for row in rows)
        total_views = sum(safe_int(row.get("view_count")) for row in rows)
        avg_engagement = round(sum(float(row.get("engagement_rate") or 0.0) for row in rows) / observed_count, 6)
        avg_sentiment = round(sum(float(row.get("sentiment_score") or 50.0) for row in rows) / observed_count, 2)
        avg_activity = round(sum(float(row.get("activity_score") or 0.0) for row in rows) / observed_count, 2)
        trust_score = round(sum(float(row.get("trust_score") or 0.0) for row in rows) / observed_count, 2)
        suspicious_count = sum(safe_int(row.get("is_suspicious")) for row in rows)
        latest_collected_at = max(str(row.get("collected_at", "")) for row in rows)
        score_rows.append(
            {
                "rank": 0,
                "platform": platform,
                "creator_id": creator_id,
                "creator_name": rows[0].get("creator_name", ""),
                "follower_count": follower_count,
                "content_count": content_count,
                "observed_content_count": observed_count,
                "total_views": total_views,
                "avg_engagement_rate": avg_engagement,
                "avg_sentiment_score": avg_sentiment,
                "avg_activity_score": avg_activity,
                "trust_score": trust_score,
                "suspicious_content_count": suspicious_count,
                "label_source": "rule_generated_not_ground_truth",
                "collected_at": latest_collected_at,
            }
        )

    score_rows.sort(key=lambda row: (float(row["trust_score"]), safe_int(row["total_views"])), reverse=True)
    for rank, row in enumerate(score_rows, start=1):
        row["rank"] = rank
    return score_rows


def build_kafka_sample_events(unified_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for row in unified_rows:
        views = safe_int(row.get("view_count"))
        if views <= 0:
            continue
        events.append(
            {
                "event_id": str(uuid4()),
                "platform": row.get("platform", ""),
                "channel_id": row.get("creator_id", ""),
                "channel_name": row.get("creator_name", ""),
                "video_id": row.get("content_id", ""),
                "views": views,
                "likes": safe_int(row.get("like_count")),
                "comments": safe_int(row.get("comment_count")),
                "subscribers": safe_int(row.get("follower_count")),
                "engagement_rate": row.get("engagement_rate", 0),
                "sentiment_score": row.get("sentiment_score", 50.0),
                "trust_score": row.get("trust_score", 0),
                "collected_at": row.get("collected_at", ""),
            }
        )
    return events


def split_name_for_creator(platform: Any, creator_id: Any) -> str:
    key = f"{platform}:{creator_id}".encode("utf-8")
    bucket = int(hashlib.sha256(key).hexdigest()[:8], 16) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "eval"
    return "analysis_profile"


def split_unified_rows_by_creator(unified_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    splits = {"train": [], "eval": [], "analysis_profile": []}
    for row in unified_rows:
        split = split_name_for_creator(row.get("platform", ""), row.get("creator_id", ""))
        splits[split].append(row)
    return splits


def split_rows_by_creator(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    splits = {"train": [], "eval": [], "analysis_profile": []}
    for row in rows:
        split = split_name_for_creator(row.get("platform", ""), row.get("creator_id", ""))
        splits[split].append(row)
    return splits


def build_simulator_profiles(unified_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in unified_rows:
        creator_id = str(row.get("creator_id", ""))
        if creator_id:
            grouped.setdefault((str(row.get("platform", "")), creator_id), []).append(row)

    profiles = []
    for (platform, creator_id), rows in grouped.items():
        observed_count = len(rows)
        profiles.append(
            {
                "platform": platform,
                "creator_id": creator_id,
                "creator_name": rows[0].get("creator_name", ""),
                "follower_count": max(safe_int(row.get("follower_count")) for row in rows),
                "content_count": max(safe_int(row.get("content_count")) for row in rows),
                "observed_content_count": observed_count,
                "total_views": sum(safe_int(row.get("view_count")) for row in rows),
                "avg_engagement_rate": round(
                    sum(float(row.get("engagement_rate") or 0.0) for row in rows) / observed_count,
                    6,
                ),
                "avg_sentiment_score": round(
                    sum(float(row.get("sentiment_score") or 50.0) for row in rows) / observed_count,
                    2,
                ),
                "avg_activity_score": round(
                    sum(float(row.get("activity_score") or 0.0) for row in rows) / observed_count,
                    2,
                ),
                "collected_at": max(str(row.get("collected_at", "")) for row in rows),
            }
        )
    profiles.sort(key=lambda row: (safe_int(row["total_views"]), safe_int(row["follower_count"])), reverse=True)
    return profiles


def count_possible_mojibake(rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if any(marker in str(value) for value in row.values() for marker in MOJIBAKE_MARKERS):
            count += 1
    return count


def write_data_dictionary(path: Path) -> None:
    path.write_text(
        """# Từ Điển Dữ Liệu

Dataset: Vietnam KOL Trustworthiness Dataset

## bronze/youtube/vietnam_youtube_channels.csv

- `platform`: Nền tảng nguồn, hiện tại là `youtube`.
- `channel_id`: YouTube channel ID.
- `channel_name`: Tên channel công khai.
- `category`: Danh mục tìm kiếm, seed keyword hoặc category heuristic dựa trên keyword.
- `subscriber_count`: Số subscriber công khai từ YouTube Data API nếu có.
- `video_count`: Tổng số video công khai của channel.
- `total_view_count`: Tổng view công khai của channel.
- `collected_at`: Thời điểm thu thập theo UTC.

## bronze/youtube/vietnam_youtube_videos.csv

- `video_id`: YouTube video ID.
- `title`: Tiêu đề video công khai.
- `published_at`: Thời điểm publish video theo UTC ISO-8601.
- `view_count`: Số view công khai của video. Các dòng thiếu hoặc bằng 0 view bị loại.
- `like_count`: Số like công khai nếu có.
- `comment_count`: Số comment công khai nếu có.
- `subscriber_count`: Số subscriber của channel tại thời điểm thu thập.
- `channel_video_count`: Tổng số video của channel tại thời điểm thu thập.

## bronze/tiktok/*.csv

File TikTok được sinh khi đã crawl raw data TikTok. Không xem bảng TikTok rỗng là dữ liệu đã crawl.

## bronze/tiktok/vietnam_tiktok_videos.csv

- `content_title` / `caption`: Caption TikTok công khai nếu có.
- `hashtags`: Hashtag phân tách bằng dấu phẩy, parse từ metadata hoặc caption công khai.
- `publish_time`: Thời điểm tạo video, chuẩn hóa về UTC ISO-8601.
- `view_count`, `like_count`, `comment_count`, `share_count`: Thống kê công khai của video.

## silver/unified/vietnam_influencer_features.csv

- `platform`: Nền tảng nguồn.
- `creator_id`: Creator ID theo từng nền tảng.
- `creator_name`: Tên creator/channel công khai.
- `content_id`: Content ID theo từng nền tảng.
- `content_title`: Tiêu đề content công khai nếu có.
- `publish_time`: Thời điểm publish content, chuẩn hóa về UTC ISO-8601.
- `follower_count`: Subscriber hoặc follower tùy nền tảng.
- `content_count`: Tổng số content/video nếu có.
- `view_count`, `like_count`, `comment_count`, `share_count`: Thống kê công khai của content.
- `engagement_rate`: `(like_count + comment_count + share_count) / max(view_count, 1)`.
- `likes_per_view`: `like_count / max(view_count, 1)`.
- `comments_per_view`: `comment_count / max(view_count, 1)`.
- `shares_per_view`: `share_count / max(view_count, 1)`.
- `sentiment_score`: Điểm sentiment trung bình theo rule, từ 0 đến 100 cho YouTube comments; mặc định neutral khi không có comment.
- `sentiment_label`: Nhãn sentiment tổng hợp.
- `positive_comment_count`, `neutral_comment_count`, `negative_comment_count`: Số lượng comment sentiment theo rule.
- `upload_frequency`: Tần suất upload/tuần quan sát được trong sample đã thu thập.
- `follower_growth_rate`: Dành cho dữ liệu longitudinal trong tương lai.
- `activity_score`, `trust_score`, `is_suspicious`: Nhãn sinh bằng rule, không phải ground truth.
- `label_source`: Nguồn sinh nhãn.

## silver/comments/vietnam_comments_sentiment.csv

- `content_id`: YouTube video ID.
- `parent_comment_id`: ID của top-level comment nếu dòng là reply.
- `is_reply`: Dòng này có phải reply comment hay không.
- `comment_author_display_name`: Tên công khai của tác giả comment, hoặc SHA-256 hash trong release build.
- `comment_author_channel_id`: Channel ID công khai của tác giả comment, hoặc SHA-256 hash trong release build.
- `comment`: Nội dung comment công khai, hoặc SHA-256 hash trong release build.
- `like_count`: Số like công khai của comment.
- `sentiment`: Nhãn theo rule: positive, neutral hoặc negative.
- `sentiment_score`: Điểm theo rule từ 0 đến 100.
- `sentiment_source`: Nguồn sinh sentiment.

## gold/features/engagement_features.csv

Metric engagement và activity ở cấp content cho analytics và ML baseline.

## gold/features/suspicious_engagement.csv

Nhãn suspicious engagement ở cấp content được sinh bằng rule. Đây không phải ground truth.

## gold/features/trust_scores.csv

Leaderboard trust score ở cấp creator, tổng hợp từ các dòng content đã quan sát. Ranking là baseline sinh bằng rule, không phải ground truth.

## Quy Tắc Chất Lượng

- Loại video/content thiếu hoặc bằng 0 `view_count`.
- Deduplicate YouTube video theo `video_id`.
- Deduplicate YouTube channel theo `channel_id`.
- Chuẩn hóa publish timestamp về UTC ISO-8601 khi có thể.
- Kafka replay sample được sinh lại từ unified rows đã clean và loại fixture/zero-view rows.
- Không chứa dữ liệu riêng tư, credential hoặc dữ liệu thu thập bằng bypass.
""",
        encoding="utf-8",
    )


def write_readme(path: Path, stats: dict[str, Any]) -> None:
    path.write_text(
        f"""# {DATASET_NAME}

Dataset công khai phục vụ nghiên cứu và demo đánh giá độ tin cậy của creator/KOL.

## Phạm Vi Hiện Tại

- YouTube: thu thập bằng YouTube Data API v3.
- TikTok: được đưa vào khi có `data/raw/tiktok_creators.jsonl` và `data/raw/tiktok_videos.jsonl`; nếu chưa crawl TikTok thì các bảng TikTok chỉ có header.

## Cấu Trúc

```text
data/
`-- processed/
    |-- bronze/
    |   |-- youtube/
    |   |   |-- vietnam_youtube_channels.csv
    |   |   `-- vietnam_youtube_videos.csv
    |   `-- tiktok/
    |       |-- vietnam_tiktok_creators.csv
    |       `-- vietnam_tiktok_videos.csv
    |-- silver/
    |   |-- comments/
    |   |   |-- splits/
    |   |   |   |-- train_comments.csv
    |   |   |   |-- eval_comments.csv
    |   |   |   `-- analysis_profile_comments.csv
    |   |   `-- vietnam_comments_sentiment.csv
    |   `-- unified/
    |       |-- splits/
    |       |   |-- train_features.csv
    |       |   |-- eval_features.csv
    |       |   `-- analysis_profile_features.csv
    |       |-- vietnam_influencer_dataset.csv
    |       `-- vietnam_influencer_features.csv
    |   `-- profiles/
    |       `-- simulator_profiles.csv
    |-- gold/
    |   `-- features/
    |       |-- engagement_features.csv
    |       |-- suspicious_engagement.csv
    |       `-- trust_scores.csv
    |-- serving/
    |   `-- kol_events.jsonl
    |-- README.md
    |-- data_dictionary.md
    |-- dataset_stats.json
    `-- manifest.json
```

## File Được Sinh Ra

- `bronze/youtube/vietnam_youtube_channels.csv`
- `bronze/youtube/vietnam_youtube_videos.csv`
- `bronze/tiktok/vietnam_tiktok_creators.csv`
- `bronze/tiktok/vietnam_tiktok_videos.csv`
- `silver/comments/vietnam_comments_sentiment.csv`
- `silver/comments/splits/train_comments.csv`
- `silver/comments/splits/eval_comments.csv`
- `silver/comments/splits/analysis_profile_comments.csv`
- `silver/unified/vietnam_influencer_features.csv`
- `silver/unified/vietnam_influencer_dataset.csv`
- `silver/unified/splits/train_features.csv`
- `silver/unified/splits/eval_features.csv`
- `silver/unified/splits/analysis_profile_features.csv`
- `silver/profiles/simulator_profiles.csv`
- `gold/features/engagement_features.csv`
- `gold/features/suspicious_engagement.csv`
- `gold/features/trust_scores.csv`
- `serving/kol_events.jsonl`

## Tóm Tắt Lần Build

- Built at: `{stats['built_at']}`
- YouTube channels: `{stats['youtube']['channels']}`
- YouTube videos: `{stats['youtube']['videos']}`
- TikTok creators: `{stats['tiktok']['creators']}`
- TikTok videos: `{stats['tiktok']['videos']}`
- Unified feature rows: `{stats['unified']['feature_rows']}`
- Train split rows: `{stats['splits']['train_rows']}`
- Eval split rows: `{stats['splits']['eval_rows']}`
- Analysis/profile split rows: `{stats['splits']['analysis_profile_rows']}`
- Train comment split rows: `{stats['splits']['train_comment_rows']}`
- Eval comment split rows: `{stats['splits']['eval_comment_rows']}`
- Analysis/profile comment split rows: `{stats['splits']['analysis_profile_comment_rows']}`
- Simulator profile creators: `{stats['splits']['simulator_profile_creators']}`
- Comment sentiment rows: `{stats['comments']['sentiment_rows']}`
- Comments anonymized: `{stats['comments']['anonymized']}`
- Kafka replay sample rows: `{stats['sample']['kafka_events']}`
- Engagement feature rows: `{stats['features']['engagement_rows']}`
- Suspicious engagement rows: `{stats['features']['suspicious_rows']}`
- Creator trust score rows: `{stats['features']['trust_score_rows']}`
- Removed YouTube videos with missing or zero views: `{stats['quality']['removed_zero_view_youtube_videos']}`
- Duplicate YouTube channels removed: `{stats['quality']['duplicate_youtube_channels_removed']}`
- Duplicate YouTube videos removed: `{stats['quality']['duplicate_youtube_videos_removed']}`

## Lưu Ý Về Nhãn

`is_suspicious`, `trust_score` và `activity_score` được sinh từ rule đơn giản để demo và làm baseline ML. Đây không phải ground truth label.

## Split Chống Leakage

Các split `train`, `eval` và `analysis_profile` được tách theo hash của `(platform, creator_id)`, không tách random từng row. Vì vậy cùng một creator không xuất hiện đồng thời ở train và eval/profile seed.
Simulator chỉ dùng `silver/profiles/simulator_profiles.csv` để lấy identity/profile cơ bản, không dùng `trust_score` hoặc nhãn rule làm realtime input.

## Đạo Đức Dữ Liệu

Dataset chỉ dùng dữ liệu công khai. Dataset không chứa credential, dữ liệu riêng tư, số điện thoại, email hoặc dữ liệu thu thập bằng cách bypass CAPTCHA/login.
Release build mặc định hash nội dung comment và định danh công khai của tác giả comment.
""",
        encoding="utf-8",
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_dataset(*, anonymize_comments: bool = True) -> dict[str, Any]:
    raw_channels = read_jsonl(RAW_DIR / "youtube_channels.jsonl")
    raw_channel_seeds = read_jsonl(RAW_DIR / "youtube_channel_seeds.jsonl")
    raw_videos = read_jsonl(RAW_DIR / "youtube_videos.jsonl")
    raw_comments = read_jsonl(RAW_DIR / "youtube_comments.jsonl")
    raw_tiktok_creators = read_jsonl(RAW_DIR / "tiktok_creators.jsonl")
    raw_tiktok_videos = read_jsonl(RAW_DIR / "tiktok_videos.jsonl")

    youtube_channels = build_youtube_channels(raw_channels, raw_channel_seeds)
    youtube_videos = build_youtube_videos(raw_videos)
    tiktok_creators = build_tiktok_creators(raw_tiktok_creators, raw_tiktok_videos)
    tiktok_videos = build_tiktok_videos(raw_tiktok_videos)
    comment_sentiment_rows = build_comment_sentiment_rows(raw_comments, anonymize=anonymize_comments)
    unified_features = add_upload_frequency(
        build_unified_features(youtube_videos, raw_comments) + tiktok_feature_rows(tiktok_creators, tiktok_videos)
    )
    engagement_features = build_engagement_features(unified_features)
    suspicious_engagement = build_suspicious_engagement(unified_features)
    trust_scores = build_creator_trust_scores(unified_features)
    kafka_sample_events = build_kafka_sample_events(unified_features)
    unified_splits = split_unified_rows_by_creator(unified_features)
    comment_splits = split_rows_by_creator(comment_sentiment_rows)
    simulator_profiles = build_simulator_profiles(unified_splits["analysis_profile"])

    write_csv(YOUTUBE_DIR / "vietnam_youtube_channels.csv", youtube_channels, YOUTUBE_CHANNEL_COLUMNS)
    write_csv(YOUTUBE_DIR / "vietnam_youtube_videos.csv", youtube_videos, YOUTUBE_VIDEO_COLUMNS)
    write_csv(TIKTOK_DIR / "vietnam_tiktok_creators.csv", tiktok_creators, TIKTOK_CREATOR_COLUMNS)
    write_csv(TIKTOK_DIR / "vietnam_tiktok_videos.csv", tiktok_videos, TIKTOK_VIDEO_COLUMNS)
    write_csv(COMMENTS_DIR / "vietnam_comments_sentiment.csv", comment_sentiment_rows, COMMENT_SENTIMENT_COLUMNS)
    write_csv(COMMENT_SPLIT_DIR / "train_comments.csv", comment_splits["train"], COMMENT_SENTIMENT_COLUMNS)
    write_csv(COMMENT_SPLIT_DIR / "eval_comments.csv", comment_splits["eval"], COMMENT_SENTIMENT_COLUMNS)
    write_csv(COMMENT_SPLIT_DIR / "analysis_profile_comments.csv", comment_splits["analysis_profile"], COMMENT_SENTIMENT_COLUMNS)
    write_csv(FEATURES_DIR / "engagement_features.csv", engagement_features, ENGAGEMENT_FEATURE_COLUMNS)
    write_csv(FEATURES_DIR / "suspicious_engagement.csv", suspicious_engagement, SUSPICIOUS_ENGAGEMENT_COLUMNS)
    write_csv(FEATURES_DIR / "trust_scores.csv", trust_scores, TRUST_SCORE_COLUMNS)
    write_csv(UNIFIED_DIR / "vietnam_influencer_features.csv", unified_features, UNIFIED_FEATURE_COLUMNS)
    write_csv(UNIFIED_DIR / "vietnam_influencer_dataset.csv", unified_features, UNIFIED_FEATURE_COLUMNS)
    write_csv(SPLIT_DIR / "train_features.csv", unified_splits["train"], UNIFIED_FEATURE_COLUMNS)
    write_csv(SPLIT_DIR / "eval_features.csv", unified_splits["eval"], UNIFIED_FEATURE_COLUMNS)
    write_csv(SPLIT_DIR / "analysis_profile_features.csv", unified_splits["analysis_profile"], UNIFIED_FEATURE_COLUMNS)
    write_csv(PROFILE_DIR / "simulator_profiles.csv", simulator_profiles, SIMULATOR_PROFILE_COLUMNS)
    write_jsonl(SERVING_DIR / "kol_events.jsonl", kafka_sample_events)

    raw_video_ids = {str(row.get("video_id")) for row in raw_videos if row.get("video_id")}
    clean_video_ids = {str(row.get("video_id")) for row in youtube_videos if row.get("video_id")}
    raw_tiktok_video_ids = {str(row.get("content_id")) for row in raw_tiktok_videos if row.get("content_id")}
    clean_tiktok_video_ids = {str(row.get("content_id")) for row in tiktok_videos if row.get("content_id")}
    stats = {
        "dataset_name": DATASET_NAME,
        "built_at": utc_now_iso(),
        "source": {
            "youtube": "YouTube Data API v3 public data",
            "tiktok": "TikTokApi public data" if tiktok_creators or tiktok_videos else "not_collected_in_this_build",
        },
        "raw": {
            "youtube_channels": len(raw_channels),
            "youtube_videos": len(raw_videos),
            "youtube_comments": len(raw_comments),
            "tiktok_creators": len(raw_tiktok_creators),
            "tiktok_videos": len(raw_tiktok_videos),
        },
        "youtube": {
            "channels": len(youtube_channels),
            "videos": len(youtube_videos),
        },
        "tiktok": {
            "creators": len(tiktok_creators),
            "videos": len(tiktok_videos),
        },
        "unified": {
            "feature_rows": len(unified_features),
            "platforms": ["youtube"] + (["tiktok"] if tiktok_videos else []),
        },
        "splits": {
            "strategy": "creator_id_hash_60_20_20",
            "train_rows": len(unified_splits["train"]),
            "eval_rows": len(unified_splits["eval"]),
            "analysis_profile_rows": len(unified_splits["analysis_profile"]),
            "train_comment_rows": len(comment_splits["train"]),
            "eval_comment_rows": len(comment_splits["eval"]),
            "analysis_profile_comment_rows": len(comment_splits["analysis_profile"]),
            "simulator_profile_creators": len(simulator_profiles),
        },
        "comments": {
            "sentiment_rows": len(comment_sentiment_rows),
            "anonymized": anonymize_comments,
        },
        "sample": {
            "kafka_events": len(kafka_sample_events),
            "fixture_rows": 0,
            "zero_view_rows": sum(1 for row in kafka_sample_events if safe_int(row.get("views")) <= 0),
        },
        "features": {
            "engagement_rows": len(engagement_features),
            "suspicious_rows": len(suspicious_engagement),
            "trust_score_rows": len(trust_scores),
        },
        "quality": {
            "removed_zero_view_youtube_videos": len(raw_video_ids - clean_video_ids),
            "removed_zero_view_tiktok_videos": len(raw_tiktok_video_ids - clean_tiktok_video_ids),
            "duplicate_youtube_channels_removed": count_duplicates(raw_channels, "channel_id"),
            "duplicate_youtube_videos_removed": count_duplicates(raw_videos, "video_id"),
            "duplicate_tiktok_creators_removed": count_duplicates(raw_tiktok_creators, "creator_id"),
            "duplicate_tiktok_videos_removed": count_duplicates(raw_tiktok_videos, "content_id"),
            "possible_mojibake_output_rows": sum(
                count_possible_mojibake(rows)
                for rows in (
                    youtube_channels,
                    youtube_videos,
                    tiktok_creators,
                    tiktok_videos,
                    unified_features,
                    comment_sentiment_rows,
                    kafka_sample_events,
                )
            ),
        },
        "label_notice": "Rule-generated labels are not ground truth.",
    }
    manifest = {
        "dataset_name": DATASET_NAME,
        "files": [
            "bronze/youtube/vietnam_youtube_channels.csv",
            "bronze/youtube/vietnam_youtube_videos.csv",
            "bronze/tiktok/vietnam_tiktok_creators.csv",
            "bronze/tiktok/vietnam_tiktok_videos.csv",
            "silver/comments/vietnam_comments_sentiment.csv",
            "silver/comments/splits/train_comments.csv",
            "silver/comments/splits/eval_comments.csv",
            "silver/comments/splits/analysis_profile_comments.csv",
            "silver/unified/vietnam_influencer_features.csv",
            "silver/unified/vietnam_influencer_dataset.csv",
            "silver/unified/splits/train_features.csv",
            "silver/unified/splits/eval_features.csv",
            "silver/unified/splits/analysis_profile_features.csv",
            "silver/profiles/simulator_profiles.csv",
            "gold/features/engagement_features.csv",
            "gold/features/suspicious_engagement.csv",
            "gold/features/trust_scores.csv",
            "serving/kol_events.jsonl",
            "README.md",
            "data_dictionary.md",
            "dataset_stats.json",
        ],
    }
    write_json(DATASET_DIR / "dataset_stats.json", stats)
    write_json(DATASET_DIR / "manifest.json", manifest)
    write_data_dictionary(DATASET_DIR / "data_dictionary.md")
    write_readme(DATASET_DIR / "README.md", stats)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Vietnam KOL Trustworthiness Dataset.")
    parser.add_argument(
        "--include-comment-text",
        action="store_true",
        help="Keep raw public comment text in data/processed/silver/comments. Default hashes comments and author identifiers.",
    )
    args = parser.parse_args()
    stats = build_dataset(anonymize_comments=not args.include_comment_text)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
