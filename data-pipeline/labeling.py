from __future__ import annotations


def add_basic_features(record: dict) -> dict:
    views = int(record.get("views") or record.get("view_count") or 0)
    likes = int(record.get("likes") or record.get("like_count") or 0)
    comments = int(record.get("comments") or record.get("comment_count") or 0)
    denominator = max(views, 1)

    enriched = dict(record)
    enriched["views"] = views
    enriched["likes"] = likes
    enriched["comments"] = comments
    enriched["engagement_rate"] = round((likes + comments) / denominator, 6)
    enriched["likes_per_view"] = round(likes / denominator, 6)
    enriched["comments_per_view"] = round(comments / denominator, 6)
    return enriched


def add_rule_labels(record: dict) -> dict:
    """Rule-generated labels for demos; these are not ground-truth labels."""
    enriched = add_basic_features(record)
    views = enriched["views"]
    comments = enriched["comments"]
    engagement_rate = enriched["engagement_rate"]
    sentiment_score = float(record.get("sentiment_score", 50.0) or 50.0)

    if engagement_rate > 0.30:
        is_suspicious = 1
    elif views > 100_000 and comments < 5:
        is_suspicious = 1
    else:
        is_suspicious = 0

    engagement_score = min(engagement_rate / 0.10, 1.0) * 100
    activity_score = min((comments / 1000) * 100, 100)
    trust_score = (0.5 * engagement_score) + (0.3 * sentiment_score) + (0.2 * activity_score)

    enriched["is_suspicious"] = is_suspicious
    enriched["sentiment_score"] = round(max(0, min(sentiment_score, 100)), 2)
    enriched["activity_score"] = round(activity_score, 2)
    enriched["trust_score"] = round(max(0, min(trust_score, 100)), 2)
    enriched["label_source"] = "rule_generated_not_ground_truth"
    return enriched
