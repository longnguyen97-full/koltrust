CREATE KEYSPACE IF NOT EXISTS kol_trust
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS kol_trust.trust_scores (
    kol_id text,
    event_ts timestamp,
    kol_name text,
    platform text,
    video_id text,
    views int,
    likes int,
    comments int,
    shares int,
    followers int,
    engagement_rate double,
    sentiment_score double,
    activity_score double,
    anomaly_score double,
    trust_score double,
    is_suspicious boolean,
    processed_at timestamp,
    PRIMARY KEY (kol_id, event_ts)
) WITH CLUSTERING ORDER BY (event_ts DESC);

CREATE INDEX IF NOT EXISTS trust_scores_suspicious_idx
ON kol_trust.trust_scores (is_suspicious);
