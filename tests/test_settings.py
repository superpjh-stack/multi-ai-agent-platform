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


# ── 웨이브 D3 — DEF-QA1-101: 경로 문자열 모양이 아니라 파일 시스템 정체성으로 판정 ──────────────
import os
import unicodedata


def _case_insensitive(p: Path) -> bool:
    return os.path.exists(str(p).swapcase()) and str(p).swapcase() != str(p)


def _roots(tmp_path, monkeypatch, home_name="casehome", agents_name="에이전트루트"):
    home = tmp_path / home_name
    agents = tmp_path / unicodedata.normalize("NFC", agents_name)
    (home / "projects").mkdir(parents=True)
    (agents / "Other Project").mkdir(parents=True)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(home))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(agents))
    return settings.get(), home, agents


def test_source_path_case_variants(tmp_path, monkeypatch):
    """대소문자만 다른 경로 — 존재하는 부분은 inode, 없는 꼬리는 casefold (대소문자 구분 볼륨이어도 거부 쪽)."""
    s, home, agents = _roots(tmp_path, monkeypatch)
    for p in (tmp_path / "CASEHOME" / "newdir" / "x.db", tmp_path / "CaseHome" / "projects" / "y.db",
              tmp_path / "CASEHOME", tmp_path / "casehome" / "PROJECTS" / "z.db",
              tmp_path / "에이전트루트" / "other project" / "sub" / "x.db"):
        assert s.is_source_path(p), p
    assert not s.is_source_path(tmp_path / "casehome2" / "x.db")
    assert not s.is_source_path(tmp_path / "elsewhere" / "x.db")


def test_source_path_case_variant_of_tmp_ancestor(tmp_path, monkeypatch):
    """존재하는 조상 쪽의 대소문자가 다를 때 (대소문자 무시 볼륨에서만 같은 폴더) — inode 비교로 잡는다."""
    s, home, _ = _roots(tmp_path, monkeypatch)
    variant = Path(str(tmp_path).swapcase()) / "casehome" / "newdir" / "x.db"
    if not _case_insensitive(tmp_path):
        pytest.skip("대소문자 구분 볼륨 — 다른 폴더")
    assert s.is_source_path(variant)


def test_source_path_unicode_normalization(tmp_path, monkeypatch):
    s, home, agents = _roots(tmp_path, monkeypatch)
    nfd = Path(unicodedata.normalize("NFD", str(agents)))
    assert str(nfd) != str(agents)
    assert s.is_source_path(nfd / "Other Project" / "x.db")          # 존재하는 폴더 (APFS 는 정규화 무시)
    assert s.is_source_path(nfd / "newdir" / "x.db")                 # 없는 꼬리
    # 루트 쪽을 NFD 로 설정해도 NFC 경로를 잡는다
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(nfd))
    assert settings.get().is_source_path(agents / "Other Project" / "x.db")


def test_source_path_symlink_and_dotdot(tmp_path, monkeypatch):
    s, home, agents = _roots(tmp_path, monkeypatch)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "link").symlink_to(home)
    (tmp_path / "out" / "link_up").symlink_to(tmp_path)
    assert s.is_source_path(tmp_path / "out" / "link" / "newdir" / "x.db")
    assert s.is_source_path(tmp_path / "out" / "LINK_UP" / "CASEHOME" / "x.db")
    assert s.is_source_path(tmp_path / "out" / ".." / "casehome" / "x.db")
    assert s.is_source_path(tmp_path / "out" / ".." / "CASEHOME" / "nope" / ".." / "x.db")
    assert not s.is_source_path(tmp_path / "casehome" / ".." / "out" / "x.db")
    # 링크가 없는 대상 (dangling) 을 가리켜도 대상 쪽으로 판정
    (tmp_path / "out" / "dangling").symlink_to(home / "nothing" / "x.db")
    assert s.is_source_path(tmp_path / "out" / "dangling")


def test_source_path_repo_exception_keeps_identity(tmp_path, monkeypatch):
    """저장소 예외도 정체성 기준 — 저장소 data/ 는 원천 아님, 대소문자 변형도 원천 아님(같은 폴더)."""
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(settings.ROOT.parent))
    s = settings.get()
    assert not s.is_source_path(settings.ROOT / "data" / "x.db")
    assert s.is_source_path(settings.ROOT.parent / "Other Project" / "x.db")
    assert s.is_source_path(Path(str(settings.ROOT.parent).upper()) / "Other Project" / "x.db")


def test_real_home_case_and_nfd_variants_guarded(tmp_path, monkeypatch):
    """실제 ~/.claude 와 기본 agents_root 의 대소문자 · NFD 변형 — 판정만 (열지 않고 쓰지 않는다)."""
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(tmp_path / "a"))
    s = settings.get()
    home = Path.home()
    default_agents = Path(settings.load_yaml("settings.yaml")["sources"]["agents_root"]).expanduser()
    for p in (home / ".CLAUDE" / "newdir" / "x.db", home / ".Claude" / "projects" / "x.db",
              Path(str(default_agents).lower()) / "Other" / "x.db",
              Path(unicodedata.normalize("NFD", str(default_agents))) / "Other" / "x.db"):
        assert s.is_source_path(p), p


def test_samepath_helper(tmp_path):
    (tmp_path / "a").mkdir()
    assert settings.same_or_under(tmp_path / "a" / "b", tmp_path / "a")
    assert settings.same_or_under(tmp_path / "A", tmp_path / "a")
    assert not settings.same_or_under(tmp_path / "ab", tmp_path / "a")
    assert not settings.same_or_under(tmp_path, tmp_path / "a")


def test_hardlinked_db_refused(tmp_path):
    """G-25 · DEF-QA1-201 — 이미 있는 DB 파일이 하드 링크(st_nlink > 1)면 거부한다 (원천 파일의 링크일 수 있다)."""
    import os

    from agentdash.db import conn

    a = tmp_path / "a.db"
    a.write_bytes(b"")
    b = tmp_path / "b.db"
    os.link(a, b)
    with pytest.raises(RuntimeError, match="하드 링크"):
        conn.connect(b)
    with pytest.raises(RuntimeError, match="하드 링크"):
        conn.init_db(b)
    fresh = conn.init_db(tmp_path / "new.db")       # 링크 없는 새 경로는 통과
    c = conn.connect(fresh)
    c.close()
