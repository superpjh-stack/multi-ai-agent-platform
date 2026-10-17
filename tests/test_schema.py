"""G-01 골격 — schema.sql 테이블 11 = spec.md §3 (goal.md §2.1)."""

import re
import sqlite3
from pathlib import Path

from agentdash.db import conn

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"agent", "edge", "usage_event", "tool_call", "file_touch", "usage_daily", "state_log", "src_file",
            "parse_error", "pipeline_cell", "hook_event"}


def _tables_in(text: str) -> list[str]:
    return re.findall(r"^CREATE TABLE (\w+)", text, re.M)


def test_spec_has_11_tables():
    assert sorted(_tables_in((ROOT / "spec.md").read_text(encoding="utf-8"))) == sorted(EXPECTED)


def test_schema_sql_equals_spec_block():
    spec = (ROOT / "spec.md").read_text(encoding="utf-8")
    block = re.search(r"```sql\n(.*?)```", spec, re.S).group(1)
    assert block in conn.SCHEMA.read_text(encoding="utf-8"), "schema.sql 이 spec.md §3 과 글자 단위로 다르다"


def test_init_db_creates_11_tables_wal(tmp_path):
    db = conn.init_db(tmp_path / "t.db")
    c = sqlite3.connect(db)
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    c.close()
    assert names == EXPECTED
    assert mode == "wal"


def test_init_db_idempotent(tmp_path):
    conn.init_db(tmp_path / "t.db")
    conn.init_db(tmp_path / "t.db")


def test_db_under_source_refused(fake_claude_home):
    import pytest

    with pytest.raises(RuntimeError):
        conn.connect(fake_claude_home / "x.db")
