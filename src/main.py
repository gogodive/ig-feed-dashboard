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
