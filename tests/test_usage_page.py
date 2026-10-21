"""G-20 비용 화면 — D-04 에 `[추정] API 정가 환산` 표기 · 단가 없음 N 건 · `make reprice` 뒤 합계 일치 (가짜 DB 만)."""

from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentdash.core import model as M
from agentdash.core import usage as U
from agentdash.db import conn

ROOT = Path(__file__).resolve().parents[1]
LABEL = "[추정] API 정가 환산"


def _ev(key, rid, at, model, i=1000, cr=5000, w5=200, o=300, speed=None):
    return M.UsageEvent(agent_key=key, request_id=rid, at=at, model=model, speed=speed, input_tokens=i, cache_read=cr,
                        cache_write_5m=w5, cache_write_1h=0, output_tokens=o, thinking_tokens=0, web_search=0,
                        web_fetch=0)


@pytest.fixture
def db():
    path = conn.init_db()
    con = conn.connect(path)
    pricing = U.load_pricing()
    for key, kind, name in (("S:s1", "SESSION", "세션1"), ("A:a1", "SUBAGENT", "자식1")):
        M.upsert_agent(con, M.Agent(agent_key=key, kind=kind, project_key="-p-demo", session_id="s1",
                                    project_path="/tmp/demo", name=name, agent_type="general-purpose" if kind == "SUBAGENT" else None,
                                    state="DONE"))
    evs = [_ev("S:s1", "r1", "2026-10-16T01:00:00Z", "claude-opus-5-5"),
           _ev("S:s1", "r2", "2026-10-16T16:00:00Z", "claude-sonnet-5"),     # KST 10-17
           _ev("A:a1", "r3", "2026-10-16T02:00:00Z", "claude-opus-5-5", o=900),
           _ev("A:a1", "r4", "2026-10-16T03:00:00Z", "claude-mystery-9")]    # 단가표에 없음 → NULL
    for e in evs:
        e.cost_usd, e.pricing_ver = U.cost(e, pricing)
        M.add_usage(con, e)
    U.rebuild_daily(con)
    con.commit()
    yield con
    con.close()


def _client():
    from agentdash.app.main import app
    return TestClient(app)


def _page_total(html: str) -> float:
    return float(re.search(r'data-total-cost="([0-9.]+)"', html).group(1))


def test_estimate_label_and_unpriced(db):
    h = _client().get("/usage?from=2026-10-16&to=2026-10-17").text
    assert LABEL in h and h.count(LABEL) >= 3          # 카드 · 추이 · 표 머리
    assert 'data-unpriced="1"' in h and "단가 없음 1 건" in h and "claude-mystery-9 1" in h
    j = _client().get("/api/v1/usage?from=2026-10-16&to=2026-10-17&group=model").json()
    assert j["unpriced"] == 1 and j["estimate_label"] == LABEL
    by = {r["key"]: r for r in j["rows"]}
    assert by["claude-mystery-9"]["cost_usd"] is None and by["claude-mystery-9"]["unpriced"] == 1
    assert by["claude-opus-5-5"]["cost_usd"] > 0


def test_total_matches_events_and_reprice(db, monkeypatch):
    ev_sum = db.execute("SELECT SUM(cost_usd) FROM usage_event").fetchone()[0]
    h = _client().get("/usage?from=2026-10-01&to=2026-10-31").text
    assert _page_total(h) == pytest.approx(ev_sum, abs=1e-6)
    # 단가를 바꿔 reprice (make reprice 와 같은 함수) → 화면 합계 = 새 usage_event 합
    p = U.load_pricing()
    p.models = {**p.models, "claude-opus-5-5": {**p.models["claude-opus-5-5"], "out": 99.0}}
    r = U.reprice(db, p)
    db.commit()
    assert r["changed"] == 2 and r["null_cost"] == 1
    ev2 = db.execute("SELECT SUM(cost_usd) FROM usage_event").fetchone()[0]
    daily = db.execute("SELECT SUM(cost_usd) FROM usage_daily").fetchone()[0]
    assert ev2 > ev_sum and daily == pytest.approx(ev2, abs=1e-9)
    h2 = _client().get("/usage?from=2026-10-01&to=2026-10-31").text
    assert _page_total(h2) == pytest.approx(ev2, abs=1e-6)
    for g in ("agent", "project", "type", "model", "day"):
        j = _client().get(f"/api/v1/usage?from=2026-10-01&to=2026-10-31&group={g}").json()
        assert sum(r["cost_usd"] or 0 for r in j["rows"]) == pytest.approx(ev2, abs=1e-9), g
        assert sum(r["output_tokens"] for r in j["rows"]) == 300 + 300 + 900 + 300, g


def test_make_reprice_cli_keeps_totals(db):
    db_path = db.execute("PRAGMA database_list").fetchone()[2]
    out = subprocess.run([sys.executable, "-m", "agentdash.core.usage", "reprice", "--db", db_path], cwd=ROOT,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    m = re.search(r"합계 event \$([0-9.]+) = daily \$([0-9.]+)", out.stdout)
    assert m and m.group(1) == m.group(2)
    h = _client().get("/usage?from=2026-10-01&to=2026-10-31").text
    assert f"{_page_total(h):.4f}" == m.group(1)


def test_kst_day_boundary_and_groups(db):
    j = _client().get("/api/v1/usage?from=2026-10-17&to=2026-10-17&group=day").json()
    assert [r["key"] for r in j["rows"]] == ["2026-10-17"] and j["total"]["requests"] == 1
    j = _client().get("/api/v1/usage?from=2026-10-16&to=2026-10-17&group=type").json()
    assert {r["key"] for r in j["rows"]} == {"SESSION", "general-purpose"}
    t = j["total"]
    assert t["cache_hit"] == pytest.approx(t["cache_read"] / (t["input_tokens"] + t["cache_read"] + t["cache_write"]))


def test_csv_export(db):
    r = _client().get("/api/v1/usage?from=2026-10-16&to=2026-10-17&group=agent&format=csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert LABEL in rows[0][U.CSV_COLS.index("cost_usd")]
    assert rows[-1][0] == "합계" and "단가 없음 1 건" in rows[-1][1]
    assert {row[0] for row in rows[1:-1]} == {"S:s1", "A:a1"}


def test_empty_db_pages_200():
    conn.init_db()
    c = _client()
    for u in ("/usage", "/api/v1/usage", "/timeline", "/api/v1/timeline", "/usage?group=day&format=csv"):
        assert c.get(u).status_code == 200, u
    h = c.get("/usage").text
    assert LABEL in h and "단가 없음 0 건" in h


def test_timeline_segments(db):
    db.execute("UPDATE agent SET started_at='2026-10-16T01:00:00Z', last_event_at='2026-10-16T03:00:00Z', "
               "ended_at='2026-10-16T03:00:00Z'")
    db.execute("UPDATE agent SET parent_key='S:s1' WHERE agent_key='A:a1'")
    db.execute("INSERT INTO state_log VALUES ('A:a1', '2026-10-16T02:00:00Z', 'RUNNING', 'R-07')")
    db.execute("INSERT INTO state_log VALUES ('A:a1', '2026-10-16T02:30:00Z', 'DONE', 'R-08')")
    db.commit()
    j = _client().get("/api/v1/timeline?from=2026-10-16T00:00:00Z&to=2026-10-16T04:00:00Z").json()
    lanes = {ln["agent_key"]: ln for ln in j["lanes"]}
    assert [ln["agent_key"] for ln in j["lanes"]] == ["S:s1", "A:a1"] and lanes["A:a1"]["depth"] == 1
    assert [s["state"] for s in lanes["A:a1"]["segments"]] == ["NONE", "RUNNING", "DONE"]
    assert max(c["n"] for c in j["concurrency"]) == 2
    h = _client().get("/timeline?from=2026-10-16T00:00:00Z&to=2026-10-16T04:00:00Z").text
    assert "seg st-RUNNING" in h and "판정 기록 없음" in h


# ── 2차-A Task 6 — 「추정 보정 (D-17)」 표기 · CSV 두 열 (spec v0.3 §6.2) ──────────────────────────────
EST = "추정 보정 (D-17)"


def test_est_label_and_csv(db):
    db.execute("UPDATE usage_event SET cost_est_usd = cost_usd")          # 수집기가 채우는 값 (의심 아님 = 기록 비용)
    db.execute("UPDATE usage_event SET output_est = 5000, cost_est_usd = cost_usd + 0.1 WHERE request_id='r3'")
    U.rebuild_daily(db)
    db.commit()
    h = _client().get("/usage?from=2026-10-16&to=2026-10-17").text
    assert EST in h and "기록상 과소" not in h
    assert 'data-total-cost-est="' in h
    j = _client().get("/api/v1/usage?from=2026-10-16&to=2026-10-17&group=agent").json()
    assert j["est_note"] == EST
    by = {r["key"]: r for r in j["rows"]}
    assert by["A:a1"]["output_est_total"] == 5000 + 300 and by["S:s1"]["output_est_total"] == 600
    assert j["total"]["cost_est_usd"] == pytest.approx(j["total"]["cost_usd"] + 0.1, abs=1e-9)
    r = _client().get("/api/v1/usage?from=2026-10-16&to=2026-10-17&group=agent&format=csv")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    head = rows[0]
    i_o, i_c = U.CSV_COLS.index("output_est_total"), U.CSV_COLS.index("cost_est_usd")
    assert EST in head[i_o] and EST in head[i_c] and LABEL in head[i_c]
    assert not any("기록상 과소" in c for c in head)
    body = {row[0]: row for row in rows[1:-1]}
    assert body["A:a1"][i_o] == "5300"

