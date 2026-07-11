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


def test_post_date_shown_in_kst():
    """UTC 20:00 게시 = KST 다음날 05:00 → KST 날짜로 표시되어야 한다."""
    acc = {**ACCOUNTS[0],
           "posts": [{**ACCOUNTS[0]["posts"][0],
                      "posted_at": "2026-07-04T20:00:00+0000"}]}
    html = render_html([acc], GENERATED)
    assert "2026-07-05" in html
    assert "2026-07-04" not in html


def test_stale_banner_only_when_kst_date_differs():
    """UTC 표기라도 같은 시각이면 stale 아님; KST 날짜가 다르면 stale."""
    same_instant = {**ACCOUNTS[0],
                    "fetched_at": "2026-07-10T22:00:00+00:00"}  # == 2026-07-11 07:00 KST
    old = {**ACCOUNTS[0], "brand": "옛날계정",
           "fetched_at": "2026-07-09T22:00:00+00:00"}  # == 2026-07-10 KST
    html = render_html([same_instant, old], GENERATED)
    assert html.count("최근 수집 실패") == 1
    assert "2026-07-10 데이터" in html
