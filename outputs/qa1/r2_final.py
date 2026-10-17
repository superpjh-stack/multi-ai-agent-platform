#!/usr/bin/env python
"""QA1 r2 — '최종본' 규칙 독립 집계 (DEF-QA1-001 재검증 · G-07). agentdash 를 import 하지 않는다.
    .venv/bin/python -I outputs/qa1/r2_final.py --db data/agentdash-qa1.db
규칙(문서 D-01 · D-02 보완에서): assistant 줄 · <synthetic> 제외 · requestId 는 세션에서 한 번.
  소유자 = 그 requestId 가 처음 나온 기록(timestamp → 깊이 → 키). 값 = 세션 전체(사본 포함) 중 output 최대 줄의 4 칸.
원천 'rb' · DB src_file.offset 까지 · DB mode=ro. 숫자 · 키만 출력.
"""
import argparse, json, os, sqlite3
from collections import defaultdict
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
proj = Path(os.path.expanduser("~/.claude/projects"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
offs = dict(con.execute("SELECT path, offset FROM src_file"))
files = (sorted(proj.glob("*/*.jsonl")) + sorted(proj.glob("*/*/subagents/agent-*.jsonl"))
         + sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl")))


def akey(p):
    return f"S:{p.stem}" if p.parent.parent == proj else f"A:{p.stem[6:]}"


def depth(p):
    if p.parent.parent == proj:
        return 0
    try:
        return int(json.loads(p.with_name(p.name[:-6] + ".meta.json").read_bytes()).get("spawnDepth") or 1)
    except Exception:
        return 1


by_s = defaultdict(list)
for p in files:
    by_s[p.stem if p.parent.parent == proj else p.parts[len(proj.parts) + 1]].append(p)
exp = defaultdict(lambda: [0, 0, 0, 0])
for sid, fs in by_s.items():
    first, best = {}, {}
    for p in fs:
        k, dp = akey(p), depth(p)
        lim = offs.get(str(p))
        with open(p, "rb") as fh:
            data = fh.read() if lim is None else fh.read(lim)
        for raw in data.split(b"\n"):
            if not raw.strip():
                continue
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("type") != "assistant":
                continue
            m = d.get("message") or {}
            rid = d.get("requestId")
            u = m.get("usage")
            if not rid or m.get("model") == "<synthetic>" or not isinstance(u, dict):
                continue
            c = (d.get("timestamp") or "", dp, k)
            if rid not in first or c < first[rid]:
                first[rid] = c
            v = [u.get("input_tokens") or 0, u.get("cache_read_input_tokens") or 0,
                 u.get("cache_creation_input_tokens") or 0, u.get("output_tokens") or 0]
            if rid not in best or v[3] > best[rid][3]:
                best[rid] = v
    for rid, c in first.items():
        e = exp[c[2]]
        for i in range(4):
            e[i] += best[rid][i]
db = {k: list(v) for k, *v in con.execute(
    "SELECT agent_key, SUM(input_tokens), SUM(cache_read), SUM(cache_write_5m+cache_write_1h), SUM(output_tokens) "
    "FROM usage_event GROUP BY agent_key")}
keys = set(exp) | set(db)
bad = [k for k in keys if exp.get(k, [0] * 4) != db.get(k, [0] * 4)]
tot_e = [sum(v[i] for v in exp.values()) for i in range(4)]
tot_d = [sum(v[i] for v in db.values()) for i in range(4)]
print(f"에이전트 {len(keys)} · 4 칸 불일치 {len(bad)}")
print(f"합 독립(최종본) in/cr/cw/out {tot_e}")
print(f"합 DB            in/cr/cw/out {tot_d}")
for k in sorted(bad)[:10]:
    print(f"  {k} 독립 {exp.get(k)} DB {db.get(k)}")
