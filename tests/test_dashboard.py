"""D-01 관제판 · D-03 상세 · 원본 보기 · lifespan(R5) — 담당 개발2. 가짜 DB · 가짜 원천만 쓴다."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agentdash.db import conn
from test_graph import NOW, Synth, iso


@pytest.fixture
def db():
    con = conn.connect(conn.init_db())
    yield con
    con.close()


def client():
    from agentdash.app.main import app
    return TestClient(app)


def seed_d01(con):
    s = Synth(con)
    s.agent("S:perm", "SESSION", "-p1", "perm", state="WAITING_PERMISSION", rule="R-01", ago_min=1, name="perm-sess",
            path="/work/alpha")
    s.agent("S:in10", "SESSION", "-p1", "in10", state="WAITING_INPUT", rule="R-05", ago_min=10, name="input-10",
            path="/work/alpha")
    s.agent("S:in2", "SESSION", "-p2", "in2", state="WAITING_INPUT", rule="R-05", ago_min=2, name="input-2",
            path="/work/beta")
    s.agent("S:run", "SESSION", "-p2", "run", state="RUNNING", rule="R-02a", ago_min=0, name="runner", out=1234,
            path="/work/beta")
    s.agent("A:kid", "SUBAGENT", "-p2", "run", parent="S:run", depth=1, state="RUNNING", rule="R-09", ago_min=0,
            name="kid agent", agent_type="Explore", out=777, path="/work/beta")
    s.agent("A:slow", "SUBAGENT", "-p2", "run", parent="S:run", depth=1, state="RUNNING", rule="R-12", ago_min=2,
            name="slow agent", path="/work/beta")
    s.agent("S:done", "SESSION", "-p1", "done", state="DONE", rule="R-07", ago_min=5, name="finished", path="/work/alpha")
    con.execute("INSERT INTO tool_call (agent_key, tool_use_id, at, tool, target, ok, result_at) VALUES "
                "('A:kid','t1',?, 'Read','/work/beta/a.py',NULL,NULL)", (iso(NOW),))
    con.execute("INSERT INTO tool_call (agent_key, tool_use_id, at, tool, target, ok, result_at) VALUES "
                "('S:perm','t2',?, 'Bash','Run tests',NULL,NULL)", (iso(NOW - timedelta(minutes=1)),))
    for i in range(3):
        con.execute("INSERT INTO parse_error (path, line_no, reason, at) VALUES ('p', ?, 'JSON', ?)", (i, iso(NOW)))
    con.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('A:kid', ?, 'RUNNING', 'R-09 90초 안')",
                (iso(NOW),))
    con.execute("INSERT INTO file_touch (agent_key, path, op, at) VALUES ('A:kid','/work/beta/a.py','Write',?)", (iso(NOW),))
    con.commit()


def test_d01_dashboard(db):
    seed_d01(db)
    from agentdash.app.routers import agents as Q
    mt = Q.my_turn(db, NOW)
    assert [r["agent_key"] for r in mt] == ["S:perm", "S:in10", "S:in2"]    # 권한 대기 먼저 · 기다린 시간 긴 순
    assert mt[1]["wait_sec"] > mt[2]["wait_sec"] and mt[0]["last_tool"]["tool"] == "Bash"
    c = client()
    sm = c.get("/api/v1/summary").json()
    assert sm["states"]["WAITING_INPUT"] == 2 and sm["states"]["WAITING_PERMISSION"] == 1
    assert sm["states"]["RUNNING"] == 3 and sm["parse_errors"] == 3 and sm["my_turn"] == 3
    assert sm["today"]["output_tokens"] == 1234 + 777 and sm["today"]["files_written"] == 1
    assert sm["done_today"]["DONE"] == 1
    t = c.get("/").text
    assert "data-placeholder" not in t
    assert 'data-copy="/work/alpha"' in t and 'data-copy="perm-sess"' in t       # cwd · 이름 복사
    assert t.index("perm-sess") < t.index("input-10") < t.index("input-2")
    assert "kid agent" in t and "Read" in t and "/work/beta/a.py" in t           # 지금 도구와 대상
    assert "응답 느림" in t                                                     # R-12
    assert "3 건" in t                                                          # 파싱 오류
    assert "R-09 90초 안" in t                                                  # 상태 변화 피드
    assert "/api/v1/stream" in t
    body = c.get("/?part=body").text
    assert "<nav>" not in body and "perm-sess" in body


def test_d01_empty_db():
    conn.init_db()
    c = client()
    r = c.get("/")
    assert r.status_code == 200 and "기다리는 세션 없음" in r.text and "살아 있는 에이전트 없음" in r.text
    sm = c.get("/api/v1/summary").json()
    assert sm["agents_total"] == 0 and sm["parse_errors"] == 0


def test_agents_list_api(db):
    seed_d01(db)
    c = client()
    j = c.get("/api/v1/agents").json()
    assert j["count"] == 7
    assert {a["agent_key"] for a in c.get("/api/v1/agents?state=WAITING_INPUT").json()["agents"]} == {"S:in10", "S:in2"}
    assert {a["agent_key"] for a in c.get("/api/v1/agents?kind=SUBAGENT").json()["agents"]} == {"A:kid", "A:slow"}
    assert {a["agent_key"] for a in c.get("/api/v1/agents?project=beta").json()["agents"]} == {"S:in2", "S:run", "A:kid", "A:slow"}
    kid = [a for a in j["agents"] if a["agent_key"] == "A:kid"][0]
    assert kid["output_tokens"] == 777


def test_d03_detail(db):
    seed_d01(db)
    s = Synth(db)
    s.agent("A:grand", "SUBAGENT", "-p2", "run", parent="A:kid", depth=2, state="DONE", ago_min=0, name="grandkid", out=50)
    s.agent("A:lost", "SUBAGENT", "-p2", "run", parent=None, depth=1, state="STALE", rule="R-11", ago_min=9, name="lost")
    db.commit()
    c = client()
    d = c.get("/api/v1/agents/A:grand").json()
    assert d["found"] and [x["agent_key"] for x in d["ancestors"]] == ["S:run", "A:kid"]
    assert d["state"]["rule"] == "R-08" and d["state"]["now"]["rule"].startswith("R-")
    assert d["usage"]["cost_label"] == "[추정] API 정가 환산"
    k = c.get("/api/v1/agents/A:kid").json()
    assert [x["agent_key"] for x in k["children"]] == ["A:grand"]
    assert k["usage"]["own"]["output_tokens"] == 777 and k["usage"]["with_descendants"]["output_tokens"] == 827
    assert k["usage"]["files_written"] == 1 and k["files"][0]["path"] == "/work/beta/a.py"
    tools = c.get("/api/v1/agents/A:kid/tools").json()
    assert tools["total"] == 1 and tools["tools"][0]["result"] == "결과 없음"
    lost = c.get("/api/v1/agents/A:lost").json()
    assert lost["parent"] is None and "부모 미확인" in lost["link_note"]
    page = c.get("/agents/A:grand").text
    assert "S:run" in page and "kid agent" in page and "[추정] API 정가 환산" in page and "R-08" in page
    assert "원본 보기" in page and "data-placeholder" not in page
    assert "부모 미확인" in c.get("/agents/A:lost").text
    nf = c.get("/api/v1/agents/S:nothing")
    assert nf.status_code == 200 and nf.json()["found"] is False and nf.json()["reason"]
    assert "에이전트 없음" in c.get("/agents/S:nothing").text


def _snapshot(con) -> dict:
    out = {}
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        out[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def test_raw_view_reads_on_request_and_stores_nothing(db, fake_claude_home_rw):
    # 가짜 원천에 기록을 쓰는 것은 Claude Code 역할 흉내 (fake_claude_home_rw) — 대시보드 코드는 읽기만 한다
    proj = fake_claude_home_rw / "projects" / "-fake"
    proj.mkdir(parents=True)
    f = proj / "rawsess.jsonl"
    lines = [
        {"type": "user", "timestamp": iso(NOW), "message": {"role": "user", "content": "hello MARK_USER_TEXT"}},
        {"type": "assistant", "timestamp": iso(NOW), "message": {"model": "claude-opus-5-5", "content": [
            {"type": "thinking", "thinking": "SECRET_THINK " * 10},
            {"type": "text", "text": "answer MARK_ASSIST"},
            {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "echo first\nSECRET_LINE2"}},
            {"type": "tool_use", "id": "tu2", "name": "Write", "input": {"file_path": "/w/x.py", "content": "SECRET_CONTENT"}},
        ]}},
        {"type": "user", "timestamp": iso(NOW), "message": {"content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": "SECRET_RESULT", "is_error": True}]}},
        {"type": "attachment", "x": 1},
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    Synth(db).agent("S:rawsess", "SESSION", "-fake", "rawsess", state="DONE", rule="R-07")
    db.execute("INSERT INTO src_file (path, inode, size, offset, mtime) VALUES (?,?,?,?,?)", (str(f), 1, 1, 1, 0.0))
    db.commit()
    before = _snapshot(db)
    r = client().get("/agents/S:rawsess/raw")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    t = r.text
    assert "MARK_USER_TEXT" in t and "MARK_ASSIST" in t
    assert "command: echo first" in t and "/w/x.py" in t                       # 경로 · 첫 줄만
    for secret in ("SECRET_THINK", "SECRET_LINE2", "SECRET_CONTENT", "SECRET_RESULT"):
        assert secret not in t, secret
    assert "도구 결과 13 자" in t and "오류" in t and "<details" in t and "open" not in t.split("<details")[1][:20]
    assert _snapshot(db) == before                                              # DB 에 아무것도 안 남김
    for (tbl,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cols = [c[1] for c in db.execute(f"PRAGMA table_info({tbl})")]
        for col in cols:
            assert db.execute(f"SELECT COUNT(*) FROM {tbl} WHERE CAST({col} AS TEXT) LIKE '%MARK_USER_TEXT%'").fetchone()[0] == 0


def test_raw_view_refuses_outside_source_root(db, tmp_path):
    outside = tmp_path / "elsewhere" / "evil.jsonl"
    outside.parent.mkdir()
    outside.write_text('{"type":"user","message":{"content":"NOPE"}}\n', encoding="utf-8")
    Synth(db).agent("S:evil", "SESSION", "-e", "evil")
    db.execute("INSERT INTO src_file (path, inode, size, offset, mtime) VALUES (?,?,?,?,?)", (str(outside), 1, 1, 1, 0.0))
    db.commit()
    t = client().get("/agents/S:evil/raw").text
    assert "NOPE" not in t and "원천 루트 밖" in t
    assert "찾지 못했다" in client().get("/agents/S:none/raw").text


# ── R5 lifespan ──────────────────────────────────────────────────────
def test_lifespan_off(monkeypatch):
    monkeypatch.setenv("AGENTDASH_NO_WATCH", "1")
    from agentdash.app.main import app
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert app.state.lifespan == {"mode": "off"}


def test_lifespan_backfills_empty_db_then_watches(fake_claude_home_ro, monkeypatch):
    monkeypatch.delenv("AGENTDASH_NO_WATCH", raising=False)
    from agentdash.app.main import app
    with TestClient(app) as c:
        st = app.state.lifespan
        deadline = time.time() + 20
        while time.time() < deadline and st.get("watcher") != "실행 중" and "error" not in st:
            time.sleep(0.1)
        assert "error" not in st, st
        assert st["watcher"] == "실행 중" and st["ticker"] == "실행 중"
        assert st["backfill"].startswith("완료"), st
        sm = c.get("/api/v1/summary").json()
        assert sm["agents_total"] > 0
        g = c.get("/api/v1/graph?since=all").json()
        assert g["stats"]["agent_nodes"] > 0
    assert st["watcher"] == "멈춤" and not st["_watcher"][0].is_alive()


def _row(page: str, head: str) -> str:
    i = page.index(f"<tr><td>{head}")
    return page[i:page.index("</tr>", i)]


def test_d03_undercount_note_d17(db):
    """D-17 임시 ①: API usage.own · with_descendants 의 undercount 가 참인 칸만 출력 · 비용 옆에 「기록상 과소 (D-17)」. 숫자는 그대로."""
    seed_d01(db)
    c = client()
    note = "기록상 과소 (D-17)"
    k = c.get("/api/v1/agents/A:kid").json()["usage"]
    assert k["own"]["undercount"] and k["with_descendants"]["undercount"]
    page = c.get("/agents/A:kid").text
    assert _row(page, "출력 토큰").count(note) == 2 and _row(page, "추정 비용").count(note) == 2
    assert "777" in _row(page, "출력 토큰")
    s = c.get("/api/v1/agents/S:run").json()["usage"]
    assert not s["own"]["undercount"] and s["with_descendants"]["undercount"]          # 세션 자기 몫은 아님 · 자손 포함은 과소
    page = c.get("/agents/S:run").text
    assert _row(page, "출력 토큰").count(note) == 1 and _row(page, "추정 비용").count(note) == 1
    out = _row(page, "출력 토큰")
    assert out.index("1,234") < out.index(note)                                         # 자손 포함 칸에만 (자기 칸 뒤)
    assert note not in c.get("/agents/S:done").text                                     # 자손 없는 세션 — 표기 없음


# ── 2차-A Task 9 — D-18 확정 (spec v0.3 §4.2): 「가설 D-18」 표시 · `hypothesis` 키 제거 (DEF-QA2-201) ──────
D18_NOTE = "가설 D-18"


def _seed_sleepers(con):
    s = Synth(con)
    s.agent("S:d18", "SESSION", "-p1", "d18", state="SLEEPING", rule="R-03", ago_min=6, name="sleeper-d18")
    s.agent("S:idle", "SESSION", "-p1", "idle", state="SLEEPING", rule="R-03", ago_min=6, name="sleeper-idle")
    con.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:d18', ?, 'SLEEPING', ?)",
                (iso(NOW), "R-03 S1 status=busy · ScheduleWakeup 깰 시각 2026-10-17T10:00:00Z · 마지막 기록 … · D-18"))
    con.execute("INSERT INTO state_log (agent_key, at, state, reason) VALUES ('S:idle', ?, 'SLEEPING', ?)",
                (iso(NOW), "R-03 S1 status=idle · ScheduleWakeup 깰 시각 2026-10-17T10:00:00Z"))
    con.commit()


def test_no_hypothesis_label(db):
    """D-01 · D-02(패널은 API) · D-03 HTML 과 API 에 「가설 D-18」 0 · `hypothesis` 키 없음 · data-hypothesis 0."""
    _seed_sleepers(db)
    c = client()
    pages = [c.get("/").text, c.get("/?part=body").text, c.get("/graph").text,
             c.get("/agents/S:d18").text, c.get("/agents/S:idle").text]
    for t in pages:
        assert D18_NOTE not in t and "data-hypothesis" not in t
    for key in ("S:d18", "S:idle"):
        j = c.get(f"/api/v1/agents/{key}").json()
        assert j["found"] and "hypothesis" not in j["state"] and "hypothesis" not in j["state"]["now"]
        assert D18_NOTE not in json.dumps(j, ensure_ascii=False)
    for path in ("/api/v1/agents", "/api/v1/agents?state=SLEEPING", "/api/v1/graph"):
        r = c.get(path)
        assert r.status_code == 200 and D18_NOTE not in r.text and '"hypothesis"' not in r.text, path
    page = c.get("/agents/S:d18").text
    assert "R-03" in page[page.index("판정 (저장)"):page.index("판정 (지금)")]      # 규칙 코드는 그대로
    from agentdash.app.routers import agents as Q
    assert not hasattr(Q, "D18_NOTE") and not hasattr(Q, "hypothesis_note")


# ── 2차-A Task 11 — D-01 예산 경고 띠 (spec v0.3 §7 D-01 맨 위 · §6.3) ─────────────────────────────
def _budget_cfg(daily=None, monthly=None, projects=None):
    return {"warn_ratio": 0.8, "total": {"daily_usd": daily, "monthly_usd": monthly}, "projects": projects or {}}


def _spend(con, est, rec=None, key="S:bud"):
    from test_graph import Synth
    if con.execute("SELECT 1 FROM agent WHERE agent_key=?", (key,)).fetchone() is None:
        Synth(con).agent(key, "SESSION", "-p1", "bud", state="DONE", rule="R-07", name="budget-sess", path="/work/alpha")
    at = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    n = con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0]
    con.execute("INSERT INTO usage_event (agent_key, request_id, at, model, output_tokens, input_tokens, cost_usd, "
                "cost_est_usd) VALUES (?,?,?,?,?,?,?,?)", (key, f"rb{n}", at, "claude-opus-5", 1, 1,
                                                          est if rec is None else rec, est))
    con.commit()


def _band(page: str) -> str | None:
    i = page.find('id="budget-band"')
    return None if i < 0 else page[page.rfind("<", 0, i):page.index("</div>", i)]


def test_budget_band(db, monkeypatch):
    from agentdash.core import budget
    c = client()
    # 전부 unset → 띠 없음
    monkeypatch.setattr(budget, "load", lambda: _budget_cfg())
    _spend(db, 85.0)
    assert _band(c.get("/").text) is None and _band(c.get("/?part=body").text) is None
    # 전체 일 한도 100 · 오늘 추정 85 → warn 띠 · /insights 링크 · 85 % · 주황(WAITING_PERMISSION 색), 빨강 아님
    monkeypatch.setattr(budget, "load", lambda: _budget_cfg(daily=100))
    for page in (c.get("/").text, c.get("/?part=body").text):
        b = _band(page)
        assert b is not None, "띠 없음"
        assert 'href="/insights"' in b and "85 %" in b and "오늘 전체" in b
        assert "st-WAITING_PERMISSION" in b and "st-FAILED" not in b
        assert "[추정] API 정가 환산" in b
    # 102 → over 빨강
    _spend(db, 17.0)
    b = _band(c.get("/").text)
    assert b is not None and "st-FAILED" in b and "102 %" in b
    # 여러 칸 — worst 가 색, 문구는 warn · over 칸 전부 (spec 「오늘 전체 82 % · Standard MES 이번 달 104 %」 꼴)
    monkeypatch.setattr(budget, "load", lambda: _budget_cfg(daily=1000, monthly=110, projects={"alpha": {"daily_usd": None,
                                                                                                    "monthly_usd": 100}}))
    b = _band(c.get("/").text)
    assert "이번 달 전체 92 %" in b and "alpha 이번 달 102 %" in b and "st-FAILED" in b and "오늘 전체" not in b
    # ok 만 → 띠 없음
    monkeypatch.setattr(budget, "load", lambda: _budget_cfg(daily=1000))
    assert _band(c.get("/").text) is None


def test_budget_band_config_error_is_shown(db, monkeypatch):
    """budget.yaml 이 깨지면 조용히 띠를 숨기지 않고 오류를 적는다 (관제판은 그대로 열린다)."""
    from agentdash import settings
    from agentdash.core import budget

    def bad():
        raise settings.SettingsError("budget.yaml warn_ratio 없음")
    monkeypatch.setattr(budget, "load", bad)
    r = client().get("/")
    assert r.status_code == 200
    b = _band(r.text)
    assert b is not None and "예산 설정 오류" in b and "warn_ratio" in b
