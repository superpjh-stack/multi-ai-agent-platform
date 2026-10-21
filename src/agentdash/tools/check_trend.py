#!/usr/bin/env python
"""V-14 check_trend — 일 · 주 · 월 추세 합 ↔ usage_daily 합 ↔ usage_event 합 (G-27, spec.md v0.3 §6.3).

    uv run python src/agentdash/tools/check_trend.py [--db 경로]

  · 기간 = 기록 전체 (usage_event 의 가장 이른 · 늦은 KST 일자).
  · 값 4 = 기록 비용 cost_usd · 추정 보정 비용 cost_est_usd · 기록 출력 output_tokens · 추정 출력 (의심 행 output_est, 나머지 output_tokens).
  · usage_event 직접 합은 budget 코드를 쓰지 않고 행마다 KST 일자 · 그 주 월요일 · 그 달 1 일을 따로 계산해 **묶음별로** 센다
    (전체 합만이 아니라 묶음 하나하나 = 추세 행).
  · usage_daily 합: 비용 2 · 기록 출력 · output_est(의심 행만의 합) ↔ usage_event 같은 값.
판정: grain 3 × group 2 의 묶음별 값이 직접 합과 같다 (비용 ≤ 1e-6 · 토큰 정확) · usage_daily 합 = usage_event 합.
출력: `G-27  추세  PASS|FAIL  …`
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

KST = timezone(timedelta(hours=9))
EPS = 1e-6
VALS = ("cost_usd", "cost_est_usd", "output_tokens", "output_est_total")


def _bucket(d: datetime, grain: str) -> str:
    if grain == "week":
        d = d - timedelta(days=d.weekday())
    elif grain == "month":
        d = d.replace(day=1)
    return d.strftime("%Y-%m-%d")


def _name(pp, pk):
    last = pp.rstrip("/").rsplit("/", 1)[-1] if pp else ""
    return last or pk or "(프로젝트 없음)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-27  추세  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    from agentdash.core import budget as B

    con = conn.connect(db)
    names = {k: _name(pp, pk) for k, pp, pk in con.execute("SELECT agent_key, project_path, project_key FROM agent")}
    events = []
    for k, at, c, ce, o, oe in con.execute(
            "SELECT agent_key, at, cost_usd, cost_est_usd, output_tokens, output_est FROM usage_event WHERE at IS NOT NULL"):
        day = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(KST).replace(tzinfo=None)
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        events.append((k, day, c, ce, o or 0, oe if oe is not None else (o or 0), oe or 0))
    if not events:
        print("G-27  추세  FAIL  usage_event 0 — make backfill")
        return 1
    frm = min(e[1] for e in events).strftime("%Y-%m-%d")
    to = max(e[1] for e in events).strftime("%Y-%m-%d")
    bad: list[str] = []
    n_buckets = 0
    for grain in B.GRAINS:
        for group in B.TREND_GROUPS:
            want: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, 0, 0])
            for k, day, c, ce, o, oet, _oe in events:
                w = want[(_bucket(day, grain), names.get(k, "(프로젝트 없음)") if group == "project" else None)]
                w[0] += c or 0.0
                w[1] += ce or 0.0
                w[2] += o
                w[3] += oet
            got = {(r["bucket"], r["project"]): r for r in B.trend(con, grain, frm, to, group)}
            n_buckets += len(want)
            for key in set(want) | set(got):
                w = want.get(key, [0.0, 0.0, 0, 0])
                g = got.get(key)
                gv = [(g[v] or 0) for v in VALS] if g else [0.0, 0.0, 0, 0]
                if abs(gv[0] - w[0]) > EPS or abs(gv[1] - w[1]) > EPS or gv[2] != w[2] or gv[3] != w[3]:
                    bad.append(f"{grain}/{group} {key[0]} {key[1] or ''} 추세 {gv} ≠ 직접 {w}")
    d = con.execute("SELECT COALESCE(SUM(cost_usd),0), COALESCE(SUM(cost_est_usd),0), COALESCE(SUM(output_tokens),0), "
                    "COALESCE(SUM(output_est),0) FROM usage_daily").fetchone()
    e = (sum(x[2] or 0.0 for x in events), sum(x[3] or 0.0 for x in events), sum(x[4] for x in events),
         sum(x[6] for x in events))
    daily_ok = abs(d[0] - e[0]) <= EPS and abs(d[1] - e[1]) <= EPS and d[2] == e[2] and d[3] == e[3]
    if not daily_ok:
        bad.append(f"usage_daily {tuple(d)} ≠ usage_event {e}")
    con.close()
    ok = not bad
    tot_est = sum(x[5] for x in events)
    detail = (f"{frm}~{to} · grain 3 × group 2 · 묶음 {n_buckets} · 불일치 {len(bad)} · usage_daily = usage_event "
              f"{'=' if daily_ok else '≠'} (기록 ${e[0]:.2f} · 추정 보정 ${e[1]:.2f} · 출력 기록 {e[2]} · 추정 {tot_est})")
    if bad:
        detail += " · " + "; ".join(bad[:2])
    print(f"G-27  추세  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
