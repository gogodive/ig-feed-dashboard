"""Instagram Graph API 클라이언트.

모든 호출은 Meta access token 기반. 각 계정은
(비즈니스 계정) → (페이스북 페이지 연결) → (시스템 사용자 토큰) 경로로 인증된다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)


class GraphAPIError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Graph API {status}: {body}")


class InstagramClient:
    # media_product_type 별 사용 가능 지표. impressions 는 v22+ deprecated → views.
    _METRICS_BY_TYPE = {
        "FEED": ["reach", "likes", "comments", "saved", "shares", "total_interactions", "views"],
        "REELS": ["reach", "likes", "comments", "saved", "shares", "total_interactions", "views"],
        "AD": ["reach", "likes", "comments", "saved", "shares", "total_interactions", "views"],
        "STORY": ["reach", "replies", "total_interactions", "views"],
    }
    _DEFAULT_METRICS = ["reach", "likes", "comments", "saved", "shares", "total_interactions", "views"]

    def __init__(self, access_token: str, version: str = "v23.0", timeout: int = 30):
        self.access_token = access_token
        self.base = f"https://graph.facebook.com/{version}"
        self.timeout = timeout

    # ── 내부 헬퍼 ──────────────────────────────────────────────
    def _get(self, path_or_url: str, params: Optional[dict] = None) -> dict:
        if path_or_url.startswith("https://"):
            url, params = path_or_url, dict(params or {})
        else:
            url = f"{self.base}/{path_or_url}"
            params = dict(params or {})
            params["access_token"] = self.access_token
        resp = requests.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise GraphAPIError(resp.status_code, resp.text)
        return resp.json()

    # ── 계정 탐색 ──────────────────────────────────────────────
    def list_pages_with_ig(self) -> list[dict]:
        """토큰으로 접근 가능한 페이지 + 연결된 IG 비즈니스 계정 목록."""
        out: list[dict] = []
        data = self._get("me/accounts",
                         {"fields": "id,name,instagram_business_account{id,username}"})
        while True:
            for p in data.get("data", []):
                iba = p.get("instagram_business_account") or {}
                out.append({
                    "page_id": p.get("id"),
                    "page_name": p.get("name"),
                    "ig_user_id": iba.get("id"),
                    "ig_username": iba.get("username"),
                })
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                return out
            data = self._get(next_url)

    # ── 계정 정보 ──────────────────────────────────────────────
    def get_account(self, ig_user_id: str) -> dict:
        return self._get(ig_user_id, {"fields": "username,followers_count,media_count"})

    # ── 최근 미디어 (페이지네이션, 최대 limit개) ────────────────
    def get_recent_media(self, ig_user_id: str, limit: int = 120) -> list[dict]:
        fields = "id,caption,media_type,media_product_type,permalink,timestamp,media_url,thumbnail_url"
        out: list[dict] = []
        data = self._get(f"{ig_user_id}/media",
                         {"fields": fields, "limit": min(limit, 100)})
        while True:
            out.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")
            if len(out) >= limit or not next_url:
                return out[:limit]
            data = self._get(next_url)

    # ── 미디어 인사이트 ────────────────────────────────────────
    def get_media_insights(self, media_id: str, product_type: str) -> dict[str, Any]:
        """{metric: value}. 미지원 지표(#100)는 자동으로 빼고 재시도."""
        metrics = list(self._METRICS_BY_TYPE.get(product_type, self._DEFAULT_METRICS))
        return self._fetch_insights_with_fallback(media_id, metrics)

    def _fetch_insights_with_fallback(self, media_id: str, metrics: list[str]) -> dict[str, Any]:
        if not metrics:
            return {}
        try:
            data = self._get(f"{media_id}/insights", {"metric": ",".join(metrics)})
        except GraphAPIError as e:
            bad = _extract_unsupported_metric(str(e), metrics)
            if bad:
                log.warning("media %s: 미지원 지표 '%s' 제외 후 재시도", media_id, bad)
                return self._fetch_insights_with_fallback(
                    media_id, [m for m in metrics if m != bad])
            log.warning("media %s: 인사이트 조회 실패 — %s", media_id, e)
            return {}
        out: dict[str, Any] = {}
        for item in data.get("data", []):
            values = item.get("values") or [{}]
            out[item.get("name")] = values[0].get("value")
        return out


def _extract_unsupported_metric(error_text: str, metrics: list[str]) -> Optional[str]:
    lowered = error_text.lower()
    for m in metrics:
        if m.lower() in lowered:
            return m
    return None
