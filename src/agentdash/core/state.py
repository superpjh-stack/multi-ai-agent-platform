"""상태 판정 (spec.md §4.2 R-01 · R-02a · R-02b · R-03~R-12) — 순수 함수 + DB 반영 도우미. 담당 개발2.

    state.evaluate(agent, ctx, now) -> Verdict(state, rule, evidence)

· 위에서부터 먼저 걸리는 규칙 하나. 근거(evidence)는 규칙 코드 + 값(마지막 기록 시각 · 지난 초 · S1 status · 예약 시각 ·
  훅 이벤트)을 담은 짧은 문자열(≤ 300 자, 본문 없음).
· 기준 시간은 settings 의 `stale_after_sec`(300) · `slow_after_sec`(90). 경계: `< slow` 이면 R-09, `< stale` 이면 R-02a.
· `STALE` 은 끝이 아니다 — 새 기록이 들어오면 같은 함수가 RUNNING 을 내고, `transition()` 이 state_log 사유에 "회복"을 붙인다.

결정 반영
  D-09  S1 `status: "shell"` — 턴이 끝난 시각(turn_duration)에 찍히고 그 세션에 백그라운드 셸 자식 프로세스가 살아 있었다(실측 1 건).
        busy 가 아니므로 idle 계열(R-03 · R-04 · R-05)로 판정하고 근거에 `S1 status=shell (D-09)` 를 남긴다.
        busy · idle · shell 밖의 값도 idle 계열로 보되 근거에 `미지 값` 을 남긴다(조용히 삼키지 않는다).
  D-14  S1 `busy` 인 채 5 분 넘게 기록이 없어도 미종료 백그라운드 자식(RUNNING · WAITING_* — STALE 자식은 빼고)이 있으면
        R-02b 의 STALE 대신 WAITING_CHILD(R-04) — 오케스트레이터가 턴을 끝내고(turn_duration) 자식을 기다리는 동안
        S1 이 busy · updatedAt 그대로 남는 실측(2026-10-17, 세션 1 건 · 자식 2).
  D-18  [가설 — 사람 확인 필요, spec R-03 은 idle 만 명시] S1 `busy` · 5 분 넘게 기록 없음이어도 마지막 assistant 가 미래 시각의
        `ScheduleWakeup` 을 예약했고 그 뒤 새 tool_use 가 없으면 SLEEPING(규칙 코드 R-03, 근거 `D-18`). R-02b STALE 보다 먼저,
        D-14 WAITING_CHILD 보다도 먼저(idle 계열의 R-03 > R-04 순서와 같게). 훅이 도구 실행 중이라 하면 RUNNING 이 이긴다.
  D-19  [가설] S1 파일은 있는데 pid 가 죽었으면 "S1 없음"(R-06 · R-07)으로 본다 — R-01 훅도 SessionEnd 밖에는 쓰지 않는다.
  R-08  반환의 오류 여부는 L-07 `linker.return_of` 의 is_error(가장 늦은 반환이 failed/killed 알림 · Agent tool_result
        is_error) — QA2 DEF-QA2-001.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

RUNNING, WAITING_INPUT, WAITING_PERMISSION = "RUNNING", "WAITING_INPUT", "WAITING_PERMISSION"
SLEEPING, WAITING_CHILD, DONE, FAILED, STALE = "SLEEPING", "WAITING_CHILD", "DONE", "FAILED", "STALE"
STATES = (RUNNING, WAITING_INPUT, WAITING_PERMISSION, SLEEPING, WAITING_CHILD, DONE, FAILED, STALE)
RULES = ("R-01", "R-02a", "R-02b", "R-03", "R-04", "R-05", "R-06", "R-07", "R-08", "R-09", "R-10", "R-11", "R-12")
SESSION_KIND = "SESSION"
EVIDENCE_MAX = 300

#: 훅 이벤트 → 상태 (spec.md §9.2 표). Stop · SessionStart · PreToolUse 는 아래에서 따로 다룬다.
HOOK_STATE = {
    "UserPromptSubmit": RUNNING,
    "PreToolUse": RUNNING,
    "PostToolUse": RUNNING,
    "SubagentStart": RUNNING,
    "SubagentStop": DONE,
    "SessionEnd": DONE,
}
#: 훅이 알려 준 "진행 중" 계열은 무기록 5 분이 지나면 R-01 을 내려놓는다 (PreToolUse 는 예외 — 긴 도구 실행).
_HOOK_PROGRESS = {"UserPromptSubmit", "PostToolUse", "SubagentStart", "SessionStart"}


@dataclass
class HookInfo:
    """그 에이전트의 최근 훅 사실 (hook_event 에서)."""
    event: str                         # 가장 최근 훅 이벤트 이름
    at: datetime
    notification_type: str | None = None   # permission_prompt | idle_prompt …
    tool_running: bool = False         # PreToolUse 뒤 PostToolUse 없음
    tool_since: datetime | None = None
    tool_name: str | None = None
    tool_target: str | None = None


@dataclass
class S1Info:
    status: str | None                 # busy | idle | shell | …
    pid_alive: bool
    updated_at: datetime | None = None


@dataclass
class Ctx:
    """판정 입력 — 기록 · S1 · 훅에서 모은 사실. 호출하는 쪽(파이프라인)이 채운다."""
    last_record_at: datetime | None = None
    s1: S1Info | None = None           # 세션만. None = S1 없음
    pending_tool_use: bool = False     # 마지막 항목이 결과 없는 tool_use (R-06)
    turn_ended: bool = False           # 마지막 기록이 system turn_duration / stop_hook_summary (D-14)
    wakeup_at: datetime | None = None  # 마지막 assistant 의 ScheduleWakeup 예약 시각 (R-03)
    open_children: int = 0             # 아직 안 끝난 백그라운드 자식 수 (R-04 · R-10)
    returned: bool = False             # L-07 결과 반환 있음 (R-08)
    return_error: bool = False
    return_at: datetime | None = None
    session_alive: bool = True         # 서브에이전트: 소속 세션 프로세스 살아 있음 (R-11)
    hook: HookInfo | None = None


@dataclass(frozen=True)
class Verdict:
    state: str
    rule: str
    evidence: str
    slow: bool = False                 # R-12 "응답 느림"
    extra: dict = field(default_factory=dict, compare=False)

    def __iter__(self):                # (state, rule, evidence) 로 풀 수 있게
        return iter((self.state, self.rule, self.evidence))


def _limits() -> tuple[int, int]:
    from agentdash import settings
    s = settings.get()
    return s.stale_after_sec, s.slow_after_sec


def _iso(t: datetime | None) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else "없음"


def _v(state: str, rule: str, *parts: str, slow: bool = False, **extra) -> Verdict:
    ev = f"{rule} " + " · ".join(p for p in parts if p)
    return Verdict(state, rule, ev[:EVIDENCE_MAX], slow, extra)


def evaluate(agent, ctx: Ctx, now: datetime, *, stale_after_sec: int | None = None,
             slow_after_sec: int | None = None) -> Verdict:
    """에이전트 하나의 상태. `agent` 는 `.kind` 속성(또는 'kind' 키)을 가진 것 — SESSION 이면 세션 규칙, 나머지는 서브에이전트 규칙."""
    if stale_after_sec is None or slow_after_sec is None:
        st, sl = _limits()
        stale_after_sec = st if stale_after_sec is None else stale_after_sec
        slow_after_sec = sl if slow_after_sec is None else slow_after_sec
    kind = agent.get("kind") if isinstance(agent, dict) else getattr(agent, "kind", None)
    age = (now - ctx.last_record_at).total_seconds() if ctx.last_record_at else None
    rec = f"마지막 기록 {_iso(ctx.last_record_at)} ({int(age)}초 전)" if age is not None else "기록 없음"

    v = _r01(kind, ctx, now, rec, stale_after_sec)
    if v is not None:
        return v
    if kind == SESSION_KIND:
        return _session(ctx, now, age, rec, stale_after_sec)
    return _subagent(ctx, now, age, rec, stale_after_sec, slow_after_sec)


def _tool_note(h: HookInfo | None, now: datetime) -> str:
    if not h or not h.tool_running:
        return ""
    since = h.tool_since or h.at
    mins = int((now - since).total_seconds() // 60)
    tgt = f" {h.tool_target[:60]}" if h.tool_target else ""
    return f"도구 실행 {mins} 분째: {h.tool_name or '?'}{tgt}"


def _r01(kind, ctx: Ctx, now: datetime, rec: str, stale: int) -> Verdict | None:
    """R-01 — 훅이 최근 상태를 알려 줌. 그 뒤에 더 새 기록이 있으면 기록이 이긴다(None → 아래 규칙)."""
    h = ctx.hook
    if h is None:
        return None
    if ctx.last_record_at and ctx.last_record_at > h.at:
        return None
    gone = ctx.s1 is None or not ctx.s1.pid_alive          # D-19: pid 소멸 = S1 없음
    if kind == SESSION_KIND and gone and h.event != "SessionEnd":
        return None                    # 프로세스가 사라졌다 — R-06/R-07 이 판단
    hook = f"훅 {h.event} {_iso(h.at)}"
    if h.event == "PreToolUse" or h.tool_running:
        if gone and kind == SESSION_KIND:
            return None
        if kind != SESSION_KIND and not ctx.session_alive:
            return None
        return _v(RUNNING, "R-01", hook, _tool_note(h, now) or "도구 실행 중", rec)
    if h.event in _HOOK_PROGRESS and (now - h.at).total_seconds() >= stale:
        return None                    # 진행 중이라던 훅도 5 분 무소식이면 기록 규칙으로
    if h.event == "Notification":
        nt = (h.notification_type or "").lower()
        if "permission" in nt:
            return _v(WAITING_PERMISSION, "R-01", hook, f"notification_type={nt[:40]}", rec)
        return _v(WAITING_INPUT, "R-01", hook, f"notification_type={nt[:40] or '없음'}", rec)
    if h.event == "Stop":
        if ctx.wakeup_at and ctx.wakeup_at > now:
            return _v(SLEEPING, "R-01", hook, f"ScheduleWakeup {_iso(ctx.wakeup_at)}", rec, wake_at=_iso(ctx.wakeup_at))
        if ctx.open_children > 0:
            return _v(WAITING_CHILD, "R-01", hook, f"미종료 자식 {ctx.open_children}", rec)
        return _v(WAITING_INPUT, "R-01", hook, rec)
    if h.event == "SessionStart":
        idle = ctx.s1 is not None and ctx.s1.status != "busy"
        return _v(WAITING_INPUT if idle else RUNNING, "R-01", hook, rec)
    if h.event == "SubagentStop" and ctx.return_error:
        return _v(FAILED, "R-01", hook, "결과 is_error", rec)
    st = HOOK_STATE.get(h.event)
    if st is None:
        return None                    # 모르는 이벤트 — 판정에 쓰지 않는다
    return _v(st, "R-01", hook, rec)


def _session(ctx: Ctx, now: datetime, age, rec: str, stale: int) -> Verdict:
    s1 = ctx.s1
    if s1 is not None and s1.pid_alive:
        status = s1.status or "없음"
        s1note = f"S1 status={status}"
        if status == "busy":
            if age is not None and age < stale:
                return _v(RUNNING, "R-02a", s1note, "pid 살아 있음", rec)
            note = _tool_note(ctx.hook, now)
            if note:
                return _v(RUNNING, "R-02b", s1note, note, rec)
            if ctx.wakeup_at and ctx.wakeup_at > now:
                return _v(SLEEPING, "R-03", s1note, f"ScheduleWakeup 깰 시각 {_iso(ctx.wakeup_at)}", rec, "D-18",
                          wake_at=_iso(ctx.wakeup_at))
            if ctx.open_children > 0:
                return _v(WAITING_CHILD, "R-04", s1note, "턴 끝(turn_duration)" if ctx.turn_ended else "",
                          f"미종료 백그라운드 자식 {ctx.open_children}", rec, "D-14")
            return _v(STALE, "R-02b", s1note, f"{stale}초 넘게 기록 없음", rec)
        if status == "shell":
            s1note += " (D-09)"
        elif status != "idle":
            s1note += " (미지 값 — idle 계열로 판정)"
        if ctx.wakeup_at and ctx.wakeup_at > now:
            return _v(SLEEPING, "R-03", s1note, f"ScheduleWakeup 깰 시각 {_iso(ctx.wakeup_at)}", rec,
                      wake_at=_iso(ctx.wakeup_at))
        if ctx.open_children > 0:
            return _v(WAITING_CHILD, "R-04", s1note, f"미종료 백그라운드 자식 {ctx.open_children}", rec)
        return _v(WAITING_INPUT, "R-05", s1note, rec)
    gone = "S1 없음" if s1 is None else "S1 있음 · pid 소멸 (D-19)"
    if ctx.pending_tool_use:
        return _v(STALE, "R-06", gone, "마지막 항목이 결과 없는 tool_use", rec)
    return _v(DONE, "R-07", gone, rec)


def _subagent(ctx: Ctx, now: datetime, age, rec: str, stale: int, slow: int) -> Verdict:
    if ctx.returned:
        when = f"반환 {_iso(ctx.return_at)}" if ctx.return_at else "반환 있음"
        if ctx.return_error:
            return _v(FAILED, "R-08", when, "결과 is_error", rec)
        return _v(DONE, "R-08", when, rec)
    if age is not None and age < slow:
        return _v(RUNNING, "R-09", f"{slow}초 안", rec)
    if ctx.open_children > 0:
        return _v(WAITING_CHILD, "R-10", f"미종료 자식 {ctx.open_children}", rec)
    note = _tool_note(ctx.hook, now) if ctx.session_alive else ""
    if not ctx.session_alive:
        return _v(STALE, "R-11", "소속 세션 프로세스 사라짐", rec)
    if (age is None or age >= stale) and not note:
        return _v(STALE, "R-11", f"{stale}초 넘게 기록 없음", rec)
    return _v(RUNNING, "R-12", "응답 느림", note or f"{slow}~{stale}초 무기록", rec, slow=True)


# ── 전이 · DB 반영 ───────────────────────────────────────────────────────────

def transition(prev_state: str | None, v: Verdict) -> str | None:
    """state_log 사유. 상태가 그대로면 None(남기지 않음). STALE → 다른 상태면 '<규칙> 회복'."""
    if prev_state == v.state:
        return None
    if prev_state == STALE and v.state != STALE:
        return f"{v.rule} 회복"
    return v.rule


def apply(con, agent_key: str, v: Verdict, now: datetime) -> str | None:
    """agent.state · state_since + state_log (개발1 `model.set_state` — agent.state SSE 도 거기서 나간다).

    state_reason = 규칙 코드, state_log.reason = 전이 사유(회복 포함) + 근거. 바뀌었으면 사유, 아니면 None.
    agent 행이 없으면 None (행 만들기는 개발1 model.upsert_agent 몫).
    """
    from agentdash.core import model as M

    row = con.execute("SELECT state, state_reason FROM agent WHERE agent_key=?", (agent_key,)).fetchone()
    if row is None:
        return None
    reason = transition(row[0], v)
    if reason is None:
        if row[1] != v.rule:
            con.execute("UPDATE agent SET state_reason=? WHERE agent_key=?", (v.rule, agent_key))
        return None
    log = v.evidence if reason == v.rule else f"{reason} · {v.evidence}"
    M.set_state(con, agent_key, v.state, log[:EVIDENCE_MAX], _iso(now))
    con.execute("UPDATE agent SET state_reason=? WHERE agent_key=?", (v.rule, agent_key))
    return reason


# ── DB 에서 Ctx 만들기 · 전체 판정 ─────────────────────────────────────────────

FINAL = (DONE, FAILED)


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def pid_alive(pid: int | None) -> bool:
    """프로세스 존재 확인 (신호 0 — 아무것도 보내지 않는다)."""
    import os
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    return True


def load_s1() -> dict:
    """session_id → S1Info. 개발1 parsers.session_file.scan() (원천 읽기만)."""
    from agentdash.collect.parsers import session_file as s1_p
    out = {}
    for sid, sf in s1_p.scan().items():
        out[sid] = S1Info(sf.status, pid_alive(sf.pid), _dt(getattr(sf, "updated_at", None)))
    return out


def build_ctx(con, row, now: datetime, s1map: dict, children: dict) -> Ctx:
    """agent 행 하나 → Ctx. row = (agent_key, kind, session_id, last_event_at, ended_at)."""
    from agentdash.collect import hooks_rx

    key, kind, sid, last, ended = row
    ctx = Ctx(last_record_at=_dt(last))
    ctx.hook = hooks_rx.hook_info(con, key)
    ctx.open_children = children.get(key, 0)
    if kind == SESSION_KIND:
        ctx.s1 = s1map.get(sid)
        t = con.execute("SELECT tool, target, ok, at FROM tool_call WHERE agent_key=? ORDER BY at DESC LIMIT 1",
                        (key,)).fetchone()
        if t is not None:
            ctx.pending_tool_use = t[2] is None and t[0] not in ("Agent", "Workflow")
        # R-03 "마지막 assistant 가 ScheduleWakeup" — 가장 늦은 tool_use 가 ScheduleWakeup 일 때만 (같은 줄의 다른 도구는 허용)
        w = con.execute("SELECT target, at FROM tool_call WHERE agent_key=? AND tool='ScheduleWakeup' ORDER BY at DESC "
                        "LIMIT 1", (key,)).fetchone()
        if w and w[0] and str(w[0]).startswith("wake@") and (t is None or str(t[3]) <= str(w[1])):
            ctx.wakeup_at = _dt(str(w[0])[5:])
    else:
        if ended is None and kind == "WORKFLOW_AGENT":
            # 워크플로 에이전트는 반환 신호가 없다 — 워크플로 실행(S6)이 끝났으면 그 에이전트도 끝 (L-03)
            w = con.execute("SELECT p.ended_at FROM agent a JOIN agent p ON p.agent_key=a.parent_key "
                            "WHERE a.agent_key=? AND p.kind='WORKFLOW'", (key,)).fetchone()
            ended = w[0] if w else None
        ctx.returned = ended is not None
        ctx.return_at = _dt(ended)
        if ctx.returned:
            from agentdash.core import linker
            ret = linker.return_of(con, key)            # failed/killed 알림 · Agent is_error (DEF-QA2-001)
            e = con.execute("SELECT 1 FROM agent a JOIN tool_call t ON t.tool_use_id=a.spawn_tool_use "
                            "WHERE a.agent_key=? AND t.ok=0", (key,)).fetchone()
            ctx.return_error = (ret is not None and ret.is_error) or (ret is None and e is not None)
        s = s1map.get(sid)
        ctx.session_alive = bool(s and s.pid_alive)
    return ctx


def _open_children(con) -> dict:
    """부모 키 → 아직 안 끝난 자식 수 (ended_at 없음 · DONE/FAILED/STALE 아님). STALE 자식은 기다리지 않는 것으로 본다."""
    out: dict = {}
    for p, n in con.execute("SELECT parent_key, COUNT(*) FROM agent WHERE parent_key IS NOT NULL AND ended_at IS NULL "
                            "AND state NOT IN ('DONE','FAILED','STALE') AND kind != 'SESSION' GROUP BY parent_key"):
        out[p] = n
    return out


def evaluate_one(con, agent_key: str, now: datetime, *, s1map: dict | None = None) -> tuple[Verdict, str | None] | None:
    row = con.execute("SELECT agent_key, kind, session_id, last_event_at, ended_at FROM agent WHERE agent_key=?",
                      (agent_key,)).fetchone()
    if row is None:
        return None
    s1map = load_s1() if s1map is None else s1map
    v = evaluate({"kind": row[1]}, build_ctx(con, tuple(row), now, s1map, _open_children(con)), now)
    return v, apply(con, agent_key, v, now)


def evaluate_all(con, now: datetime | None = None) -> dict[str, Verdict]:
    """전체 판정 — 깊은 것(자식)부터 돌려 부모의 '미종료 자식' 이 새 값을 보게 한다. 커밋하지 않는다."""
    now = now or datetime.now(timezone.utc)
    s1map = load_s1()
    out: dict[str, Verdict] = {}
    rows = con.execute("SELECT agent_key, kind, session_id, last_event_at, ended_at, depth FROM agent "
                       "ORDER BY depth DESC").fetchall()
    for r in rows:
        v = evaluate({"kind": r[1]}, build_ctx(con, tuple(r[:5]), now, s1map, _open_children(con)), now)
        apply(con, r[0], v, now)
        out[r[0]] = v
    return out


# ── 수집 뒤 · 주기 판정 ─────────────────────────────────────────────────────

def post_hook(con, changed: set[str]) -> None:
    """개발1 ingest.add_post_hook 용 — 연결(linker.resolve_all) 뒤 바뀐 에이전트와 그 조상만 다시 판정한다."""
    from agentdash.core import linker
    before = dict(con.execute("SELECT agent_key, ended_at FROM agent").fetchall())
    linker.resolve_all(con, sources_complete=False)
    # 부모 기록의 알림 · 다시 깨움으로 ended_at 이 바뀐 자식도 다시 판정 (자식 기록은 그대로라 changed 에 없다)
    changed = set(changed) | {k for k, e in con.execute("SELECT agent_key, ended_at FROM agent") if before.get(k) != e}
    if not changed:
        return
    now = datetime.now(timezone.utc)
    s1map = load_s1()
    keys: list[str] = []
    seen: set[str] = set()
    for k in changed:
        cur = k
        while cur and cur not in seen:          # 자식 → 부모 순 (부모가 새 자식 상태를 보게)
            seen.add(cur)
            keys.append(cur)
            row = con.execute("SELECT parent_key FROM agent WHERE agent_key=?", (cur,)).fetchone()
            cur = row[0] if row else None
    depth = {r[0]: r[1] for r in con.execute("SELECT agent_key, depth FROM agent")}
    for k in sorted(keys, key=lambda x: -(depth.get(x) or 0)):
        evaluate_one(con, k, now, s1map=s1map)


def register() -> None:
    """ingest 수집 뒤 연결 · 판정을 붙인다 (한 번만)."""
    from agentdash.collect import ingest
    ingest.add_post_hook(post_hook)


def tick(db_path=None) -> int:
    """10 초 주기 판정 한 번 — 끝나지 않은(DONE · FAILED 아님) 에이전트 전부. 바뀐 수."""
    from agentdash.db import conn
    con = conn.connect(db_path)
    try:
        now = datetime.now(timezone.utc)
        s1map = load_s1()
        n = 0
        rows = con.execute("SELECT agent_key FROM agent WHERE state NOT IN ('DONE','FAILED') OR state IS NULL "
                           "ORDER BY depth DESC").fetchall()
        for (k,) in rows:
            res = evaluate_one(con, k, now, s1map=s1map)
            if res and res[1]:
                n += 1
        con.commit()
        return n
    finally:
        con.close()


def start_ticker(interval_sec: float | None = None, db_path=None):
    """판정 주기 스레드 (spec §4.2 '10 초마다'). (thread, stop_event) — 앱 lifespan 이 부른다(§3 요청)."""
    import threading
    from agentdash import settings
    if interval_sec is None:
        interval_sec = float((settings.get().raw.get("collect") or {}).get("state_tick_sec", 10))
    stop = threading.Event()

    def loop():
        while not stop.wait(interval_sec):
            tick(db_path)

    t = threading.Thread(target=loop, name="agentdash-state-tick", daemon=True)
    t.start()
    return t, stop
