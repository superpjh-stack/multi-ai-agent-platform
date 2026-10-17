"""FastAPI 앱 — 화면 6 · API 10 (spec.md §7 · §8). 실행은 `make run` (127.0.0.1:8095 만).

라우터 소유 (goal.md §3.2 — 한 파일은 한 사람만)
  개발1: routers/{usage,timeline,pipeline}.py
  개발2: routers/{pages,agents,graph,stream,hooks}.py
이 파일과 settings.py 는 아키텍트 소유. 새 라우터가 필요하면 progress-devN.md §3 에 요청한다.
"""

from __future__ import annotations

from fastapi import FastAPI

from agentdash.app.routers import agents, graph, hooks, pages, pipeline, stream, timeline, usage

ROUTERS = [pages, usage, timeline, pipeline, agents, graph, stream, hooks]


def create_app() -> FastAPI:
    app = FastAPI(title="agentdash", docs_url=None, redoc_url=None, openapi_url=None)
    for mod in ROUTERS:
        app.include_router(mod.router)
    return app


app = create_app()
