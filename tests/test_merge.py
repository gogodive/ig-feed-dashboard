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


def test_frozen_post_without_stored_metrics_accepts_backfill():
    """저장 지표가 없는 동결 게시물은 최초 1회 인사이트를 받아들인다(백필)."""
    fresh = [media("m1", "2026-01-01T00:00:00+0000")]  # 6개월 전
    insights = {"m1": {"likes": 300, "views": 9000}}
    out = merge_posts([], fresh, insights, NOW)
    assert out[0]["frozen"] is True
    assert out[0]["metrics"] == {"likes": 300, "views": 9000}
    assert out[0]["metrics_updated_at"] is not None


def test_frozen_post_with_stored_metrics_ignores_new_insights():
    """이미 지표가 저장된 동결 게시물은 새 인사이트가 와도 동결값을 유지한다."""
    stored = [{"media_id": "m1", "metrics": {"likes": 77},
               "metrics_updated_at": "2026-01-31T07:00:00+09:00"}]
    fresh = [media("m1", "2026-01-01T00:00:00+0000")]
    out = merge_posts(stored, fresh, {"m1": {"likes": 999}}, NOW)
    assert out[0]["metrics"] == {"likes": 77}
