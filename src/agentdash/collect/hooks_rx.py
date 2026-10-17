"""훅 이벤트 수신 (spec.md §9.2) — 필요한 필드만 남기고 나머지(프롬프트 · 도구 입력 본문 · 응답)는 버린다. 담당 개발2.

    payload = filter_payload(raw_dict)        # 화이트리스트 — 본문 0
    key     = agent_key_for(payload)          # A:<agent_id> (서브에이전트 안) → S:<session_id>
    store(con, payload, now)                  # hook_event 1 행 (detail ≤ 300 자 JSON)
    hook_info(con, key) -> state.HookInfo     # 판정용: 최근 이벤트 · 도구 실행 중 여부

식별 필드 (decisions.md D-05) — 공식 문서(code.claude.com/docs/en/hooks, 2026-10-17 읽음): 모든 이벤트 공통
`session_id` · `transcript_path` · `cwd` · `hook_event_name`, 서브에이전트 안에서 난 이벤트에는 `agent_id` · `agent_type`,
`SubagentStop` 에는 `agent_transcript_path` 도 있다. 그래서 `agent_id` 가 있으면 `A:<agent_id>`, 없으면
`agent_transcript_path`/`transcript_path` 파일 이름이 `agent-<id>.jsonl` 이면 `A:<id>`, 그 밖은 `S:<session_id>`.
실제 페이로드 실측은 사람이 훅을 설치한 뒤 (미검증).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from agentdash.core import state as S

EVENTS = ("SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop", "Notification", "PreToolUse",
          "PostToolUse", "UserPromptSubmit")
SHORT = 120                     # 설명 · 메시지 앞 120 자 (spec.md §2.3)
DETAIL_MAX = 300                # hook_event.detail ≤ 300 자 (V-04)
#: 남기는 최상위 필드 (짧은 식별자 · 이름 · 경로). 나머지는 전부 버린다.
KEEP = ("hook_event_name", "session_id", "transcript_path", "cwd", "agent_id", "agent_type", "agent_transcript_path",
        "tool_name", "tool_use_id", "notification_type", "source", "reason")
#: 앞 120 자만 남기는 필드
KEEP_SHORT = ("message", "title")
#: 도구 입력에서 남기는 키 (본문 command · prompt · content 는 버린다)
TOOL_INPUT_KEEP = ("file_path", "notebook_path", "path", "url", "description", "subagent_type", "run_in_background")
_AGENT_FILE = re.compile(r"agent-([0-9a-zA-Z]+)\.jsonl$")


def _clip(v, n: int) -> str | None:
    if v is None:
        return None
    s = v if isinstance(v, str) else str(v)
    return s[:n]


def filter_payload(raw) -> dict:
    """화이트리스트. dict 가 아니면 빈 dict. 결과 값은 전부 짧은 문자열 · bool."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for k in KEEP:
        v = raw.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            out[k] = _clip(v, 300)
    for k in KEEP_SHORT:
        v = raw.get(k)
        if isinstance(v, str):
            out[k] = v[:SHORT]
    ti = raw.get("tool_input")
    if isinstance(ti, dict):
        kept = {}
        for k in TOOL_INPUT_KEEP:
            v = ti.get(k)
            if isinstance(v, bool):
                kept[k] = v
            elif isinstance(v, str):
                kept[k] = v[:SHORT]
        if kept:
            out["tool_input"] = kept
    return out


def agent_key_for(p: dict) -> str | None:
    aid = p.get("agent_id")
    if isinstance(aid, str) and aid:
        return f"A:{aid}"
    for f in ("agent_transcript_path", "transcript_path"):
        m = _AGENT_FILE.search(p.get(f) or "")
        if m:
            return f"A:{m.group(1)}"
    sid = p.get("session_id")
    return f"S:{sid}" if isinstance(sid, str) and sid else None


def target_of(p: dict) -> str | None:
    ti = p.get("tool_input") or {}
    for k in ("file_path", "notebook_path", "path", "url", "description"):
        if ti.get(k):
            return str(ti[k])[:SHORT]
    return None


def detail_of(p: dict) -> str:
    """hook_event.detail — 판정에 쓰는 짧은 필드만 JSON 으로 (≤ 300 자)."""
    d = {k: p[k] for k in ("tool_name", "tool_use_id", "notification_type", "source", "reason", "agent_type")
         if p.get(k)}
    tgt = target_of(p)
    if tgt:
        d["target"] = tgt[:80]
    if p.get("message") and p.get("hook_event_name") == "Notification":
        d["message"] = p["message"][:80]
    s = json.dumps(d, ensure_ascii=False)
    while len(s) > DETAIL_MAX and d:
        d.popitem()
        s = json.dumps(d, ensure_ascii=False)
    return s[:DETAIL_MAX]


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def store(con, p: dict, now: datetime) -> str | None:
    """hook_event 1 행. 모르는 이벤트 이름도 남긴다(조용히 버리지 않는다 — 이름 앞 40 자). 붙인 agent_key 를 돌려준다."""
    from agentdash.core import model as M

    ev = p.get("hook_event_name")
    if not ev:
        return None
    key = agent_key_for(p)
    M.add_hook_event(con, key, iso(now), str(ev)[:40], detail_of(p))
    return key


def parse_at(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hook_info(con, agent_key: str) -> S.HookInfo | None:
    """그 에이전트의 최근 훅 → HookInfo. PreToolUse 뒤 같은 tool_use_id(없으면 아무) PostToolUse 가 없으면 도구 실행 중."""
    rows = con.execute("SELECT at, event, detail FROM hook_event WHERE agent_key=? ORDER BY at DESC, rowid DESC LIMIT 50",
                       (agent_key,)).fetchall()
    if not rows:
        return None
    at, ev, det = rows[0][0], rows[0][1], rows[0][2]
    d = _loads(det)
    info = S.HookInfo(event=ev, at=parse_at(at), notification_type=d.get("notification_type"))
    # 도구 실행 중: 가장 최근 PreToolUse 이후 그 도구의 PostToolUse · Stop · SessionEnd · SubagentStop 이 없다
    closed: set[str] = set()
    for r_at, r_ev, r_det in rows:
        rd = _loads(r_det)
        if r_ev in ("Stop", "SessionEnd", "SubagentStop", "UserPromptSubmit"):
            break
        if r_ev == "PostToolUse":
            closed.add(rd.get("tool_use_id") or "*")
        elif r_ev == "PreToolUse":
            tid = rd.get("tool_use_id") or "*"
            if tid not in closed and "*" not in closed:
                info.tool_running = True
                info.tool_since = parse_at(r_at)
                info.tool_name = rd.get("tool_name")
                info.tool_target = rd.get("target")
            break
    return info


def _loads(s) -> dict:
    try:
        v = json.loads(s) if s else {}
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}
