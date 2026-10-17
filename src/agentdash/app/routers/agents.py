"""GET /api/v1/summary · /api/v1/agents · /api/v1/agents/{key} · /api/v1/agents/{key}/tools — 담당 개발2."""

from __future__ import annotations

from fastapi import APIRouter

from agentdash.app.placeholders import api

router = APIRouter()
OWNER = "개발2"


@router.get("/api/v1/summary")
def summary():
    return api(OWNER, states={}, today={}, parse_errors=0)


@router.get("/api/v1/agents")
def agents(state: str | None = None, project: str | None = None, kind: str | None = None, since: str | None = None):
    return api(OWNER, agents=[])


@router.get("/api/v1/agents/{key}/tools")
def agent_tools(key: str):
    return api(OWNER, key=key[:60], tools=[])


@router.get("/api/v1/agents/{key}")
def agent_detail(key: str):
    return api(OWNER, key=key[:60], agent=None, parent=None, children=[], usage={}, state_reason=None)
