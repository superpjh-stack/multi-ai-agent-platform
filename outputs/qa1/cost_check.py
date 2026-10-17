#!/usr/bin/env python
"""QA1 비용 손계산 (G-08 · G-20). 단가는 spec.md §6.1 표를 이 파일에 옮겨 적은 값(config 를 믿지 않는다).

    .venv/bin/python -I outputs/qa1/cost_check.py --db data/agentdash-qa1.db [--seed 3] [--project <project_key>]

1. config/pricing.yaml ↔ spec §6.1 표 대조
2. 실제 표본 20 건: DB usage_event 에서 층화 추출 → 원천 줄(같은 기록 · 같은 requestId · output 최대)을 직접 읽어 손계산 → DB cost_usd
3. 프로젝트 하나 전 기간 비용: 원천 독립 집계(recount.py 와 같은 소유 규칙) × 손계산 단가 → 출력 (API 값은 따로 받아 대조)
원천은 'rb' 로만, DB 는 mode=ro 로만 연다. 출력은 숫자 · 키뿐.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# spec.md §6.1 기본 단가표 (1M 토큰당 US$) — in, out, cr, fast_mult(None = 빠른 모드 단가 없음)
SPEC = {
    "claude-fable-5-1": (10.00, 50.00, 0.25, None),
    "claude-fable-5": (10.00, 50.00, 1.00, None),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 2.0),
    "claude-opus-5": (5.00, 25.00, 0.50, 2.0),
    "claude-opus-4-8": (5.00, 25.00, 0.50, None),
    "claude-opus-4-7": (5.00, 25.00, 0.50, None),
    "claude-opus-4-6": (5.00, 25.00, 0.50, None),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, None),
    "claude-sonnet-5": (2.00, 10.00, 0.20, None),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30, None),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, None),
}
HAIKU55 = [(100000, 0.10, 0.50, 0.01), (None, 0.50, 2.50, 0.05)]
ALIASES = {"claude-opus-5-5[1m]": "claude-opus-5-5"}


def hand(model, speed, i, cr, w5, w1, o):
    m = ALIASES.get(model, model)
    if m == "claude-haiku-5-5":
        prompt = i + cr + w5 + w1
        tin, tout, tcr = next((a, b, c) for mx, a, b, c in HAIKU55 if mx is None or prompt <= mx)
        fm = None
    elif m in SPEC:
        tin, tout, tcr, fm = SPEC[m]
    else:
        return None
    mult = 1.0
    if speed == "fast":
        if fm is None:
            return None
        mult = fm
    return (i * tin + cr * tcr + w5 * tin * 1.25 + w1 * tin * 2.0 + o * tout) / 1e6 * mult


def raw_usage(u: dict):
    cc = u.get("cache_creation")
    if isinstance(cc, dict) and ("ephemeral_5m_input_tokens" in cc or "ephemeral_1h_input_tokens" in cc):
        w5, w1 = cc.get("ephemeral_5m_input_tokens") or 0, cc.get("ephemeral_1h_input_tokens") or 0
    else:
        w5, w1 = u.get("cache_creation_input_tokens") or 0, 0
    return (u.get("input_tokens") or 0, u.get("cache_read_input_tokens") or 0, w5, w1, u.get("output_tokens") or 0,
            u.get("speed"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--project")
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)

    # 1. config ↔ spec
    import yaml
    cfg = yaml.safe_load((root / "config/pricing.yaml").read_text())
    bad = []
    for m, (tin, tout, tcr, fm) in SPEC.items():
        e = cfg["models"].get(m)
        if not e or (e["in"], e["out"], e["cache_read"], e.get("fast_mult")) != (tin, tout, tcr, fm):
            bad.append(m)
    hk = cfg["models"]["claude-haiku-5-5"]["tiers"]
    if [(t["max_prompt"], t["in"], t["out"], t["cache_read"]) for t in hk] != HAIKU55:
        bad.append("claude-haiku-5-5")
    extra = set(cfg["models"]) - set(SPEC) - {"claude-haiku-5-5"}
    print(f"## 단가표 config ↔ spec §6.1: 모델 {len(cfg['models'])} · 불일치 {bad or 0} · spec 밖 모델 {sorted(extra) or 0}"
          f" · 캐시 배수 {cfg['cache_write_mult']} · alias {cfg.get('aliases')} · version {cfg['version']}")

    # 2. 실제 표본 20
    paths = defaultdict(list)
    for (p,) in con.execute("SELECT path FROM src_file WHERE path LIKE '%.jsonl'"):
        n = Path(p).name
        if n == "journal.jsonl":
            continue
        k = f"A:{n[6:-6]}" if n.startswith("agent-") else f"S:{n[:-6]}"
        paths[k].append(p)
    rows = con.execute("SELECT agent_key, request_id, model, speed, cache_write_5m, cache_write_1h, cost_usd FROM usage_event"
                       ).fetchall()
    rng = random.Random(a.seed)
    pick = []

    def take(pred, n, tag):
        cand = [r for r in rows if pred(r) and r not in [p[0] for p in pick]]
        for r in rng.sample(cand, min(n, len(cand))):
            pick.append((r, tag))

    take(lambda r: (r[5] or 0) > 0, 3, "1h")
    take(lambda r: (r[4] or 0) > 0 and not r[5], 3, "5m")
    take(lambda r: r[3] is None, 2, "speed 없음")
    for mdl in sorted({r[2] for r in rows}):
        take(lambda r, mdl=mdl: r[2] == mdl, 1, f"모델 {mdl}")
    take(lambda r: True, 20 - len(pick), "무작위")
    print(f"\n## 실제 표본 {len(pick)} 건 (시드 {a.seed}) — 원천 줄 직접 손계산 vs DB cost_usd")
    ok = 0
    for (k, rid, mdl, spd, _w5, _w1, dbc), tag in pick:
        best = None
        for p in paths[k]:
            with open(p, "rb") as fh:
                for raw in fh:
                    if rid.encode() not in raw:
                        continue
                    d = json.loads(raw)
                    if d.get("type") != "assistant" or d.get("requestId") != rid:
                        continue
                    u = raw_usage(d["message"]["usage"])
                    if best is None or u[4] > best[1][4]:
                        best = (d["message"]["model"], u)
        model, (i, cr, w5, w1, o, speed) = best
        h = hand(model, speed, i, cr, w5, w1, o)
        same = h is not None and dbc is not None and abs(h - dbc) <= 1e-9
        ok += same
        print(f"  {tag:22s} {k[:10]} {model} speed={speed} in={i} cr={cr} w5={w5} w1={w1} out={o} → 손 {h:.6f} · DB {dbc:.6f} "
              f"{'일치' if same else '불일치'}")
    print(f"  일치 {ok}/{len(pick)}")
    nulls = con.execute("SELECT COUNT(*) FROM usage_event WHERE cost_usd IS NULL").fetchone()[0]
    unk = [m for (m,) in con.execute("SELECT DISTINCT model FROM usage_event") if ALIASES.get(m, m) not in SPEC
           and m != "claude-haiku-5-5"]
    print(f"  DB 비용 NULL 행 {nulls} · 단가표 밖 모델 {unk}")

    # 3. 합성 경계 (실제 기록에 없는 경우) — 손계산 값만 찍는다. DB 쪽은 qa1 가 cost() 를 따로 불러 대조
    cases = [("claude-opus-5-5", "fast", 1000, 20000, 3000, 4000, 500), ("claude-opus-5", "fast", 10, 0, 0, 0, 100),
             ("claude-opus-4-8", "fast", 10, 0, 0, 0, 100), ("claude-haiku-5-5", None, 50000, 49999, 1, 0, 1000),
             ("claude-haiku-5-5", None, 50000, 50000, 1, 0, 1000), ("claude-haiku-5-5", "standard", 100000, 0, 0, 0, 10),
             ("claude-haiku-5-5", None, 100001, 0, 0, 0, 10), ("claude-made-up-9", None, 10, 10, 10, 10, 10),
             ("claude-opus-5-5[1m]", None, 100, 1000, 0, 200, 50), (None, None, 1, 1, 1, 1, 1)]
    print("\n## 합성 경계 손계산 (model, speed, in, cr, w5, w1, out → US$)")
    out = []
    for c in cases:
        h = hand(*c)
        out.append([*c, h])
        print(f"  {c} → {h}")
    (root / "outputs/qa1/cost_cases.json").write_text(json.dumps(out))

    # 4. 프로젝트 전 기간
    if a.project:
        proj = Path(os.path.expanduser("~/.claude/projects")) / a.project
        files = sorted(proj.glob("*.jsonl")) + sorted(proj.glob("*/subagents/agent-*.jsonl")) + \
            sorted(proj.glob("*/subagents/workflows/wf_*/agent-*.jsonl"))
        offs = {r[0]: r[1] for r in con.execute("SELECT path, offset FROM src_file")}
        by_sess = defaultdict(list)
        for f in files:
            sid = f.stem if f.parent == proj else f.relative_to(proj).parts[0]
            by_sess[sid].append(f)
        total, n_req, toks = 0.0, 0, [0, 0, 0, 0, 0]
        for sid, fs in by_sess.items():
            first = {}
            recs = []
            for f in fs:
                k = f"S:{f.stem}" if f.parent == proj else f"A:{f.stem[6:]}"
                dep = 0 if f.parent == proj else 1
                with open(f, "rb") as fh:
                    data = fh.read(offs.get(str(f)))
                for raw in data.split(b"\n"):
                    if not raw.strip():
                        continue
                    d = json.loads(raw)
                    if d.get("type") != "assistant" or not d.get("requestId"):
                        continue
                    m = d["message"]
                    if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
                        continue
                    c = (d.get("timestamp") or "", dep, k)
                    if d["requestId"] not in first or c < first[d["requestId"]]:
                        first[d["requestId"]] = c
                    recs.append((k, d["requestId"], m["model"], raw_usage(m["usage"])))
            best = {}
            for k, rid, mdl, u in recs:
                if first[rid][2] != k:
                    continue
                if (k, rid) not in best or u[4] > best[(k, rid)][1][4]:
                    best[(k, rid)] = (mdl, u)
            for mdl, (i, cr, w5, w1, o, sp) in best.values():
                h = hand(mdl, sp, i, cr, w5, w1, o)
                total += h or 0
                n_req += 1
                for j, v in enumerate((i, cr, w5 + w1, o)):
                    toks[j] += v
        print(f"\n## 프로젝트 {a.project} 전 기간 손계산: 세션 {len(by_sess)} · 기록 {len(files)} · 요청 {n_req} · "
              f"입력 {toks[0]} · 캐시읽기 {toks[1]} · 캐시쓰기 {toks[2]} · 출력 {toks[3]} · 비용 ${total:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
