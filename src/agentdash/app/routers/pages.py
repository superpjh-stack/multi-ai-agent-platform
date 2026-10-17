"""화면 D-01 관제판 · D-02 구성도 · D-03 에이전트 상세 — 담당 개발2 (goal.md §3.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from agentdash.app.placeholders import label
from agentdash.app.templating import render

router = APIRouter()
OWNER = "개발2"


@router.get("/")
def dashboard(request: Request):
    return render(request, "placeholder.html", {"screen": "D-01", "title": "관제판", "active": "/",
                                                "label": label(OWNER), "spec": "spec.md §7 D-01"})


@router.get("/graph")
def graph_page(request: Request):
    return render(request, "placeholder.html", {"screen": "D-02", "title": "네트워크 구성도", "active": "/graph",
                                                "label": label(OWNER), "spec": "spec.md §5 · §7 D-02"})


@router.get("/agents/{key}")
def agent_page(request: Request, key: str):
    return render(request, "placeholder.html", {"screen": "D-03", "title": "에이전트 상세", "active": "",
                                                "label": label(OWNER), "spec": f"spec.md §7 D-03 · key={key[:60]}"})
