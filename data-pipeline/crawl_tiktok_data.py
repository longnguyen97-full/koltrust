from __future__ import annotations

import argparse
from pathlib import Path

from tiktok_client import TikTokPublicClient, normalize_tiktok_creator, normalize_tiktok_video
from utils import (
    append_jsonl,
    ensure_output_dirs,
    get_tiktok_ms_token,
    log_event,
    read_nonempty_lines,
    setup_logging,
    utc_now_iso,
)


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl public TikTok creator/video metadata using TikTokApi.")
    parser.add_argument("--username", action="append", default=[], help="Public TikTok username. Can be repeated.")
    parser.add_argument("--username-list", type=Path, help="Text file with one public TikTok username per line.")
    parser.add_argument("--category", default="unknown", help="Optional category label for all usernames in this run.")
    parser.add_argument("--max-videos", type=int, default=20, help="Maximum public videos per creator.")
    parser.add_argument("--browser", default="chromium", help="Playwright browser: chromium, firefox, or webkit.")
    parser.add_argument("--show-browser", action="store_true", help="Run browser visibly for debugging public pages.")
    parser.add_argument("--sleep-after", type=int, default=3, help="Seconds TikTokApi waits after session creation.")
    parser.add_argument("--no-ms-token", action="store_true", help="Do not pass ms_token to TikTokApi sessions.")
    return parser


def load_usernames(args: argparse.Namespace) -> list[str]:
    usernames = [username.lstrip("@").strip() for username in args.username if username.strip()]
    if args.username_list:
        usernames.extend(username.lstrip("@").strip() for username in read_nonempty_lines(args.username_list))
    return list(dict.fromkeys(username for username in usernames if username))


def main() -> int:
    args = build_parser().parse_args()
    ensure_output_dirs(ROOT)
    setup_logging(ROOT / "logs" / "tiktok_crawler.log")

    usernames = load_usernames(args)
    if not usernames:
        raise RuntimeError("Provide --username or --username-list with public TikTok usernames.")

    ms_token = None if args.no_ms_token else get_tiktok_ms_token()
    client = TikTokPublicClient(
        browser=args.browser,
        headless=not args.show_browser,
        sleep_after=args.sleep_after,
        ms_token=ms_token,
    )
    collected_at = utc_now_iso()
    creators: list[dict] = []
    videos: list[dict] = []

    for username in usernames:
        try:
            log_event("info", "tiktok", "collect_creator_started", username=username, max_videos=args.max_videos)
            creator_raw, video_raw_rows = client.collect_user_sync(username, max_videos=args.max_videos)
            creator = normalize_tiktok_creator(
                creator_raw,
                username=username,
                category=args.category,
                collected_at=collected_at,
            )
            creators.append(creator)
            videos.extend(
                normalize_tiktok_video(row, creator=creator, collected_at=collected_at)
                for row in video_raw_rows
            )
        except Exception as exc:
            log_event("error", "tiktok", "collect_creator_failed", username=username, error=str(exc))

    append_jsonl(RAW_DIR / "tiktok_creators.jsonl", creators)
    append_jsonl(RAW_DIR / "tiktok_videos.jsonl", videos)
    log_event("info", "tiktok", "crawl_finished", creators=len(creators), videos=len(videos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
