"""SQLite 연결 (WAL). DB 는 이 저장소의 data/ 아래에만 만든다 — 원천 루트 아래면 거부한다."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from agentdash import settings as _settings

SCHEMA = Path(__file__).with_name("schema.sql")
SIDE_SUFFIXES = ("-wal", "-shm", "-journal")


def _refuse_source(path: Path) -> None:
    """원천(읽기 전용) 아래에 DB 를 만들려는 시도는 거부한다 — G-14. 디스크에 아무것도 만들기 전에 부른다."""
    if _settings.get().is_source_path(path):
        raise RuntimeError(f"DB 경로가 원천 루트 아래: {path}")
    # 이미 있는 파일이 하드 링크면(다른 이름이 같은 inode 를 가리킴) 원천 파일의 링크일 수 있다 — 거부 (DEF-QA1-201 · G-25).
    # SQLite 가 쓰는 옆 파일(-wal · -shm · -journal)도 같다 (DEF-QA1-301)
    for f in (path, *(path.with_name(path.name + s) for s in SIDE_SUFFIXES)):
        if f.exists() and f.stat().st_nlink > 1:
            raise RuntimeError(f"DB 파일이 하드 링크 (st_nlink={f.stat().st_nlink}): {f}")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path is not None else _settings.get().db_path
    _refuse_source(p)
    con = sqlite3.connect(p, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db(path: str | Path | None = None) -> Path:
    """schema.sql 을 적용한다 (이미 있으면 그대로 둔다). 만든 DB 경로를 돌려준다."""
    p = Path(path) if path is not None else _settings.get().db_path
    _refuse_source(p)                          # 검사 먼저 — 원천 아래면 폴더도 만들지 않는다 (DEF-QA1-003)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = connect(p)
    try:
        sql = SCHEMA.read_text(encoding="utf-8").replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
        con.executescript(sql)
        _add_missing_columns(con, SCHEMA.read_text(encoding="utf-8"))
        con.commit()
    finally:
        con.close()
    return p


def schema_columns(sql: str) -> dict[str, list[tuple[str, str]]]:
    """schema.sql 의 CREATE TABLE 블록에서 표마다 (열 이름, 형) 목록을 읽는다 (PRIMARY KEY 절 제외)."""
    out: dict[str, list[tuple[str, str]]] = {}
    text = re.sub(r"--[^\n]*", "", sql)
    for m in re.finditer(r"CREATE TABLE\s+(\w+)\s*\((.*?)\);", text, re.S):
        body, depth, parts, cur = m.group(2), 0, [], ""
        for ch in body:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        parts.append(cur)
        cols = []
        for part in parts:
            toks = part.split()
            if len(toks) < 2 or toks[0].upper() in ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK"):
                continue
            cols.append((toks[0], toks[1]))
        out[m.group(1)] = cols
    return out


def _add_missing_columns(con: sqlite3.Connection, sql: str) -> list[str]:
    """기존 DB(예: spec v0.2)에 없는 열을 ALTER TABLE … ADD COLUMN 으로 덧붙인다. 덧붙인 `표.열` 목록."""
    added = []
    for table, cols in schema_columns(sql).items():
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
                added.append(f"{table}.{name}")
    return added


def tables(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


if __name__ == "__main__":
    import sys

    target = init_db(sys.argv[1] if len(sys.argv) > 1 else None)
    con = connect(target)
    names = tables(con)
    con.close()
    print(f"DB {target}: 테이블 {len(names)} — {' '.join(names)}")
