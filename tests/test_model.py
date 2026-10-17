"""core/model.py 쓰기 규칙 · ingest 의 agent.last_event_at (웨이브 D2 — R8 · R9).

R9  `add_edge` — 더 이른(또는 시각 없는) 값이 기존 엣지의 label 을 덮지 않는다. 엣지 4 종 모두.
R8  `agent.last_event_at` = 마지막 기록 — **모든 줄 종류**(timestamp 있는 줄, 포크 사본 제외). 단 `SubagentHandback` 뒤
    활동이 아닌 꼬리 줄(그 결과 · 첨부 · 마지막 인사 텍스트)은 넣지 않는다 → linker 가 기록 꼬리를 다시 읽지 않고
    `last_event_at > 가장 늦은 반환` 이면 다시 깨어난 것으로 본다 (L-07 · D-04).
원천 흉내는 tmp 의 가짜 루트로만.
"""

import json
from pathlib import Path

import pytest

from agentdash.collect import ingest
from agentdash.core import model as M
from agentdash.db import conn

PK = "-tmp-proj"
SID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def con(tmp_path):
    c = conn.connect(conn.init_db(tmp_path / "m.db"))
    yield c
    c.close()


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "projects" / PK).mkdir(parents=True)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(h))
    return h


# ── R9 add_edge label ────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["spawn", "message", "handback", "workflow"])
def test_add_edge_older_label_does_not_overwrite(con, kind):
    M.add_edge(con, "S:a", "A:b", kind, "2026-10-17T07:10:00Z", "new")
    M.add_edge(con, "S:a", "A:b", kind, "2026-10-17T07:00:00Z", "old")      # 늦게 읽힌 옛 값
    at, label = con.execute("SELECT at, label FROM edge WHERE kind=?", (kind,)).fetchone()
    assert (at, label) == ("2026-10-17T07:10:00Z", "new")


@pytest.mark.parametrize("kind", ["spawn", "message", "handback", "workflow"])
def test_add_edge_newer_label_wins(con, kind):
    M.add_edge(con, "S:a", "A:b", kind, "2026-10-17T07:00:00Z", "old")
    M.add_edge(con, "S:a", "A:b", kind, "2026-10-17T07:10:00Z", "new")
    assert tuple(con.execute("SELECT at, label FROM edge").fetchone()) == ("2026-10-17T07:10:00Z", "new")


def test_add_edge_untimed_label_does_not_overwrite_timed(con):
    M.add_edge(con, "S:a", "A:b", "message", "2026-10-17T07:00:00Z", "timed")
    M.add_edge(con, "S:a", "A:b", "message", None, "untimed")
    assert tuple(con.execute("SELECT at, label FROM edge").fetchone()) == ("2026-10-17T07:00:00Z", "timed")


def test_add_edge_none_label_keeps_label(con):
    M.add_edge(con, "S:a", "A:b", "spawn", "2026-10-17T07:00:00Z", "L-01")
    M.add_edge(con, "S:a", "A:b", "spawn", "2026-10-17T07:10:00Z", None)
    assert tuple(con.execute("SELECT at, label, count FROM edge").fetchone()) == ("2026-10-17T07:10:00Z", "L-01", 2)


# ── R8 last_event_at ────────────────────────────────────────────────

def _line(typ, ts, content=None, **kw):
    d = {"type": typ, "uuid": kw.pop("uuid", f"u-{typ}-{ts}"), "timestamp": ts, "sessionId": SID, "cwd": "/tmp/proj"}
    if typ == "assistant":
        d["message"] = {"model": "claude-opus-5-5", "content": content or []}
    elif typ == "user":
        d["message"] = {"content": content if content is not None else "hi"}
    d.update(kw)
    return json.dumps(d)


def _tu(name, tid):
    return [{"type": "tool_use", "id": tid, "name": name, "input": {}}]


def _write(p: Path, lines, mode="w"):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open(mode, encoding="utf-8") as fh:
        fh.write("".join(x + "\n" for x in lines))


def _last(con, key):
    return con.execute("SELECT last_event_at FROM agent WHERE agent_key=?", (key,)).fetchone()[0]


def test_session_last_event_counts_all_line_kinds(home, con):
    """세션 — 마지막 줄이 system · attachment 같은 다른 종류여도 그 시각이 마지막 기록 (QA2 judge `last_at` 과 같은 기준)."""
    _write(home / "projects" / PK / f"{SID}.jsonl", [
        _line("user", "2026-10-17T07:00:00.000Z"),
        _line("assistant", "2026-10-17T07:00:05.000Z", [{"type": "text", "text": "x"}]),
        _line("system", "2026-10-17T07:00:06.000Z", subtype="turn_duration"),
        _line("attachment", "2026-10-17T07:00:07.000Z"),
        json.dumps({"type": "last-prompt", "sessionId": SID}),                      # 시각 없는 줄 — 무시
    ])
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, f"S:{SID}") == "2026-10-17T07:00:07.000Z"
    assert con.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0] == 0


def _sub(home, lines, mode="w"):
    sub = home / "projects" / PK / SID / "subagents"
    _write(sub / "agent-c1.jsonl", lines, mode)
    meta = sub / "agent-c1.meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({"agentType": "general-purpose", "toolUseId": "t1", "spawnDepth": 1}))
    _write(home / "projects" / PK / f"{SID}.jsonl", [_line("assistant", "2026-10-17T06:59:00.000Z", _tu("Agent", "t1"))])


def test_post_handback_tail_is_not_a_record(home, con):
    """handback 뒤 tool_result · 첨부 · 마지막 인사 텍스트 → last_event_at 은 handback 시각 그대로."""
    _sub(home, [
        _line("user", "2026-10-17T07:00:00.000Z", agentId="c1"),
        _line("assistant", "2026-10-17T07:01:00.000Z", _tu("Bash", "b1"), agentId="c1"),
        _line("user", "2026-10-17T07:01:30.000Z", [{"type": "tool_result", "tool_use_id": "b1"}], agentId="c1"),
        _line("assistant", "2026-10-17T07:02:00.000Z", _tu("SubagentHandback", "h1"), agentId="c1"),
        _line("user", "2026-10-17T07:02:02.000Z", [{"type": "tool_result", "tool_use_id": "h1"}], agentId="c1"),
        _line("attachment", "2026-10-17T07:02:02.002Z"),
        _line("assistant", "2026-10-17T07:02:05.000Z", [{"type": "text", "text": "bye"}], agentId="c1"),
        _line("user", "2026-10-17T07:02:06.000Z", "meta", isMeta=True, agentId="c1"),
    ])
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:02:00.000Z"


def test_incoming_message_after_handback_is_a_record_across_increments(home, con):
    """반환 뒤 들어온 메시지(user 텍스트) — 다음 증분에서 읽혀도 last_event_at 이 그 시각으로, 그 뒤 꼬리는 다시 다 센다."""
    _sub(home, [
        _line("assistant", "2026-10-17T07:02:00.000Z", _tu("SubagentHandback", "h1"), agentId="c1"),
        _line("user", "2026-10-17T07:02:02.000Z", [{"type": "tool_result", "tool_use_id": "h1"}], agentId="c1"),
    ])
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:02:00.000Z"
    _sub(home, [_line("attachment", "2026-10-17T07:05:00.000Z")], mode="a")          # 증분: 활동 아닌 꼬리 — 여전히 제외
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:02:00.000Z"
    _sub(home, [_line("user", "2026-10-17T07:20:00.000Z", [{"type": "text", "text": "again"}], agentId="c1"),
                _line("attachment", "2026-10-17T07:20:01.000Z")], mode="a")
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:20:01.000Z"                         # 깨어난 뒤엔 모든 줄


# ── 웨이브 D3 — DEF-QA1-102: last_event_at ≥ 그 에이전트의 마지막 usage · tool_call 시각 ──────────────
_USAGE = {"input_tokens": 1, "output_tokens": 7, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _billed(ts, text="note", rid=None):
    d = json.loads(_line("assistant", ts, [{"type": "text", "text": text}], agentId="c1"))
    d["message"]["usage"] = dict(_USAGE)
    d["requestId"] = rid or f"req-{ts}"
    return json.dumps(d)


def _floor_ok(con, key):
    le = _last(con, key)
    u = con.execute("SELECT MAX(at) FROM usage_event WHERE agent_key=?", (key,)).fetchone()[0]
    t = con.execute("SELECT MAX(at) FROM tool_call WHERE agent_key=?", (key,)).fetchone()[0]
    return all(x is None or le >= x for x in (u, t))


def test_post_handback_billed_reply_is_a_record(home, con):
    """handback 뒤 isMeta task-notification 에 응답한 assistant 줄(사용량 있음) — 마지막 기록에 들어간다 (QA1 재현 꼴)."""
    _sub(home, [
        _line("assistant", "2026-10-17T07:02:00.000Z", _tu("SubagentHandback", "h1"), agentId="c1"),
        _line("user", "2026-10-17T07:02:02.000Z", [{"type": "tool_result", "tool_use_id": "h1"}], agentId="c1"),
        _line("user", "2026-10-17T07:25:00.000Z", "<task-notification>x</task-notification>", isMeta=True, agentId="c1"),
        _billed("2026-10-17T07:25:03.000Z"),
        _line("attachment", "2026-10-17T07:25:04.000Z"),                         # 활동 아닌 꼬리 — 여전히 제외
    ])
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:25:03.000Z"
    assert _floor_ok(con, "A:c1")


def test_post_handback_billed_reply_across_increments(home, con):
    """증분으로 읽어도 같다 — 사용량 줄 뒤의 꼬리 줄은 다음 증분에서도 「handback 뒤」 로 이어 간다."""
    _sub(home, [
        _line("assistant", "2026-10-17T07:02:00.000Z", _tu("SubagentHandback", "h1"), agentId="c1"),
        _billed("2026-10-17T07:02:05.000Z", "bye"),
    ])
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:02:05.000Z"
    _sub(home, [_line("attachment", "2026-10-17T07:05:00.000Z"),
                _line("user", "2026-10-17T07:30:00.000Z", "meta", isMeta=True, agentId="c1"),
                _billed("2026-10-17T07:30:02.000Z", "again")], mode="a")
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:30:02.000Z"
    _sub(home, [_line("system", "2026-10-17T07:31:00.000Z", subtype="turn_duration")], mode="a")
    ingest.ingest_all(con, run_hooks=False)
    assert _last(con, "A:c1") == "2026-10-17T07:30:02.000Z"
    assert _floor_ok(con, "A:c1")
