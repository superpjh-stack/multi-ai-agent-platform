"""작업량 집계 (spec.md §6) — requestId 중복 제거 (D-01) · <synthetic> 제외 · 포크 사본 제외 (D-02) · 자기/자손 합 ·
KST 일자 · active_seconds 5 분 (D-06).

원천 흉내는 fake_claude_home_rw (Claude Code 역할) 또는 tmp 의 가짜 루트로만.
"""

import json
from pathlib import Path

import pytest

from agentdash.collect import ingest
from agentdash.core import model as M
from agentdash.core import usage as U
from agentdash.db import conn

PK = "-tmp-proj"
SID = "11111111-2222-3333-4444-555555555555"


def _asst(uuid, rid, ts, out, model="claude-opus-5-5", tools=(), agent=None, **usage):
    u = {"input_tokens": usage.get("inp", 10), "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
         "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0}, "output_tokens": out}
    d = {"type": "assistant", "uuid": uuid, "timestamp": ts, "sessionId": SID, "requestId": rid, "cwd": "/tmp/proj",
         "message": {"model": model, "content": [{"type": "tool_use", "id": t, "name": "Bash", "input": {}} for t in tools],
                     "usage": u}}
    if rid is None:
        d.pop("requestId")
    if agent:
        d.update(agentId=agent, isSidechain=True)
    return json.dumps(d)


def _write(p: Path, lines):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(x + "\n" for x in lines))


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "projects" / PK).mkdir(parents=True)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(h))
    return h


@pytest.fixture
def con(tmp_path):
    c = conn.connect(conn.init_db(tmp_path / "u.db"))
    yield c
    c.close()


def _build(home):
    sess = home / "projects" / PK / f"{SID}.jsonl"
    _write(sess, [
        _asst("p1", "R1", "2026-10-16T14:59:00Z", 5),            # 스트리밍 중간본
        _asst("p2", "R1", "2026-10-16T14:59:01Z", 40, tools=["t1"]),   # 같은 requestId 최종본 (D-01)
        _asst("p3", "R2", "2026-10-16T15:01:00Z", 100),         # KST 10-17 00:01
        _asst("p4", None, "2026-10-16T15:02:00Z", 999, model="<synthetic>"),   # 제외
    ])
    sub = home / "projects" / PK / SID / "subagents"
    _write(sub / "agent-c1.jsonl", [_asst("c1a", "RC1", "2026-10-16T15:10:00Z", 7, agent="c1")])
    (sub / "agent-c1.meta.json").write_text(json.dumps({"agentType": "general-purpose", "toolUseId": "t1",
                                                        "spawnDepth": 1, "description": "child"}))
    # 포크: 부모(세션) 줄 p3 를 uuid · requestId 그대로 다시 적고(사본), 띄운 호출 R2 를 새 uuid 로 다시 적은 뒤 자기 줄
    _write(sub / "agent-f1.jsonl", [
        _asst("p3", "R2", "2026-10-16T15:01:00Z", 100, agent="f1"),
        _asst("fx", "R2", "2026-10-16T15:01:00Z", 100, agent="f1"),
        _asst("f1a", "RF1", "2026-10-16T15:20:00Z", 3, agent="f1"),
    ])
    (sub / "agent-f1.meta.json").write_text(json.dumps({"agentType": "fork", "isFork": True, "toolUseId": "t9",
                                                        "spawnDepth": 1, "description": "fork"}))
    # 손자 (포크 아님, parentAgentId)
    _write(sub / "agent-g1.jsonl", [_asst("g1a", "RG1", "2026-10-16T15:30:00Z", 11, agent="g1")])
    (sub / "agent-g1.meta.json").write_text(json.dumps({"agentType": "general-purpose", "toolUseId": "t8",
                                                        "spawnDepth": 2, "parentAgentId": "c1"}))


def test_dedupe_synthetic_fork_and_totals(home, con):
    _build(home)
    ingest.ingest_all(con, run_hooks=False)
    rows = dict(con.execute("SELECT request_id, output_tokens FROM usage_event WHERE agent_key=?", (f"S:{SID}",)).fetchall())
    assert rows == {"R1": 40, "R2": 100}                          # 최종본 40 · synthetic 없음
    assert con.execute("SELECT COUNT(*) FROM usage_event WHERE model='<synthetic>'").fetchone()[0] == 0
    fork = dict(con.execute("SELECT request_id, output_tokens FROM usage_event WHERE agent_key='A:f1'").fetchall())
    assert fork == {"RF1": 3}                                      # 사본 2 줄 제외 (D-02 가설 반박 → 대안 규칙)
    me = U.totals(con, f"S:{SID}")
    assert me["output_tokens"] == 140 and me["requests"] == 2
    allx = U.totals(con, f"S:{SID}", descendants=True)
    assert allx["output_tokens"] == 140 + 7 + 3 + 11              # 자기 + 자손
    kids = U.descendants(con, f"S:{SID}")
    assert set(kids) == {"A:c1", "A:f1", "A:g1"}
    # 서브에이전트 자손: 메타 parentAgentId (linker 가 parent_key 를 채우기 전)
    assert U.descendants(con, "A:c1") == ["A:g1"]
    assert U.totals(con, "A:c1", descendants=True)["output_tokens"] == 18


def test_descendants_follow_parent_key_when_set(home, con):
    _build(home)
    ingest.ingest_all(con, run_hooks=False)
    M.set_parent(con, "A:g1", "A:f1")                              # linker 가 다르게 판단하면 그것을 따른다
    assert U.descendants(con, "A:f1") == ["A:g1"]
    assert U.descendants(con, "A:c1") == []


def test_daily_kst_and_active_seconds(home, con):
    _build(home)
    ingest.ingest_all(con, run_hooks=False)
    U.rebuild_daily(con)
    rows = {(d, m): (o, t) for d, m, o, t in con.execute(
        "SELECT day, model, output_tokens, tool_calls FROM usage_daily WHERE agent_key=?", (f"S:{SID}",))}
    assert rows == {("2026-10-16", "claude-opus-5-5"): (40, 1), ("2026-10-17", "claude-opus-5-5"): (100, 0)}


def test_active_seconds_gap_rule():
    ts = ["2026-10-17T00:00:00Z", "2026-10-17T00:04:59Z", "2026-10-17T00:10:00Z", "2026-10-17T00:15:00Z",
          "2026-10-17T00:20:01Z"]
    # 299 s (포함) · 301 s (제외) · 300 s (포함) · 301 s (제외)
    assert U.active_seconds(ts) == 299 + 300
    assert U.active_seconds([]) == 0


def test_add_usage_keeps_final_stream():
    import sqlite3

    c = sqlite3.connect(":memory:")
    c.executescript(conn.SCHEMA.read_text(encoding="utf-8"))
    e = M.UsageEvent(agent_key="A:x", request_id="r", at="t1", model="m", output_tokens=5)
    assert M.add_usage(c, e)
    e2 = M.UsageEvent(agent_key="A:x", request_id="r", at="t2", model="m", output_tokens=50)
    assert not M.add_usage(c, e2)
    e3 = M.UsageEvent(agent_key="A:x", request_id="r", at="t3", model="m", output_tokens=20)
    M.add_usage(c, e3)
    assert c.execute("SELECT output_tokens, at FROM usage_event").fetchall() == [(50, "t2")]


# ── 웨이브 D — DEF-QA1-001: 포크 사본이 부모보다 더 최종인 usage 를 가지면 그 값으로 (부모 몫 그대로) ──
def _build_fork_final(home):
    sess = home / "projects" / PK / f"{SID}.jsonl"
    _write(sess, [
        _asst("p1", "R1", "2026-10-16T14:59:00Z", 10),          # 부모 기록엔 스트리밍 시작값만
        _asst("p2", "R2", "2026-10-16T15:00:00Z", 60),
    ])
    sub = home / "projects" / PK / SID / "subagents"
    # 깊이 1 서브에이전트 c1 (포크 아님) — 손자 포크의 부모
    _write(sub / "agent-c1.jsonl", [_asst("c1a", "RC1", "2026-10-16T15:10:00Z", 7, agent="c1")])
    (sub / "agent-c1.meta.json").write_text(json.dumps({"agentType": "general-purpose", "toolUseId": "t1",
                                                        "spawnDepth": 1}))
    # 포크 f1 (세션의 사본): p1 은 같은 uuid 로 더 큰 output 178 · p2 는 더 작은 값 · 띄운 호출 재기록(새 uuid · R1) 200
    _write(sub / "agent-f1.jsonl", [
        _asst("p1", "R1", "2026-10-16T14:59:00Z", 178, agent="f1"),
        _asst("p2", "R2", "2026-10-16T15:00:00Z", 30, agent="f1"),
        _asst("fx", "R1", "2026-10-16T15:00:30Z", 200, agent="f1"),
        _asst("f1a", "RF1", "2026-10-16T15:20:00Z", 3, agent="f1"),
    ])
    (sub / "agent-f1.meta.json").write_text(json.dumps({"agentType": "fork", "isFork": True, "toolUseId": "t9",
                                                        "spawnDepth": 1}))
    # 손자 포크 f2 (c1 의 사본, parentAgentId) — 경로 정렬상 부모 c1 보다 먼저 읽힐 수 있다
    _write(sub / "agent-a0f2.jsonl", [
        _asst("c1a", "RC1", "2026-10-16T15:10:00Z", 50, agent="a0f2"),
        _asst("f2a", "RF2", "2026-10-16T15:30:00Z", 4, agent="a0f2"),
    ])
    (sub / "agent-a0f2.meta.json").write_text(json.dumps({"agentType": "fork", "isFork": True, "toolUseId": "t8",
                                                          "spawnDepth": 2, "parentAgentId": "c1"}))
    return sess, sub


def _rows_of(con, key):
    return dict(con.execute("SELECT request_id, output_tokens FROM usage_event WHERE agent_key=?", (key,)).fetchall())


def test_fork_copy_final_value_goes_to_owner(home, con):
    _build_fork_final(home)
    ingest.ingest_all(con, run_hooks=False)
    assert _rows_of(con, f"S:{SID}") == {"R1": 200, "R2": 60}       # 세션 안 최댓값 · 줄어든 사본은 무시
    assert _rows_of(con, "A:f1") == {"RF1": 3}                       # 사본은 여전히 부모 몫
    assert _rows_of(con, "A:c1") == {"RC1": 50}                      # 손자 포크 사본 → 부모 서브에이전트
    assert _rows_of(con, "A:a0f2") == {"RF2": 4}
    # 시각은 소유 기록 그대로 (일자 경계가 사본 시각으로 밀리지 않게)
    at = con.execute("SELECT at FROM usage_event WHERE agent_key=? AND request_id='R1'", (f"S:{SID}",)).fetchone()[0]
    assert at == "2026-10-16T14:59:00Z"
    dup = con.execute("SELECT COUNT(*) FROM (SELECT request_id FROM usage_event GROUP BY request_id HAVING COUNT(*)>1)")
    assert dup.fetchone()[0] == 0
    assert U.totals(con, f"S:{SID}", descendants=True)["output_tokens"] == 200 + 60 + 50 + 3 + 4
    # 비용도 최종값으로 다시 계산
    c = con.execute("SELECT cost_usd FROM usage_event WHERE agent_key=? AND request_id='R1'", (f"S:{SID}",)).fetchone()[0]
    ev = M.UsageEvent(agent_key="x", request_id="R1", at="", model="claude-opus-5-5", input_tokens=10, cache_read=0,
                      cache_write_5m=0, cache_write_1h=0, output_tokens=200)
    assert c == pytest.approx(U.cost(ev, U.load_pricing())[0])


def test_fork_copy_final_when_fork_read_before_owner(home, con):
    """포크 기록이 부모보다 먼저 읽혀도(감시기 순서) 나중에 소유 행에 반영되고, 부모의 작은 값이 덮지 않는다."""
    sess, sub = _build_fork_final(home)
    ingest.ingest_path(con, sub / "agent-c1.meta.json")
    ingest.ingest_path(con, sub / "agent-a0f2.meta.json")
    ingest.ingest_path(con, sub / "agent-a0f2.jsonl")              # 부모 c1 기록 아직 안 읽음
    assert _rows_of(con, "A:a0f2") == {"RF2": 4}
    ingest.ingest_path(con, sub / "agent-c1.jsonl")
    assert _rows_of(con, "A:c1") == {"RC1": 50}


# ── 웨이브 D — DEF-QA1-006: 기간 · 묶음의 「작성 파일」 = 기간 안 고유 (agent, path) 수 ──
def _file_tool(uuid, rid, ts, tool, path, tid):
    d = json.loads(_asst(uuid, rid, ts, 5))
    d["message"]["content"] = [{"type": "tool_use", "id": tid, "name": tool, "input": {"file_path": path}}]
    return json.dumps(d)


def test_files_written_unique_over_period(home, con):
    sess = home / "projects" / PK / f"{SID}.jsonl"
    _write(sess, [
        _file_tool("w1", "R1", "2026-10-15T01:00:00Z", "Write", "/tmp/proj/a.py", "t1"),   # KST 10-15
        _file_tool("w2", "R2", "2026-10-16T01:00:00Z", "Edit", "/tmp/proj/a.py", "t2"),    # KST 10-16 같은 파일
        _file_tool("w3", "R3", "2026-10-16T02:00:00Z", "Write", "/tmp/proj/b.py", "t3"),
    ])
    ingest.ingest_all(con, run_hooks=False)
    U.rebuild_daily(con)
    for group in ("agent", "project", "type", "model"):
        t = U.table(con, "2026-10-15", "2026-10-16", group)
        assert t["total"]["files_written"] == 2, group                 # a.py · b.py (Write 와 Edit 가 다른 날이어도 1)
        assert sum(r["files_written"] for r in t["rows"]) == 2, group
    by_day = {r["key"]: r["files_written"] for r in U.table(con, "2026-10-15", "2026-10-16", "day")["rows"]}
    assert by_day == {"2026-10-15": 1, "2026-10-16": 2}                # 일자 묶음은 그날 고유 수
    assert U.table(con, "2026-10-16", "2026-10-16", "agent")["total"]["files_written"] == 2
    assert U.table(con, "2026-10-15", "2026-10-15", "agent")["total"]["files_written"] == 1


# ── 웨이브 D — DEF-QA1-002 / D-17 (차단) 임시 표기 ①: 서브에이전트 · 워크플로 출력은 「기록상 과소 (D-17)」 ──
def test_undercount_flag_on_subagent_totals(home, con):
    _build(home)
    ingest.ingest_all(con, run_hooks=False)
    own = U.totals(con, f"S:{SID}")
    assert own["undercount"] is False and own["undercount_note"] is None      # 메인 세션 자기 몫은 표기 없음
    allx = U.totals(con, f"S:{SID}", descendants=True)
    assert allx["undercount"] is True and allx["undercount_note"] == "기록상 과소 (D-17)"
    assert allx["undercount_output"] == 7 + 3 + 11                            # 과소 의심 몫 = 자손 출력
    assert U.totals(con, "A:c1")["undercount"] is True
    assert allx["output_tokens"] == 140 + 7 + 3 + 11                          # 숫자는 원천 그대로


def test_undercount_flag_in_usage_table(home, con):
    _build(home)
    ingest.ingest_all(con, run_hooks=False)
    U.rebuild_daily(con)
    t = U.table(con, "2026-10-16", "2026-10-17", "agent")
    flags = {r["key"]: r["undercount"] for r in t["rows"]}
    assert flags[f"S:{SID}"] is False and flags["A:c1"] is True and flags["A:f1"] is True
    assert t["total"]["undercount"] is True and t["undercount_note"] == "기록상 과소 (D-17)"
    assert t["total"]["undercount_output"] == 21
    by_day = U.table(con, "2026-10-16", "2026-10-17", "day")
    assert all("undercount" in r for r in by_day["rows"])
