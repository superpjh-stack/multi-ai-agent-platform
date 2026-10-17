"""G-02 파서 회귀 (V-08) — 픽스처(tests/fixtures/{2.1.295,2.1.301}, 본문 제거)로 S1 · S2 · S3 · S4 · S5 · S6 파서.

기대값은 픽스처 README 와 goal.md §6 · decisions.md D-10 · D-11 에서 온다. 모르는 필드는 무시, 필수 필드가 없으면 parse_error.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from agentdash.collect import ingest
from agentdash.collect.parsers import ParseError
from agentdash.collect.parsers import meta as meta_p
from agentdash.collect.parsers import session_file as s1_p
from agentdash.collect.parsers import transcript as tr_p
from agentdash.collect.parsers import workflow as wf_p
from agentdash.db import conn

FIX = Path(__file__).resolve().parent / "fixtures"
P301 = FIX / "2.1.301" / "projects" / "-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard"
S301 = "2bee9170-9e95-4e4e-873d-8490f228ad20"
P295 = FIX / "2.1.295" / "projects" / "-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub"
S295 = "8f3a6abd-0740-4164-9188-e5ac6af4cd37"
WF = "wf_fa635efe-270"


def _lines(p):
    return [ln for ln in p.read_bytes().split(b"\n") if ln.strip()]


# ── S1 ───────────────────────────────────────────────────────────────
def test_s1_session_file():
    sf = s1_p.parse(FIX / "2.1.301" / "sessions" / "85955.json")
    assert sf.pid == 85955 and sf.session_id == S301
    assert sf.status == "busy" and sf.kind == "interactive" and sf.version == "2.1.301"
    assert sf.updated_at.endswith("Z") and sf.started_at


def test_s1_missing_required(tmp_path):
    p = tmp_path / "1.json"
    p.write_text(json.dumps({"pid": 1, "sessionId": "x"}))
    with pytest.raises(ParseError, match="status"):
        s1_p.parse(p)
    p.write_text("{broken")
    with pytest.raises(ParseError):
        s1_p.parse(p)


# ── S2 / S3 / S5 transcript ──────────────────────────────────────────
ALL_JSONL = sorted(p for p in FIX.rglob("agent-*.jsonl")) + [P301 / f"{S301}.jsonl", P295 / f"{S295}.jsonl"]


@pytest.mark.parametrize("path", ALL_JSONL, ids=lambda p: p.name[:20])
def test_transcript_fixture_lines_all_parse(path):
    types = Counter()
    asst_tools = blob_tools = 0
    for raw in _lines(path):
        d = json.loads(raw)
        types[d.get("type")] += 1
        if d.get("type") == "api-request-blob":
            blob_tools += sum(1 for b in d["message"]["content"] if isinstance(b, dict) and b.get("type") == "tool_use")
        if d.get("type") == "assistant":
            asst_tools += sum(1 for b in d["message"]["content"] if isinstance(b, dict) and b.get("type") == "tool_use")
        rec = tr_p.parse_line(raw)          # LineError 가 나면 실패
        if d.get("type") in ("assistant", "user"):
            assert rec is not None and rec.uuid == d["uuid"] and rec.timestamp == d["timestamp"]
        elif d.get("type") != "agent-name":
            assert rec is None, d.get("type")
    recs = [tr_p.parse_line(r) for r in _lines(path)]
    tools = sum(len(r.tool_uses) for r in recs if r is not None)
    assert tools == asst_tools                    # D-11: api-request-blob 의 tool_use 는 세지 않는다
    assert types["assistant"] > 0


def test_d11_blob_tool_use_not_counted():
    path = P301 / f"{S301}.jsonl"
    recs = [r for r in (tr_p.parse_line(x) for x in _lines(path)) if r is not None]
    assert sum(len(r.tool_uses) for r in recs) == 17      # assistant 줄 tool_use 17 (blob 36 줄 안의 것은 제외)
    assert {r.type for r in recs} == {"assistant", "user"}


def test_assistant_fields_and_usage():
    path = P301 / "2bee9170-9e95-4e4e-873d-8490f228ad20" / "subagents" / "agent-ae52277140e6732bc.jsonl"
    recs = [r for r in (tr_p.parse_line(x) for x in _lines(path)) if r is not None and r.type == "assistant"]
    assert recs and all(r.model and r.request_id and r.usage for r in recs)
    assert all(r.is_sidechain is True and r.agent_id == "ae52277140e6732bc" for r in recs)
    for r in recs:
        u = r.usage
        assert u.ttl_split and u.cache_write_5m + u.cache_write_1h == u.cache_creation


def test_unknown_type_ignored_and_errors():
    assert tr_p.parse_line(b'{"type":"brand-new-kind","foo":1}') is None
    with pytest.raises(tr_p.LineError, match="JSON"):
        tr_p.parse_line(b'{"type":"assistant"')
    with pytest.raises(tr_p.LineError, match="uuid"):
        tr_p.parse_line(json.dumps({"type": "assistant", "timestamp": "2026-10-17T00:00:00Z", "sessionId": "s",
                                    "message": {"model": "m"}}))
    with pytest.raises(tr_p.LineError, match="message.model"):
        tr_p.parse_line(json.dumps({"type": "assistant", "uuid": "u", "timestamp": "2026-10-17T00:00:00Z",
                                    "sessionId": "s", "message": {"content": []}}))
    with pytest.raises(tr_p.LineError, match="type"):
        tr_p.parse_line(b'{"uuid":"x"}')


def _asst(content, usage=None, **top):
    d = {"type": "assistant", "uuid": "u1", "timestamp": "2026-10-17T00:00:00.000Z", "sessionId": "s1",
         "requestId": "r1", "message": {"model": "claude-opus-5-5", "content": content, "usage": usage or {}}}
    d.update(top)
    return json.dumps(d).encode()


def test_targets_keep_no_body():
    secret = "SECRET-BODY-xyz"
    content = [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": secret}},
        {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": secret, "description": "list files"}},
        {"type": "tool_use", "id": "t3", "name": "Write", "input": {"file_path": "/x/a.py", "content": secret}},
        {"type": "tool_use", "id": "t4", "name": "Agent", "input": {"description": "D" * 200, "prompt": secret}},
        {"type": "tool_use", "id": "t5", "name": "WebFetch", "input": {"url": "https://example.org/p?q=1", "prompt": secret}},
        {"type": "tool_use", "id": "t6", "name": "SendMessage", "input": {"to": "dev2", "message": secret}},
        {"type": "tool_use", "id": "t7", "name": "ScheduleWakeup", "input": {"delaySeconds": 90, "prompt": secret}},
        {"type": "text", "text": secret},
        {"type": "thinking", "thinking": secret},
    ]
    r = tr_p.parse_line(_asst(content))
    got = {t.id: (t.target, t.file_path) for t in r.tool_uses}
    assert got["t1"] == (None, None)
    assert got["t2"] == ("list files", None)
    assert got["t3"] == ("/x/a.py", "/x/a.py")
    assert got["t4"][0] == "D" * 120
    assert got["t5"][0] == "example.org"
    assert got["t6"][0] == "dev2"
    assert got["t7"][0] == "wake@2026-10-17T00:01:30Z"
    assert secret not in repr(r)


def test_usage_ttl_split_and_legacy():
    r = tr_p.parse_line(_asst([], {"input_tokens": 3, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 30,
                                   "cache_creation": {"ephemeral_5m_input_tokens": 10, "ephemeral_1h_input_tokens": 20},
                                   "output_tokens": 50, "output_tokens_details": {"thinking_tokens": 7},
                                   "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 2},
                                   "speed": "fast"}))
    u = r.usage
    assert (u.input_tokens, u.cache_read, u.cache_write_5m, u.cache_write_1h, u.output_tokens) == (3, 10, 10, 20, 50)
    assert (u.thinking_tokens, u.web_search, u.web_fetch, u.speed, u.ttl_split) == (7, 1, 2, "fast", True)
    legacy = tr_p.parse_line(_asst([], {"input_tokens": 1, "cache_creation_input_tokens": 40, "output_tokens": 2}))
    assert (legacy.usage.cache_write_5m, legacy.usage.cache_write_1h, legacy.usage.ttl_split) == (40, 0, False)
    assert legacy.usage.speed is None and legacy.usage.thinking_tokens is None


def test_user_tool_result():
    line = json.dumps({"type": "user", "uuid": "u2", "timestamp": "2026-10-17T00:00:01Z", "sessionId": "s1",
                       "message": {"role": "user", "content": [
                           {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "x"},
                           {"type": "tool_result", "tool_use_id": "t2", "content": "y"}]}})
    r = tr_p.parse_line(line)
    assert [(x.tool_use_id, x.is_error) for x in r.tool_results] == [("t1", True), ("t2", None)]


# ── S4 / S5 meta ─────────────────────────────────────────────────────
def test_s4_meta_depth1():
    m = meta_p.parse(P301 / S301 / "subagents" / "agent-ae52277140e6732bc.meta.json")
    assert m.agent_id == "ae52277140e6732bc" and m.session_id == S301
    assert m.project_key == P301.name and m.spawn_depth == 1 and m.tool_use_id and m.agent_type
    assert not m.is_fork and m.parent_agent_id is None and m.wf_id is None


def test_s4_meta_depth2_fork_d10():
    m = meta_p.parse(P295 / S295 / "subagents" / "agent-a76932516fc410131.meta.json")
    assert m.agent_type == "fork" and m.is_fork and m.spawn_depth == 2
    assert m.parent_agent_id == "aca12685adbb11b9c" and m.tool_use_id
    ex = m.extra()
    assert ex.parent_agent_id == "aca12685adbb11b9c" and ex.is_fork and ex.jsonl_path.endswith(".jsonl")


def test_s5_workflow_meta_d10():
    metas = sorted((P295 / S295 / "subagents" / "workflows" / WF).glob("agent-*.meta.json"))
    assert len(metas) == 6
    for p in metas:
        m = meta_p.parse(p)
        assert m.agent_type == "workflow-subagent" and m.workflow_phase and m.tool_use_id is None
        assert m.wf_id == WF and m.session_id == S295 and m.is_workflow_agent


def test_meta_missing_agent_type(tmp_path):
    d = tmp_path / "proj" / "sess" / "subagents"
    d.mkdir(parents=True)
    p = d / "agent-abc.meta.json"
    p.write_text(json.dumps({"description": "x"}))
    with pytest.raises(ParseError, match="agentType"):
        meta_p.parse(p)


# ── S6 workflow + journal ───────────────────────────────────────────
def test_s6_workflow():
    w = wf_p.parse(P295 / S295 / "workflows" / f"{WF}.json")
    assert w.run_id == WF and w.session_id == S295 and w.project_key == P295.name
    assert w.status == "completed" and w.agent_count == 6 and w.phases == ["Port"]
    assert w.duration_ms and w.started_at and w.ended_at and w.ended_at > w.started_at


def test_s5_journal_labels():
    labels = {}
    for raw in _lines(P295 / S295 / "subagents" / "workflows" / WF / "journal.jsonl"):
        got = wf_p.parse_journal_line(raw)
        if got:
            labels[got[0]] = got[1]
    assert len(labels) == 6
    ids = {p.name[len("agent-"):-len(".jsonl")] for p in (P295 / S295 / "subagents" / "workflows" / WF).glob("agent-*.jsonl")}
    assert set(labels) == ids


# ── 분류 + 전체 수집 (가짜 루트, 읽기 전용) ───────────────────────────
def test_classify(fake_claude_home):
    h = fake_claude_home
    pk = P295.name
    assert ingest.classify(h / "sessions" / "85955.json") == "S1"
    assert ingest.classify(h / "projects" / pk / f"{S295}.jsonl") == "S2"
    assert ingest.classify(h / "projects" / pk / S295 / "subagents" / "agent-aca12685adbb11b9c.jsonl") == "S3"
    assert ingest.classify(h / "projects" / pk / S295 / "subagents" / "agent-aca12685adbb11b9c.meta.json") == "S4"
    wfd = h / "projects" / pk / S295 / "subagents" / "workflows" / WF
    assert ingest.classify(wfd / "agent-a5de9442449dd9e3f.jsonl") == "S5"
    assert ingest.classify(wfd / "agent-a5de9442449dd9e3f.meta.json") == "S5meta"
    assert ingest.classify(wfd / "journal.jsonl") == "S5journal"
    assert ingest.classify(h / "projects" / pk / S295 / "workflows" / f"{WF}.json") == "S6"
    assert ingest.classify(h / "projects" / pk / S295 / "tool-results" / "x.txt") is None


@pytest.mark.readonly_source
def test_ingest_fixture_tree(fake_claude_home, tmp_path):
    con = conn.connect(conn.init_db(tmp_path / "p.db"))
    ingest.ingest_all(con, run_hooks=False)
    con.commit()
    kinds = dict(con.execute("SELECT kind, COUNT(*) FROM agent GROUP BY kind").fetchall())
    assert kinds == {"SESSION": 2, "SUBAGENT": 3, "WORKFLOW_AGENT": 6, "WORKFLOW": 1}
    assert con.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0] == 0
    # 메타 필드 저장 (D-10) — 연결 판단은 하지 않는다
    a = con.execute("SELECT depth, agent_type, spawn_tool_use, name, parent_key FROM agent WHERE agent_key='A:a76932516fc410131'").fetchone()
    assert a[0] == 2 and a[1] == "fork" and a[2] and a[3]
    w = con.execute("SELECT kind, name, session_id FROM agent WHERE agent_key=?", (f"W:{WF}",)).fetchone()
    assert w[0] == "WORKFLOW" and w[2] == S295
    s = con.execute("SELECT pid, name, cc_version, project_path FROM agent WHERE agent_key=?", (f"S:{S301}",)).fetchone()
    assert s[0] == 85955 and s[1] and s[3]
    # 도구 호출: assistant 줄 tool_use 만 (D-11) — 세션 2.1.301 은 17
    assert con.execute("SELECT COUNT(*) FROM tool_call WHERE agent_key=?", (f"S:{S301}",)).fetchone()[0] == 17
    # 모든 TEXT ≤ 300 (V-04)
    for t in ("agent", "edge", "usage_event", "tool_call", "file_touch", "parse_error", "src_file"):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        for c in cols:
            mx = con.execute(f"SELECT MAX(LENGTH({c})) FROM {t} WHERE typeof({c})='text'").fetchone()[0]
            assert mx is None or mx <= 300, (t, c, mx)
    con.close()


def test_broken_line_goes_to_parse_error(fake_claude_home_rw, tmp_path):
    p = fake_claude_home_rw / "projects" / P301.name / f"{S301}.jsonl"
    with open(p, "ab") as fh:                 # Claude Code 역할 — 깨진 줄 · 필수 필드 없는 줄
        fh.write(b'{"type":"assistant","uuid":\n')
        fh.write(b'{"type":"user","timestamp":"2026-10-17T00:00:00Z","sessionId":"s"}\n')
        fh.write(b'{"type":"brand-new","x":1}\n')
    con = conn.connect(conn.init_db(tmp_path / "p.db"))
    ingest.ingest_all(con, run_hooks=False)
    rows = con.execute("SELECT line_no, reason FROM parse_error WHERE path=?", (str(p),)).fetchall()
    n = len(_lines(p))
    assert [r[0] for r in rows] == [n - 2, n - 1]
    assert "JSON" in rows[0][1] and "uuid" in rows[1][1]
    con.close()


def test_workflow_result_run_id():
    line = json.dumps({"type": "user", "uuid": "u3", "timestamp": "2026-10-17T00:00:02Z", "sessionId": "s1",
                       "toolUseResult": {"status": "async_launched", "runId": "wf_abc-1", "summary": "본문"},
                       "message": {"content": [{"type": "tool_result", "tool_use_id": "tw", "content": "x"}]}})
    r = tr_p.parse_line(line)
    assert r.tool_results[0].run_id == "wf_abc-1"
    assert "본문" not in repr(r)
