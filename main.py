from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_PIPELINE_ROOT = ROOT / "data-pipeline"
SIMULATION_ROOT = ROOT / "livestream-simulator"
REALTIME_ROOT = ROOT / "realtime-kol-trust"

DATA_PIPELINE_PROCESSED = DATA_PIPELINE_ROOT / "data" / "processed"
DATA_PIPELINE_REPLAY_EVENTS = DATA_PIPELINE_PROCESSED / "serving" / "kol_events.jsonl"
REALTIME_DATASET = REALTIME_ROOT / "dataset"
REALTIME_REPLAY_EVENTS = REALTIME_DATASET / "serving" / "kol_events.jsonl"
REALTIME_PROCESSED = REALTIME_ROOT / "data" / "processed" / "trust_scores.json"


def run_command(command: list[str], cwd: Path) -> int:
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.call(command, cwd=str(cwd))


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing source path: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing source file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sync_dataset(_: argparse.Namespace) -> int:
    copy_tree(DATA_PIPELINE_PROCESSED, REALTIME_DATASET)
    if DATA_PIPELINE_REPLAY_EVENTS.exists():
        copy_file(DATA_PIPELINE_REPLAY_EVENTS, REALTIME_REPLAY_EVENTS)
    print(f"Synced processed dataset: {DATA_PIPELINE_PROCESSED} -> {REALTIME_DATASET}")
    if DATA_PIPELINE_REPLAY_EVENTS.exists():
        print(f"Synced replay events: {DATA_PIPELINE_REPLAY_EVENTS} -> {REALTIME_REPLAY_EVENTS}")
    return 0


def build_dataset(args: argparse.Namespace) -> int:
    exit_code = run_command([sys.executable, "build_dataset.py"], DATA_PIPELINE_ROOT)
    if exit_code != 0:
        return exit_code
    return sync_dataset(args)


def process_sample(args: argparse.Namespace) -> int:
    input_path = Path(args.input) if args.input else REALTIME_REPLAY_EVENTS
    output_path = Path(args.output) if args.output else REALTIME_PROCESSED
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    return run_command(
        [
            sys.executable,
            "scripts/process_sample.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        REALTIME_ROOT,
    )


def fetch_text(url: str, timeout: int = 15) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "koltrust-system/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def pull_simulator_sample(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    if args.kol_id:
        path = f"/api/kols/{args.kol_id}/export/kol_events.jsonl?limit={args.limit}"
    else:
        path = f"/api/export/kol_events.jsonl?limit={args.limit}"
    output = Path(args.output) if args.output else REALTIME_REPLAY_EVENTS
    if not output.is_absolute():
        output = ROOT / output

    try:
        payload = fetch_text(f"{base_url}{path}")
    except urllib.error.URLError as exc:
        print(
            f"Cannot reach simulator at {base_url}. Start it first with:\n"
            f"  uv run --directory \"{SIMULATION_ROOT}\" python -m uvicorn app.main:app --reload --port 8010\n"
            f"from {SIMULATION_ROOT}\n\n{exc}",
            file=sys.stderr,
        )
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"Wrote simulator events to {output}")
    return 0


def doctor(_: argparse.Namespace) -> int:
    checks = {
        "Data pipeline source": DATA_PIPELINE_ROOT,
        "Simulator source": SIMULATION_ROOT,
        "Realtime source": REALTIME_ROOT,
        "Data pipeline processed": DATA_PIPELINE_PROCESSED,
        "Realtime API": REALTIME_ROOT / "backend" / "fastapi" / "main.py",
        "Simulator API": SIMULATION_ROOT / "app" / "main.py",
        "Realtime replay events": REALTIME_REPLAY_EVENTS,
    }
    failed = False
    for label, path in checks.items():
        ok = path.exists()
        failed = failed or not ok
        marker = "ok" if ok else "missing"
        print(f"{marker:7} {label}: {path}")
    return 1 if failed else 0


def print_commands(_: argparse.Namespace) -> int:
    print("Run these in separate terminals:")
    print(f"1. Simulator API:  uv run --directory \"{SIMULATION_ROOT}\" python -m uvicorn app.main:app --reload --port 8010")
    print(f"2. Realtime API:   uv run --directory \"{REALTIME_ROOT}\" python -m uvicorn backend.fastapi.main:app --reload --port 8000")
    print(f"3. Dashboard:      uv run --directory \"{REALTIME_ROOT}\" python -m streamlit run dashboard/streamlit/app.py")
    print(f"4. Docker stack:   docker compose --project-directory \"{REALTIME_ROOT}\" --profile replay up --build")
    return 0


def run_pipeline(args: argparse.Namespace | None = None) -> int:
    args = args or argparse.Namespace(input=None, output=None)
    exit_code = build_dataset(args)
    if exit_code != 0:
        return exit_code
    return process_sample(args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coordinator CLI for data ingestion, livestream simulation, and realtime KOL trust scoring."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Check whether the three source trees and key files exist.").set_defaults(
        func=doctor
    )
    subparsers.add_parser("sync-dataset", help="Copy data-pipeline processed outputs into the realtime source.").set_defaults(
        func=sync_dataset
    )

    subparsers.add_parser("build-dataset", help="Build data-pipeline processed data, then sync it to realtime.").set_defaults(
        func=build_dataset
    )

    process_parser = subparsers.add_parser("process-sample", help="Score replay JSONL events with the realtime model.")
    process_parser.add_argument("--input", default=None)
    process_parser.add_argument("--output", default=None)
    process_parser.set_defaults(func=process_sample)

    sim_parser = subparsers.add_parser("pull-simulator-sample", help="Fetch simulator JSONL events into realtime serving data.")
    sim_parser.add_argument("--base-url", default="http://localhost:8010")
    sim_parser.add_argument("--kol-id", default=None)
    sim_parser.add_argument("--limit", type=int, default=500)
    sim_parser.add_argument("--output", default=None)
    sim_parser.set_defaults(func=pull_simulator_sample)

    subparsers.add_parser("commands", help="Print the service commands for local development.").set_defaults(
        func=print_commands
    )

    pipeline_parser = subparsers.add_parser("pipeline", help="Build data-pipeline processed data, sync it, and score replay events.")
    pipeline_parser.add_argument("--input", default=None)
    pipeline_parser.add_argument("--output", default=None)
    pipeline_parser.set_defaults(func=run_pipeline)

    parser.set_defaults(func=doctor)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
