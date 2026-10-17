"""GET /api/v1/stream — SSE (agent.new · agent.state · agent.usage · edge.new). 담당 개발2.

placeholder 는 표지 이벤트 하나를 보내고 끝난다 (연결을 붙잡아 두지 않는다 — check_routes 가 기다리지 않게).
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from agentdash.app.placeholders import label

router = APIRouter()
OWNER = "개발2"


@router.get("/api/v1/stream")
async def stream():
    async def gen():
        yield {"event": "placeholder", "data": json.dumps({"_placeholder": label(OWNER)}, ensure_ascii=False)}

    return EventSourceResponse(gen())
