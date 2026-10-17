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


# ── 웨이브 D — DEF-QA1-003 · DEF-QA1-008 ──────────────────────────────
def test_init_db_refuses_source_before_mkdir(tmp_path, monkeypatch):
    """원천 아래 DB 경로 → 예외 + 폴더를 하나도 만들지 않는다 (DEF-QA1-003). 가짜 루트는 쓰기 가능 — mkdir 이 성공할 수 있는 조건."""
    from agentdash.db import conn

    home, agents = tmp_path / "home", tmp_path / "agents"
    (agents / "Other Project").mkdir(parents=True)
    home.mkdir()
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(agents))
    for target in (home / "newdir" / "deeper" / "x.db", agents / "Other Project" / "sub" / "x.db"):
        monkeypatch.setenv("AGENTDASH_DB", str(target))
        with pytest.raises(RuntimeError):
            conn.init_db()
        with pytest.raises(RuntimeError):
            conn.init_db(target)
        with pytest.raises(RuntimeError):
            conn.connect(target)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == \
        ["agents", "agents/Other Project", "home"]


def test_is_source_path_always_guards_real_roots(tmp_path, monkeypatch):
    """설정된 루트가 가짜여도 실제 홈의 .claude 와 기본 agents_root(이 저장소 밖) 는 늘 원천 (DEF-QA1-008). 비교만 — 열지 않는다."""
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(tmp_path / "a"))
    s = settings.get()
    real_home = Path.home() / ".claude"
    default_agents = Path(settings.load_yaml("settings.yaml")["sources"]["agents_root"]).expanduser()
    assert s.is_source_path(real_home / "newdir" / "x.db")
    assert s.is_source_path(real_home)
    assert s.is_source_path(default_agents / "Other Project" / "x.db")
    assert not s.is_source_path(settings.ROOT / "data" / "x.db")        # 이 저장소 자신은 예외
    assert not s.is_source_path(settings.ROOT / "outputs" / "a.csv")
    # 가짜 루트(tmp) 는 그대로 원천, 그 밖 tmp 는 아님
    assert s.is_source_path(tmp_path / "h" / "projects")
    assert s.is_source_path(tmp_path / "a" / "01 Analyze Agent")
    assert not s.is_source_path(tmp_path / "elsewhere" / "x.db")
