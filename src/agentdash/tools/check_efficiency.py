#!/usr/bin/env python
"""V-15 check_efficiency — 캐시 적중률 표본 10 행 손계산 ↔ API (G-28, spec.md v0.3 §6 · §6.3).

    uv run python src/agentdash/tools/check_efficiency.py [--db 경로] [--n 10]

  · API 값 = `budget.efficiency(group, 기록 전체 기간)` (= `GET /api/v1/efficiency` rows), 묶음 3 (project · session · agent).
  · 표본 = 고정 시드(20261021) 무작위 n 행 — project · session 각 n//3, 나머지 agent (분모 0 행이 있으면 1 행은 반드시 넣는다).
  · 손계산은 budget 코드를 쓰지 않고 usage_event 를 그 행의 정의대로 다시 고른다: project = 에이전트 project_path 마지막 이름
    (없으면 project_key) · session = 그 세션 폴더의 모든 에이전트 · agent = 자기만. hit = cache_read ÷ (input + cache_read +
    cache_write_5m + cache_write_1h), 분모 0 → None.
판정: 표본 전부 |API − 손| ≤ 0.001 (None 은 None 끼리) · 정렬 = waste 내림차순.
출력: `G-28  캐시 적중률  PASS|FAIL  …`
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

TOL = 0.001


def _name(pp, pk):
    last = pp.rstrip("/").rsplit("/", 1)[-1] if pp else ""
    return last or pk or "(프로젝트 없음)"


def hand(con, group: str, key: str) -> float | None:
    agents = list(con.execute("SELECT agent_key, project_path, project_key, session_id FROM agent"))
    if group == "project":
        keys = [k for k, pp, pk, _s in agents if _name(pp, pk) == key]
    elif group == "session":
        sid = key[2:] if key.startswith("S:") else None
        keys = [k for k, _pp, _pk, s in agents if s == sid] if sid else [key]
    else:
        keys = [key]
    i = cr = cw = 0
    for k in keys:
        r = con.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(cache_read),0), "
                        "COALESCE(SUM(cache_write_5m),0) + COALESCE(SUM(cache_write_1h),0) FROM usage_event "
                        "WHERE agent_key=?", (k,)).fetchone()
        i, cr, cw = i + r[0], cr + r[1], cw + r[2]
    den = i + cr + cw
    return cr / den if den else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-28  캐시 적중률  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    from agentdash.core import budget as B
    from agentdash.core import usage as U

    con = conn.connect(db)
    span = con.execute("SELECT MIN(at), MAX(at) FROM usage_event WHERE at IS NOT NULL").fetchone()
    if not span[0]:
        print("G-28  캐시 적중률  FAIL  usage_event 0 — make backfill")
        return 1
    frm, to = U.kst_day(span[0]), U.kst_day(span[1])
    pool, order_bad, zero = [], 0, 0
    for g in B.EFF_GROUPS:
        rows = B.efficiency(con, g, frm, to)
        order_bad += sum(1 for x, y in zip(rows, rows[1:]) if x["waste"] < y["waste"])
        zero += sum(r["hit"] is None for r in rows)
        pool += [(g, r) for r in rows]
    rnd = random.Random(20261021)
    sample = []                     # 묶음마다 고르게 (project · session 각 n//3, 나머지 agent), 모자라면 다른 묶음에서 채운다
    quota = {"project": a.n // 3, "session": a.n // 3, "agent": a.n - 2 * (a.n // 3)}
    for g in B.EFF_GROUPS:
        part = [x for x in pool if x[0] == g]
        sample += rnd.sample(part, min(quota[g], len(part)))
    rest = [x for x in pool if x not in sample]
    sample += rnd.sample(rest, min(a.n - len(sample), len(rest)))
    zeros = [x for x in pool if x[1]["hit"] is None]
    if zeros and not any(x[1]["hit"] is None for x in sample):
        sample[-1] = zeros[0]
    bad, worst = [], 0.0
    for g, r in sample:
        h = hand(con, g, r["key"])
        if (h is None) != (r["hit"] is None):
            bad.append(f"{g}:{r['key'][:20]} API {r['hit']} · 손 {h}")
            continue
        if h is not None:
            d = abs(h - r["hit"])
            worst = max(worst, d)
            if d > TOL:
                bad.append(f"{g}:{r['key'][:20]} API {r['hit']:.4f} · 손 {h:.4f}")
    con.close()
    ok = not bad and order_bad == 0 and len(sample) >= min(a.n, len(pool)) and pool
    by = {g: sum(1 for x, _ in sample if x == g) for g in B.EFF_GROUPS}
    detail = (f"표본 {len(sample)} (" + " · ".join(f"{g} {n}" for g, n in by.items()) + f", 시드 20261021) · 최대 차 "
              f"{worst:.6f} (≤ {TOL}) · 불일치 {len(bad)} · 정렬 위반 {order_bad} · 분모 0 → — {zero} 행 · {frm}~{to}")
    if bad:
        detail += " · " + "; ".join(bad[:3])
    print(f"G-28  캐시 적중률  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
