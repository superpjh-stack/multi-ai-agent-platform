"""placeholder 표지 — 아직 구현하지 않은 화면 · API 를 명확히 드러낸다 (조용한 빈 화면 금지).

화면 GET 을 실제로 구현하면 그 라우터의 placeholder 호출을 지운다. `tools/check_routes.py` 가 남은 placeholder 수를 센다.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

MARK = "미구현"


def label(owner: str) -> str:
    return f"{MARK} — 담당 {owner}"


def api(owner: str, **empty) -> dict:
    """빈 응답 + 표지. 키 `_placeholder` 가 있으면 미구현이다."""
    return {"_placeholder": label(owner), **empty}


# ── 2차-A 자리 잡기: D-07 비용 · 효율 + API 3 (spec.md v0.3 §7 D-07 · §8) ────────────────────────────────────────
# 실제 구현은 개발1 이 계획 Task 8 에서 `app/routers/insights.py` (router = APIRouter()) 로 만든다.
# main.py 는 그 모듈이 **있으면 그것을, 없을 때만** 아래 INSIGHTS_STUB 를 등록한다 (importlib.util.find_spec — 파일이 있는데
# import 가 깨지면 그대로 예외, 조용히 stub 로 돌아가지 않는다). Task 8 이 끝나면 아키텍트가 이 블록과 main.py 분기를 지운다.
INSIGHTS_OWNER = "개발1"
INSIGHTS_PATHS = ("/insights", "/api/v1/budget", "/api/v1/trend", "/api/v1/efficiency")


def _insights_stub():
    from agentdash.app import templating

    r = APIRouter()

    @r.get("/insights")
    def insights_page(request: Request):
        return templating.render(request, "placeholder.html", {
            "screen": "D-07", "title": "비용 · 효율", "label": label(INSIGHTS_OWNER),
            "spec": "spec.md v0.3 §7 D-07 · §6.3 — 계획 Task 8"})

    @r.get("/api/v1/budget")
    def budget_api():
        return api(INSIGHTS_OWNER, cells=[])

    @r.get("/api/v1/trend")
    def trend_api(grain: str = "day", group: str = "total"):
        return api(INSIGHTS_OWNER, grain=grain, group=group, series=[])

    @r.get("/api/v1/efficiency")
    def efficiency_api(group: str = "project"):
        return api(INSIGHTS_OWNER, group=group, rows=[])

    return r


INSIGHTS_STUB = _insights_stub()
