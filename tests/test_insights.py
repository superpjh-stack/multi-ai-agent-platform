"""D-07 비용 · 효율 화면 + API 3 (spec.md v0.3 §7 D-07 · §8) — G-17 · G-26~G-28 화면 쪽. 가짜 DB 만, 금액은 가짜 한도."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agentdash.core import budget as B
from agentdash.core import model as M
from agentdash.core import usage as U
from agentdash.db import conn

LABEL = "[추정] API 정가 환산"
PATHS = ("/insights", "/api/v1/budget", "/api/v1/trend", "/api/v1/efficiency")


def _client():
    from agentdash.app.main import app
    return TestClient(app)


@pytest.fixture
def db():
    con = conn.connect(conn.init_db())
    now = datetime.now(timezone.utc)
    for key, kind, path, parent in (("S:s1", "SESSION", "/x/Alpha", None), ("A:a1", "SUBAGENT", "/x/Beta", "S:s1")):
        M.upsert_agent(con, M.Agent(agent_key=key, kind=kind, project_key="-x", session_id="s1", project_path=path,
                                    depth=0 if parent is None else 1, parent_key=parent, name=key + " 이름"))
    for n, (key, c, ce, i, cr) in enumerate((("S:s1", 1.0, 1.0, 100, 900), ("A:a1", 2.0, 3.5, 500, 500),
                                             ("A:a1", None, None, 10, 0))):
        at = (now - timedelta(seconds=1 + n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        M.add_usage(con, M.UsageEvent(agent_key=key, request_id=f"r{n}", at=at, model="claude-opus-5-5" if c else "x-9",
                                      input_tokens=i, cache_read=cr, output_tokens=10, cost_usd=c, cost_est_usd=ce,
                                      output_est=40 if ce and ce != c else None))
    U.rebuild_daily(con)
    con.commit()
    yield con
    con.close()


def _fake_cfg(monkeypatch, daily=None, monthly=None, projects=None):
    cfg = {"warn_ratio": 0.8, "total": {"daily_usd": daily, "monthly_usd": monthly}, "projects": projects or {}}
    monkeypatch.setattr(B, "load", lambda: cfg)
    return cfg


def test_empty_db_routes_200_no_placeholder():
    conn.init_db()
    c = _client()
    for p in PATHS:
        r = c.get(p)
        assert r.status_code == 200, p
        assert "_placeholder" not in r.text and "data-placeholder" not in r.text, p
    h = c.get("/insights").text
    assert "한도 미설정" in h and "config/budget.yaml" in h and LABEL in h
    assert c.get("/api/v1/budget").json()["label"] == LABEL


def test_bad_params_422():
    conn.init_db()
    c = _client()
    assert c.get("/api/v1/trend?grain=year").status_code == 422
    assert c.get("/api/v1/trend?group=team").status_code == 422
    assert c.get("/api/v1/efficiency?group=team").status_code == 422
    assert c.get("/api/v1/trend?from=2026-13-01").status_code == 422
    assert c.get("/insights?grain=year").status_code == 422


def test_budget_api_equals_status(db, monkeypatch):
    _fake_cfg(monkeypatch, daily=4.0, projects={"Beta": {"daily_usd": 10.0, "monthly_usd": None},
                                                "오타": {"daily_usd": 5.0, "monthly_usd": None}})
    j = _client().get("/api/v1/budget").json()
    want = B.status(db)
    assert j["rows"] == want and j["label"] == LABEL
    day = next(r for r in j["rows"] if r["scope"] == "total" and r["period"] == "day")
    assert day["est_usd"] == pytest.approx(4.5) and day["level"] == "over" and day["unpriced"] == 1
    assert j["worst"]["ratio"] == pytest.approx(4.5 / 4.0)
    h = _client().get("/insights").text
    assert "113 %" in h or "112 %" in h                  # 4.5 / 4.0 = 112.5 % (반올림 표시)
    assert "st-FAILED" in h and "기록 없음" in h and "단가 없음 1 건" in h


def test_trend_and_efficiency_api(db):
    c = _client()
    j = c.get("/api/v1/trend?grain=month&group=project").json()
    assert j["grain"] == "month" and j["group"] == "project"
    assert sum(r["cost_est_usd"] or 0 for r in j["rows"]) == pytest.approx(4.5)
    assert {r["project"] for r in j["rows"]} == {"Alpha", "Beta"}
    e = c.get("/api/v1/efficiency?group=agent").json()
    assert [r["key"] for r in e["rows"]] == ["A:a1", "S:s1"]          # waste 내림차순
    assert e["rows"][0]["hit"] == pytest.approx(500 / 1010)
    h = c.get("/insights?eff=session").text
    assert 'href="/agents/S:s1"' in h and "chart.js@4.4.1" in h
    assert "Chart.js 4.4.1 를 불러오지 못했다" in h                     # 못 불러오면 표만 (문구는 스크립트 안)
