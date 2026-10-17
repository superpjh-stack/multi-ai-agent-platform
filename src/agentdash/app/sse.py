"""SSE 방송 (spec.md §8 `GET /api/v1/stream`) — 담당 개발2.

이벤트 4 종 (공표 — progress-dev2.md §1)
  agent.new    {"agent_key", "kind"}
  agent.state  {"agent_key", "state", "reason"}
  agent.usage  {"agent_key"}
  edge.new     {"src", "dst", "kind"}
각 이벤트는 단조 증가 `id` 를 가진다. 재접속 때 `Last-Event-ID` 를 주면 링 버퍼(최근 1000 건)에서 이어 보낸다.

원천은 개발1 `model.on_change(fn)` — DB 쓰기 함수가 부른다. 감시기 스레드 · 요청 스레드 어디서 불려도 되게
`publish()` 는 스레드 안전하고, 구독자 큐에는 그 구독자의 이벤트 루프로 `call_soon_threadsafe` 로 넣는다.
본문은 싣지 않는다 — 키 · 상태 · 규칙 코드뿐.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import deque

EVENTS = ("agent.new", "agent.state", "agent.usage", "edge.new")
RING = 1000
_FIELDS = {"agent.new": ("agent_key", "kind"), "agent.state": ("agent_key", "state", "reason"),
           "agent.usage": ("agent_key",), "edge.new": ("src", "dst", "kind")}


class Broker:
    def __init__(self, ring: int = RING):
        self._lock = threading.Lock()
        self._seq = 0
        self._ring: deque[tuple[int, str, dict]] = deque(maxlen=ring)
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []

    def publish(self, event: str, payload: dict) -> int | None:
        if event not in _FIELDS:
            return None
        data = {k: (str(payload.get(k))[:300] if payload.get(k) is not None else None) for k in _FIELDS[event]}
        with self._lock:
            self._seq += 1
            item = (self._seq, event, data)
            self._ring.append(item)
            subs = list(self._subs)
        for loop, q in subs:
            try:
                loop.call_soon_threadsafe(q.put_nowait, item)
            except RuntimeError:          # 루프가 닫힘 — 그 구독자는 끊긴 것
                self._drop(loop, q)
        return item[0]

    def subscribe(self, last_id: int | None = None) -> tuple[asyncio.Queue, list[tuple[int, str, dict]]]:
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subs.append((loop, q))
            backlog = [it for it in self._ring if last_id is not None and it[0] > last_id]
        return q, backlog

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [(lp, x) for lp, x in self._subs if x is not q]

    def _drop(self, loop, q) -> None:
        with self._lock:
            self._subs = [(lp, x) for lp, x in self._subs if x is not q]

    @property
    def subscribers(self) -> int:
        with self._lock:
            return len(self._subs)

    def recent(self, n: int = 50) -> list[tuple[int, str, dict]]:
        with self._lock:
            return list(self._ring)[-n:]


broker = Broker()
_hooked = False


def attach_model() -> None:
    """개발1 model.on_change 에 방송을 붙인다 (한 번만)."""
    global _hooked
    if _hooked:
        return
    from agentdash.core import model as M
    from agentdash.core import state
    M.on_change(broker.publish)
    state.register()                   # 수집 뒤 연결 · 판정 (ingest post hook)
    _hooked = True


def format_sse(item: tuple[int, str, dict]) -> dict:
    sid, event, data = item
    return {"id": str(sid), "event": event, "data": json.dumps(data, ensure_ascii=False)}
