"""FastAPI 앱 — 화면 7 · API 13 (spec.md v0.3 §7 · §8). 실행은 `make run` (127.0.0.1:8095 만).

라우터 소유 (goal.md §3.2 — 한 파일은 한 사람만)
  개발1: routers/{usage,timeline,pipeline,insights}.py  (insights = 2차-A Task 8 — 없으면 placeholders.INSIGHTS_STUB)
  개발2: routers/{pages,agents,graph,stream,hooks}.py
이 파일과 settings.py 는 아키텍트 소유. 새 라우터가 필요하면 progress-devN.md §3 에 요청한다.

lifespan (R5 — 오케스트레이터 지시로 개발2 가 넣음, 회전 4)
  기동: `app.sse.attach_model()` (model.on_change → SSE · ingest 뒤 연결 · 판정) → `core.state.start_ticker()` (10 초 판정)
        → 백그라운드 스레드: DB 에 agent 행이 0 이면 `collect.backfill.run()` (증분 오프셋 기록 — 그 뒤 감시기는 이어 읽는다)
        → `collect.watcher.start()` (1 초 묶음 + 60 초 재스캔).
  종료: 감시기 · 판정 스레드의 stop 이벤트를 set 하고 잠깐 기다린다.
  `AGENTDASH_NO_WATCH=1` 이면 아무것도 띄우지 않는다(테스트 · 검사 도구용). 상태는 `app.state.lifespan` 에 남긴다(조용히 삼키지 않음).
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentdash.app import placeholders
from agentdash.app.routers import agents, graph, hooks, pages, pipeline, stream, timeline, usage

INSIGHTS_MODULE = "agentdash.app.routers.insights"


def _insights_router():
    """D-07 · API 3 (2차-A). 개발1 의 routers/insights.py 가 있으면 그 router, 없으면 placeholder (placeholders.INSIGHTS_STUB).
    파일이 있는데 import 가 실패하면 예외가 그대로 난다 — stub 로 숨기지 않는다."""
    if importlib.util.find_spec(INSIGHTS_MODULE) is not None:
        return importlib.import_module(INSIGHTS_MODULE).router
    return placeholders.INSIGHTS_STUB


ROUTERS = [pages, usage, timeline, pipeline, agents, graph, stream, hooks]
EXTRA_ROUTERS = [_insights_router()]          # APIRouter 객체 그대로 (Task 8 뒤 insights 를 ROUTERS 로 옮기고 지운다)
NO_WATCH_ENV = "AGENTDASH_NO_WATCH"
log = logging.getLogger("agentdash.lifespan")


def _db_empty() -> bool:
    from agentdash.db import conn
    db = conn.init_db()
    con = conn.connect(db)
    try:
        return con.execute("SELECT COUNT(*) FROM agent").fetchone()[0] == 0
    finally:
        con.close()


def _bootstrap(status: dict, stop: threading.Event) -> None:
    """빈 DB 면 백필 → 감시기. 실패는 status 에 남기고 로그에 한 줄 (본문 없음)."""
    from agentdash.collect import backfill, watcher
    try:
        if _db_empty():
            status["backfill"] = "진행 중"
            out = backfill.run()
            status["backfill"] = f"완료 {out['seconds']} s · agent {sum(out['agents'].values())}"
        else:
            status["backfill"] = "건너뜀 (DB 에 agent 행 있음 — 감시기가 증분으로 이어 읽음)"
        if stop.is_set():
            return
        t, ev = watcher.start()
        status["watcher"] = "실행 중"
        status["_watcher"] = (t, ev)
    except Exception as e:  # noqa: BLE001 — 기동 실패를 화면 · 로그에 드러낸다
        status["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        log.error("agentdash 기동 실패: %s", status["error"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    status: dict = {"mode": "off" if os.environ.get(NO_WATCH_ENV) == "1" else "on"}
    app.state.lifespan = status
    from agentdash.db import conn
    conn.init_db()                     # 없으면 schema 11 테이블 (data/ 아래만 — 원천 경로는 conn 이 거부)
    if status["mode"] == "off":
        yield
        return
    from agentdash.app import sse
    from agentdash.core import state

    sse.attach_model()
    tick_t, tick_stop = state.start_ticker()
    status["ticker"] = "실행 중"
    stop = threading.Event()
    boot = threading.Thread(target=_bootstrap, args=(status, stop), name="agentdash-bootstrap", daemon=True)
    boot.start()
    try:
        yield
    finally:
        stop.set()
        tick_stop.set()
        w = status.get("_watcher")
        if w:
            w[1].set()
            w[0].join(timeout=3)
        tick_t.join(timeout=3)
        status["watcher"] = status["ticker"] = "멈춤"


def create_app() -> FastAPI:
    app = FastAPI(title="agentdash", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    for mod in ROUTERS:
        app.include_router(mod.router)
    for r in EXTRA_ROUTERS:
        app.include_router(r)
    return app


app = create_app()
