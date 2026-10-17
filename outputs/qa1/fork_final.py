#!/usr/bin/env python
"""QA1 — 포크 사본이 부모 기록보다 '더 최종인' usage 를 가진 requestId (D-01 × D-02 교차, 빠뜨림 사냥).

    .venv/bin/python -I outputs/qa1/fork_final.py --db data/agentdash-qa1.db

세션마다 requestId 별로: 소유 기록(가장 이른 timestamp, 같으면 얕은 깊이) 안 output 최대 줄 vs 세션 전체(사본 포함) output 최대 줄.
차이(4 칸 · 비용)를 센다. 원천 'rb' · DB mode=ro. 숫자 · 키만 출력.
"""
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
tot = dict(rids=0, input=0, cache_read=0, cache_write=0, output=0, cost=0.0, sessions=set(), agents=defaultdict(int))
for sid, fs in by_s.items():
    occ = defaultdict(list)
    for f in fs:
        k = f"S:{f.stem}" if f.parent.parent == proj else f"A:{f.stem[6:]}"
        mp = f.with_name(f.name[:-6] + ".meta.json")
        dep = 0 if f.parent.parent == proj else int((json.loads(mp.read_bytes()).get("spawnDepth") if mp.exists() else 1) or 1)
        for raw in open(f, "rb").read(offs.get(str(f))).split(b"\n"):
            if not raw.strip():
                continue
            d = json.loads(raw)
            if d.get("type") != "assistant" or not d.get("requestId"):
                continue
            m = d["message"]
            if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
                continue
            occ[d["requestId"]].append(((d.get("timestamp") or "", dep, k), k, m["model"], raw_usage(m["usage"])))
    for rid, L in occ.items():
        if len({x[1] for x in L}) < 2:
            continue
        owner = min(x[0] for x in L)[2]
        own = max((x for x in L if x[1] == owner), key=lambda x: x[3][4])
        best = max(L, key=lambda x: x[3][4])
        if best[3][4] > own[3][4]:
            tot["rids"] += 1
            tot["sessions"].add(sid)
            tot["agents"][owner] += 1
            i0, cr0, w50, w10, o0, s0 = own[3]
            i1, cr1, w51, w11, o1, s1 = best[3]
            tot["input"] += i1 - i0; tot["cache_read"] += cr1 - cr0; tot["cache_write"] += (w51 + w11) - (w50 + w10); tot["output"] += o1 - o0
            tot.setdefault("per_s", defaultdict(int))[sid[:8]] += o1 - o0
            tot["cost"] += (hand(best[2], s1, i1, cr1, w51, w11, o1) or 0) - (hand(own[2], s0, i0, cr0, w50, w10, o0) or 0)
print(f"부모 기록보다 사본이 더 최종(output 큼)인 requestId {tot['rids']} · 세션 {len(tot['sessions'])} · 부모 에이전트 {len(tot['agents'])}")
print(f"  빠진 양: 입력 {tot['input']} · 캐시읽기 {tot['cache_read']} · 캐시쓰기 {tot['cache_write']} · 출력 {tot['output']} · 비용 ${tot['cost']:.6f}")
print("  부모 에이전트별 건수:", dict(sorted(tot["agents"].items(), key=lambda x: -x[1])[:10]))
print("  세션별 빠진 출력:", dict(tot.get("per_s", {})))
