"""S4 `agent-<id>.meta.json` · S5 워크플로 에이전트 meta (spec.md §2.1, D-10).

필드는 **저장만** 한다. 부모 연결 판단(parentAgentId 우선 · toolUseId 대조 · 워크플로 폴더)은 개발2 linker 몫.
경로에서 project_key · session_id · agent_id · wf_id 를 복원한다:
  projects/<proj>/<sessionId>/subagents/agent-<id>.meta.json
  projects/<proj>/<sessionId>/subagents/workflows/wf_<id>/agent-<id>.meta.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from agentdash.collect.parsers import ParseError

DESC_MAX = 120
_AGENT_FILE = re.compile(r"^agent-(?P<id>[^/.]+)\.(?:meta\.json|jsonl)$")


@dataclass
class Location:
    project_key: str
    session_id: str
    agent_id: str
    wf_id: str | None          # "wf_<id>" (워크플로 에이전트만)


def locate(path: str | Path) -> Location:
    """서브에이전트 · 워크플로 에이전트 파일 경로 → 소속. 형식이 다르면 ParseError."""
    p = Path(path)
    m = _AGENT_FILE.match(p.name)
    if not m:
        raise ParseError(f"에이전트 파일 이름 형식 아님: {p.name}")
    parent = p.parent
    wf_id = None
    if parent.parent.name == "workflows" and parent.name.startswith("wf_"):
        wf_id = parent.name
        subagents = parent.parent.parent
    else:
        subagents = parent
    if subagents.name != "subagents":
        raise ParseError("subagents/ 아래가 아님")
    sess_dir = subagents.parent
    return Location(project_key=sess_dir.parent.name, session_id=sess_dir.name, agent_id=m.group("id"), wf_id=wf_id)


@dataclass
class Meta:
    agent_id: str
    project_key: str
    session_id: str
    agent_type: str | None
    description: str | None
    tool_use_id: str | None
    spawn_depth: int | None
    request_shape: str | None
    request_non_interactive: bool | None
    parent_agent_id: str | None
    is_fork: bool
    model: str | None
    workflow_phase: str | None
    wf_id: str | None
    path: str

    @property
    def is_workflow_agent(self) -> bool:
        return self.wf_id is not None or self.agent_type == "workflow-subagent"

    def extra(self):
        from agentdash.core.model import AgentExtra

        return AgentExtra(agent_id=self.agent_id, tool_use_id=self.tool_use_id, parent_agent_id=self.parent_agent_id,
                          is_fork=self.is_fork, workflow_phase=self.workflow_phase, wf_id=self.wf_id,
                          spawn_depth=self.spawn_depth, meta_model=self.model,
                          jsonl_path=self.path[: -len(".meta.json")] + ".jsonl", meta_path=self.path)


def _cut(s):
    if not isinstance(s, str):
        return None
    s = " ".join(s.split())
    return s[:DESC_MAX] or None


def parse(path: str | Path) -> Meta:
    loc = locate(path)
    try:
        d = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as e:
        raise ParseError(f"meta JSON 읽기 실패: {type(e).__name__}") from None
    if not isinstance(d, dict):
        raise ParseError("meta 최상위가 객체가 아님")
    if "agentType" not in d:
        raise ParseError("meta 필수 필드 없음: agentType")
    depth = d.get("spawnDepth")
    return Meta(
        agent_id=loc.agent_id, project_key=loc.project_key, session_id=loc.session_id,
        agent_type=d.get("agentType"), description=_cut(d.get("description")), tool_use_id=d.get("toolUseId"),
        spawn_depth=int(depth) if isinstance(depth, int) else None, request_shape=d.get("requestShape"),
        request_non_interactive=d.get("requestNonInteractive"), parent_agent_id=d.get("parentAgentId"),
        is_fork=bool(d.get("isFork")), model=d.get("model"), workflow_phase=_cut(d.get("workflowPhase")),
        wf_id=loc.wf_id, path=str(path))
