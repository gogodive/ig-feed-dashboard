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


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("+0000", "+00:00"))


def _fmt_date(ts: str) -> str:
    if not ts:
        return ""
    return _parse_ts(ts).astimezone(KST).strftime("%Y-%m-%d")


def _days_since(posted_at: str, generated_at: datetime) -> int:
    return (generated_at - _parse_ts(posted_at)).days


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
        for p in acc.get("posts", []):
            p["_days"] = _days_since(p["posted_at"], generated_at)
    return tpl.render(
        accounts=accounts,
        generated_label=generated_at.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
    )
