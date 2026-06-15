from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = ROOT / "data-pipeline" / "data" / "processed"


def load_pandera() -> Any:
    try:
        import pandera.pandas as pa
        from pandera.pandas import Check, Column, DataFrameSchema
    except ImportError as exc:
        raise SystemExit(
            "Pandera chưa được cài. Chạy `uv sync`, sau đó chạy lại `uv run python -m validate-data`."
        ) from exc
    return pa, Check, Column, DataFrameSchema


def influencer_schema() -> Any:
    _, Check, Column, DataFrameSchema = load_pandera()
    return DataFrameSchema(
        {
            "platform": Column(str, Check.isin(["youtube", "tiktok"]), nullable=False),
            "creator_id": Column(str, nullable=False),
            "creator_name": Column(str, nullable=True),
            "content_id": Column(str, nullable=False),
            "view_count": Column(int, Check.ge(0), nullable=False),
            "like_count": Column(int, Check.ge(0), nullable=False),
            "comment_count": Column(int, Check.ge(0), nullable=False),
            "share_count": Column(int, Check.ge(0), nullable=False),
            "engagement_rate": Column(float, Check.ge(0), nullable=False),
            "sentiment_score": Column(float, Check.in_range(0, 100), nullable=False),
            "activity_score": Column(float, Check.in_range(0, 100), nullable=False),
            "trust_score": Column(float, Check.in_range(0, 100), nullable=False),
            "is_suspicious": Column(int, Check.isin([0, 1]), nullable=False),
            "label_source": Column(str, nullable=False),
        },
        coerce=True,
        strict=False,
    )


def comments_schema() -> Any:
    _, Check, Column, DataFrameSchema = load_pandera()
    return DataFrameSchema(
        {
            "platform": Column(str, Check.isin(["youtube"]), nullable=False),
            "creator_id": Column(str, nullable=False),
            "content_id": Column(str, nullable=False),
            "comment_id": Column(str, nullable=False),
            "is_reply": Column(bool, nullable=False),
            "comment_text_is_hashed": Column(bool, nullable=False),
            "like_count": Column(int, Check.ge(0), nullable=False),
            "sentiment": Column(str, Check.isin(["positive", "neutral", "negative"]), nullable=False),
            "sentiment_score": Column(float, Check.in_range(0, 100), nullable=False),
            "sentiment_source": Column(str, nullable=False),
        },
        coerce=True,
        strict=False,
    )


def trust_scores_schema() -> Any:
    _, Check, Column, DataFrameSchema = load_pandera()
    return DataFrameSchema(
        {
            "rank": Column(int, Check.ge(1), nullable=False),
            "platform": Column(str, Check.isin(["youtube", "tiktok"]), nullable=False),
            "creator_id": Column(str, nullable=False),
            "creator_name": Column(str, nullable=True),
            "follower_count": Column(int, Check.ge(0), nullable=False),
            "observed_content_count": Column(int, Check.ge(0), nullable=False),
            "avg_engagement_rate": Column(float, Check.ge(0), nullable=False),
            "avg_sentiment_score": Column(float, Check.in_range(0, 100), nullable=False),
            "avg_activity_score": Column(float, Check.in_range(0, 100), nullable=False),
            "trust_score": Column(float, Check.in_range(0, 100), nullable=False),
            "suspicious_content_count": Column(int, Check.ge(0), nullable=False),
            "label_source": Column(str, nullable=False),
        },
        coerce=True,
        strict=False,
    )


def validate_csv(label: str, path: Path, schema: Any) -> dict[str, Any]:
    if not path.exists():
        return {"name": label, "path": str(path), "status": "missing", "rows": 0}
    frame = pd.read_csv(path)
    schema.validate(frame, lazy=True)
    return {
        "name": label,
        "path": str(path),
        "status": "ok",
        "rows": int(len(frame)),
        "columns": list(frame.columns),
    }


def validate_jsonl(path: Path) -> dict[str, Any]:
    required = {"event_id", "platform", "engagement_rate", "sentiment_score", "trust_score", "collected_at"}
    if not path.exists():
        return {"name": "serving_events", "path": str(path), "status": "missing", "rows": 0}

    rows = 0
    bad_rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rows += 1
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                bad_rows.append({"line": line_no, "error": str(exc)})
                continue
            missing = sorted(required - set(payload))
            if missing:
                bad_rows.append({"line": line_no, "missing": missing})

    status = "ok" if not bad_rows else "failed"
    return {
        "name": "serving_events",
        "path": str(path),
        "status": status,
        "rows": rows,
        "bad_rows": bad_rows[:20],
    }


def run_validation(data_root: Path) -> dict[str, Any]:
    results = [
        validate_csv(
            "influencer_features",
            data_root / "silver" / "unified" / "vietnam_influencer_features.csv",
            influencer_schema(),
        ),
        validate_csv(
            "comments_sentiment",
            data_root / "silver" / "comments" / "vietnam_comments_sentiment.csv",
            comments_schema(),
        ),
        validate_csv(
            "trust_scores",
            data_root / "gold" / "features" / "trust_scores.csv",
            trust_scores_schema(),
        ),
        validate_jsonl(data_root / "serving" / "kol_events.jsonl"),
    ]
    failed = [item for item in results if item["status"] != "ok"]
    return {
        "status": "failed" if failed else "ok",
        "data_root": str(data_root),
        "checks": results,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate processed KOLTrust datasets with Pandera.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--report", default=str(DEFAULT_DATA_ROOT / "quality_report.json"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    report = run_validation(Path(args.data_root))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1
