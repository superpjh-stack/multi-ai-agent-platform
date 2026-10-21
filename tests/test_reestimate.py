"""D-24: 가짜 원천 재계산 · 보관 보존 · 원자적 갱신."""

import json
import sqlite3
from pathlib import Path

import pytest

from agentdash.collect import ingest, reestimate
from agentdash.core import model as M
from agentdash.db import conn


def _write_request(home, *, rid="r1", output=1, model="claude-opus-5-5"):
    path = home / "projects" / "-tmp-reestimate" / "session.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"type": "assistant", "uuid": rid, "requestId": rid,
            "timestamp": "2026-10-20T00:00:00Z", "sessionId": "session",
            "message": {"model": model, "content": [{"type": "text", "text": "x" * 2000}],
                        "usage": {"input_tokens": 10, "output_tokens": output}}}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    return path


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    _write_request(home)
    db = conn.init_db(tmp_path / "legacy.db")
    with conn.connect(db) as con:
        ingest.ingest_all(con, run_hooks=False, link=False)
        con.execute("UPDATE usage_event SET output_est=NULL, cost_est_usd=NULL")
        M.upsert_agent(con, M.Agent(agent_key="S:archived", kind="SESSION",
                                   session_id="archived", project_key="-tmp-archive"))
        M.add_usage(con, M.UsageEvent(agent_key="S:archived", request_id="gone", at="2026-09-01T00:00:00Z",
                                     model="claude-opus-5-5", output_tokens=100, cost_usd=0.002))
        con.commit()
    return db, home


def _snapshot(db):
    with sqlite3.connect(f"{Path(db).as_uri()}?mode=ro", uri=True) as con:
        return {table: sorted(con.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr)
                for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def test_reestimate_preserves_records_and_archive_and_is_idempotent(legacy):
    db, _ = legacy
    before = _snapshot(db)
    report = reestimate.run(db)
    after = _snapshot(db)
    assert report["updated"] == 1 and report["unavailable"] == 1
    assert report["missing_est_cost"] == 1
    assert report["mismatched"] == 0
    assert _snapshot(report["backup"]) == before
    for table in before.keys() - {"usage_event", "usage_daily"}:
        assert before[table] == after[table], table
    assert len(after["usage_event"]) == len(before["usage_event"]) == 2
    for old, new in zip(before["usage_event"], after["usage_event"]):
        assert old[:-2] == new[:-2]  # 기록값 전부 그대로
    assert next(r for r in after["usage_event"] if r[0] == "S:archived") == next(
        r for r in before["usage_event"] if r[0] == "S:archived")
    repaired = next(r for r in after["usage_event"] if r[0] == "S:session")
    assert repaired[-2] == 500 and repaired[-1] > repaired[-4]
    second = reestimate.run(db)
    assert second["updated"] == 0 and second["backup"] is None
    assert _snapshot(db) == after
    with conn.connect(db) as con:
        assert con.execute("SELECT SUM(cost_est_usd) FROM usage_event").fetchone()[0] == pytest.approx(
            con.execute("SELECT SUM(cost_est_usd) FROM usage_daily").fetchone()[0])


def test_new_or_changed_requests_are_reported_without_overwriting_recorded_values(legacy):
    db, home = legacy
    _write_request(home, rid="new")
    _write_request(home, output=40)  # 원천 최종본이 DB 보다 앞섬
    before = _snapshot(db)
    report = reestimate.run(db)
    assert report["mismatched"] == 1 and report["source_only"] == 1
    assert report["updated"] == 0 and report["backup"] is None
    assert _snapshot(db) == before


def test_unknown_model_remains_unpriced(legacy):
    db, home = legacy
    _write_request(home, rid="unknown", model="unknown-model")
    with conn.connect(db) as con:
        ingest.ingest_all(con, run_hooks=False, link=False)
        con.execute("UPDATE usage_event SET output_est=NULL, cost_est_usd=NULL WHERE request_id='unknown'")
        con.commit()
    report = reestimate.run(db)
    assert report["unpriced"] == 1
    row = next(r for r in _snapshot(db)["usage_event"] if r[1] == "unknown")
    assert row[-2] == 500 and row[-1] is None


def test_parse_error_aborts_before_writing(legacy):
    db, home = legacy
    path = home / "projects" / "-tmp-reestimate" / "broken.jsonl"
    path.write_text("{broken}\n", encoding="utf-8")
    before = _snapshot(db)
    with pytest.raises(RuntimeError, match="파싱 오류"):
        reestimate.run(db)
    assert _snapshot(db) == before


def test_rebuild_failure_rolls_back(legacy, monkeypatch):
    db, _ = legacy
    before = _snapshot(db)

    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(reestimate.U, "rebuild_daily", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        reestimate.run(db)
    assert _snapshot(db) == before


def test_source_database_path_rejected_before_creation(legacy):
    _, home = legacy
    path = home / "forbidden.db"
    with pytest.raises(RuntimeError, match="원천 루트 아래"):
        reestimate.run(path)
    assert not path.exists()


def test_cli_reports_backup_and_unavailable_records(legacy, capsys):
    db, _ = legacy
    assert reestimate.main(["--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "갱신 1" in out and "원천 미확인 1" in out and "백업" in out


def test_readonly_fixtures_restore_same_estimates_including_fork_ownership(fake_claude_home_ro, tmp_path):
    db = conn.init_db(tmp_path / "fixtures.db")
    with conn.connect(db) as con:
        ingest.ingest_all(con, run_hooks=False, link=False)
        con.commit()
    expected = _snapshot(db)
    with conn.connect(db) as con:
        con.execute("UPDATE usage_event SET output_est=NULL, cost_est_usd=NULL")
        con.commit()
    report = reestimate.run(db)
    assert report["mismatched"] == report["unavailable"] == 0
    assert _snapshot(db) == expected


def test_backup_failure_prevents_updates(legacy, monkeypatch):
    db, _ = legacy
    before = _snapshot(db)

    def fail(*args):
        raise OSError("backup failed")

    monkeypatch.setattr(reestimate, "_backup", fail)
    with pytest.raises(OSError, match="backup failed"):
        reestimate.run(db)
    assert _snapshot(db) == before


def test_missing_database_not_created(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError, match="기존 DB 없음"):
        reestimate.run(path)
    assert not path.exists()


def test_hardlinked_database_rejected(legacy, tmp_path):
    db, _ = legacy
    link = tmp_path / "linked.db"
    link.hardlink_to(db)
    before = _snapshot(db)
    with pytest.raises(RuntimeError, match="하드 링크"):
        reestimate.run(link)
    assert _snapshot(db) == before
