"""GET /api/v1/graph — Cytoscape 형식 {nodes, edges}. 담당 개발2."""

from __future__ import annotations

from fastapi import APIRouter

from agentdash.app.placeholders import api

router = APIRouter()
OWNER = "개발2"


@router.get("/api/v1/graph")
def graph(since: str | None = None, project: str | None = None, view: str | None = None):
    return api(OWNER, nodes=[], edges=[], view=view or "tree")
