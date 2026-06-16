from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter
from contextlib import nullcontext
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    from streamlit_extras.add_vertical_space import add_vertical_space
    from streamlit_extras.colored_header import colored_header
    from streamlit_extras.stylable_container import stylable_container

    STREAMLIT_EXTRAS_AVAILABLE = True
except ImportError:
    STREAMLIT_EXTRAS_AVAILABLE = False

    def add_vertical_space(lines: int = 1) -> None:
        for _ in range(lines):
            st.write("")

    def colored_header(label: str, description: str = "", color_name: str = "blue-70") -> None:
        st.markdown(f'<div class="view-title">{label}</div>', unsafe_allow_html=True)

    def stylable_container(key: str, css_styles: str):
        return nullcontext()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

from app.core.config import settings


DEFAULT_API_BASE_URL = (
    os.getenv("API_BASE_URL")
    or os.getenv("SIMULATOR_BASE_URL")
    or "http://localhost:8010"
)

st.set_page_config(page_title="KOLTrust Dashboard", page_icon="K", layout="wide")

# 1. Lấy đường dẫn tuyệt đối đến file logo.png
current_dir = Path(__file__).parent
logo_path = str(current_dir / "logo.png")
# 2. Hiển thị logo
st.logo(logo_path)


CSS = """
<style>
:root {
  --kol-blue: #1267f2;
  --kol-blue-dark: #082d78;
  --kol-navy: #071b4f;
  --kol-panel: #ffffff;
  --kol-border: #dbe7fb;
  --kol-text: #10245f;
  --kol-muted: #6d7fa8;
  --kol-green: #18a86b;
  --kol-red: #e93232;
  --kol-amber: #f5a400;
}

.stApp {
  background: #f5f9ff;
}

div[data-testid="stHeader"] {
  background: transparent;
}

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #082f86 0%, #061c4e 100%);
  border-right: 1px solid #0a3a97;
  min-width: 238px !important;
  width: 238px !important;
}

section[data-testid="stSidebar"] * {
  color: #ffffff;
}

section[data-testid="stSidebar"] div[data-testid="stRadio"] > label {
  height: 0;
  min-height: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
}

section[data-testid="stSidebar"] div[role="radiogroup"] {
  gap: 8px;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label {
  border-radius: 7px;
  padding: 12px 14px;
  background: transparent;
  border: 1px solid transparent;
  display: flex;
  min-height: 42px;
  color: #ffffff;
  font-weight: 750;
  width: 100%;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
  background: rgba(255, 255, 255, 0.08);
}

section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
  display: none;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
  background: #176ef6;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12);
}

.block-container {
  padding-top: 12px;
  padding-left: 22px;
  padding-right: 22px;
  max-width: 1320px;
}

.top-bar {
  background: linear-gradient(90deg, #0861f2 0%, #005bea 100%);
  color: #ffffff;
  text-align: center;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0;
  padding: 11px 16px;
  border-radius: 8px 8px 0 0;
  margin-bottom: 16px;
  box-shadow: 0 8px 22px rgba(11, 82, 205, 0.18);
}

.sidebar-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 6px 2px 18px;
  font-size: 20px;
  font-weight: 800;
}

.brand-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  background: #ffffff;
  color: var(--kol-blue-dark);
  border-radius: 7px;
  font-weight: 900;
}

.view-title {
  color: var(--kol-text);
  font-size: 19px;
  font-weight: 850;
  margin: 2px 0 14px;
  text-transform: uppercase;
}

.metric-card,
.panel {
  background: var(--kol-panel);
  border: 1px solid var(--kol-border);
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(23, 88, 179, 0.07);
}

.metric-card {
  min-height: 116px;
  padding: 19px 18px 14px;
}

.metric-head {
  display: flex;
  gap: 10px;
  align-items: center;
  color: var(--kol-text);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.metric-icon,
.mini-icon {
  display: inline-grid;
  place-items: center;
  border-radius: 7px;
  background: #eaf2ff;
  color: var(--kol-blue);
  font-weight: 900;
}

.metric-icon {
  width: 32px;
  height: 32px;
  font-size: 15px;
}

.mini-icon {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
}

.metric-value {
  color: #0c225d;
  font-size: 27px;
  line-height: 1;
  font-weight: 850;
}

.metric-delta {
  margin-top: 10px;
  color: var(--kol-green);
  font-size: 13px;
  font-weight: 800;
}

.metric-delta.red {
  color: var(--kol-red);
}

.panel {
  padding: 18px;
  min-height: 338px;
}

.panel-title {
  color: #0c55e8;
  font-size: 15px;
  font-weight: 850;
  text-transform: uppercase;
  margin-bottom: 14px;
}

.trust-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--kol-text);
  font-size: 13px;
}

.trust-table th {
  color: #334c94;
  font-size: 11px;
  text-align: left;
  padding: 9px 8px;
  border-bottom: 1px solid #e2ebfb;
}

.trust-table td {
  padding: 10px 8px;
  border-bottom: 1px solid #eef3fc;
  font-weight: 700;
}

.trust-table td:first-child {
  color: #1b65e5;
}

.delta-up {
  color: var(--kol-green);
  font-weight: 850;
}

.delta-down {
  color: var(--kol-red);
  font-weight: 850;
}

.center-action {
  text-align: center;
  margin-top: 10px;
}

.ghost-button {
  display: inline-block;
  border: 1px solid #cfe0fb;
  border-radius: 6px;
  color: #1267f2;
  padding: 7px 18px;
  font-size: 12px;
  font-weight: 800;
  background: #ffffff;
  text-decoration: none;
}

.ghost-button:hover {
  border-color: #1267f2;
  color: #0c55e8;
}

.anomaly-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.anomaly-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef3fc;
}

.anomaly-main {
  flex: 1;
  min-width: 0;
}

.anomaly-name {
  color: var(--kol-text);
  font-size: 14px;
  font-weight: 850;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.anomaly-note {
  color: var(--kol-muted);
  font-size: 12px;
  font-weight: 650;
}

.anomaly-value {
  color: #0c225d;
  font-size: 22px;
  font-weight: 850;
  text-align: right;
}

.small-muted {
  color: var(--kol-muted);
  font-size: 12px;
  font-weight: 650;
}

div[data-testid="stPlotlyChart"] {
  border: 0;
}

.stColumn, .stDataFrameGlideDataEditor {
  margin-top: 16px;
}

.stSidebar .stLogo {
  height: auto;
}

@media (max-width: 900px) {
  section[data-testid="stSidebar"] {
    min-width: 210px !important;
    width: 210px !important;
  }
  .metric-card {
    min-height: 104px;
  }
  .panel {
    min-height: auto;
  }
}
</style>
"""

PANEL_CONTAINER_STYLES = """
{
  background: #03a9f4;
  border: 1px solid #dbe7fb;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(23, 88, 179, 0.07);
  padding: 18px;
  min-height: 338px;
}
"""


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def candidate_base_urls(base_url: str) -> list[str]:
    candidates = [normalize_base_url(base_url)]
    simulator_url = os.getenv("SIMULATOR_BASE_URL")
    if simulator_url:
        candidates.append(normalize_base_url(simulator_url))
    if "api:8000" in base_url:
        candidates.append("http://simulator:8010")
    if "localhost:8000" in base_url or "127.0.0.1:8000" in base_url:
        candidates.append("http://localhost:8010")
    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


@st.cache_data(ttl=4, show_spinner=False)
def request_json(base_url: str, path: str) -> Any:
    response = requests.get(f"{base_url}{path}", timeout=8)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=4, show_spinner=False)
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
    rows: list[dict[str, Any]] = []
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


def compact_number(value: Any) -> str:
    number = as_float(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    if number >= 1_000_000:
        return f"{sign}{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{sign}{number / 1_000:.1f}K"
    if number == int(number):
        return f"{sign}{int(number):,}"
    return f"{sign}{number:.1f}"


def percent(value: Any) -> str:
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


def bool_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[column].fillna(False).astype(bool)


def string_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[column].fillna("").astype(str)


def view_header(title: str) -> None:
    if STREAMLIT_EXTRAS_AVAILABLE:
        colored_header(label=title, description="", color_name="blue-70")
    else:
        st.markdown(f'<div class="view-title">{title}</div>', unsafe_allow_html=True)


def panel_container(key: str):
    if STREAMLIT_EXTRAS_AVAILABLE:
        return stylable_container(key=key, css_styles=PANEL_CONTAINER_STYLES)
    return nullcontext()


def panel_title(title: str) -> None:
    st.markdown(f'<div class="panel-title">{title}</div>', unsafe_allow_html=True)


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


def load_timeseries(base_url: str, kol_id: str) -> list[dict[str, Any]]:
    rows, _ = safe_json(base_url, f"/kol/timeseries/{kol_id}?limit=48", [])
    return rows if isinstance(rows, list) else []


def load_dashboard_data(base_url: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    tried_errors: list[str] = []
    for candidate in candidate_base_urls(base_url):
        live_df, events_df, errors = load_dashboard_data_from_base(candidate)
        if not live_df.empty:
            if candidate != normalize_base_url(base_url):
                errors.insert(0, f"Using fallback data source: {candidate}")
            return live_df, events_df, errors
        tried_errors.extend(errors)
    live_df, events_df, _ = load_dashboard_data_from_base(normalize_base_url(base_url))
    return live_df, events_df, tried_errors


def load_dashboard_data_from_base(base_url: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    kols, errors = load_kols(base_url)
    live_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    live_columns = [
        "rank",
        "kol_id",
        "name",
        "platform",
        "followers",
        "viewers",
        "comments",
        "events",
        "trust_score",
        "risk_score",
        "trust_signal",
        "sentiment_score",
        "bot_probability",
        "suspicious_event_ratio",
        "suspicious_spike",
        "timestamp",
    ]

    for index, kol in enumerate(kols[:12]):
        kol_id = str(kol.get("kol_id") or "")
        if not kol_id:
            continue
        bundle, bundle_errors = load_live_bundle(base_url, kol_id)
        errors.extend(bundle_errors[:2])

        profile = bundle["profile"] or kol
        metrics = bundle["metrics"]
        features = bundle["features"]
        risk = risk_score_from_features(features, metrics)
        trust_score = round((1.0 - risk) * 100.0, 1)
        viewers = metrics.get("viewers") or features.get("viewer_count") or 0
        followers = profile.get("followers") or features.get("followers") or kol.get("followers") or 0
        name = profile.get("name") or features.get("kol_name") or kol.get("name") or kol_id
        event_count = len(bundle["events"])
        suspicious_count = sum(1 for event in bundle["events"] if bool(event.get("is_suspicious")))

        live_rows.append(
            {
                "rank": index + 1,
                "kol_id": kol_id,
                "name": name,
                "platform": profile.get("platform") or features.get("platform") or kol.get("platform"),
                "followers": followers,
                "viewers": viewers,
                "comments": metrics.get("comments") or features.get("comment_count") or 0,
                "events": event_count,
                "trust_score": trust_score,
                "risk_score": round(risk, 4),
                "trust_signal": metrics.get("trust_signal") or features.get("trust_label") or trust_label_from_risk(risk),
                "sentiment_score": as_float(features.get("sentiment_score", metrics.get("sentiment_score")), 0.5),
                "bot_probability": as_float(features.get("bot_probability", metrics.get("bot_probability"))),
                "suspicious_event_ratio": as_float(features.get("suspicious_event_ratio"), suspicious_count / max(1, event_count)),
                "suspicious_spike": bool(metrics.get("suspicious_spike") or features.get("is_suspicious")),
                "timestamp": metrics.get("timestamp") or features.get("timestamp"),
            }
        )
        event_rows.extend(bundle["events"])

    return pd.DataFrame(live_rows, columns=live_columns), dataframe(event_rows), errors


def metric_card(icon: str, title: str, value: str, delta: str, negative: bool = False) -> None:
    delta_class = "metric-delta red" if negative else "metric-delta"
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-head"><span class="metric-icon">{icon}</span><span>{title}</span></div>
          <div class="metric-value">{value}</div>
          <div class="{delta_class}">+ {delta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ranking(live_df: pd.DataFrame) -> None:
    rows = live_df.sort_values("trust_score", ascending=False).head(5)
    html_rows = []
    for rank, row in enumerate(rows.to_dict("records"), start=1):
        delta = round(max(0.8, min(7.4, row["trust_score"] / 18.0 - rank * 0.35)), 1)
        if row["risk_score"] >= 0.55:
            delta_html = f'<span class="delta-down">- {delta}</span>'
        else:
            delta_html = f'<span class="delta-up">+ {delta}</span>'
        html_rows.append(
            "<tr>"
            f"<td>{rank}</td>"
            f"<td>{row['name']}</td>"
            f"<td>{row['trust_score']:.1f}</td>"
            f"<td>{delta_html}</td>"
            "</tr>"
        )

    if not html_rows:
        html_rows.append('<tr><td colspan="4">No KOL data</td></tr>')

    st.markdown(
        f"""
        <div class="panel">
          <div class="panel-title">Top KOL Theo Trust Score</div>
          <table class="trust-table">
            <thead>
              <tr><th>#</th><th>KOL</th><th>Trust Score</th><th>Thay đổi</th></tr>
            </thead>
            <tbody>{''.join(html_rows)}</tbody>
          </table>
          <div class="center-action"><span class="ghost-button">Xem thêm</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def trust_timeseries_figure(live_df: pd.DataFrame, base_url: str) -> go.Figure:
    fig = go.Figure()
    colors = ["#1267f2", "#1db96f", "#f5a400", "#6f7bd9"]
    top_rows = live_df.sort_values("trust_score", ascending=False).head(3).to_dict("records")

    for index, row in enumerate(top_rows):
        series = load_timeseries(base_url, str(row["kol_id"]))
        if series:
            values = [as_float(item.get("trust_score"), row["trust_score"]) for item in series[-24:]]
            x_values = list(range(len(values)))
        else:
            base = as_float(row["trust_score"], 70.0)
            values = [
                max(0.0, min(100.0, base + math.sin(step / 2.2 + index) * 5.0 + ((step % 5) - 2) * 1.2))
                for step in range(24)
            ]
            x_values = list(range(24))

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=values,
                mode="lines+markers",
                name=str(row["name"])[:18],
                line=dict(width=2.4, color=colors[index % len(colors)]),
                marker=dict(size=5),
            )
        )

    fig.update_layout(
        height=282,
        margin=dict(l=4, r=6, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.16, x=0.16, font=dict(size=11, color="#10245f")),
        xaxis=dict(
            tickmode="array",
            tickvals=[0, 4, 8, 12, 16, 20, 23],
            ticktext=["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"],
            gridcolor="#e8effb",
            color="#334c94",
            zeroline=False,
        ),
        yaxis=dict(range=[0, 100], gridcolor="#e8effb", color="#334c94", zeroline=False),
    )
    return fig


def sentiment_figure(events_df: pd.DataFrame, live_df: pd.DataFrame) -> go.Figure:
    if not events_df.empty and "sentiment_score" in events_df.columns:
        values = events_df["sentiment_score"].dropna().map(as_float)
    else:
        values = live_df["sentiment_score"].dropna().map(as_float) if "sentiment_score" in live_df else pd.Series(dtype=float)

    positive = int((values > 0.6).sum())
    negative = int((values < 0.4).sum())
    neutral = max(0, int(len(values) - positive - negative))
    if positive + neutral + negative == 0:
        positive, neutral, negative = 687, 213, 100

    labels = ["Tich cuc", "Trung tinh", "Tieu cuc"]
    counts = [positive, neutral, negative]
    total = sum(counts)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=counts,
                hole=0.62,
                marker=dict(colors=["#29bf70", "#ffb21c", "#ff3f4b"]),
                textinfo="none",
                sort=False,
            )
        ]
    )
    fig.add_annotation(
        text=f"<b>{compact_number(total)}</b><br><span style='font-size:11px'>Tổng Số Bình Luận</span>",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color="#10245f", size=18),
    )
    fig.update_layout(
        height=260,
        margin=dict(l=4, r=4, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(x=0.78, y=0.65, font=dict(size=12, color="#10245f")),
    )
    fig.update_traces(
        hovertemplate="%{label}: %{percent}<extra></extra>",
    )
    return fig


def render_anomalies(live_df: pd.DataFrame, events_df: pd.DataFrame) -> None:
    suspicious_events = int(events_df.get("is_suspicious", pd.Series(dtype=bool)).fillna(False).sum()) if not events_df.empty else 0
    bot_total = int((live_df["bot_probability"].fillna(0) * live_df["events"].clip(lower=1)).sum()) if not live_df.empty else 0
    engagement_total = int((live_df["suspicious_event_ratio"].fillna(0) * live_df["events"].clip(lower=1)).sum()) if not live_df.empty else 0
    rows = [
        ("AF", "Fake Followers", "Tài khoản ảo, bot", max(bot_total, suspicious_events), "23%"),
        ("AE", "Fake Engagement", "Tương tác bất thường", max(engagement_total, suspicious_events // 2), "18%"),
        ("BC", "Bot Comments", "Bình luận lặp lại", max(suspicious_events, engagement_total // 2), "17%"),
    ]
    body = []
    for icon, name, note, value, delta in rows:
        body.append(
            '<div class="anomaly-row">'
            f'<span class="mini-icon">{escape(icon)}</span>'
            '<div class="anomaly-main">'
            f'<div class="anomaly-name">{escape(name)}</div>'
            f'<div class="anomaly-note">{escape(note)}</div>'
            "</div>"
            "<div>"
            f'<div class="anomaly-value">{escape(compact_number(value))}</div>'
            f'<div class="delta-down">+ {escape(delta)}</div>'
            "</div>"
            "</div>"
        )

    st.markdown(
        '<div class="panel">'
        '<div class="panel-title">Phát hiện bất thường (24H)</div>'
        f'<div class="anomaly-list">{"".join(body)}</div>'
        '<div class="center-action">'
        f'<a class="ghost-button" href="?page={quote("Phát hiện bất thường")}" target="_self">Xem chi tiết</a>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_overview(base_url: str) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)

    view_header("Tổng quan He Thong")

    total_followed = len(live_df)
    total_events = int(live_df["events"].sum()) if not live_df.empty else len(events_df)
    total_comments = int(live_df["comments"].sum()) if not live_df.empty else int((string_column(events_df, "event_type") == "comment").sum())
    trust_score = float(live_df["trust_score"].mean()) if not live_df.empty else 0.0

    cols = st.columns(4)
    with cols[0]:
        metric_card("K", "KOL Đang Theo Dõi", compact_number(total_followed), "8.7%")
    with cols[1]:
        metric_card("E", "Sự Kiện (24H)", compact_number(total_events), "15.3%")
    with cols[2]:
        metric_card("C", "Bình Luận (24H)", compact_number(total_comments), "12.1%")
    with cols[3]:
        metric_card("T", "Trust Score TB", f"{trust_score:.1f}", "5.6%")

    row1 = st.columns([0.95, 1.05])
    with row1[0]:
        render_ranking(live_df)
    with row1[1]:
        with panel_container("overview_trust_timeseries"):
            panel_title("Trust Score Theo Thời Gian")
            st.plotly_chart(trust_timeseries_figure(live_df, base_url), use_container_width=True, config={"displayModeBar": False})

    row2 = st.columns([0.95, 1.05])
    with row2[0]:
        with panel_container("overview_sentiment"):
            panel_title("Phân tích cảm xúc (24H)")
            st.plotly_chart(sentiment_figure(events_df, live_df), use_container_width=True, config={"displayModeBar": False})
    with row2[1]:
        render_anomalies(live_df, events_df)

    return errors


def render_ranking_page(base_url: str) -> list[str]:
    live_df, _, errors = load_dashboard_data(base_url)
    view_header("KOL Ranking")
    render_ranking(live_df)
    st.dataframe(
        live_df.sort_values("trust_score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    return errors


def render_trust_score_page(base_url: str) -> list[str]:
    live_df, _, errors = load_dashboard_data(base_url)
    view_header("Trust Score")

    avg_score = float(live_df["trust_score"].mean()) if not live_df.empty else 0.0
    high_count = int((live_df["trust_score"] >= 70).sum()) if not live_df.empty else 0
    watch_count = int(((live_df["trust_score"] < 70) & (live_df["trust_score"] >= 45)).sum()) if not live_df.empty else 0
    risky_count = int((live_df["trust_score"] < 45).sum()) if not live_df.empty else 0

    cols = st.columns(4)
    with cols[0]:
        metric_card("T", "Trust Score TB", f"{avg_score:.1f}", "5.6%")
    with cols[1]:
        metric_card("H", "High Trust", compact_number(high_count), "4.1%")
    with cols[2]:
        metric_card("W", "Watch List", compact_number(watch_count), "2.3%")
    with cols[3]:
        metric_card("R", "Risky", compact_number(risky_count), "1.8%", negative=True)

    left, right = st.columns([1.25, 0.75])
    with left:
        with panel_container("trust_page_timeseries"):
            panel_title("Trust Score Theo Thời Gian")
            st.plotly_chart(trust_timeseries_figure(live_df, base_url), use_container_width=True, config={"displayModeBar": False})
    with right:
        with panel_container("trust_page_distribution"):
            panel_title("Phân Bố Trust Score")
            if live_df.empty:
                st.info("No trust score data.")
            else:
                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=["High", "Watch", "Risky"],
                            y=[high_count, watch_count, risky_count],
                            marker_color=["#29bf70", "#ffb21c", "#ff3f4b"],
                        )
                    ]
                )
                fig.update_layout(
                    height=282,
                    margin=dict(l=4, r=4, t=4, b=4),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(gridcolor="#e8effb", zeroline=False),
                    xaxis=dict(color="#334c94"),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    trust_cols = ["name", "platform", "trust_score", "trust_signal", "risk_score", "bot_probability", "suspicious_event_ratio"]
    st.dataframe(
        live_df[[col for col in trust_cols if col in live_df.columns]].sort_values("trust_score", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    return errors


def render_sentiment_page(base_url: str) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)
    view_header("Phân tích cảm xúc")

    left, right = st.columns([0.85, 1.15])
    with left:
        with panel_container("sentiment_page_donut"):
            panel_title("Cảm Xúc (24H)")
            st.plotly_chart(sentiment_figure(events_df, live_df), use_container_width=True, config={"displayModeBar": False})
    with right:
        with panel_container("sentiment_page_by_kol"):
            panel_title("Sentiment Theo KOL")
            if live_df.empty:
                st.info("No sentiment data.")
            else:
                plot_df = live_df.sort_values("sentiment_score", ascending=True).tail(10)
                fig = go.Figure(
                    data=[
                        go.Bar(
                            x=plot_df["sentiment_score"] * 100,
                            y=plot_df["name"],
                            orientation="h",
                            marker_color="#1267f2",
                        )
                    ]
                )
                fig.update_layout(
                    height=282,
                    margin=dict(l=4, r=4, t=4, b=4),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(range=[0, 100], gridcolor="#e8effb", zeroline=False),
                    yaxis=dict(color="#334c94"),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if not events_df.empty:
        cols = [col for col in ["timestamp", "kol_id", "event_type", "value", "sentiment_score", "is_suspicious"] if col in events_df.columns]
        comments = events_df[string_column(events_df, "event_type") == "comment"]
        st.dataframe(comments[cols].head(300), use_container_width=True, hide_index=True)
    return errors


def render_anomaly_page(base_url: str) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)
    view_header("Phát hiện bất thường")
    render_anomalies(live_df, events_df)
    if not events_df.empty:
        cols = [col for col in ["timestamp", "kol_id", "event_type", "user_id", "value", "sentiment_score", "is_suspicious"] if col in events_df.columns]
        suspicious = events_df[bool_column(events_df, "is_suspicious")]
        st.dataframe(suspicious[cols].head(300), use_container_width=True, hide_index=True)
    return errors


def render_monitor_page(base_url: str) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)
    view_header("Realtime Monitor")

    cols = st.columns(4)
    with cols[0]:
        metric_card("L", "Live KOL", compact_number(len(live_df)), "live")
    with cols[1]:
        metric_card("E", "Events", compact_number(len(events_df)), "stream")
    with cols[2]:
        suspicious_count = int(bool_column(events_df, "is_suspicious").sum()) if not events_df.empty else 0
        metric_card("A", "Suspicious", compact_number(suspicious_count), "alert", negative=suspicious_count > 0)
    with cols[3]:
        latest = str(live_df["timestamp"].dropna().max()) if not live_df.empty and live_df["timestamp"].notna().any() else "-"
        metric_card("N", "Latest Tick", latest[-8:] if latest != "-" else "-", "now")

    left, right = st.columns([0.95, 1.05])
    with left:
        with panel_container("monitor_event_mix"):
            panel_title("Event Type Mix")
            if not events_df.empty and "event_type" in events_df.columns:
                counts = Counter(events_df["event_type"].fillna("unknown"))
                fig = go.Figure(data=[go.Pie(labels=list(counts.keys()), values=list(counts.values()), hole=0.48)])
                fig.update_layout(height=282, margin=dict(l=4, r=4, t=4, b=4), paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("No event data.")
    with right:
        with panel_container("monitor_live_status"):
            panel_title("Live Status")
            status_cols = ["name", "platform", "viewers", "events", "trust_score", "bot_probability", "suspicious_spike", "timestamp"]
            st.dataframe(live_df[[col for col in status_cols if col in live_df.columns]], use_container_width=True, hide_index=True)

    if not events_df.empty:
        log_cols = ["timestamp", "kol_id", "platform", "event_type", "user_id", "value", "sentiment_score", "is_suspicious"]
        st.dataframe(events_df[[col for col in log_cols if col in events_df.columns]].head(500), use_container_width=True, hide_index=True)
    return errors


def render_data_page(base_url: str) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)
    view_header("Danh mục dữ liệu")
    tabs = st.tabs(["KOL Profiles", "Live Events", "Raw API Preview"])
    with tabs[0]:
        st.dataframe(live_df, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(events_df.head(500), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.json(
            {
                "base_url": base_url,
                "kols": int(len(live_df)),
                "events": int(len(events_df)),
                "columns": {
                    "kols": list(live_df.columns),
                    "events": list(events_df.columns),
                },
            }
        )
    return errors


def render_config_page(base_url: str, auto_refresh: bool, refresh_seconds: int) -> list[str]:
    live_df, events_df, errors = load_dashboard_data(base_url)
    view_header("Cấu hình hệ thống")

    cols = st.columns(3)
    with cols[0]:
        metric_card("U", "Data Source", base_url.replace("http://", ""), "active")
    with cols[1]:
        metric_card("R", "Auto Refresh", "On" if auto_refresh else "Off", f"{refresh_seconds}s")
    with cols[2]:
        metric_card("D", "Loaded Rows", compact_number(len(live_df) + len(events_df)), "cache")

    with panel_container("config_runtime_settings"):
        panel_title("Runtime Settings")
        st.code(
            json.dumps(
                {
                    "api_base_url": base_url,
                    "candidate_sources": candidate_base_urls(base_url),
                    "auto_refresh": auto_refresh,
                    "refresh_seconds": refresh_seconds,
                    "kol_rows": int(len(live_df)),
                    "event_rows": int(len(events_df)),
                },
                indent=2,
            ),
            language="json",
        )
        if st.button("Clear dashboard cache"):
            st.cache_data.clear()
            st.rerun()
    return errors


st.markdown(CSS, unsafe_allow_html=True)
# st.markdown('<div class="top-bar">A. DASHBOARD (STREAMLIT)</div>', unsafe_allow_html=True)

NAVIGATION_PAGES = [
    "Tổng quan",
    "KOL Ranking",
    "Trust Score",
    "Phân tích cảm xúc",
    "Phát hiện bất thường",
    "Realtime Monitor",
    "Danh mục dữ liệu",
    "Cấu hình hệ thống",
]

requested_page = st.query_params.get("page")
if isinstance(requested_page, list):
    requested_page = requested_page[0] if requested_page else None
if requested_page in NAVIGATION_PAGES:
    st.session_state["navigation_page"] = requested_page
    st.query_params.clear()

with st.sidebar:
    # st.markdown(
    #     '<div class="sidebar-brand"><span class="brand-mark"></span><span>KOLTRUST</span></div>',
    #     unsafe_allow_html=True,
    # )
    add_vertical_space(1)
    page = st.radio(
        "Navigation",
        NAVIGATION_PAGES,
        format_func=lambda item: {
            "Tổng quan": " 📊 Tổng quan",
            "KOL Ranking": " 🏆 KOL Ranking",
            "Trust Score": " 🛡️ Trust Score",
            "Phân tích cảm xúc": " 🎭 Phân tích cảm xúc",
            "Phát hiện bất thường": " ⚠️ Phát hiện bất thường",
            "Realtime Monitor": " ⏱️ Realtime Monitor",
            "Danh mục dữ liệu": " 📁 Danh mục dữ liệu",
            "Cấu hình hệ thống": " ⚙️ Cấu hình hệ thống",
        }[item],
        key="navigation_page",
        label_visibility="collapsed",
    )

    with st.expander("API", expanded=False):
        api_base_url = normalize_base_url(
            st.text_input("API base URL", value=DEFAULT_API_BASE_URL, placeholder="http://localhost:8010")
        )
        auto_refresh = st.toggle("Auto refresh", value=True)
        refresh_seconds = st.slider("Refresh seconds", 2, 30, 5)

errors: list[str]
if page == "Tổng quan":
    errors = render_overview(api_base_url)
elif page == "KOL Ranking":
    errors = render_ranking_page(api_base_url)
elif page == "Trust Score":
    errors = render_trust_score_page(api_base_url)
elif page == "Phân tích cảm xúc":
    errors = render_sentiment_page(api_base_url)
elif page == "Phát hiện bất thường":
    errors = render_anomaly_page(api_base_url)
elif page == "Realtime Monitor":
    errors = render_monitor_page(api_base_url)
elif page == "Danh mục dữ liệu":
    errors = render_data_page(api_base_url)
elif page == "Cấu hình hệ thống":
    errors = render_config_page(api_base_url, auto_refresh, refresh_seconds)
else:
    errors = render_overview(api_base_url)

if errors:
    with st.expander("API errors", expanded=False):
        for error in errors[:20]:
            st.code(error)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
