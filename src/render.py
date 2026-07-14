"""수집 결과 → 단일 HTML 대시보드."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape, Undefined

KST = timezone(timedelta(hours=9))
_TEMPLATE_DIR = Path(__file__).parent

HOT_RATIO = 2.0          # 계정 중앙값 대비 이 배수 이상이면 🔥
HOT_RATIO_LABELED = 3.0  # 이 배수 이상이면 배수까지 표기 (🔥 4.2x)
HOT_MIN_POSTS = 5        # 조회수 있는 게시물이 이보다 적으면 표시 안 함


def _fmt_num(v) -> str:
    if v is None or isinstance(v, Undefined):
        return "–"
    return f"{v:,}"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("+0000", "+00:00"))


def _fmt_date(ts: str) -> str:
    if not ts:
        return ""
    return _parse_ts(ts).astimezone(KST).strftime("%Y-%m-%d")


def _days_since(posted_at: str, generated_at: datetime) -> int:
    return (generated_at - _parse_ts(posted_at)).days


def _annotate_hot(posts: list[dict]) -> None:
    """계정 내 조회수 중앙값 대비 배수로 히트 게시물에 _hot 라벨을 단다."""
    views = [p["metrics"].get("views") for p in posts]
    views = [v for v in views if isinstance(v, int) and v > 0]
    if len(views) < HOT_MIN_POSTS:
        return
    median = statistics.median(views)
    if median <= 0:
        return
    for p in posts:
        v = p["metrics"].get("views")
        if isinstance(v, int) and v / median >= HOT_RATIO:
            ratio = v / median
            p["_hot"] = f"🔥 {ratio:.1f}x" if ratio >= HOT_RATIO_LABELED else "🔥"


def _chart_payload(posts: list[dict]) -> dict | None:
    """산점도용 [게시일(KST), 조회수, 히트여부, 캡션] 목록. 데이터가 적으면 None."""
    pts = [
        [_fmt_date(p["posted_at"]), p["metrics"]["views"],
         1 if p.get("_hot") else 0, (p.get("caption") or "")[:30]]
        for p in posts
        if isinstance(p["metrics"].get("views"), int) and p["metrics"]["views"] > 0
    ]
    if len(pts) < HOT_MIN_POSTS:
        return None
    return {"median": statistics.median(x[1] for x in pts), "points": pts}


def render_html(accounts: list[dict], generated_at: datetime) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["num"] = _fmt_num
    env.filters["date"] = _fmt_date
    tpl = env.get_template("template.html")
    gen_date = generated_at.astimezone(KST).date()
    for acc in accounts:
        fetched = acc.get("fetched_at")
        acc["_stale_date"] = None
        if fetched:
            fdt = _parse_ts(fetched).astimezone(KST)
            if fdt.date() != gen_date:
                acc["_stale_date"] = fdt.strftime("%Y-%m-%d")
    charts: dict[int, dict] = {}
    for i, acc in enumerate(accounts):
        for p in acc.get("posts", []):
            p["_days"] = _days_since(p["posted_at"], generated_at)
        _annotate_hot(acc.get("posts", []))
        payload = _chart_payload(acc.get("posts", []))
        acc["_has_chart"] = payload is not None
        if payload:
            charts[i] = payload
    # "<" 를 이스케이프해 캡션의 </script> 로 스크립트가 닫히는 것을 방지
    chart_json = json.dumps(charts, ensure_ascii=False).replace("<", "\\u003c")
    return tpl.render(
        accounts=accounts,
        chart_json=chart_json,
        generated_label=generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
    )
