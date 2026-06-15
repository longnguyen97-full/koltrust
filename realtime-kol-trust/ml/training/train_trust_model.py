from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.inference.trust_model import TRUST_CATEGORICAL_FEATURES, TRUST_NUMERIC_FEATURES


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "dataset" / "silver" / "unified" / "splits" / "train_features.csv"
DEFAULT_EVAL_DATASET = PROJECT_ROOT / "dataset" / "silver" / "unified" / "splits" / "eval_features.csv"
FALLBACK_DATASET = PROJECT_ROOT / "dataset" / "silver" / "unified" / "vietnam_influencer_features.csv"
DEFAULT_MODEL = PROJECT_ROOT / "ml" / "models" / "trust_score" / "kol_trust_model.joblib"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train KOL trust score model from influencer feature dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--eval-dataset", default=str(DEFAULT_EVAL_DATASET))
    parser.add_argument("--output", default=str(DEFAULT_MODEL))
    parser.add_argument("--target-column", default="trust_score")
    return parser.parse_args()


def prepare_frame(df: pd.DataFrame, target_column: str) -> tuple[pd.DataFrame, pd.Series]:
    required = TRUST_NUMERIC_FEATURES + TRUST_CATEGORICAL_FEATURES + [target_column]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = df[required].copy()
    for column in TRUST_NUMERIC_FEATURES:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    for column in TRUST_CATEGORICAL_FEATURES:
        data[column] = data[column].fillna("unknown").astype(str)
    data[target_column] = pd.to_numeric(data[target_column], errors="coerce")
    data = data.dropna(subset=[target_column])

    x = data[TRUST_NUMERIC_FEATURES + TRUST_CATEGORICAL_FEATURES]
    y = data[target_column]
    return x, y


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    eval_dataset_path = Path(args.eval_dataset)
    output_path = Path(args.output)

    if not dataset_path.exists() and dataset_path == DEFAULT_DATASET:
        dataset_path = FALLBACK_DATASET
    if not eval_dataset_path.exists():
        eval_dataset_path = dataset_path

    train_df = pd.read_csv(dataset_path)
    eval_df = pd.read_csv(eval_dataset_path)
    x_train, y_train = prepare_frame(train_df, args.target_column)
    x_test, y_test = prepare_frame(eval_df, args.target_column)

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", TRUST_NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), TRUST_CATEGORICAL_FEATURES),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_leaf=2,
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions) if len(y_test) >= 2 else 0.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "numeric_features": TRUST_NUMERIC_FEATURES,
            "categorical_features": TRUST_CATEGORICAL_FEATURES,
            "target_column": args.target_column,
            "label_notice": "Trained on rule-generated trust_score labels, not human ground truth.",
            "split_strategy": "creator_id_hash_60_20_20",
            "train_dataset": str(dataset_path),
            "eval_dataset": str(eval_dataset_path),
            "metrics": {"mae": mae, "r2": r2, "train_rows": len(x_train), "test_rows": len(x_test)},
        },
        output_path,
    )

    print(f"Trained trust model with {len(x_train)} train rows and {len(x_test)} test rows.")
    print(f"Saved model to {output_path}")
    print(f"MAE: {mae:.4f}")
    print(f"R2: {r2:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
