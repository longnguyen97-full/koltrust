from __future__ import annotations

from typing import Any
from labeling import add_rule_labels
from sentiment import analyze_comment_sentiment
from utils import safe_int


def _stats(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("statistics", {}) or {}


def _snippet(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("snippet", {}) or {}


def normalize_channel(item: dict[str, Any], collected_at: str) -> dict[str, Any]:
    stats = _stats(item)
    snippet = _snippet(item)
    return {
        "platform": "youtube",
        "channel_id": item.get("id"),
        "channel_name": snippet.get("title"),
        "subscriber_count": safe_int(stats.get("subscriberCount")),
        "video_count": safe_int(stats.get("videoCount")),
        "view_count": safe_int(stats.get("viewCount")),
        "collected_at": collected_at,
    }


def normalize_video(
    item: dict[str, Any],
    *,
    channel: dict[str, Any] | None,
    collected_at: str,
) -> dict[str, Any]:
    stats = _stats(item)
    snippet = _snippet(item)
    channel = channel or {}
    record = {
        "platform": "youtube",
        "channel_id": snippet.get("channelId") or channel.get("channel_id"),
        "channel_name": snippet.get("channelTitle") or channel.get("channel_name"),
        "video_id": item.get("id"),
        "video_title": snippet.get("title"),
        "published_at": snippet.get("publishedAt"),
        "view_count": safe_int(stats.get("viewCount")),
        "like_count": safe_int(stats.get("likeCount")),
        "comment_count": safe_int(stats.get("commentCount")),
        "subscriber_count": safe_int(channel.get("subscriber_count")),
        "video_count": safe_int(channel.get("video_count")),
        "collected_at": collected_at,
    }
    return add_rule_labels(record)


def normalize_comment(
    item: dict[str, Any],
    *,
    video_id: str,
    channel_id: str | None,
    collected_at: str,
    anonymize: bool = False,
) -> dict[str, Any]:
    from utils import hash_text

    top_comment = item.get("snippet", {}).get("topLevelComment", {})
    comment_snippet = top_comment.get("snippet", {}) or {}
    comment_text = comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay") or ""
    sentiment = analyze_comment_sentiment(comment_text)
    author_channel = comment_snippet.get("authorChannelId") or {}
    record = {
        "platform": "youtube",
        "channel_id": channel_id,
        "video_id": video_id,
        "comment_id": top_comment.get("id"),
        "parent_comment_id": "",
        "is_reply": False,
        "comment_author_display_name": comment_snippet.get("authorDisplayName", ""),
        "comment_author_channel_id": author_channel.get("value") if isinstance(author_channel, dict) else author_channel,
        "comment_text": hash_text(comment_text) if anonymize else comment_text,
        "comment_text_is_hashed": anonymize,
        "comment_like_count": safe_int(comment_snippet.get("likeCount")),
        **sentiment,
        "comment_published_at": comment_snippet.get("publishedAt"),
        "collected_at": collected_at,
    }
    return record


def normalize_comment_thread(
    item: dict[str, Any],
    *,
    video_id: str,
    channel_id: str | None,
    collected_at: str,
    anonymize: bool = False,
) -> list[dict[str, Any]]:
    records = [
        normalize_comment(
            item,
            video_id=video_id,
            channel_id=channel_id,
            collected_at=collected_at,
            anonymize=anonymize,
        )
    ]
    parent_comment_id = records[0].get("comment_id", "")
    for reply in item.get("replies", {}).get("comments", []) or []:
        snippet = reply.get("snippet", {}) or {}
        comment_text = snippet.get("textOriginal") or snippet.get("textDisplay") or ""
        sentiment = analyze_comment_sentiment(comment_text)
        author_channel = snippet.get("authorChannelId") or {}
        records.append(
            {
                "platform": "youtube",
                "channel_id": channel_id,
                "video_id": video_id,
                "comment_id": reply.get("id"),
                "parent_comment_id": parent_comment_id,
                "is_reply": True,
                "comment_author_display_name": snippet.get("authorDisplayName", ""),
                "comment_author_channel_id": author_channel.get("value") if isinstance(author_channel, dict) else author_channel,
                "comment_text": hash_text(comment_text) if anonymize else comment_text,
                "comment_text_is_hashed": anonymize,
                "comment_like_count": safe_int(snippet.get("likeCount")),
                **sentiment,
                "comment_published_at": snippet.get("publishedAt"),
                "collected_at": collected_at,
            }
        )
    return records
