"""백필 — `make backfill [SINCE=2026-08-01]` (spec.md §1.3). 담당 개발1.

    uv run python -m agentdash.collect.backfill [--since 2026-08-01] [--db data/agentdash-dev1.db]

DB 경로는 --db > AGENTDASH_DB > config/settings.yaml. 원천(settings.claude_home)은 읽기만 한다.
수집 뒤 agentdash.core.linker.resolve_all(con) · agentdash.core.state.evaluate_all(con, now) 가 있으면 부른다 (개발2 몫).
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from datetime import datetime, timezone
from pathlib import Path

from agentdash import settings
from agentdash.collect import ingest
from agentdash.core import usage as U
from agentdash.db import conn


def _optional(module: str, func: str):
    if importlib.util.find_spec(module) is None:
        return None
    mod = importlib.import_module(module)
    return getattr(mod, func, None)


def run(db_path: str | Path | None = None, since: str | None = None, *, verbose: bool = False) -> dict:
    t0 = time.time()
    db = conn.init_db(db_path)
    con = conn.connect(db)
    try:
        rep = ingest.ingest_all(con, since=since)
        con.commit()
        post = {}
        resolve_all = _optional("agentdash.core.linker", "resolve_all")
        if resolve_all is not None:
            post["linker"] = resolve_all(con)
            con.commit()
        evaluate_all = _optional("agentdash.core.state", "evaluate_all")
        if evaluate_all is not None:
            post["state"] = evaluate_all(con, datetime.now(timezone.utc))
            con.commit()
        daily = U.rebuild_daily(con)
        con.commit()
        counts = dict(con.execute("SELECT kind, COUNT(*) FROM agent GROUP BY kind").fetchall())
        out = {
            "db": str(db), "seconds": round(time.time() - t0, 1), "ingest_seconds": round(rep.seconds, 1),
            "files": rep.files, "agents": counts,
            "usage_event": con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0],
            "tool_call": con.execute("SELECT COUNT(*) FROM tool_call").fetchone()[0],
            "file_touch": con.execute("SELECT COUNT(*) FROM file_touch").fetchone()[0],
            "parse_error": con.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0],
            "usage_daily": daily, "post": {k: (v if isinstance(v, (int, dict, str)) else str(v)) for k, v in post.items()},
            "linker": "있음" if resolve_all else "없음 (개발2 core/linker.resolve_all 대기)",
            "state": "있음" if evaluate_all else "없음 (개발2 core/state.evaluate_all 대기)",
        }
        return out
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="원천(읽기만) 전체 백필")
    ap.add_argument("--since", default=None, help="이 날짜(YYYY-MM-DD) 이전에 수정된 파일은 건너뛴다 (기본: settings backfill.since)")
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    since = a.since or settings.get().backfill_since
    out = run(a.db, since)
    print(f"backfill {out['db']} — {out['seconds']} s (수집 {out['ingest_seconds']} s, since {since})")
    print(f"  원천 파일 {sum(out['files'].values())}: " + " · ".join(f"{k} {v}" for k, v in sorted(out['files'].items())))
    print("  agent " + " · ".join(f"{k} {v}" for k, v in sorted(out["agents"].items())))
    print(f"  usage_event {out['usage_event']} · tool_call {out['tool_call']} · file_touch {out['file_touch']} · "
          f"usage_daily {out['usage_daily']} · parse_error {out['parse_error']}")
    print(f"  linker {out['linker']} · state {out['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


