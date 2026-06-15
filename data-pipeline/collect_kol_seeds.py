from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from normalizer import normalize_channel
from utils import (
    QuotaExceededError,
    ensure_output_dirs,
    get_youtube_api_key,
    log_event,
    setup_logging,
    utc_now_iso,
)
from youtube_client import YouTubeClient


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "data" / "input"
RAW_DIR = ROOT / "data" / "raw"

DEFAULT_KEYWORDS = [
    "Vietnam gaming",
    "Vietnam music",
    "Vietnam tech",
    "Vietnam cooking",
    "Vietnam travel",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a seed list of public YouTube KOL channels.")
    parser.add_argument("--keyword", action="append", default=[], help="Search keyword. Can be repeated.")
    parser.add_argument("--keywords-file", type=Path, help="Text file with one keyword per line.")
    parser.add_argument("--max-results", type=int, default=20, help="Maximum channels per keyword.")
    parser.add_argument("--region-code", default="VN", help="Optional YouTube search region code.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API requests.")
    parser.add_argument("--output-list", type=Path, default=INPUT_DIR / "vn_channels.txt")
    parser.add_argument("--output-csv", type=Path, default=RAW_DIR / "youtube_channel_seeds.csv")
    parser.add_argument("--output-jsonl", type=Path, default=RAW_DIR / "youtube_channel_seeds.jsonl")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite seed outputs instead of failing if they exist.")
    return parser


def load_keywords(args: argparse.Namespace) -> list[str]:
    keywords = list(args.keyword)
    if args.keywords_file:
        with args.keywords_file.open("r", encoding="utf-8") as handle:
            keywords.extend(line.strip() for line in handle if line.strip() and not line.strip().startswith("#"))
    if not keywords:
        keywords = DEFAULT_KEYWORDS
    return list(dict.fromkeys(keywords))


def assert_can_write(paths: list[Path], overwrite: bool) -> None:
    if overwrite:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise RuntimeError(f"Output file already exists. Use --overwrite to replace: {', '.join(existing)}")


def write_seed_files(channels: list[dict], *, list_path: Path, csv_path: Path, jsonl_path: Path) -> None:
    list_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with list_path.open("w", encoding="utf-8") as handle:
        for channel in channels:
            handle.write(f"{channel['channel_id']}\n")

    fieldnames = [
        "seed_keyword",
        "platform",
        "channel_id",
        "channel_name",
        "subscriber_count",
        "video_count",
        "view_count",
        "channel_url",
        "collected_at",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for channel in channels:
            writer.writerow({field: channel.get(field) for field in fieldnames})

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for channel in channels:
            handle.write(json.dumps(channel, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    args = build_parser().parse_args()
    ensure_output_dirs(ROOT)
    setup_logging(ROOT / "logs" / "collect_kol_seeds.log")
    assert_can_write([args.output_list, args.output_csv, args.output_jsonl], args.overwrite)

    api_key = get_youtube_api_key(ROOT)
    client = YouTubeClient(api_key, sleep_seconds=args.sleep)
    collected_at = utc_now_iso()
    keywords = load_keywords(args)
    channels_by_id: dict[str, dict] = {}

    try:
        for keyword in keywords:
            log_event("info", "youtube", "seed_search_started", keyword=keyword, max_results=args.max_results)
            for item in client.search_channels(keyword, max_results=args.max_results, region_code=args.region_code):
                channel = normalize_channel(item, collected_at)
                channel["seed_keyword"] = keyword
                channel["channel_url"] = f"https://www.youtube.com/channel/{channel['channel_id']}"
                channels_by_id[channel["channel_id"]] = channel
    except QuotaExceededError:
        log_event("error", "youtube", "quota_exceeded_stop", error="quotaExceeded")
    finally:
        channels = sorted(
            channels_by_id.values(),
            key=lambda row: int(row.get("subscriber_count") or 0),
            reverse=True,
        )
        write_seed_files(channels, list_path=args.output_list, csv_path=args.output_csv, jsonl_path=args.output_jsonl)
        log_event("info", "youtube", "seed_collection_finished", channels=len(channels))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
