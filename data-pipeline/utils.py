from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


class QuotaExceededError(RuntimeError):
    """Raised when the YouTube API reports quota exhaustion."""


class RateLimitExceededError(RuntimeError):
    """Raised when the YouTube API reports temporary rate limiting."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_output_dirs(base_dir: Path) -> None:
    (base_dir / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (base_dir / "data" / "sample").mkdir(parents=True, exist_ok=True)
    (base_dir / "data" / "input").mkdir(parents=True, exist_ok=True)
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def read_nonempty_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.strip().startswith("#")]


def load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def get_youtube_api_key(base_dir: Path) -> str:
    key_names = ("YOUTUBE_API_KEY", "YOUTUBE_API_Key")
    for key_name in key_names:
        value = os.getenv(key_name)
        if value:
            return value

    dotenv_values = load_dotenv_values(base_dir / ".env")
    for key_name in key_names:
        value = dotenv_values.get(key_name)
        if value:
            return value

    raise RuntimeError("Missing YOUTUBE_API_KEY. Set it in the OS environment or project .env file.")


def get_tiktok_ms_token() -> str:
    value = os.getenv("ms_token")
    if value:
        return value

    dotenv_values = load_dotenv_values(Path(__file__).resolve().parent / ".env")
    value = dotenv_values.get("ms_token")
    if value:
        return value

    raise RuntimeError("Missing ms_token. Set it in the OS environment or project .env file.")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def log_event(level: str, source: str, message: str, **fields: Any) -> None:
    payload = {
        "level": level,
        "source": source,
        "message": message,
        "timestamp": utc_now_iso(),
        **fields,
    }
    logger = logging.getLogger(__name__)
    getattr(logger, level if level in {"info", "warning", "error"} else "info")(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def retry_with_backoff(
    func: Callable[[], dict[str, Any]],
    *,
    attempts: int = 3,
    base_sleep: float = 1.0,
    source: str = "youtube",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or {}
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except (QuotaExceededError, RateLimitExceededError):
            raise
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            sleep_for = base_sleep * (2 ** (attempt - 1))
            log_event(
                "warning",
                source,
                "request_failed_retrying",
                attempt=attempt,
                sleep_seconds=sleep_for,
                error=str(exc),
                **context,
            )
            time.sleep(sleep_for)
    raise RuntimeError(str(last_error) if last_error else "request failed")
