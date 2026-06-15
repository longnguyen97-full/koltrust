# Source Layout

The workspace has three application sources plus one small shared package:

- `data-pipeline`: collects and builds the canonical processed dataset.
- `livestream-simulator`: generates synthetic realtime livestream events.
- `realtime-kol-trust`: serves API/dashboard and runs Kafka/Spark/Cassandra.
- `koltrust_common`: shared path helpers used by API and simulator.

## Dataset Ownership

`data-pipeline/data/processed` is the canonical local dataset output.

`realtime-kol-trust/dataset` is only a runtime copy/fallback for Docker and older commands. Local API and simulator code now resolve dataset paths through `koltrust_common.paths`, which prefers:

```text
KOLTRUST_DATASET_ROOT
data-pipeline/data/processed
realtime-kol-trust/dataset
```

This keeps the three sources separate by responsibility while avoiding repeated dataset path logic.

## Remaining Intentional Duplication

- API and simulator still have separate HTTP apps because they serve different workflows.
- Realtime Cassandra schema and batch dataset schema remain separate because one is serving state and one is offline lake data.
- Runtime generated datasets and model artifacts are ignored by Git.

## Legacy/Debug Surface Kept Intentionally

These are not part of the main realtime path, but are still useful for local smoke tests or demos:

- `process-sample`: offline model scoring for a local JSONL sample.
- `pull-simulator-sample`: export simulator events into a local JSONL sample file.
- `realtime-kol-trust/dataset/serving/kol_events.jsonl`: optional file replay/debug input.
- `realtime-kol-trust/scripts/train_and_evaluate_from_api.py`: API integration evaluation script.

The main realtime path is simulator API -> replay producer -> Kafka raw topic -> Spark Streaming -> MinIO lake layers -> Cassandra serving table.
