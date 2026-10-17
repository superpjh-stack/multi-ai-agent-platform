"""원천 파일 → DB (spec.md §2 · §3). 담당 개발1.

    classify(path)          원천 종류 S1 · S2 · S3 · S4 · S5 · S5meta · S5journal · S6 | None
    ingest_path(con, path)  그 파일의 새 부분을 읽어 쓴다 → 바뀐 agent_key 집합
    ingest_all(con)         원천 전체 스캔 (백필 · 60 초 재스캔)
    add_post_hook(fn)       수집 뒤 fn(con, changed_keys) — linker · state 가 등록

원천은 읽기만 한다 (tail 이 'rb' 로 연다). 원천 루트는 settings.get().claude_home 로만 받는다.

포크 사본 (D-02 가설 반박): `isFork` 서브에이전트 기록은 맨 앞에 부모 기록 줄을 uuid · requestId · 시각 그대로 다시 적는다.
그 줄(부모 파일에 같은 uuid 가 있는 줄 + 부모 assistant 와 requestId 가 같은 assistant 줄 = 띄운 호출의 재기록)은
부모 몫이므로 토큰 · 도구 호출로 세지 않는다. 사본은 포크 시작 때 한 번에 적히므로 처음 읽기(offset 0)에서만 확인한다.
단 사본 줄의 usage 가 소유 행보다 **더 최종**(output 큼)이면 그 값을 소유 행에 반영한다 (DEF-QA1-001 —
requestId 하나는 세션에서 한 번, 값은 소유 기록 + 사본을 통틀어 output 최대 줄). 소유 행이 아직 없으면(부모 기록을
아직 못 읽음) `_fork_pending` 에 두었다가 다음 기록을 읽은 뒤 다시 반영한다.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from agentdash import settings
from agentdash.collect import tail
from agentdash.collect.parsers import ParseError
from agentdash.collect.parsers import meta as meta_p
from agentdash.collect.parsers import session_file as s1_p
from agentdash.collect.parsers import transcript as tr_p
from agentdash.collect.parsers import workflow as wf_p
from agentdash.core import model as M
from agentdash.core import usage as U

META_WAIT_SEC = 60          # 서브에이전트 jsonl 이 meta 보다 먼저 보이면 이만큼 기다린다 (포크 여부를 알아야 사본을 뺀다)
_post_hooks: list[Callable[[sqlite3.Connection, set[str]], None]] = []
fork_copied: dict[str, int] = {}      # 포크 jsonl 경로 → 사본으로 뺀 줄 수 (check 도구 · 보고용)
#: (DB 파일, session_id, requestId) → 사본 줄 중 output 최대 UsageEvent — 소유 행이 생기면 반영 (DEF-QA1-001)
_fork_pending: dict[tuple[str, str, str], M.UsageEvent] = {}
_pricing_cache: dict = {}


def add_post_hook(fn: Callable[[sqlite3.Connection, set[str]], None]) -> None:
    if fn not in _post_hooks:
        _post_hooks.append(fn)


def remove_post_hook(fn) -> None:
    if fn in _post_hooks:
        _post_hooks.remove(fn)


_on_line_cache: dict = {}


def _on_line():
    """개발2 linker.on_line(con, author_key, line_dict) — tool_call 에 안 남는 연결 사실(task-notification · Workflow runId).
    progress-dev2 §3 R1. 모듈이 없으면 None."""
    if "fn" not in _on_line_cache:
        import importlib
        import importlib.util

        fn = None
        if importlib.util.find_spec("agentdash.core.linker") is not None:
            fn = getattr(importlib.import_module("agentdash.core.linker"), "on_line", None)
        _on_line_cache["fn"] = fn
    return _on_line_cache["fn"]


def _state_post_hook():
    """개발2 state.post_hook(con, changed) — linker.resolve_all + 바뀐 키 재판정 (progress-dev2 §3 R3). 없으면 None."""
    if "post" not in _on_line_cache:
        import importlib
        import importlib.util

        fn = None
        if importlib.util.find_spec("agentdash.core.state") is not None:
            fn = getattr(importlib.import_module("agentdash.core.state"), "post_hook", None)
        _on_line_cache["post"] = fn
    return _on_line_cache["post"]


def _pricing() -> U.Pricing:
    p = settings.CONFIG_DIR / "pricing.yaml"
    m = p.stat().st_mtime
    if _pricing_cache.get("mtime") != m:
        _pricing_cache.update(mtime=m, pricing=U.load_pricing())
    return _pricing_cache["pricing"]


def project_key_of(cwd: str) -> str:
    """프로젝트 폴더명 규칙 (spec §2.1): 경로의 / · 공백 · 비ASCII → '-'. 실측 36/36 일치."""
    return re.sub(r"[^A-Za-z0-9-]", "-", cwd)


# ── 분류 ─────────────────────────────────────────────────────────────
def _rel(path: Path, home: Path) -> tuple[str, ...] | None:
    try:
        return path.resolve().relative_to(home).parts
    except ValueError:
        return None


def classify(path: str | Path, home: Path | None = None) -> str | None:
    home = home or settings.get().claude_home
    parts = _rel(Path(path), home)
    if not parts:
        return None
    name = parts[-1]
    if parts[0] == "sessions" and len(parts) == 2 and name.endswith(".json"):
        return "S1"
    if parts[0] != "projects":
        return None
    n = len(parts)
    if n == 3 and name.endswith(".jsonl"):
        return "S2"
    if n == 5 and parts[3] == "subagents" and name.startswith("agent-"):
        return "S3" if name.endswith(".jsonl") else ("S4" if name.endswith(".meta.json") else None)
    if n == 7 and parts[3] == "subagents" and parts[4] == "workflows" and parts[5].startswith("wf_"):
        if name.startswith("agent-"):
            return "S5" if name.endswith(".jsonl") else ("S5meta" if name.endswith(".meta.json") else None)
        if name == "journal.jsonl":
            return "S5journal"
        return None
    if n == 5 and parts[3] == "workflows" and name.startswith("wf_") and name.endswith(".json"):
        return "S6"
    return None


# ── 이름 ─────────────────────────────────────────────────────────────
def _set_name(con: sqlite3.Connection, key: str, name: str | None, *, force: bool, fallback_only: str | None = None) -> None:
    """force=True 는 덮어쓰기. 아니면 비어 있거나 대체 이름(fallback_only)일 때만."""
    if not name:
        return
    name = M.clip(name, M.DESC_MAX)
    if force:
        con.execute("UPDATE agent SET name=? WHERE agent_key=?", (name, key))
    else:
        con.execute("UPDATE agent SET name=? WHERE agent_key=? AND (name IS NULL OR name=?)", (name, key, fallback_only))


# ── S1 ───────────────────────────────────────────────────────────────
def _ingest_s1(con: sqlite3.Connection, path: Path) -> set[str]:
    if not tail.whole_changed(con, path):
        return set()
    try:
        sf = s1_p.parse(path)
    except ParseError as e:
        con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
        M.add_parse_error(con, path, None, str(e))
        tail.mark_whole(con, path)
        return set()
    con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
    key = M.key_session(sf.session_id)
    cur = M.get_agent(con, key)
    a = M.Agent(agent_key=key, kind="SESSION", project_key=cur.project_key if cur else project_key_of(sf.cwd),
                session_id=sf.session_id, project_path=sf.cwd, depth=0, cc_version=sf.version, pid=sf.pid,
                started_at=sf.started_at)
    M.upsert_agent(con, a)
    _set_name(con, key, sf.name, force=True)
    tail.mark_whole(con, path)
    return {key}


# ── meta (S4 · S5meta) ───────────────────────────────────────────────
def _agent_from_meta(m: meta_p.Meta, kind: str) -> M.Agent:
    return M.Agent(agent_key=M.key_agent(m.agent_id), kind=kind, project_key=m.project_key, session_id=m.session_id,
                   spawn_tool_use=m.tool_use_id, depth=m.spawn_depth if m.spawn_depth is not None else 1,
                   agent_type=m.agent_type, request_shape=m.request_shape, extra=m.extra())


def _ingest_meta(con: sqlite3.Connection, path: Path, kind: str) -> set[str]:
    if not tail.whole_changed(con, path):
        return set()
    con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
    try:
        m = meta_p.parse(path)
    except ParseError as e:
        M.add_parse_error(con, path, None, str(e))
        tail.mark_whole(con, path)
        return set()
    a = _agent_from_meta(m, kind)
    M.upsert_agent(con, a)
    fallback = f"{m.agent_type or 'agent'} {m.agent_id[:6]}"
    if m.description:
        # 서브에이전트: description 이 1 순위 · 워크플로 에이전트: journal label 이 1 순위 (spec §3.1)
        _set_name(con, a.agent_key, m.description, force=(kind == "SUBAGENT"), fallback_only=fallback)
    else:
        _set_name(con, a.agent_key, fallback, force=False)
    if kind == "WORKFLOW_AGENT" and m.wf_id:
        _ensure_workflow_node(con, m.wf_id, m.project_key, m.session_id)
    tail.mark_whole(con, path)
    return {a.agent_key}


def _ensure_workflow_node(con: sqlite3.Connection, wf_id: str, project_key: str, session_id: str) -> str:
    key = M.key_workflow(wf_id)
    if M.get_agent(con, key) is None:
        M.upsert_agent(con, M.Agent(agent_key=key, kind="WORKFLOW", project_key=project_key, session_id=session_id,
                                    depth=1, name=wf_id))
    return key


# ── S6 ───────────────────────────────────────────────────────────────
def _ingest_s6(con: sqlite3.Connection, path: Path) -> set[str]:
    if not tail.whole_changed(con, path):
        return set()
    con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
    try:
        w = wf_p.parse(path)
    except ParseError as e:
        M.add_parse_error(con, path, None, str(e))
        tail.mark_whole(con, path)
        return set()
    key = _ensure_workflow_node(con, w.run_id, w.project_key, w.session_id)
    M.upsert_agent(con, M.Agent(agent_key=key, kind="WORKFLOW", project_key=w.project_key, session_id=w.session_id,
                                depth=1, model=w.default_model, started_at=w.started_at or w.timestamp,
                                last_event_at=w.ended_at or w.timestamp, extra=M.AgentExtra(wf_id=w.run_id)))
    _set_name(con, key, w.name, force=True)
    if w.ended_at:
        M.set_ended(con, key, w.ended_at)
    tail.mark_whole(con, path)
    return {key}


# ── journal (S5 부속) ────────────────────────────────────────────────
def _ingest_journal(con: sqlite3.Connection, path: Path) -> set[str]:
    ch = tail.read_new(con, path)
    if ch.unchanged:
        return set()
    if ch.reset:
        con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
    loc_wf = path.parent.name
    sess_dir = path.parent.parent.parent.parent
    changed: set[str] = set()
    for raw, ln in zip(ch.lines, ch.line_numbers):
        try:
            got = wf_p.parse_journal_line(raw)
        except ParseError as e:
            M.add_parse_error(con, path, ln, str(e))
            continue
        if got is None:
            continue
        aid, label, _phase = got
        key = M.key_agent(aid)
        if M.get_agent(con, key) is None:
            M.upsert_agent(con, M.Agent(agent_key=key, kind="WORKFLOW_AGENT", project_key=sess_dir.parent.name,
                                        session_id=sess_dir.name, depth=1))
            _ensure_workflow_node(con, loc_wf, sess_dir.parent.name, sess_dir.name)
        _set_name(con, key, label, force=True)
        changed.add(key)
    tail.commit(con, ch)
    return changed


# ── transcript (S2 · S3 · S5) ────────────────────────────────────────
def _ids_of(path: Path) -> tuple[set[str], set[str]]:
    """부모 기록의 (uuid 집합, assistant requestId 집합) — 포크 사본 판정용, 읽기만.
    깨진 줄은 부모 쪽 수집이 parse_error 로 센다."""
    import json

    uuids: set[str] = set()
    rids: set[str] = set()
    if not path.exists():
        return uuids, rids
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            if isinstance(d.get("uuid"), str):
                uuids.add(d["uuid"])
            if d.get("type") == "assistant" and isinstance(d.get("requestId"), str):
                rids.add(d["requestId"])
    return uuids, rids


def _db_id(con: sqlite3.Connection) -> str:
    row = con.execute("PRAGMA database_list").fetchone()
    return (row[2] or ":memory:") if row else ""


def _apply_fork_pending(con: sqlite3.Connection) -> set[str]:
    """미뤄 둔 사본 최종값을 소유 행에 반영한다 → 값이 바뀐 소유 agent_key 집합 (usage_daily 재계산 대상)."""
    if not _fork_pending:
        return set()
    dbid = _db_id(con)
    changed: set[str] = set()
    for k in [k for k in _fork_pending if k[0] == dbid]:
        r = M.upgrade_owner_usage(con, k[1], _fork_pending[k])
        if r is not None:
            del _fork_pending[k]
            if r:
                changed.add(r)
    return changed


def _fork_parent_file(jsonl: Path, extra: M.AgentExtra) -> Path:
    sess_dir = jsonl.parent.parent
    if extra.parent_agent_id:
        return sess_dir / "subagents" / f"agent-{extra.parent_agent_id}.jsonl"
    return sess_dir.parent / f"{sess_dir.name}.jsonl"


def _ingest_transcript(con: sqlite3.Connection, path: Path, kind: str) -> set[str]:
    # 소속 · 키
    if kind == "S2":
        key = M.key_session(path.stem)
        base = M.Agent(agent_key=key, kind="SESSION", project_key=path.parent.name, session_id=path.stem, depth=0)
        extra = None
    else:
        loc = meta_p.locate(path)
        key = M.key_agent(loc.agent_id)
        akind = "WORKFLOW_AGENT" if kind == "S5" else "SUBAGENT"
        meta_path = path.with_name(path.name[: -len(".jsonl")] + ".meta.json")
        extra = None
        if meta_path.exists():
            if tail.whole_changed(con, meta_path):
                _ingest_meta(con, meta_path, akind)
            try:
                extra = meta_p.parse(meta_path).extra()
            except ParseError:
                extra = None          # meta 오류는 _ingest_meta 가 parse_error 로 남겼다
        elif time.time() - os.stat(path).st_mtime < META_WAIT_SEC and tail.state(con, path) is None:
            return set()              # meta 가 곧 생긴다 — 다음 회차 (offset 을 옮기지 않는다)
        base = M.Agent(agent_key=key, kind=akind, project_key=loc.project_key, session_id=loc.session_id,
                       depth=(extra.spawn_depth if extra and extra.spawn_depth is not None else 1))
        if kind == "S5" and loc.wf_id:
            _ensure_workflow_node(con, loc.wf_id, loc.project_key, loc.session_id)
    ch = tail.read_new(con, path)
    if ch.unchanged and M.get_agent(con, key) is not None:
        return set()
    if ch.reset:
        con.execute("DELETE FROM parse_error WHERE path=?", (str(path),))
    M.upsert_agent(con, base)

    # 포크 사본: 부모 기록에 같은 uuid 가 있는 줄 + 부모 assistant 와 같은 requestId 인 assistant 줄 (띄운 호출의 재기록)
    parent_ids: tuple[set[str], set[str]] | None = None
    if extra is not None and extra.is_fork and ch.start_offset == 0:
        parent_ids = _ids_of(_fork_parent_file(path, extra))
    copied = 0

    pricing = _pricing()
    on_line = _on_line()
    from agentdash.core.linker import is_activity
    # 마지막 기록(last_event_at) = 모든 줄 종류의 마지막 시각 — 단 SubagentHandback 뒤 활동 아닌 꼬리 줄(그 결과 · 첨부 ·
    # 마지막 인사)은 넣지 않는다. 그래야 linker 가 기록 꼬리를 다시 읽지 않고 「last_event_at > 반환」 = 다시 깨어남 (R8, L-07).
    after_hb = False
    if ch.start_offset > 0 and not ch.reset:
        hb = con.execute("SELECT tool, at FROM tool_call WHERE agent_key=? ORDER BY at DESC LIMIT 1", (key,)).fetchone()
        le = con.execute("SELECT last_event_at FROM agent WHERE agent_key=?", (key,)).fetchone()
        after_hb = bool(hb and hb[0] == "SubagentHandback" and hb[1] and (le is None or le[0] is None or le[0] <= hb[1]))
    first_ts = last_ts = None
    cwd = branch = version = agent_name = None
    usage_n = 0
    for raw, ln in zip(ch.lines, ch.line_numbers):
        try:
            rec = tr_p.parse_line(raw, others=True)
        except tr_p.LineError as e:
            M.add_parse_error(con, path, ln, str(e))
            continue
        if rec is None:
            continue
        if rec.type == "agent-name":
            agent_name = rec.agent_name
            continue
        if parent_ids is not None and (rec.uuid in parent_ids[0]
                                       or (rec.type == "assistant" and rec.request_id in parent_ids[1])):
            copied += 1
            if rec.type == "assistant" and rec.usage is not None and rec.request_id \
                    and rec.model not in pricing.exclude:      # 사본 쪽이 더 최종일 수 있다 → 소유 행에 반영 (DEF-QA1-001)
                u = rec.usage
                cev = M.UsageEvent(agent_key="", request_id=rec.request_id, at=rec.timestamp, model=rec.model,
                                   speed=u.speed, input_tokens=u.input_tokens, cache_read=u.cache_read,
                                   cache_write_5m=u.cache_write_5m, cache_write_1h=u.cache_write_1h,
                                   output_tokens=u.output_tokens, thinking_tokens=u.thinking_tokens,
                                   web_search=u.web_search, web_fetch=u.web_fetch)
                cev.cost_usd, cev.pricing_ver = U.cost(cev, pricing)
                pk = (_db_id(con), base.session_id, rec.request_id)
                prev = _fork_pending.get(pk)
                if prev is None or (cev.output_tokens or 0) > (prev.output_tokens or 0):
                    _fork_pending[pk] = cev
            continue                # 포크 사본 — 부모 몫
        ts = rec.timestamp
        if rec.type not in tr_p.COUNTED:      # system · attachment … — 마지막 기록 시각만 (본문 · 숫자 없음)
            if not after_hb:
                last_ts = ts if last_ts is None or ts > last_ts else last_ts
            continue
        act = rec.raw is not None and is_activity(rec.raw)
        if act:
            after_hb = any(tu.name == "SubagentHandback" for tu in rec.tool_uses)
        if act or not after_hb:
            last_ts = ts if last_ts is None or ts > last_ts else last_ts
        first_ts = ts if first_ts is None or ts < first_ts else first_ts
        cwd = rec.cwd or cwd
        branch = rec.git_branch or branch
        version = rec.version or version
        if rec.type == "assistant":
            if rec.usage is not None and rec.model not in pricing.exclude:
                u = rec.usage
                ev = M.UsageEvent(agent_key=key, request_id=rec.request_id or f"uuid:{rec.uuid}", at=ts, model=rec.model,
                                  speed=u.speed, input_tokens=u.input_tokens, cache_read=u.cache_read,
                                  cache_write_5m=u.cache_write_5m, cache_write_1h=u.cache_write_1h,
                                  output_tokens=u.output_tokens, thinking_tokens=u.thinking_tokens,
                                  web_search=u.web_search, web_fetch=u.web_fetch)
                ev.cost_usd, ev.pricing_ver = U.cost(ev, pricing)
                M.add_usage(con, ev)
                usage_n += 1
            for tu in rec.tool_uses:
                M.add_tool_call(con, M.ToolCall(agent_key=key, tool_use_id=tu.id, at=ts, tool=tu.name, target=tu.target))
                if tu.file_path:
                    M.add_file_touch(con, M.FileTouch(agent_key=key, path=tu.file_path, op=tu.name, at=ts))
        else:
            for tr in rec.tool_results:
                M.set_tool_result(con, tr.tool_use_id, not tr.is_error, ts,     # is_error 없음 = 성공
                                  target=tr.run_id)                            # Workflow → runId (L-03 단서)
        if on_line is not None and rec.raw is not None:
            on_line(con, key, rec.raw)
    upd = M.Agent(agent_key=key, kind=base.kind, project_key=base.project_key, session_id=base.session_id,
                  depth=base.depth, project_path=cwd, git_branch=branch, cc_version=version,
                  started_at=first_ts, last_event_at=last_ts, extra=extra)
    M.upsert_agent(con, upd)
    if usage_n:
        top = con.execute("SELECT model FROM usage_event WHERE agent_key=? GROUP BY model ORDER BY COUNT(*) DESC, model "
                          "LIMIT 1", (key,)).fetchone()
        if top:
            con.execute("UPDATE agent SET model=? WHERE agent_key=?", (top[0], key))
    if kind == "S2":
        fallback = Path(cwd).name if cwd else path.parent.name
        cur_name = con.execute("SELECT name FROM agent WHERE agent_key=?", (key,)).fetchone()[0]
        if agent_name and (cur_name is None or cur_name == fallback):
            _set_name(con, key, agent_name, force=True)
        elif cur_name is None:
            _set_name(con, key, fallback, force=True)
    if parent_ids is not None:
        fork_copied[str(path)] = copied
    owners = _apply_fork_pending(con)   # 이 기록이 소유 행을 만들었거나, 이 기록의 사본이 소유 행을 기다린다
    tail.commit(con, ch)
    return {key} | owners


# ── 진입점 ────────────────────────────────────────────────────────────
def ingest_path(con: sqlite3.Connection, path: str | Path) -> set[str]:
    path = Path(path)
    if not path.is_file():
        return set()
    k = classify(path)
    if k is None:
        return set()
    if k == "S1":
        return _ingest_s1(con, path)
    if k == "S4":
        return _ingest_meta(con, path, "SUBAGENT")
    if k == "S5meta":
        return _ingest_meta(con, path, "WORKFLOW_AGENT")
    if k == "S6":
        return _ingest_s6(con, path)
    if k == "S5journal":
        return _ingest_journal(con, path)
    return _ingest_transcript(con, path, k)


@dataclass
class Report:
    files: dict[str, int] = field(default_factory=dict)      # 종류별 파일 수
    changed: set[str] = field(default_factory=set)
    seconds: float = 0.0


# 메타 먼저: 자식 행(spawn_tool_use)이 있어야 부모 기록의 task-notification 을 linker.on_line 이 바로 붙인다
_ORDER = {"S4": 0, "S5meta": 0, "S6": 1, "S2": 2, "S5journal": 3, "S3": 4, "S5": 4, "S1": 5}


def source_files(home: Path | None = None) -> list[tuple[str, Path]]:
    """원천 파일 목록 (종류, 경로) — 세션 → 메타 → 워크플로 → 에이전트 기록 → S1 순."""
    home = home or settings.get().claude_home
    out: list[tuple[str, Path]] = []
    roots = [home / "sessions", home / "projects"]
    for root in roots:
        if not root.is_dir():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in ("tool-results", "scripts", "memory")]
            for fn in fns:
                p = Path(dp) / fn
                k = classify(p, home)
                if k:
                    out.append((k, p))
    out.sort(key=lambda kp: (_ORDER[kp[0]], str(kp[1])))
    return out


def ingest_all(con: sqlite3.Connection, *, since: str | None = None, run_hooks: bool = True,
               link: bool = True) -> Report:
    """전체 스캔. run_hooks 면 등록된 post hook 을 부르고, link 이고 state.post_hook 이 등록돼 있지 않으면
    그것을 직접 부른다(R3 — check_counts · 감시기 재스캔 경로에서도 연결 · 판정이 돈다). backfill 은 link=False 로
    부르고 끝에 resolve_all · evaluate_all 을 따로 돈다."""
    t0 = time.time()
    rep = Report()
    since_ts = None
    if since:
        since_ts = time.mktime(time.strptime(since, "%Y-%m-%d"))
    M.ensure_indexes(con)
    for k, p in source_files():
        if since_ts is not None and os.stat(p).st_mtime < since_ts:
            continue
        rep.files[k] = rep.files.get(k, 0) + 1
        rep.changed |= ingest_path(con, p)
    rep.changed |= _apply_fork_pending(con)
    if run_hooks:
        for fn in list(_post_hooks):
            fn(con, rep.changed)
        post = _state_post_hook()
        if link and post is not None and post not in _post_hooks:
            post(con, rep.changed)
    rep.seconds = time.time() - t0
    return rep
