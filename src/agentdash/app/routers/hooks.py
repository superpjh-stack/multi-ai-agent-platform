"""POST /hooks/event — 훅 이벤트 수신 (spec.md §9.2). 담당 개발2.

· 본문 1 MB(`limits.hook_body_max_bytes`) 넘으면 413 — 읽다가 끊는다(전부 메모리에 올리지 않는다).
· 필드 화이트리스트(`collect.hooks_rx.filter_payload`) 뒤에 남은 것만 `hook_event` 에 1 행. 프롬프트 · 도구 입력 본문 · 응답은 버린다.
· 저장 직후 그 에이전트를 바로 다시 판정한다(R-01) → 바뀌면 `agent.state` SSE (G-11 훅 1 초).
· 훅 송신 쪽(hook_send.sh)은 응답을 보지 않는다. 그래도 조용히 삼키지 않게 응답에 accepted · 이유를 적는다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agentdash import settings
from agentdash.collect import hooks_rx

router = APIRouter()


async def _read_limited(request: Request, limit: int) -> bytes | None:
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > limit:
        return None
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > limit:
            return None
    return bytes(buf)


@router.post("/hooks/event")
async def hook_event(request: Request):
    s = settings.get()
    body = await _read_limited(request, s.hook_body_max_bytes)
    if body is None:
        return JSONResponse({"accepted": False, "reason": f"본문 > {s.hook_body_max_bytes} 바이트"}, status_code=413)
    try:
        raw = json.loads(body) if body else {}
    except ValueError:
        return {"accepted": False, "reason": "JSON 아님"}
    p = hooks_rx.filter_payload(raw)
    del raw, body                      # 원문은 여기서 버린다
    if not p.get("hook_event_name"):
        return {"accepted": False, "reason": "hook_event_name 없음"}
    now = datetime.now(timezone.utc)
    from agentdash.core import state
    from agentdash.db import conn

    con = conn.connect()
    try:
        key = hooks_rx.store(con, p, now)
        res = state.evaluate_one(con, key, now) if key else None
        con.commit()
    finally:
        con.close()
    out = {"accepted": True, "event": p["hook_event_name"][:40], "agent_key": key}
    if res is not None:
        v, changed = res
        out.update(state=v.state, rule=v.rule, changed=changed is not None)
    else:
        out.update(state=None, rule=None, changed=False, note="agent 행 없음 — 수집 뒤 판정")
    return out
