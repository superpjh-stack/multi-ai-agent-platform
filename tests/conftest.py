"""가짜 루트 — 모든 테스트는 실제 원천(~/.claude · ~/Desktop/AI Coding 의 다른 폴더)을 보지 않는다 (G-14 · goal.md §0.2).

자동 (autouse)
  · `_isolate_sources` — 테스트마다 AGENTDASH_CLAUDE_HOME · AGENTDASH_AGENTS_ROOT 를 tmp 의 **빈** 가짜 루트로,
    AGENTDASH_DB 를 tmp DB 로 바꾼다. 실수로 settings 기본값을 써도 실제 ~/.claude 에 닿지 않는다.
    단 `check_readonly --runtime` 이 AGENTDASH_TEST_READONLY=1 로 부르면 그쪽이 준 읽기 전용 가짜 루트를 그대로 쓴다
    (그 루트가 임시 폴더 아래인지 확인한다).
픽스처
  · `fake_claude_home`     tests/fixtures/<ver>/ 전부를 tmp 로 복사한 가짜 ~/.claude. 읽기 전용 모드면(AGENTDASH_TEST_READONLY=1
                           또는 `@pytest.mark.readonly_source`) `chmod -R a-w` 로 닫는다. 환경변수도 이 경로로 바꾼다.
  · `fake_claude_home_ro`  항상 읽기 전용.
  · `fake_claude_home_rw`  항상 쓰기 가능 — **Claude Code 역할(새 세션 파일 쓰기 등)을 흉내 낼 때만** 쓴다. 대시보드 코드가
                           이 경로에 쓰면 안 된다는 점은 같다.
  · `fake_agents_root`     config/pipeline.yaml 의 단계 폴더(`00 PM Agent` …)를 빈 outputs/ 와 함께 만든 가짜 에이전트 루트.
  · `fixture_versions`     tests/fixtures 아래 버전 목록.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
READONLY_ENV = "AGENTDASH_TEST_READONLY"


def _real_roots() -> list[Path]:
    # 가드용 비교 대상 — 이 값으로 열거나 쓰지 않는다
    home = Path.home()
    return [(home / ".claude").resolve(), (home / "Desktop" / "AI Coding").resolve()]


def _assert_fake(p: Path) -> None:
    p = p.resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    for real in _real_roots():
        if p == real:
            raise RuntimeError(f"테스트가 실제 원천을 가리킨다: {p}")
    if tmp not in p.parents and not str(p).startswith(("/private/var/folders", "/var/folders", "/tmp", "/private/tmp")):
        raise RuntimeError(f"가짜 루트가 임시 폴더 밖: {p}")


def pytest_configure(config):
    config.addinivalue_line("markers", "readonly_source: 가짜 원천 루트를 chmod -R a-w 로 닫는다")
    if os.environ.get(READONLY_ENV) == "1":
        for var in ("AGENTDASH_CLAUDE_HOME", "AGENTDASH_AGENTS_ROOT"):
            val = os.environ.get(var)
            if not val:
                raise pytest.UsageError(f"{READONLY_ENV}=1 인데 {var} 없음")
            _assert_fake(Path(val))


def _chmod_tree(root: Path, writable: bool) -> None:
    paths = [root, *root.rglob("*")]
    if not writable:
        paths.reverse()
    for p in paths:
        m = p.stat().st_mode
        os.chmod(p, (m | stat.S_IWUSR) if writable else (m & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)))


@pytest.fixture(autouse=True)
def _isolate_sources(monkeypatch, tmp_path_factory):
    if os.environ.get(READONLY_ENV) != "1":
        base = tmp_path_factory.mktemp("isolated")
        (base / "claude_home").mkdir()
        (base / "agents_root").mkdir()
        monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(base / "claude_home"))
        monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(base / "agents_root"))
    monkeypatch.setenv("AGENTDASH_DB", str(tmp_path_factory.mktemp("db") / "test.db"))
    yield


@pytest.fixture
def fixture_versions() -> list[str]:
    return sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())


def _make_home(tmp_path: Path, readonly: bool) -> Path:
    home = tmp_path / "fake_claude_home"
    home.mkdir()
    for ver in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        shutil.copytree(ver, home, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    if readonly:
        _chmod_tree(home, writable=False)
    return home


def _readonly_mode(request) -> bool:
    return os.environ.get(READONLY_ENV) == "1" or request.node.get_closest_marker("readonly_source") is not None


@pytest.fixture
def fake_claude_home(tmp_path, monkeypatch, request):
    ro = _readonly_mode(request)
    home = _make_home(tmp_path, ro)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    yield home
    if ro:
        _chmod_tree(home, writable=True)


@pytest.fixture
def fake_claude_home_ro(tmp_path, monkeypatch):
    home = _make_home(tmp_path, True)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    yield home
    _chmod_tree(home, writable=True)


@pytest.fixture
def fake_claude_home_rw(tmp_path, monkeypatch):
    home = _make_home(tmp_path, False)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    yield home


@pytest.fixture
def fake_agents_root(tmp_path, monkeypatch, request):
    root = tmp_path / "fake_agents_root"
    root.mkdir()
    cfg = yaml.safe_load((ROOT / "config" / "pipeline.yaml").read_text(encoding="utf-8"))
    for st in cfg["stages"].values():
        (root / st["folder"] / "outputs").mkdir(parents=True)
    ro = _readonly_mode(request)
    if ro:
        _chmod_tree(root, writable=False)
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(root))
    yield root
    if ro:
        _chmod_tree(root, writable=True)
