# 인스타 데일리 피드 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자사 인스타 4개 계정의 피드를 매일 아침 7시(KST)에 수집해 인스타 피드 모양의 정적 HTML 대시보드를 GitHub Pages로 배포한다.

**Architecture:** GitHub Actions cron이 매일 Python 수집기를 실행한다. 수집기는 Graph API로 계정당 최근 120개 게시물을 가져오고, 게시 후 30일 이내 게시물만 인사이트를 갱신하며(30일 경과분은 저장된 JSON의 동결값 사용), 결과를 `data/*.json`에 커밋하고 `site/index.html`을 생성해 Pages로 배포한다.

**Tech Stack:** Python 3.12, requests, Jinja2, PyYAML, pytest. GitHub Actions + GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-07-11-ig-feed-dashboard-design.md`

## Global Constraints

- 계정당 표시 게시물 최대 **120개**, 인사이트 갱신은 **게시 후 30일 이내**만 (스펙 결정 2, 3)
- cron: `0 22 * * *` (UTC) = 07:00 KST. 시각 표기는 모두 **Asia/Seoul**
- 배포 대상: `site/index.html` 단일 파일. `<meta name="robots" content="noindex">` 필수
- 토큰은 환경변수 `META_ACCESS_TOKEN` 로만 접근. 코드·저장소에 하드코딩 금지
- Graph API 버전 `v23.0`
- 의존성은 requests, Jinja2, PyYAML, pytest 만 사용
- 대상 계정 4개: 고고다이브 @gogodive / 인투더블루 @intotheblue_store / 라세린 @laserin_swim / 시크릿스 @secrets__fit
- 계정 1개 실패 시 나머지는 정상 진행, 실패 계정은 기존 JSON 유지

## 데이터 모델 (`data/<username>.json`)

```json
{
  "brand": "고고다이브",
  "username": "gogodive",
  "followers_count": 1234,
  "fetched_at": "2026-07-11T07:00:12+09:00",
  "posts": [
    {
      "media_id": "17900000000000000",
      "caption": "캡션 앞 120자",
      "media_type": "IMAGE",
      "media_product_type": "FEED",
      "permalink": "https://www.instagram.com/p/XXXX/",
      "thumbnail": "https://scontent.cdninstagram.com/...",
      "posted_at": "2026-07-01T09:00:00+0000",
      "frozen": false,
      "metrics": {"views": 1000, "reach": 800, "likes": 50, "comments": 3, "saved": 12, "shares": 4, "total_interactions": 69},
      "metrics_updated_at": "2026-07-11T07:00:12+09:00"
    }
  ]
}
```

`posts`는 최신순, 최대 120개. `frozen=true` 인 게시물의 `metrics`는 마지막 갱신값 그대로 유지된다.

## File Structure

```
ig-feed-dashboard/
├── .github/workflows/daily.yml   # Task 5 — cron + 수동실행 + Pages 배포
├── config.yaml                    # Task 3 — 브랜드/계정 목록, 상수
├── requirements.txt               # Task 1
├── .gitignore                     # Task 1
├── src/
│   ├── __init__.py                # Task 1
│   ├── merge.py                   # Task 1 — 30일 동결 병합 (순수 함수)
│   ├── instagram.py               # Task 2 — Graph API 클라이언트
│   ├── collect.py                 # Task 3 — 계정별 수집 오케스트레이션
│   ├── render.py                  # Task 4 — HTML 생성
│   ├── template.html              # Task 4 — Jinja2 템플릿
│   └── main.py                    # Task 5 — 엔트리포인트
├── data/                          # Actions가 커밋 (계정별 JSON)
├── site/                          # 생성물 (gitignore, Pages 아티팩트로 배포)
├── tests/
│   ├── test_merge.py              # Task 1
│   ├── test_instagram.py          # Task 2
│   ├── test_collect.py            # Task 3
│   └── test_render.py             # Task 4
└── README.md                      # Task 5 — 셋업 가이드
```

---

### Task 1: 프로젝트 골격 + 30일 동결 병합 로직 (`src/merge.py`)

**Files:**
- Create: `requirements.txt`, `.gitignore`, `src/__init__.py`, `src/merge.py`
- Test: `tests/test_merge.py`

**Interfaces:**
- Produces: `merge.merge_posts(stored_posts: list[dict], fresh_media: list[dict], fresh_insights: dict[str, dict], now: datetime, freeze_days: int = 30, limit: int = 120) -> list[dict]`
  - `fresh_media` 항목은 Graph API `/media` 응답 그대로 (`id`, `caption`, `media_type`, `media_product_type`, `permalink`, `timestamp`, `media_url`, `thumbnail_url`)
  - 반환은 위 데이터 모델의 `posts` 배열 형식
- Produces: `merge.is_frozen(posted_at: str, now: datetime, freeze_days: int = 30) -> bool`

- [ ] **Step 1: 골격 파일 생성**

`requirements.txt`:
```
requests>=2.32
Jinja2>=3.1
PyYAML>=6.0
pytest>=8.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
site/
.env
.DS_Store
```

`src/__init__.py`: 빈 파일.

가상환경 및 설치:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_merge.py`:
```python
from datetime import datetime, timezone

from src.merge import is_frozen, merge_posts

NOW = datetime(2026, 7, 11, 7, 0, 0, tzinfo=timezone.utc)


def media(mid, ts, **kw):
    base = {
        "id": mid,
        "caption": "캡션",
        "media_type": "IMAGE",
        "media_product_type": "FEED",
        "permalink": f"https://instagram.com/p/{mid}/",
        "media_url": f"https://cdn/{mid}.jpg",
        "timestamp": ts,
    }
    base.update(kw)
    return base


def test_is_frozen_boundary():
    assert is_frozen("2026-06-01T00:00:00+0000", NOW) is True   # 40일 전
    assert is_frozen("2026-07-01T00:00:00+0000", NOW) is False  # 10일 전


def test_recent_post_gets_fresh_metrics():
    fresh = [media("m1", "2026-07-01T00:00:00+0000")]
    insights = {"m1": {"likes": 10, "views": 100}}
    out = merge_posts([], fresh, insights, NOW)
    assert out[0]["metrics"] == {"likes": 10, "views": 100}
    assert out[0]["frozen"] is False
    assert out[0]["metrics_updated_at"] is not None


def test_old_post_keeps_stored_metrics_frozen():
    stored = [{
        "media_id": "m1",
        "metrics": {"likes": 999},
        "metrics_updated_at": "2026-07-01T07:00:00+09:00",
    }]
    fresh = [media("m1", "2026-05-01T00:00:00+0000",
                   media_url="https://cdn/new-url.jpg")]
    out = merge_posts(stored, fresh, {}, NOW)
    assert out[0]["frozen"] is True
    assert out[0]["metrics"] == {"likes": 999}          # 동결값 유지
    assert out[0]["metrics_updated_at"] == "2026-07-01T07:00:00+09:00"
    assert out[0]["thumbnail"] == "https://cdn/new-url.jpg"  # 썸네일은 갱신


def test_video_uses_thumbnail_url():
    fresh = [media("m1", "2026-07-01T00:00:00+0000",
                   media_type="VIDEO",
                   thumbnail_url="https://cdn/thumb.jpg")]
    out = merge_posts([], fresh, {}, NOW)
    assert out[0]["thumbnail"] == "https://cdn/thumb.jpg"


def test_post_missing_from_fresh_is_dropped():
    stored = [{"media_id": "gone", "metrics": {}, "metrics_updated_at": None}]
    out = merge_posts(stored, [media("m1", "2026-07-01T00:00:00+0000")], {}, NOW)
    assert [p["media_id"] for p in out] == ["m1"]


def test_limit_120():
    fresh = [media(f"m{i}", "2026-07-01T00:00:00+0000") for i in range(150)]
    out = merge_posts([], fresh, {}, NOW)
    assert len(out) == 120


def test_caption_truncated_to_120_chars():
    fresh = [media("m1", "2026-07-01T00:00:00+0000", caption="가" * 500)]
    out = merge_posts([], fresh, {}, NOW)
    assert len(out[0]["caption"]) == 120
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `pytest tests/test_merge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.merge'`

- [ ] **Step 4: 최소 구현 작성**

`src/merge.py`:
```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_merge.py -v`
Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt .gitignore src/__init__.py src/merge.py tests/test_merge.py
git commit -m "feat: 30일 동결 병합 로직 + 프로젝트 골격"
```

---

### Task 2: Graph API 클라이언트 (`src/instagram.py`)

**Files:**
- Create: `src/instagram.py`
- Test: `tests/test_instagram.py`

**Interfaces:**
- Produces: `InstagramClient(access_token: str, version: str = "v23.0", timeout: int = 30)`
  - `.list_pages_with_ig() -> list[dict]` — `[{page_id, page_name, ig_user_id, ig_username}, ...]`
  - `.get_account(ig_user_id: str) -> dict` — `{username, followers_count, media_count}`
  - `.get_recent_media(ig_user_id: str, limit: int = 120) -> list[dict]` — 페이지네이션 따라가며 최대 limit개
  - `.get_media_insights(media_id: str, product_type: str) -> dict[str, Any]` — `{metric: value}`, 미지원 지표는 자동 제외
- Produces: `GraphAPIError(status: int, body: str)` 예외

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_instagram.py`:
```python
import json

import pytest

from src.instagram import GraphAPIError, InstagramClient


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_insights_retries_without_unsupported_metric(monkeypatch):
    """views 지표가 (#100) 으로 거부되면 views 만 빼고 재시도한다."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params["metric"])
        if "views" in params["metric"]:
            return FakeResponse(400, {"error": {
                "message": "(#100) metric[0] must be one of the following values: ... views is not supported"}})
        return FakeResponse(200, {"data": [
            {"name": "reach", "values": [{"value": 800}]},
            {"name": "likes", "values": [{"value": 50}]},
        ]})

    monkeypatch.setattr("src.instagram.requests.get", fake_get)
    client = InstagramClient("token")
    out = client.get_media_insights("m1", "FEED")
    assert out == {"reach": 800, "likes": 50}
    assert len(calls) == 2
    assert "views" not in calls[1]


def test_insights_returns_empty_on_unrecoverable_error(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResponse(400, {"error": {"message": "Unsupported get request"}})

    monkeypatch.setattr("src.instagram.requests.get", fake_get)
    client = InstagramClient("token")
    assert client.get_media_insights("m1", "FEED") == {}


def test_get_recent_media_follows_pagination(monkeypatch):
    page1 = {"data": [{"id": f"m{i}"} for i in range(100)],
             "paging": {"next": "https://graph.facebook.com/next"}}
    page2 = {"data": [{"id": f"m{i}"} for i in range(100, 200)]}

    def fake_get(url, params=None, timeout=None):
        return FakeResponse(200, page2 if url.endswith("/next") else page1)

    monkeypatch.setattr("src.instagram.requests.get", fake_get)
    client = InstagramClient("token")
    out = client.get_recent_media("igid", limit=120)
    assert len(out) == 120
    assert out[0]["id"] == "m0" and out[-1]["id"] == "m119"


def test_get_raises_graph_api_error(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResponse(500, {"error": {"message": "boom"}})

    monkeypatch.setattr("src.instagram.requests.get", fake_get)
    client = InstagramClient("token")
    with pytest.raises(GraphAPIError):
        client.get_account("igid")
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `pytest tests/test_instagram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.instagram'`

- [ ] **Step 3: 구현 작성**

`src/instagram.py`:
```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_instagram.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/instagram.py tests/test_instagram.py
git commit -m "feat: Graph API 클라이언트 (페이지네이션 + 지표 fallback)"
```

---

### Task 3: 수집 오케스트레이션 (`src/collect.py` + `config.yaml`)

**Files:**
- Create: `config.yaml`, `src/collect.py`, `data/.gitkeep`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `InstagramClient` (Task 2), `merge_posts`/`is_frozen` (Task 1)
- Produces: `collect.collect_all(client, config: dict, data_dir: Path, now: datetime) -> list[dict]`
  - 반환: 계정별 결과 dict 목록 (데이터 모델의 최상위 구조). 실패 계정은 기존 JSON 내용 그대로 반환
  - 부수효과: `data/<username>.json` 갱신 (실패 계정은 파일 유지)
- Produces: `collect.load_config(path: str | Path) -> dict`

- [ ] **Step 1: config.yaml 작성**

```yaml
brands:
  - name: 고고다이브
    username: gogodive
  - name: 인투더블루
    username: intotheblue_store
  - name: 라세린
    username: laserin_swim
  - name: 시크릿스
    username: secrets__fit

graph_api:
  version: "v23.0"

display_limit: 120
freeze_days: 30
```

`data/.gitkeep`: 빈 파일 (디렉터리 유지용).

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_collect.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

from src.collect import collect_all

NOW = datetime(2026, 7, 11, 7, 0, 0, tzinfo=timezone.utc)

CONFIG = {
    "brands": [
        {"name": "브랜드A", "username": "brand_a"},
        {"name": "브랜드B", "username": "brand_b"},
    ],
    "display_limit": 120,
    "freeze_days": 30,
}


class FakeClient:
    """brand_a 는 정상, brand_b 는 계정 조회에서 실패하는 가짜 클라이언트."""

    def list_pages_with_ig(self):
        return [
            {"page_id": "p1", "page_name": "A", "ig_user_id": "ig_a", "ig_username": "brand_a"},
            {"page_id": "p2", "page_name": "B", "ig_user_id": "ig_b", "ig_username": "brand_b"},
        ]

    def get_account(self, ig_user_id):
        if ig_user_id == "ig_b":
            raise RuntimeError("계정 조회 실패")
        return {"username": "brand_a", "followers_count": 500, "media_count": 2}

    def get_recent_media(self, ig_user_id, limit=120):
        return [
            {"id": "recent", "caption": "새 글", "media_type": "IMAGE",
             "media_product_type": "FEED", "permalink": "https://ig/p/recent/",
             "media_url": "https://cdn/recent.jpg",
             "timestamp": "2026-07-10T00:00:00+0000"},
            {"id": "old", "caption": "옛 글", "media_type": "IMAGE",
             "media_product_type": "FEED", "permalink": "https://ig/p/old/",
             "media_url": "https://cdn/old.jpg",
             "timestamp": "2026-01-01T00:00:00+0000"},
        ]

    def get_media_insights(self, media_id, product_type):
        assert media_id != "old", "30일 지난 게시물엔 인사이트를 호출하면 안 됨"
        return {"likes": 5, "views": 50}


def test_collect_all(tmp_path: Path):
    # brand_b 는 이전 실행 데이터가 있는 상태
    prev_b = {"brand": "브랜드B", "username": "brand_b", "followers_count": 100,
              "fetched_at": "2026-07-10T07:00:00+09:00", "posts": []}
    (tmp_path / "brand_b.json").write_text(json.dumps(prev_b), encoding="utf-8")
    # brand_a 의 old 게시물엔 동결값이 저장돼 있음
    prev_a = {"brand": "브랜드A", "username": "brand_a", "followers_count": 400,
              "fetched_at": "2026-07-10T07:00:00+09:00",
              "posts": [{"media_id": "old", "metrics": {"likes": 77},
                         "metrics_updated_at": "2026-01-31T07:00:00+09:00"}]}
    (tmp_path / "brand_a.json").write_text(json.dumps(prev_a), encoding="utf-8")

    results = collect_all(FakeClient(), CONFIG, tmp_path, NOW)

    a = next(r for r in results if r["username"] == "brand_a")
    assert a["followers_count"] == 500
    assert a["posts"][0]["media_id"] == "recent"
    assert a["posts"][0]["metrics"] == {"likes": 5, "views": 50}
    assert a["posts"][1]["frozen"] is True
    assert a["posts"][1]["metrics"] == {"likes": 77}  # 동결값 유지

    # 실패한 brand_b 는 기존 데이터 그대로
    b = next(r for r in results if r["username"] == "brand_b")
    assert b["fetched_at"] == "2026-07-10T07:00:00+09:00"

    # 파일도 갱신됨
    saved = json.loads((tmp_path / "brand_a.json").read_text(encoding="utf-8"))
    assert saved["posts"][0]["media_id"] == "recent"


def test_collect_unknown_username_keeps_previous(tmp_path: Path):
    """토큰으로 못 찾는 계정(페이지 미연결)은 실패 처리하고 이전 데이터 유지."""
    cfg = {"brands": [{"name": "없는계정", "username": "nope"}],
           "display_limit": 120, "freeze_days": 30}
    results = collect_all(FakeClient(), cfg, tmp_path, NOW)
    assert results[0]["username"] == "nope"
    assert results[0]["posts"] == []
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `pytest tests/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collect'`

- [ ] **Step 4: 구현 작성**

`src/collect.py`:
```python
"""계정별 수집 오케스트레이션.

계정 하나가 실패해도 나머지는 진행하고, 실패 계정은 기존 JSON 을 유지한다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import yaml

from src.merge import is_frozen, merge_posts

log = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_previous(data_dir: Path, username: str) -> dict:
    p = data_dir / f"{username}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"username": username, "followers_count": None,
            "fetched_at": None, "posts": []}


def _collect_account(client, brand: dict, ig_user_id: str,
                     prev: dict, config: dict, now: datetime) -> dict:
    limit = config.get("display_limit", 120)
    freeze_days = config.get("freeze_days", 30)

    account = client.get_account(ig_user_id)
    media = client.get_recent_media(ig_user_id, limit=limit)

    insights: dict[str, dict] = {}
    for m in media:
        if not is_frozen(m["timestamp"], now, freeze_days):
            insights[m["id"]] = client.get_media_insights(
                m["id"], m.get("media_product_type", "FEED"))

    posts = merge_posts(prev.get("posts", []), media, insights, now,
                        freeze_days=freeze_days, limit=limit)
    return {
        "brand": brand["name"],
        "username": brand["username"],
        "followers_count": account.get("followers_count"),
        "fetched_at": now.isoformat(),
        "posts": posts,
    }


def collect_all(client, config: dict, data_dir: Path, now: datetime) -> list[dict]:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    ig_ids = {p["ig_username"]: p["ig_user_id"]
              for p in client.list_pages_with_ig() if p.get("ig_user_id")}

    results: list[dict] = []
    for brand in config["brands"]:
        username = brand["username"]
        prev = _load_previous(data_dir, username)
        prev.setdefault("brand", brand["name"])
        try:
            ig_user_id = ig_ids.get(username)
            if not ig_user_id:
                raise LookupError(
                    f"'{username}' 계정을 찾지 못함 — 페이스북 페이지 연결/권한 확인 필요")
            result = _collect_account(client, brand, ig_user_id, prev, config, now)
            (data_dir / f"{username}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(result)
        except Exception:
            log.exception("%s 수집 실패 — 이전 데이터 유지", username)
            results.append(prev)
    return results
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_collect.py -v`
Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add config.yaml src/collect.py tests/test_collect.py data/.gitkeep
git commit -m "feat: 계정별 수집 오케스트레이션 (부분 실패 허용)"
```

---

### Task 4: HTML 렌더러 (`src/render.py` + `src/template.html`)

**Files:**
- Create: `src/render.py`, `src/template.html`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: Task 3 의 계정 결과 dict 목록
- Produces: `render.render_html(accounts: list[dict], generated_at: datetime) -> str`
  - `generated_at` 은 KST aware datetime. 반환값은 완성된 HTML 문자열

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render.py`:
```python
from datetime import datetime, timezone, timedelta

from src.render import render_html

KST = timezone(timedelta(hours=9))
GENERATED = datetime(2026, 7, 11, 7, 0, tzinfo=KST)

ACCOUNTS = [{
    "brand": "고고다이브",
    "username": "gogodive",
    "followers_count": 1234,
    "fetched_at": "2026-07-11T07:00:00+09:00",
    "posts": [
        {"media_id": "m1", "caption": "신상 입고", "media_type": "IMAGE",
         "media_product_type": "FEED", "permalink": "https://ig/p/m1/",
         "thumbnail": "https://cdn/m1.jpg",
         "posted_at": "2026-07-05T00:00:00+0000", "frozen": False,
         "metrics": {"views": 1500, "likes": 120, "comments": 8,
                     "saved": 30, "shares": 5},
         "metrics_updated_at": "2026-07-11T07:00:00+09:00"},
        {"media_id": "m2", "caption": "지난 글", "media_type": "VIDEO",
         "media_product_type": "REELS", "permalink": "https://ig/p/m2/",
         "thumbnail": "https://cdn/m2.jpg",
         "posted_at": "2026-05-01T00:00:00+0000", "frozen": True,
         "metrics": {"views": 99999, "likes": 3000, "comments": 40,
                     "saved": 500, "shares": 100},
         "metrics_updated_at": "2026-05-31T07:00:00+09:00"},
    ],
}, {
    "brand": "라세린",
    "username": "laserin_swim",
    "followers_count": None,
    "fetched_at": None,   # 아직 한 번도 수집 안 된 계정
    "posts": [],
}]


def test_render_contains_core_elements():
    html = render_html(ACCOUNTS, GENERATED)
    assert '<meta name="robots" content="noindex">' in html
    assert "고고다이브" in html and "라세린" in html
    assert "https://cdn/m1.jpg" in html
    assert "https://ig/p/m1/" in html
    assert "1,500" in html          # 천단위 콤마
    assert "2026-07-05" in html     # 게시일
    assert "확정" in html            # 동결 배지
    assert "집계중" in html          # 집계중 배지
    assert "D+5" in html  # 7/5 09:00 KST 게시 → 7/11 07:00 KST 기준 5일 22시간 경과
    assert "2026-07-11 07:00" in html  # 갱신 시각


def test_render_escapes_caption():
    accounts = [dict(ACCOUNTS[0])]
    accounts[0] = {**ACCOUNTS[0],
                   "posts": [{**ACCOUNTS[0]["posts"][0],
                              "caption": "<script>alert(1)</script>"}]}
    html = render_html(accounts, GENERATED)
    assert "<script>alert(1)</script>" not in html


def test_render_empty_account_shows_placeholder():
    html = render_html(ACCOUNTS, GENERATED)
    assert "아직 수집된 데이터가 없습니다" in html
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.render'`

- [ ] **Step 3: 렌더러 구현**

`src/render.py`:
```python
"""수집 결과 → 단일 HTML 대시보드."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

KST = timezone(timedelta(hours=9))
_TEMPLATE_DIR = Path(__file__).parent


def _fmt_num(v) -> str:
    if v is None:
        return "–"
    return f"{v:,}"


def _fmt_date(ts: str) -> str:
    return ts[:10] if ts else ""


def _days_since(posted_at: str, generated_at: datetime) -> int:
    posted = datetime.fromisoformat(posted_at.replace("+0000", "+00:00"))
    return (generated_at - posted).days


def render_html(accounts: list[dict], generated_at: datetime) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["num"] = _fmt_num
    env.filters["date"] = _fmt_date
    tpl = env.get_template("template.html")
    for acc in accounts:
        for p in acc.get("posts", []):
            p["_days"] = _days_since(p["posted_at"], generated_at)
    return tpl.render(
        accounts=accounts,
        generated_label=generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
    )
```

- [ ] **Step 4: 템플릿 작성**

`src/template.html`:
```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>자사 인스타그램 데일리 피드</title>
<style>
  :root { --line:#dbdbdb; --sub:#737373; --accent:#0095f6; }
  * { box-sizing:border-box; margin:0; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
         background:#fafafa; color:#262626; }
  header { background:#fff; border-bottom:1px solid var(--line); padding:14px 16px;
           display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  header h1 { font-size:17px; }
  header .updated { color:var(--sub); font-size:12px; }
  nav { background:#fff; border-bottom:1px solid var(--line); display:flex;
        overflow-x:auto; position:sticky; top:0; }
  nav button { flex:1; min-width:110px; padding:12px 8px; border:0; background:none;
               font-size:14px; cursor:pointer; border-bottom:2px solid transparent; color:var(--sub); }
  nav button.active { color:#262626; font-weight:600; border-bottom-color:#262626; }
  .meta { padding:12px 16px; font-size:13px; color:var(--sub); }
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px;
          max-width:900px; margin:0 auto; padding:0 16px 40px; }
  .card { background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
  .thumb { position:relative; display:block; aspect-ratio:1/1; background:#eee; }
  .thumb img { width:100%; height:100%; object-fit:cover; display:block; }
  .badge { position:absolute; top:8px; left:8px; font-size:11px; padding:2px 8px;
           border-radius:10px; color:#fff; }
  .badge.live { background:var(--accent); }
  .badge.frozen { background:#8e8e8e; }
  .info { padding:10px 12px; }
  .date { font-size:12px; color:var(--sub); }
  .caption { font-size:13px; margin:4px 0 8px; overflow:hidden; white-space:nowrap;
             text-overflow:ellipsis; }
  .metrics { display:flex; flex-wrap:wrap; gap:8px 12px; font-size:12px; }
  .metrics span b { font-weight:600; }
  .empty { text-align:center; color:var(--sub); padding:60px 0; grid-column:1/-1; }
  .stale { background:#fff8e1; border:1px solid #ffe082; border-radius:6px;
           margin:12px 16px; padding:8px 12px; font-size:12px; color:#8d6e00; }
  section { display:none; } section.active { display:block; }
  @media (max-width:600px){ .grid{ grid-template-columns:repeat(3,1fr); gap:4px; padding:0 4px 40px; }
    .info{ padding:6px 8px; } .caption{ display:none; }
    .metrics{ gap:4px 8px; font-size:10px; } }
</style>
</head>
<body>
<header>
  <h1>자사 인스타그램 데일리 피드</h1>
  <span class="updated">마지막 갱신: {{ generated_label }} (매일 07:00 자동 갱신)</span>
</header>
<nav>
  {% for acc in accounts %}
  <button data-tab="{{ loop.index0 }}"{% if loop.first %} class="active"{% endif %}>{{ acc.brand }}</button>
  {% endfor %}
</nav>
{% for acc in accounts %}
<section id="tab-{{ loop.index0 }}"{% if loop.first %} class="active"{% endif %}>
  <div class="meta">@{{ acc.username }}
    {% if acc.followers_count %}· 팔로워 {{ acc.followers_count | num }}{% endif %}</div>
  {% if acc.fetched_at and acc.fetched_at[:10] != generated_label[:10] %}
  <div class="stale">⚠️ 이 계정은 {{ acc.fetched_at[:10] }} 데이터입니다 (최근 수집 실패)</div>
  {% endif %}
  <div class="grid">
    {% for p in acc.posts %}
    <div class="card">
      <a class="thumb" href="{{ p.permalink }}" target="_blank" rel="noopener">
        {% if p.frozen %}<span class="badge frozen">확정</span>
        {% else %}<span class="badge live">집계중 D+{{ p._days }}</span>{% endif %}
        <img src="{{ p.thumbnail }}" alt="" loading="lazy">
      </a>
      <div class="info">
        <div class="date">{{ p.posted_at | date }}</div>
        <div class="caption">{{ p.caption }}</div>
        <div class="metrics">
          <span>▶ <b>{{ p.metrics.views | num }}</b></span>
          <span>❤️ <b>{{ p.metrics.likes | num }}</b></span>
          <span>💬 <b>{{ p.metrics.comments | num }}</b></span>
          <span>🔖 <b>{{ p.metrics.saved | num }}</b></span>
          <span>↗ <b>{{ p.metrics.shares | num }}</b></span>
        </div>
      </div>
    </div>
    {% else %}
    <div class="empty">아직 수집된 데이터가 없습니다</div>
    {% endfor %}
  </div>
</section>
{% endfor %}
<script>
document.querySelectorAll("nav button").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll("section").forEach(s => s.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});
</script>
</body>
</html>
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_render.py -v`
Expected: 3 passed

주의: `metrics.views` 가 없는 dict 에서도 Jinja2 는 undefined → `num` 필터에서 None 처리되어 "–" 로 출력되어야 한다. 실패하면 `_fmt_num` 시작에 `if v is None or v == ""` 대신 Jinja Undefined 체크 추가:
```python
from jinja2 import Undefined
def _fmt_num(v) -> str:
    if v is None or isinstance(v, Undefined):
        return "–"
    return f"{v:,}"
```

- [ ] **Step 6: 눈으로 확인 (수동 스냅샷)**

```bash
python - <<'EOF'
from datetime import datetime, timezone, timedelta
from tests.test_render import ACCOUNTS
from src.render import render_html
html = render_html(ACCOUNTS, datetime(2026,7,11,7,0,tzinfo=timezone(timedelta(hours=9))))
open("/tmp/preview.html","w").write(html)
print("open /tmp/preview.html")
EOF
```
브라우저로 열어 3열 그리드·탭·배지가 보이는지 확인.

- [ ] **Step 7: 커밋**

```bash
git add src/render.py src/template.html tests/test_render.py
git commit -m "feat: 인스타 피드형 HTML 대시보드 렌더러"
```

---

### Task 5: 엔트리포인트 + GitHub Actions + README

**Files:**
- Create: `src/main.py`, `.github/workflows/daily.yml`, `README.md`

**Interfaces:**
- Consumes: `load_config`/`collect_all` (Task 3), `render_html` (Task 4), `InstagramClient` (Task 2)
- Produces: `python -m src.main` — 수집 → `data/*.json` 갱신 → `site/index.html` 생성. 환경변수 `META_ACCESS_TOKEN` 필수

- [ ] **Step 1: main.py 작성**

`src/main.py`:
```python
"""엔트리포인트: 수집 → data/*.json 갱신 → site/index.html 생성."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collect import collect_all, load_config
from src.instagram import InstagramClient
from src.render import render_html

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        print("META_ACCESS_TOKEN 환경변수가 없습니다", file=sys.stderr)
        return 1

    config = load_config(ROOT / "config.yaml")
    client = InstagramClient(token, version=config.get("graph_api", {}).get("version", "v23.0"))
    now = datetime.now(KST)

    accounts = collect_all(client, config, ROOT / "data", now)

    site = ROOT / "site"
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text(render_html(accounts, now), encoding="utf-8")
    print(f"완료: {len(accounts)}개 계정 → site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 로컬 스모크 테스트 (토큰 없이 실패 경로 확인)**

Run: `python -m src.main`
Expected: exit code 1, stderr에 "META_ACCESS_TOKEN 환경변수가 없습니다"

Run: `pytest -v`
Expected: 전체 테스트 passed (merge 7 + instagram 4 + collect 2 + render 3 = 16)

- [ ] **Step 3: GitHub Actions workflow 작성**

`.github/workflows/daily.yml`:
```yaml
name: daily-feed

on:
  schedule:
    - cron: "0 22 * * *"   # 22:00 UTC = 07:00 KST
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: daily-feed
  cancel-in-progress: false

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - run: pip install -r requirements.txt

      - name: Collect and render
        env:
          META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
        run: python -m src.main

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data
          git diff --cached --quiet || git commit -m "chore: daily data update"
          git push

      - uses: actions/configure-pages@v5

      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 4: README 작성**

`README.md`:
```markdown
# 자사 인스타그램 데일리 피드 대시보드

자사 인스타 4개 계정의 피드를 매일 아침 7시(KST)에 수집해
인스타 피드 모양의 HTML 대시보드로 GitHub Pages 에 배포합니다.

- 계정당 최근 **120개** 게시물 표시
- 성과(조회·좋아요·댓글·저장·공유)는 **게시 후 30일까지만** 매일 갱신, 이후 동결(`확정` 배지)
- 계정 목록·표시 개수는 `config.yaml` 에서 수정

## 일회성 셋업

### 1. 인스타 계정 준비
1. 4개 계정 모두 비즈니스 계정인지 확인 (완료됨)
2. 각 계정을 페이스북 페이지에 연결 (인스타 앱 → 설정 → 페이지 연결)
3. 4개 페이지를 하나의 비즈니스 관리자(business.facebook.com)에 추가

### 2. Meta 앱 + 토큰
1. https://developers.facebook.com → 앱 생성 (유형: Business)
2. 비즈니스 관리자 → 시스템 사용자 생성 → 앱과 페이지 자산 할당
3. 시스템 사용자 토큰 발급 — scope:
   `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`, `pages_show_list`
4. 이 토큰은 만료되지 않음. 절대 커밋하지 말 것

### 3. GitHub
1. 이 저장소를 GitHub 에 push (public — Pages 무료 사용 조건)
2. Settings → Secrets and variables → Actions → `META_ACCESS_TOKEN` 등록
3. Settings → Pages → Source: **GitHub Actions** 선택
4. Actions 탭 → daily-feed → **Run workflow** 로 첫 실행
5. 배포 URL 확인 → 노션에 링크 등록

## 로컬 실행 (검증용)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export META_ACCESS_TOKEN="..."
python -m src.main
open site/index.html
```

## 테스트

```bash
pytest -v
```

## 트러블슈팅
- **계정이 안 잡힘** — 해당 인스타 계정이 페이지에 연결됐는지, 그 페이지가 시스템 사용자에 할당됐는지 확인
- **(#100) 지표 오류** — 자동으로 해당 지표만 제외하고 재시도함. 노출이 빈 값이면 정상 동작
- **실행 실패 메일** — GitHub 이 workflow 실패 시 자동 발송. Actions 탭에서 로그 확인
```

- [ ] **Step 5: 최종 확인 + 커밋**

Run: `pytest -v`
Expected: 16 passed

```bash
git add src/main.py .github/workflows/daily.yml README.md
git commit -m "feat: 엔트리포인트 + 데일리 Actions 워크플로 + 셋업 가이드"
```

---

## Task 6 (코드 외): 배포 셋업 체크리스트

코드 구현이 아닌 일회성 셋업. 사용자와 함께 진행한다.

- [ ] 인스타 4개 계정 ↔ FB 페이지 연결 + 비즈니스 관리자 묶기 (사용자)
- [ ] Meta 앱 생성 + 시스템 사용자 토큰 발급 (사용자, README 2번 절차 안내)
- [ ] GitHub 저장소 생성(public) + push
- [ ] `META_ACCESS_TOKEN` Secret 등록 (사용자 — 토큰을 Claude 에게 전달하지 않고 직접 등록)
- [ ] Pages Source = GitHub Actions 설정
- [ ] workflow_dispatch 수동 실행 → 대시보드 URL 확인
- [ ] 노션 상위 페이지 + 계정 페이지 4곳에 대시보드 링크 삽입 (Claude)
