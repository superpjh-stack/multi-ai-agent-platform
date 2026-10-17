"""G-15 — 훅 설치 안전 (spec.md §9.1 · V-10). **가짜 settings.json 으로만** — 실제 ~/.claude/settings.json 은 열지 않는다.

가짜 파일은 실제 파일의 `hooks` **구조만** 본떴다 (2026-10-17 구조 확인: PostToolUse 3 · PreToolUse 1 · Stop 1 항목,
matcher 는 AskUserQuestion 패턴 · '*' · 없음). 명령 문자열은 가짜(`echo fixture-N`).
"""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "hooks_install.py"
SEND = ROOT / "scripts" / "hook_send.sh"
EVENTS = ["SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop", "Notification", "PreToolUse",
          "PostToolUse", "UserPromptSubmit"]
ASK = "(AskUserQuestion|mcp__.*__AskUserQuestion)"


def fake_settings() -> dict:
    return {
        "model": "fixture",
        "hooks": {
            "PostToolUse": [
                {"matcher": ASK, "hooks": [{"type": "command", "command": "echo fixture-1", "timeout": 10}]},
                {"matcher": ASK, "hooks": [{"type": "command", "command": "echo fixture-2", "timeout": 10}]},
                {"matcher": "*", "hooks": [{"type": "command", "command": "echo fixture-3"}]},
            ],
            "PreToolUse": [{"matcher": ASK, "hooks": [{"type": "command", "command": "echo fixture-4", "timeout": 5}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "echo fixture-5 한글"}]}],
        },
        "theme": "dark",
        "enabledPlugins": {"x@y": True},
    }


@pytest.fixture
def target(tmp_path) -> Path:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(fake_settings(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def run(*args, stdin="", env=None):
    return subprocess.run([sys.executable, str(INSTALL), *args], capture_output=True, text=True, input=stdin,
                          timeout=60, env=env)


def marked(e) -> bool:
    return "hook_send.sh" in json.dumps(e)


def test_install_keeps_existing_and_adds_nine(target):
    original = target.read_bytes()
    before = json.loads(original)["hooks"]
    r = run("--settings", str(target), "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "+" in r.stdout and "백업" in r.stdout                       # diff · 백업 표시
    after = json.loads(target.read_text(encoding="utf-8"))
    for ev, entries in before.items():                                   # 기존 항목 바이트(JSON) 동일 · 순서 그대로
        assert json.dumps(after["hooks"][ev][: len(entries)], ensure_ascii=False) == \
            json.dumps(entries, ensure_ascii=False)
    added = [(ev, e) for ev in EVENTS for e in after["hooks"].get(ev, []) if marked(e)]
    assert len(added) == 9 and sorted(ev for ev, _ in added) == sorted(EVENTS)
    assert all("matcher" not in e for _, e in added)                     # 전체(매처 없음)
    assert {k: v for k, v in after.items() if k != "hooks"} == {k: v for k, v in fake_settings().items() if k != "hooks"}
    baks = list(target.parent.glob("settings.json.bak-agentdash-*"))
    assert len(baks) == 1 and baks[0].read_bytes() == original
    # 다시 돌려도 9 개 그대로
    r = run("--settings", str(target), "--yes")
    assert r.returncode == 0 and "이미 설치됨" in r.stdout
    again = json.loads(target.read_text(encoding="utf-8"))
    assert sum(1 for ev in EVENTS for e in again["hooks"].get(ev, []) if marked(e)) == 9


def test_uninstall_restores_bytes(target):
    original = target.read_bytes()
    assert run("--settings", str(target), "--yes").returncode == 0
    assert target.read_bytes() != original
    r = run("--settings", str(target), "--uninstall", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.read_bytes() == original


def test_uninstall_without_backup_removes_only_marked(target):
    assert run("--settings", str(target), "--yes").returncode == 0
    for b in target.parent.glob("settings.json.bak-agentdash-*"):
        b.unlink()
    data = json.loads(target.read_text(encoding="utf-8"))
    data["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "echo later"}]})   # 사람이 나중에 더한 것
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert run("--settings", str(target), "--uninstall", "--yes").returncode == 0
    got = json.loads(target.read_text(encoding="utf-8"))
    want = fake_settings()
    want["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "echo later"}]})
    assert got == want


def test_confirm_no_keeps_file(target):
    original = target.read_bytes()
    r = run("--settings", str(target), stdin="n\n")
    assert r.returncode == 1 and "취소" in r.stdout
    assert target.read_bytes() == original
    assert not list(target.parent.glob("settings.json.bak-agentdash-*"))


def test_confirm_yes_typed(target):
    r = run("--settings", str(target), stdin="y\n")
    assert r.returncode == 0
    assert sum(1 for ev in EVENTS for e in json.loads(target.read_text())["hooks"].get(ev, []) if marked(e)) == 9


def _load_module():
    spec = importlib.util.spec_from_file_location("hooks_install_mod", INSTALL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bad_json_after_write_rolls_back(target, monkeypatch, capsys):
    original = target.read_bytes()
    mod = _load_module()
    monkeypatch.setattr(mod, "dump", lambda data, indent: '{"hooks": [broken\n')
    assert mod.install(target, yes=True) == 1
    assert "되돌림" in capsys.readouterr().out
    assert target.read_bytes() == original


def test_yes_refused_on_claude_home_settings(tmp_path, monkeypatch):
    """settings.claude_home 의 settings.json 에는 --yes 금지 (가짜 claude_home 으로 확인)."""
    home = tmp_path / "home"
    home.mkdir()
    p = home / "settings.json"
    p.write_text(json.dumps(fake_settings(), indent=2) + "\n", encoding="utf-8")
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    original = p.read_bytes()
    import os
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}   # --yes 가드 자체를 본다
    r = run("--settings", str(p), "--yes", env=env)
    assert r.returncode == 2 and "--yes" in r.stdout
    assert p.read_bytes() == original
    r = run("--settings", str(p), "--yes", env={**os.environ})                     # pytest 중 — 무조건 거부
    assert r.returncode == 2 and "테스트 중" in r.stdout
    assert p.read_bytes() == original and not list(home.glob("*.bak-agentdash-*"))


def test_check_reports(target):
    run("--settings", str(target), "--yes")
    r = run("--settings", str(target), "--check")
    assert r.returncode == 0 and "설치: 9/9" in r.stdout and "다른 훅 항목: 5" in r.stdout


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_send_server_down_exit0_fast_silent():
    import os
    env = {**os.environ, "AGENTDASH_PORT": str(_free_port())}
    payload = json.dumps({"hook_event_name": "Stop", "session_id": "fixture", "prompt": "x" * 5000}).encode()
    t0 = time.time()
    q = subprocess.run(["bash", str(SEND)], input=payload, capture_output=True, timeout=10, env=env)
    dt = time.time() - t0
    assert q.returncode == 0 and q.stdout == b"" and q.stderr == b"" and dt <= 1.0, dt


def test_send_unreachable_host_still_within_1s():
    """듣기만 하고 응답하지 않는 서버 — curl -m 1 로 1 초 안에 끝난다."""
    import os
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        env = {**os.environ, "AGENTDASH_PORT": str(port)}
        t0 = time.time()
        q = subprocess.run(["bash", str(SEND)], input=b'{"hook_event_name":"Stop"}', capture_output=True, timeout=10,
                           env=env)
        dt = time.time() - t0
    finally:
        s.close()
    assert q.returncode == 0 and q.stdout == b"" and dt <= 1.3, dt


# ---- 웨이브 D — DEF-QA1-004 · DEF-QA1-005 ----------------------------------------------------------------------
# 실제 ~/.claude/settings.json 은 **비교 · 읽기(stat · sha)만** 한다. 쓰기 경로는 전부 함정(trap)으로 막아
# 가드가 틀려도 쓰지 못하게 하고, 함정이 한 번이라도 불리면 실패한다.
import hashlib  # noqa: E402
import os  # noqa: E402
import shlex  # noqa: E402

REAL_SETTINGS = Path.home() / ".claude" / "settings.json"          # 비교 대상 — 열어서 쓰지 않는다


def _snap(p: Path):
    if not p.exists():
        return None
    return p.stat().st_mtime_ns, hashlib.sha1(p.read_bytes()).hexdigest()


@pytest.fixture
def trapped(monkeypatch):
    mod = _load_module()
    calls: list[str] = []

    def trap(name):
        def f(*a, **k):
            calls.append(name)
            raise AssertionError(f"쓰기 · 확인 시도: {name}")
        return f

    for n in ("install", "uninstall", "atomic_write", "restore"):
        monkeypatch.setattr(mod, n, trap(n))
    monkeypatch.setattr("builtins.input", trap("input"))
    monkeypatch.setattr(Path, "write_bytes", trap("Path.write_bytes"))
    monkeypatch.setattr(Path, "write_text", trap("Path.write_text"))
    monkeypatch.setattr(os, "replace", trap("os.replace"))
    return mod, calls


def _assert_fake_home_on():
    assert os.environ["AGENTDASH_CLAUDE_HOME"] and \
        Path(os.environ["AGENTDASH_CLAUDE_HOME"]).resolve() != (Path.home() / ".claude").resolve()
    assert os.environ.get("PYTEST_CURRENT_TEST")


@pytest.mark.parametrize("arg", [str(REAL_SETTINGS), "~/.claude/settings.json"])
def test_real_home_settings_refused_with_fake_home_yes(trapped, arg, capsys):
    """DEF-QA1-004 — conftest 의 가짜 home 이 켜져 있어도 실제 홈의 settings.json 에 --yes 는 거부."""
    mod, calls = trapped
    _assert_fake_home_on()
    before = _snap(REAL_SETTINGS)
    assert mod.is_real_target(Path(arg).expanduser()) is True
    assert mod.main(["--settings", arg, "--yes"]) == 2
    assert mod.main(["--settings", arg, "--uninstall", "--yes"]) == 2
    assert calls == []
    assert _snap(REAL_SETTINGS) == before
    assert "거부" in capsys.readouterr().out


def test_real_home_settings_refused_in_pytest_without_prompt(trapped):
    """pytest 중이면 --yes 없이도 확인 프롬프트를 띄우지 않고 거부."""
    mod, calls = trapped
    _assert_fake_home_on()
    before = _snap(REAL_SETTINGS)
    assert mod.main(["--settings", str(REAL_SETTINGS)]) == 2
    assert mod.main(["--settings", str(REAL_SETTINGS), "--uninstall"]) == 2
    assert calls == []                                   # input() 도 불리지 않음
    assert _snap(REAL_SETTINGS) == before


def test_real_home_settings_via_symlink_refused(trapped, tmp_path):
    """심볼릭 링크(파일 · 상위 폴더)로 실제 경로를 가리켜도 거부 (resolve 후 비교)."""
    mod, calls = trapped
    link = tmp_path / "link-settings.json"
    os.symlink(REAL_SETTINGS, link)                      # tmp 안에 링크만 만든다 (원천 무변경)
    dlink = tmp_path / "home-link"
    os.symlink(REAL_SETTINGS.parent, dlink)
    before = _snap(REAL_SETTINGS)
    for p in (link, dlink / "settings.json"):
        assert mod.is_real_target(p) is True
        assert mod.main(["--settings", str(p), "--yes"]) == 2
    assert calls == []
    assert _snap(REAL_SETTINGS) == before


def test_configured_claude_home_settings_refused_in_pytest(trapped):
    """설정된(가짜) claude_home 의 settings.json 도 실제 파일로 본다 — pytest 중 무조건 거부."""
    mod, calls = trapped
    p = Path(os.environ["AGENTDASH_CLAUDE_HOME"]) / "settings.json"
    assert mod.is_real_target(p) is True
    assert mod.main(["--settings", str(p), "--yes"]) == 2
    assert mod.main(["--settings", str(p)]) == 2
    assert calls == []


def test_other_tmp_file_is_not_real(tmp_path):
    mod = _load_module()
    assert mod.is_real_target(tmp_path / "settings.json") is False


OTHER = {"hooks": [{"type": "command", "command": "bash /other/project/hook_send.sh"}]}


def _mine() -> str:
    return f"bash {shlex.quote(str(SEND))}"


def _count_mine(data: dict) -> int:
    return sum(1 for ev in EVENTS for e in data.get("hooks", {}).get(ev, []) for h in e.get("hooks", [])
               if h.get("command") == _mine())


def test_other_projects_hook_send_is_not_mine(tmp_path):
    """DEF-QA1-005 — 남의 `…/hook_send.sh` 는 내 것이 아니다: 설치 9 · 제거 후 남의 항목 남음 · 원본 바이트 동일."""
    data = fake_settings()
    data["hooks"]["Stop"].append(OTHER)
    data["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": "/x/agentdash/scripts/hook_send.sh"}]}]
    t = tmp_path / "settings.json"
    t.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    original = t.read_bytes()
    r = run("--settings", str(t), "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    after = json.loads(t.read_text(encoding="utf-8"))
    assert _count_mine(after) == 9
    assert after["hooks"]["Stop"][: len(data["hooks"]["Stop"])] == data["hooks"]["Stop"]
    assert run("--settings", str(t), "--check").stdout.count("설치: 9/9") == 1
    r = run("--settings", str(t), "--uninstall", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert t.read_bytes() == original
    # 백업 없이 제거해도 남의 항목은 남는다
    assert run("--settings", str(t), "--yes").returncode == 0
    for b in t.parent.glob("settings.json.bak-agentdash-*"):
        b.unlink()
    assert run("--settings", str(t), "--uninstall", "--yes").returncode == 0
    assert json.loads(t.read_text(encoding="utf-8")) == data


def test_only_others_hook_send_counts_as_not_installed(tmp_path):
    data = {"hooks": {ev: [OTHER] for ev in EVENTS}}
    t = tmp_path / "settings.json"
    t.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    r = run("--settings", str(t), "--check")
    assert "설치: 0/9" in r.stdout
    r = run("--settings", str(t), "--uninstall", "--yes")
    assert r.returncode == 0 and "없음" in r.stdout
    assert json.loads(t.read_text()) == data
