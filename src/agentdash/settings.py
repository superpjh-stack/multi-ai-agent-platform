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
import unicodedata
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

    @property
    def guard_roots(self) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        """쓰기 거부 판정에 쓰는 루트 — (claude_home 류, agents_root 류).

        설정된 루트에 더해 **항상** 실제 홈의 `.claude` 와 config/settings.yaml 의 기본 agents_root 를 넣는다
        (DEF-QA1-008 — 환경변수 두 개를 함께 잘못 줘도 실제 원천 아래는 거부). 비교에만 쓴다 — 이 값으로 열지 않는다.
        """
        homes = [self.claude_home, (Path.home() / ".claude").resolve()]
        agents = [self.agents_root]
        try:
            agents.append(_path(_need(load_yaml("settings.yaml"), "sources.agents_root")).resolve())
        except SettingsError:
            pass     # get() 이 이미 같은 키를 요구했다 — 여기서 빠질 일은 없다
        return tuple(dict.fromkeys(homes)), tuple(dict.fromkeys(agents))

    def is_source_path(self, path: str | Path) -> bool:
        """원천(쓰기 금지)인가. claude_home 류 아래 전부 + agents_root 류 아래 중 이 저장소(ROOT) 밖.

        이 저장소 자체가 agents_root 아래에 있으므로(`~/Desktop/AI Coding/Multi-agent Dashboard`)
        저장소 안(data/ · outputs/ · tests/fixtures/)만 예외다. 루트는 `guard_roots` (설정값 + 실제 기본값).
        """
        homes, agents = self.guard_roots
        if any(same_or_under(path, h) for h in homes):
            return True
        return any(same_or_under(path, a) for a in agents) and not same_or_under(path, ROOT, loose=False)


# ── 경로 정체성 비교 (DEF-QA1-101) ────────────────────────────────────────────────────────────────
# 경로 문자열 모양(대소문자 · 유니코드 정규화 · 심볼릭 링크 · `..`)과 무관하게 **같은 폴더인가** 로 판정한다.
# macOS APFS(기본)는 대소문자 · NFC/NFD 를 무시하므로 `~/.CLAUDE` 와 `~/.claude` 가 같은 폴더다.
# 비교 전용 — stat 만 하고 열거나 만들지 않는다.

def _norm(part: str) -> str:
    return unicodedata.normalize("NFC", part).casefold()


def _abs_resolved(path: str | Path) -> Path:
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()          # 존재하는 부분은 심볼릭 링크를 따라가고 `..` 를 정리한다 (없는 꼬리도)


def _existing_base(p: Path) -> Path:
    """p 자신 또는 존재하는 가장 가까운 조상."""
    cur = p
    while not os.path.exists(cur) and cur != cur.parent:
        cur = cur.parent
    return cur


def _ident(p: Path) -> tuple[int, int] | None:
    try:
        st = os.stat(p)
    except OSError:
        return None
    return st.st_dev, st.st_ino


def same_or_under(path: str | Path, root: str | Path, *, loose: bool = True) -> bool:
    """path 가 root 와 같은 곳이거나 그 아래인가 — 파일 시스템 정체성 기준.

    1. 둘 다 resolve(심볼릭 링크 · `..`). root 의 존재하는 가장 가까운 조상(rb)과 그 아래 없는 꼬리(rt).
    2. path 의 존재하는 가장 가까운 조상부터 위로 올라가며 (st_dev, st_ino) 가 rb 와 같은 조상 X 를 찾고,
       X 아래 path 이름들이 rt 로 시작하면(NFC + casefold 비교) 같은 곳/아래.
    3. loose(기본) 이면 이름 비교도 더한다 — 경로 전체를 NFC + casefold 해 root 가 접두면 같은 곳으로 본다
       (없는 꼬리 · 대소문자 구분 볼륨에서는 과잉 거부 쪽 — 쓰기 거부 판정에 쓴다). 허용 예외 판정은 loose=False.
    """
    p, r = _abs_resolved(path), _abs_resolved(root)
    rn = [_norm(x) for x in r.parts]
    if loose and [_norm(x) for x in p.parts][: len(rn)] == rn:
        return True
    rb = _existing_base(r)
    rid = _ident(rb)
    if rid is None:
        return False
    rt = rn[len(rb.parts):]
    pb = _existing_base(p)
    for x in (pb, *pb.parents):
        if _ident(x) == rid:
            rest = [_norm(s) for s in p.parts[len(x.parts):]]
            if rest[: len(rt)] == rt:
                return True
    return False


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
