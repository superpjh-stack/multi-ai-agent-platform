#!/usr/bin/env python
"""V-04 check_no_payload — DB 에 본문이 없는가 (G-13 의 DB 쪽).

    uv run python src/agentdash/tools/check_no_payload.py [--db 경로]

판정
  1. 스키마에 본문 저장 열(content · text · body · prompt · command · message · thinking · payload · stdout · stderr ·
     tool_input · tool_result · raw · transcript) 이 없다.
  2. 모든 테이블의 모든 TEXT 값(typeof = 'text') 길이 ≤ 300 (config/settings.yaml limits.text_max).
  3. 테이블 수가 11 이 아니면 FAIL (빈 DB 를 PASS 로 속이지 않게 — 스키마가 있어야 검사가 뜻이 있다).
출력: `G-13  DB 본문 미저장  PASS|FAIL  실측` + 위반 목록.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402

BODY_COLS = {"content", "text", "body", "prompt", "command", "message", "messages", "thinking", "payload", "stdout",
             "stderr", "tool_input", "tool_result", "raw", "transcript", "input", "output"}
EXPECTED_TABLES = 11


def check(db: Path, text_max: int) -> tuple[bool, str, list[str]]:
    if not db.exists():
        return False, f"DB 없음 {db} — make setup", []
    uri = f"file:{db}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    bad: list[str] = []
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        rows = 0
        texts = 0
        for t in tables:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            for c in cols:
                if c.lower() in BODY_COLS:
                    bad.append(f"{t}.{c}: 본문 저장 열 이름")
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            rows += n
            for c in cols:
                cnt, mx = con.execute(
                    f'SELECT count(*), max(length("{c}")) FROM "{t}" WHERE typeof("{c}")=\'text\'').fetchone()
                texts += cnt
                if mx is not None and mx > text_max:
                    over = con.execute(
                        f'SELECT count(*) FROM "{t}" WHERE typeof("{c}")=\'text\' AND length("{c}") > ?',
                        (text_max,)).fetchone()[0]
                    bad.append(f"{t}.{c}: {over} 행이 {text_max} 자 초과 (최대 {mx})")
    finally:
        con.close()
    if len(tables) != EXPECTED_TABLES:
        bad.append(f"테이블 {len(tables)} ≠ {EXPECTED_TABLES}")
    detail = (f"{db.name} 테이블 {len(tables)} · 행 {rows} · TEXT 값 {texts} · 상한 {text_max} 자 · 위반 {len(bad)}"
              + (" (빈 DB — 백필 뒤 다시 잰다)" if rows == 0 else ""))
    return not bad, detail, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    a = ap.parse_args()
    s = _settings.get()
    db = Path(a.db) if a.db else s.db_path
    ok, detail, bad = check(db, s.text_max)
    for b in bad[:30]:
        print("  위반", b)
    print(f"G-13  DB 본문 미저장  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
