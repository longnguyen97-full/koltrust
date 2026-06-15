from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "dataset" / "silver" / "comments" / "splits" / "train_comments.csv"
DEFAULT_EVAL_DATASET = PROJECT_ROOT / "dataset" / "silver" / "comments" / "splits" / "eval_comments.csv"
FALLBACK_DATASET = PROJECT_ROOT / "dataset" / "silver" / "comments" / "vietnam_comments_sentiment.csv"
DEFAULT_MODEL = PROJECT_ROOT / "ml" / "models" / "sentiment" / "comment_sentiment.joblib"

LABEL_TO_SCORE = {
    "negative": 0.15,
    "neutral": 0.50,
    "positive": 0.85,
}


def normalize_label(value: Any) -> str:
    label = str(value).strip().lower()
    aliases = {
        "0": "negative",
        "1": "neutral",
        "2": "positive",
        "neg": "negative",
        "neu": "neutral",
        "pos": "positive",
    }
    label = aliases.get(label, label)
    if label not in LABEL_TO_SCORE:
        raise ValueError(f"Unsupported label: {value!r}. Use negative, neutral, or positive.")
    return label


def read_csv(path: Path, text_column: str, label_column: str) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            text = str(row.get(text_column, "")).strip()
            if not text:
                continue
            texts.append(text)
            labels.append(normalize_label(row.get(label_column)))
    return texts, labels


def read_jsonl(path: Path, text_column: str, label_column: str) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = str(row.get(text_column, "")).strip()
        if not text:
            continue
        texts.append(text)
        labels.append(normalize_label(row.get(label_column)))
    return texts, labels


def load_dataset(path: Path, text_column: str, label_column: str) -> tuple[list[str], list[str]]:
    if path.suffix.lower() == ".jsonl":
        return read_jsonl(path, text_column, label_column)
    return read_csv(path, text_column, label_column)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train comment sentiment model from a labeled dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="CSV or JSONL file with text and label columns.")
    parser.add_argument("--eval-dataset", default=str(DEFAULT_EVAL_DATASET), help="CSV or JSONL eval split.")
    parser.add_argument("--output", default=str(DEFAULT_MODEL), help="Output .joblib model path.")
    parser.add_argument("--text-column", default="comment")
    parser.add_argument("--label-column", default="sentiment")
    parser.add_argument("--test-size", type=float, default=0.25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    eval_dataset_path: Path | None = Path(args.eval_dataset)
    output_path = Path(args.output)
    if not dataset_path.exists() and dataset_path == DEFAULT_DATASET:
        dataset_path = FALLBACK_DATASET
    if eval_dataset_path and not eval_dataset_path.exists():
        eval_dataset_path = None

    texts, labels = load_dataset(dataset_path, args.text_column, args.label_column)

    if len(texts) < 6:
        raise ValueError("Need at least 6 labeled comments to train a sentiment model.")

    if eval_dataset_path is not None:
        x_train, y_train = texts, labels
        x_test, y_test = load_dataset(eval_dataset_path, args.text_column, args.label_column)
    else:
        stratify = labels if min(labels.count(label) for label in set(labels)) >= 2 else None
        x_train, x_test, y_train, y_test = train_test_split(
            texts,
            labels,
            test_size=args.test_size,
            random_state=42,
            stratify=stratify,
        )

    model = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, strip_accents="unicode", lowercase=True)),
            ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    model.fit(x_train, y_train)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "label_to_score": LABEL_TO_SCORE,
            "text_column": args.text_column,
            "label_column": args.label_column,
            "split_strategy": "creator_id_hash_60_20_20",
            "train_dataset": str(dataset_path),
            "eval_dataset": str(eval_dataset_path) if eval_dataset_path is not None else "random_split_fallback",
        },
        output_path,
    )

    predictions = model.predict(x_test)
    print(f"Trained sentiment model with {len(x_train)} train rows and {len(x_test)} test rows.")
    print(f"Saved model to {output_path}")
    print(classification_report(y_test, predictions, zero_division=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
