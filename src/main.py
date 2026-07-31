"""엔트리포인트: 수집 → data/*.json 갱신 → site/index.html 생성."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collect import collect_all, load_config
from src.instagram import InstagramClient
from src.notion_status import build_status, update_callout
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

    icon, status = build_status(accounts, now)
    print(f"완료: {icon} {status} → site/index.html")

    # 노션 상태 기록은 부가 기능 — 실패해도 수집/배포를 막지 않는다
    notion_token = os.environ.get("NOTION_TOKEN")
    page_id = config.get("notion", {}).get("hub_page_id")
    if notion_token and page_id:
        if update_callout(notion_token, page_id, icon, status):
            print("노션 상태 콜아웃 갱신 완료")
    else:
        print("NOTION_TOKEN 또는 hub_page_id 없음 — 노션 상태 기록 건너뜀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
