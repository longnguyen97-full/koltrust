from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


POSITIVE_TERMS = {
    "amazing",
    "beautiful",
    "best",
    "cool",
    "excellent",
    "funny",
    "good",
    "great",
    "helpful",
    "love",
    "nice",
    "perfect",
    "thanks",
    "wonderful",
    "cam on",
    "cảm ơn",
    "de thuong",
    "dễ thương",
    "dinh",
    "đỉnh",
    "hay",
    "qua hay",
    "rat hay",
    "rất hay",
    "tot",
    "tốt",
    "tuyet",
    "tuyệt",
    "tuyet voi",
    "tuyệt vời",
    "ung ho",
    "ủng hộ",
    "xinh",
    "xuat sac",
    "xuất sắc",
}

NEGATIVE_TERMS = {
    "awful",
    "bad",
    "boring",
    "disappointed",
    "fake",
    "hate",
    "poor",
    "scam",
    "terrible",
    "trash",
    "worst",
    "chan",
    "chán",
    "do",
    "dở",
    "gia tao",
    "giả tạo",
    "kem",
    "kém",
    "lua dao",
    "lừa đảo",
    "nham",
    "nhảm",
    "qua te",
    "quá tệ",
    "te",
    "tệ",
    "that vong",
    "thất vọng",
    "xam",
    "xàm",
}

NEGATION_TERMS = {"khong", "không", "ko", "k", "not", "no", "chua", "chưa"}
TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def _normalize_text(text: str) -> str:
    lowered = text.casefold()
    return re.sub(r"\s+", " ", lowered).strip()


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(_normalize_text(text))


def _phrase_hits(text: str, terms: set[str]) -> int:
    padded = f" {_normalize_text(text)} "
    return sum(1 for term in terms if " " in term and f" {term} " in padded)


def _token_hits(tokens: list[str], terms: set[str]) -> int:
    term_tokens = {term for term in terms if " " not in term}
    hits = 0
    for index, token in enumerate(tokens):
        if token not in term_tokens:
            continue
        window = tokens[max(0, index - 3) : index]
        hits += -1 if any(item in NEGATION_TERMS for item in window) else 1
    return hits


def analyze_comment_sentiment(text: str) -> dict[str, object]:
    """Return a simple rule-based sentiment label and 0-100 score.

    This is intended as a transparent baseline for Vietnamese/English public
    comments. It is not a model prediction or ground truth.
    """
    if not text.strip():
        return {
            "comment_sentiment": "neutral",
            "comment_sentiment_score": 50.0,
            "comment_sentiment_source": "rule_keyword_baseline",
        }

    tokens = _tokens(text)
    positive_hits = _token_hits(tokens, POSITIVE_TERMS) + _phrase_hits(text, POSITIVE_TERMS)
    negative_hits = _token_hits(tokens, NEGATIVE_TERMS) + _phrase_hits(text, NEGATIVE_TERMS)
    raw_score = positive_hits - negative_hits

    if raw_score > 0:
        label = "positive"
    elif raw_score < 0:
        label = "negative"
    else:
        label = "neutral"

    score = max(0, min(100, 50 + raw_score * 20))
    return {
        "comment_sentiment": label,
        "comment_sentiment_score": round(float(score), 2),
        "comment_sentiment_source": "rule_keyword_baseline",
    }


def aggregate_comment_sentiment(comments: Iterable[dict]) -> dict[str, object]:
    rows = []
    for row in comments:
        if "comment_sentiment" in row and "comment_sentiment_score" in row:
            rows.append(row)
            continue
        if row.get("comment_text") and not row.get("comment_text_is_hashed"):
            rows.append({**row, **analyze_comment_sentiment(str(row.get("comment_text") or ""))})
        else:
            rows.append(
                {
                    **row,
                    "comment_sentiment": "neutral",
                    "comment_sentiment_score": 50.0,
                    "comment_sentiment_source": "missing_comment_text_default_neutral",
                }
            )
    if not rows:
        return {
            "sentiment_score": 50.0,
            "sentiment_label": "neutral",
            "positive_comment_count": 0,
            "neutral_comment_count": 0,
            "negative_comment_count": 0,
            "sentiment_source": "no_comments_default_neutral",
        }

    counts = Counter(str(row.get("comment_sentiment") or "neutral") for row in rows)
    scores = [float(row.get("comment_sentiment_score") or 50.0) for row in rows]
    sentiment_score = round(sum(scores) / max(len(scores), 1), 2)
    if sentiment_score >= 60:
        label = "positive"
    elif sentiment_score <= 40:
        label = "negative"
    else:
        label = "neutral"

    return {
        "sentiment_score": sentiment_score,
        "sentiment_label": label,
        "positive_comment_count": counts.get("positive", 0),
        "neutral_comment_count": counts.get("neutral", 0),
        "negative_comment_count": counts.get("negative", 0),
        "sentiment_source": "rule_keyword_baseline",
    }
