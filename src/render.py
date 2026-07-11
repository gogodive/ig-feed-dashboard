"""수집 결과 → 단일 HTML 대시보드."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape, Undefined

KST = timezone(timedelta(hours=9))
_TEMPLATE_DIR = Path(__file__).parent


def _fmt_num(v) -> str:
    if v is None or isinstance(v, Undefined):
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
