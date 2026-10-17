#!/usr/bin/env python
"""QA1 — 합성 경계(fast · Haiku 100K 구간 · 모르는 모델 · alias · fast 단가 없음)를 개발 cost() 에 먹여 손계산(cost_cases.json)과 대조.
    uv run python outputs/qa1/cost_edge.py"""
import json
from pathlib import Path
from agentdash.core import model as M, usage as U
P = U.load_pricing()
ok = 0
cases = json.loads((Path(__file__).parent / "cost_cases.json").read_text())
for mdl, sp, i, cr, w5, w1, o, h in cases:
    ev = M.UsageEvent(agent_key="x", request_id="r", at=None, model=mdl, speed=sp, input_tokens=i, cache_read=cr,
                      cache_write_5m=w5, cache_write_1h=w1, output_tokens=o)
    c, ver = U.cost(ev, P)
    same = (c is None and h is None) or (c is not None and h is not None and abs(c - h) <= 1e-12)
    ok += same
    print(f"  {mdl} speed={sp} prompt={i+cr+w5+w1} → 손 {h} · 개발 {c} {'일치' if same else '불일치'}")
print(f"일치 {ok}/{len(cases)}")
