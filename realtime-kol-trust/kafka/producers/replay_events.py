from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from confluent_kafka import Producer
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

DEFAULT_SAMPLE_PATH = PROJECT_ROOT / "dataset" / "serving" / "kol_events.jsonl"
DEFAULT_SIMULATOR_BASE_URL = os.getenv("SIMULATOR_BASE_URL", "http://localhost:8010")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def jitter_event(event: dict[str, Any]) -> dict[str, Any]:
    item = dict(event)
    item["timestamp"] = utc_now()
    for key, drift in {
        "views": 0.08,
        "likes": 0.06,
        "comments": 0.10,
        "shares": 0.10,
        "followers": 0.02,
    }.items():
        value = int(item.get(key, 0) or 0)
        item[key] = max(0, int(value * random.uniform(1.0 - drift, 1.0 + drift)))
    item["follower_growth_rate"] = round(
        max(0.0, float(item.get("follower_growth_rate", 0.0)) + random.uniform(-0.01, 0.01)),
        4,
    )
    item["comment_spam_ratio"] = round(
        min(1.0, max(0.0, float(item.get("comment_spam_ratio", 0.0)) + random.uniform(-0.02, 0.02))),
        4,
    )
    return item


def delivery_report(error: Any, message: Any) -> None:
    if error is not None:
        print(f"delivery failed: {error}", file=sys.stderr)
        return
    print(f"sent {message.topic()}[{message.partition()}] offset={message.offset()}")


def fetch_simulator_kols(base_url: str) -> list[dict[str, Any]]:
    response = requests.get(f"{base_url.rstrip('/')}/api/kols", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_simulator_bundle(base_url: str, kol_id: str) -> dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/api/kols/{kol_id}/live", timeout=10)
    response.raise_for_status()
    return response.json()


def simulator_bundle_to_kafka_event(bundle: dict[str, Any]) -> dict[str, Any]:
    profile = bundle.get("profile") or {}
    metrics = bundle.get("metrics") or {}
    features = bundle.get("model_features") or {}
    recent_events = bundle.get("recent_events") or []
    comments = [
        str(event.get("value"))
        for event in recent_events
        if event.get("event_type") == "comment" and event.get("value") is not None
    ]
    views = int(metrics.get("viewers") or features.get("viewer_count") or 0)
    likes = int(metrics.get("likes") or features.get("like_count") or 0)
    comment_count = int(metrics.get("comments") or features.get("comment_count") or 0)
    shares = int(metrics.get("shares") or features.get("share_count") or 0)
    followers = int(profile.get("followers") or features.get("followers") or 0)
    return {
        "event_id": f"sim_{metrics.get('live_id', 'live')}_{int(time.time() * 1000)}",
        "kol_id": str(profile.get("kol_id") or metrics.get("kol_id") or features.get("kol_id") or "unknown"),
        "kol_name": str(profile.get("name") or features.get("kol_name") or "Unknown KOL"),
        "channel_id": str(profile.get("kol_id") or metrics.get("kol_id") or features.get("kol_id") or "unknown"),
        "channel_title": str(profile.get("name") or features.get("kol_name") or "Unknown KOL"),
        "platform": str(profile.get("platform") or features.get("platform") or "youtube"),
        "source": "simulator",
        "video_id": str(metrics.get("live_id") or features.get("live_id") or ""),
        "timestamp": str(metrics.get("timestamp") or features.get("timestamp") or utc_now()),
        "views": views,
        "likes": likes,
        "comments": comment_count,
        "shares": shares,
        "followers": followers,
        "upload_frequency_7d": round(float(features.get("activity_score") or 0.3) * 7.0, 4),
        "live_concurrent_viewers": float(views),
        "follower_growth_rate": float(features.get("bot_probability") or 0.0),
        "comment_spam_ratio": float(features.get("suspicious_event_ratio") or 0.0),
        "text": " ".join(comments[-20:]),
    }


def produce_payload(producer: Producer, topic: str, payload: dict[str, Any]) -> None:
    producer.produce(
        topic,
        key=str(payload.get("kol_id", "unknown")),
        value=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        callback=delivery_report,
    )
    producer.poll(0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce simulator or sample-file KOL events into Kafka.")
    parser.add_argument("--input", default=str(DEFAULT_SAMPLE_PATH))
    parser.add_argument("--source", choices=["simulator", "file"], default="simulator")
    parser.add_argument("--simulator-base-url", default=DEFAULT_SIMULATOR_BASE_URL)
    parser.add_argument("--topic", default=settings.kafka_raw_topic)
    parser.add_argument("--bootstrap-servers", default=settings.kafka_bootstrap_servers)
    parser.add_argument("--interval", type=float, default=settings.replay_interval_seconds)
    parser.add_argument("--loop", action="store_true", help="Keep replaying with small random drift.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    producer = Producer({"bootstrap.servers": args.bootstrap_servers})

    if args.source == "simulator":
        kols = fetch_simulator_kols(args.simulator_base_url)
        if not kols:
            print(f"No simulator KOLs returned from {args.simulator_base_url}", file=sys.stderr)
            return 1
        print(
            f"Producing simulator events for {len(kols)} KOLs to {args.topic} "
            f"via {args.bootstrap_servers}"
        )
        while True:
            for kol in kols:
                kol_id = str(kol.get("kol_id") or "")
                if not kol_id:
                    continue
                try:
                    bundle = fetch_simulator_bundle(args.simulator_base_url, kol_id)
                    produce_payload(producer, args.topic, simulator_bundle_to_kafka_event(bundle))
                except Exception as exc:
                    print(f"simulator fetch failed for {kol_id}: {exc}", file=sys.stderr)
                time.sleep(args.interval)
            producer.flush()
            if not args.loop:
                break
        return 0

    events = load_jsonl(Path(args.input))
    if not events:
        print(f"No events found in {args.input}", file=sys.stderr)
        return 1

    print(f"Replaying {len(events)} file events to {args.topic} via {args.bootstrap_servers}")

    while True:
        for event in events:
            payload = jitter_event(event) if args.loop else event
            produce_payload(producer, args.topic, payload)
            time.sleep(args.interval)
        producer.flush()
        if not args.loop:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
