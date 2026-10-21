"""G-32 (V-17) check_twin — 가짜 DB 로 PASS 한 번 · 스파크 값 하나를 틀리게 만든 몽키패치로 FAIL 한 번. 담당 개발1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentdash.core import usage
from agentdash.db import conn
from agentdash.tools import check_twin as CT

NOW = datetime(2026, 10, 21, 10, 30, 20, tzinfo=timezone.utc)
COLS = ("agent_key", "kind", "project_key", "project_path", "session_id", "parent_key", "depth", "name",
        "started_at", "last_event_at", "ended_at", "state", "state_reason", "state_since")


def iso(m: float) -> str:
    return (NOW - timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


@pytest.fixture
def db(tmp_path):
    p = conn.init_db(tmp_path / "t.db")
    c = conn.connect(p)
    rows = [
        ("S:s1", "SESSION", "-p-a", "/x/a", "s1", None, 0, "세션1", iso(60), iso(1), None, "RUNNING", "R-02a", iso(1)),
        ("A:a1", "SUBAGENT", "-p-a", "/x/a", "s1", "S:s1", 1, "자식1", iso(40), iso(2), None, "RUNNING", "R-09", iso(2)),
        ("A:a2", "SUBAGENT", "-p-a", "/x/a", "s1", "S:s1", 1, "끝난 자식", iso(90), iso(80), iso(80), "DONE", "R-08", iso(80)),
        ("A:a3", "SUBAGENT", "-p-a", "/x/a", "s1", "S:gone", 1, "부모 없음", iso(20), iso(5), None, "RUNNING", "R-09", iso(5)),
        ("S:s2", "SESSION", "-p-b", "/x/b", "s2", None, 0, "세션2", iso(300), iso(200), iso(200), "DONE", "R-07", iso(200)),
        ("S:old", "SESSION", "-p-c", "/x/c", "old", None, 0, "옛", iso(5000), iso(4000), iso(4000), "DONE", "R-07", iso(4000)),
    ]
    c.executemany(f"INSERT INTO agent ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})", rows)
    c.executemany("INSERT INTO edge (src_key, dst_key, kind, at) VALUES (?,?,?,?)",
                  [("S:s1", "A:a1", "spawn", iso(40)), ("S:s1", "A:a2", "spawn", iso(90))])
    ev = [("S:s1", "r1", iso(0.2), "claude-opus-5-5", 10, None, 0.01), ("S:s1", "r2", iso(10), "claude-opus-5-5", 5, 70, 0.02),
          ("A:a1", "r3", iso(29), "claude-opus-5-5", 8, None, None), ("A:a1", "r4", iso(31), "claude-opus-5-5", 100, None, 0.5),
          ("A:a1", "r5", iso(3), "<synthetic>", 999, None, None), ("A:a3", "r6", iso(4), "claude-opus-5-5", 3, None, 0.001)]
    c.executemany("INSERT INTO usage_event (agent_key, request_id, at, model, output_tokens, output_est, cost_est_usd) "
                  "VALUES (?,?,?,?,?,?,?)", ev)
    c.commit()
    c.close()
    return p


def test_check_twin_pass(db, capsys):
    assert CT.main(["--db", str(db), "--now", NOW.isoformat()]) == 0
    out = capsys.readouterr().out
    assert out.startswith("G-32  트윈 API  PASS  ")
    assert "누적 불일치 0 · 스파크 불일치 0 · 겹침 0" in out
    assert "DB 직접 5" in out                     # S:old 만 범위 밖


def test_check_twin_spark_mismatch_fails(db, capsys, monkeypatch):
    real = usage.spark

    def wrong(con, keys, now, minutes=usage.SPARK_MINUTES):
        out = real(con, keys, now, minutes)
        if "S:s1" in out:
            out["S:s1"][-1] += 1
        return out

    monkeypatch.setattr(usage, "spark", wrong)
    assert CT.main(["--db", str(db), "--now", NOW.isoformat()]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "스파크 불일치 1" in out


def test_direct_spark_independent(db):
    c = conn.connect(db)
    try:
        assert CT.direct_spark(c, {"S:s1", "A:a1"}, NOW, 30) == usage.spark(c, ["S:s1", "A:a1"], NOW)
    finally:
        c.close()
