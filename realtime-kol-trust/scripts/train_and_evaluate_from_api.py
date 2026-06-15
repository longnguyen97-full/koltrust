from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "api_kol_trust_predictions.csv"

sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.trust_model import score_event


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train from /dataset, call export APIs, and evaluate KOL trust scores."
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--skip-train", action="store_true")
    return parser.parse_args()


def train_model() -> None:
    subprocess.run(
        [sys.executable, "-m", "ml.training.train_trust_model"],
        cwd=PROJECT_ROOT,
        check=True,
    )


def get_json(base_url: str, path: str, limit: int) -> Any:
    response = requests.get(f"{base_url}{path}", params={"limit": limit}, timeout=30)
    response.raise_for_status()
    return response.json()


def get_jsonl(base_url: str, path: str, limit: int) -> list[dict[str, Any]]:
    response = requests.get(f"{base_url}{path}", params={"limit": limit}, timeout=30)
    response.raise_for_status()
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def main() -> int:
    args = parse_args()
    if not args.skip_train:
        train_model()

    bundle = get_json(args.base_url, "/api/export/bundle", args.limit)
    features = get_json(args.base_url, "/api/export/features", args.limit)
    events = get_jsonl(args.base_url, "/api/export/kol_events.jsonl", args.limit)

    scored = [score_event(event) for event in events]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        if scored:
            writer = csv.DictWriter(handle, fieldnames=list(scored[0].keys()))
            writer.writeheader()
            writer.writerows(scored)

    print(f"Bundle keys: {', '.join(bundle.keys())}")
    print(f"Feature rows: {len(features)}")
    print(f"Event rows: {len(events)}")
    print(f"Scored rows: {len(scored)}")
    print(f"Wrote predictions to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
