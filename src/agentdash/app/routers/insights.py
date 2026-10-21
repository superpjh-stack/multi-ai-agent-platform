"""D-07 비용 · 효율 `/insights` + API 3 — 담당 개발1 (spec.md v0.3 §7 D-07 · §6.3 · §8).

  GET /insights                                  예산 게이지 · 비용 추세 · 캐시 적중률 순위 (서버 렌더 표 + Chart.js 4.4.1)
  GET /api/v1/budget                             {"rows": budget.status(), "worst", "label"}
  GET /api/v1/trend?grain&from&to&group          {"rows": budget.trend(), …} — grain · group 이 틀리면 422
  GET /api/v1/efficiency?group&from&to           {"rows": budget.efficiency(), …}
모든 금액은 `[추정] API 정가 환산` (usage.ESTIMATE_LABEL). 한도는 config/budget.yaml 에서만 (null = 「한도 미설정」).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from agentdash.app.templating import render
from agentdash.core import budget as B
from agentdash.core import usage as U
from agentdash.db import conn

router = APIRouter()
OWNER = "개발1"
DAY_RE = r"^\d{4}-\d{2}-\d{2}$"
DEFAULT_DAYS = {"day": 30, "week": 26 * 7, "month": 365}
GRAIN_LABEL = {"day": "일", "week": "주 (월요일 시작)", "month": "월"}
EFF_LABEL = {"project": "프로젝트", "session": "세션 (자손 포함)", "agent": "에이전트 (자기만)"}
LEVEL_CLASS = {"ok": "st-DONE", "warn": "st-WAITING_INPUT", "over": "st-FAILED", "unset": "st-STALE",
               "no_records": "st-STALE"}
PERIOD_LABEL = {"day": "오늘", "month": "이번 달"}


def _con():
    return conn.connect(conn.init_db())


def _range(frm: str | None, to: str | None, days: int) -> tuple[str, str]:
    for v in (frm, to):
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(422, f"날짜 형식 YYYY-MM-DD: {v!r}") from None
    t = to or U.kst_today()
    f = frm or (datetime.strptime(t, "%Y-%m-%d") - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    return (f, t) if f <= t else (t, f)


# Query 객체는 경로마다 새로 만든다 — 한 객체를 매개변수 이름이 다른 두 경로가 같이 쓰면 별칭이 섞인다
def _grain_q():
    return Query("day", pattern="^(day|week|month)$")


def _tgroup_q():
    return Query("total", pattern="^(total|project)$")


def _egroup_q():
    return Query("project", pattern="^(project|session|agent)$")


@router.get("/api/v1/budget")
def budget_api():
    con = _con()
    try:
        rows = B.status(con)
    finally:
        con.close()
    return {"rows": rows, "worst": B.worst(rows), "label": U.ESTIMATE_LABEL, "levels": list(B.LEVELS)}


@router.get("/api/v1/trend")
def trend_api(grain: str = _grain_q(), frm: str | None = Query(None, alias="from"), to: str | None = None,
              group: str = _tgroup_q()):
    f, t = _range(frm, to, DEFAULT_DAYS[grain])
    con = _con()
    try:
        rows = B.trend(con, grain, f, t, group)
    finally:
        con.close()
    return {"grain": grain, "group": group, "from": f, "to": t, "rows": rows, "label": U.ESTIMATE_LABEL,
            "est_note": U.UNDERCOUNT_NOTE}


@router.get("/api/v1/efficiency")
def efficiency_api(group: str = _egroup_q(), frm: str | None = Query(None, alias="from"), to: str | None = None):
    f, t = _range(frm, to, 30)
    con = _con()
    try:
        rows = B.efficiency(con, group, f, t)
    finally:
        con.close()
    return {"group": group, "from": f, "to": t, "rows": rows, "label": U.ESTIMATE_LABEL}


def _money(v) -> str:
    return "—" if v is None else f"${v:,.2f}"


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


@router.get("/insights")
def insights_page(request: Request, grain: str = _grain_q(), frm: str | None = Query(None, alias="from"),
                  to: str | None = None, eff: str = _egroup_q()):
    f, t = _range(frm, to, DEFAULT_DAYS[grain])
    con = _con()
    try:
        cells = B.status(con)
        total = B.trend(con, grain, f, t, "total")
        by_project = B.trend(con, grain, f, t, "project")
        daily_hit = B.trend(con, "day", f, t, "total")
        eff_rows = B.efficiency(con, eff, f, t)
    finally:
        con.close()
    projects = sorted({r["project"] for r in by_project})
    buckets = [r["bucket"] for r in total]
    stack = {p: {r["bucket"]: r["cost_est_usd"] or 0 for r in by_project if r["project"] == p} for p in projects}
    chart = {
        "buckets": buckets,
        "rec": [r["cost_usd"] or 0 for r in total],
        "est": [r["cost_est_usd"] or 0 for r in total],
        "projects": [{"name": p, "data": [stack[p].get(b, 0) for b in buckets]} for p in projects],
        "hit_days": [r["bucket"] for r in daily_hit],
        "hit": [None if r["hit"] is None else round(r["hit"] * 100, 2) for r in daily_hit],
    }
    for c in cells:
        c["cls"] = LEVEL_CLASS[c["level"]]
        c["width"] = 0 if c["ratio"] is None else min(100.0, c["ratio"] * 100)
        c["pct"] = None if c["ratio"] is None else f"{c['ratio'] * 100:.0f} %"
    ctx = {"title": "비용 · 효율", "active": "/insights", "cells": cells, "worst": B.worst(cells),
           "grain": grain, "grains": GRAIN_LABEL, "frm": f, "to": t, "eff": eff, "effs": EFF_LABEL,
           "total": total, "eff_rows": eff_rows[:200], "eff_more": max(0, len(eff_rows) - 200), "chart": chart,
           "label": U.ESTIMATE_LABEL, "est_note": U.UNDERCOUNT_NOTE, "money": _money, "pct": _pct,
           "periods": PERIOD_LABEL, "fmt": lambda v: f"{v:,}" if isinstance(v, int) else v}
    return render(request, "insights.html", ctx)
