"""설정 — 환경변수 > config/settings.yaml. 원천 경로를 코드에 박지 않는다 (goal.md §3.1-2).

| 이름 | 환경변수 | yaml |
|---|---|---|
| 원천 ~/.claude          | AGENTDASH_CLAUDE_HOME | sources.claude_home |
| 원천 에이전트 폴더 루트 | AGENTDASH_AGENTS_ROOT | sources.agents_root |
| DB                      | AGENTDASH_DB          | db.path |
| 포트                    | AGENTDASH_PORT        | server.port (8095) |
| host                    | (없음 — 127.0.0.1 고정, G-16) | server.host |

`get()` 은 매번 환경변수를 다시 읽는다(테스트가 monkeypatch 로 가짜 루트를 넣을 수 있게).
설정 파일이 없거나 값이 빠지면 조용히 기본값을 쓰지 않고 SettingsError 를 낸다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # 이 저장소 루트
CONFIG_DIR = ROOT / "config"
LOOPBACK = "127.0.0.1"


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    claude_home: Path       # 원천 (읽기 전용)
    agents_root: Path       # 원천 (읽기 전용)
    db_path: Path
    host: str
    port: int
    stale_after_sec: int
    slow_after_sec: int
    backfill_since: str
    text_max: int
    description_max: int
    hook_body_max_bytes: int
    raw: dict

    @property
    def source_roots(self) -> tuple[Path, Path]:
        """쓰기 금지 루트 두 개 (check_readonly 가 쓴다)."""
        return (self.claude_home, self.agents_root)

    def is_source_path(self, path: str | Path) -> bool:
        """원천(쓰기 금지)인가. claude_home 아래 전부 + agents_root 아래 중 이 저장소(ROOT) 밖.

        이 저장소 자체가 agents_root 아래에 있으므로(`~/Desktop/AI Coding/Multi-agent Dashboard`)
        저장소 안(data/ · outputs/ · tests/fixtures/)만 예외다.
        """
        p = Path(path).expanduser().resolve()
        if _under(p, self.claude_home):
            return True
        return _under(p, self.agents_root) and not _under(p, ROOT)


def _under(p: Path, root: Path) -> bool:
    return p == root or root in p.parents


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise SettingsError(f"설정 파일 없음: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SettingsError(f"설정 파일 형식 오류: {path}")
    return data


def _need(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise SettingsError(f"config/settings.yaml 에 {dotted} 없음")
        cur = cur[part]
    return cur


def _path(value: str, *, relative_to: Path | None = None) -> Path:
    p = Path(os.path.expanduser(str(value)))
    if not p.is_absolute() and relative_to is not None:
        p = relative_to / p
    return p


def get() -> Settings:
    raw = load_yaml("settings.yaml")
    host = str(_need(raw, "server.host"))
    if host != LOOPBACK:
        raise SettingsError(f"server.host 는 {LOOPBACK} 만 허용 (지금 {host!r}) — G-16")
    port = int(os.environ.get("AGENTDASH_PORT") or _need(raw, "server.port"))
    claude_home = os.environ.get("AGENTDASH_CLAUDE_HOME") or _need(raw, "sources.claude_home")
    agents_root = os.environ.get("AGENTDASH_AGENTS_ROOT") or _need(raw, "sources.agents_root")
    db = os.environ.get("AGENTDASH_DB") or _need(raw, "db.path")
    return Settings(
        claude_home=_path(claude_home).resolve(),
        agents_root=_path(agents_root).resolve(),
        db_path=_path(db, relative_to=ROOT),
        host=host,
        port=port,
        stale_after_sec=int(_need(raw, "state.stale_after_sec")),
        slow_after_sec=int(_need(raw, "state.slow_after_sec")),
        backfill_since=str(_need(raw, "backfill.since")),
        text_max=int(_need(raw, "limits.text_max")),
        description_max=int(_need(raw, "limits.description_max")),
        hook_body_max_bytes=int(_need(raw, "limits.hook_body_max_bytes")),
        raw=raw,
    )
