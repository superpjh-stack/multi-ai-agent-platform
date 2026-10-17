"""안전 게이트 도구가 위반을 실제로 잡는가 (참 양성) — G-13 · G-14 · G-16."""

import sqlite3
import textwrap

from agentdash.db import conn
from agentdash.tools import check_bind, check_no_payload, check_readonly


def _write(tmp_path, name, code):
    p = tmp_path / name
    p.write_text(textwrap.dedent(code), encoding="utf-8")
    return p


def test_readonly_static_catches_writes(tmp_path):
    p = _write(tmp_path, "bad.py", """
        import os, shutil
        from agentdash import settings
        def f():
            s = settings.get()
            proj = s.claude_home / "projects"
            for p in proj.rglob("*.jsonl"):
                p.write_text("x")
            open(s.agents_root / "x", "a")
            log = proj / "a.log"
            with log.open("w") as fh:
                fh.write("x")
            shutil.rmtree(proj)
            os.remove(s.claude_home / "y")
            shutil.copy("/tmp/a", proj / "b")
    """)
    bad, _ = check_readonly.scan_file(p)
    assert len(bad) == 6, bad


def test_readonly_static_allows_reads_and_repo_writes(tmp_path):
    p = _write(tmp_path, "ok.py", """
        from pathlib import Path
        from agentdash import settings
        OUT = Path(__file__).parent / "data"
        def f():
            home = settings.get().claude_home
            for p in sorted(home.glob("projects/*/*.jsonl")):
                with p.open("r") as fh:
                    rel = p.relative_to(home)
                    (OUT / rel).write_text(fh.read())
    """)
    bad, writes = check_readonly.scan_file(p)
    assert bad == [] and writes == 1


def test_readonly_static_flags_hardcoded_source(tmp_path):
    p = _write(tmp_path, "hard.py", 'X = "~/.claude/projects"\n')
    bad, _ = check_readonly.scan_file(p)
    assert bad and "하드코딩" in bad[0]


def test_readonly_static_repo_clean():
    ok, detail, bad = check_readonly.static()
    assert ok, bad


def test_no_payload_catches_long_text(tmp_path):
    db = conn.init_db(tmp_path / "t.db")
    ok, _, _ = check_no_payload.check(db, 300)
    assert ok
    c = sqlite3.connect(db)
    c.execute("INSERT INTO hook_event VALUES ('S:x', 't', 'Stop', ?)", ("가" * 301,))
    c.commit()
    c.close()
    ok, _, bad = check_no_payload.check(db, 300)
    assert not ok and "hook_event.detail" in bad[0]


def test_no_payload_catches_body_column(tmp_path):
    db = conn.init_db(tmp_path / "t.db")
    c = sqlite3.connect(db)
    c.execute("ALTER TABLE tool_call ADD COLUMN content TEXT")
    c.commit()
    c.close()
    ok, _, bad = check_no_payload.check(db, 300)
    assert not ok and any("tool_call.content" in b for b in bad)


def test_bind_catches_external(tmp_path):
    p = _write(tmp_path, "net.py", """
        import requests
        import uvicorn
        URL = "https://example.com/api"
        uvicorn.run("x:app", host="0.0.0.0")
    """)
    ok, _, bad = check_bind.check([p])
    assert not ok and len(bad) >= 3, bad


def test_bind_repo_clean():
    ok, _, bad = check_bind.check()
    assert ok, bad
