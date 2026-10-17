"""G-09 — 판정 규칙 13 (R-01 · R-02a · R-02b · R-03~R-12) 표 기반 테스트 (spec.md §4.2).

경계: 89/91 초(SLOW 90) · 299/301 초(STALE 300) · 훅 도구 실행 중 · STALE → 새 기록 → RUNNING 회복.
기준 시간은 settings(config/settings.yaml) 에서 읽는다 — 테스트도 숫자를 박지 않고 settings 값 ± 1 로 경계를 만든다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentdash import settings
from agentdash.core import state as S
from agentdash.core.state import Ctx, HookInfo, S1Info

NOW = datetime(2026, 10, 17, 7, 0, 0, tzinfo=timezone.utc)
CFG = settings.get()
STALE, SLOW = CFG.stale_after_sec, CFG.slow_after_sec
SESSION = {"kind": "SESSION"}
SUB = {"kind": "SUBAGENT"}


def ago(sec: float) -> datetime:
    return NOW - timedelta(seconds=sec)


def busy(alive=True):
    return S1Info("busy", alive)


def idle(alive=True, status="idle"):
    return S1Info(status, alive)


def hook(event, sec_ago, **kw):
    return HookInfo(event=event, at=ago(sec_ago), **kw)


# (id, 규칙, agent, ctx, 기대 상태)
CASES = [
    # R-01 훅 — 기록보다 새 훅이 상태를 정한다
    ("R-01 권한 요청", "R-01", SESSION, Ctx(last_record_at=ago(30), s1=idle(), hook=hook("Notification", 10,
                                                                                    notification_type="permission_prompt")),
     S.WAITING_PERMISSION),
    ("R-01 입력 대기", "R-01", SESSION, Ctx(last_record_at=ago(30), s1=idle(), hook=hook("Notification", 10,
                                                                                  notification_type="idle_prompt")),
     S.WAITING_INPUT),
    ("R-01 SubagentStop", "R-01", SUB, Ctx(last_record_at=ago(30), hook=hook("SubagentStop", 5)), S.DONE),
    ("R-01 Stop + 자식", "R-01", SESSION, Ctx(last_record_at=ago(30), s1=busy(), open_children=2,
                                               hook=hook("Stop", 5)), S.WAITING_CHILD),
    ("R-01 Stop + 예약", "R-01", SESSION, Ctx(last_record_at=ago(30), s1=busy(), wakeup_at=NOW + timedelta(minutes=9),
                                               hook=hook("Stop", 5)), S.SLEEPING),
    ("R-01 SessionEnd", "R-01", SESSION, Ctx(last_record_at=ago(30), s1=None, hook=hook("SessionEnd", 5)), S.DONE),
    ("R-01 훅 도구 실행 중 · 301초 무기록 → RUNNING", "R-01", SESSION,
     Ctx(last_record_at=ago(STALE + 1), s1=busy(), hook=hook("PreToolUse", STALE + 1, tool_running=True,
                                                            tool_name="Bash")), S.RUNNING),
    # R-01 은 '그 뒤 더 새 기록' 이 있으면 진다 → R-02a
    ("R-01 진다: 훅보다 새 기록", "R-02a", SESSION, Ctx(last_record_at=ago(5), s1=busy(),
                                                    hook=hook("Notification", 60, notification_type="permission_prompt")),
     S.RUNNING),
    # R-02a / R-02b 경계 299 / 301
    ("R-02a 299초", "R-02a", SESSION, Ctx(last_record_at=ago(STALE - 1), s1=busy()), S.RUNNING),
    ("R-02b 301초", "R-02b", SESSION, Ctx(last_record_at=ago(STALE + 1), s1=busy()), S.STALE),
    ("R-02b 301초 · 훅 도구 실행 중(기록이 더 새것)", "R-02b", SESSION,
     Ctx(last_record_at=ago(STALE + 1), s1=busy(),
         hook=HookInfo("PreToolUse", ago(STALE + 30), tool_running=True, tool_since=ago(STALE + 30), tool_name="Bash")),
     S.RUNNING),
    # R-03 / R-04 / R-05
    ("R-03 예약 미래", "R-03", SESSION, Ctx(last_record_at=ago(600), s1=idle(), wakeup_at=NOW + timedelta(minutes=5)),
     S.SLEEPING),
    ("R-03 아님: 예약 지남 → R-05", "R-05", SESSION, Ctx(last_record_at=ago(600), s1=idle(),
                                                    wakeup_at=NOW - timedelta(seconds=1)), S.WAITING_INPUT),
    ("R-04 자식 대기", "R-04", SESSION, Ctx(last_record_at=ago(600), s1=idle(), open_children=1), S.WAITING_CHILD),
    ("R-05 idle", "R-05", SESSION, Ctx(last_record_at=ago(600), s1=idle()), S.WAITING_INPUT),
    ("R-05 shell (D-09)", "R-05", SESSION, Ctx(last_record_at=ago(600), s1=idle(status="shell")), S.WAITING_INPUT),
    ("R-04 busy · 턴 끝 · 자식 (D-14)", "R-04", SESSION,
     Ctx(last_record_at=ago(STALE + 60), s1=busy(), turn_ended=True, open_children=2), S.WAITING_CHILD),
    ("R-04 busy · 자식만 (D-14, 턴 끝 모름)", "R-04", SESSION,
     Ctx(last_record_at=ago(STALE + 60), s1=busy(), open_children=1), S.WAITING_CHILD),
    # R-06 / R-07
    ("R-06 S1 없음 · 결과 없는 tool_use", "R-06", SESSION, Ctx(last_record_at=ago(60), s1=None, pending_tool_use=True),
     S.STALE),
    ("R-06 pid 소멸", "R-06", SESSION, Ctx(last_record_at=ago(60), s1=busy(alive=False), pending_tool_use=True),
     S.STALE),
    ("R-07 S1 없음", "R-07", SESSION, Ctx(last_record_at=ago(60), s1=None), S.DONE),
    # R-08 ~ R-12 서브에이전트, 경계 89 / 91 · 299 / 301
    ("R-08 반환", "R-08", SUB, Ctx(last_record_at=ago(10), returned=True, return_at=ago(5)), S.DONE),
    ("R-08 반환 is_error", "R-08", SUB, Ctx(last_record_at=ago(10), returned=True, return_error=True), S.FAILED),
    ("R-09 89초", "R-09", SUB, Ctx(last_record_at=ago(SLOW - 1)), S.RUNNING),
    ("R-12 91초", "R-12", SUB, Ctx(last_record_at=ago(SLOW + 1)), S.RUNNING),
    ("R-10 자식 미종료 91초", "R-10", SUB, Ctx(last_record_at=ago(SLOW + 1), open_children=1), S.WAITING_CHILD),
    ("R-12 299초", "R-12", SUB, Ctx(last_record_at=ago(STALE - 1)), S.RUNNING),
    ("R-11 301초", "R-11", SUB, Ctx(last_record_at=ago(STALE + 1)), S.STALE),
    ("R-11 세션 소멸", "R-11", SUB, Ctx(last_record_at=ago(SLOW + 1), session_alive=False), S.STALE),
    ("R-12 301초 · 훅 도구 실행 중(기록이 더 새것)", "R-12", SUB,
     Ctx(last_record_at=ago(STALE + 1), hook=HookInfo("PreToolUse", ago(STALE + 30), tool_running=True,
                                                     tool_name="Bash")), S.RUNNING),
    ("R-01 서브에이전트 훅 도구 실행 중 · 301초", "R-01", SUB,
     Ctx(last_record_at=ago(STALE + 10), hook=hook("PreToolUse", STALE + 1, tool_running=True, tool_name="Bash")),
     S.RUNNING),
]


@pytest.mark.parametrize("cid,rule,agent,ctx,expected", CASES, ids=[c[0] for c in CASES])
def test_rule_table(cid, rule, agent, ctx, expected):
    v = S.evaluate(agent, ctx, NOW)
    assert (v.state, v.rule) == (expected, rule), v.evidence
    assert v.evidence.startswith(rule) and len(v.evidence) <= 300


def test_every_rule_has_a_case():
    covered = {c[1] for c in CASES}
    assert covered == set(S.RULES), set(S.RULES) - covered
    assert len(S.RULES) == 13


def test_evidence_carries_values():
    s1 = S.evaluate(SESSION, Ctx(last_record_at=ago(STALE + 1), s1=busy()), NOW)
    assert "S1 status=busy" in s1.evidence and f"({STALE + 1}초 전)" in s1.evidence
    v = S.evaluate(SESSION, Ctx(last_record_at=ago(600), s1=idle(status="shell")), NOW)
    assert "D-09" in v.evidence
    v = S.evaluate(SESSION, Ctx(last_record_at=ago(600), s1=idle(status="weird")), NOW)
    assert v.state == S.WAITING_INPUT and "미지 값" in v.evidence
    w = NOW + timedelta(minutes=5)
    v = S.evaluate(SESSION, Ctx(last_record_at=ago(600), s1=idle(), wakeup_at=w), NOW)
    assert v.extra["wake_at"] == "2026-10-17T07:05:00Z"
    v = S.evaluate(SUB, Ctx(last_record_at=ago(STALE - 1)), NOW)
    assert v.slow is True and "응답 느림" in v.evidence


def test_long_bash_shows_minutes():
    h = HookInfo("PreToolUse", ago(STALE + 1), tool_running=True, tool_since=ago(7 * 60), tool_name="Bash",
                 tool_target="make test")
    v = S.evaluate(SESSION, Ctx(last_record_at=ago(STALE + 2), s1=busy(), hook=h), NOW)
    assert v.state == S.RUNNING and "도구 실행 7 분째: Bash" in v.evidence


def test_progress_hook_expires_after_stale():
    """UserPromptSubmit 이 마지막인데 5 분 넘게 무소식이면 R-01 을 내려놓고 R-02b."""
    v = S.evaluate(SESSION, Ctx(last_record_at=ago(STALE + 5), s1=busy(), hook=hook("UserPromptSubmit", STALE + 1)),
                   NOW)
    assert (v.state, v.rule) == (S.STALE, "R-02b")


def test_unpack_triple():
    st, rule, ev = S.evaluate(SUB, Ctx(last_record_at=ago(1)), NOW)
    assert (st, rule) == (S.RUNNING, "R-09") and ev


def test_stale_recovers_to_running(tmp_path):
    """STALE → 새 기록 → RUNNING, state_log 사유에 '회복'."""
    from agentdash.db import conn
    db = tmp_path / "s.db"
    conn.init_db(db)
    con = conn.connect(db)
    con.execute("INSERT INTO agent(agent_key, kind, project_key, session_id, depth, state) VALUES "
                "('A:x','SUBAGENT','p','s',1,'RUNNING')")
    v1 = S.evaluate(SUB, Ctx(last_record_at=ago(STALE + 1)), NOW)
    assert S.apply(con, "A:x", v1, NOW) == "R-11"
    later = NOW + timedelta(seconds=30)
    v2 = S.evaluate(SUB, Ctx(last_record_at=later - timedelta(seconds=2)), later)
    assert v2.state == S.RUNNING
    assert S.apply(con, "A:x", v2, later) == "R-09 회복"
    assert S.apply(con, "A:x", v2, later) is None          # 그대로면 남기지 않는다
    rows = con.execute("SELECT state, reason FROM state_log WHERE agent_key='A:x' ORDER BY rowid").fetchall()
    assert [r[0] for r in rows] == ["STALE", "RUNNING"] and rows[1][1].startswith("R-09 회복")
    assert all(len(r[1]) <= 300 for r in rows)
    assert con.execute("SELECT state, state_reason FROM agent").fetchone()[:] == ("RUNNING", "R-09")
    con.close()


def test_limits_come_from_settings(monkeypatch):
    """settings 값을 바꾸면 경계도 따라간다 (숫자를 코드에 박지 않았다)."""
    v = S.evaluate(SUB, Ctx(last_record_at=ago(50)), NOW, stale_after_sec=100, slow_after_sec=40)
    assert v.rule == "R-12"
    v = S.evaluate(SUB, Ctx(last_record_at=ago(101)), NOW, stale_after_sec=100, slow_after_sec=40)
    assert v.rule == "R-11"


def test_evaluate_all_on_ingested_fixture(fake_claude_home_ro, tmp_path):
    """픽스처 DB 전체 판정 — 모든 행이 상태 8 중 하나 · 규칙 13 중 하나 · S1 없는 세션은 R-06/R-07."""
    from agentdash.collect import ingest
    from agentdash.core import linker
    from agentdash.db import conn
    db = tmp_path / "e.db"
    conn.init_db(db)
    con = conn.connect(db)
    ingest.ingest_all(con, run_hooks=False)
    linker.resolve_all(con)
    out = S.evaluate_all(con, NOW)
    assert out and all(v.state in S.STATES and v.rule in S.RULES for v in out.values())
    rows = con.execute("SELECT agent_key, kind, state, state_reason FROM agent").fetchall()
    assert all(r[2] in S.STATES for r in rows)
    # 픽스처 S1 의 pid 는 이 컴퓨터에서 살아 있지 않을 수 있다 → 세션은 R-02a~R-07 중 하나
    assert {r[3] for r in rows if r[1] == "SESSION"} <= {"R-02a", "R-02b", "R-03", "R-04", "R-05", "R-06", "R-07"}
    assert con.execute("SELECT COUNT(*) FROM state_log").fetchone()[0] >= len(rows)
    con.close()
