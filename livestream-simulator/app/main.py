from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.models import ExportBundle, KolEvent, KolProfile, LiveMetrics, SimulationConfig
from app.simulator import LivestreamSimulator

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="KOLTrust Livestream Simulator",
    description="Website va API gia lap KOL livestream de feed vao realtime-kol-trust.",
    version="0.1.0",
)
simulator = LivestreamSimulator()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kol-livestream-simulator"}


def require_session(kol_id: str):
    try:
        return simulator.session(kol_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown kol_id: {kol_id}") from exc


@app.get("/api/kols", response_model=list[KolProfile])
def list_kols() -> list[KolProfile]:
    return simulator.list_profiles()


@app.get("/api/profile", response_model=KolProfile)
def get_profile() -> KolProfile:
    return simulator.profile


@app.get("/api/live", response_model=ExportBundle)
def get_live_tick() -> ExportBundle:
    return simulator.tick()


@app.get("/api/metrics", response_model=LiveMetrics)
def get_metrics() -> LiveMetrics:
    return simulator.metrics()


@app.get("/api/events", response_model=list[KolEvent])
def get_events(limit: int = Query(default=100, ge=1, le=1000)) -> list[KolEvent]:
    return simulator.recent_events(limit=limit)


@app.get("/api/export/bundle", response_model=ExportBundle)
def export_bundle() -> ExportBundle:
    return simulator.tick()


@app.get("/api/export/features")
def export_features() -> dict[str, int | float | str | bool]:
    metrics = simulator.metrics()
    return simulator.model_features(metrics)


@app.get("/api/export/kol_events.jsonl", response_class=PlainTextResponse)
def export_events_jsonl(limit: int = Query(default=500, ge=1, le=1000)) -> str:
    return simulator.export_jsonl(limit=limit)


@app.post("/api/simulation/config", response_model=SimulationConfig)
def set_simulation_config(config: SimulationConfig) -> SimulationConfig:
    return simulator.set_config(config)


@app.post("/api/simulation/reset")
def reset_simulation() -> dict[str, str]:
    simulator.reset()
    return {"status": "reset", "live_id": simulator.metrics().live_id}


@app.get("/api/kols/{kol_id}/profile", response_model=KolProfile)
def get_kol_profile(kol_id: str) -> KolProfile:
    return require_session(kol_id).profile


@app.get("/api/kols/{kol_id}/live", response_model=ExportBundle)
def get_kol_live_tick(kol_id: str) -> ExportBundle:
    require_session(kol_id)
    return simulator.tick(kol_id)


@app.get("/api/kols/{kol_id}/metrics", response_model=LiveMetrics)
def get_kol_metrics(kol_id: str) -> LiveMetrics:
    require_session(kol_id)
    return simulator.metrics(kol_id)


@app.get("/api/kols/{kol_id}/events", response_model=list[KolEvent])
def get_kol_events(kol_id: str, limit: int = Query(default=100, ge=1, le=1000)) -> list[KolEvent]:
    require_session(kol_id)
    return simulator.recent_events(kol_id, limit=limit)


@app.get("/api/kols/{kol_id}/export/bundle", response_model=ExportBundle)
def export_kol_bundle(kol_id: str) -> ExportBundle:
    require_session(kol_id)
    return simulator.tick(kol_id)


@app.get("/api/kols/{kol_id}/export/features")
def export_kol_features(kol_id: str) -> dict[str, int | float | str | bool]:
    require_session(kol_id)
    return simulator.model_features(kol_id)


@app.get("/api/kols/{kol_id}/export/kol_events.jsonl", response_class=PlainTextResponse)
def export_kol_events_jsonl(kol_id: str, limit: int = Query(default=500, ge=1, le=1000)) -> str:
    require_session(kol_id)
    return simulator.export_jsonl(kol_id, limit=limit)


@app.post("/api/kols/{kol_id}/simulation/config", response_model=SimulationConfig)
def set_kol_simulation_config(kol_id: str, config: SimulationConfig) -> SimulationConfig:
    require_session(kol_id)
    return simulator.set_config(config.model_copy(update={"kol_id": kol_id}))


@app.post("/api/kols/{kol_id}/simulation/reset")
def reset_kol_simulation(kol_id: str) -> dict[str, str]:
    require_session(kol_id)
    simulator.reset(kol_id)
    return {"status": "reset", "live_id": simulator.metrics(kol_id).live_id}
