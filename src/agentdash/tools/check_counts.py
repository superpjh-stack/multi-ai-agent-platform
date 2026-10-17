#!/usr/bin/env python
"""V-01 check_counts — 원천 파일 수 ↔ agent 행 수 (G-04).

    uv run python src/agentdash/tools/check_counts.py [--db 경로] [--no-sync]

  · 원천은 계속 늘어나므로 **같은 시각에** 센다: 먼저 증분 수집(원천은 읽기만, DB 에만 씀)을 한 번 돌리고 곧바로 원천 파일을 센다
    (--no-sync 면 수집 없이 지금 DB 와 비교).
  · 종류별: 세션 = projects/<proj>/<sid>.jsonl · 서브에이전트 = <sid>/subagents/agent-*.jsonl (workflows 제외) ·
    워크플로 에이전트 = <sid>/subagents/workflows/wf_*/agent-*.jsonl. 워크플로 노드(workflows/wf_*.json)는 참고로 찍는다.
  · 개수만이 아니라 **키 집합**이 같은지 본다 (빠진 키 · 남는 키).
출력: `G-04  전체 수집 (<종류>)  PASS|FAIL  원천 N · DB N …`
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.collect import ingest  # noqa: E402
from agentdash.db import conn  # noqa: E402


def source_keys(home: Path) -> dict[str, set[str]]:
    out = {"SESSION": set(), "SUBAGENT": set(), "WORKFLOW_AGENT": set(), "WORKFLOW": set()}
    for kind, p in ingest.source_files(home):
        if kind == "S2":
            out["SESSION"].add(f"S:{p.stem}")
        elif kind == "S3":
            out["SUBAGENT"].add(f"A:{p.name[len('agent-'):-len('.jsonl')]}")
        elif kind == "S5":
            out["WORKFLOW_AGENT"].add(f"A:{p.name[len('agent-'):-len('.jsonl')]}")
        elif kind == "S6":
            out["WORKFLOW"].add(f"W:{p.stem}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--no-sync", action="store_true")
    a = ap.parse_args(argv)
    s = _settings.get()
    db = Path(a.db) if a.db else s.db_path
    if not db.exists():
        print(f"G-04  전체 수집  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    con = conn.connect(db)
    synced = ""
    if not a.no_sync:
        rep = ingest.ingest_all(con)
        con.commit()
        synced = f" · 직전 증분 수집 바뀐 키 {len(rep.changed)}"
    src = source_keys(s.claude_home)
    when = datetime.now().strftime("%H:%M:%S")
    ok_all = True
    for kind, label in (("SESSION", "세션"), ("SUBAGENT", "서브에이전트"), ("WORKFLOW_AGENT", "워크플로 에이전트")):
        dbk = {r[0] for r in con.execute("SELECT agent_key FROM agent WHERE kind=?", (kind,))}
        missing, extra = src[kind] - dbk, dbk - src[kind]
        ok = not missing and not extra
        ok_all &= ok
        detail = f"원천 {len(src[kind])} · DB {len(dbk)} · 빠짐 {len(missing)} · 남음 {len(extra)} ({when}{synced})"
        if missing:
            detail += " · 빠진 예 " + ",".join(sorted(missing)[:3])
        if extra:
            detail += " · 남은 예 " + ",".join(sorted(extra)[:3])
        print(f"G-04  전체 수집 ({label})  {'PASS' if ok else 'FAIL'}  {detail}")
    wf_db = {r[0] for r in con.execute("SELECT agent_key FROM agent WHERE kind='WORKFLOW'")}
    print(f"# 참고 워크플로 노드: 원천 {len(src['WORKFLOW'])} · DB {len(wf_db)}")
    con.close()
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
