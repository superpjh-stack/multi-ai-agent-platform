"""S2 / S3 / S5 transcript 줄 파서 (spec.md §2.1, goal.md §6, D-11).

  · 세는 줄 종류는 `assistant` · `user` 뿐이다. 도구 호출 · 토큰은 `assistant` 줄에서만 센다 — `api-request-blob` 의
    `message.content` 에도 `tool_use` 가 있지만 요청 사본이다 (D-11 확정: 그 121 건이 전부 assistant 줄에 있는 id).
  · 그 밖의 종류(attachment · api-request · ai-title · mode …)는 None — 무시하되 오류로 세지 않는다. `agent-name` 은 이름만 꺼낸다.
  · assistant/user 줄에 필수 필드가 없거나 JSON 이 깨졌으면 LineError → parse_error.
  · 꺼내는 것: id · 시각 · 모델 · usage 숫자 · 도구 이름 · 대상(file_path · URL 호스트 · 설명 앞 120 자 · SendMessage 받는 이름 ·
    ScheduleWakeup 깰 시각). 텍스트 · thinking · 도구 결과 본문 · command/prompt/content 는 꺼내지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from agentdash.collect.parsers import ParseError

COUNTED = ("assistant", "user")
NAME_TYPES = {"agent-name": "agentName"}
REQUIRED_TOP = ("uuid", "timestamp", "sessionId")
DESC_MAX = 120
FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
READ_TOOLS = {"Read": "file_path", "NotebookRead": "notebook_path"}
DESC_TOOLS = {"Agent", "Task", "Bash", "Monitor"}     # 입력 description 앞 120 자 (command · prompt 는 안 봄)


class LineError(ParseError):
    pass


@dataclass
class ToolUse:
    id: str
    name: str
    target: str | None = None
    file_path: str | None = None      # Write · Edit · NotebookEdit 대상 (file_touch)


@dataclass
class ToolResult:
    tool_use_id: str
    is_error: bool | None
    run_id: str | None = None         # Workflow 결과의 toolUseResult.runId ("wf_…", L-03 단서 — id 만)


@dataclass
class Usage:
    input_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    ttl_split: bool = False           # cache_creation.ephemeral_5m/1h 가 있었나 (없으면 전부 5m, spec §6.1)
    output_tokens: int = 0
    thinking_tokens: int | None = None
    web_search: int = 0
    web_fetch: int = 0
    speed: str | None = None


@dataclass
class Record:
    type: str
    uuid: str | None = None
    parent_uuid: str | None = None
    timestamp: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    request_id: str | None = None
    is_sidechain: bool | None = None
    cwd: str | None = None
    git_branch: str | None = None
    version: str | None = None
    model: str | None = None
    usage: Usage | None = None
    tool_uses: list[ToolUse] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    agent_name: str | None = None     # agent-name 줄
    raw: dict | None = field(default=None, repr=False, compare=False)   # 원래 줄 dict — 메모리에서만 (linker.on_line), 저장 안 함


def _int(v) -> int:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _cut(s, n=DESC_MAX):
    if not isinstance(s, str):
        return None
    s = " ".join(s.split())
    return s[:n] if s else None


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _target(name: str, inp: dict, at: str | None) -> tuple[str | None, str | None]:
    """(target, file_path). 본문 필드는 보지 않는다."""
    if name in FILE_TOOLS:
        fp = inp.get(FILE_TOOLS[name])
        return (fp if isinstance(fp, str) else None), (fp if isinstance(fp, str) else None)
    if name in READ_TOOLS:
        fp = inp.get(READ_TOOLS[name])
        return (fp if isinstance(fp, str) else None), None
    if name in DESC_TOOLS:
        return _cut(inp.get("description")), None
    if name == "SendMessage":
        return _cut(inp.get("to") or inp.get("recipient")), None
    if name == "WebFetch":
        u = inp.get("url")
        return (urlsplit(u).hostname if isinstance(u, str) else None), None
    if name == "Skill":
        return _cut(inp.get("skill")), None
    if name == "ScheduleWakeup":
        if inp.get("stop"):
            return "stop", None
        d = inp.get("delaySeconds")
        if isinstance(d, (int, float)) and at:
            wake = parse_iso(at) + timedelta(seconds=float(d))
            return "wake@" + wake.isoformat(timespec="seconds").replace("+00:00", "Z"), None
        return None, None
    if name.startswith("mcp__"):
        return None, None
    return None, None


def _usage(u: dict) -> Usage:
    cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else None
    total_cc = _int(u.get("cache_creation_input_tokens"))
    if cc is not None and ("ephemeral_5m_input_tokens" in cc or "ephemeral_1h_input_tokens" in cc):
        w5, w1, split = _int(cc.get("ephemeral_5m_input_tokens")), _int(cc.get("ephemeral_1h_input_tokens")), True
    else:
        w5, w1, split = total_cc, 0, False
    otd = u.get("output_tokens_details") if isinstance(u.get("output_tokens_details"), dict) else {}
    stu = u.get("server_tool_use") if isinstance(u.get("server_tool_use"), dict) else {}
    th = otd.get("thinking_tokens")
    return Usage(
        input_tokens=_int(u.get("input_tokens")), cache_read=_int(u.get("cache_read_input_tokens")),
        cache_creation=total_cc, cache_write_5m=w5, cache_write_1h=w1, ttl_split=split,
        output_tokens=_int(u.get("output_tokens")), thinking_tokens=_int(th) if th is not None else None,
        web_search=_int(stu.get("web_search_requests")), web_fetch=_int(stu.get("web_fetch_requests")),
        speed=u.get("speed") if isinstance(u.get("speed"), str) else None)


def parse_line(raw: bytes | str, *, others: bool = False) -> Record | None:
    """줄 하나 → Record. 세지 않는 줄 종류(D-11)는 None — 단 `others=True` 면 시각이 있는 그런 줄도
    `Record(type, uuid, timestamp)` 만 채워 돌려준다(마지막 기록 시각용, 웨이브 D2 R8). 본문은 꺼내지 않는다."""
    try:
        d = json.loads(raw)
    except ValueError:
        raise LineError("JSON 깨짐") from None
    if not isinstance(d, dict):
        raise LineError("줄이 객체가 아님")
    t = d.get("type")
    if t in NAME_TYPES:
        nm = d.get(NAME_TYPES[t])
        return Record(type=t, session_id=d.get("sessionId"), agent_name=_cut(nm)) if isinstance(nm, str) else None
    if t not in COUNTED:
        if t is None:
            raise LineError("type 없음")
        ts = d.get("timestamp")
        if others and isinstance(ts, str) and ts:
            u = d.get("uuid")
            return Record(type=str(t)[:40], uuid=u if isinstance(u, str) else None, timestamp=ts)
        return None
    miss = [k for k in REQUIRED_TOP if not d.get(k)]
    msg = d.get("message")
    if not isinstance(msg, dict):
        miss.append("message")
    if miss:
        raise LineError(f"{t} 필수 필드 없음: {','.join(miss)}")
    rec = Record(
        type=t, uuid=d["uuid"], parent_uuid=d.get("parentUuid"), timestamp=d["timestamp"], session_id=d["sessionId"],
        agent_id=d.get("agentId"), request_id=d.get("requestId"), is_sidechain=d.get("isSidechain"),
        cwd=d.get("cwd"), git_branch=d.get("gitBranch"), version=d.get("version"), raw=d)
    content = msg.get("content")
    blocks = content if isinstance(content, list) else []
    if t == "assistant":
        if "model" not in msg:
            raise LineError("assistant 필수 필드 없음: message.model")
        rec.model = msg.get("model")
        if isinstance(msg.get("usage"), dict):
            rec.usage = _usage(msg["usage"])
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                if not b.get("id") or not b.get("name"):
                    raise LineError("tool_use 에 id/name 없음")
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                target, fp = _target(b["name"], inp, rec.timestamp)
                rec.tool_uses.append(ToolUse(b["id"], b["name"], target, fp))
    else:
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id"):
                ie = b.get("is_error")
                rec.tool_results.append(ToolResult(b["tool_use_id"], ie if isinstance(ie, bool) else None))
        tur = d.get("toolUseResult")
        if len(rec.tool_results) == 1 and isinstance(tur, dict):
            rid = tur.get("runId")
            if isinstance(rid, str) and rid.startswith("wf_") and len(rid) <= 80:
                rec.tool_results[0].run_id = rid
    return rec
