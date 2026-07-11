"""게시물 병합 + 30일 동결 규칙 (순수 함수 — API/파일 접근 없음)."""

from __future__ import annotations

from datetime import datetime, timedelta

FREEZE_DAYS = 30
DISPLAY_LIMIT = 120
CAPTION_MAX = 120


def _parse_ts(ts: str) -> datetime:
    # IG 타임스탬프는 "2026-07-01T09:00:00+0000" 형식
    return datetime.fromisoformat(ts.replace("+0000", "+00:00"))


def is_frozen(posted_at: str, now: datetime, freeze_days: int = FREEZE_DAYS) -> bool:
    return now - _parse_ts(posted_at) > timedelta(days=freeze_days)


def merge_posts(
    stored_posts: list[dict],
    fresh_media: list[dict],
    fresh_insights: dict[str, dict],
    now: datetime,
    freeze_days: int = FREEZE_DAYS,
    limit: int = DISPLAY_LIMIT,
) -> list[dict]:
    """오늘 받아온 미디어 목록을 기준으로 저장분과 병합한다.

    - 30일 이내: fresh_insights 의 값으로 지표 갱신
    - 30일 경과: stored_posts 의 동결값 유지 (썸네일/permalink 는 갱신)
    - fresh_media 에 없는 저장분은 탈락 (삭제되었거나 120개 밖)
    """
    stored_by_id = {p["media_id"]: p for p in stored_posts}
    merged: list[dict] = []
    for m in fresh_media[:limit]:
        mid = m["id"]
        old = stored_by_id.get(mid)
        frozen = is_frozen(m["timestamp"], now, freeze_days)
        post = {
            "media_id": mid,
            "caption": (m.get("caption") or "")[:CAPTION_MAX],
            "media_type": m.get("media_type"),
            "media_product_type": m.get("media_product_type"),
            "permalink": m.get("permalink"),
            "thumbnail": m.get("thumbnail_url") or m.get("media_url"),
            "posted_at": m["timestamp"],
            "frozen": frozen,
            "metrics": {},
            "metrics_updated_at": None,
        }
        if not frozen and mid in fresh_insights:
            post["metrics"] = fresh_insights[mid]
            post["metrics_updated_at"] = now.isoformat()
        elif old:
            post["metrics"] = old.get("metrics", {})
            post["metrics_updated_at"] = old.get("metrics_updated_at")
        merged.append(post)
    return merged
