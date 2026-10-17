"""POST /hooks/event — 훅 이벤트 수신. 담당 개발2 (spec.md §9.2).

placeholder 는 본문을 읽지도 저장하지도 않는다 (G-13). 구현 시 1 MB 제한 · 필요한 필드만 남김.
"""

from __future__ import annotations

from fastapi import APIRouter

from agentdash.app.placeholders import api

router = APIRouter()
OWNER = "개발2"


@router.post("/hooks/event")
async def hook_event():
    return api(OWNER, accepted=False)
