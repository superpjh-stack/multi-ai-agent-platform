"""D-01 공장 평면도 API — `GET /api/v1/twin?since=&project=` (spec.md v0.4 §5.4 · §8).

소유: **개발2** (goal.md §3 · 계획 Task 3 · 4). 아키텍트는 Phase 0 에 자리만 만들었다 —
개발2 가 `core/twin.build(...)` 를 연결하면서 아래 placeholder 를 지운다(`check_routes` 가 남은 placeholder 를 센다).
"""

from __future__ import annotations

from fastapi import APIRouter

from agentdash.app import placeholders

router = APIRouter()


@router.get("/api/v1/twin")
def twin_api(since: str | None = None, project: str | None = None) -> dict:
    return placeholders.api("개발2", lines=[], links=[], folded_lines=0)
