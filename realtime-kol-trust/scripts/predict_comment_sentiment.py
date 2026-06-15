from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.trust_model import predict_comment_sentiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict comment sentiment with the trained model.")
    parser.add_argument("--text", help="Single comment text to score.")
    parser.add_argument("--input", help="CSV or JSONL file to score.")
    parser.add_argument("--output", help="Output CSV or JSONL path when --input is used.")
    parser.add_argument("--text-column", default="comment", help="Text column in input file.")
    return parser.parse_args()


def score_text(text: str) -> dict:
    prediction = predict_comment_sentiment(text)
    return {"comment": text, **prediction}


def score_file(input_path: Path, output_path: Path | None, text_column: str) -> pd.DataFrame:
    if input_path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        df = pd.DataFrame(rows)
    else:
        df = pd.read_csv(input_path)

    if text_column not in df.columns:
        raise ValueError(f"Missing text column {text_column!r}. Available columns: {list(df.columns)}")

    predictions = df[text_column].fillna("").map(predict_comment_sentiment)
    pred_df = pd.DataFrame(predictions.tolist()).rename(
        columns={
            "sentiment_label": "pred_sentiment_label",
            "sentiment_score": "pred_sentiment_score",
            "sentiment_source": "pred_sentiment_source",
        }
    )
    result = pd.concat([df.reset_index(drop=True), pred_df], axis=1)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.suffix.lower() == ".jsonl":
            output_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in result.to_dict(orient="records")) + "\n",
                encoding="utf-8",
            )
        else:
            result.to_csv(output_path, index=False, encoding="utf-8-sig")

    return result


def main() -> int:
    args = parse_args()
    if args.text:
        print(json.dumps(score_text(args.text), ensure_ascii=False, indent=2))
        return 0

    if not args.input:
        raise SystemExit("Pass --text or --input.")

    result = score_file(Path(args.input), Path(args.output) if args.output else None, args.text_column)
    print(result.head(20).to_string(index=False))
    if args.output:
        print(f"Wrote {len(result)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
