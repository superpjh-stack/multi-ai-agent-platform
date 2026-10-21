"""D-24: 현재 원천에서 추정값만 보완한다. 기록값 · 보관 행 · 수집 오프셋은 유지.

    uv run python -m agentdash.collect.reestimate [--db data/agentdash.db]

원천을 메모리 DB 에 처음부터 수집하고 같은 기록값의 기존 요청만 갱신한다.
삭제된 원천의 추정값은 복원할 수 없으므로 그대로 두고 미확인 수를 보고한다.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agentdash import settings
from agentdash.collect import ingest
from agentdash.core import usage as U
from agentdash.db import conn

RECORDED = ("at", "model", "speed", "input_tokens", "cache_read", "cache_write_5m",
            "cache_write_1h", "output_tokens", "thinking_tokens", "web_search", "web_fetch")


def _backup(con: sqlite3.Connection, db: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = db.with_name(f"{db.stem}.reestimate-{stamp}.db")
    dest = conn.connect(path)
    try:
        con.backup(dest)
    finally:
        dest.close()
    return path


def run(db_path: str | Path | None = None) -> dict:
    db = Path(db_path) if db_path is not None else settings.get().db_path
    conn._refuse_source(db)  # 존재 검사 · 백업보다 먼저 원천 경로/하드 링크 거부
    if not db.is_file():
        raise FileNotFoundError(f"기존 DB 없음: {db} (make setup 먼저 실행)")
    target = conn.connect(db)
    staged = conn.connect(":memory:")
    backup = None
    try:
        staged.executescript(conn.SCHEMA.read_text(encoding="utf-8"))
        ingest.ingest_all(staged, run_hooks=False, link=False, daily=False)
        errors = staged.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0]
        if errors:
            raise RuntimeError(f"원천 재계산 파싱 오류 {errors}건 — 기존 DB 변경 없음")
        fresh = {(r["agent_key"], r["request_id"]): r
                 for r in staged.execute("SELECT * FROM usage_event")}

        # 재계산 동안 감시기가 진행했어도 최신 기록과 다시 비교한다.
        target.execute("BEGIN IMMEDIATE")
        updates, unavailable, mismatched, matched = [], 0, 0, 0
        existing = set()
        for old in target.execute("SELECT * FROM usage_event"):
            key = old["agent_key"], old["request_id"]
            existing.add(key)
            new = fresh.get(key)
            if new is None:
                unavailable += 1
                continue
            if any(old[c] != new[c] for c in RECORDED):
                mismatched += 1
                continue
            matched += 1
            est = new["output_est"]
            cost = old["cost_usd"] if est is None else new["cost_est_usd"]
            if (old["output_est"], old["cost_est_usd"]) != (est, cost):
                updates.append((est, cost, *key))

        if updates:
            # 별도 연결의 읽기 백업: 쓰기 잠금은 유지하되 backup() 대상은 트랜잭션 없는 연결.
            reader = conn.connect(db)
            try:
                backup = _backup(reader, db)
            finally:
                reader.close()
            target.executemany("UPDATE usage_event SET output_est=?, cost_est_usd=? "
                               "WHERE agent_key=? AND request_id=?", updates)
            daily = U.rebuild_daily(target)
        else:
            daily = target.execute("SELECT COUNT(*) FROM usage_daily").fetchone()[0]
        unpriced = target.execute("SELECT COUNT(*) FROM usage_event WHERE cost_usd IS NULL").fetchone()[0]
        missing_est_cost = target.execute("SELECT COUNT(*) FROM usage_event WHERE cost_est_usd IS NULL").fetchone()[0]
        target.commit()
        return {"db": str(db), "updated": len(updates), "matched": matched,
                "unavailable": unavailable, "mismatched": mismatched,
                "source_only": len(fresh.keys() - existing), "unpriced": unpriced,
                "missing_est_cost": missing_est_cost,
                "daily_rows": daily, "backup": str(backup) if backup else None}
    except BaseException:
        target.rollback()
        raise
    finally:
        staged.close()
        target.close()
        # 메모리 수집에서 생긴 길이 누적기를 다음 실행에 넘기지 않는다.
        for cache in (ingest._req_acc, ingest._fork_pending):
            for key in [k for k in cache if k[0] == ":memory:"]:
                del cache[key]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="보관 기록을 유지하면서 현재 원천의 추정값 보완")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)
    out = run(args.db)
    print(f"reestimate {out['db']} — 갱신 {out['updated']} · 기록 일치 {out['matched']} · "
          f"원천 미확인 {out['unavailable']} · 기록 불일치 {out['mismatched']} · "
          f"원천에만 있음 {out['source_only']} · 단가 없음 {out['unpriced']} · "
          f"추정 비용 미확인 {out['missing_est_cost']} · 일 집계 {out['daily_rows']}")
    print(f"  백업 {out['backup'] or '없음 (변경 없음)'}")
    if out["unavailable"] or out["mismatched"]:
        print("  원천 미확인·기록 불일치 행은 기존 값 유지. output_est NULL은 비의심 요청에도 정상.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
