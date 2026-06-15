from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.trust_model import predict_kol_trust


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict KOL trust score with the trained trust model.")
    parser.add_argument("--input", help="CSV or JSONL feature file.")
    parser.add_argument("--output", help="Output CSV or JSONL path.")
    return parser.parse_args()


def load_rows(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return pd.DataFrame(rows)
    return pd.read_csv(path)


def write_rows(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".jsonl":
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in df.to_dict(orient="records")) + "\n",
            encoding="utf-8",
        )
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> int:
    args = parse_args()
    if not args.input:
        raise SystemExit("Pass --input.")

    df = load_rows(Path(args.input))
    predictions = [predict_kol_trust(row) for row in df.to_dict(orient="records")]
    pred_df = pd.DataFrame(predictions).rename(
        columns={
            "trust_score": "pred_trust_score",
            "trust_label": "pred_trust_label",
            "trust_source": "pred_trust_source",
            "engagement_rate": "pred_engagement_rate",
            "sentiment_score": "pred_sentiment_score",
            "activity_score": "pred_activity_score",
            "anomaly_score": "pred_anomaly_score",
            "is_suspicious": "pred_is_suspicious",
        }
    )
    result = pd.concat([df.reset_index(drop=True), pred_df], axis=1)
    print(result.head(20).to_string(index=False))
    if args.output:
        write_rows(result, Path(args.output))
        print(f"Wrote {len(result)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
