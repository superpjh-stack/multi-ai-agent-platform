"""화면 D-01 관제판 · D-02 구성도 · D-03 에이전트 상세 — 담당 개발2 (goal.md §3.2). 질의는 routers/agents.py.

· `/` 관제판. `/?part=body` 는 갱신용 본문 조각(SSE 이벤트 뒤 · 15 초마다 다시 받는다).
· `/graph` 구성도 — 데이터는 `/api/v1/graph` (core/graph.py), 그리기는 Cytoscape.js 3.30.2 (CDN 고정 버전).
· `/agents/{key}` 상세. `/agents/{key}/raw` 원본 보기 조각 — 요청 때 원천 .jsonl 을 읽기 전용으로 읽어 응답으로만 보낸다.
  DB · 캐시 · 로그에 남기지 않는다(Cache-Control: no-store).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from agentdash.app.routers import agents as Q
from agentdash import settings
from agentdash.app.templating import render
from agentdash.core import budget
from agentdash.core import state as S
from agentdash.core.usage import ESTIMATE_LABEL
from agentdash.db import conn

router = APIRouter()
OWNER = "개발2"


_PERIOD_KO = {"day": "오늘", "month": "이번 달"}
_BAND_CLASS = {"over": "st-FAILED", "warn": "st-WAITING_PERMISSION"}    # spec §6.3: 0.8 부터 주황, 1.0 부터 빨강


def _pct(ratio: float) -> int:
    return math.floor(ratio * 100 + 1e-9)          # 99.9 % 를 100 % 로 올려 over 처럼 보이지 않게 내린다


def budget_band(con, now: datetime) -> dict | None:
    """D-01 맨 위 경고 띠 (spec v0.3 D-01) — warn · over 칸이 하나라도 있으면 그 칸 전부를 「오늘 전체 82 %」 꼴로,
    색은 budget.worst. 설정이 깨졌으면 숨기지 않고 오류 문구 (조용한 실패 금지)."""
    try:
        rows = budget.status(con, now)
    except settings.SettingsError as e:
        return {"cls": "st-FAILED", "error": str(e)[:200], "cells": []}
    w = budget.worst(rows)
    if w is None:
        return None
    items = []
    for r in rows:
        if r["level"] not in _BAND_CLASS:
            continue
        who = "전체" if r["scope"] == "total" else r["project"]
        text = (f"{_PERIOD_KO[r['period']]} {who}" if r["scope"] == "total" else f"{who} {_PERIOD_KO[r['period']]}")
        items.append({"text": f"{text} {_pct(r['ratio'])} %", "level": r["level"],
                      "title": f"${r['est_usd']:.2f} / 한도 ${r['limit']:.2f}" +
                               (f" · 단가 없음 {r['unpriced']} 건" if r["unpriced"] else "")})
    return {"cls": _BAND_CLASS[w["level"]], "level": w["level"], "cells": items, "label": ESTIMATE_LABEL}


def _dash_ctx(con, now: datetime) -> dict:
    return {
        "budget": budget_band(con, now),
        "sm": Q.summary_data(con, now), "my_turn": Q.my_turn(con, now), "live": Q.live_agents(con, now),
        "card_states": Q.CARD_STATES, "state_ko": Q.STATE_KO, "now_kst": Q.kst(now.isoformat()),
        "hooks_seen": con.execute("SELECT 1 FROM hook_event LIMIT 1").fetchone() is not None,
    }


@router.get("/")
def dashboard(request: Request, part: str | None = None):
    now = datetime.now(timezone.utc)
    con = conn.connect()
    try:
        ctx = _dash_ctx(con, now)
        if part == "body":
            return render(request, "_d01_body.html", ctx)
        ctx.update(title="관제판", active="/", feed=Q.feed(con, 40))
        return render(request, "dashboard.html", ctx)
    finally:
        con.close()


@router.get("/graph")
def graph_page(request: Request, project: str | None = None):
    # 프로젝트 옵션을 서버에서 미리 채운다 — 첫 로드의 `?project=` 가 select 에 남아 첫 fetch 에 실린다 (DEF-QA2-103)
    con = conn.connect()
    try:
        rows = con.execute("SELECT project_key, MAX(project_path) FROM agent GROUP BY project_key").fetchall()
    finally:
        con.close()
    projects = sorted(({"key": k, "label": Q.project_label(k, p)} for k, p in rows if k),
                      key=lambda x: (x["label"].lower(), x["key"]))
    if project and project not in {x["key"] for x in projects}:
        projects.insert(0, {"key": project, "label": project[:60]})     # 모르는 키도 그대로 보낸다 (API 가 판단)
    return render(request, "graph.html", {"title": "네트워크 구성도", "active": "/graph", "states": S.STATES,
                                          "state_ko": Q.STATE_KO, "projects": projects, "project": project or ""})


@router.get("/agents/{key}/raw")
def agent_raw(request: Request, key: str, offset: int = -200, limit: int = Query(200, ge=1, le=1000)):
    con = conn.connect()
    try:
        path = Q.source_path(con, key)
    finally:
        con.close()
    ctx: dict = {"read_at": Q.kst(datetime.now(timezone.utc).isoformat())}
    if path is None:
        ctx["error"] = f"원천 .jsonl 을 찾지 못했다 ({key[:80]}) — src_file 에 없거나 원천 루트 밖"
    elif not path.exists():
        ctx["error"] = f"원천 파일이 없다 (지워졌거나 옮겨짐): {path.name}"
    else:
        ctx["r"] = Q.raw_messages(path, offset=offset, limit=limit)
    resp = render(request, "agent_raw.html", ctx)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.get("/agents/{key}")
def agent_page(request: Request, key: str):
    con = conn.connect()
    try:
        d = Q.agent_detail(con, key)
        tools = Q.agent_tools(con, key, limit=1000) if d["found"] else {"total": 0, "tools": []}
        name = (d["agent"]["name"] or key) if d["found"] else key
        return render(request, "agent.html", {"title": f"{name[:40]} · 상세", "active": "", "d": d, "tools": tools,
                                              "state_ko": Q.STATE_KO})
    finally:
        con.close()
