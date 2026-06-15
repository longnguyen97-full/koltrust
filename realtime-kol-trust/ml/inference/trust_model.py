from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


POSITIVE_WORDS = {
    "good",
    "great",
    "love",
    "excellent",
    "amazing",
    "trust",
    "trusted",
    "hay",
    "tot",
    "uy tin",
    "thich",
    "chat luong",
}

NEGATIVE_WORDS = {
    "bad",
    "fake",
    "spam",
    "scam",
    "hate",
    "poor",
    "bot",
    "lua dao",
    "te",
    "kem",
    "ao",
}

SENTIMENT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "sentiment" / "comment_sentiment.joblib"
TRUST_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "trust_score" / "kol_trust_model.joblib"
DEFAULT_LABEL_TO_SCORE = {
    "negative": 0.15,
    "neutral": 0.50,
    "positive": 0.85,
}
TRUST_NUMERIC_FEATURES = [
    "follower_count",
    "content_count",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "engagement_rate",
    "likes_per_view",
    "comments_per_view",
    "shares_per_view",
    "sentiment_score",
    "positive_comment_count",
    "neutral_comment_count",
    "negative_comment_count",
    "upload_frequency",
    "follower_growth_rate",
    "activity_score",
    "is_suspicious",
]
TRUST_CATEGORICAL_FEATURES = ["platform"]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def normalize_unit_score(value: Any, default: float = 0.5) -> float:
    score = to_float(value, default)
    if score > 1.0:
        return clamp(score / 100.0)
    return clamp(score)


@lru_cache(maxsize=1)
def load_sentiment_model() -> dict[str, Any] | None:
    if not SENTIMENT_MODEL_PATH.exists():
        return None
    try:
        return joblib.load(SENTIMENT_MODEL_PATH)
    except Exception:
        return None


@lru_cache(maxsize=1)
def load_trust_model() -> dict[str, Any] | None:
    if not TRUST_MODEL_PATH.exists():
        return None
    try:
        return joblib.load(TRUST_MODEL_PATH)
    except Exception:
        return None


def rule_based_sentiment_score(text: str | None) -> float:
    if not text:
        return 0.5
    normalized = re.sub(r"\s+", " ", text.lower())
    pos = sum(1 for word in POSITIVE_WORDS if word in normalized)
    neg = sum(1 for word in NEGATIVE_WORDS if word in normalized)
    if pos == 0 and neg == 0:
        return 0.5
    return clamp(0.5 + (pos - neg) / max(4, pos + neg) * 0.5)


def model_sentiment_score(text: str) -> float | None:
    payload = load_sentiment_model()
    if not payload:
        return None
    model = payload.get("model")
    if model is None:
        return None
    label_to_score = payload.get("label_to_score") or DEFAULT_LABEL_TO_SCORE
    probabilities = getattr(model, "predict_proba", None)
    if probabilities:
        classes = list(getattr(model, "classes_", []))
        scores = model.predict_proba([text])[0]
        return clamp(sum(float(prob) * float(label_to_score.get(label, 0.5)) for label, prob in zip(classes, scores)))
    label = str(model.predict([text])[0])
    return clamp(float(label_to_score.get(label, 0.5)))


def sentiment_label_from_score(score: float) -> str:
    if score >= 0.65:
        return "positive"
    if score <= 0.35:
        return "negative"
    return "neutral"


def sentiment_score(text: str | None) -> float:
    if not text:
        return 0.5
    model_score = model_sentiment_score(text)
    if model_score is not None:
        return model_score
    return rule_based_sentiment_score(text)


def predict_comment_sentiment(text: str | None) -> dict[str, Any]:
    score = sentiment_score(text)
    source = "trained_model" if text and load_sentiment_model() else "rule_fallback"
    return {
        "sentiment_label": sentiment_label_from_score(score),
        "sentiment_score": round(score, 6),
        "sentiment_source": source,
    }


def engagement_rate(likes: float, comments: float, shares: float, views: float) -> float:
    if views <= 0:
        return 0.0
    return clamp((likes + comments * 2.0 + shares * 3.0) / views)


def activity_score(upload_frequency_7d: float, live_viewers: float) -> float:
    upload_component = clamp(upload_frequency_7d / 7.0)
    live_component = clamp(math.log10(live_viewers + 1.0) / 5.0)
    return clamp(upload_component * 0.75 + live_component * 0.25)


def anomaly_score(
    engagement: float,
    follower_growth_rate: float,
    comment_spam_ratio: float,
) -> float:
    growth_penalty = clamp((follower_growth_rate - 0.15) / 0.85)
    engagement_penalty = clamp((engagement - 0.25) / 0.75)
    spam_penalty = clamp(comment_spam_ratio)
    return clamp(growth_penalty * 0.35 + engagement_penalty * 0.25 + spam_penalty * 0.40)


def rule_based_trust_score(anomaly: float, sentiment: float, activity: float) -> float:
    return clamp(0.50 * (1.0 - anomaly) + 0.25 * sentiment + 0.25 * activity) * 100.0


def trust_label_from_score(score: float) -> str:
    if score >= 70.0:
        return "high_trust"
    if score >= 45.0:
        return "medium_trust"
    return "low_trust"


def build_trust_features(
    event: dict[str, Any],
    *,
    views: float,
    likes: float,
    comments: float,
    shares: float,
    followers: float,
    engagement: float,
    sentiment: float,
    activity: float,
    is_suspicious: bool,
) -> dict[str, Any]:
    return {
        "platform": str(event.get("platform") or event.get("source") or "youtube"),
        "follower_count": followers,
        "content_count": to_float(event.get("content_count") or event.get("channel_video_count") or event.get("video_count")),
        "view_count": views,
        "like_count": likes,
        "comment_count": comments,
        "share_count": shares,
        "engagement_rate": engagement,
        "likes_per_view": likes / views if views > 0 else 0.0,
        "comments_per_view": comments / views if views > 0 else 0.0,
        "shares_per_view": shares / views if views > 0 else 0.0,
        "sentiment_score": sentiment * 100.0 if sentiment <= 1.0 else sentiment,
        "positive_comment_count": to_float(event.get("positive_comment_count")),
        "neutral_comment_count": to_float(event.get("neutral_comment_count")),
        "negative_comment_count": to_float(event.get("negative_comment_count")),
        "upload_frequency": to_float(event.get("upload_frequency") or event.get("upload_frequency_7d"), 2.0),
        "follower_growth_rate": to_float(event.get("follower_growth_rate")),
        "activity_score": activity * 100.0 if activity <= 1.0 else activity,
        "is_suspicious": int(is_suspicious),
    }


def model_trust_score(features: dict[str, Any]) -> float | None:
    payload = load_trust_model()
    if not payload:
        return None
    model = payload.get("model")
    if model is None:
        return None
    numeric_features = payload.get("numeric_features") or TRUST_NUMERIC_FEATURES
    categorical_features = payload.get("categorical_features") or TRUST_CATEGORICAL_FEATURES
    row = {name: features.get(name, 0.0) for name in numeric_features}
    row.update({name: features.get(name, "unknown") for name in categorical_features})
    prediction = float(model.predict(pd.DataFrame([row]))[0])
    return clamp(prediction, 0.0, 100.0)


def predict_kol_trust(event: dict[str, Any]) -> dict[str, Any]:
    views = to_float(event.get("views") or event.get("view_count"))
    likes = to_float(event.get("likes") or event.get("like_count"))
    comments = to_float(event.get("comments") or event.get("comment_count"))
    shares = to_float(event.get("shares") or event.get("share_count"))
    followers = to_float(event.get("followers") or event.get("follower_count") or event.get("subscriber_count"))
    upload_frequency_7d = to_float(event.get("upload_frequency_7d") or event.get("upload_frequency"), 2.0)
    live_viewers = to_float(event.get("live_concurrent_viewers"))
    follower_growth_rate = to_float(event.get("follower_growth_rate"))
    spam_ratio = to_float(event.get("comment_spam_ratio"))

    engagement = to_float(event.get("engagement_rate"), engagement_rate(likes, comments, shares, views))
    text = event.get("text") or event.get("comment")
    sentiment = sentiment_score(text) if text else normalize_unit_score(event.get("sentiment_score"), 0.5)
    activity = normalize_unit_score(event.get("activity_score"), activity_score(upload_frequency_7d, live_viewers))
    anomaly = anomaly_score(engagement, follower_growth_rate, spam_ratio)
    suspicious = bool(to_float(event.get("is_suspicious"), 1.0 if (anomaly >= 0.55) else 0.0))
    fallback_score = rule_based_trust_score(anomaly, sentiment, activity)
    features = build_trust_features(
        event,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        followers=followers,
        engagement=engagement,
        sentiment=sentiment,
        activity=activity,
        is_suspicious=suspicious,
    )
    score = model_trust_score(features)
    source = "trained_model" if score is not None else "rule_fallback"
    if score is None:
        score = fallback_score
    return {
        "trust_score": round(score, 2),
        "trust_label": trust_label_from_score(score),
        "trust_source": source,
        "engagement_rate": round(engagement, 6),
        "sentiment_score": round(sentiment, 6),
        "activity_score": round(activity, 6),
        "anomaly_score": round(anomaly, 6),
        "is_suspicious": suspicious or score < 45.0,
    }


def score_event(event: dict[str, Any]) -> dict[str, Any]:
    views = to_float(event.get("views") or event.get("view_count"))
    likes = to_float(event.get("likes") or event.get("like_count"))
    comments = to_float(event.get("comments") or event.get("comment_count"))
    shares = to_float(event.get("shares") or event.get("share_count"))
    followers = to_float(event.get("followers") or event.get("follower_count") or event.get("subscriber_count"))
    upload_frequency_7d = to_float(event.get("upload_frequency_7d"), 2.0)
    live_viewers = to_float(event.get("live_concurrent_viewers"))
    follower_growth_rate = to_float(event.get("follower_growth_rate"))
    spam_ratio = to_float(event.get("comment_spam_ratio"))

    engagement = engagement_rate(likes, comments, shares, views)
    text = event.get("text") or event.get("comment")
    sentiment = sentiment_score(text) if text else to_float(event.get("sentiment_score"), 0.5)
    activity = activity_score(upload_frequency_7d, live_viewers)
    anomaly = anomaly_score(engagement, follower_growth_rate, spam_ratio)
    trust_prediction = predict_kol_trust(
        {
            **event,
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "followers": followers,
            "engagement_rate": engagement,
            "sentiment_score": sentiment * 100.0,
            "activity_score": activity * 100.0,
            "is_suspicious": anomaly >= 0.55,
        }
    )

    timestamp = event.get("timestamp") or event.get("crawled_at")
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "kol_id": str(event.get("kol_id") or event.get("channel_id") or event.get("channel") or "unknown"),
        "kol_name": str(event.get("kol_name") or event.get("channel_title") or event.get("channel") or "Unknown KOL"),
        "platform": str(event.get("platform") or event.get("source") or "youtube"),
        "video_id": str(event.get("video_id") or ""),
        "timestamp": timestamp,
        "views": int(views),
        "likes": int(likes),
        "comments": int(comments),
        "shares": int(shares),
        "followers": int(followers),
        "engagement_rate": round(engagement, 6),
        "sentiment_score": round(sentiment, 6),
        "activity_score": round(activity, 6),
        "anomaly_score": round(anomaly, 6),
        "trust_score": trust_prediction["trust_score"],
        "trust_label": trust_prediction["trust_label"],
        "trust_source": trust_prediction["trust_source"],
        "is_suspicious": trust_prediction["is_suspicious"],
    }
