"""D-06 파이프라인 화면 + GET /api/v1/pipeline — 담당 개발1."""

from __future__ import annotations

from fastapi import APIRouter, Request

from agentdash.app.placeholders import api, label
from agentdash.app.templating import render

router = APIRouter()
OWNER = "개발1"


@router.get("/pipeline")
def pipeline_page(request: Request):
    return render(request, "placeholder.html", {"screen": "D-06", "title": "파이프라인", "active": "/pipeline",
                                                "label": label(OWNER), "spec": "spec.md §7 D-06 · §7.1"})


@router.get("/api/v1/pipeline")
def pipeline_api():
    return api(OWNER, companies=[], stages=[], cells=[], unregistered=0)
