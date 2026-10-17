"""GET /api/v1/stream — SSE (agent.new · agent.state · agent.usage · edge.new). 담당 개발2.

· `Accept: text/event-stream`(브라우저 EventSource 는 늘 보낸다)이면 연결을 붙잡고 실시간으로 보낸다. 재접속은 `Last-Event-ID`.
· 그 밖(Accept 없음 · `*/*` — curl · 검사 도구 · TestClient)은 `hello` + 최근 이벤트 묶음 한 번을 보내고 닫는다.
  연결을 붙잡지 않으므로 check_routes(G-17)가 기다리지 않는다. `?follow=1` 이면 Accept 와 상관없이 붙잡는다.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from agentdash.app import sse

router = APIRouter()
sse.attach_model()
KEEPALIVE_SEC = 15


@router.get("/api/v1/stream")
async def stream(request: Request, follow: int = 0, recent: int = 20):
    want_stream = follow == 1 or "text/event-stream" in request.headers.get("accept", "")
    last = request.headers.get("last-event-id")
    last_id = int(last) if last and last.isdigit() else None

    if not want_stream:
        async def once():
            yield {"event": "hello", "data": json.dumps({"mode": "once", "events": list(sse.EVENTS),
                                                         "subscribers": sse.broker.subscribers})}
            for it in sse.broker.recent(max(0, min(recent, 200))):
                yield sse.format_sse(it)
        return EventSourceResponse(once())

    async def live():
        q, backlog = sse.broker.subscribe(last_id)
        try:
            yield {"event": "hello", "data": json.dumps({"mode": "live", "events": list(sse.EVENTS)})}
            for it in backlog:
                yield sse.format_sse(it)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    it = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                yield sse.format_sse(it)
        finally:
            sse.broker.unsubscribe(q)

    return EventSourceResponse(live(), ping=KEEPALIVE_SEC)
