from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KolProfile(BaseModel):
    kol_id: str
    name: str
    platform: Literal["youtube", "tiktok", "facebook"]
    category: str
    followers: int
    verified: bool = True
    reputation_score: float = Field(default=0.8, ge=0, le=1)
    risk_profile: Literal["trusted", "watch", "risky"] = "trusted"
    default_mode: Literal["normal", "viral", "bot_attack", "trust_drop"] = "normal"
    avatar_url: str | None = None


class LiveMetrics(BaseModel):
    live_id: str
    kol_id: str
    title: str
    started_at: datetime
    timestamp: datetime
    viewers: int
    likes: int
    shares: int
    comments: int
    purchases: int
    engagement_rate: float
    sentiment_score: float
    bot_probability: float
    suspicious_spike: bool
    trust_signal: Literal["trusted", "watch", "risky"]


class KolEvent(BaseModel):
    event_id: str
    live_id: str
    kol_id: str
    platform: str
    event_type: Literal["view", "like", "comment", "share", "purchase", "follower"]
    timestamp: datetime
    user_id: str
    value: int | float | str
    sentiment_score: float | None = None
    is_suspicious: bool = False
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SimulationConfig(BaseModel):
    mode: Literal["normal", "viral", "bot_attack", "trust_drop"] = "normal"
    speed: float = Field(default=1.0, ge=0.25, le=5.0)
    kol_id: str = "yt_beauty_02"


class ExportBundle(BaseModel):
    profile: KolProfile
    metrics: LiveMetrics
    recent_events: list[KolEvent]
    model_features: dict[str, int | float | str | bool]
