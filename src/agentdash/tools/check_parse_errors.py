#!/usr/bin/env python
"""V-07 check_parse_errors — 파싱 오류율 ≤ 0.1% 줄 (G-05).

    uv run python src/agentdash/tools/check_parse_errors.py [--db 경로]

분모 = DB 가 읽은 원천(src_file)의 줄 수: jsonl 은 offset 까지의 비어 있지 않은 줄, JSON 한 덩어리 파일(S1 · S4 · S6)은 1 줄.
분자 = parse_error 행 수. src_file 이 비어 있으면(백필 안 함) FAIL — 빈 DB 를 PASS 로 속이지 않는다.
출력: `G-05  파싱 오류율  PASS|FAIL  오류 N / 줄 N = x% (상한 0.1%)`
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

LIMIT = 0.001


def lines_upto(path: str, offset: int) -> int:
    n = 0
    with open(path, "rb") as fh:
        data = fh.read(offset)
    for ln in data.split(b"\n"):
        if ln.strip():
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-05  파싱 오류율  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    con = conn.connect(db)
    total = files = gone = 0
    for path, off in con.execute("SELECT path, offset FROM src_file"):
        if not os.path.exists(path):
            gone += 1
            continue
        files += 1
        total += lines_upto(path, off) if path.endswith(".jsonl") else 1
    errs = con.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0]
    reasons = con.execute("SELECT reason, COUNT(*) FROM parse_error GROUP BY reason ORDER BY 2 DESC LIMIT 3").fetchall()
    con.close()
    if total == 0:
        print("G-05  파싱 오류율  FAIL  읽은 줄 0 — make backfill 먼저")
        return 1
    rate = errs / total
    ok = rate <= LIMIT
    why = (" · 사유 " + "; ".join(f"{r} {n}" for r, n in reasons)) if reasons else ""
    print(f"G-05  파싱 오류율  {'PASS' if ok else 'FAIL'}  오류 {errs} / 줄 {total} = {rate * 100:.4f}% "
          f"(상한 0.1%) · 파일 {files}{f' · 사라진 파일 {gone}' if gone else ''}{why}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
