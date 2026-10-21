"""G-31 · G-32 — 디지털 트윈 배치 (spec.md v0.4 §5.4 T-01~T-07 · §8 `/api/v1/twin`). 담당 개발2.

합성 데이터(가짜 DB, 원천 없음)로 배치 규칙 표 기반 테스트 + 계획 Review Focus (라인 간 부모 · 순환 · 뿌리 안 접힘 ·
24 자 · 경과 클램프) + 300 설비 겹침 0 · ≤ 300 ms + API (빈 DB 200 · build 와 같음 · 잘못된 since 422 · TEXT ≤ 300).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agentdash.core import twin as T
from agentdash.core import usage
from agentdash.db import conn

NOW = datetime(2026, 10, 21, 10, 30, 20, tzinfo=timezone.utc)

COLS = ("agent_key", "kind", "project_key", "project_path", "session_id", "parent_key", "depth", "agent_type", "name",
        "started_at", "last_event_at", "ended_at", "state", "state_reason", "state_since")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ago(minutes: float) -> datetime:
    return NOW - timedelta(minutes=minutes)


class Synth:
    def __init__(self, con):
        self.con = con
        self.n = 0

    def agent(self, key, kind="SUBAGENT", proj="-p-a", sid=None, parent=None, depth=0, state="RUNNING", rule="R-02a",
              started=20, last=1, ended=None, name=None, path=None, state_since=None, edge=True):
        sid = sid or (key[2:] if kind == "SESSION" else "s0")
        if ended is None and state in ("DONE", "FAILED"):
            ended = last
        self.con.execute(
            f"INSERT INTO agent ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})",
            (key, kind, proj, path if path is not None else f"/x/{proj.strip('-')}", sid, parent, depth, None,
             name if name is not None else key, iso(ago(started)), iso(ago(last)),
             iso(ago(ended)) if ended is not None else None, state, rule,
             state_since if state_since is not None else iso(ago(last))))
        if parent and edge:
            self.con.execute("INSERT OR IGNORE INTO edge (src_key, dst_key, kind, at) VALUES (?,?,?,?)",
                             (parent, key, "workflow" if parent.startswith("W:") else "spawn", iso(ago(started))))
        return key

    def usage(self, key, minutes_ago, out, est=None, cost=None, model="claude-opus-5-5"):
        self.n += 1
        self.con.execute(
            "INSERT INTO usage_event (agent_key, request_id, at, model, output_tokens, output_est, input_tokens, cost_usd, "
            "cost_est_usd) VALUES (?,?,?,?,?,?,?,?,?)",
            (key, f"r{self.n}", iso(ago(minutes_ago)), model, out, est, 10, cost, cost))

    def tool(self, key, tid, minutes_ago, tool, target, ok=None):
        self.con.execute("INSERT INTO tool_call (agent_key, tool_use_id, at, tool, target, ok) VALUES (?,?,?,?,?,?)",
                         (key, tid, iso(ago(minutes_ago)), tool, target, ok))

    def edge(self, src, dst, kind, count=1):
        self.con.execute("INSERT OR REPLACE INTO edge (src_key, dst_key, kind, at, count) VALUES (?,?,?,?,?)",
                         (src, dst, kind, iso(NOW), count))


@pytest.fixture
def db():
    p = conn.init_db()
    con = conn.connect(p)
    yield con
    con.close()


def build(con, **kw):
    kw.setdefault("now", NOW)
    return T.build(con, **kw)


_LINE_X: dict[str, int] = {}          # 설비 키 → 자기 라인 상자 x (T-08 격자에서 열 계산용)


def machines(resp) -> dict[str, dict]:
    for ln in resp["lines"]:
        for m in ln["machines"]:
            _LINE_X[m["key"]] = ln["box"]["x"]
    return {m["key"]: m for ln in resp["lines"] for m in ln["machines"]}


def line_of(resp, key) -> dict:
    return next(ln for ln in resp["lines"] if any(m["key"] == key for m in ln["machines"]))


def col(m) -> int:
    return (m["box"]["x"] - _LINE_X.get(m["key"], 0) - T.LINE_PAD) // (T.BOX_W + T.GAP_X)


def rows_order(line) -> list[str]:
    return [m["key"] for m in sorted(line["machines"], key=lambda m: (m["box"]["y"], m["box"]["x"]))]


# ── T-01 라인 순서 ────────────────────────────────────────────────────
def test_T01_line_order(db):
    s = Synth(db)
    s.agent("S:old", "SESSION", proj="-p-zzz", state="DONE", last=5)          # 끝남, 최근
    s.agent("S:b", "SESSION", proj="-p-bbb", state="RUNNING", last=50)        # 살아 있음, 오래됨
    s.agent("S:a", "SESSION", proj="-p-aaa", state="WAITING_INPUT", last=10)  # 살아 있음, 최근
    s.agent("S:c1", "SESSION", proj="-p-ccc", state="DONE", last=60)          # 끝남, 같은 시각 → 이름 순
    s.agent("S:c2", "SESSION", proj="-p-ddd", state="DONE", last=60)
    db.commit()
    r = build(db)
    assert [ln["name"] for ln in r["lines"]] == ["p-aaa", "p-bbb", "p-zzz", "p-ccc", "p-ddd"]
    assert r["lines"][0]["live"] == 1 and r["lines"][2]["live"] == 0
    assert r["lines"][0]["counts"] == {"WAITING_INPUT": 1}


# ── T-02 열 = 부모 사슬 길이 ──────────────────────────────────────────
def test_T02_column_is_chain_depth(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:c", parent="S:s0", depth=5)        # agent.depth 는 일부러 틀리게
    s.agent("A:g", parent="A:c", depth=0)
    s.agent("A:orphan", depth=1)                  # 부모 미확인 → 반입구 아래 1 열
    db.commit()
    r = build(db)
    m = machines(r)
    assert (col(m["S:s0"]), col(m["A:c"]), col(m["A:g"])) == (0, 1, 2)
    assert col(m["A:orphan"]) == 1
    ln = r["lines"][0]
    assert ln["inlet"]["key"] == "U:-p-a"
    assert ln["inlet"]["box"]["y"] == m["A:orphan"]["box"]["y"] and ln["inlet"]["box"]["x"] == T.LINE_PAD
    assert {"src": "U:-p-a", "dst": "A:orphan", "kind": "spawn"}.items() <= next(
        p for p in ln["pipes"] if p["dst"] == "A:orphan").items()


# ── T-03 행 = 깊이 우선 · started_at 순 ───────────────────────────────
def test_T03_rows_dfs_by_started(db):
    s = Synth(db)
    s.agent("S:A", "SESSION", started=120)
    s.agent("A:B", parent="S:A", started=30)    # 10:00
    s.agent("A:C", parent="S:A", started=90)    # 09:00 — 먼저
    s.agent("A:D", parent="A:B", started=20)
    s.agent("A:E", parent="S:A", started=30)    # B 와 같은 시각 → agent_key 순 (B < E)
    db.commit()
    r = build(db)
    assert rows_order(r["lines"][0]) == ["S:A", "A:C", "A:B", "A:D", "A:E"]
    ys = [m["box"]["y"] for m in r["lines"][0]["machines"]]
    assert len(set(ys)) == len(ys)              # 한 설비는 한 행


# ── T-04 겹침 0 (합성 300 설비) ───────────────────────────────────────
def synth_300(con) -> int:
    s = Synth(con)
    n = 0
    for li in range(7):
        proj = f"-p-line{li}"
        sessions = 6 if li < 6 else 3
        for si in range(sessions):
            sk = s.agent(f"S:{li}-{si}", "SESSION", proj=proj, sid=f"{li}-{si}", state="RUNNING", started=60 - si)
            n += 1
            s.usage(sk, 0.5, 50)
            sid = f"{li}-{si}"
            c0 = s.agent(f"A:{sid}-0", proj=proj, sid=sid, parent=sk, state="WAITING_CHILD", started=50)
            g = s.agent(f"A:{sid}-0-0", proj=proj, sid=sid, parent=c0, state="WAITING_CHILD", started=45)
            x = s.agent(f"A:{sid}-0-0-0", proj=proj, sid=sid, parent=g, state="RUNNING", started=40)
            s.agent(f"A:{sid}-0-0-0-0", proj=proj, sid=sid, parent=x, state="RUNNING", started=35)   # 4 열
            c1 = s.agent(f"A:{sid}-1", proj=proj, sid=sid, parent=sk, state="DONE", started=49, ended=1)
            s.agent(f"A:{sid}-1-0", proj=proj, sid=sid, parent=c1, state="DONE", started=48, ended=2)
            n += 6
            s.usage(x, 3, 100 + si)
            s.usage(c1, 1, 7)
    # 부모 미확인 몇 개
    while n < 300:
        s.agent(f"A:orph{n}", proj="-p-line0", sid="0-0", state="RUNNING")
        n += 1
    con.commit()
    return n


def test_T04_no_overlap_300(db):
    n = synth_300(db)
    assert n == 300
    r = build(db)
    m = machines(r)
    assert len(m) == 300
    assert len(r["lines"]) == 7
    assert max(col(x) for x in m.values()) == 4
    assert T.overlaps(r) == 0
    for ln in r["lines"]:                       # 라인 상자는 자기 설비를 감싼다
        lb = ln["box"]
        for x in ln["machines"]:
            b = x["box"]
            assert lb["x"] <= b["x"] and b["x"] + b["w"] <= lb["x"] + lb["w"]
            assert lb["y"] <= b["y"] and b["y"] + b["h"] <= lb["y"] + lb["h"]
        assert all(isinstance(v, int) for v in lb.values())


def test_overlaps_counts_pairs():
    box = {"x": 0, "y": 0, "w": 10, "h": 10}
    resp = {"lines": [{"box": {"x": 0, "y": 0, "w": 100, "h": 100}, "inlet": None,
                       "machines": [{"box": box}, {"box": {"x": 5, "y": 5, "w": 10, "h": 10}},
                                    {"box": {"x": 10, "y": 0, "w": 10, "h": 10}}]}]}   # 마지막은 닿기만 — 겹침 아님
    assert T.overlaps(resp) == 2                 # (0,1) · (1,2)


# ── T-05 끝난 지 30 분 넘으면 접기 ────────────────────────────────────
def test_T05_fold_done_after_30m(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:old", parent="S:s0", state="DONE", rule="R-08", last=31)
    s.agent("A:oldkid", parent="A:old", state="DONE", rule="R-08", last=40)   # 자손도 함께
    s.agent("A:fresh", parent="S:s0", state="FAILED", rule="R-10", last=29)
    s.usage("A:old", 31, 500)
    db.commit()
    r = build(db)
    m = machines(r)
    assert "A:old" not in m and "A:oldkid" not in m
    assert "A:fresh" in m
    assert m["S:s0"]["folded"] == 2
    assert m["S:s0"]["out_total"] == 0           # 접힌 설비 숫자는 부모 누적에 더하지 않는다 (§6 그대로)
    assert all(p["dst"] not in ("A:old", "A:oldkid") for p in r["lines"][0]["pipes"])


def test_T05_live_descendant_keeps_parent(db):
    """끝난 부모 아래 살아 있는 자손이 있으면 접지 않는다 — 살아 있는 설비를 숨기지 않는다 (progress-dev2 2차-T 해석)."""
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:old", parent="S:s0", state="DONE", last=45)
    s.agent("A:live", parent="A:old", state="RUNNING")
    db.commit()
    m = machines(build(db))
    assert {"A:old", "A:live"} <= set(m)


def test_T05_orphan_folds_into_inlet(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:o1", state="DONE", last=50)
    db.commit()
    r = build(db)
    assert "A:o1" not in machines(r)
    assert r["lines"][0]["inlet"]["folded"] == 1
    assert T.scope_count(r) == r["agents_in_scope"] == 2


# ── T-06 300 넘으면 뒤 라인부터 접기 ──────────────────────────────────
def test_T06_fold_lines_over_limit(db):
    s = Synth(db)
    for li, (n, last) in enumerate([(5, 1), (4, 2), (5, 3)]):
        proj = f"-p-l{li}"
        sk = s.agent(f"S:{li}", "SESSION", proj=proj, sid=str(li), last=last)
        for i in range(n - 1):
            s.agent(f"A:{li}-{i}", proj=proj, sid=str(li), parent=sk, last=last)
    db.commit()
    r = build(db, limit=10)
    assert r["folded_lines"] >= 1
    assert sum(len(ln["machines"]) for ln in r["lines"]) <= 10
    assert [ln["name"] for ln in r["lines"]] == ["p-l0", "p-l1", "p-l2"]      # 접힌 라인도 머리 한 줄로 남는다
    folded = [ln for ln in r["lines"] if ln["folded_line"]]
    assert [ln["name"] for ln in folded] == ["p-l2"]                          # 뒤 라인부터
    assert folded[0]["hidden"] == 5 and folded[0]["machines"] == []
    narrow = [ln for ln in build(db, limit=10, width=360)["lines"] if ln["folded_line"]]
    assert narrow[0]["box"]["h"] == T.LINE_HEAD                               # 1 열이면 머리 한 줄 (같은 행 높이 맞춤 없음)
    assert T.scope_count(r) == 14
    assert T.overlaps(r) == 0


# ── T-07 결정적 ──────────────────────────────────────────────────────
def test_T07_deterministic(db):
    synth_300(db)
    a, b = build(db), build(db)
    a.pop("elapsed_ms"), b.pop("elapsed_ms")
    assert a == b


# ── 설비 값 ──────────────────────────────────────────────────────────
def test_machine_values(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:c", parent="S:s0")
    s.usage("A:c", 0.1, 10, est=None, cost=0.5)
    s.usage("A:c", 5, 2, est=400, cost=0.25)
    s.usage("A:c", 90, 7, cost=None)
    s.usage("A:c", 2, 999, model="<synthetic>")
    s.usage("S:s0", 1, 3, cost=0.1)
    s.tool("A:c", "t1", 10, "Read", "/x/a.py", ok=1)
    s.tool("A:c", "t2", 4, "Bash", "uv run pytest", ok=None)     # 결과 없는 마지막
    s.tool("A:c", "t3", 3, "Edit", "/x/b.py", ok=0)
    db.commit()
    r = build(db)
    m = machines(r)
    for k in ("S:s0", "A:c"):
        t = usage.totals(db, k)
        assert m[k]["out_total"] == t["output_tokens"]
        assert m[k]["out_est_total"] == t["output_est_total"]
        assert m[k]["cost_est_usd"] == t["cost_est_usd"]
    assert m["A:c"]["spark"] == usage.spark(db, ["A:c"], NOW)["A:c"]
    assert len(m["A:c"]["spark"]) == 30 and m["A:c"]["spark"][-1] == 10 and m["A:c"]["spark"][-6] == 400
    assert (m["A:c"]["tool"], m["A:c"]["target"]) == ("Bash", "uv run pytest")
    assert (m["S:s0"]["tool"], m["S:s0"]["target"]) == (None, None)
    c = m["A:c"]
    assert set(c) == {"key", "kind", "name", "parent", "state", "rule", "since", "elapsed_s", "tool", "target",
                      "out_total", "out_est_total", "cost_est_usd", "spark", "folded", "box", "wake_at",
                      "ended_ago_s", "last_ago_s"}
    assert c["parent"] == "S:s0" and c["kind"] == "SUBAGENT" and c["rule"] == "R-02a"
    assert c["box"] == {"x": c["box"]["x"], "y": c["box"]["y"], "w": T.BOX_W, "h": T.BOX_H}
    assert set(r) >= {"generated_at", "lines", "links", "folded_lines", "elapsed_ms"}
    assert set(r["lines"][0]) >= {"key", "name", "live", "counts", "box", "machines", "pipes"}
    assert r["lines"][0]["pipes"] == [{"src": "S:s0", "dst": "A:c", "kind": "spawn", "at": iso(ago(20))}]


def test_sleeping_wake_at(db):
    """spec §7.4 SLEEPING 「깰 시각 표시」 — 마지막 state_log 근거의 ScheduleWakeup 시각 (★ wake_at). 다른 상태는 None."""
    s = Synth(db)
    s.agent("S:z", "SESSION", state="SLEEPING", rule="R-03")
    s.agent("S:w", "SESSION", state="SLEEPING", rule="R-03")
    s.agent("S:r", "SESSION", state="RUNNING")
    db.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:z', ?, 'RUNNING', 'R-02a x')", (iso(ago(9)),))
    db.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:z', ?, 'SLEEPING', ?)",
               (iso(ago(2)), "R-03 S1 status=idle · ScheduleWakeup 깰 시각 2026-10-21T11:00:00Z · 마지막 기록 …"))
    db.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:w', ?, 'SLEEPING', 'R-03 근거 없음')",
               (iso(ago(2)),))
    db.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:r', ?, 'SLEEPING', ?)",
               (iso(ago(3)), "R-01 ScheduleWakeup 2026-10-21T11:00:00Z"))
    db.commit()
    m = machines(build(db))
    assert m["S:z"]["wake_at"] == "2026-10-21T11:00:00Z"
    assert m["S:w"]["wake_at"] is None and m["S:r"]["wake_at"] is None


def test_handback_and_message(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:c", parent="S:s0", state="DONE", last=2)
    s.agent("S:s1", "SESSION", proj="-p-b")
    s.edge("A:c", "S:s0", "handback")
    s.edge("S:s0", "S:s1", "message", count=3)
    s.edge("S:s0", "X:someone", "message", count=2)
    db.commit()
    r = build(db)
    ln = line_of(r, "A:c")
    assert {"src": "A:c", "dst": "S:s0", "kind": "handback"}.items() <= next(
        p for p in ln["pipes"] if p["kind"] == "handback").items()
    links = {(x["src"], x["dst"], x["kind"]): x["count"] for x in r["links"]}
    assert links == {("S:s0", "S:s1", "message"): 3, ("S:s0", "X:someone", "message"): 2}


def test_filters(db):
    s = Synth(db)
    s.agent("S:a", "SESSION", proj="-p-a", state="DONE", started=60 * 31, last=60 * 30)  # 24h 밖
    s.agent("S:b", "SESSION", proj="-p-b", state="RUNNING", started=60 * 31, last=60 * 30)  # 살아 있으면 범위 안
    s.agent("S:c", "SESSION", proj="-p-c", state="DONE", last=10)
    db.commit()
    assert set(machines(build(db))) == {"S:b", "S:c"}
    assert set(machines(build(db, since="all"))) == {"S:a", "S:b", "S:c"}
    assert set(machines(build(db, project="p-c"))) == {"S:c"}
    with pytest.raises(T.TwinError):
        build(db, since="yesterday")


def test_workflow_children(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("W:wf", "WORKFLOW", parent="S:s0")
    s.agent("A:w1", "WORKFLOW_AGENT", parent="W:wf")
    db.commit()
    r = build(db)
    m = machines(r)
    assert (col(m["W:wf"]), col(m["A:w1"])) == (1, 2)
    kinds = {(p["src"], p["dst"]): p["kind"] for p in r["lines"][0]["pipes"]}
    assert kinds == {("S:s0", "W:wf"): "spawn", ("W:wf", "A:w1"): "workflow"}


# ── Review Focus ─────────────────────────────────────────────────────
def test_cross_line_parent(db):
    """부모가 다른 라인 → 자식은 자기 라인 반입구 아래 1 열, 부모 쪽으로 links kind=spawn. 한 번만 그린다."""
    s = Synth(db)
    s.agent("S:p", "SESSION", proj="-p-a", sid="p")
    s.agent("S:q", "SESSION", proj="-p-b", sid="q")
    s.agent("A:x", proj="-p-b", sid="q", parent="S:p")
    s.agent("A:xk", proj="-p-b", sid="q", parent="A:x")
    db.commit()
    r = build(db)
    keys = [m["key"] for ln in r["lines"] for m in ln["machines"]]
    assert keys.count("A:x") == 1 and keys.count("A:xk") == 1
    lb = line_of(r, "A:x")
    assert lb["key"] == "-p-b"
    m = machines(r)
    assert col(m["A:x"]) == 1 and col(m["A:xk"]) == 2
    assert lb["inlet"]["box"]["y"] == m["A:x"]["box"]["y"]
    assert {"src": "S:p", "dst": "A:x", "kind": "spawn", "count": 1} in r["links"]
    assert all(p["dst"] != "A:x" for ln in r["lines"] for p in ln["pipes"])       # 배관과 라인 간 링크 이중 0
    assert m["A:x"]["parent"] == "S:p"
    assert T.overlaps(r) == 0


def test_parent_cycle_terminates(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:a", parent="A:b", edge=False)
    s.agent("A:b", parent="A:a", edge=False)
    s.agent("A:self", parent="A:self", edge=False)
    s.agent("A:k", parent="A:a")
    db.commit()
    r = build(db)
    keys = [m["key"] for ln in r["lines"] for m in ln["machines"]]
    assert sorted(keys) == ["A:a", "A:b", "A:k", "A:self", "S:s0"]           # 각 한 번
    m = machines(r)
    assert col(m["A:a"]) == 1 and col(m["A:self"]) == 1                     # 순환을 끊은 설비는 반입구 아래 1 열
    assert col(m["A:b"]) == 2 and col(m["A:k"]) == 2
    assert T.overlaps(r) == 0


def test_root_never_folded(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION", state="DONE", rule="R-08", last=120)
    s.agent("A:c", parent="S:s0", state="DONE", rule="R-08", last=100)
    db.commit()
    r = build(db)
    m = machines(r)
    assert set(m) == {"S:s0"}
    assert m["S:s0"]["folded"] == 1


def test_name_clip_24(db):
    s = Synth(db)
    long_ko = "가나다라마바사아자차카타파하" * 3
    emoji = "🤖🚀" * 20
    s.agent("S:s0", "SESSION", name=long_ko)
    s.agent("A:e", parent="S:s0", name=emoji)
    s.agent("A:blank", parent="S:s0", name="  ")
    db.commit()
    m = machines(build(db))
    assert m["S:s0"]["name"] == long_ko[:24] and len(m["S:s0"]["name"]) == 24
    assert m["A:e"]["name"] == emoji[:24]
    assert m["A:blank"]["name"] == "blank"[:24]                  # 이름이 비면 키 앞부분


def test_elapsed_clamped(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION", state_since=iso(NOW + timedelta(minutes=5)))   # 미래
    s.agent("A:c", parent="S:s0", state_since=iso(ago(2)))
    s.agent("A:n", parent="S:s0", state_since="")
    db.commit()
    m = machines(build(db))
    assert m["S:s0"]["elapsed_s"] == 0
    assert m["A:c"]["elapsed_s"] == 120
    assert m["A:n"]["elapsed_s"] is None


# ── 성능 ─────────────────────────────────────────────────────────────
def test_build_300_under_300ms(db):
    synth_300(db)
    build(db)                                     # 첫 호출(캐시) 제외
    r = build(db)
    assert sum(len(ln["machines"]) for ln in r["lines"]) == 300
    assert r["elapsed_ms"] <= 300


# ── API (Task 4) ─────────────────────────────────────────────────────
@pytest.fixture
def client():
    from agentdash.app.main import app
    conn.init_db()
    return TestClient(app)


def test_twin_api_empty_db_200(client):
    r = client.get("/api/v1/twin")
    assert r.status_code == 200
    j = r.json()
    assert "_placeholder" not in j
    assert j["lines"] == [] and j["links"] == [] and j["folded_lines"] == 0


def test_twin_api_matches_build(client, monkeypatch):
    con = conn.connect()
    synth_300(con)
    con.close()
    fixed = datetime.now(timezone.utc)
    monkeypatch.setattr(T, "_now", lambda: fixed)
    j = client.get("/api/v1/twin", params={"since": "all"}).json()
    con = conn.connect()
    b = T.build(con, since="all", now=fixed)
    con.close()
    j.pop("elapsed_ms"), b.pop("elapsed_ms")
    assert j == b
    assert client.get("/api/v1/twin", params={"project": "line3"}).json()["lines"][0]["name"] == "p-line3"


def test_twin_api_bad_since_422(client):
    r = client.get("/api/v1/twin", params={"since": "어제"})
    assert r.status_code == 422
    assert "since" in r.json()["error"]


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def test_twin_text_le_300(client):
    con = conn.connect()
    s = Synth(con)
    s.agent("S:s0", "SESSION", name="x" * 300, path="/x/" + "p" * 300)
    s.agent("A:c", parent="S:s0")
    s.tool("A:c", "t1", 1, "Bash", "y" * 300)
    con.commit()
    con.close()
    j = client.get("/api/v1/twin").json()
    assert j["lines"]
    assert max(len(x) for x in _strings(j)) <= 300


# ── 웨이브 D (2차-T) — DEF-QA1-402 · D-28 라인 이름 · T-07 행 순서 ────────────
TABLES = ("agent", "usage_event", "tool_call", "edge", "state_log")


def reversed_copy(con, path):
    """같은 DB 상태를 행 물리 순서만 뒤집어 새 DB 에 넣는다 (rowid 도 거꾸로)."""
    p = conn.init_db(path)
    dst = conn.connect(p)
    for t in TABLES:
        rows = con.execute(f"SELECT * FROM {t} ORDER BY rowid DESC").fetchall()
        if rows:
            dst.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * len(rows[0]))})", [tuple(r) for r in rows])
    dst.commit()
    return dst


def seed_names(s):
    s.agent("A:sub", proj="-x-Proj", sid="s0", parent="S:s0", path="/x/Proj/dev")       # 하위 폴더 — 먼저 넣는다
    s.agent("S:s0", "SESSION", proj="-x-Proj", path="/x/Proj")
    s.agent("A:deep", proj="-x-Proj", sid="s0", parent="A:sub", path="/x/Proj/dev/contracts")
    s.agent("S:t1", "SESSION", proj="-x-tie", path="/x/bb")                               # 길이 같음 → 사전순
    s.agent("S:t2", "SESSION", proj="-x-tie", path="/x/aa")
    s.agent("S:np", "SESSION", proj="-Users-me-NoPath", path="")                          # 경로 없음 → project_key
    s.agent("S:z", "SESSION", state="SLEEPING", rule="R-03")
    for reason in ("R-03 ScheduleWakeup 깰 시각 2026-10-21T11:00:00Z", "R-03 ScheduleWakeup 깰 시각 2026-10-21T12:00:00Z"):
        s.con.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:z', ?, 'SLEEPING', ?)",
                      (iso(ago(2)), reason))                                               # 같은 시각 두 줄
    s.con.commit()


def test_line_name_shortest_path(db):
    """D-28: 그 project_key 의 project_path 중 가장 짧은 것(같으면 사전순)의 마지막 이름, 없으면 project_key."""
    seed_names(Synth(db))
    names = {ln["key"]: ln["name"] for ln in build(db)["lines"]}
    assert names["-x-Proj"] == "Proj"
    assert names["-x-tie"] == "aa"
    assert names["-Users-me-NoPath"] == "-Users-me-NoPath"


def test_T07_row_order_independent(db, tmp_path):
    """T-07 (v0.4.1): DB 행 물리 순서만 다른 같은 상태 → 좌표까지 같은 응답."""
    seed_names(Synth(db))
    synth_300(db)
    other = reversed_copy(db, tmp_path / "rev.db")
    try:
        for kw in ({}, {"since": "all"}, {"project": "Proj"}):
            a, b = build(db, **kw), build(other, **kw)
            a.pop("elapsed_ms"), b.pop("elapsed_ms")
            assert a == b, kw
    finally:
        other.close()


# ── DEF-QA1-401 프로젝트 필터 = 라인 단위 (D-02 와 같음) ─────────────────────
def test_project_filter_whole_line(db):
    seed_names(Synth(db))
    for f in ("Proj", "-x-Proj", "roj"):
        r = build(db, project=f)
        assert [ln["key"] for ln in r["lines"]] == ["-x-Proj"], f
        assert set(machines(r)) == {"S:s0", "A:sub", "A:deep"}, f          # 하위 폴더 에이전트도 라인에 남는다
        assert r["lines"][0]["inlet"] is None                              # 부모가 빠져 반입구로 가지 않는다
    assert build(db, project="contracts")["lines"] == []                   # 하위 폴더 이름은 라인 이름이 아니다
    from agentdash.core import graph as G
    g = {n["data"]["id"] for n in G.build(db, project="Proj", now=NOW)["nodes"] if n["data"]["kind"] != "PROJECT"}
    assert g == set(machines(build(db, project="Proj")))                   # D-02 와 같은 집합


# ── DEF-QA1-403 빠진 테스트 (T-05 경계 · FAILED · D-25 범위 밖 부모 · T-06 + T-05) ───
def test_T05_exactly_30m_stays(db):
    """「30 분 넘게」 — 정확히 30:00 은 남고 30:01 은 접힌다."""
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:at30", parent="S:s0", state="DONE", rule="R-08", last=30)
    s.agent("A:at30s1", parent="S:s0", state="DONE", rule="R-08", last=30 + 1 / 60)
    db.commit()
    m = machines(build(db))
    assert "A:at30" in m and "A:at30s1" not in m
    assert m["S:s0"]["folded"] == 1


def test_T05_failed_after_30m_folds(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:f", parent="S:s0", state="FAILED", rule="R-10", last=45)
    s.agent("A:fk", parent="A:f", state="DONE", rule="R-08", last=50)
    db.commit()
    r = build(db)
    assert set(machines(r)) == {"S:s0"}
    assert machines(r)["S:s0"]["folded"] == 2
    assert T.scope_count(r) == r["agents_in_scope"] == 3


def test_D25_parent_outside_24h(db):
    """D-25: 부모가 범위(24h) 밖 → 조상을 끌어오지 않고 자기 라인 반입구 아래 1 열. parent 키는 실제 부모."""
    s = Synth(db)
    s.agent("S:old", "SESSION", state="DONE", rule="R-08", started=60 * 40, last=60 * 30)      # 24h 밖
    s.agent("A:mid", parent="S:old", state="DONE", rule="R-08", started=60 * 39, last=60 * 29)
    s.agent("A:stale", parent="A:mid", state="STALE", rule="R-11", started=60 * 28, last=60 * 26)  # 살아 있음 → 범위 안
    s.agent("S:now", "SESSION")
    db.commit()
    r = build(db)
    m = machines(r)
    assert set(m) == {"S:now", "A:stale"} and r["agents_in_scope"] == 2
    ln = line_of(r, "A:stale")
    assert col(m["A:stale"]) == 1 and m["A:stale"]["parent"] == "A:mid"
    assert ln["inlet"]["box"]["y"] == m["A:stale"]["box"]["y"]
    assert {"src": ln["inlet"]["key"], "dst": "A:stale", "kind": "spawn"}.items() <= next(
        p for p in ln["pipes"] if p["dst"] == "A:stale").items()
    assert r["links"] == []
    assert T.scope_count(r) == 2


def test_T06_after_T05(db):
    """T-05 로 접은 뒤에도 > limit 이면 뒤 라인부터 접는다. 칸 + 접힘 = 범위."""
    s = Synth(db)
    for li, last in enumerate((1, 2, 3)):
        proj = f"-p-k{li}"
        sk = s.agent(f"S:{li}", "SESSION", proj=proj, sid=str(li), last=last)
        for i in range(4):
            s.agent(f"A:{li}-{i}", proj=proj, sid=str(li), parent=sk, last=last)
        for i in range(3):                                      # T-05 로 접히는 끝난 자식
            s.agent(f"A:{li}-d{i}", proj=proj, sid=str(li), parent=sk, state="DONE", rule="R-08", last=40)
    db.commit()
    r = build(db, limit=10)
    shown = sum(len(ln["machines"]) for ln in r["lines"])
    assert shown == 10 and r["folded_lines"] == 1
    assert [ln["key"] for ln in r["lines"] if ln["folded_line"]] == ["-p-k2"]
    assert next(ln for ln in r["lines"] if ln["folded_line"])["hidden"] == 8
    assert all(machines(r)[f"S:{li}"]["folded"] == 3 for li in (0, 1))
    assert T.scope_count(r) == r["agents_in_scope"] == 24
    assert T.overlaps(r) == 0


# ── T-08 라인 격자 (v0.4.1 · D-30 · DEF-QA2-402) ──────────────────────────────
def six_lines(con, extra_rows=None):
    s = Synth(con)
    for li in range(6):
        proj = f"-p-g{li}"
        sk = s.agent(f"S:g{li}", "SESSION", proj=proj, sid=f"g{li}", last=1 + li)       # T-01: g0 가장 최근
        for i in range((extra_rows or {}).get(li, 1)):
            s.agent(f"A:g{li}-{i}", proj=proj, sid=f"g{li}", parent=sk, last=1 + li)
    con.commit()


def inside(ln, b):
    lb = ln["box"]
    return lb["x"] <= b["x"] and b["x"] + b["w"] <= lb["x"] + lb["w"] and lb["y"] <= b["y"] and b["y"] + b["h"] <= lb["y"] + lb["h"]


def test_T08_grid_1400_two_or_more_cols(db):
    six_lines(db)
    r = build(db)                                                   # width 기본 1400
    ls = r["lines"]
    assert [ln["key"] for ln in ls] == [f"-p-g{i}" for i in range(6)]
    xs = sorted({ln["box"]["x"] for ln in ls})
    assert len(xs) >= 2 and r["grid"]["cols"] == len(xs) and r["grid"]["width"] == 1400
    cols = r["grid"]["cols"]
    widths = [ln["box"]["w"] for ln in ls]
    assert sum(sorted(widths)[-cols:]) + (cols - 1) * T.LINE_GAP <= 1400  # 들어간다
    # T-01 순서대로 왼 → 오른, 위 → 아래
    for i, ln in enumerate(ls):
        row, c = divmod(i, cols)
        assert ln["box"]["x"] == xs[c]
        if row == 0:
            assert ln["box"]["y"] == 0
        else:
            assert ln["box"]["y"] > ls[(row - 1) * cols]["box"]["y"]
    for ln in ls:
        for m in ln["machines"]:
            assert inside(ln, m["box"])
    assert T.overlaps(r) == 0
    a, b = build(db), build(db, width=1400)
    a.pop("elapsed_ms"), b.pop("elapsed_ms")
    assert a == b                                                   # width 없으면 1400


def test_T08_narrow_one_col(db):
    six_lines(db)
    r = build(db, width=360)
    assert r["grid"]["cols"] == 1
    ys = [ln["box"]["y"] for ln in r["lines"]]
    assert all(ln["box"]["x"] == 0 for ln in r["lines"]) and ys == sorted(ys) and len(set(ys)) == 6
    y = 0
    for ln in r["lines"]:                                             # v0.4 과 같은 세로 쌓기
        assert ln["box"]["y"] == y
        y += ln["box"]["h"] + T.LINE_GAP
    assert T.overlaps(r) == 0


def test_T08_same_row_height(db):
    six_lines(db, extra_rows={0: 4, 1: 1, 2: 2})
    r = build(db, width=1400)
    cols = r["grid"]["cols"]
    assert cols >= 2
    ls = r["lines"]
    for i in range(0, len(ls), cols):
        row = ls[i:i + cols]
        assert len({ln["box"]["y"] for ln in row}) == 1
        assert len({ln["box"]["h"] for ln in row}) == 1                # 그 행에서 가장 높은 라인에 맞춘다
    assert ls[0]["box"]["h"] == T.LINE_HEAD + 5 * (T.BOX_H + T.GAP_Y) - T.GAP_Y + T.LINE_PAD
    assert T.overlaps(r) == 0


def test_T08_column_width_is_widest_in_column(db):
    """한 열 너비 = 그 열에 놓인 라인 중 가장 넓은 라인 — 다음 열 x = 앞 열 최대 너비 + LINE_GAP."""
    s = Synth(db)
    s.agent("S:w0", "SESSION", proj="-p-w0", sid="w0", last=1)
    s.agent("S:w1", "SESSION", proj="-p-w1", sid="w1", last=2)
    s.agent("S:w2", "SESSION", proj="-p-w2", sid="w2", last=3)
    a = s.agent("A:w2a", proj="-p-w2", sid="w2", parent="S:w2", last=3)
    s.agent("A:w2b", proj="-p-w2", sid="w2", parent=a, last=3)          # 3 열짜리 라인 — 0 열 2 행째
    s.agent("S:w3", "SESSION", proj="-p-w3", sid="w3", last=4)
    db.commit()
    r = build(db, width=1100)
    assert r["grid"]["cols"] == 2
    ls = {ln["key"]: ln["box"] for ln in r["lines"]}
    assert ls["-p-w1"]["x"] == ls["-p-w3"]["x"] == ls["-p-w2"]["w"] + T.LINE_GAP
    assert T.overlaps(r) == 0


@pytest.mark.parametrize("width", [1, 360, 1400, 4000])
def test_T08_300_no_overlap_fast(db, width):
    synth_300(db)
    build(db, width=width)
    r = build(db, width=width)
    assert sum(len(ln["machines"]) for ln in r["lines"]) == 300
    assert T.overlaps(r) == 0
    for ln in r["lines"]:
        for m in ln["machines"]:
            assert inside(ln, m["box"])
        if ln["inlet"]:
            assert inside(ln, ln["inlet"]["box"])
    assert r["elapsed_ms"] <= 300
    assert r["grid"]["cols"] >= (3 if width >= 4000 else 1)          # 300 합성 라인 폭 1296


def test_T08_bad_width(db):
    for w in (0, -5, True, 1.5, "x"):
        with pytest.raises(T.TwinError):
            build(db, width=w)


def test_twin_api_width(client):
    con = conn.connect()
    six_lines(con)
    con.close()
    assert client.get("/api/v1/twin", params={"width": "360"}).json()["grid"]["cols"] == 1
    assert client.get("/api/v1/twin").json()["grid"] == client.get("/api/v1/twin", params={"width": 1400}).json()["grid"]
    for bad in ("abc", "0", "-3", "1.5", "99999999"):
        r = client.get("/api/v1/twin", params={"width": bad})
        assert r.status_code == 422, bad
        assert "width" in r.json()["error"]


# ── DEF-QA2-401 경과 의미 · DEF-QA2-404 끝난 설비의 지금 도구 ──────────────────
def test_elapsed_meaning_after_backfill(db):
    """백필 직후(state_since = 백필 시각 1 분 전 전부 같음)에도 끝난 설비는 ended_at 기준, 멈춤 의심은 마지막 기록 기준이 다르다.
    elapsed_s = now − state_since (상태 지속) · ended_ago_s = now − ended_at (DONE/FAILED 만) · last_ago_s = now − last_event_at."""
    s = Synth(db)
    bf = iso(ago(1))
    s.agent("S:s0", "SESSION", state_since=bf, last=0.5)
    s.agent("A:d10", parent="S:s0", state="DONE", rule="R-08", last=10, state_since=bf)
    s.agent("A:d20", parent="S:s0", state="FAILED", rule="R-10", last=20, state_since=bf)
    s.agent("S:st", "SESSION", proj="-p-b", state="STALE", rule="R-11", last=60 * 20, state_since=bf)
    db.commit()
    m = machines(build(db))
    assert {x["elapsed_s"] for x in m.values()} == {60}                       # 상태 지속은 모두 같다 (백필 시각)
    assert m["A:d10"]["ended_ago_s"] == 600 and m["A:d20"]["ended_ago_s"] == 1200
    assert m["S:s0"]["ended_ago_s"] is None and m["S:st"]["ended_ago_s"] is None
    assert m["S:st"]["last_ago_s"] == 60 * 60 * 20 and m["S:s0"]["last_ago_s"] == 30
    s.agent("A:fut", parent="S:s0", state="DONE", rule="R-08", last=-5)        # 미래 시각 → 0 으로
    db.commit()
    m = machines(build(db))
    assert m["A:fut"]["ended_ago_s"] == 0 and m["A:fut"]["last_ago_s"] == 0


def test_final_machine_has_no_current_tool(db):
    s = Synth(db)
    s.agent("S:s0", "SESSION")
    s.agent("A:done", parent="S:s0", state="DONE", rule="R-08", last=3)
    s.agent("A:run", parent="S:s0")
    s.tool("A:done", "t1", 4, "SubagentHandback", "x", ok=None)               # 결과 없는 마지막 도구가 남아 있어도
    s.tool("A:run", "t2", 1, "Bash", "uv run pytest", ok=None)
    db.commit()
    m = machines(build(db))
    assert (m["A:done"]["tool"], m["A:done"]["target"]) == (None, None)
    assert (m["A:run"]["tool"], m["A:run"]["target"]) == ("Bash", "uv run pytest")
