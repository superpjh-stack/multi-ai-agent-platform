#!/usr/bin/env python
"""V-01 check_counts — 원천 파일 수 ↔ agent 행 수 (G-04).

    uv run python src/agentdash/tools/check_counts.py [--db 경로] [--no-sync]

  · 원천은 계속 늘어나므로 **같은 시각에** 센다: 먼저 증분 수집(원천은 읽기만, DB 에만 씀)을 한 번 돌리고 곧바로 원천 파일을 센다
    (--no-sync 면 수집 없이 지금 DB 와 비교).
  · 종류별: 세션 = projects/<proj>/<sid>.jsonl · 서브에이전트 = <sid>/subagents/agent-*.jsonl (workflows 제외) ·
    워크플로 에이전트 = <sid>/subagents/workflows/wf_*/agent-*.jsonl. 워크플로 노드(workflows/wf_*.json)는 참고로 찍는다.
  · 개수만이 아니라 **키 집합**이 같은지 본다 (빠진 키 · 남는 키).
  · 원천 삭제 보관 (decisions.md D-22 · problem.md Q10 「원천이 지워져도 DB 는 집계 숫자를 남긴다」): DB 에만 있는 키 중
    그 키의 기록 경로(S2 · S3 · S5 jsonl)가 `src_file` 에 있고 그 경로가 **전부 지금 디스크에 없음**을 확인한 것만 보관으로 센다.
    경로가 기록돼 있지 않거나 하나라도 아직 있으면 「남음」 = FAIL (확인 못 한 것을 보관으로 넘기지 않는다).
판정: 빠짐 0 · 남음 0 (DB 전용 키 = 전부 원천 삭제 보관). 보관 수는 늘 따로 찍는다.
출력: `G-04  전체 수집 (<종류>)  PASS|FAIL  원천 N · DB N · 빠짐 · 남음 · 원천 삭제 보관 N …`
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


def recorded_paths(con, home: Path) -> dict[str, list[Path]]:
    """agent_key → src_file 에 기록된 그 키의 기록(jsonl) 경로들. 경로 → 키는 수집기 분류(classify)와 같은 경로 규칙."""
    out: dict[str, list[Path]] = {}
    for (path,) in con.execute("SELECT path FROM src_file"):
        p = Path(path)
        kind = ingest.classify(p, home)
        if kind == "S2":
            key = f"S:{p.stem}"
        elif kind in ("S3", "S5"):
            key = f"A:{p.name[len('agent-'):-len('.jsonl')]}"
        else:
            continue
        out.setdefault(key, []).append(p)
    return out


def split_extra(extra: set[str], recorded: dict[str, list[Path]]) -> tuple[set[str], set[str]]:
    """DB 전용 키 → (원천 삭제 보관, 확인 못 함). 보관 = 기록 경로가 있고 전부 지금 없음."""
    archived = {k for k in extra if recorded.get(k) and not any(p.exists() for p in recorded[k])}
    return archived, extra - archived


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
    recorded = recorded_paths(con, s.claude_home)
    when = datetime.now().strftime("%H:%M:%S")
    ok_all = True
    for kind, label in (("SESSION", "세션"), ("SUBAGENT", "서브에이전트"), ("WORKFLOW_AGENT", "워크플로 에이전트")):
        dbk = {r[0] for r in con.execute("SELECT agent_key FROM agent WHERE kind=?", (kind,))}
        missing, db_only = src[kind] - dbk, dbk - src[kind]
        archived, extra = split_extra(db_only, recorded)
        ok = not missing and not extra
        ok_all &= ok
        detail = (f"원천 {len(src[kind])} · DB {len(dbk)} · 빠짐 {len(missing)} · 남음 {len(extra)} · "
                  f"원천 삭제 보관 {len(archived)} ({when}{synced})")
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
