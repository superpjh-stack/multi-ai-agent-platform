"""G-10 — 연결 규칙 L-01~L-07 (spec.md §3.2 · decisions.md D-04 · D-10).

손자 깊이 2 · 워크플로 · 늦게 읽힌 부모 재시도 · SendMessage 미해결 → 외부 노드 · 반환 신호.
픽스처(tests/fixtures, 본문 지운 실제 기록 구조)는 읽기 전용 가짜 루트로, 합성 줄은 tmp 에서만 쓴다.
"""

from __future__ import annotations

import json

import pytest

from agentdash.core import linker as L
from agentdash.core.linker import AgentRec, ReturnSignal, SpawnIndex

DH_SESSION = "8f3a6abd-0740-4164-9188-e5ac6af4cd37"
MAD_SESSION = "2bee9170-9e95-4e4e-873d-8490f228ad20"


@pytest.fixture
def scan(fake_claude_home_ro):
    return L.scan_projects(fake_claude_home_ro / "projects")


def _link(sc, key):
    return L.resolve(sc.agents[key], sc.index)


# ── L-01 ──────────────────────────────────────────────────────────────────

def test_L01_fixture_session_spawn(scan):
    lk = _link(scan, "A:ae52277140e6732bc")
    assert (lk.parent_key, lk.rule) == (f"S:{MAD_SESSION}", "L-01")
    lk = _link(scan, "A:aca12685adbb11b9c")
    assert (lk.parent_key, lk.rule) == (f"S:{DH_SESSION}", "L-01")


def test_L01_session_wins_over_fork_copy():
    """포크 기록은 부모 대화 사본을 품는다 — 같은 tool_use.id 가 세션 · 포크 둘 다 있으면 세션 (D-04 실측 26 건)."""
    idx = SpawnIndex()
    idx.add_agent_call("toolu_X", "A:fork1")
    idx.add_agent_call("toolu_X", "S:s1")
    idx.depth.update({"A:fork1": 1})
    lk = L.resolve(AgentRec("A:c", "SUBAGENT", "s1", "p", 1, "toolu_X"), idx)
    assert (lk.parent_key, lk.rule) == ("S:s1", "L-01")


# ── L-02 ──────────────────────────────────────────────────────────────────

def test_L02_fixture_grandchild_parentAgentId(scan):
    a = scan.agents["A:a76932516fc410131"]
    assert a.depth == 2 and a.parent_agent_id == "aca12685adbb11b9c"
    lk = _link(scan, "A:a76932516fc410131")
    assert (lk.parent_key, lk.rule) == ("A:aca12685adbb11b9c", "L-02")
    assert "parentAgentId" in lk.evidence and "일치" in lk.evidence


def test_L02_grandchild_without_parentAgentId_picks_lowest_depth():
    idx = SpawnIndex()
    for k, d in (("A:mid", 1), ("A:forkOfMid", 2)):
        idx.add_agent_call("toolu_G", k)
        idx.depth[k] = d
    lk = L.resolve(AgentRec("A:g", "SUBAGENT", "s1", "p", 2, "toolu_G"), idx)
    assert (lk.parent_key, lk.rule) == ("A:mid", "L-02")


def test_L02_parentAgentId_mismatch_is_reported():
    idx = SpawnIndex()
    idx.add_agent_call("toolu_M", "A:other")
    lk = L.resolve(AgentRec("A:g", "SUBAGENT", "s1", "p", 2, "toolu_M", parent_agent_id="pp"), idx)
    assert lk.parent_key == "A:pp" and "불일치" in lk.evidence


# ── L-03 ──────────────────────────────────────────────────────────────────

def test_L03_fixture_workflow(scan):
    wf = "wf_fa635efe-270"
    agents = [a for a in scan.agents.values() if a.kind == "WORKFLOW_AGENT"]
    assert len(agents) == 6
    for a in agents:
        lk = L.resolve(a, scan.index)
        assert (lk.parent_key, lk.rule) == (f"W:{wf}", "L-03")
    lk = _link(scan, f"W:{wf}")
    assert (lk.parent_key, lk.rule) == (f"S:{DH_SESSION}", "L-03")
    e = L.spawn_edge(agents[0].agent_key, L.resolve(agents[0], scan.index))
    assert e.kind == "workflow" and e.src_key == f"W:{wf}"


# ── L-04 · L-05 ───────────────────────────────────────────────────────────

def test_L04_late_parent_then_retry():
    idx = SpawnIndex()
    child = AgentRec("A:c", "SUBAGENT", "s1", "proj", 1, "toolu_LATE")
    lk = L.resolve(child, idx, sources_complete=False)
    assert (lk.parent_key, lk.rule) == (None, "L-04")
    links = {"A:c": lk}
    assert L.retry_pending([child], links, idx, sources_complete=False) == {}   # 그대로면 바뀐 것 없음
    idx.add_agent_call("toolu_LATE", "S:s1")                                    # 부모 기록이 늦게 읽힘
    changed = L.retry_pending([child], links, idx, sources_complete=False)
    assert changed["A:c"].parent_key == "S:s1" and changed["A:c"].rule == "L-01"


def test_L05_unresolved_keeps_parent_null():
    lk = L.resolve(AgentRec("A:o", "SUBAGENT", "s1", "proj-x", 1, "toolu_NONE"), SpawnIndex(), sources_complete=True)
    assert lk.parent_key is None and lk.rule == "L-05"
    assert L.unresolved_key("proj-x") in lk.evidence
    assert L.spawn_edge("A:o", lk) is None


def test_L05_fixture_tree_fully_linked(scan):
    subs = [a for a in scan.agents.values() if a.kind != "SESSION"]
    links = [L.resolve(a, scan.index) for a in subs]
    assert all(lk.resolved for lk in links), [lk.evidence for lk in links if not lk.resolved]


# ── L-06 ──────────────────────────────────────────────────────────────────

def test_L06_send_message_targets():
    ids = {"a1234567890abcdef"}
    names = {"multi-agent-dashboard-ce": "S:s1"}
    e = L.resolve_message("S:s0", "a1234567890abcdef", agent_ids=ids, names=names)
    assert (e.dst_key, e.kind, e.external) == ("A:a1234567890abcdef", "message", False)
    e = L.resolve_message("A:x", "multi-agent-dashboard-ce", agent_ids=ids, names=names)
    assert e.dst_key == "S:s1" and e.label == "multi-agent-dashboard-ce"
    e = L.resolve_message("A:x", "someone-else", agent_ids=ids, names=names)
    assert e.external and e.dst_key == "X:someone-else" and e.label == "someone-else" and e.rule == "L-06"


# ── L-07 ──────────────────────────────────────────────────────────────────

def test_L07_handback_ends_child():
    r = L.returned([ReturnSignal("2026-10-17T07:00:05.000Z", "handback")], "2026-10-17T07:00:05.000Z")
    assert r and not r.is_error and r.source == "handback"
    e = L.handback_edge("A:c", "S:s", r)
    assert (e.src_key, e.dst_key, e.kind) == ("A:c", "S:s", "handback")


def test_L07_notification_failed_is_error_and_running_is_not_end():
    r = L.returned([ReturnSignal("2026-10-17T07:00:09Z", "notification", "failed")], "2026-10-17T07:00:01Z")
    assert r and r.is_error
    assert L.returned([ReturnSignal("2026-10-17T07:00:09Z", "notification", "running")], None) is None


def test_L07_resumed_after_handback_is_not_ended():
    """handback 뒤 SendMessage 로 다시 깨워 기록이 더 쌓이면 아직 안 끝났다 (D-04: 반환 ≥ 2 실측 16 건)."""
    sig = [ReturnSignal("2026-10-17T07:00:00.000Z", "handback")]
    assert L.returned(sig, "2026-10-17T07:05:00.000Z") is None
    sig.append(ReturnSignal("2026-10-17T07:06:00.000Z", "handback"))
    r = L.returned(sig, "2026-10-17T07:06:00.000Z")
    assert r and r.count == 2


def test_L07_facts_from_lines():
    """줄 → 사실: Agent 호출 · Workflow runId · SendMessage · handback · task-notification · agent-message. 본문 없음."""
    lines = [
        {"type": "assistant", "timestamp": "t1", "message": {"content": [
            {"type": "tool_use", "name": "Agent", "id": "toolu_A", "input": {"prompt": "SECRET"}},
            {"type": "tool_use", "name": "SendMessage", "id": "toolu_S", "input": {"to": "a1", "message": "SECRET"}},
            {"type": "tool_use", "name": "SubagentHandback", "id": "toolu_H", "input": {"message": "SECRET"}}]}},
        {"type": "user", "timestamp": "t2", "toolUseResult": {"status": "async_launched", "runId": "wf_abc-1"},
         "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_W", "content": "x"}]}},
        {"type": "user", "timestamp": "t3", "message": {"content":
            "<task-notification><task-id>t</task-id><tool-use-id>toolu_A</tool-use-id><status>failed</status>"
            "<summary>SECRET</summary></task-notification> <agent-message from=\"a1\">SECRET</agent-message>"}},
        {"type": "api-request-blob", "message": {"content": [{"type": "tool_use", "name": "Agent", "id": "toolu_dup"}]}},
    ]
    got = [f for ln in lines for f in L.facts(ln)]
    kinds = [(f.kind, f.key, f.status) for f in got]
    assert kinds == [("agent_call", "toolu_A", None), ("send_message", "a1", None),
                     ("handback_call", "toolu_H", None), ("workflow_call", "wf_abc-1", None),
                     ("notification", "toolu_A", "failed"), ("agent_message", "a1", None)]
    assert "SECRET" not in json.dumps([f.__dict__ for f in got])


def test_L07_scan_end_to_end(tmp_path):
    """합성 트리: 세션 → 자식(handback) · 자식(notification failed) · 자식(신호 없음) · 손자."""
    proj = tmp_path / "projects" / "-tmp-proj"
    sdir = proj / "sess1" / "subagents"
    sdir.mkdir(parents=True)

    def w(p, rows):
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def call(tid, ts):
        return {"type": "assistant", "timestamp": ts,
                "message": {"content": [{"type": "tool_use", "name": "Agent", "id": tid, "input": {}}]}}

    w(proj / "sess1.jsonl", [call("tu1", "2026-10-17T07:00:00Z"), call("tu2", "2026-10-17T07:00:01Z"),
                             call("tu3", "2026-10-17T07:00:02Z"),
                             {"type": "user", "timestamp": "2026-10-17T07:09:00Z", "message": {"content":
                                 "<task-notification><tool-use-id>tu2</tool-use-id><status>failed</status>"
                                 "</task-notification>"}}])
    for aid, tid, depth, extra in (("a1", "tu1", 1, None), ("a2", "tu2", 1, None), ("a3", "tu3", 1, None),
                                   ("a4", "tu4", 2, None)):
        (sdir / f"agent-{aid}.meta.json").write_text(json.dumps(
            {"agentType": "general-purpose", "toolUseId": tid, "spawnDepth": depth}), encoding="utf-8")
    w(sdir / "agent-a1.jsonl", [call("tu4", "2026-10-17T07:01:00Z"),
                                {"type": "assistant", "timestamp": "2026-10-17T07:02:00Z", "message": {"content": [
                                    {"type": "tool_use", "name": "SubagentHandback", "id": "h1", "input": {}}]}}])
    w(sdir / "agent-a2.jsonl", [{"type": "assistant", "timestamp": "2026-10-17T07:03:00Z", "message": {"content": []}}])
    w(sdir / "agent-a3.jsonl", [{"type": "assistant", "timestamp": "2026-10-17T07:04:00Z", "message": {"content": []}}])
    w(sdir / "agent-a4.jsonl", [{"type": "assistant", "timestamp": "2026-10-17T07:05:00Z", "message": {"content": []}}])
    sc = L.scan_projects(tmp_path / "projects")
    got = {k: _link(sc, k).parent_key for k in ("A:a1", "A:a2", "A:a3", "A:a4")}
    assert got == {"A:a1": "S:sess1", "A:a2": "S:sess1", "A:a3": "S:sess1", "A:a4": "A:a1"}
    ret = {k: L.returned(sc.signals.get(k, []), sc.last_activity.get(k)) for k in got}
    assert ret["A:a1"] and not ret["A:a1"].is_error
    assert ret["A:a2"] and ret["A:a2"].is_error
    assert ret["A:a3"] is None and ret["A:a4"] is None


# ── DB 경로 (개발1 ingest 가 채운 DB) ─────────────────────────────────────────

def _db(tmp_path):
    from agentdash.db import conn
    p = tmp_path / "l.db"
    conn.init_db(p)
    return conn.connect(p)


def test_resolve_all_on_ingested_fixture(fake_claude_home_ro, tmp_path):
    """픽스처를 개발1 ingest 로 DB 에 넣고 resolve_all → 서브에이전트 · 워크플로 에이전트 전부 연결 (L-01 · L-02 · L-03)."""
    from agentdash.collect import ingest
    con = _db(tmp_path)
    ingest.ingest_all(con, run_hooks=False)
    # 개발1 ingest 가 줄마다 부를 linker.on_line (progress-dev2 §3 R1) 을 여기서 대신 부른다 — 픽스처에는 Workflow
    # tool_use 줄이 없고 tool_result(runId) 줄만 있다
    for jl in sorted((fake_claude_home_ro / "projects").rglob("*.jsonl")):
        if jl.name == "journal.jsonl":
            continue
        sess = jl.stem if jl.parent.parent == fake_claude_home_ro / "projects" else None
        author = f"S:{sess}" if sess else f"A:{jl.stem.removeprefix('agent-')}"
        for raw in jl.read_bytes().splitlines():
            L.on_line(con, author, json.loads(raw))
    links = L.resolve_all(con)
    rows = con.execute("SELECT agent_key, kind, parent_key FROM agent WHERE kind != 'SESSION'").fetchall()
    assert rows and all(r[2] for r in rows), [tuple(r) for r in rows if not r[2]]
    assert {lk.rule for lk in links.values()} >= {"L-01", "L-02", "L-03"}
    kinds = {r[0] for r in con.execute("SELECT DISTINCT kind FROM edge")}
    assert {"spawn", "workflow"} <= kinds
    con.close()


def test_note_notification_and_message_edges(tmp_path):
    from agentdash.core import model as M
    con = _db(tmp_path)
    M.upsert_agent(con, M.Agent(agent_key="S:s", kind="SESSION", project_key="p", session_id="s"))
    M.upsert_agent(con, M.Agent(agent_key="A:c1", kind="SUBAGENT", project_key="p", session_id="s", depth=1,
                                spawn_tool_use="tu1"))
    M.add_tool_call(con, M.ToolCall("S:s", "tu1", "2026-10-17T07:00:00Z", "Agent"))
    M.add_tool_call(con, M.ToolCall("A:c1", "tm1", "2026-10-17T07:00:10Z", "SendMessage", target="nobody"))
    M.add_tool_call(con, M.ToolCall("S:s", "tm2", "2026-10-17T07:00:11Z", "SendMessage", target="c1"))
    M.add_tool_call(con, M.ToolCall("S:s", "tm3", "2026-10-17T07:00:12Z", "SendMessage", target="c1"))
    assert L.note_notification(con, "S:s", "tu-unknown", "completed", "2026-10-17T07:01:00Z") is False
    line = {"type": "user", "timestamp": "2026-10-17T07:01:00Z",
            "message": {"content": "<task-notification><tool-use-id>tu1</tool-use-id><status>failed</status>"
                                   "</task-notification>"}}
    assert L.on_line(con, "S:s", line) == 1
    L.resolve_all(con)
    assert con.execute("SELECT parent_key, ended_at FROM agent WHERE agent_key='A:c1'").fetchone()[:] == \
        ("S:s", "2026-10-17T07:01:00Z")
    e = {(r[0], r[1], r[2]): (r[3], r[4]) for r in con.execute("SELECT src_key, dst_key, kind, label, count FROM edge")}
    assert e[("A:c1", "S:s", "handback")][0] == "notification:failed"
    assert e[("A:c1", "X:nobody", "message")] == ("nobody", 1)
    assert e[("S:s", "A:c1", "message")][1] == 2                    # 굵기 = 횟수, 다시 돌려도 그대로
    L.resolve_all(con)
    assert con.execute("SELECT count FROM edge WHERE src_key='S:s' AND dst_key='A:c1' AND kind='message'").fetchone()[0] == 2
    con.close()
