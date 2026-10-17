"""G-18 — 구성도 (spec.md §5). 합성 데이터(가짜 DB, 원천 없음)로:
  · 노드 300 개에서 /api/v1/graph ≤ 300 ms (보기 3 종 각각)
  · 노드 300 초과 → DONE 서브에이전트를 부모 안으로 접고 "+N", expand 로 펼침
  · 보기 3 종 응답 (breadthfirst · cose · preset + 파이프라인 열)
  · 노드 5 종 · 엣지 4 종 · 상태 색 데이터 · √토큰 크기 · 사람 행동 배지 · 필터
  · 빈 DB 200
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agentdash.core import graph as G
from agentdash.db import conn

NOW = datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


COLS = ("agent_key", "kind", "project_key", "project_path", "session_id", "parent_key", "depth", "agent_type", "name",
        "started_at", "last_event_at", "ended_at", "state", "state_reason", "state_since")


class Synth:
    def __init__(self, con):
        self.con = con
        self.n = 0

    def agent(self, key, kind, proj, sid, parent=None, depth=0, state="DONE", rule="R-08", ago_min=10, name=None,
              agent_type=None, out=0, path=None):
        t = NOW - timedelta(minutes=ago_min)
        self.con.execute(f"INSERT INTO agent ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})",
                         (key, kind, proj, path or f"/x/{proj}", sid, parent, depth, agent_type, name or key,
                          iso(t - timedelta(minutes=5)), iso(t), iso(t) if state in ("DONE", "FAILED") and kind != "SESSION" else None,
                          state, rule, iso(t)))
        if parent:
            self.con.execute("INSERT OR IGNORE INTO edge (src_key, dst_key, kind, at) VALUES (?,?,?,?)",
                             (parent, key, "workflow" if parent.startswith("W:") else "spawn", iso(t)))
        if out:
            self.n += 1
            self.con.execute("INSERT INTO usage_event (agent_key, request_id, at, model, output_tokens, input_tokens) "
                             "VALUES (?,?,?,?,?,?)", (key, f"req{self.n}", iso(t), "claude-opus-5-5", out, 10))
        return key

    def edge(self, src, dst, kind, count=1, label=None):
        self.con.execute("INSERT OR REPLACE INTO edge (src_key, dst_key, kind, at, count, label) VALUES (?,?,?,?,?,?)",
                         (src, dst, kind, iso(NOW), count, label))


@pytest.fixture
def db():
    p = conn.init_db()
    con = conn.connect(p)
    yield con
    con.close()


def build_300(con) -> int:
    """정확히 노드 300 개가 되게: 프로젝트 4 · 세션 48 · 서브에이전트 240 · 워크플로 1 + 에이전트 3 · 부모 미확인 1 + 그룹 1 · 외부 그룹 1 + 외부 1."""
    s = Synth(con)
    names = ["01 Analyze Agent", "02 Design Agent", "03 UI Agent", "Multi-agent Dashboard"]
    for pi, pname in enumerate(names):
        proj = f"-x-{pi}"
        for si in range(12):
            sid = f"s{pi}-{si}"
            sk = s.agent(f"S:{sid}", "SESSION", proj, sid, state="WAITING_INPUT" if si == 0 else "RUNNING",
                         rule="R-05" if si == 0 else "R-02a", ago_min=1, out=5000 * si, path=f"/x/{pname}")
            for ai in range(5):
                st = ["RUNNING", "DONE", "STALE", "WAITING_CHILD", "DONE"][ai]
                s.agent(f"A:{sid}-{ai}", "SUBAGENT", proj, sid, parent=sk, depth=1, state=st, rule="R-09",
                        ago_min=2, agent_type="general-purpose", out=1000 * ai * ai, path=f"/x/{pname}")
    # 워크플로 (프로젝트 0)
    s.agent("W:wf_1", "WORKFLOW", "-x-0", "s0-1", parent="S:s0-1", depth=1, state="DONE", rule="R-08", ago_min=3,
            path="/x/01 Analyze Agent")
    for i in range(3):
        s.agent(f"A:wf1-{i}", "WORKFLOW_AGENT", "-x-0", "s0-1", parent="W:wf_1", depth=2, state="DONE",
                agent_type="workflow-subagent", ago_min=3, path="/x/01 Analyze Agent")
    # 부모 미확인 (L-05)
    s.agent("A:orphan", "SUBAGENT", "-x-1", "s1-0", parent=None, depth=1, state="STALE", rule="R-11", ago_min=4,
            path="/x/02 Design Agent")
    # message · handback · 외부
    s.edge("S:s0-0", "S:s1-0", "message", count=4)
    s.edge("A:s0-0-1", "S:s0-0", "handback", label="success")
    s.edge("S:s2-0", "X:someone", "message", count=2, label="someone")
    con.commit()
    return 300


def test_empty_db_200():
    conn.init_db()
    c = TestClient(__import__("agentdash.app.main", fromlist=["app"]).app)
    for v in ("tree", "collab", "pipeline"):
        r = c.get(f"/api/v1/graph?view={v}")
        assert r.status_code == 200
        j = r.json()
        assert j["nodes"] == [] and j["edges"] == [] and j["view"] == v
        assert "_placeholder" not in j
    assert c.get("/graph").status_code == 200


def test_300_nodes_under_300ms_each_view(db):
    build_300(db)
    from agentdash.app.main import app
    c = TestClient(app)
    c.get("/api/v1/graph")                        # 데우기 (import · 첫 연결)
    timings = {}
    for v, layout in (("tree", "breadthfirst"), ("collab", "cose"), ("pipeline", "preset")):
        t0 = time.perf_counter()
        r = c.get(f"/api/v1/graph?view={v}")
        ms = (time.perf_counter() - t0) * 1000
        timings[v] = ms
        assert r.status_code == 200
        j = r.json()
        assert j["layout"] == layout
        assert j["stats"]["nodes"] == 300, j["stats"]
        assert j["stats"]["folded"] == 0
        assert ms <= 300, timings
    print("G-18 /api/v1/graph ms", {k: round(v, 1) for k, v in timings.items()})


def test_node_and_edge_kinds(db):
    build_300(db)
    g = G.build(db, now=NOW)
    kinds = {n["data"]["kind"] for n in g["nodes"]}
    assert {"PROJECT", "SESSION", "SUBAGENT", "WORKFLOW", "UNRESOLVED", "EXTERNAL"} <= kinds
    ekinds = {e["data"]["kind"] for e in g["edges"]}
    assert ekinds == {"spawn", "message", "handback", "workflow"}
    by = {n["data"]["id"]: n for n in g["nodes"]}
    # 부모 미확인 → U:<project> 점선 엣지
    assert "U:-x-1" in by and by["U:-x-1"]["data"]["parent"] == "P:-x-1"
    un = [e for e in g["edges"] if e["data"]["target"] == "A:orphan"]
    assert un and un[0]["data"]["source"] == "U:-x-1" and un[0]["data"].get("unresolved") == 1
    # 외부 노드 (L-06)
    assert by["X:someone"]["data"]["kind"] == "EXTERNAL"
    # message 굵기 = 횟수
    m = [e for e in g["edges"] if e["data"]["kind"] == "message" and e["data"]["target"] == "S:s1-0"][0]
    assert m["data"]["count"] == 4 and m["data"]["width"] == 5
    # 워크플로 → 에이전트 엣지는 workflow
    assert any(e["data"]["kind"] == "workflow" and e["data"]["source"] == "W:wf_1" for e in g["edges"])
    # 상태 · 배지 · 크기 · 맥박 대상
    assert by["S:s0-0"]["data"]["badge"] == "!" and "badge" in by["S:s0-0"]["classes"]
    assert by["A:s0-0-2"]["data"]["badge"] == "?"             # STALE — 확인
    assert by["A:s0-0-0"]["data"]["state"] == "RUNNING"
    assert by["A:s0-0-4"]["data"]["size"] > by["A:s0-0-1"]["data"]["size"]   # √출력 토큰
    assert G.node_size(0) == 18 and G.node_size(10 ** 8) == 90
    # 서브에이전트 라벨 = 유형 + 이름 앞 24 자
    assert by["A:s0-0-0"]["data"]["label"].startswith("[GP] ")
    # 파이프라인 열
    assert by["P:-x-0"]["data"]["col"] == 1 and by["P:-x-3"]["data"]["col"] is None


def test_fold_over_300_and_expand(db):
    s = Synth(db)
    for si in range(2):
        sid = f"big{si}"
        sk = s.agent(f"S:{sid}", "SESSION", "-p", sid, state="WAITING_CHILD", rule="R-04", ago_min=1)
        for ai in range(200):
            st = "RUNNING" if ai < 5 else "DONE"
            ak = s.agent(f"A:{sid}-{ai}", "SUBAGENT", "-p", sid, parent=sk, depth=1, state=st, ago_min=2)
            if ai == 7:                               # 손자 — DONE 이면 먼저 손자가 자식 안으로, 그다음 자식이 세션 안으로
                s.agent(f"A:{sid}-{ai}-g", "SUBAGENT", "-p", sid, parent=ak, depth=2, state="DONE", ago_min=2)
            if ai == 8:                               # 살아 있는 손자 → 그 부모(DONE)는 접지 않는다
                s.agent(f"A:{sid}-{ai}-g", "SUBAGENT", "-p", sid, parent=ak, depth=2, state="RUNNING", ago_min=1)
    db.commit()
    g = G.build(db, now=NOW)
    st = g["stats"]
    assert st["nodes_before_fold"] > G.NODE_LIMIT
    assert st["nodes"] <= G.NODE_LIMIT, st
    by = {n["data"]["id"]: n["data"] for n in g["nodes"]}
    # 세션 둘 다 "+N" — 접힌 수 = 자식 DONE 195-1(8 번은 살아 있는 손자 때문에 남음) + 손자 1
    for si in range(2):
        d = by[f"S:big{si}"]
        assert d["folded"] == 195 and d["label"].endswith(f"+{d['folded']}"), d
    assert st["folded"] == 2 * 195
    assert "A:big0-8" in by and "A:big0-8-g" in by           # 살아 있는 손자를 품은 DONE 자식은 남는다
    assert all(f"A:big0-{i}" in by for i in range(5))          # RUNNING 은 접지 않는다
    assert "A:big0-100" not in by
    # 접힌 노드의 엣지는 빠진다 (없는 노드를 가리키는 엣지 0)
    ids = set(by)
    assert all(e["data"]["source"] in ids and e["data"]["target"] in ids for e in g["edges"])
    # expand — 그 세션의 직계 자식은 접지 않는다
    g2 = G.build(db, now=NOW, expand="S:big0")
    by2 = {n["data"]["id"]: n["data"] for n in g2["nodes"]}
    assert "A:big0-100" in by2 and by2["S:big0"]["folded"] == 0
    assert by2["S:big1"]["folded"] == 195
    # API 로도 같은 결과
    from agentdash.app.main import app
    j = TestClient(app).get("/api/v1/graph?view=tree").json()
    assert j["stats"]["folded"] == 2 * 195 and j["stats"]["nodes"] <= 300


def test_filters(db):
    s = Synth(db)
    s.agent("S:old", "SESSION", "-a", "old", state="DONE", rule="R-07", ago_min=60 * 48)
    s.agent("S:oldalive", "SESSION", "-a", "oldalive", state="WAITING_INPUT", rule="R-05", ago_min=60 * 48)
    s.agent("S:new", "SESSION", "-b", "new", state="DONE", rule="R-07", ago_min=30, out=50000, path="/x/02 Design Agent")
    s.agent("A:new-1", "SUBAGENT", "-b", "new", parent="S:new", depth=1, state="DONE", ago_min=30, out=10)
    db.commit()
    ids = lambda g: {n["data"]["id"] for n in g["nodes"] if n["data"]["kind"] != "PROJECT"}
    assert ids(G.build(db, now=NOW)) == {"S:oldalive", "S:new", "A:new-1"}         # 기본 24 시간 + 살아 있는 것
    assert "S:old" in ids(G.build(db, now=NOW, since="all"))
    assert ids(G.build(db, now=NOW, since="7d")) >= {"S:old"}
    assert ids(G.build(db, now=NOW, project="-b")) == {"S:new", "A:new-1"}
    assert ids(G.build(db, now=NOW, project="Design")) == {"S:new", "A:new-1"}       # 폴더 이름 일부
    assert ids(G.build(db, now=NOW, states="WAITING_INPUT")) == {"S:oldalive"}
    assert ids(G.build(db, now=NOW, kinds="SUBAGENT")) == {"A:new-1", "S:new"}       # 조상은 흐리게(ctx) 붙는다
    g = G.build(db, now=NOW, kinds="SUBAGENT")
    assert "ctx" in {n["data"]["id"]: n for n in g["nodes"]}["S:new"]["classes"]
    assert ids(G.build(db, now=NOW, min_tokens=1000)) == {"S:new"}
    with pytest.raises(G.GraphError):
        G.build(db, now=NOW, since="yesterday")
    from agentdash.app.main import app
    c = TestClient(app)
    assert c.get("/api/v1/graph?view=nope").status_code == 422
    assert "view" in c.get("/api/v1/graph?view=nope").json()["error"]


def test_graph_page_has_pinned_cdn_and_views():
    conn.init_db()
    from agentdash.app.main import app
    t = TestClient(app).get("/graph").text
    assert 'src="https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"' in t
    for v in ("tree", "collab", "pipeline"):
        assert f'data-view="{v}"' in t
    assert "breadthfirst" in t and "cose" in t and "/api/v1/stream" in t   # 보기 배치 · SSE
    assert "data-placeholder" not in t
