from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

from app.core.config import settings


DEFAULT_API_BASE_URL = settings.api_base_url or "http://localhost:8000"

st.set_page_config(page_title="KOL Monitor", page_icon=":bar_chart:", layout="wide")


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


@st.cache_data(ttl=3, show_spinner=False)
def request_json(base_url: str, path: str) -> Any:
    response = requests.get(f"{base_url}{path}", timeout=8)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3, show_spinner=False)
def request_text(base_url: str, path: str) -> str:
    response = requests.get(f"{base_url}{path}", timeout=8)
    response.raise_for_status()
    return response.text


def safe_json(base_url: str, path: str, default: Any) -> tuple[Any, str | None]:
    try:
        return request_json(base_url, path), None
    except Exception as exc:
        return default, f"{path}: {exc}"


def safe_text(base_url: str, path: str, default: str = "") -> tuple[str, str | None]:
    try:
        return request_text(base_url, path), None
    except Exception as exc:
        return default, f"{path}: {exc}"


def parse_jsonl(payload: str) -> list[dict[str, Any]]:
    rows = []
    for line in payload.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_percent(value: Any) -> str:
    return f"{as_float(value) * 100:.1f}%"


def risk_score_from_features(features: dict[str, Any], metrics: dict[str, Any]) -> float:
    bot = as_float(features.get("bot_probability", metrics.get("bot_probability")))
    suspicious = as_float(features.get("suspicious_event_ratio"))
    sentiment = as_float(features.get("sentiment_score", metrics.get("sentiment_score")), 0.5)
    reputation = as_float(features.get("profile_reputation_score"), 0.5)
    risk = bot * 0.4 + suspicious * 0.3 + (1.0 - sentiment) * 0.2 + (1.0 - reputation) * 0.1
    return max(0.0, min(1.0, risk))


def trust_label_from_risk(risk: float) -> str:
    if risk >= 0.65:
        return "risky"
    if risk >= 0.38:
        return "watch"
    return "trusted"


def dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def load_kols(base_url: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    kols, error = safe_json(base_url, "/api/kols", [])
    if error:
        errors.append(error)
        latest, latest_error = safe_json(base_url, "/kol/top?limit=100", [])
        if latest_error:
            errors.append(latest_error)
        kols = [
            {
                "kol_id": row.get("kol_id"),
                "name": row.get("kol_name", row.get("kol_id")),
                "platform": row.get("platform"),
                "followers": row.get("followers"),
                "risk_profile": row.get("trust_label"),
                "reputation_score": as_float(row.get("trust_score")) / 100,
            }
            for row in latest
        ]
    return kols, errors


def load_live_bundle(base_url: str, kol_id: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    live, error = safe_json(base_url, f"/api/kols/{kol_id}/live", {})
    if error:
        errors.append(error)
    metrics = live.get("metrics") if isinstance(live, dict) else {}
    profile = live.get("profile") if isinstance(live, dict) else {}
    recent_events = live.get("recent_events") if isinstance(live, dict) else []

    if not metrics:
        metrics, error = safe_json(base_url, f"/api/kols/{kol_id}/metrics", {})
        if error:
            errors.append(error)
    events, error = safe_json(base_url, f"/api/kols/{kol_id}/events?limit=250", recent_events)
    if error:
        errors.append(error)
        events = recent_events
    features, error = safe_json(base_url, f"/api/kols/{kol_id}/export/features", {})
    if error:
        errors.append(error)
    jsonl_text, error = safe_text(base_url, f"/api/kols/{kol_id}/export/kol_events.jsonl?limit=500")
    if error:
        errors.append(error)
    export_events = parse_jsonl(jsonl_text) if jsonl_text else []
    return {
        "profile": profile,
        "metrics": metrics,
        "events": events or export_events,
        "features": features,
        "export_events": export_events,
    }, errors


def metric_cards(metrics: dict[str, Any], features: dict[str, Any]) -> None:
    cols = st.columns(6)
    cols[0].metric("Viewers", f"{int(as_float(metrics.get('viewers', features.get('viewer_count')))):,}")
    cols[1].metric("Likes", f"{int(as_float(metrics.get('likes', features.get('like_count')))):,}")
    cols[2].metric("Comments", f"{int(as_float(metrics.get('comments', features.get('comment_count')))):,}")
    cols[3].metric("Shares", f"{int(as_float(metrics.get('shares', features.get('share_count')))):,}")
    cols[4].metric("Bot probability", as_percent(features.get("bot_probability", metrics.get("bot_probability"))))
    cols[5].metric("Sentiment", as_percent(features.get("sentiment_score", metrics.get("sentiment_score"))))


def monitoring_page(base_url: str, refresh_seconds: int) -> None:
    st.title("Monitoring & Logging")
    kols, errors = load_kols(base_url)
    kols_df = dataframe(kols)

    if kols_df.empty:
        st.warning("No KOL data returned from the configured API.")
        for error in errors:
            st.error(error)
        return

    live_rows = []
    event_rows: list[dict[str, Any]] = []
    page_errors = errors[:]
    for kol in kols:
        kol_id = kol.get("kol_id")
        if not kol_id:
            continue
        bundle, bundle_errors = load_live_bundle(base_url, str(kol_id))
        page_errors.extend(bundle_errors)
        profile = bundle["profile"] or kol
        metrics = bundle["metrics"]
        features = bundle["features"]
        risk = risk_score_from_features(features, metrics)
        live_rows.append(
            {
                "kol_id": kol_id,
                "name": profile.get("name") or kol.get("name"),
                "platform": profile.get("platform") or kol.get("platform"),
                "risk_profile": profile.get("risk_profile") or trust_label_from_risk(risk),
                "trust_signal": metrics.get("trust_signal") or features.get("trust_label"),
                "viewers": metrics.get("viewers") or features.get("viewer_count"),
                "engagement_rate": metrics.get("engagement_rate") or features.get("engagement_rate"),
                "sentiment_score": metrics.get("sentiment_score") or features.get("sentiment_score"),
                "bot_probability": metrics.get("bot_probability") or features.get("bot_probability"),
                "suspicious_spike": metrics.get("suspicious_spike") or features.get("is_suspicious"),
                "risk_score": round(risk, 4),
                "timestamp": metrics.get("timestamp") or features.get("timestamp"),
            }
        )
        event_rows.extend(bundle["events"])

    live_df = dataframe(live_rows)
    events_df = dataframe(event_rows)

    status_cols = st.columns(5)
    status_cols[0].metric("API", "online" if not kols_df.empty else "offline")
    status_cols[1].metric("KOLs", len(kols_df))
    status_cols[2].metric("Events", len(events_df))
    status_cols[3].metric("Suspicious events", int(events_df.get("is_suspicious", pd.Series(dtype=bool)).fillna(False).sum()) if not events_df.empty else 0)
    status_cols[4].metric("Refresh", f"{refresh_seconds}s")

    chart_cols = st.columns([1.15, 0.85])
    with chart_cols[0]:
        if not live_df.empty:
            fig = px.bar(
                live_df.sort_values("risk_score"),
                x="risk_score",
                y="name",
                color="risk_profile",
                orientation="h",
                range_x=[0, 1],
                labels={"risk_score": "Risk score", "name": ""},
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with chart_cols[1]:
        if not events_df.empty and "event_type" in events_df.columns:
            counts = Counter(events_df["event_type"].fillna("unknown"))
            fig = px.pie(
                names=list(counts.keys()),
                values=list(counts.values()),
                hole=0.45,
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Live KOL Status")
    show_cols = [
        "name",
        "platform",
        "risk_profile",
        "trust_signal",
        "viewers",
        "engagement_rate",
        "sentiment_score",
        "bot_probability",
        "suspicious_spike",
        "timestamp",
    ]
    st.dataframe(live_df[[col for col in show_cols if col in live_df.columns]], use_container_width=True, hide_index=True)

    st.subheader("Event Log")
    if events_df.empty:
        st.info("No live events returned.")
    else:
        log_cols = ["timestamp", "kol_id", "platform", "event_type", "user_id", "value", "sentiment_score", "is_suspicious"]
        st.dataframe(events_df[[col for col in log_cols if col in events_df.columns]].head(300), use_container_width=True, hide_index=True)

    if page_errors:
        with st.expander("API errors"):
            for error in page_errors[:20]:
                st.code(error)


def kol_evaluation_page(base_url: str) -> None:
    st.title("KOL Evaluation")
    kols, errors = load_kols(base_url)
    if not kols:
        st.warning("No KOL list available.")
        for error in errors:
            st.error(error)
        return

    options = {f"{kol.get('name', kol.get('kol_id'))} ({kol.get('kol_id')})": kol for kol in kols}
    selected_label = st.selectbox("Select KOL", list(options.keys()))
    selected = options[selected_label]
    kol_id = str(selected.get("kol_id"))
    bundle, bundle_errors = load_live_bundle(base_url, kol_id)

    profile = bundle["profile"] or selected
    metrics = bundle["metrics"]
    features = bundle["features"]
    events_df = dataframe(bundle["events"])
    risk_score = risk_score_from_features(features, metrics)
    label = features.get("trust_label") or metrics.get("trust_signal") or trust_label_from_risk(risk_score)
    trust_score = round((1.0 - risk_score) * 100, 2)

    header_cols = st.columns([1.2, 1, 1, 1])
    header_cols[0].metric("KOL", profile.get("name") or selected.get("name") or kol_id)
    header_cols[1].metric("Trust score", trust_score)
    header_cols[2].metric("Risk label", str(label))
    header_cols[3].metric("Followers", f"{int(as_float(profile.get('followers', features.get('followers')))):,}")

    metric_cards(metrics, features)

    st.subheader("Assessment")
    reasons = [
        {
            "signal": "Bot probability",
            "value": as_percent(features.get("bot_probability", metrics.get("bot_probability"))),
            "impact": "high" if as_float(features.get("bot_probability", metrics.get("bot_probability"))) >= 0.7 else "normal",
        },
        {
            "signal": "Suspicious event ratio",
            "value": as_percent(features.get("suspicious_event_ratio")),
            "impact": "high" if as_float(features.get("suspicious_event_ratio")) >= 0.5 else "normal",
        },
        {
            "signal": "Sentiment",
            "value": as_percent(features.get("sentiment_score", metrics.get("sentiment_score"))),
            "impact": "low" if as_float(features.get("sentiment_score", metrics.get("sentiment_score")), 0.5) < 0.35 else "normal",
        },
        {
            "signal": "Profile reputation",
            "value": as_percent(features.get("profile_reputation_score", profile.get("reputation_score"))),
            "impact": "low" if as_float(features.get("profile_reputation_score", profile.get("reputation_score")), 0.5) < 0.4 else "normal",
        },
    ]
    st.dataframe(pd.DataFrame(reasons), use_container_width=True, hide_index=True)

    cols = st.columns([1, 1])
    with cols[0]:
        if not events_df.empty and "timestamp" in events_df.columns:
            event_plot = events_df.copy()
            event_plot["timestamp"] = pd.to_datetime(event_plot["timestamp"], errors="coerce")
            if "event_type" in event_plot.columns:
                event_plot = event_plot.dropna(subset=["timestamp"])
                if not event_plot.empty:
                    grouped = event_plot.groupby([pd.Grouper(key="timestamp", freq="15s"), "event_type"]).size().reset_index(name="events")
                    fig = px.line(grouped, x="timestamp", y="events", color="event_type")
                    fig.update_layout(height=330, margin=dict(l=10, r=10, t=20, b=10))
                    st.plotly_chart(fig, use_container_width=True)
    with cols[1]:
        if not events_df.empty and "is_suspicious" in events_df.columns:
            suspicion = events_df["is_suspicious"].fillna(False).astype(bool).value_counts().rename_axis("is_suspicious").reset_index(name="events")
            fig = px.bar(suspicion, x="is_suspicious", y="events", color="is_suspicious")
            fig.update_layout(height=330, showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Feature Export")
    if features:
        st.dataframe(pd.DataFrame([features]), use_container_width=True, hide_index=True)
    else:
        st.info("No feature export returned for this KOL.")

    st.subheader("KOL Event Export")
    if bundle["export_events"]:
        st.dataframe(dataframe(bundle["export_events"]).head(200), use_container_width=True, hide_index=True)
    else:
        st.info("No JSONL export returned for this KOL.")

    if bundle_errors:
        with st.expander("API errors"):
            for error in bundle_errors[:20]:
                st.code(error)


with st.sidebar:
    st.header("Controls")
    api_base_url = normalize_base_url(
        st.text_input("API base URL", value=DEFAULT_API_BASE_URL, placeholder="http://localhost:8010")
    )
    page = st.radio("Page", ["Monitoring & Logging", "KOL Evaluation"])
    auto_refresh = st.toggle("Auto refresh", value=True)
    refresh_seconds = st.slider("Refresh seconds", 2, 30, 5)
    st.caption(api_base_url)

if page == "Monitoring & Logging":
    monitoring_page(api_base_url, refresh_seconds)
else:
    kol_evaluation_page(api_base_url)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
