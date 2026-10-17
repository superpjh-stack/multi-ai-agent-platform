"""D-04 작업량 화면 + GET /api/v1/usage — 담당 개발1."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from agentdash.app.placeholders import api, label
from agentdash.app.templating import render

router = APIRouter()
OWNER = "개발1"


@router.get("/usage")
def usage_page(request: Request):
    return render(request, "placeholder.html", {"screen": "D-04", "title": "작업량", "active": "/usage",
                                                "label": label(OWNER), "spec": "spec.md §6 · §7 D-04 — [추정] API 정가 환산"})


@router.get("/api/v1/usage")
def usage_api(frm: str | None = Query(None, alias="from"), to: str | None = None, group: str | None = None):
    return api(OWNER, rows=[], group=group, pricing_ver=None, unpriced=0)
