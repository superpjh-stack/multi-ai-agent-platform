"""settings — 원천 경로는 환경변수로, host 는 127.0.0.1 만 (goal.md §3.1-2 · G-16)."""

from pathlib import Path

import pytest

from agentdash import settings


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(tmp_path / "a"))
    monkeypatch.setenv("AGENTDASH_DB", str(tmp_path / "x.db"))
    s = settings.get()
    assert s.claude_home == (tmp_path / "h").resolve()
    assert s.agents_root == (tmp_path / "a").resolve()
    assert s.db_path == tmp_path / "x.db"


def test_defaults_from_yaml():
    s = settings.get()
    assert (s.host, s.port, s.stale_after_sec, s.slow_after_sec) == ("127.0.0.1", 8095, 300, 90)
    assert s.text_max == 300 and s.description_max == 120


def test_tests_never_see_real_home():
    s = settings.get()
    real = (Path.home() / ".claude").resolve()
    assert s.claude_home != real
    assert not s.is_source_path(settings.ROOT / "data" / "x.db")


def test_non_loopback_host_refused(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    text = (settings.CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8").replace('"127.0.0.1"', '"0.0.0.0"', 1)
    (cfg / "settings.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg)
    with pytest.raises(settings.SettingsError):
        settings.get()


def test_missing_key_is_loud(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "settings.yaml").write_text("server: {host: '127.0.0.1', port: 8095}\n", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_DIR", cfg)
    with pytest.raises(settings.SettingsError):
        settings.get()


def test_is_source_path(fake_claude_home, fake_agents_root):
    s = settings.get()
    assert s.is_source_path(fake_claude_home / "projects")
    assert s.is_source_path(fake_agents_root / "01 Analyze Agent" / "progress.md")
