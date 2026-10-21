#!/usr/bin/env python
"""V-13 check_budget — 예산 칸 기준 금액 ↔ usage_event 직접 합 (G-26, spec.md v0.3 §6.3).

    uv run python src/agentdash/tools/check_budget.py [--db 경로]

  · 칸 = `budget.status()` (= `GET /api/v1/budget` rows) — 실제 config/budget.yaml 그대로. 한도가 비어 있어도(unset) 금액은 잰다.
  · 프로젝트 칸은 budget.yaml 에 적힌 것만 나오므로, **기록에 있는 모든 프로젝트**를 한도 없는 칸으로 더해(`cfg` 인자 — 금액 없음)
    같은 대조를 한다. 설정 파일은 바꾸지 않는다.
  · 직접 합은 budget 코드를 쓰지 않고 따로 센다: usage_event 를 모두 읽어 각 행의 시각을 KST 로 바꾼 일자 · 달이 지금과 같고
    시각 ≤ 지금인 행의 cost_est_usd (NULL 제외) · cost_usd 합, NULL 건수. 프로젝트 = agent.project_path 마지막 이름(없으면 project_key).
판정: 모든 칸 |기준 − 직접| ≤ $0.01 · |기록 − 직접| ≤ $0.01 · 단가 없음 건수 같음.
출력: `G-26  예산  PASS|FAIL  칸 N · 최대 차 $x · …`
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

TOL = 0.01
KST = timezone(timedelta(hours=9))


def direct(con, now: datetime) -> dict[tuple[str, str | None, str], list]:
    """(scope, project, period) → [est 합, 기록 합, NULL 건수] — budget 모듈을 쓰지 않는 직접 합."""
    names = {}
    for k, pp, pk in con.execute("SELECT agent_key, project_path, project_key FROM agent"):
        n = pp.rstrip("/").rsplit("/", 1)[-1] if pp and pp.rstrip("/").rsplit("/", 1)[-1] else (pk or "(프로젝트 없음)")
        names[k] = n
    nk = now.astimezone(KST)
    out: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, 0])
    for k, at, c, ce in con.execute("SELECT agent_key, at, cost_usd, cost_est_usd FROM usage_event"):
        if not at:
            continue
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if t > now:
            continue
        tk = t.astimezone(KST)
        periods = []
        if (tk.year, tk.month) == (nk.year, nk.month):
            periods.append("month")
            if tk.day == nk.day:
                periods.append("day")
        for per in periods:
            for key in (("total", None, per), ("project", names.get(k), per)):
                v = out[key]
                if ce is None:
                    v[2] += 1
                else:
                    v[0] += ce
                if c is not None:
                    v[1] += c
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-26  예산  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    from agentdash.core import budget as B

    con = conn.connect(db)
    now = datetime.now(timezone.utc)
    cfg = B.load()
    rows = B.status(con, now)                                   # 실제 설정 그대로 (= API)
    projects = sorted({B.project_name(r[0], r[1]) for r in con.execute("SELECT project_path, project_key FROM agent")})
    all_cfg = {**cfg, "projects": {**{p: {"daily_usd": None, "monthly_usd": None} for p in projects}, **cfg["projects"]}}
    rows_all = B.status(con, now, cfg=all_cfg)
    want = direct(con, now)
    con.close()
    worst_d, bad = 0.0, []
    seen = set()
    for r in rows + rows_all:
        key = (r["scope"], r["project"], r["period"])
        if key in seen:
            continue
        seen.add(key)
        w = want.get(key, [0.0, 0.0, 0])
        d = max(abs(r["est_usd"] - w[0]), abs(r["rec_usd"] - w[1]))
        worst_d = max(worst_d, d)
        if d > TOL or r["unpriced"] != w[2]:
            bad.append(f"{key[1] or '전체'}/{key[2]} 차 ${d:.4f} · 단가 없음 {r['unpriced']}/{w[2]}")
    levels = defaultdict(int)
    for r in rows:
        levels[r["level"]] += 1
    tot_day = next(r for r in rows if r["scope"] == "total" and r["period"] == "day")
    tot_mon = next(r for r in rows if r["scope"] == "total" and r["period"] == "month")
    ok = not bad
    detail = (f"칸 {len(seen)} (설정 {len(rows)} + 기록 프로젝트 {len(projects)}×2) · 최대 차 ${worst_d:.6f} (≤ ${TOL}) · "
              f"위반 {len(bad)} · 오늘 전체 추정 ${tot_day['est_usd']:.2f} / 기록 ${tot_day['rec_usd']:.2f} · "
              f"이번 달 ${tot_mon['est_usd']:.2f} / ${tot_mon['rec_usd']:.2f} · 단가 없음 {tot_mon['unpriced']} 건 · "
              f"단계 " + " · ".join(f"{k} {v}" for k, v in sorted(levels.items())) + f" (KST {now.astimezone(KST):%m-%d %H:%M})")
    if bad:
        detail += " · " + "; ".join(bad[:3])
    print(f"G-26  예산  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
