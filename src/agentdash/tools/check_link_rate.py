#!/usr/bin/env python
"""V-02 check_link_rate — 서브에이전트 부모 연결률 ≥ 95% (G-06). 담당 개발2.

    uv run python src/agentdash/tools/check_link_rate.py [--db 경로] [--no-source]

두 가지를 잰다 (원천 · DB 모두 **읽기만**)
  1. DB — `agent` 의 SUBAGENT · WORKFLOW_AGENT 행 중 `parent_key` 가 있는 비율. 가상 노드(`U:` 부모 미확인 · `X:` 외부)는
     연결로 세지 않는다. 행이 0 이면(백필 전) `미검증` — 통과한 것처럼 보이지 않게.
  2. 원천 — `settings.claude_home/projects` 를 직접 훑어 `core.linker.resolve` 로 이은 비율(같은 시각 원천 대조용) +
     L-07 반환 신호 분포(D-04: handback · task-notification).
출력: `G-06  부모 연결 (DB)  PASS|FAIL|미검증  …` · `G-06  부모 연결 (원천 직접)  PASS|FAIL  …`
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from agentdash import settings as _settings  # noqa: E402
from agentdash.core import linker as L  # noqa: E402

THRESHOLD = 0.95
KINDS = ("SUBAGENT", "WORKFLOW_AGENT")


def db_rate(db: Path) -> tuple[str, str]:
    if not db.exists():
        return "미검증", f"DB 없음 {db.name} — 백필 대기 (개발1 make backfill)"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(f"SELECT kind, parent_key FROM agent WHERE kind IN ({','.join('?' * len(KINDS))})",
                           KINDS).fetchall()
        wf = con.execute("SELECT COUNT(*), SUM(parent_key IS NOT NULL) FROM agent WHERE kind='WORKFLOW'").fetchone()
    except sqlite3.Error as e:
        return "FAIL", f"{db.name} 읽기 실패 {e}"
    finally:
        con.close()
    if not rows:
        return "미검증", f"{db.name} 서브에이전트 행 0 — 백필 대기 (개발1 make backfill)"
    ok = sum(1 for _, p in rows if p and not p.startswith(("U:", "X:")))
    n = len(rows)
    rate = ok / n
    by = Counter(k for k, _ in rows)
    st = "PASS" if rate >= THRESHOLD else "FAIL"
    return st, (f"{db.name} 서브에이전트 {by.get('SUBAGENT', 0)} · 워크플로 에이전트 {by.get('WORKFLOW_AGENT', 0)} 중 "
                f"부모 있음 {ok} = {rate:.1%} (기준 ≥ {THRESHOLD:.0%}) · 부모 미확인 {n - ok} · 워크플로 노드 "
                f"{wf[0] or 0} 중 {wf[1] or 0}")


def source_rate(home: Path) -> tuple[str, str, list[str]]:
    t0 = time.time()
    sc = L.scan_projects(home / "projects")
    rules: Counter = Counter()
    unresolved = []
    ret: Counter = Counter()
    n = ok = 0
    for a in sc.agents.values():
        if a.kind not in KINDS:
            continue
        n += 1
        lk = L.resolve(a, sc.index, sources_complete=True)
        rules[lk.rule] += 1
        if lk.resolved:
            ok += 1
        else:
            unresolved.append(f"{a.agent_key} {lk.evidence[:100]}")
        if a.kind == "SUBAGENT":
            sig = sc.signals.get(a.agent_key, [])
            r = L.returned(sig, sc.last_activity.get(a.agent_key))
            hb = sum(1 for s in sig if s.source == "handback")
            nt = sum(1 for s in sig if s.source == "notification")
            ret[("반환" if r else "미반환") + (" handback" if hb else "") + (" notification" if nt else "")] += 1
            if hb >= 2:
                ret["handback ≥ 2"] += 1
    if n == 0:
        return "미검증", "원천 서브에이전트 0", []
    rate = ok / n
    wf_nodes = [a for a in sc.agents.values() if a.kind == "WORKFLOW"]
    wf_ok = sum(1 for a in wf_nodes if L.resolve(a, sc.index).resolved)
    detail = (f"원천 서브에이전트+워크플로 에이전트 {n} 중 연결 {ok} = {rate:.1%} · "
              + " ".join(f"{k}={v}" for k, v in sorted(rules.items(), key=lambda x: str(x[0])))
              + f" · 워크플로 노드 {len(wf_nodes)} 중 {wf_ok} · 줄 {sc.lines} · {time.time() - t0:.1f}s")
    notes = [f"  반환 분포(D-04) {k}: {v}" for k, v in sorted(ret.items())] + [f"  부모 미확인 {u}" for u in unresolved[:20]]
    return ("PASS" if rate >= THRESHOLD else "FAIL"), detail, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path)
    ap.add_argument("--no-source", action="store_true")
    a = ap.parse_args()
    s = _settings.get()
    db = a.db if a.db else s.db_path
    if not db.is_absolute():
        db = ROOT / db
    st, detail = db_rate(db)
    if not a.no_source:
        sst, sdetail, notes = source_rate(s.claude_home)
        for n in notes:
            print(n)
        print(f"G-06  부모 연결 (원천 직접)  {sst}  {sdetail}")
    print(f"G-06  부모 연결 (DB)  {st}  {detail}")
    return 1 if st == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
