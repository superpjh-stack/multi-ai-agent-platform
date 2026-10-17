"""D-06 파이프라인 화면 + GET /api/v1/pipeline — 담당 개발1 (spec.md §7 D-06 · §7.1).

판정은 core/pipeline.py (원천은 읽기만). 원천 변경 또는 5 분마다 다시 판정해 pipeline_cell 에 저장한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from agentdash.app.templating import render
from agentdash.core import pipeline as P
from agentdash.db import conn

router = APIRouter()
OWNER = "개발1"
STATUS_LABEL = {"DONE": "완료", "PARTIAL": "일부", "IN_PROGRESS": "진행 중", "NEEDS_DECISION": "판단 필요",
                "NOT_STARTED": "시작 전", "UNKNOWN": "규칙 없음"}


def _result():
    con = conn.connect(conn.init_db())
    try:
        return P.cached(con)
    finally:
        con.close()


@router.get("/pipeline")
def pipeline_page(request: Request):
    res = _result()
    d = res.as_dict()
    grid = {(c.company, c.stage): c for c in res.cells}
    ctx = {"title": "파이프라인", "active": "/pipeline", "r": res, "d": d, "grid": grid, "label": STATUS_LABEL,
           "next": res.next_stage(), "stage_label": {s["code"]: s["label"] for s in res.stages}}
    return render(request, "pipeline.html", ctx)


@router.get("/api/v1/pipeline")
def pipeline_api():
    return _result().as_dict()
