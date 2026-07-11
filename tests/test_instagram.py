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
