"""D-04 작업량 화면 + GET /api/v1/usage — 담당 개발1 (spec.md §6 · §6.1 · §7 D-04).

비용은 항상 `[추정] API 정가 환산` 표기 — Claude Code 구독 요금과 다르다. 단가 없는 모델은 비용 NULL + 「단가 없음 N 건」.
CSV: `GET /api/v1/usage?…&format=csv` (화면의 내보내기 버튼) · `make export`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from agentdash.app.routers import _svg
from agentdash.app.templating import render
from agentdash.core import usage as U
from agentdash.db import conn

router = APIRouter()
OWNER = "개발1"
GROUP_LABEL = {"agent": "에이전트", "project": "프로젝트", "type": "유형", "model": "모델", "day": "일자"}


def _table(frm, to, group) -> dict:
    con = conn.connect(conn.init_db())
    try:
        return U.table(con, frm, to, group)
    finally:
        con.close()


def _hours(sec: int) -> str:
    return f"{sec / 3600:.1f} h" if sec else "—"


@router.get("/usage")
def usage_page(request: Request, frm: str | None = Query(None, alias="from"), to: str | None = None,
               group: str | None = None):
    t = _table(frm, to, group)
    trend = [(d["day"], d["output_tokens"]) for d in t["trend"]]
    cost = [(d["day"], d["cost_usd"]) for d in t["trend"]]
    ctx = {"title": "작업량", "active": "/usage", "t": t, "glabel": GROUP_LABEL, "fmt": _svg.fmt_int, "hours": _hours,
           "svg_out": _svg.bars(trend, unit=" 출력 토큰", title="일별 출력 토큰"),
           "svg_cost": _svg.bars(cost, unit=" US$", fmt=lambda v: f"${v:,.2f}", title="일별 추정 비용"),
           "rows": t["rows"][:300], "more": max(0, len(t["rows"]) - 300)}
    return render(request, "usage.html", ctx)


@router.get("/api/v1/usage")
def usage_api(frm: str | None = Query(None, alias="from"), to: str | None = None, group: str | None = None,
              format: str | None = None):
    t = _table(frm, to, group)
    if format == "csv":
        name = f"usage_{t['from']}_{t['to']}_{t['group']}.csv"
        return Response(U.to_csv(t).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                        headers={"content-disposition": f'attachment; filename="{name}"'})
    return t
