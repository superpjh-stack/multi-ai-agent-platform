"""백필 · 재실행 멱등 · reprice · pricing-check (spec.md §1.3 · §6.1). 가짜 루트(읽기 전용)만."""

import pytest

from agentdash.collect import backfill, ingest
from agentdash.core import usage as U
from agentdash.db import conn


def _counts(con):
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("agent", "usage_event", "tool_call", "file_touch", "parse_error", "usage_daily")}


@pytest.mark.readonly_source
def test_backfill_fixture_and_idempotent(fake_claude_home, tmp_path):
    db = tmp_path / "b.db"
    out = backfill.run(db, since=None)
    assert out["agents"] == {"SESSION": 2, "SUBAGENT": 3, "WORKFLOW_AGENT": 6, "WORKFLOW": 1}
    assert out["parse_error"] == 0 and out["usage_event"] > 0 and out["usage_daily"] > 0
    con = conn.connect(db)
    first = _counts(con)
    con.close()
    out2 = backfill.run(db, since=None)              # 두 번째: 바뀐 것 없음 → 같은 숫자
    con = conn.connect(db)
    assert _counts(con) == first
    assert out2["usage_event"] == out["usage_event"]
    con.close()


@pytest.mark.readonly_source
def test_reprice_keeps_totals(fake_claude_home, tmp_path):
    db = tmp_path / "r.db"
    backfill.run(db)
    con = conn.connect(db)
    before = con.execute("SELECT ROUND(SUM(cost_usd), 9), COUNT(*) FROM usage_event").fetchone()
    con.execute("UPDATE usage_event SET cost_usd = NULL, pricing_ver = 'old'")
    r = U.reprice(con)
    con.commit()
    after = con.execute("SELECT ROUND(SUM(cost_usd), 9), COUNT(*) FROM usage_event").fetchone()
    assert after == before and r["rows"] == before[1]
    assert con.execute("SELECT COUNT(DISTINCT pricing_ver) FROM usage_event").fetchone()[0] == 1
    daily = con.execute("SELECT ROUND(SUM(cost_usd), 9) FROM usage_daily").fetchone()[0]
    assert daily == before[0]
    con.close()


def test_pricing_check_lists_unknown(tmp_path):
    con = conn.connect(conn.init_db(tmp_path / "p.db"))
    con.execute("INSERT INTO usage_event (agent_key, request_id, model, output_tokens) VALUES ('A:x','r1','claude-new-7',1)")
    con.execute("INSERT INTO usage_event (agent_key, request_id, model, output_tokens) VALUES ('A:x','r2','claude-opus-5-5',1)")
    assert U.unpriced_models(con) == [("claude-new-7", 1)]
    con.close()


@pytest.mark.readonly_source
def test_post_hook_called(fake_claude_home, tmp_path):
    con = conn.connect(conn.init_db(tmp_path / "h.db"))
    seen = []

    def hook(c, keys):
        seen.append(len(keys))

    ingest.add_post_hook(hook)
    try:
        ingest.ingest_all(con)
    finally:
        ingest.remove_post_hook(hook)
    assert seen and seen[0] == 12
    con.close()


def test_watcher_picks_up_new_session(fake_claude_home_rw, tmp_path):
    """감시기: 가짜 루트에 새 세션 파일(Claude Code 역할)을 쓰면 5 초 안에 agent 행이 생긴다."""
    import json
    import time

    from agentdash.collect import watcher

    db = tmp_path / "w.db"
    seen: list[set] = []
    t, stop = watcher.start(db, on_batch=seen.append)
    try:
        deadline = time.time() + 5
        while not seen and time.time() < deadline:      # 첫 전체 스캔
            time.sleep(0.05)
        proj = fake_claude_home_rw / "projects" / "-tmp-new"
        proj.mkdir()
        line = {"type": "assistant", "uuid": "n1", "timestamp": "2026-10-17T00:00:00Z", "sessionId": "newsess",
                "requestId": "rq", "message": {"model": "claude-opus-5-5", "content": [], "usage": {"output_tokens": 3}}}
        (proj / "newsess.jsonl").write_text(json.dumps(line) + "\n")
        t0 = time.time()
        found = False
        while time.time() - t0 < 5:
            if any("S:newsess" in s for s in seen):
                found = True
                break
            time.sleep(0.05)
        assert found, "5 초 안에 반영 안 됨"
    finally:
        stop.set()
        t.join(timeout=5)
    con = conn.connect(db)
    assert con.execute("SELECT kind FROM agent WHERE agent_key='S:newsess'").fetchone()[0] == "SESSION"
    con.close()
