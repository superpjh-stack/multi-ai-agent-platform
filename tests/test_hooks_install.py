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
    r = run("--settings", str(p), "--yes", env={**os.environ})
    assert r.returncode == 2 and "--yes" in r.stdout
    assert p.read_bytes() == original


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
