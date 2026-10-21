"""G-26 예산 · G-27 추세 · G-28 캐시 적중률 (spec.md v0.3 §6.3) — core/budget.py.

금액은 테스트 안의 가짜 한도만 쓴다 (실제 config/budget.yaml 은 null 그대로 — goal.md §0.2).
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from agentdash import settings
from agentdash.core import budget as B
from agentdash.core import model as M
from agentdash.core import usage as U
from agentdash.db import conn

NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)      # KST 2026-10-20 21:00


def _cfg(daily=None, monthly=None, projects=None, warn=0.8):
    return {"warn_ratio": warn, "total": {"daily_usd": daily, "monthly_usd": monthly}, "projects": projects or {}}


@pytest.fixture
def con(tmp_path):
    c = conn.connect(conn.init_db(tmp_path / "b.db"))
    yield c
    c.close()


def _agent(con, key, kind="SESSION", path="/x/Alpha", sid="s1", parent=None):
    M.upsert_agent(con, M.Agent(agent_key=key, kind=kind, project_key="-x-" + (path or "none").rsplit("/", 1)[-1],
                                session_id=sid, project_path=path, depth=0 if kind == "SESSION" else 1,
                                parent_key=parent, name=key))


def _ev(con, key, rid, at, cost, est=None, *, i=0, cr=0, w5=0, o=0, oe=None):
    M.add_usage(con, M.UsageEvent(agent_key=key, request_id=rid, at=at, model="claude-opus-5-5", input_tokens=i,
                                  cache_read=cr, cache_write_5m=w5, output_tokens=o, cost_usd=cost,
                                  cost_est_usd=cost if est is None else est, output_est=oe))


def _cell(rows, scope="total", period="day", project=None):
    return next(r for r in rows if r["scope"] == scope and r["period"] == period and r["project"] == project)


# ── 설정 ─────────────────────────────────────────────────────────────
def test_load_real_yaml_is_unset():
    cfg = B.load()
    assert cfg["warn_ratio"] == 0.8 and cfg["total"] == {"daily_usd": None, "monthly_usd": None}
    assert cfg["projects"] == {}


def test_load_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "load_yaml", lambda name: {"warn_ratio": 0.8, "projects": {}})
    with pytest.raises(settings.SettingsError):
        B.load()


# ── 단계 · 기간 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("est,limit,want", [(79.99, 100, "ok"), (80, 100, "warn"), (99.99, 100, "warn"),
                                            (100, 100, "over"), (150, 100, "over"), (5, None, "unset")])
def test_level_boundaries(con, est, limit, want):
    assert B.level(est, limit, 0.8) == want
    _agent(con, "S:a")
    _ev(con, "S:a", "r1", "2026-10-20T01:00:00Z", 1.0, est)
    rows = B.status(con, NOW, cfg=_cfg(daily=limit))
    c = _cell(rows)
    assert c["level"] == want and c["limit"] == limit and c["est_usd"] == pytest.approx(est)
    assert c["ratio"] == (None if limit is None else pytest.approx(est / limit))


def test_kst_day_month_boundary(con):
    _agent(con, "S:a")
    _ev(con, "S:a", "d0", "2026-10-20T14:59:59Z", 1.0)         # KST 10-20 23:59:59
    _ev(con, "S:a", "d1", "2026-10-20T15:00:00Z", 2.0)         # KST 10-21 00:00
    _ev(con, "S:a", "m0", "2026-10-31T14:59:59Z", 4.0)         # KST 10-31
    _ev(con, "S:a", "m1", "2026-10-31T15:00:00Z", 8.0)         # KST 11-01
    _ev(con, "S:a", "old", "2026-09-30T15:00:00Z", 16.0)       # KST 10-01 00:00 — 10 월
    at = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    assert _cell(B.status(con, at("2026-10-20T14:59:59Z"), cfg=_cfg()))["est_usd"] == pytest.approx(1.0)
    assert _cell(B.status(con, at("2026-10-21T00:00:00Z"), cfg=_cfg()))["est_usd"] == pytest.approx(2.0)
    m = _cell(B.status(con, at("2026-10-31T14:59:59Z"), cfg=_cfg()), period="month")
    assert m["est_usd"] == pytest.approx(16 + 1 + 2 + 4)
    nov = _cell(B.status(con, at("2026-10-31T15:00:00Z"), cfg=_cfg()), period="month")
    assert nov["est_usd"] == pytest.approx(8.0)
    assert B.kst_bucket("2026-10-20T14:59:59Z", "day") == "2026-10-20"
    assert B.kst_bucket("2026-10-20T15:00:00Z", "day") == "2026-10-21"
    assert B.kst_bucket("2026-10-31T15:00:00Z", "month") == "2026-11-01"


def test_project_mapping(con):
    _agent(con, "S:m", path="/x/Standard MES Platform", sid="m")
    _agent(con, "A:k", kind="SUBAGENT", path="/x/Standard MES Platform", sid="m", parent="S:m")
    _agent(con, "A:other", kind="SUBAGENT", path="/y/Other", sid="m", parent="S:m")   # 자손은 자기 project_path 로
    _agent(con, "S:np", path=None, sid="np")                                         # project_path 없음 → project_key
    _ev(con, "S:m", "r1", "2026-10-20T01:00:00Z", 1.0)
    _ev(con, "A:k", "r2", "2026-10-20T02:00:00Z", 3.0, 5.0)
    _ev(con, "A:other", "r3", "2026-10-20T02:00:00Z", 7.0)
    _ev(con, "S:np", "r4", "2026-10-20T02:00:00Z", 11.0)
    rows = B.status(con, NOW, cfg=_cfg(projects={"Standard MES Platform": {"daily_usd": 10, "monthly_usd": None},
                                                 "-x-none": {"daily_usd": 100, "monthly_usd": None}}))
    c = _cell(rows, "project", "day", "Standard MES Platform")
    assert c["est_usd"] == pytest.approx(1 + 5) and c["rec_usd"] == pytest.approx(1 + 3)
    assert c["level"] == "ok" and c["ratio"] == pytest.approx(0.6)
    assert _cell(rows, "project", "month", "Standard MES Platform")["level"] == "unset"
    assert _cell(rows, "project", "day", "-x-none")["est_usd"] == pytest.approx(11.0)
    assert _cell(rows)["est_usd"] == pytest.approx(1 + 5 + 7 + 11)


def test_project_not_in_records(con):
    _agent(con, "S:a")
    _ev(con, "S:a", "r1", "2026-10-20T01:00:00Z", 1.0)
    rows = B.status(con, NOW, cfg=_cfg(projects={"오타": {"daily_usd": 10, "monthly_usd": 100}}))
    c = _cell(rows, "project", "day", "오타")
    assert c["level"] == "no_records" and c["ratio"] is None and c["est_usd"] == 0


def test_unpriced_not_summed(con):
    _agent(con, "S:a")
    _ev(con, "S:a", "r1", "2026-10-20T01:00:00Z", 2.5)
    _ev(con, "S:a", "r2", "2026-10-20T02:00:00Z", None)
    _ev(con, "S:a", "r3", "2026-10-20T03:00:00Z", None)
    c = _cell(B.status(con, NOW, cfg=_cfg(daily=10)))
    assert c["unpriced"] == 2 and c["est_usd"] == pytest.approx(2.5) and c["rec_usd"] == pytest.approx(2.5)


def test_worst(con):
    assert B.worst([]) is None
    rows = [dict(level="ok", ratio=0.5), dict(level="warn", ratio=0.9), dict(level="over", ratio=1.02),
            dict(level="over", ratio=1.5), dict(level="unset", ratio=None), dict(level="no_records", ratio=None)]
    assert B.worst(rows)["ratio"] == 1.5
    assert B.worst([dict(level="ok", ratio=0.7), dict(level="unset", ratio=None)]) is None
    assert B.worst([dict(level="warn", ratio=0.85), dict(level="warn", ratio=0.95)])["ratio"] == 0.95


# ── 추세 ─────────────────────────────────────────────────────────────
def test_trend_week_starts_monday_kst(con):
    _agent(con, "S:a")
    _ev(con, "S:a", "w1", "2026-10-25T14:00:00Z", 1.0)          # KST 10-25(일) 23:00
    _ev(con, "S:a", "w2", "2026-10-25T15:30:00Z", 2.0)          # KST 10-26(월) 00:30
    U.rebuild_daily(con)
    rows = B.trend(con, "week", "2026-10-19", "2026-11-01", "total")
    assert [(r["bucket"], r["cost_usd"]) for r in rows] == [("2026-10-19", 1.0), ("2026-10-26", 2.0)]
    assert B.kst_bucket("2026-10-25T15:30:00Z", "week") == "2026-10-26"


def test_trend_sums_equal_events(con):
    rnd = random.Random(7)
    _agent(con, "S:a", path="/x/Alpha", sid="a")
    _agent(con, "A:b", kind="SUBAGENT", path="/x/Beta", sid="a", parent="S:a")
    for n in range(20):
        key = "S:a" if n % 2 else "A:b"
        day = rnd.randint(1, 60)
        at = datetime.fromtimestamp(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() + day * 86400
                                    + rnd.randint(0, 86399), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        o = rnd.randint(1, 500)
        oe = rnd.choice([None, o + rnd.randint(0, 900)])
        c = rnd.random()
        _ev(con, key, f"r{n}", at, c, c + (0.5 if oe else 0), o=o, oe=oe)
    U.rebuild_daily(con)
    ev = con.execute("SELECT SUM(cost_usd), SUM(cost_est_usd), SUM(output_tokens), "
                     "SUM(COALESCE(output_est, output_tokens)) FROM usage_event").fetchone()
    for grain in ("day", "week", "month"):
        for group in ("total", "project"):
            rows = B.trend(con, grain, "2026-08-01", "2026-12-31", group)
            got = [sum(r[k] or 0 for r in rows) for k in ("cost_usd", "cost_est_usd", "output_tokens", "output_est_total")]
            assert got[0] == pytest.approx(ev[0]) and got[1] == pytest.approx(ev[1]), (grain, group)
            assert got[2] == ev[2] and got[3] == ev[3], (grain, group)
            if group == "project":
                assert {r["project"] for r in rows} <= {"Alpha", "Beta"}
    with pytest.raises(ValueError):
        B.trend(con, "year", "2026-08-01", "2026-12-31", "total")


# ── 캐시 적중률 ──────────────────────────────────────────────────────
def test_efficiency_formula_and_zero(con):
    _agent(con, "S:a", path="/x/Alpha", sid="a")
    _agent(con, "A:b", kind="SUBAGENT", path="/x/Alpha", sid="a", parent="S:a")
    _agent(con, "S:z", path="/x/Zero", sid="z")
    _ev(con, "S:a", "r1", "2026-10-20T01:00:00Z", 1.0, i=100, cr=800, w5=100)       # hit 0.8
    _ev(con, "A:b", "r2", "2026-10-20T01:00:00Z", 4.0, 6.0, i=500, cr=500, w5=0)   # hit 0.5
    _ev(con, "S:z", "r3", "2026-10-20T01:00:00Z", 0.5, i=0, cr=0, w5=0, o=10)      # 분모 0
    ag = {r["key"]: r for r in B.efficiency(con, "agent", "2026-10-01", "2026-10-31")}
    assert ag["S:a"]["hit"] == pytest.approx(0.8) and ag["A:b"]["hit"] == pytest.approx(0.5)
    assert ag["S:z"]["hit"] is None and ag["S:z"]["waste"] == 0
    assert ag["A:b"]["waste"] == pytest.approx(0.5 * 6.0) and ag["S:a"]["waste"] == pytest.approx(0.2 * 1.0)
    assert [r["key"] for r in B.efficiency(con, "agent", "2026-10-01", "2026-10-31")] == ["A:b", "S:a", "S:z"]
    se = {r["key"]: r for r in B.efficiency(con, "session", "2026-10-01", "2026-10-31")}
    assert se["S:a"]["hit"] == pytest.approx(1300 / 2000)                           # 자기 + 자손
    assert se["S:a"]["cost_est_usd"] == pytest.approx(7.0)
    pr = {r["key"]: r for r in B.efficiency(con, "project", "2026-10-01", "2026-10-31")}
    assert pr["Alpha"]["input_tokens"] == 600 and pr["Alpha"]["cache_write"] == 100 and pr["Zero"]["hit"] is None
    assert B.efficiency(con, "agent", "2026-11-01", "2026-11-30") == []
    with pytest.raises(ValueError):
        B.efficiency(con, "team", "2026-10-01", "2026-10-31")
