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

    stored_metrics = {p["media_id"]: p.get("metrics") for p in prev.get("posts", [])}
    insights: dict[str, dict] = {}
    for m in media:
        # 30일 이내는 매일 갱신, 동결 게시물은 저장 지표가 없을 때만 최초 1회 조회(백필)
        if not is_frozen(m["timestamp"], now, freeze_days) or not stored_metrics.get(m["id"]):
            ins = client.get_media_insights(
                m["id"], m.get("media_product_type", "FEED"))
            if ins:
                insights[m["id"]] = ins

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
