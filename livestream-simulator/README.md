# Livestream Simulator

Simulates KOL livestream rooms and exports realtime events for `realtime-kol-trust`.

## Run

From repo root:

```powershell
uv run --directory livestream-simulator python -m uvicorn app.main:app --reload --port 8010
```

Open:

```text
http://localhost:8010
http://localhost:8010/docs
```

## KOL Source

The simulator reads KOL identity/profile seeds from:

```text
realtime-kol-trust/dataset/silver/profiles/simulator_profiles.csv
```

This file is generated from the `analysis_profile` split. It contains basic profile fields only and does not include `trust_score`. If the file is missing, the simulator falls back to five demo KOL profiles.

## Export Events

```powershell
curl http://localhost:8010/api/kols/<kol_id>/export/kol_events.jsonl?limit=500
```

Or sync simulator events into the realtime serving sample:

```powershell
uv run python -m pull-simulator-sample --kol-id <kol_id> --limit 500
```

Output:

```text
realtime-kol-trust/dataset/serving/kol_events.jsonl
```
