"""정규화 모델 — 데이터 클래스 + DB 쓰기 (spec.md §3). 담당 개발1. 시그니처는 progress-dev1.md §1 에 공표.

규칙
  · 테이블은 schema.sql 11 개 그대로. 여기서는 인덱스만 더한다.
  · 쓰기 함수는 커밋하지 않는다 — 호출한 쪽이 con.commit().
  · TEXT 값은 전부 clip() 을 거친다 (≤ 300 자, V-04). 본문은 받지 않는다.
  · upsert 는 None 인 칸으로 기존 값을 지우지 않는다 (parent_key · state 는 개발2 linker · state 가 쓴다).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable

TEXT_MAX = 300
DESC_MAX = 120
STATE_UNSET = "UNKNOWN"
STATE_UNSET_REASON = "unevaluated"
KINDS = ("SESSION", "SUBAGENT", "WORKFLOW_AGENT", "WORKFLOW")


def key_session(session_id: str) -> str:
    return f"S:{session_id}"


def key_agent(agent_id: str) -> str:
    return f"A:{agent_id}"


def key_workflow(wf_id: str) -> str:
    return f"W:{wf_id}"


def clip(s, n: int = TEXT_MAX):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n]


@dataclass
class AgentExtra:
    agent_id: str | None = None
    tool_use_id: str | None = None
    parent_agent_id: str | None = None
    is_fork: bool = False
    workflow_phase: str | None = None
    wf_id: str | None = None
    spawn_depth: int | None = None
    meta_model: str | None = None
    jsonl_path: str | None = None
    meta_path: str | None = None


@dataclass
class Agent:
    agent_key: str
    kind: str
    project_key: str
    session_id: str
    project_path: str | None = None
    parent_key: str | None = None
    spawn_tool_use: str | None = None
    depth: int = 0
    agent_type: str | None = None
    name: str | None = None
    request_shape: str | None = None
    model: str | None = None
    cc_version: str | None = None
    git_branch: str | None = None
    started_at: str | None = None
    last_event_at: str | None = None
    ended_at: str | None = None
    state: str | None = None
    state_reason: str | None = None
    state_since: str | None = None
    pid: int | None = None
    extra: AgentExtra | None = field(default=None, compare=False)


AGENT_COLS = [f.name for f in fields(Agent) if f.name != "extra"]


@dataclass
class UsageEvent:
    agent_key: str
    request_id: str
    at: str | None
    model: str | None
    speed: str | None = None
    input_tokens: int = 0
    cache_read: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    output_tokens: int = 0
    thinking_tokens: int | None = None
    web_search: int = 0
    web_fetch: int = 0
    cost_usd: float | None = None
    pricing_ver: str | None = None


@dataclass
class ToolCall:
    agent_key: str
    tool_use_id: str
    at: str | None
    tool: str | None
    target: str | None = None
    ok: int | None = None
    result_at: str | None = None


@dataclass
class FileTouch:
    agent_key: str
    path: str
    op: str
    at: str | None


# ── 변경 구독 (SSE 용) ────────────────────────────────────────────────
_listeners: list[Callable[[str, dict], None]] = []


def on_change(fn: Callable[[str, dict], None]) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def off_change(fn: Callable[[str, dict], None]) -> None:
    if fn in _listeners:
        _listeners.remove(fn)


def _emit(event: str, payload: dict) -> None:
    for fn in list(_listeners):
        fn(event, payload)


# ── 인덱스 ────────────────────────────────────────────────────────────
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_agent_session ON agent(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_agent_parent ON agent(parent_key)",
    "CREATE INDEX IF NOT EXISTS ix_agent_spawn ON agent(spawn_tool_use)",
    "CREATE INDEX IF NOT EXISTS ix_usage_agent ON usage_event(agent_key)",
    "CREATE INDEX IF NOT EXISTS ix_usage_at ON usage_event(at)",
    "CREATE INDEX IF NOT EXISTS ix_tool_agent ON tool_call(agent_key)",
    "CREATE INDEX IF NOT EXISTS ix_edge_dst ON edge(dst_key)",
    "CREATE INDEX IF NOT EXISTS ix_state_log_agent ON state_log(agent_key)",
    "CREATE INDEX IF NOT EXISTS ix_parse_error_path ON parse_error(path)",
]


def ensure_indexes(con: sqlite3.Connection) -> None:
    for sql in _INDEXES:
        con.execute(sql)


# ── agent ────────────────────────────────────────────────────────────
def _row_to_agent(r: sqlite3.Row | tuple) -> Agent:
    return Agent(**{c: r[i] for i, c in enumerate(AGENT_COLS)})


def get_agent(con: sqlite3.Connection, agent_key: str) -> Agent | None:
    r = con.execute(f"SELECT {','.join(AGENT_COLS)} FROM agent WHERE agent_key=?", (agent_key,)).fetchone()
    return _row_to_agent(r) if r else None


def list_agents(con: sqlite3.Connection, *, kind: str | None = None, session_id: str | None = None) -> list[Agent]:
    sql, args = f"SELECT {','.join(AGENT_COLS)} FROM agent WHERE 1=1", []
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if session_id:
        sql += " AND session_id=?"
        args.append(session_id)
    return [_row_to_agent(r) for r in con.execute(sql + " ORDER BY agent_key", args)]


_DESC_COLS = {"name"}


def upsert_agent(con: sqlite3.Connection, a: Agent) -> bool:
    if a.kind not in KINDS:
        raise ValueError(f"알 수 없는 kind {a.kind!r}")
    vals = {c: getattr(a, c) for c in AGENT_COLS}
    for c, v in vals.items():
        if isinstance(v, str):
            vals[c] = clip(v, DESC_MAX if c in _DESC_COLS else TEXT_MAX)
    exists = con.execute("SELECT 1 FROM agent WHERE agent_key=?", (a.agent_key,)).fetchone() is not None
    if not exists:
        if vals["state"] is None:
            vals["state"] = STATE_UNSET
            vals["state_reason"] = vals["state_reason"] or STATE_UNSET_REASON
        cols = ",".join(AGENT_COLS)
        con.execute(f"INSERT INTO agent ({cols}) VALUES ({','.join('?' * len(AGENT_COLS))})",
                    [vals[c] for c in AGENT_COLS])
        _emit("agent.new", {"agent_key": a.agent_key, "kind": a.kind})
        return True
    sets, args = [], []
    for c in AGENT_COLS:
        if c == "agent_key" or vals[c] is None:
            continue
        if c == "started_at":
            sets.append("started_at = CASE WHEN started_at IS NULL OR ? < started_at THEN ? ELSE started_at END")
            args += [vals[c], vals[c]]
        elif c == "last_event_at":
            sets.append("last_event_at = CASE WHEN last_event_at IS NULL OR ? > last_event_at THEN ? ELSE last_event_at END")
            args += [vals[c], vals[c]]
        elif c == "depth" and a.extra is None and vals[c] == 0 and a.kind != "SESSION":
            continue  # 기본값 0 으로 메타의 깊이를 지우지 않는다
        else:
            sets.append(f"{c} = ?")
            args.append(vals[c])
    if sets:
        con.execute(f"UPDATE agent SET {', '.join(sets)} WHERE agent_key=?", [*args, a.agent_key])
    return False


def set_parent(con: sqlite3.Connection, agent_key: str, parent_key: str | None, spawn_tool_use: str | None = None) -> bool:
    cur = con.execute("SELECT parent_key, spawn_tool_use FROM agent WHERE agent_key=?", (agent_key,)).fetchone()
    if cur is None:
        raise KeyError(agent_key)
    new_spawn = spawn_tool_use if spawn_tool_use is not None else cur[1]
    if cur[0] == parent_key and cur[1] == new_spawn:
        return False
    con.execute("UPDATE agent SET parent_key=?, spawn_tool_use=? WHERE agent_key=?", (parent_key, new_spawn, agent_key))
    return True


def set_state(con: sqlite3.Connection, agent_key: str, state: str, reason: str | None, at: str | None) -> bool:
    cur = con.execute("SELECT state, state_reason FROM agent WHERE agent_key=?", (agent_key,)).fetchone()
    if cur is None:
        raise KeyError(agent_key)
    reason = clip(reason)
    if cur[0] == state and cur[1] == reason:
        return False
    if cur[0] == state:
        con.execute("UPDATE agent SET state_reason=? WHERE agent_key=?", (reason, agent_key))
        return False
    con.execute("UPDATE agent SET state=?, state_reason=?, state_since=? WHERE agent_key=?", (state, reason, at, agent_key))
    con.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES (?,?,?,?)", (agent_key, at, state, reason))
    _emit("agent.state", {"agent_key": agent_key, "state": state, "reason": reason})
    return True


def set_ended(con: sqlite3.Connection, agent_key: str, ended_at: str | None) -> None:
    con.execute("UPDATE agent SET ended_at=? WHERE agent_key=?", (ended_at, agent_key))


# ── edge ─────────────────────────────────────────────────────────────
def add_edge(con: sqlite3.Connection, src_key: str, dst_key: str, kind: str, at: str | None, label: str | None = None) -> bool:
    cur = con.execute("SELECT count, at FROM edge WHERE src_key=? AND dst_key=? AND kind=?", (src_key, dst_key, kind)).fetchone()
    if cur is None:
        con.execute("INSERT INTO edge (src_key, dst_key, kind, at, count, label) VALUES (?,?,?,?,1,?)",
                    (src_key, dst_key, kind, at, clip(label, DESC_MAX)))
        _emit("edge.new", {"src": src_key, "dst": dst_key, "kind": kind})
        return True
    new_at = at if (cur[1] is None or (at is not None and at > cur[1])) else cur[1]
    con.execute("UPDATE edge SET count=count+1, at=?, label=COALESCE(?, label) WHERE src_key=? AND dst_key=? AND kind=?",
                (new_at, clip(label, DESC_MAX), src_key, dst_key, kind))
    return False


# ── usage · tool · file ──────────────────────────────────────────────
_USAGE_COLS = [f.name for f in fields(UsageEvent)]


def add_usage(con: sqlite3.Connection, ev: UsageEvent) -> bool:
    """같은 (agent_key, requestId) 는 한 행 (D-01). 스트리밍 중간본보다 output_tokens 가 큰 최종본으로 바꾼다."""
    cur = con.execute("SELECT output_tokens FROM usage_event WHERE agent_key=? AND request_id=?",
                      (ev.agent_key, ev.request_id)).fetchone()
    vals = [clip(v) if isinstance(v, str) else v for v in (getattr(ev, c) for c in _USAGE_COLS)]
    if cur is None:
        con.execute(f"INSERT INTO usage_event ({','.join(_USAGE_COLS)}) VALUES ({','.join('?' * len(_USAGE_COLS))})", vals)
        _emit("agent.usage", {"agent_key": ev.agent_key})
        return True
    if (ev.output_tokens or 0) > (cur[0] or 0):
        sets = ",".join(f"{c}=?" for c in _USAGE_COLS[2:])
        con.execute(f"UPDATE usage_event SET {sets} WHERE agent_key=? AND request_id=?",
                    [*vals[2:], ev.agent_key, ev.request_id])
        _emit("agent.usage", {"agent_key": ev.agent_key})
    return False



def upgrade_owner_usage(con: sqlite3.Connection, session_id: str, ev: UsageEvent) -> str | bool | None:
    """포크 사본 줄의 usage 를 그 requestId 의 소유 행(같은 세션에서 이미 센 행)에 반영한다 (DEF-QA1-001).

    소유 행 = 같은 세션 에이전트 중 이 requestId 를 가진 행(세션 안에서 한 행 — D-02). 사본의 output 이 더 크면
    usage 칸만 바꾼다 — agent_key · request_id · at(소유 기록의 시각) 은 그대로. 돌려줌: 바뀜 → 소유 agent_key · 그대로 False ·
    소유 행 아직 없음 None (부모 기록을 아직 못 읽음 — 호출한 쪽이 나중에 다시 부른다).
    """
    cur = con.execute("SELECT u.agent_key, u.output_tokens FROM usage_event u JOIN agent g ON g.agent_key=u.agent_key "
                      "WHERE g.session_id=? AND u.request_id=? ORDER BY u.at, u.agent_key LIMIT 1",
                      (session_id, ev.request_id)).fetchone()
    if cur is None:
        return None
    if (ev.output_tokens or 0) <= (cur[1] or 0):
        return False
    cols = [c for c in _USAGE_COLS if c not in ("agent_key", "request_id", "at")]
    con.execute(f"UPDATE usage_event SET {','.join(f'{c}=?' for c in cols)} WHERE agent_key=? AND request_id=?",
                [*(clip(getattr(ev, c)) if isinstance(getattr(ev, c), str) else getattr(ev, c) for c in cols),
                 cur[0], ev.request_id])
    _emit("agent.usage", {"agent_key": cur[0]})
    return cur[0]

def add_tool_call(con: sqlite3.Connection, tc: ToolCall) -> bool:
    cur = con.execute(
        "INSERT OR IGNORE INTO tool_call (agent_key, tool_use_id, at, tool, target, ok, result_at) VALUES (?,?,?,?,?,?,?)",
        (tc.agent_key, tc.tool_use_id, tc.at, clip(tc.tool), clip(tc.target), tc.ok, tc.result_at))
    return cur.rowcount == 1


def set_tool_result(con: sqlite3.Connection, tool_use_id: str, ok: bool | None, result_at: str | None,
                    target: str | None = None) -> bool:
    """결과 반환 기록. target 을 주면 대상도 바꾼다 (Workflow 호출 → 결과의 runId "wf_…")."""
    cur = con.execute("UPDATE tool_call SET ok=?, result_at=?, target=COALESCE(?, target) WHERE tool_use_id=?",
                      (None if ok is None else int(bool(ok)), result_at, clip(target), tool_use_id))
    return cur.rowcount == 1


def add_file_touch(con: sqlite3.Connection, ft: FileTouch) -> bool:
    cur = con.execute("INSERT OR IGNORE INTO file_touch (agent_key, path, op, at) VALUES (?,?,?,?)",
                      (ft.agent_key, clip(ft.path), clip(ft.op), ft.at))
    if cur.rowcount == 0 and ft.at:
        con.execute("UPDATE file_touch SET at=? WHERE agent_key=? AND path=? AND op=? AND (at IS NULL OR at < ?)",
                    (ft.at, ft.agent_key, clip(ft.path), clip(ft.op), ft.at))
    return cur.rowcount == 1


def add_parse_error(con: sqlite3.Connection, path: str | Path, line_no: int | None, reason: str) -> None:
    from datetime import datetime, timezone

    con.execute("INSERT INTO parse_error (path, line_no, reason, at) VALUES (?,?,?,?)",
                (clip(str(path)), line_no, clip(reason, DESC_MAX), datetime.now(timezone.utc).isoformat(timespec="seconds")))


def add_hook_event(con: sqlite3.Connection, agent_key: str | None, at: str | None, event: str, detail: str | None) -> None:
    con.execute("INSERT INTO hook_event (agent_key, at, event, detail) VALUES (?,?,?,?)",
                (agent_key, at, clip(event), clip(detail)))


# ── 메타 다시 읽기 (DB 열이 없는 연결 단서) ────────────────────────────
def load_extra(con: sqlite3.Connection, agent_key: str) -> AgentExtra | None:
    """agent 행에 없는 메타 단서(parentAgentId · isFork · workflowPhase · wf_id)를 원천 meta 에서 다시 읽는다 (읽기만)."""
    from agentdash.collect.parsers import meta as meta_parser

    if not agent_key.startswith("A:"):
        return None
    aid = agent_key[2:]
    r = con.execute("SELECT path FROM src_file WHERE path LIKE ? ESCAPE '\\'",
                    (f"%agent-{aid}.meta.json",)).fetchone()
    if r is None:
        return None
    p = Path(r[0])
    if not p.exists():
        return None
    m = meta_parser.parse(p)
    return m.extra()


def as_dict(obj) -> dict:
    d = asdict(obj)
    d.pop("extra", None)
    return d


def dumps(obj) -> str:
    return json.dumps(as_dict(obj), ensure_ascii=False)
