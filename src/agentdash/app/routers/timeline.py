"""D-05 타임라인 화면 + GET /api/v1/timeline — 담당 개발1."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from agentdash.app.placeholders import api, label
from agentdash.app.templating import render

router = APIRouter()
OWNER = "개발1"


@router.get("/timeline")
def timeline_page(request: Request):
    return render(request, "placeholder.html", {"screen": "D-05", "title": "타임라인", "active": "/timeline",
                                                "label": label(OWNER), "spec": "spec.md §7 D-05"})


@router.get("/api/v1/timeline")
def timeline_api(frm: str | None = Query(None, alias="from"), to: str | None = None):
    return api(OWNER, lanes=[], concurrency=[])
