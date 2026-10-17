"""부모 연결 (spec.md §3.2 L-01~L-07) — 순수 함수. 담당 개발2.

입력은 기록에서 뽑은 **사실**(에이전트 메타 · 누가 어떤 tool_use 를 썼나 · 결과 반환 신호)이고, 출력은 `Link`
(`parent_key` · 규칙 코드 · 근거) 와 엣지다. DB · 파일을 직접 만지지 않는다 — 호출하는 쪽(개발1 파이프라인 · backfill ·
`tools/check_link_rate.py`)이 `SpawnIndex` 를 채워 넘긴다.

규칙 (decisions.md D-04 · D-10 실측 반영)
  L-01  서브에이전트 meta `toolUseId` = 소속 세션 기록의 `Agent` tool_use.id → 부모 = 세션 `S:<sessionId>`.
  L-02  세션에 없으면 같은 세션 폴더의 다른 서브에이전트 기록에서 찾는다. meta 의 `parentAgentId`(포크 · 깊이 2)가 있으면
        그것이 1순위이고 `toolUseId` 대조는 확인용(근거에 일치 여부를 남긴다). 같은 tool_use.id 가 여러 기록에 나오면
        (포크 기록은 부모 대화 사본을 품는다 — D-04 실측 26 건) 세션 > 깊이 낮은 서브에이전트 > 먼저 시작한 것.
  L-03  워크플로 에이전트(`subagents/workflows/wf_<id>/`)의 부모 = 워크플로 노드 `W:<wfId>`, 워크플로 노드의 부모 =
        `Workflow` tool_result 의 `toolUseResult.runId` 가 그 wfId 인 줄을 쓴 에이전트.
  L-04  부모 기록을 아직 다 못 읽었으면(`sources_complete=False`) `parent_key=None` · 규칙 L-04 — 다음 증분 때 다시 부른다.
  L-05  다 읽었는데도 못 찾으면 `parent_key=None` · 규칙 L-05. 구성도는 `U:<project_key>` "부모 미확인" 가상 노드에 붙인다
        (`unresolved_key`). **`parent_key` 에 가상 노드 키를 넣지 않는다** — 연결률(V-02)을 부풀리지 않게.
  L-06  `SendMessage` 의 `to` 를 agentId(실측 95/95 가 agentId) · S1 `name` · 에이전트 이름과 맞춰 `message` 엣지.
        못 맞추면 `X:<to>` "외부" 노드 + label 에 원래 이름(앞 40 자).
  L-07  자식 종료 = `SubagentHandback`(자식 기록) · `<task-notification>` 의 completed/failed/killed(부모 기록) ·
        Agent tool_result is_error 중 **가장 늦은 반환이 자식의 마지막 기록 이후**일 때. 반환 뒤에 자식 기록이 더 있으면
        (SendMessage 로 다시 깨움 — 실측 16 건이 반환 ≥ 2) 아직 안 끝났다. handback ↔ 종료 1:1 은 반박(D-04).
        · 알림은 `<tool-use-id>` = 자식 spawn tool_use 로 잇고, 못 이으면 `<task-id>` = agentId 로 잇는다 — 다시 깨운 뒤 온
          알림은 SendMessage 호출 id 를 달고 온다 (QA2 DEF-QA2-002).
        · "마지막 활동" = `is_activity` 줄(tool_use 를 낸 assistant · 들어온 메시지 user, isMeta 제외)의 마지막 시각. DB 경로는
          tool_call 과 반환 뒤 `agent.last_event_at`(ingest 가 handback 뒤 꼬리를 뺀 마지막 기록, R8)을 본다 —
          원천 기록 파일을 다시 읽지 않는다 (DEF-QA2-003, `last_activity`).
"""

from __future__ import annotations

import re as _re
from dataclasses import dataclass, field
from typing import Iterable

#: 연결 규칙 코드
L01, L02, L03, L04, L05, L06, L07 = "L-01", "L-02", "L-03", "L-04", "L-05", "L-06", "L-07"

SESSION, SUBAGENT, WORKFLOW_AGENT, WORKFLOW = "SESSION", "SUBAGENT", "WORKFLOW_AGENT", "WORKFLOW"

#: 종료로 보는 task-notification status (실측: completed 154 · failed 43 · killed 10)
END_STATUSES = {"completed": False, "failed": True, "killed": True}
LABEL_MAX = 40


def session_key(session_id: str) -> str:
    return f"S:{session_id}"


def agent_key(agent_id: str) -> str:
    return f"A:{agent_id}"


def workflow_key(wf_id: str) -> str:
    return f"W:{wf_id}"


def unresolved_key(project_key: str) -> str:
    """L-05 "부모 미확인" 가상 노드 (구성도 전용 — agent.parent_key 에는 넣지 않는다)."""
    return f"U:{project_key}"


def external_key(name: str) -> str:
    """L-06 "외부" 노드."""
    return f"X:{name[:LABEL_MAX]}"


@dataclass
class AgentRec:
    """연결에 필요한 에이전트 사실 (S4 meta · 경로에서)."""
    agent_key: str
    kind: str                         # SESSION | SUBAGENT | WORKFLOW_AGENT | WORKFLOW
    session_id: str
    project_key: str = ""
    depth: int = 0
    spawn_tool_use: str | None = None  # S4 toolUseId
    parent_agent_id: str | None = None  # S4 parentAgentId (포크, D-10)
    workflow_id: str | None = None     # 워크플로 에이전트: 폴더 wf_<id> / 워크플로 노드: 자기 id
    started_at: str | None = None
    name: str | None = None


@dataclass
class SpawnIndex:
    """기록에서 모은 '누가 무엇을 불렀나'. 호출하는 쪽이 채운다."""
    #: Agent tool_use.id → 그 tool_use 를 품은 기록의 에이전트 키 목록 (포크 사본 때문에 여럿일 수 있다)
    agent_calls: dict[str, list[str]] = field(default_factory=dict)
    #: wfId → Workflow tool_result(runId) 를 품은 에이전트 키 목록
    workflow_calls: dict[str, list[str]] = field(default_factory=dict)
    #: 에이전트 키 → 깊이 · 시작 시각 (후보 고르기용)
    depth: dict[str, int] = field(default_factory=dict)
    started: dict[str, str] = field(default_factory=dict)

    def add_agent_call(self, tool_use_id: str, author_key: str) -> None:
        lst = self.agent_calls.setdefault(tool_use_id, [])
        if author_key not in lst:
            lst.append(author_key)

    def add_workflow_call(self, wf_id: str, author_key: str) -> None:
        lst = self.workflow_calls.setdefault(wf_id, [])
        if author_key not in lst:
            lst.append(author_key)

    def add_agent(self, rec: AgentRec) -> None:
        self.depth[rec.agent_key] = rec.depth
        if rec.started_at:
            self.started[rec.agent_key] = rec.started_at


@dataclass(frozen=True)
class Link:
    parent_key: str | None
    rule: str | None                  # L-01 … L-05 (세션은 None — 부모가 없다)
    evidence: str                     # 근거 (≤ 300 자, 본문 없음)

    @property
    def resolved(self) -> bool:
        return self.parent_key is not None


def _pick(cands: list[str], index: SpawnIndex, session: str) -> str:
    """같은 tool_use 가 여러 기록에 있으면: 세션 > 깊이 낮은 것 > 먼저 시작한 것 > 키 순."""
    def rank(k: str):
        return (0 if k == session else 1, index.depth.get(k, 99), index.started.get(k) or "~", k)
    return sorted(cands, key=rank)[0]


def resolve(agent: AgentRec, index: SpawnIndex, *, sources_complete: bool = True) -> Link:
    """에이전트 하나의 부모를 정한다. `sources_complete=False` 면 못 찾았을 때 L-04(재시도), True 면 L-05."""
    sess = session_key(agent.session_id)
    if agent.kind == SESSION:
        return Link(None, None, "세션 — 부모 없음")

    if agent.kind == WORKFLOW_AGENT:
        if agent.workflow_id:
            return Link(workflow_key(agent.workflow_id), L03, f"폴더 subagents/workflows/{agent.workflow_id}/")
        return _missing(agent, sources_complete, "워크플로 폴더 id 없음")

    if agent.kind == WORKFLOW:
        wf = agent.workflow_id or agent.agent_key.removeprefix("W:")
        cands = [k for k in index.workflow_calls.get(wf, []) if k != agent.agent_key]
        if cands:
            p = _pick(cands, index, sess)
            return Link(p, L03, f"Workflow toolUseResult.runId={wf[:40]} · 기록 {p[:60]}")
        return _missing(agent, sources_complete, f"runId={wf[:40]} 를 낸 Workflow 호출 못 찾음")

    # SUBAGENT
    tu = agent.spawn_tool_use
    cands = [k for k in index.agent_calls.get(tu, []) if k != agent.agent_key] if tu else []
    if agent.parent_agent_id:
        p = agent_key(agent.parent_agent_id)
        if p in cands:
            ok = "일치"
        elif tu and cands:
            ok = f"불일치(tool_use 는 {_pick(cands, index, sess)[:30]})"
        else:
            ok = "tool_use 미확인"
        return Link(p, L02, f"meta parentAgentId={agent.parent_agent_id} · toolUseId {ok}")
    if not tu:
        return _missing(agent, sources_complete, "meta toolUseId 없음")
    if sess in cands:
        return Link(sess, L01, f"toolUseId={tu[:40]} · 세션 기록")
    subs = [k for k in cands if k.startswith("A:")]
    if subs:
        p = _pick(subs, index, sess)
        return Link(p, L02, f"toolUseId={tu[:40]} · 서브에이전트 기록 {p[:30]} (후보 {len(subs)})")
    if cands:          # 세션 · 서브에이전트가 아닌 작성자 (워크플로 에이전트 등)
        p = _pick(cands, index, sess)
        return Link(p, L02, f"toolUseId={tu[:40]} · 기록 {p[:30]}")
    return _missing(agent, sources_complete, f"toolUseId={tu[:40]} 를 품은 Agent 호출 못 찾음")


def _missing(agent: AgentRec, complete: bool, why: str) -> Link:
    if complete:
        return Link(None, L05, f"부모 미확인 → {unresolved_key(agent.project_key)[:80]} · {why}")
    return Link(None, L04, f"부모 기록 아직 안 읽힘 — 다음 증분 때 재시도 · {why}")


def retry_pending(agents: Iterable[AgentRec], links: dict[str, Link], index: SpawnIndex, *,
                  sources_complete: bool) -> dict[str, Link]:
    """L-04 재시도 — 아직 못 이은(parent_key None) 에이전트만 다시 resolve 해서 바뀐 것만 돌려준다."""
    changed: dict[str, Link] = {}
    for a in agents:
        cur = links.get(a.agent_key)
        if cur is not None and (cur.resolved or a.kind == SESSION):
            continue
        new = resolve(a, index, sources_complete=sources_complete)
        if cur is None or new != cur:
            changed[a.agent_key] = new
    return changed


# ── L-06 message 엣지 ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Edge:
    src_key: str
    dst_key: str
    kind: str                         # spawn | message | handback | workflow
    at: str | None = None
    label: str | None = None
    rule: str | None = None
    external: bool = False


def resolve_message(sender_key: str, to: str, *, agent_ids: set[str], names: dict[str, str],
                    at: str | None = None, keys: set[str] | None = None) -> Edge:
    """SendMessage `to` → message 엣지. `agent_ids` = 알려진 agentId 집합, `names` = 이름(S1 name · 에이전트 이름) → 키,
    `keys` = 알려진 에이전트 키 전체(`S:<id>` 처럼 접두가 붙은 to 를 맞춘다)."""
    raw = (to or "").strip()
    if raw in agent_ids:
        return Edge(sender_key, agent_key(raw), "message", at, None, L06)
    if raw.startswith(("A:", "S:", "W:")):
        known = set(keys or ()) | set(names.values()) | {agent_key(i) for i in agent_ids}
        if raw in known:
            return Edge(sender_key, raw, "message", at, None, L06)
    if raw in names:
        return Edge(sender_key, names[raw], "message", at, raw[:LABEL_MAX], L06)
    return Edge(sender_key, external_key(raw or "?"), "message", at, (raw or "?")[:LABEL_MAX], L06, external=True)


def spawn_edge(child_key: str, link: Link, at: str | None = None) -> Edge | None:
    if not link.resolved:
        return None
    kind = "workflow" if link.parent_key and link.parent_key.startswith("W:") else "spawn"
    return Edge(link.parent_key, child_key, kind, at, None, link.rule)


# ── L-07 결과 반환 ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReturnSignal:
    """결과 반환 신호 하나. source = handback | notification | tool_error | hook_stop."""
    at: str
    source: str
    status: str | None = None         # task-notification <status> · hook 이벤트 이름
    is_error: bool = False


@dataclass(frozen=True)
class Return:
    ended_at: str
    is_error: bool
    source: str
    count: int                        # 반환 신호 수 (handback ≥ 2 = 다시 깨운 적 있음)
    evidence: str


def returned(signals: Iterable[ReturnSignal], last_record_at: str | None) -> Return | None:
    """L-07 — 가장 늦은 종료 신호가 자식의 마지막 기록 이후(같거나 늦음)면 끝난 것. 시각은 ISO-8601 UTC 문자열.

    `<task-notification>` status 가 END_STATUSES 밖(running 등)이면 종료가 아니다.
    """
    ends = []
    for s in signals:
        if s.source == "notification":
            if s.status not in END_STATUSES:
                continue
            ends.append(ReturnSignal(s.at, s.source, s.status, s.is_error or END_STATUSES[s.status]))
        else:
            ends.append(s)
    if not ends:
        return None
    last = max(ends, key=lambda s: _norm(s.at))
    if last_record_at and _norm(last_record_at) > _norm(last.at):
        return None                    # 반환 뒤에 자식 기록이 더 있다 — 다시 깨어남
    # 같은 시각대 신호 중 오류가 하나라도 있으면 오류 (notification failed 가 handback 보다 정확)
    err = any(s.is_error for s in ends if _norm(s.at) == _norm(last.at)) or (last.source == "notification" and last.is_error)
    srcs = sorted({s.source for s in ends})
    return Return(last.at, err, last.source, len(ends),
                  f"{L07} 반환 {len(ends)} 건 ({'·'.join(srcs)}) · 마지막 {last.source}"
                  f"{'=' + last.status if last.status else ''} {last.at[:19]}")


def handback_edge(child_key: str, parent_key: str | None, ret: Return | None) -> Edge | None:
    if ret is None or parent_key is None:
        return None
    return Edge(child_key, parent_key, "handback", ret.ended_at, ret.source, L07)


def _norm(ts: str) -> str:
    """ISO 시각 비교용 — 'Z' 와 '+00:00' 을 맞추고 밀리초 자리 차이를 없앤다."""
    t = ts.replace("+00:00", "Z")
    if t.endswith("Z") and "." not in t:
        t = t[:-1] + ".000Z"
    return t


# ── 줄 하나에서 연결 사실 뽑기 (파서 · check_link_rate 가 공용으로 쓴다) ────────────────


_NOTIF = _re.compile(r"<task-notification>(.*?)</task-notification>", _re.S)
_TAG = {k: _re.compile(rf"<{k}>([^<]{{0,80}})</{k}>") for k in ("tool-use-id", "status", "task-id")}
_AGENT_MSG = _re.compile(r'<agent-message from="([^"]{1,80})"')


@dataclass(frozen=True)
class Fact:
    """기록 한 줄에서 뽑은 연결 사실. kind = agent_call | workflow_call | send_message | handback_call |
    notification | agent_error | agent_message. 본문은 담지 않는다 (id · 상태 · 시각 · 이름 앞 40 자)."""
    kind: str
    at: str | None
    key: str                          # tool_use.id · runId · to · agentId
    status: str | None = None
    is_error: bool = False
    task_id: str | None = None        # notification 의 <task-id> (서브에이전트면 agentId — 다시 깨운 뒤 알림 잇기)


def is_activity(line: dict) -> bool:
    """L-07 '다시 깨어남' 판정용 활동 줄 — tool_use 를 낸 assistant 줄 또는 들어온 메시지(문자열 · text 블록) user 줄."""
    msg = line.get("message") or {}
    c = msg.get("content") if isinstance(msg, dict) else None
    if line.get("type") == "assistant":
        return isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "tool_use" for x in c)
    if line.get("type") == "user":
        if line.get("isMeta"):
            return False
        if isinstance(c, str):
            return True
        return isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "text" for x in c)
    return False


def facts(line: dict) -> list[Fact]:
    """transcript 줄(dict) 하나 → 연결 사실 목록. `assistant` · `user` 줄만 본다(D-11: api-request-blob 은 사본)."""
    t = line.get("type")
    at = line.get("timestamp")
    msg = line.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    out: list[Fact] = []
    if t == "assistant" and isinstance(content, list):
        for c in content:
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            name, tid, inp = c.get("name"), c.get("id") or "", c.get("input") or {}
            if name == "Agent":
                out.append(Fact("agent_call", at, tid))
            elif name == "SendMessage":
                out.append(Fact("send_message", at, str(inp.get("to") or "")[:LABEL_MAX]))
            elif name == "SubagentHandback":
                out.append(Fact("handback_call", at, tid))
    elif t == "user":
        res = line.get("toolUseResult")
        if isinstance(res, dict) and isinstance(res.get("runId"), str) and res["runId"].startswith("wf_"):
            out.append(Fact("workflow_call", at, res["runId"][:80]))
        texts: list[str] = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and isinstance(c.get("text"), str):
                    texts.append(c["text"])
                elif c.get("type") == "tool_result" and c.get("is_error") is True:
                    out.append(Fact("agent_error", at, str(c.get("tool_use_id") or ""), None, True))
        for s in texts:
            if "<task-notification>" in s:
                for m in _NOTIF.finditer(s):
                    body = m.group(1)
                    tid = _TAG["tool-use-id"].search(body)
                    st = _TAG["status"].search(body)
                    task = _TAG["task-id"].search(body)
                    if tid or task:
                        status = st.group(1).strip() if st else None
                        out.append(Fact("notification", at, tid.group(1).strip() if tid else "", status,
                                        bool(status and END_STATUSES.get(status)),
                                        task.group(1).strip() if task else None))
            if "<agent-message" in s:
                for m in _AGENT_MSG.finditer(s):
                    out.append(Fact("agent_message", at, m.group(1)))
    return out


# ── 파일 트리에서 직접 모으기 (읽기만) — check_link_rate 의 DB 없는 경로 · 테스트용 ─────────────

@dataclass
class Scan:
    """projects/ 트리를 읽어 모은 것. 개발1 파이프라인이 붙으면 DB 에서 같은 것을 채운다."""
    agents: dict[str, AgentRec] = field(default_factory=dict)
    index: SpawnIndex = field(default_factory=SpawnIndex)
    signals: dict[str, list[ReturnSignal]] = field(default_factory=dict)   # 자식 키 → 반환 신호
    last_record: dict[str, str] = field(default_factory=dict)              # 에이전트 키 → 마지막 timestamp
    #: 에이전트 키 → 마지막 '활동' 시각 = tool_use 를 낸 assistant 줄 · 들어온 메시지(user 문자열/텍스트) 줄.
    #: handback 직후의 tool_result · 마지막 인사 텍스트는 활동이 아니다 (D-04 실측: 반환 뒤 194/200 이 이것뿐).
    last_activity: dict[str, str] = field(default_factory=dict)
    messages: list[tuple[str, str, str | None]] = field(default_factory=list)  # (보낸 키, to, at)
    lines: int = 0
    bad_lines: int = 0


def scan_projects(projects_dir, *, limit_sessions: int | None = None) -> Scan:
    """`<claude_home>/projects` 를 읽기 전용으로 훑는다. 본문은 꺼내지 않는다(facts 가 id · 상태만 돌려준다)."""
    import json
    from pathlib import Path

    root = Path(projects_dir)
    sc = Scan()
    session_files = sorted(root.glob("*/*.jsonl"))
    if limit_sessions is not None:
        session_files = session_files[:limit_sessions]
    files: list[tuple[str, Path]] = []
    pending: list[tuple[str, str | None, str, ReturnSignal]] = []   # (tool_use.id, task-id, 쓴 쪽, 신호)
    for sf in session_files:
        proj, sid = sf.parent.name, sf.stem
        sk = session_key(sid)
        sc.agents[sk] = AgentRec(sk, SESSION, sid, proj, 0)
        files.append((sk, sf))
        sdir = sf.with_suffix("")
        for meta in sorted(sdir.glob("subagents/agent-*.meta.json")) + sorted(
                sdir.glob("subagents/workflows/wf_*/agent-*.meta.json")):
            aid = meta.name[len("agent-"):-len(".meta.json")]
            with meta.open("r", encoding="utf-8") as fh:
                m = json.load(fh)
            wf = meta.parent.name if meta.parent.name.startswith("wf_") else None
            ak = agent_key(aid)
            rec = AgentRec(ak, WORKFLOW_AGENT if wf else SUBAGENT, sid, proj, int(m.get("spawnDepth") or 1),
                           m.get("toolUseId"), m.get("parentAgentId"), wf, None,
                           str(m.get("description") or "")[:LABEL_MAX])
            sc.agents[ak] = rec
            if wf and workflow_key(wf) not in sc.agents:
                sc.agents[workflow_key(wf)] = AgentRec(workflow_key(wf), WORKFLOW, sid, proj, 1, workflow_id=wf)
            jl = meta.with_name(f"agent-{aid}.jsonl")
            if jl.exists():
                files.append((ak, jl))
    for ak, path in files:
        with path.open("rb") as fh:
            for raw in fh:
                sc.lines += 1
                try:
                    line = json.loads(raw)
                except ValueError:
                    sc.bad_lines += 1
                    continue
                if not isinstance(line, dict):
                    continue
                ts = line.get("timestamp")
                if ts and line.get("type") in ("assistant", "user", "system"):
                    if ts > sc.last_record.get(ak, ""):
                        sc.last_record[ak] = ts
                    if ak in sc.agents and (not sc.agents[ak].started_at or ts < sc.agents[ak].started_at):
                        sc.agents[ak].started_at = ts
                    if ts and is_activity(line) and ts > sc.last_activity.get(ak, ""):
                        sc.last_activity[ak] = ts
                for f in facts(line):
                    if f.kind == "agent_call":
                        sc.index.add_agent_call(f.key, ak)
                    elif f.kind == "workflow_call":
                        sc.index.add_workflow_call(f.key, ak)
                    elif f.kind == "send_message":
                        sc.messages.append((ak, f.key, f.at))
                    elif f.kind == "handback_call" and f.at:
                        sc.signals.setdefault(ak, []).append(ReturnSignal(f.at, "handback"))
                    elif f.kind in ("notification", "agent_error") and f.at:
                        pending.append((f.key, f.task_id, ak, ReturnSignal(
                            f.at, "notification" if f.kind == "notification" else "tool_error", f.status, f.is_error)))
    for rec in sc.agents.values():
        sc.index.add_agent(rec)
    # tool_use.id 로 모은 신호를 자식 키로 옮긴다 — 못 맞추면 task-id(= agentId, 다시 깨운 뒤 알림)
    by_tu = {rec.spawn_tool_use: rec.agent_key for rec in sc.agents.values()
             if rec.spawn_tool_use and rec.kind in (SUBAGENT, WORKFLOW_AGENT)}
    for tu, task, author, sig in pending:
        child = by_tu.get(tu)
        if child is None and task and sig.source == "notification" and agent_key(task) in sc.agents:
            child = agent_key(task)
        if child is not None and child != author:
            sc.signals.setdefault(child, []).append(sig)
    return sc


# ── DB 연결 (개발1 model · ingest 가 채운 DB 에서) ──────────────────────────────────────

def _extra(con, key: str):
    from agentdash.core import model as M
    try:
        return M.load_extra(con, key)
    except (OSError, ValueError, KeyError):
        return None                    # meta 를 다시 못 읽음 — parent_agent_id 없이 toolUseId 로만 잇는다


def index_from_db(con) -> tuple[dict[str, AgentRec], SpawnIndex]:
    """agent · tool_call 테이블 → AgentRec · SpawnIndex. 포크 사본 줄은 개발1 ingest 가 이미 뺐다(progress-dev1)."""
    recs: dict[str, AgentRec] = {}
    idx = SpawnIndex()
    for r in con.execute("SELECT agent_key, kind, session_id, project_key, depth, spawn_tool_use, started_at, name "
                         "FROM agent"):
        rec = AgentRec(r[0], r[1], r[2], r[3] or "", int(r[4] or 0), r[5], None, None, r[6], r[7])
        if rec.kind in (SUBAGENT, WORKFLOW_AGENT) and (rec.depth >= 2 or rec.kind == WORKFLOW_AGENT):
            ex = _extra(con, rec.agent_key)
            if ex is not None:
                rec.parent_agent_id = ex.parent_agent_id
                rec.workflow_id = ex.wf_id
        if rec.kind == WORKFLOW:
            rec.workflow_id = rec.agent_key.removeprefix("W:")
        recs[rec.agent_key] = rec
        idx.add_agent(rec)
    for tid, author, tool, target in con.execute(
            "SELECT tool_use_id, agent_key, tool, target FROM tool_call WHERE tool IN ('Agent','Workflow')"):
        if tool == "Agent":
            idx.add_agent_call(tid, author)
        elif target and str(target).startswith("wf_"):
            idx.add_workflow_call(str(target), author)
        else:                          # runId 를 아직 안 남기는 경우: 같은 세션의 Workflow 호출자를 후보로 (§3 요청)
            idx.add_workflow_call(f"session:{recs[author].session_id if author in recs else '?'}", author)
    for src, dst in con.execute("SELECT src_key, dst_key FROM edge WHERE kind='spawn' AND dst_key LIKE 'W:%'"):
        idx.add_workflow_call(dst[2:], src)          # on_line 이 남긴 Workflow runId 근거
    # runId 없는 워크플로 노드 → 같은 세션의 Workflow 호출자가 하나뿐이면 그것
    for rec in recs.values():
        if rec.kind == WORKFLOW and rec.workflow_id not in idx.workflow_calls:
            c = idx.workflow_calls.get(f"session:{rec.session_id}", [])
            if len(c) == 1:
                idx.workflow_calls[rec.workflow_id] = list(c)
    return recs, idx


def signals_from_db(con, key: str | None = None) -> dict[str, list[ReturnSignal]]:
    """자식 키 → 반환 신호: SubagentHandback(자식 tool_call) · spawn tool_use 의 is_error · SubagentStop 훅 ·
    task-notification(`note_notification` 이 남긴 handback 엣지 label). `key` 를 주면 그 에이전트만."""
    out: dict[str, list[ReturnSignal]] = {}
    one = " AND {col}=?" if key else ""
    arg = (key,) if key else ()
    for k, at in con.execute("SELECT agent_key, at FROM tool_call WHERE tool='SubagentHandback' AND at IS NOT NULL"
                             + one.format(col="agent_key"), arg):
        out.setdefault(k, []).append(ReturnSignal(at, "handback"))
    for k, at in con.execute(
            "SELECT a.agent_key, t.result_at FROM agent a JOIN tool_call t ON t.tool_use_id = a.spawn_tool_use "
            "WHERE t.ok = 0 AND t.result_at IS NOT NULL" + one.format(col="a.agent_key"), arg):
        out.setdefault(k, []).append(ReturnSignal(at, "tool_error", None, True))
    for k, at in con.execute("SELECT agent_key, at FROM hook_event WHERE event='SubagentStop' AND agent_key LIKE 'A:%'"
                             + one.format(col="agent_key"), arg):
        out.setdefault(k, []).append(ReturnSignal(at, "hook_stop"))
    rows = con.execute("SELECT a.agent_key, e.at, e.label FROM edge e JOIN agent a ON a.agent_key = e.src_key "
                       "WHERE e.kind='handback' AND e.label LIKE 'notification:%' AND e.at IS NOT NULL"
                       + one.format(col="a.agent_key"), arg).fetchall()
    for key_, at, label in rows:
        st = label.split(":", 1)[1]
        out.setdefault(key_, []).append(ReturnSignal(at, "notification", st))
    return out


# ── L-07 마지막 활동 (DEF-QA2-003) ─────────────────────────────────────────────────────

def _activity(con, key: str, tool_last: str | None, last_event: str | None,
              signals: list[ReturnSignal]) -> str | None:
    """마지막 활동 = max(tool_call 마지막 시각, 반환 뒤 last_event_at). 원천 기록 파일은 열지 않는다 (R8).

    ingest 가 `agent.last_event_at` 에 SubagentHandback 뒤 활동 아닌 꼬리 줄(그 결과 · 첨부)을 넣지 않으므로
    `last_event_at > 가장 늦은 반환` 이면 그 뒤에 활동(들어온 메시지 · 새 tool_use)이 있었던 것 (DEF-QA2-003).
    단 그 시각이 사용량 줄(assistant 응답) 시각이면 활동으로 보지 않는다 (DEF-QA1-102 — 응답은 마지막 기록엔 넣는다)."""
    ends = [s.at for s in signals if s.source != "notification" or s.status in END_STATUSES]
    act = tool_last
    if not ends or not last_event:
        return act
    latest = max(ends, key=_norm)
    if _norm(last_event) <= _norm(latest):
        return act
    # ingest 는 handback 뒤 사용량 줄(tool_use 없는 응답)도 last_event_at 에 넣는다 (DEF-QA1-102) — 그 시각이면 활동 아님
    # (tool_use 가 있었다면 tool_last 가 이미 그 시각). 들어온 메시지 · 그 뒤 다른 줄이 마지막이면 활동.
    if con.execute("SELECT 1 FROM usage_event WHERE agent_key=? AND at=? LIMIT 1", (key, last_event)).fetchone():
        return act
    if act is None or _norm(last_event) > _norm(act):
        act = last_event
    return act


def last_activity(con, key: str) -> str | None:
    """에이전트 하나의 L-07 마지막 활동 시각 (DB tool_call + 반환 뒤 last_event_at)."""
    t = con.execute("SELECT MAX(at) FROM tool_call WHERE agent_key=?", (key,)).fetchone()
    le = con.execute("SELECT last_event_at FROM agent WHERE agent_key=?", (key,)).fetchone()
    return _activity(con, key, t[0] if t else None, le[0] if le else None, signals_from_db(con, key).get(key, []))


def return_of(con, key: str) -> Return | None:
    """에이전트 하나의 L-07 반환 (state.build_ctx 가 오류 여부 — failed/killed 알림 — 를 읽는다)."""
    ss = signals_from_db(con, key).get(key, [])
    if not ss:
        return None
    t = con.execute("SELECT MAX(at) FROM tool_call WHERE agent_key=?", (key,)).fetchone()
    le = con.execute("SELECT last_event_at FROM agent WHERE agent_key=?", (key,)).fetchone()
    return returned(ss, _activity(con, key, t[0] if t else None, le[0] if le else None, ss))


def note_notification(con, author_key: str, tool_use_id: str, status: str | None, at: str | None,
                      task_id: str | None = None) -> bool:
    """`<task-notification>` 한 건 → handback 엣지(자식 → 부모, label 'notification:<status>'). 개발1 ingest 가 부른다.

    자식 찾기: spawn_tool_use = tool_use_id, 없으면 `A:<task_id>` 서브에이전트 (다시 깨운 뒤 알림 — DEF-QA2-002).
    자식 행이 아직 없으면 False — 다음 증분 때 다시 온다(L-04 와 같은 재시도).
    엣지는 (자식, 부모) 하나 — 더 늦은 알림만 시각 · 상태를 바꾼다(늦게 읽힌 옛 알림이 새 반환을 덮지 않게).
    """
    from agentdash.core import model as M

    if not at or not (tool_use_id or task_id):
        return False
    row = con.execute("SELECT agent_key FROM agent WHERE spawn_tool_use=?", (tool_use_id,)).fetchone() \
        if tool_use_id else None
    if row is None and task_id:
        row = con.execute("SELECT agent_key FROM agent WHERE agent_key=? AND kind IN ('SUBAGENT','WORKFLOW_AGENT')",
                          (agent_key(task_id[:80]),)).fetchone()
    if row is None or row[0] == author_key:
        return False
    label = f"notification:{(status or '?')[:20]}"
    cur = con.execute("SELECT at FROM edge WHERE src_key=? AND dst_key=? AND kind='handback'",
                      (row[0], author_key)).fetchone()
    if cur is None:
        M.add_edge(con, row[0], author_key, "handback", at, label)
        return True
    if cur[0] is None or _norm(at) >= _norm(cur[0]):
        con.execute("UPDATE edge SET at=?, label=?, count=count+1 WHERE src_key=? AND dst_key=? AND kind='handback'",
                    (at, label, row[0], author_key))
    return True


def note_workflow_call(con, author_key: str, wf_id: str, at: str | None) -> bool:
    """Workflow tool_result 의 `toolUseResult.runId` → 부르는 쪽 → 워크플로 노드 spawn 엣지 (L-03 근거로 남긴다)."""
    from agentdash.core import model as M

    if not wf_id:
        return False
    wk = workflow_key(wf_id)
    if con.execute("SELECT 1 FROM edge WHERE src_key=? AND dst_key=? AND kind='spawn'", (author_key, wk)).fetchone():
        return False
    M.add_edge(con, author_key, wk, "spawn", at, "Workflow runId")
    return True


def on_line(con, author_key: str, line: dict) -> int:
    """transcript 줄(dict) 하나에서 tool_call 에 안 남는 연결 사실을 DB 에 남긴다 — task-notification(L-07) ·
    Workflow runId(L-03). 남긴 수. 개발1 ingest 가 assistant/user 줄마다 부른다 (progress-dev2 §3 R1)."""
    n = 0
    for f in facts(line):
        if f.kind == "notification" and note_notification(con, author_key, f.key, f.status, f.at, f.task_id):
            n += 1
        elif f.kind == "workflow_call" and note_workflow_call(con, author_key, f.key, f.at):
            n += 1
    return n


def resolve_all(con, *, sources_complete: bool = True) -> dict[str, Link]:
    """DB 전체 연결 — parent_key · spawn/workflow 엣지 · L-06 message 엣지 · L-07 handback 엣지 · ended_at.

    부모가 바뀐 것만 쓴다. 반환: 에이전트 키 → Link (세션 제외). 커밋하지 않는다(개발1 규약).
    """
    from agentdash.core import model as M

    recs, idx = index_from_db(con)
    links: dict[str, Link] = {}
    cur_parent = {r[0]: r[1] for r in con.execute("SELECT agent_key, parent_key FROM agent")}
    # 마지막 활동 = 마지막 tool_use 시각(handback 자신 포함) + 반환 뒤 last_event_at (`_activity`, DEF-QA2-003 · R8)
    last = {r[0]: r[1] for r in con.execute("SELECT agent_key, MAX(at) FROM tool_call GROUP BY agent_key")}
    last_event = {r[0]: r[1] for r in con.execute("SELECT agent_key, last_event_at FROM agent")}
    for rec in sorted(recs.values(), key=lambda r: r.depth):
        if rec.kind == SESSION:
            continue
        lk = resolve(rec, idx, sources_complete=sources_complete)
        links[rec.agent_key] = lk
        if lk.resolved and cur_parent.get(rec.agent_key) != lk.parent_key:
            M.set_parent(con, rec.agent_key, lk.parent_key)
        if lk.resolved:
            e = spawn_edge(rec.agent_key, lk, rec.started_at)
            if not _has_edge(con, e):
                M.add_edge(con, e.src_key, e.dst_key, e.kind, e.at)
    # L-07
    sig = signals_from_db(con)
    for key, ss in sig.items():
        rec = recs.get(key)
        if rec is None:
            continue
        ret = returned(ss, _activity(con, key, last.get(key), last_event.get(key), ss))
        ended = con.execute("SELECT ended_at FROM agent WHERE agent_key=?", (key,)).fetchone()[0]
        if ret is not None:
            if ended != ret.ended_at:
                M.set_ended(con, key, ret.ended_at)
            p = links[key].parent_key if key in links else cur_parent.get(key)
            e = handback_edge(key, p, ret)
            if e and not _has_edge(con, e):
                M.add_edge(con, e.src_key, e.dst_key, "handback", e.at, e.label)
        elif ended is not None and rec.kind == SUBAGENT:
            M.set_ended(con, key, None)    # 반환 뒤 다시 깨어남
    # L-06
    ids = {k[2:] for k in recs if k.startswith("A:")}
    names = {r.name: k for k, r in recs.items() if r.name}
    keys = set(recs)
    counts: dict[tuple[str, str], int] = {}
    for sender, to, at in con.execute("SELECT agent_key, target, at FROM tool_call WHERE tool='SendMessage'").fetchall():
        e = resolve_message(sender, to or "", agent_ids=ids, names=names, at=at, keys=keys)
        counts[(e.src_key, e.dst_key)] = counts.get((e.src_key, e.dst_key), 0) + 1
        if not _has_edge(con, e):
            M.add_edge(con, e.src_key, e.dst_key, "message", e.at, e.label)
    for (src, dst), n in counts.items():     # 굵기 = 횟수 (spec §5.2) — 다시 돌려도 늘지 않게 센 값으로 맞춘다
        con.execute("UPDATE edge SET count=? WHERE src_key=? AND dst_key=? AND kind='message'", (n, src, dst))
    return links


def _has_edge(con, e: Edge) -> bool:
    return con.execute("SELECT 1 FROM edge WHERE src_key=? AND dst_key=? AND kind=?",
                       (e.src_key, e.dst_key, e.kind)).fetchone() is not None
