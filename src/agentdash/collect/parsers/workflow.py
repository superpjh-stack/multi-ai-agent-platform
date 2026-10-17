"""S6 `workflows/wf_<id>.json` (워크플로 실행 기록) · S5 부속 `subagents/workflows/wf_<id>/journal.jsonl` (spec.md §2.1).

꺼내는 것: runId · workflowName · status · 시각 · agentCount · 합계 숫자 · 단계 제목 / journal 의 agentId → label.
`script` · `result` · `logs` · `summary` 본문과 `scripts/` 폴더는 읽지 않는다 (D-10).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from agentdash.collect.parsers import ParseError
from agentdash.collect.parsers.session_file import ms_to_iso

DESC_MAX = 120


@dataclass
class Workflow:
    run_id: str
    project_key: str
    session_id: str
    name: str | None
    status: str | None
    timestamp: str | None
    started_at: str | None
    duration_ms: int | None
    agent_count: int | None
    default_model: str | None
    total_tokens: int | None
    total_tool_calls: int | None
    phases: list[str] = field(default_factory=list)
    path: str = ""

    @property
    def ended_at(self) -> str | None:
        if self.started_at is None or self.duration_ms is None or self.status not in ("completed", "failed", "error"):
            return None
        from datetime import datetime, timedelta

        st = datetime.fromisoformat(self.started_at.replace("Z", "+00:00")) + timedelta(milliseconds=self.duration_ms)
        return st.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _cut(s):
    return s[:DESC_MAX] if isinstance(s, str) else None


def parse(path: str | Path) -> Workflow:
    p = Path(path)
    if p.parent.name != "workflows" or not p.name.startswith("wf_") or p.suffix != ".json":
        raise ParseError(f"워크플로 기록 경로 형식 아님: {p.name}")
    sess_dir = p.parent.parent
    try:
        d = json.loads(p.read_bytes())
    except (OSError, ValueError) as e:
        raise ParseError(f"워크플로 JSON 읽기 실패: {type(e).__name__}") from None
    if not isinstance(d, dict):
        raise ParseError("워크플로 최상위가 객체가 아님")
    run_id = d.get("runId") or p.stem
    if run_id != p.stem:
        raise ParseError("runId 와 파일 이름이 다름")
    phases = [_cut(x.get("title")) for x in d.get("phases") or [] if isinstance(x, dict) and x.get("title")]

    def num(k):
        v = d.get(k)
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    return Workflow(
        run_id=run_id, project_key=sess_dir.parent.name, session_id=sess_dir.name, name=_cut(d.get("workflowName")),
        status=d.get("status") if isinstance(d.get("status"), str) else None, timestamp=d.get("timestamp"),
        started_at=ms_to_iso(d.get("startTime")) if isinstance(d.get("startTime"), (int, float)) else None,
        duration_ms=num("durationMs"), agent_count=num("agentCount"), default_model=d.get("defaultModel"),
        total_tokens=num("totalTokens"), total_tool_calls=num("totalToolCalls"), phases=phases, path=str(p))


def parse_journal_line(raw: bytes) -> tuple[str, str | None, str | None] | None:
    """journal 한 줄 → (agentId, label, phase) | None. `started` 줄만 쓴다."""
    try:
        d = json.loads(raw)
    except ValueError:
        raise ParseError("journal JSON 깨짐") from None
    if not isinstance(d, dict) or "type" not in d:
        raise ParseError("journal 줄에 type 없음")
    if d.get("type") != "started" or not d.get("agentId"):
        return None
    return d["agentId"], _cut(d.get("label")), _cut(d.get("phase"))
