#!/usr/bin/env python
"""QA1 — 전 기간 · 전 에이전트 비용 손계산 (소유 규칙: 세션 안 requestId 첫 등장 기록 · 그 기록 안 output 최대) vs DB 합.
    .venv/bin/python -I outputs/qa1/global_cost.py --db data/agentdash-qa1.db"""
import argparse, json, os, sqlite3, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cost_check import hand, raw_usage  # noqa: E402
ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
proj = Path(os.path.expanduser("~/.claude/projects"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
offs = dict(con.execute("SELECT path, offset FROM src_file"))
files = sorted(proj.glob("*/*.jsonl")) + sorted(proj.glob("*/*/subagents/agent-*.jsonl")) + sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl"))
by_s = defaultdict(list)
for f in files:
    by_s[f.stem if f.parent.parent == proj else f.parts[len(proj.parts) + 1]].append(f)
per_agent = defaultdict(float); per_model = defaultdict(float)
for sid, fs in by_s.items():
    occ = defaultdict(list)
    for f in fs:
        k = f"S:{f.stem}" if f.parent.parent == proj else f"A:{f.stem[6:]}"
        mp = f.with_name(f.name[:-6] + ".meta.json")
        dep = 0 if f.parent.parent == proj else int((json.loads(mp.read_bytes()).get("spawnDepth") if mp.exists() else 1) or 1)
        for raw in open(f, "rb").read(offs.get(str(f))).split(b"\n"):
            if not raw.strip(): continue
            d = json.loads(raw)
            if d.get("type") != "assistant" or not d.get("requestId"): continue
            m = d["message"]
            if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict): continue
            occ[d["requestId"]].append(((d.get("timestamp") or "", dep, k), k, m["model"], raw_usage(m["usage"])))
    for rid, L in occ.items():
        owner = min(x[0] for x in L)[2]
        own = max((x for x in L if x[1] == owner), key=lambda x: x[3][4])
        i, cr, w5, w1, o, sp = own[3]
        c = hand(own[2], sp, i, cr, w5, w1, o) or 0.0
        per_agent[owner] += c; per_model[own[2]] += c
db_agent = dict(con.execute("SELECT agent_key, SUM(cost_usd) FROM usage_event GROUP BY agent_key"))
bad = [k for k in set(per_agent) | set(db_agent) if abs(per_agent.get(k, 0) - (db_agent.get(k) or 0)) > 1e-6]
print(f"손계산 합 ${sum(per_agent.values()):.6f} · DB 합 ${sum(v or 0 for v in db_agent.values()):.6f} · 에이전트 {len(per_agent)} · 차이 > 1e-6 인 에이전트 {len(bad)}")
print("모델별 손계산:", {k: round(v, 4) for k, v in sorted(per_model.items())})
