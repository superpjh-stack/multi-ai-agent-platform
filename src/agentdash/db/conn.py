"""SQLite 연결 (WAL). DB 는 이 저장소의 data/ 아래에만 만든다 — 원천 루트 아래면 거부한다."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from agentdash import settings as _settings

SCHEMA = Path(__file__).with_name("schema.sql")


def _refuse_source(path: Path) -> None:
    """원천(읽기 전용) 아래에 DB 를 만들려는 시도는 거부한다 — G-14."""
    if _settings.get().is_source_path(path):
        raise RuntimeError(f"DB 경로가 원천 루트 아래: {path}")


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
    p.parent.mkdir(parents=True, exist_ok=True)
    con = connect(p)
    try:
        sql = SCHEMA.read_text(encoding="utf-8").replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
        con.executescript(sql)
        con.commit()
    finally:
        con.close()
    return p


def tables(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


if __name__ == "__main__":
    import sys

    target = init_db(sys.argv[1] if len(sys.argv) > 1 else None)
    con = connect(target)
    names = tables(con)
    con.close()
    print(f"DB {target}: 테이블 {len(names)} — {' '.join(names)}")
