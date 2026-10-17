"""픽스처 — 본문 제거(G-13) · 원래 디렉터리 구조 · 가짜 루트 읽기 전용."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_fixtures_redacted():
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_fixtures_redacted.py")],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "G-13  픽스처 본문  PASS" in p.stdout


def test_checker_catches_leak(tmp_path):
    f = tmp_path / "leak.jsonl"
    f.write_text(json.dumps({"type": "user", "message": {"content": [{"type": "text", "text": "비밀 본문"}]}}) + "\n"
                 + json.dumps({"type": "x", "whatever": "가" * 121}) + "\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_fixtures_redacted.py"), str(f)],
                       capture_output=True, text=True)
    assert p.returncode == 1
    assert "본문 키 'text'" in p.stdout and "허용 밖 키 'whatever'" in p.stdout


def test_fake_home_layout(fake_claude_home):
    assert list((fake_claude_home / "sessions").glob("*.json"))
    projects = fake_claude_home / "projects"
    assert list(projects.glob("*/*.jsonl")), "S2 세션"
    assert list(projects.glob("*/*/subagents/agent-*.jsonl")), "S3 서브에이전트"
    assert list(projects.glob("*/*/subagents/agent-*.meta.json")), "S4 meta"
    assert list(projects.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl")), "S5 워크플로 에이전트"
    assert list(projects.glob("*/*/workflows/wf_*.json")), "S6 워크플로"
    depths = {json.loads(p.read_text())["spawnDepth"] for p in projects.glob("*/*/subagents/agent-*.meta.json")}
    assert {1, 2} <= depths


def test_fixture_child_links_to_parent(fake_claude_home):
    """L-01 회귀 재료가 살아 있는가 — 깊이 1 서브에이전트의 toolUseId 가 소속 세션 기록에 있다."""
    for meta in fake_claude_home.glob("projects/*/*/subagents/agent-*.meta.json"):
        m = json.loads(meta.read_text())
        if m.get("spawnDepth") != 1 or not m.get("toolUseId"):
            continue
        session = meta.parent.parent.with_suffix(".jsonl")
        assert m["toolUseId"] in session.read_text(), meta.name


def test_readonly_fake_home_blocks_writes(fake_claude_home_ro):
    with pytest.raises(PermissionError):
        (fake_claude_home_ro / "sessions" / "new.json").write_text("{}")
    target = next(fake_claude_home_ro.glob("projects/*/*.jsonl"))
    with pytest.raises(PermissionError):
        target.open("a")


def test_fake_agents_root(fake_agents_root):
    assert (fake_agents_root / "01 Analyze Agent" / "outputs").is_dir()
    assert (fake_agents_root / "08 AI Agent Making Agent").is_dir()
