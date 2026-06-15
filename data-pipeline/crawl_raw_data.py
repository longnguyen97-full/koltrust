from __future__ import annotations

import argparse
from pathlib import Path

from normalizer import normalize_channel, normalize_comment_thread, normalize_video
from labeling import add_rule_labels
from sentiment import aggregate_comment_sentiment
from utils import (
    QuotaExceededError,
    RateLimitExceededError,
    append_jsonl,
    ensure_output_dirs,
    get_youtube_api_key,
    log_event,
    read_nonempty_lines,
    setup_logging,
    utc_now_iso,
)
from youtube_client import YouTubeClient


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl public YouTube KOL data into JSONL files.")
    parser.add_argument("--video-id", action="append", default=[], help="YouTube video id. Can be repeated.")
    parser.add_argument("--channel-id", action="append", default=[], help="YouTube channel id. Can be repeated.")
    parser.add_argument("--channel-list", type=Path, help="Text file with one YouTube channel id per line.")
    parser.add_argument("--max-videos", type=int, default=10, help="Maximum recent videos per channel.")
    parser.add_argument("--max-comments", type=int, default=50, help="Maximum top-level comments per video.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API requests.")
    parser.add_argument("--anonymize-comments", action="store_true", help="Store SHA-256 hashes instead of comment text.")
    return parser


def load_targets(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    video_ids = list(dict.fromkeys(args.video_id))
    channel_ids = list(dict.fromkeys(args.channel_id))
    if args.channel_list:
        channel_ids.extend(read_nonempty_lines(args.channel_list))
        channel_ids = list(dict.fromkeys(channel_ids))
    return video_ids, channel_ids


def collect_video(
    client: YouTubeClient,
    video_item: dict,
    *,
    collected_at: str,
    max_comments: int,
    anonymize_comments: bool,
) -> tuple[dict | None, list[dict]]:
    snippet = video_item.get("snippet", {}) or {}
    channel_id = snippet.get("channelId")
    channel_record = None
    if channel_id:
        channel_item = client.get_channel(channel_id)
        if channel_item:
            channel_record = normalize_channel(channel_item, collected_at)

    video_record = normalize_video(video_item, channel=channel_record, collected_at=collected_at)
    comments: list[dict] = []
    if max_comments > 0 and video_record.get("video_id"):
        try:
            comment_items = client.list_comments(video_record["video_id"], max_comments=max_comments)
            comments = [
                comment
                for item in comment_items
                for comment in normalize_comment_thread(
                    item,
                    video_id=video_record["video_id"],
                    channel_id=video_record.get("channel_id"),
                    collected_at=collected_at,
                    anonymize=anonymize_comments,
                )
            ]
        except Exception as exc:
            log_event(
                "error",
                "youtube",
                "comments_failed",
                video_id=video_record.get("video_id"),
                error=str(exc),
            )
    sentiment_summary = aggregate_comment_sentiment(comments)
    video_record = add_rule_labels({**video_record, **sentiment_summary})
    return channel_record, [video_record, *comments]


def write_outputs(channels: list[dict], videos: list[dict], comments: list[dict]) -> None:
    if channels:
        append_jsonl(RAW_DIR / "youtube_channels.jsonl", channels)
    if videos:
        append_jsonl(RAW_DIR / "youtube_videos.jsonl", videos)
    if comments:
        append_jsonl(RAW_DIR / "youtube_comments.jsonl", comments)


def main() -> int:
    args = build_parser().parse_args()
    ensure_output_dirs(ROOT)
    setup_logging(ROOT / "logs" / "crawler.log")

    api_key = get_youtube_api_key(ROOT)

    video_ids, channel_ids = load_targets(args)
    if not video_ids and not channel_ids:
        raise RuntimeError("Provide --video-id, --channel-id, or --channel-list")

    client = YouTubeClient(api_key, sleep_seconds=args.sleep)
    collected_at = utc_now_iso()
    channels_by_id: dict[str, dict] = {}
    videos: list[dict] = []
    comments: list[dict] = []

    try:
        for video_id in video_ids:
            log_event("info", "youtube", "collect_video_started", video_id=video_id)
            video_item = client.get_video(video_id)
            if not video_item:
                log_event("error", "youtube", "video_not_found", video_id=video_id)
                continue
            channel_record, records = collect_video(
                client,
                video_item,
                collected_at=collected_at,
                max_comments=args.max_comments,
                anonymize_comments=args.anonymize_comments,
            )
            if channel_record:
                channels_by_id[channel_record["channel_id"]] = channel_record
            videos.append(records[0])
            comments.extend(records[1:])

        for channel_id in channel_ids:
            log_event("info", "youtube", "collect_channel_started", channel_id=channel_id)
            channel_item = client.get_channel(channel_id)
            if channel_item:
                channels_by_id[channel_id] = normalize_channel(channel_item, collected_at)
            for video_item in client.list_channel_videos(channel_id, max_videos=args.max_videos):
                channel_record, records = collect_video(
                    client,
                    video_item,
                    collected_at=collected_at,
                    max_comments=args.max_comments,
                    anonymize_comments=args.anonymize_comments,
                )
                if channel_record:
                    channels_by_id[channel_record["channel_id"]] = channel_record
                videos.append(records[0])
                comments.extend(records[1:])

    except QuotaExceededError:
        log_event("error", "youtube", "quota_exceeded_stop", error="quotaExceeded")
    except RateLimitExceededError:
        log_event("error", "youtube", "rate_limit_exceeded_stop", error="rateLimitExceeded")
    finally:
        write_outputs(list(channels_by_id.values()), videos, comments)
        log_event(
            "info",
            "youtube",
            "crawl_finished",
            channels=len(channels_by_id),
            videos=len(videos),
            comments=len(comments),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
