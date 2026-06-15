from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.trust_model import score_event

DEFAULT_INPUT = PROJECT_ROOT / "dataset" / "serving" / "kol_events.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "trust_scores.json"


def load_events(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "records" in payload:
        return payload["records"]
    if isinstance(payload, list):
        return payload
    return [payload]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run base trust model against sample/raw data.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    events = load_events(Path(args.input))
    scores = [score_event(event) for event in events]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(scores)} scored events to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
