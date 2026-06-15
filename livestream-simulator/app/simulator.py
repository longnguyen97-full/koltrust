from __future__ import annotations

import csv
import hashlib
import random
import sys
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import ExportBundle, KolEvent, KolProfile, LiveMetrics, SimulationConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from koltrust_common.paths import simulator_profiles_path

SIMULATOR_PROFILES_PATH = simulator_profiles_path()


COMMENTS_POSITIVE = [
    "Sản phẩm nhìn ổn quá",
    "Đã mua theo link của bạn",
    "Review rất có tâm",
    "Giá này hợp lý",
    "Nội dung rõ ràng, dễ tin",
]

COMMENTS_NEUTRAL = [
    "Còn size M không?",
    "Ship về Đà Nẵng bao lâu?",
    "Cho xem cận cảnh sản phẩm",
    "Mã giảm giá ở đâu vậy?",
    "Live đến mấy giờ?",
]

COMMENTS_NEGATIVE = [
    "Giá cao hơn lần trước",
    "Sao comment hỏi không trả lời",
    "Cần check lại nguồn hàng",
    "Review hơi nhanh quá",
    "Mình thấy feedback trái chiều",
]

BOT_COMMENTS = [
    "Quá rẻ mua ngay",
    "Link đâu link đâu",
    "Chốt 10 cái",
    "Uy tín 100 phần trăm",
    "Tăng follow tăng tim",
]


FALLBACK_KOL_PROFILES = [
    KolProfile(
        kol_id="yt_beauty_02",
        name="Glow Lab",
        platform="youtube",
        category="beauty-commerce",
        followers=410_000,
        verified=True,
        reputation_score=0.84,
        risk_profile="trusted",
        default_mode="normal",
    ),
    KolProfile(
        kol_id="tt_food_03",
        name="Saigon Food Map",
        platform="tiktok",
        category="food-lifestyle",
        followers=1_200_000,
        verified=True,
        reputation_score=0.82,
        risk_profile="trusted",
        default_mode="viral",
    ),
    KolProfile(
        kol_id="yt_tech_01",
        name="Tech Insight VN",
        platform="youtube",
        category="tech-review",
        followers=820_000,
        verified=True,
        reputation_score=0.88,
        risk_profile="trusted",
        default_mode="viral",
    ),
    KolProfile(
        kol_id="yt_finance_04",
        name="Money Signal",
        platform="youtube",
        category="finance-advice",
        followers=250_000,
        verified=True,
        reputation_score=0.32,
        risk_profile="risky",
        default_mode="bot_attack",
    ),
    KolProfile(
        kol_id="tt_lifestyle_05",
        name="Daily Style",
        platform="tiktok",
        category="lifestyle",
        followers=680_000,
        verified=False,
        reputation_score=0.64,
        risk_profile="watch",
        default_mode="normal",
    ),
]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def risk_profile_from_score(score: float) -> str:
    if score >= 70:
        return "trusted"
    if score >= 45:
        return "watch"
    return "risky"


def default_mode_from_risk(risk_profile: str) -> str:
    if risk_profile == "risky":
        return "bot_attack"
    if risk_profile == "watch":
        return "trust_drop"
    return "normal"


def category_from_platform(platform: str) -> str:
    if platform == "tiktok":
        return "commerce-deals"
    if platform == "youtube":
        return "content-review"
    return "livestream-commerce"


def simulation_profile_from_identity(kol_id: str) -> tuple[float, str, str, bool]:
    bucket = int(hashlib.sha256(kol_id.encode("utf-8")).hexdigest()[:8], 16) % 5
    if bucket == 0:
        return 0.42, "risky", "bot_attack", False
    if bucket == 1:
        return 0.58, "watch", "trust_drop", False
    if bucket == 2:
        return 0.72, "trusted", "viral", True
    return 0.80, "trusted", "normal", True


def read_kol_profiles_from_dataset() -> list[KolProfile]:
    if not SIMULATOR_PROFILES_PATH.exists():
        return []

    profiles: list[KolProfile] = []
    with SIMULATOR_PROFILES_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            platform = str(row.get("platform") or "youtube").lower()
            if platform not in {"youtube", "tiktok", "facebook"}:
                platform = "youtube"
            kol_id = str(row.get("creator_id") or "unknown")
            reputation_score, risk_profile, default_mode, verified = simulation_profile_from_identity(kol_id)
            profiles.append(
                KolProfile(
                    kol_id=kol_id,
                    name=str(row.get("creator_name") or row.get("creator_id") or "Unknown KOL"),
                    platform=platform,
                    category=category_from_platform(platform),
                    followers=int(to_float(row.get("follower_count"))),
                    verified=verified,
                    reputation_score=reputation_score,
                    risk_profile=risk_profile,
                    default_mode=default_mode,
                )
            )
    return profiles


KOL_PROFILES = read_kol_profiles_from_dataset() or FALLBACK_KOL_PROFILES


class LivestreamSession:
    def __init__(self, profile: KolProfile) -> None:
        self.profile = profile
        self.config = SimulationConfig(mode=profile.default_mode, kol_id=profile.kol_id)
        self.live_id = self._new_live_id()
        self.started_at = self._now()
        self.viewers = self._initial_viewers()
        self.likes = random.randint(9000, 26000)
        self.shares = random.randint(500, 2100)
        self.comments = random.randint(2400, 7200)
        self.purchases = random.randint(80, 420)
        self.events: deque[KolEvent] = deque(maxlen=1400)
        self.tick_count = 0

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _new_live_id(self) -> str:
        return f"live_{self.profile.kol_id}_{uuid.uuid4().hex[:8]}"

    def _initial_viewers(self) -> int:
        base = int(self.profile.followers * random.uniform(0.002, 0.006))
        if self.profile.risk_profile == "risky":
            base = int(base * random.uniform(1.4, 2.4))
        return max(420, min(base, 18_000))

    def set_config(self, config: SimulationConfig) -> SimulationConfig:
        self.config = config.model_copy(update={"kol_id": self.profile.kol_id})
        return self.config

    def reset(self) -> None:
        self.live_id = self._new_live_id()
        self.started_at = self._now()
        self.viewers = self._initial_viewers()
        self.likes = random.randint(9000, 26000)
        self.shares = random.randint(500, 2100)
        self.comments = random.randint(2400, 7200)
        self.purchases = random.randint(80, 420)
        self.events.clear()
        self.tick_count = 0

    def tick(self) -> ExportBundle:
        self.tick_count += 1
        mode = self.config.mode
        speed = self.config.speed
        suspicious = self._is_suspicious_tick(mode)

        viewer_delta = self._viewer_delta(mode, speed)
        like_delta = self._scaled_random(12, 48, speed)
        share_delta = self._scaled_random(1, 10, speed)
        comment_count = self._comment_count(mode, speed)
        purchase_delta = self._purchase_delta(mode, speed)

        self.viewers = max(120, self.viewers + viewer_delta)
        self.likes += like_delta
        self.shares += share_delta
        self.comments += comment_count
        self.purchases += purchase_delta

        for _ in range(comment_count):
            self.events.append(self._make_comment_event(suspicious=suspicious))
        for event_type, total in [
            ("view", max(1, abs(viewer_delta))),
            ("like", like_delta),
            ("share", share_delta),
            ("purchase", purchase_delta),
        ]:
            for _ in range(min(total, 12)):
                self.events.append(self._make_numeric_event(event_type, suspicious))

        metrics = self.metrics()
        return ExportBundle(
            profile=self.profile,
            metrics=metrics,
            recent_events=self.recent_events(limit=80),
            model_features=self.model_features(metrics),
        )

    def metrics(self) -> LiveMetrics:
        recent = self.recent_events(limit=180)
        sentiment_values = [
            event.sentiment_score
            for event in recent
            if event.event_type == "comment" and event.sentiment_score is not None
        ]
        suspicious_ratio = sum(1 for event in recent if event.is_suspicious) / max(1, len(recent))
        sentiment = sum(sentiment_values) / max(1, len(sentiment_values))
        engagement_rate = (self.likes + self.comments + self.shares) / max(1, self.profile.followers)

        adjusted_risk = suspicious_ratio + (1 - self.profile.reputation_score) * 0.28
        trust_signal = "trusted"
        if adjusted_risk > 0.35 or sentiment < -0.18:
            trust_signal = "risky"
        elif adjusted_risk > 0.18 or sentiment < 0.05:
            trust_signal = "watch"

        return LiveMetrics(
            live_id=self.live_id,
            kol_id=self.profile.kol_id,
            title=self._title(),
            started_at=self.started_at,
            timestamp=self._now(),
            viewers=self.viewers,
            likes=self.likes,
            shares=self.shares,
            comments=self.comments,
            purchases=self.purchases,
            engagement_rate=round(engagement_rate, 5),
            sentiment_score=round(sentiment, 4),
            bot_probability=round(min(0.98, adjusted_risk * 1.65), 4),
            suspicious_spike=adjusted_risk > 0.28,
            trust_signal=trust_signal,
        )

    def recent_events(self, limit: int = 100) -> list[KolEvent]:
        return list(self.events)[-limit:]

    def model_features(self, metrics: LiveMetrics) -> dict[str, int | float | str | bool]:
        recent = self.recent_events(limit=260)
        comments = [event for event in recent if event.event_type == "comment"]
        suspicious_events = [event for event in recent if event.is_suspicious]
        unique_users = {event.user_id for event in recent}
        comment_sentiments = [event.sentiment_score or 0 for event in comments]

        return {
            "kol_id": self.profile.kol_id,
            "kol_name": self.profile.name,
            "platform": self.profile.platform,
            "category": self.profile.category,
            "followers": self.profile.followers,
            "verified": self.profile.verified,
            "profile_reputation_score": self.profile.reputation_score,
            "profile_risk_label": self.profile.risk_profile,
            "live_id": metrics.live_id,
            "viewer_count": metrics.viewers,
            "like_count": metrics.likes,
            "share_count": metrics.shares,
            "comment_count": metrics.comments,
            "purchase_count": metrics.purchases,
            "engagement_rate": metrics.engagement_rate,
            "sentiment_score": metrics.sentiment_score,
            "bot_probability": metrics.bot_probability,
            "suspicious_event_ratio": round(len(suspicious_events) / max(1, len(recent)), 4),
            "unique_user_ratio": round(len(unique_users) / max(1, len(recent)), 4),
            "avg_comment_sentiment": round(sum(comment_sentiments) / max(1, len(comment_sentiments)), 4),
            "activity_score": round(min(1.0, metrics.viewers / 8000 + metrics.engagement_rate), 4),
            "is_suspicious": metrics.suspicious_spike,
            "trust_label": metrics.trust_signal,
            "timestamp": metrics.timestamp.isoformat(),
        }

    def export_jsonl(self, limit: int = 500) -> str:
        if not self.events:
            self.tick()
        events = self.recent_events(limit=limit)
        return "\n".join(event.model_dump_json() for event in events) + ("\n" if events else "")

    def _title(self) -> str:
        titles = {
            "beauty-commerce": "Livestream review mỹ phẩm và flash sale",
            "tech-review": "Mở hộp thiết bị mới và Q&A trực tiếp",
            "food-lifestyle": "Nấu ăn tại nhà và review dụng cụ bếp",
            "commerce-deals": "Săn deal độc quyền trong phiên live",
        }
        return titles.get(self.profile.category, "KOL livestream realtime")

    def _is_suspicious_tick(self, mode: str) -> bool:
        if mode in {"bot_attack", "trust_drop"}:
            return self.tick_count % 3 != 0
        if self.profile.risk_profile == "risky":
            return random.random() < 0.48
        if self.profile.risk_profile == "watch":
            return random.random() < 0.18
        return random.random() < 0.05

    def _viewer_delta(self, mode: str, speed: float) -> int:
        if mode == "viral":
            return self._scaled_random(45, 180, speed)
        if mode == "bot_attack":
            return self._scaled_random(180, 460, speed)
        if mode == "trust_drop":
            return -self._scaled_random(30, 140, speed)
        return self._scaled_random(-28, 55, speed)

    def _comment_count(self, mode: str, speed: float) -> int:
        if mode == "bot_attack":
            return self._scaled_random(18, 46, speed)
        if mode == "viral":
            return self._scaled_random(10, 28, speed)
        if mode == "trust_drop":
            return self._scaled_random(8, 22, speed)
        if self.profile.risk_profile == "risky":
            return self._scaled_random(9, 24, speed)
        return self._scaled_random(3, 12, speed)

    def _purchase_delta(self, mode: str, speed: float) -> int:
        if mode == "trust_drop":
            return self._scaled_random(0, 2, speed)
        if mode == "viral":
            return self._scaled_random(2, 8, speed)
        return self._scaled_random(0, 5, speed)

    def _scaled_random(self, low: int, high: int, speed: float) -> int:
        value = random.randint(low, high)
        return int(value * speed)

    def _make_numeric_event(self, event_type: str, suspicious: bool) -> KolEvent:
        return KolEvent(
            event_id=uuid.uuid4().hex,
            live_id=self.live_id,
            kol_id=self.profile.kol_id,
            platform=self.profile.platform,
            event_type=event_type,
            timestamp=self._now(),
            user_id=self._user_id(suspicious),
            value=1,
            is_suspicious=suspicious and random.random() < self._bot_event_probability(),
            metadata={
                "source": "simulator",
                "mode": self.config.mode,
                "profile_risk": self.profile.risk_profile,
            },
        )

    def _make_comment_event(self, suspicious: bool) -> KolEvent:
        bot_probability = self._bot_event_probability()
        if suspicious and random.random() < bot_probability:
            text = random.choice(BOT_COMMENTS)
            sentiment = random.uniform(0.12, 0.55)
            is_suspicious = True
        elif self.config.mode == "trust_drop" or (
            self.profile.risk_profile == "risky" and random.random() < 0.36
        ):
            text = random.choice(COMMENTS_NEGATIVE)
            sentiment = random.uniform(-0.75, -0.2)
            is_suspicious = random.random() < 0.32
        else:
            pool = COMMENTS_POSITIVE + COMMENTS_NEUTRAL + COMMENTS_NEGATIVE
            text = random.choice(pool)
            if text in COMMENTS_POSITIVE:
                sentiment = random.uniform(0.25, 0.85)
            elif text in COMMENTS_NEGATIVE:
                sentiment = random.uniform(-0.65, -0.1)
            else:
                sentiment = random.uniform(-0.08, 0.25)
            is_suspicious = random.random() < (0.12 if self.profile.risk_profile == "watch" else 0.05)

        return KolEvent(
            event_id=uuid.uuid4().hex,
            live_id=self.live_id,
            kol_id=self.profile.kol_id,
            platform=self.profile.platform,
            event_type="comment",
            timestamp=self._now(),
            user_id=self._user_id(is_suspicious),
            value=text,
            sentiment_score=round(sentiment, 4),
            is_suspicious=is_suspicious,
            metadata={
                "language": "vi",
                "mode": self.config.mode,
                "profile_risk": self.profile.risk_profile,
            },
        )

    def _bot_event_probability(self) -> float:
        if self.profile.risk_profile == "risky":
            return 0.76
        if self.profile.risk_profile == "watch":
            return 0.38
        return 0.18

    def _user_id(self, suspicious: bool) -> str:
        if suspicious:
            return f"bot_{self.profile.kol_id}_{random.randint(1, 42):03d}"
        return f"user_{random.randint(1000, 99999)}"


class LivestreamSimulator:
    def __init__(self) -> None:
        self.sessions = {profile.kol_id: LivestreamSession(profile) for profile in KOL_PROFILES}
        self.default_kol_id = KOL_PROFILES[0].kol_id

    @property
    def profile(self) -> KolProfile:
        return self.session(self.default_kol_id).profile

    def list_profiles(self) -> list[KolProfile]:
        return [session.profile for session in self.sessions.values()]

    def session(self, kol_id: str) -> LivestreamSession:
        if kol_id not in self.sessions:
            raise KeyError(kol_id)
        return self.sessions[kol_id]

    def set_config(self, config: SimulationConfig) -> SimulationConfig:
        return self.session(config.kol_id).set_config(config)

    def reset(self, kol_id: str | None = None) -> None:
        self.session(kol_id or self.default_kol_id).reset()

    def tick(self, kol_id: str | None = None) -> ExportBundle:
        return self.session(kol_id or self.default_kol_id).tick()

    def metrics(self, kol_id: str | None = None) -> LiveMetrics:
        return self.session(kol_id or self.default_kol_id).metrics()

    def recent_events(self, kol_id: str | None = None, limit: int = 100) -> list[KolEvent]:
        return self.session(kol_id or self.default_kol_id).recent_events(limit=limit)

    def model_features(self, kol_id: str | None = None) -> dict[str, int | float | str | bool]:
        session = self.session(kol_id or self.default_kol_id)
        return session.model_features(session.metrics())

    def export_jsonl(self, kol_id: str | None = None, limit: int = 500) -> str:
        return self.session(kol_id or self.default_kol_id).export_jsonl(limit=limit)
