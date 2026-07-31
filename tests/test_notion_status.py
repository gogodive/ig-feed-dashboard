import json
from datetime import datetime, timedelta, timezone

from src.notion_status import build_status, update_callout

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 7, 14, 7, 0, tzinfo=KST)


def acc(name, fetched_at, n_posts=100):
    return {"brand": name, "username": name, "fetched_at": fetched_at,
            "posts": [{"media_id": str(i)} for i in range(n_posts)]}


def test_status_all_success():
    accounts = [acc("A", NOW.isoformat(), 120), acc("B", NOW.isoformat(), 43)]
    icon, text = build_status(accounts, NOW)
    assert icon == "✅"
    assert "2026-07-14 07:00" in text
    assert "2개 계정" in text
    assert "163" in text  # 게시물 합계


def test_status_partial_failure_names_the_account():
    accounts = [acc("A", NOW.isoformat()),
                acc("딥바이브", "2026-07-13T07:00:00+09:00")]
    icon, text = build_status(accounts, NOW)
    assert icon == "⚠️"
    assert "1/2" in text
    assert "딥바이브" in text


def test_status_total_failure():
    accounts = [acc("A", "2026-07-13T07:00:00+09:00"), acc("B", None)]
    icon, text = build_status(accounts, NOW)
    assert icon == "🚨"
    assert "0/2" in text


def test_status_treats_utc_same_instant_as_success():
    """fetched_at 이 UTC 표기라도 같은 시각이면 성공으로 본다."""
    accounts = [acc("A", "2026-07-13T22:00:00+00:00")]  # == 07-14 07:00 KST
    icon, _ = build_status(accounts, NOW)
    assert icon == "✅"


def test_update_callout_patches_first_callout_block(monkeypatch):
    calls = {}

    class Resp:
        def __init__(self, status, payload):
            self.status_code = status
            self._p = payload
            self.text = json.dumps(payload)

        def json(self):
            return self._p

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["get"] = url
        return Resp(200, {"results": [
            {"id": "para-1", "type": "paragraph"},
            {"id": "callout-1", "type": "callout"},
            {"id": "callout-2", "type": "callout"},
        ]})

    def fake_patch(url, headers=None, json=None, timeout=None):
        calls["patch_url"] = url
        calls["body"] = json
        return Resp(200, {})

    monkeypatch.setattr("src.notion_status.requests.get", fake_get)
    monkeypatch.setattr("src.notion_status.requests.patch", fake_patch)

    assert update_callout("tok", "page-id", "✅", "정상") is True
    assert "page-id" in calls["get"]
    assert calls["patch_url"].endswith("/blocks/callout-1")  # 첫 콜아웃만
    assert calls["body"]["callout"]["icon"]["emoji"] == "✅"
    assert calls["body"]["callout"]["rich_text"][0]["text"]["content"] == "정상"


def test_update_callout_returns_false_when_no_callout(monkeypatch):
    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"results": [{"id": "p", "type": "paragraph"}]}

    monkeypatch.setattr("src.notion_status.requests.get",
                        lambda *a, **k: Resp())
    assert update_callout("tok", "page-id", "✅", "정상") is False


def test_update_callout_returns_false_on_api_error(monkeypatch):
    class Resp:
        status_code = 401
        text = "unauthorized"

        def json(self):
            return {}

    monkeypatch.setattr("src.notion_status.requests.get",
                        lambda *a, **k: Resp())
    assert update_callout("tok", "page-id", "✅", "정상") is False
