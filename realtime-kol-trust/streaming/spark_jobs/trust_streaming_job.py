from __future__ import annotations

import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    concat_ws,
    current_timestamp,
    date_format,
    expr,
    from_json,
    greatest,
    least,
    lit,
    lower,
    regexp_replace,
    udf,
    when,
)
from pyspark.sql.types import BooleanType, DoubleType, IntegerType, StringType, StructField, StructType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.trust_model import predict_kol_trust, sentiment_score as trained_sentiment_score


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RAW_TOPIC = os.getenv("KAFKA_RAW_TOPIC", "kol_raw_events")
PROCESSED_TOPIC = os.getenv("KAFKA_PROCESSED_TOPIC", "kol_processed_events")
CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra")
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "kol_trust")
CHECKPOINT_DIR = os.getenv("SPARK_CHECKPOINT_DIR", "/tmp/spark-checkpoints/kol-trust")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
RAW_LAKE_PATH = os.getenv("S3_RAW_PATH", "s3a://koltrust-raw/streaming/raw_events")
PROCESSED_LAKE_PATH = os.getenv("S3_PROCESSED_PATH", "s3a://koltrust-processed/streaming/silver/trust_scores")
SERVING_LAKE_PATH = os.getenv("S3_SERVING_PATH", "s3a://koltrust-serving/streaming/trust_scores")

CASSANDRA_COLUMNS = [
    "kol_id",
    "event_ts",
    "kol_name",
    "platform",
    "video_id",
    "views",
    "likes",
    "comments",
    "shares",
    "followers",
    "engagement_rate",
    "sentiment_score",
    "activity_score",
    "anomaly_score",
    "trust_score",
    "is_suspicious",
    "processed_at",
]

RAW_LAKE_COLUMNS = [
    "raw_payload",
    "kafka_topic",
    "kafka_partition",
    "kafka_offset",
    "kafka_timestamp",
    "processed_at",
    "event_date",
]


schema = StructType(
    [
        StructField("kol_id", StringType()),
        StructField("kol_name", StringType()),
        StructField("channel_id", StringType()),
        StructField("channel_title", StringType()),
        StructField("channel", StringType()),
        StructField("platform", StringType()),
        StructField("source", StringType()),
        StructField("video_id", StringType()),
        StructField("timestamp", StringType()),
        StructField("crawled_at", StringType()),
        StructField("views", IntegerType()),
        StructField("view_count", IntegerType()),
        StructField("likes", IntegerType()),
        StructField("like_count", IntegerType()),
        StructField("comments", IntegerType()),
        StructField("comment_count", IntegerType()),
        StructField("shares", IntegerType()),
        StructField("followers", IntegerType()),
        StructField("subscriber_count", IntegerType()),
        StructField("upload_frequency_7d", DoubleType()),
        StructField("live_concurrent_viewers", DoubleType()),
        StructField("follower_growth_rate", DoubleType()),
        StructField("comment_spam_ratio", DoubleType()),
        StructField("text", StringType()),
    ]
)

sentiment_udf = udf(lambda text: float(trained_sentiment_score(text)), DoubleType())
trust_score_udf = udf(
    lambda platform, views, likes, comments, shares, followers, engagement, sentiment, activity, suspicious: float(
        predict_kol_trust(
            {
                "platform": platform,
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "followers": followers,
                "engagement_rate": engagement,
                "sentiment_score": sentiment,
                "activity_score": activity,
                "is_suspicious": bool(suspicious),
            }
        )["trust_score"]
    ),
    DoubleType(),
)


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("kol-trust-streaming")
        .config("spark.cassandra.connection.host", CASSANDRA_HOSTS)
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SQL_SHUFFLE_PARTITIONS", "2"))
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def add_features(df):
    base = (
        df.select(
            col("value").cast("string").alias("raw_payload"),
            col("topic").alias("kafka_topic"),
            col("partition").alias("kafka_partition"),
            col("offset").alias("kafka_offset"),
            col("timestamp").alias("kafka_timestamp"),
            from_json(col("value").cast("string"), schema).alias("event"),
        )
        .select(
            "event.*",
            "raw_payload",
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "kafka_timestamp",
        )
        .withColumn("kol_id", expr("coalesce(kol_id, channel_id, channel, 'unknown')"))
        .withColumn("kol_name", expr("coalesce(kol_name, channel_title, channel, 'Unknown KOL')"))
        .withColumn("platform", expr("coalesce(platform, source, 'youtube')"))
        .withColumn("event_ts", expr("to_timestamp(coalesce(timestamp, crawled_at))"))
        .withColumn("event_ts", expr("coalesce(event_ts, current_timestamp())"))
        .withColumn("views", expr("coalesce(views, view_count, 0)"))
        .withColumn("likes", expr("coalesce(likes, like_count, 0)"))
        .withColumn("comments", expr("coalesce(comments, comment_count, 0)"))
        .withColumn("shares", expr("coalesce(shares, 0)"))
        .withColumn("followers", expr("coalesce(followers, subscriber_count, 0)"))
        .withColumn("upload_frequency_7d", expr("coalesce(upload_frequency_7d, 2.0D)"))
        .withColumn("live_concurrent_viewers", expr("coalesce(live_concurrent_viewers, 0.0D)"))
        .withColumn("follower_growth_rate", expr("coalesce(follower_growth_rate, 0.0D)"))
        .withColumn("comment_spam_ratio", expr("coalesce(comment_spam_ratio, 0.0D)"))
        .withColumn("text", expr("coalesce(text, '')"))
    )

    text = lower(regexp_replace(col("text"), "\\s+", " "))
    sentiment = sentiment_udf(text)
    engagement = when(
        col("views") > 0,
        (col("likes") + col("comments") * lit(2.0) + col("shares") * lit(3.0)) / col("views"),
    ).otherwise(lit(0.0))
    engagement = least(lit(1.0), greatest(lit(0.0), engagement))
    activity = least(
        lit(1.0),
        greatest(lit(0.0), col("upload_frequency_7d") / lit(7.0) * lit(0.75) + expr("log10(live_concurrent_viewers + 1.0)") / lit(5.0) * lit(0.25)),
    )
    anomaly = least(
        lit(1.0),
        greatest(lit(0.0), (col("follower_growth_rate") - lit(0.15)) / lit(0.85)) * lit(0.35)
        + greatest(lit(0.0), (engagement - lit(0.25)) / lit(0.75)) * lit(0.25)
        + least(lit(1.0), greatest(lit(0.0), col("comment_spam_ratio"))) * lit(0.40),
    )
    suspicious = (anomaly >= lit(0.55)).cast(BooleanType())
    trust = trust_score_udf(col("platform"), col("views"), col("likes"), col("comments"), col("shares"), col("followers"), engagement, sentiment, activity, suspicious)

    return (
        base.withColumn("engagement_rate", engagement.cast(DoubleType()))
        .withColumn("sentiment_score", sentiment.cast(DoubleType()))
        .withColumn("activity_score", activity.cast(DoubleType()))
        .withColumn("anomaly_score", anomaly.cast(DoubleType()))
        .withColumn("trust_score", trust.cast(DoubleType()))
        .withColumn("is_suspicious", (suspicious | (trust < lit(45.0))).cast(BooleanType()))
        .withColumn("processed_at", current_timestamp())
        .withColumn("event_date", date_format(col("event_ts"), "yyyy-MM-dd"))
        .select(
            "raw_payload",
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "kafka_timestamp",
            "kol_id",
            "kol_name",
            "platform",
            "video_id",
            "event_ts",
            "views",
            "likes",
            "comments",
            "shares",
            "followers",
            "engagement_rate",
            "sentiment_score",
            "activity_score",
            "anomaly_score",
            "trust_score",
            "is_suspicious",
            "processed_at",
            "event_date",
        )
    )


def write_batch(batch_df, batch_id: int) -> None:
    if batch_df.rdd.isEmpty():
        return

    batch = batch_df.withColumn("batch_id", lit(batch_id)).cache()
    try:
        (
            batch.select(*RAW_LAKE_COLUMNS, "batch_id")
            .write.mode("append")
            .partitionBy("event_date")
            .json(RAW_LAKE_PATH)
        )
        (
            batch.drop("raw_payload")
            .write.mode("append")
            .partitionBy("event_date")
            .parquet(PROCESSED_LAKE_PATH)
        )
        (
            batch.select(*CASSANDRA_COLUMNS, "event_date", "batch_id")
            .write.mode("append")
            .partitionBy("event_date")
            .parquet(SERVING_LAKE_PATH)
        )
        (
            batch.select(*CASSANDRA_COLUMNS)
            .write.format("org.apache.spark.sql.cassandra")
            .mode("append")
            .option("keyspace", CASSANDRA_KEYSPACE)
            .option("table", "trust_scores")
            .save()
        )
    finally:
        batch.unpersist()


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", RAW_TOPIC)
        .option("startingOffsets", "earliest")
        .load()
    )
    scored = add_features(raw)

    query = (
        scored.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", CHECKPOINT_DIR)
        .outputMode("append")
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()
