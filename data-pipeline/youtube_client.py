from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from utils import QuotaExceededError, RateLimitExceededError, retry_with_backoff


class YouTubeClient:
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, *, sleep_seconds: float = 0.2, timeout: int = 20) -> None:
        self.api_key = api_key
        self.sleep_seconds = sleep_seconds
        self.timeout = timeout

    def _request(self, endpoint: str, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        def do_request() -> dict[str, Any]:
            query = urllib.parse.urlencode({**params, "key": self.api_key})
            url = f"{self.BASE_URL}/{endpoint}?{query}"
            request = urllib.request.Request(url, headers={"User-Agent": "koltrust-data-pipeline/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    import json

                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                import json

                body = exc.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(body)
                    reason = payload.get("error", {}).get("errors", [{}])[0].get("reason")
                except json.JSONDecodeError:
                    reason = str(exc)
                if reason == "quotaExceeded":
                    raise QuotaExceededError("quotaExceeded") from exc
                if reason == "rateLimitExceeded":
                    raise RateLimitExceededError("rateLimitExceeded") from exc
                raise RuntimeError(reason or body) from exc
            finally:
                time.sleep(self.sleep_seconds)

            return payload

        return retry_with_backoff(do_request, source="youtube", context=context)

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        payload = self._request(
            "videos",
            {"part": "snippet,statistics", "id": video_id, "maxResults": 1},
            {"video_id": video_id},
        )
        return next(iter(payload.get("items", [])), None)

    def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        payload = self._request(
            "channels",
            {"part": "snippet,statistics", "id": channel_id, "maxResults": 1},
            {"channel_id": channel_id},
        )
        return next(iter(payload.get("items", [])), None)

    def search_channels(self, query: str, *, max_results: int, region_code: str | None = None) -> list[dict[str, Any]]:
        channel_ids: list[str] = []
        page_token: str | None = None
        while len(channel_ids) < max_results:
            params: dict[str, Any] = {
                "part": "snippet",
                "q": query,
                "type": "channel",
                "maxResults": min(50, max_results - len(channel_ids)),
            }
            if region_code:
                params["regionCode"] = region_code
            if page_token:
                params["pageToken"] = page_token
            payload = self._request("search", params, {"query": query})
            for item in payload.get("items", []):
                channel_id = item.get("snippet", {}).get("channelId")
                if channel_id and channel_id not in channel_ids:
                    channel_ids.append(channel_id)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return self.get_channels(channel_ids)

    def get_channels(self, channel_ids: list[str]) -> list[dict[str, Any]]:
        channels: list[dict[str, Any]] = []
        for start in range(0, len(channel_ids), 50):
            chunk = channel_ids[start : start + 50]
            payload = self._request(
                "channels",
                {"part": "snippet,statistics", "id": ",".join(chunk), "maxResults": len(chunk)},
                {"channel_ids": chunk},
            )
            channels.extend(payload.get("items", []))
        return channels

    def list_channel_videos(self, channel_id: str, *, max_videos: int) -> list[dict[str, Any]]:
        video_ids: list[str] = []
        page_token: str | None = None
        while len(video_ids) < max_videos:
            params: dict[str, Any] = {
                "part": "id",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "maxResults": min(50, max_videos - len(video_ids)),
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._request("search", params, {"channel_id": channel_id})
            for item in payload.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return self.get_videos(video_ids)

    def get_videos(self, video_ids: list[str]) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            payload = self._request(
                "videos",
                {"part": "snippet,statistics", "id": ",".join(chunk), "maxResults": len(chunk)},
                {"video_ids": chunk},
            )
            videos.extend(payload.get("items", []))
        return videos

    def list_comments(self, video_id: str, *, max_comments: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        page_token: str | None = None
        while len(comments) < max_comments:
            params: dict[str, Any] = {
                "part": "snippet,replies",
                "videoId": video_id,
                "textFormat": "plainText",
                "maxResults": min(100, max_comments - len(comments)),
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._request("commentThreads", params, {"video_id": video_id})
            comments.extend(payload.get("items", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return comments
