"""S1 `sessions/<pid>.json` — 살아 있는 세션 (spec.md §2.1, goal.md §6)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentdash import settings
from agentdash.collect.parsers import ParseError

REQUIRED = ("pid", "sessionId", "cwd", "status", "updatedAt", "kind", "version")


@dataclass
class SessionFile:
    pid: int
    session_id: str
    cwd: str
    status: str                 # busy | idle | shell (D-09) …
    updated_at: str             # ISO UTC (원천은 epoch ms)
    status_updated_at: str | None
    started_at: str | None
    name: str | None
    kind: str
    entrypoint: str | None
    version: str
    path: str


def ms_to_iso(ms) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse(path: str | Path) -> SessionFile:
    try:
        d = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as e:
        raise ParseError(f"S1 JSON 읽기 실패: {type(e).__name__}") from None
    if not isinstance(d, dict):
        raise ParseError("S1 최상위가 객체가 아님")
    miss = [k for k in REQUIRED if k not in d]
    if miss:
        raise ParseError(f"S1 필수 필드 없음: {','.join(miss)}")
    return SessionFile(
        pid=int(d["pid"]), session_id=str(d["sessionId"]), cwd=str(d["cwd"]), status=str(d["status"]),
        updated_at=ms_to_iso(d["updatedAt"]), status_updated_at=ms_to_iso(d.get("statusUpdatedAt")),
        started_at=ms_to_iso(d.get("startedAt")), name=d.get("name"), kind=str(d["kind"]),
        entrypoint=d.get("entrypoint"), version=str(d["version"]), path=str(path))


def scan(claude_home: Path | None = None) -> dict[str, SessionFile]:
    """지금 있는 S1 전부 {sessionId: SessionFile}. 못 읽은 파일은 빼고 errors 로 돌려주지 않는다 — 그 경우 ingest 가 parse_error 를 쌓는다."""
    home = claude_home or settings.get().claude_home
    out: dict[str, SessionFile] = {}
    sess_dir = home / "sessions"
    if not sess_dir.is_dir():
        return out
    for p in sorted(sess_dir.glob("*.json")):
        try:
            sf = parse(p)
        except ParseError:
            continue
        out[sf.session_id] = sf
    return out
