"""G-04 · G-07 회귀 — 원천에서 지워진 기록 (decisions.md D-22 · problem.md Q10).

Claude Code 가 오래된 기록을 지우면 DB 는 집계 숫자를 남긴다(Q10). 검사기는 느슨해지지 않고 더 엄밀하게 나눈다:
  · check_counts (V-01): 원천에 있는 파일은 전부 DB 에 (빠짐 0), DB 전용 키는 전부 「원천 삭제 보관」 = 그 키의 기록 경로가
    src_file 에 있고 **지금 디스크에 없음**을 확인한 것. 그렇게 확인 못 한 DB 전용 키는 FAIL.
  · check_usage_sum (V-03): 표본은 원천 파일이 지금 다 있는 세션에서만 뽑고, 선정 규칙을 출력에 적는다.
원천 흉내(파일 쓰기 · 지우기)는 tmp 의 가짜 루트에서만 — Claude Code 역할.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentdash.collect import ingest
from agentdash.core import model as M
from agentdash.db import conn
from agentdash.tools import check_counts, check_usage_sum

PK = "-tmp-arch"
SIDS = [f"{c * 8}-0000-0000-0000-000000000000" for c in "abcd"]


def _asst(sid, uuid, rid, ts, out, agent=None):
    d = {"type": "assistant", "uuid": uuid, "timestamp": ts, "sessionId": sid, "requestId": rid, "cwd": "/tmp/arch",
         "message": {"model": "claude-opus-5-5", "content": [],
                     "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "cache_creation_input_tokens": 0,
                               "output_tokens": out}}}
    if agent:
        d.update(agentId=agent, isSidechain=True)
    return json.dumps(d) + "\n"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    proj = h / "projects" / PK
    proj.mkdir(parents=True)
    for n, sid in enumerate(SIDS):
        (proj / f"{sid}.jsonl").write_text(_asst(sid, f"m{n}", f"R{n}", "2026-10-20T01:00:00Z", 100 + n))
        sub = proj / sid / "subagents"
        sub.mkdir(parents=True)
        aid = f"sub{n}"
        (sub / f"agent-{aid}.jsonl").write_text(_asst(sid, f"c{n}", f"RC{n}", "2026-10-20T01:05:00Z", 7 + n, agent=aid))
        (sub / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": "general-purpose", "toolUseId": f"t{n}",
                                                                "spawnDepth": 1, "description": f"child {n}"}))
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(h))
    return h


@pytest.fixture
def db(tmp_path, monkeypatch, home):
    path = tmp_path / "arch.db"
    monkeypatch.setenv("AGENTDASH_DB", str(path))
    con = conn.connect(conn.init_db(path))
    ingest.ingest_all(con, run_hooks=False)
    con.commit()
    con.close()
    return path


def _rows(out: str, gid: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith(gid)]


def _delete_session(home: Path, n: int) -> None:
    """Claude Code 가 오래된 기록을 지운 것처럼 (가짜 루트에서만)."""
    sid = SIDS[n]
    (home / "projects" / PK / f"{sid}.jsonl").unlink()
    for p in sorted((home / "projects" / PK / sid).rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    (home / "projects" / PK / sid).rmdir()


# ── check_counts (V-01) ──────────────────────────────────────────────
def test_counts_all_present_pass(db, capsys):
    assert check_counts.main(["--no-sync"]) == 0
    rows = _rows(capsys.readouterr().out, "G-04")
    assert len(rows) == 3 and all("  PASS  " in r and "원천 삭제 보관 0" in r for r in rows)


def test_counts_deleted_source_is_archived_pass(db, home, capsys):
    _delete_session(home, 0)
    assert check_counts.main(["--no-sync"]) == 0
    out = capsys.readouterr().out
    sess = next(r for r in _rows(out, "G-04") if "(세션)" in r)
    sub = next(r for r in _rows(out, "G-04") if "(서브에이전트)" in r)
    assert "  PASS  " in sess and "원천 3 · DB 4" in sess and "원천 삭제 보관 1" in sess and "남음 0" in sess
    assert "  PASS  " in sub and "원천 삭제 보관 1" in sub


def test_counts_db_only_without_recorded_path_fails(db, home, capsys):
    """src_file 에 경로가 없는 DB 전용 키는 「원천 삭제」 를 확인할 수 없다 → FAIL (느슨하게 넘기지 않는다)."""
    con = conn.connect(db)
    M.upsert_agent(con, M.Agent(agent_key="S:ghost", kind="SESSION", project_key=PK, session_id="ghost", depth=0))
    con.commit()
    con.close()
    assert check_counts.main(["--no-sync"]) == 1
    sess = next(r for r in _rows(capsys.readouterr().out, "G-04") if "(세션)" in r)
    assert "  FAIL  " in sess and "남음 1" in sess and "S:ghost" in sess


def test_counts_recorded_path_still_exists_fails(db, home, capsys):
    """기록 경로가 아직 디스크에 있는데 DB 키만 남은 경우(키 불일치)는 보관이 아니다 → FAIL."""
    con = conn.connect(db)
    path = str(home / "projects" / PK / f"{SIDS[1]}.jsonl")
    con.execute("UPDATE agent SET agent_key='S:renamed' WHERE agent_key=?", (f"S:{SIDS[1]}",))
    con.commit()
    con.close()
    assert Path(path).exists()
    assert check_counts.main(["--no-sync"]) == 1
    sess = next(r for r in _rows(capsys.readouterr().out, "G-04") if "(세션)" in r)
    assert "  FAIL  " in sess and "빠짐 1" in sess and "남음 1" in sess


def test_counts_missing_source_fails(db, home, capsys):
    sid = "22222222-0000-0000-0000-000000000000"
    (home / "projects" / PK / f"{sid}.jsonl").write_text(_asst(sid, "x", "RX", "2026-10-20T02:00:00Z", 1))
    assert check_counts.main(["--no-sync"]) == 1
    sess = next(r for r in _rows(capsys.readouterr().out, "G-04") if "(세션)" in r)
    assert "  FAIL  " in sess and "빠짐 1" in sess


# ── check_usage_sum (V-03) ───────────────────────────────────────────
def test_usage_sum_samples_only_present_sessions(db, home, capsys):
    _delete_session(home, 0)                                         # 전부 지움
    (home / "projects" / PK / SIDS[1] / "subagents" / "agent-sub1.jsonl").unlink()   # 일부만 지움
    assert check_usage_sum.main(["--no-sync", "--n", "2"]) == 0
    out = capsys.readouterr().out
    rows = _rows(out, "G-07")
    assert len(rows) == 2 and all("  PASS  " in r for r in rows)
    sampled = {r.split("(")[1][:8] for r in rows}
    assert sampled == {"cccccccc", "dddddddd"}                        # 전부 · 일부 지운 세션은 표본에서 빠진다
    rule = next(ln for ln in out.splitlines() if ln.startswith("# 표본 선정"))
    assert "원천 파일이 지금 다 있는 세션" in rule and "제외 2" in rule and "후보 2" in rule


def test_usage_sum_too_few_present_sessions_fails(db, home, capsys):
    for n in range(3):
        _delete_session(home, n)
    assert check_usage_sum.main(["--no-sync", "--n", "2"]) == 1
    row = _rows(capsys.readouterr().out, "G-07")[0]
    assert "  FAIL  " in row and "원천 파일이 지금 다 있는" in row
