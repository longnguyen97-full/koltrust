from __future__ import annotations

import asyncio
import re
from typing import Any

from TikTokApi import TikTokApi


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _unwrap_video(video: Any) -> dict[str, Any]:
    if hasattr(video, "as_dict") and isinstance(video.as_dict, dict):
        return video.as_dict
    if hasattr(video, "data") and isinstance(video.data, dict):
        return video.data
    return {}


HASHTAG_RE = re.compile(r"#([\wÀ-ỹ]+)", re.UNICODE)


def _extract_hashtags(raw: dict[str, Any], caption: str) -> list[str]:
    hashtags: list[str] = []
    for challenge in raw.get("challenges", []) or []:
        title = _first_present(challenge, ("title", "hashtagName", "name"), "")
        if title:
            hashtags.append(str(title).lstrip("#"))
    for extra in raw.get("textExtra", []) or []:
        tag_name = _first_present(extra, ("hashtagName", "tagName"), "")
        if tag_name:
            hashtags.append(str(tag_name).lstrip("#"))
    hashtags.extend(match.group(1) for match in HASHTAG_RE.finditer(caption or ""))
    return list(dict.fromkeys(tag for tag in hashtags if tag))


class TikTokPublicClient:
    """Small wrapper around TikTokApi for public creator/video metadata only."""

    def __init__(
        self,
        *,
        browser: str = "chromium",
        headless: bool = True,
        sleep_after: int = 3,
        timeout_ms: int = 30_000,
        ms_token: str | None = None,
    ) -> None:
        self.browser = browser
        self.headless = headless
        self.sleep_after = sleep_after
        self.timeout_ms = timeout_ms
        self.ms_token = ms_token

    async def collect_user(self, username: str, *, max_videos: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        async with TikTokApi() as api:
            await api.create_sessions(
                num_sessions=1,
                ms_tokens=[self.ms_token] if self.ms_token else None,
                headless=self.headless,
                sleep_after=self.sleep_after,
                browser=self.browser,
                timeout=self.timeout_ms,
                allow_partial_sessions=True,
                min_sessions=1,
            )
            user = api.user(username=username)
            creator_info = await user.info()
            videos: list[dict[str, Any]] = []
            async for video in user.videos(count=max_videos):
                video_data = _unwrap_video(video)
                if not video_data:
                    video_data = await video.info()
                videos.append(video_data)
                if len(videos) >= max_videos:
                    break
            return creator_info, videos

    def collect_user_sync(self, username: str, *, max_videos: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return asyncio.run(self.collect_user(username, max_videos=max_videos))


def normalize_tiktok_creator(raw: dict[str, Any], *, username: str, category: str, collected_at: str) -> dict[str, Any]:
    user_info = raw.get("userInfo", raw)
    user = user_info.get("user", user_info.get("userInfo", {}).get("user", {}))
    stats = user_info.get("stats", user_info.get("userInfo", {}).get("stats", {}))
    return {
        "platform": "tiktok",
        "creator_id": _first_present(user, ("id", "uid"), username),
        "creator_name": _first_present(user, ("nickname", "uniqueId"), username),
        "username": _first_present(user, ("uniqueId", "username"), username),
        "category": category,
        "follower_count": int(_first_present(stats, ("followerCount", "followers"), 0) or 0),
        "following_count": int(_first_present(stats, ("followingCount", "following"), 0) or 0),
        "content_count": int(_first_present(stats, ("videoCount", "videos"), 0) or 0),
        "collected_at": collected_at,
    }


def normalize_tiktok_video(
    raw: dict[str, Any],
    *,
    creator: dict[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    stats = raw.get("stats", raw.get("statistics", {}))
    author = raw.get("author", {})
    caption = _first_present(raw, ("desc", "title"), "")
    return {
        "platform": "tiktok",
        "content_id": _first_present(raw, ("id", "video_id", "aweme_id"), ""),
        "creator_id": creator.get("creator_id") or _first_present(author, ("id", "uid"), ""),
        "creator_name": creator.get("creator_name") or _first_present(author, ("nickname", "uniqueId"), ""),
        "username": creator.get("username") or _first_present(author, ("uniqueId", "username"), ""),
        "content_title": caption,
        "caption": caption,
        "hashtags": _extract_hashtags(raw, str(caption or "")),
        "publish_time": _first_present(raw, ("createTime", "create_time"), ""),
        "view_count": int(_first_present(stats, ("playCount", "viewCount", "views"), 0) or 0),
        "like_count": int(_first_present(stats, ("diggCount", "likeCount", "likes"), 0) or 0),
        "comment_count": int(_first_present(stats, ("commentCount", "comments"), 0) or 0),
        "share_count": int(_first_present(stats, ("shareCount", "shares"), 0) or 0),
        "collected_at": collected_at,
    }
