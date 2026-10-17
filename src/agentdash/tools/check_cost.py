#!/usr/bin/env python
"""V-09 check_cost — 표본 메시지 20 건의 비용: spec.md §6.1 손계산 ↔ DB + 단가 없는 모델 목록 (G-08).

    uv run python src/agentdash/tools/check_cost.py [--db 경로] [--n 20]

손계산은 core/usage.py 를 부르지 않고 이 파일 안에서 config/pricing.yaml 을 직접 읽어 계산한다:
    cost = (in×P_in + cr×P_cr + w5m×P_in×1.25 + w1h×P_in×2.0 + out×P_out) / 1e6 × (fast ? fast_mult : 1)
    Haiku 5.5 는 프롬프트(in+cr+w5m+w1h) ≤ 100K / 초과 구간. 표에 없는 모델 · fast 단가 없는 모델 → NULL.
표본: 1h 캐시 쓰기 있는 것 · 5m 만 있는 것 · 모델마다 · fast (있으면) · 단가 없는 모델 (있으면) 을 먼저 고르고 나머지는 고정 시드 무작위.
출력: `G-08  비용 손계산 (표본 20)  PASS|FAIL  …` · `G-08  단가 없는 모델 목록  PASS  …` (목록 출력이 곧 통과 조건)
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

COLS = "agent_key, request_id, model, speed, input_tokens, cache_read, cache_write_5m, cache_write_1h, output_tokens, " \
       "cost_usd, pricing_ver"


def hand_cost(row: dict, pr: dict) -> float | None:
    models, aliases = pr["models"], pr.get("aliases") or {}
    m = row["model"]
    m = m if m in models else aliases.get(m)
    if m not in models:
        return None
    e = models[m]
    i, cr, w5, w1, o = (row[k] or 0 for k in ("input_tokens", "cache_read", "cache_write_5m", "cache_write_1h",
                                                "output_tokens"))
    if "tiers" in e:
        prompt = i + cr + w5 + w1
        e = next(t for t in e["tiers"] if t["max_prompt"] is None or prompt <= t["max_prompt"])
        fast = models[m].get("fast_mult")
    else:
        fast = e.get("fast_mult")
    mult = 1.0
    if row["speed"] == "fast":
        if fast is None:
            return None
        mult = fast
    k5, k1 = pr["cache_write_mult"]["5m"], pr["cache_write_mult"]["1h"]
    return (i * e["in"] + cr * e["cache_read"] + w5 * e["in"] * k5 + w1 * e["in"] * k1 + o * e["out"]) / 1e6 * mult


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-08  비용 손계산  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    pr = yaml.safe_load((_settings.CONFIG_DIR / "pricing.yaml").read_text(encoding="utf-8"))
    con = conn.connect(db)
    rows = [dict(r) for r in con.execute(f"SELECT {COLS} FROM usage_event ORDER BY agent_key, request_id")]
    if len(rows) < a.n:
        print(f"G-08  비용 손계산 (표본 {a.n})  FAIL  usage_event {len(rows)} 행 — make backfill")
        return 1
    rnd = random.Random(20261017)
    picks: list[dict] = []

    def take(pred, k=1, why=""):
        cand = [r for r in rows if pred(r) and r not in picks]
        for r in rnd.sample(cand, min(k, len(cand))):
            r["_why"] = why
            picks.append(r)

    take(lambda r: (r["cache_write_1h"] or 0) > 0, 3, "1h")
    take(lambda r: (r["cache_write_5m"] or 0) > 0 and not r["cache_write_1h"], 3, "5m")
    take(lambda r: r["speed"] == "fast", 2, "fast")
    take(lambda r: r["speed"] is None, 2, "speed 없음(옛 기록)")
    for m in sorted({r["model"] for r in rows if r["model"]}):
        take(lambda r, m=m: r["model"] == m, 1, m)
    take(lambda r: hand_cost(r, pr) is None, 1, "단가 없음")
    take(lambda r: True, max(0, a.n - len(picks)), "무작위")
    picks = picks[: a.n]
    bad = []
    for r in picks:
        h = hand_cost(r, pr)
        d = r["cost_usd"]
        same = (h is None and d is None) or (h is not None and d is not None and abs(h - d) <= 1e-12)
        if not same or r["pricing_ver"] != str(pr["version"]):
            bad.append(f"{r['agent_key']}/{r['request_id'][:10]} 손 {h} DB {d} ver {r['pricing_ver']}")
    kinds = sorted({r["_why"] for r in picks})
    have_fast = any(r["speed"] == "fast" for r in rows)
    note = "" if have_fast else " · 기록에 speed=fast 0 건 (fast 는 tests/test_cost.py 로)"
    total_h = sum(hand_cost(r, pr) or 0 for r in picks)
    print(f"G-08  비용 손계산 (표본 {len(picks)})  {'PASS' if not bad else 'FAIL'}  일치 {len(picks) - len(bad)}/{len(picks)} "
          f"· 손계산 합 ${total_h:.6f} · 단가표 {pr['version']} · 표본 종류 {','.join(kinds)}{note}"
          + (" · 불일치 " + "; ".join(bad[:3]) if bad else ""))
    nulls = con.execute("SELECT model, COUNT(*) FROM usage_event WHERE cost_usd IS NULL GROUP BY model").fetchall()
    unpriced = [(m, n) for m, n in con.execute("SELECT model, COUNT(*) FROM usage_event GROUP BY model ORDER BY 2 DESC")
                if hand_cost({"model": m, "speed": None, "input_tokens": 0, "cache_read": 0, "cache_write_5m": 0,
                              "cache_write_1h": 0, "output_tokens": 0}, pr) is None]
    listing = ", ".join(f"{m} {n}" for m, n in unpriced) or "없음 (0 건)"
    null_ok = {m for m, _ in nulls} <= {m for m, _ in unpriced} | {m for m, _ in nulls if m is not None and any(
        r["speed"] == "fast" for r in rows if r["model"] == m)}
    print(f"G-08  단가 없는 모델 목록  {'PASS' if null_ok else 'FAIL'}  {listing} · 비용 NULL 행 {sum(n for _, n in nulls)}"
          f" · 기록 모델 {con.execute('SELECT COUNT(DISTINCT model) FROM usage_event').fetchone()[0]}")
    con.close()
    return 0 if not bad and null_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
