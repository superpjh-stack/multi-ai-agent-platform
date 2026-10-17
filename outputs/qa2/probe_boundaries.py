"""G-09 경계 탐침 — state.evaluate 순수 함수만 부른다(DB · 원천 없음)."""
from datetime import datetime, timedelta, timezone
from agentdash.core import state as S
from agentdash.core.state import Ctx, S1Info, HookInfo
N = datetime(2026, 10, 17, 7, 0, tzinfo=timezone.utc)
ago = lambda s: N - timedelta(seconds=s)
cases = [
 ("SUB 정확히 90초", {"kind": "SUBAGENT"}, Ctx(last_record_at=ago(90))),
 ("SUB 정확히 300초", {"kind": "SUBAGENT"}, Ctx(last_record_at=ago(300))),
 ("SES busy 정확히 300초", {"kind": "SESSION"}, Ctx(last_record_at=ago(300), s1=S1Info("busy", True))),
 ("SES busy · pid 죽음 · 60초 · 미결 없음", {"kind": "SESSION"}, Ctx(last_record_at=ago(60), s1=S1Info("busy", False))),
 ("SES busy · pid 죽음 · 600초", {"kind": "SESSION"}, Ctx(last_record_at=ago(600), s1=S1Info("busy", False))),
 ("SES busy · 600초 · ScheduleWakeup 미래 · 자식 0", {"kind": "SESSION"}, Ctx(last_record_at=ago(600), s1=S1Info("busy", True), wakeup_at=N + timedelta(minutes=5))),
 ("SES idle · 예약 미래 + 자식 1 (R-03 먼저)", {"kind": "SESSION"}, Ctx(last_record_at=ago(600), s1=S1Info("idle", True), wakeup_at=N + timedelta(minutes=5), open_children=1)),
 ("SUB 세션 죽음 · 훅 도구 실행 중", {"kind": "SUBAGENT"}, Ctx(last_record_at=ago(120), session_alive=False, hook=HookInfo("PreToolUse", ago(130), tool_running=True))),
 ("SUB 반환 · 그 뒤 새 기록 (returned=True 이면 기록 무시)", {"kind": "SUBAGENT"}, Ctx(last_record_at=ago(5), returned=True, return_at=ago(60))),
]
for name, a, c in cases:
    v = S.evaluate(a, c, N)
    print(f"{name:45s} -> {v.state} {v.rule}")
