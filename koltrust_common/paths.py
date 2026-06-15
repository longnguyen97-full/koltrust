from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PIPELINE_ROOT = REPO_ROOT / "data-pipeline"
REALTIME_ROOT = REPO_ROOT / "realtime-kol-trust"
SIMULATOR_ROOT = REPO_ROOT / "livestream-simulator"

DATA_PIPELINE_PROCESSED = DATA_PIPELINE_ROOT / "data" / "processed"
REALTIME_DATASET = REALTIME_ROOT / "dataset"
APP_DATASET = REPO_ROOT / "dataset"


def dataset_root() -> Path:
    configured = os.getenv("KOLTRUST_DATASET_ROOT")
    if configured:
        return Path(configured)
    if DATA_PIPELINE_PROCESSED.exists():
        return DATA_PIPELINE_PROCESSED
    if APP_DATASET.exists():
        return APP_DATASET
    return REALTIME_DATASET


def serving_events_path() -> Path:
    return dataset_root() / "serving" / "kol_events.jsonl"


def features_path() -> Path:
    return dataset_root() / "silver" / "unified" / "vietnam_influencer_features.csv"


def trust_scores_path() -> Path:
    return dataset_root() / "gold" / "features" / "trust_scores.csv"


def manifest_path() -> Path:
    return dataset_root() / "manifest.json"


def stats_path() -> Path:
    return dataset_root() / "dataset_stats.json"


def simulator_profiles_path() -> Path:
    return dataset_root() / "silver" / "profiles" / "simulator_profiles.csv"
