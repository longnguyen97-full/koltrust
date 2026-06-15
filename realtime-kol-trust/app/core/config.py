import os
from dataclasses import dataclass


def env(key: str, default: str) -> str:
    return os.getenv(key, default)


def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = env("APP_ENV", "dev")
    kafka_bootstrap_servers: str = env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
    kafka_raw_topic: str = env("KAFKA_RAW_TOPIC", "kol_raw_events")
    kafka_processed_topic: str = env("KAFKA_PROCESSED_TOPIC", "kol_processed_events")
    cassandra_hosts: str = env("CASSANDRA_HOSTS", "localhost")
    cassandra_port: int = env_int("CASSANDRA_PORT", 9042)
    cassandra_keyspace: str = env("CASSANDRA_KEYSPACE", "kol_trust")
    api_base_url: str = env("API_BASE_URL", "http://localhost:8000")
    replay_interval_seconds: float = float(env("REPLAY_INTERVAL_SECONDS", "1.0"))

    @property
    def cassandra_host_list(self) -> list[str]:
        return [host.strip() for host in self.cassandra_hosts.split(",") if host.strip()]


settings = Settings()
