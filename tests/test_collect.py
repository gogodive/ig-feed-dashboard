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


def test_failed_insights_keeps_stored_metrics(tmp_path: Path):
    """인사이트 호출이 실패(빈 dict)해도 저장된 지표를 {} 로 덮어쓰면 안 된다."""

    class EmptyInsightsClient(FakeClient):
        def get_media_insights(self, media_id, product_type):
            return {}  # API 실패 시 클라이언트는 빈 dict 반환

    prev = {"brand": "브랜드A", "username": "brand_a", "followers_count": 400,
            "fetched_at": "2026-07-10T07:00:00+09:00",
            "posts": [{"media_id": "recent", "metrics": {"likes": 42},
                       "metrics_updated_at": "2026-07-10T07:00:00+09:00"}]}
    (tmp_path / "brand_a.json").write_text(json.dumps(prev), encoding="utf-8")

    cfg = {"brands": [{"name": "브랜드A", "username": "brand_a"}],
           "display_limit": 120, "freeze_days": 30}
    results = collect_all(EmptyInsightsClient(), cfg, tmp_path, NOW)

    a = results[0]
    recent = next(p for p in a["posts"] if p["media_id"] == "recent")
    assert recent["metrics"] == {"likes": 42}  # 이전 지표 유지
    assert recent["metrics_updated_at"] == "2026-07-10T07:00:00+09:00"
