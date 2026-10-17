#!/usr/bin/env python
"""QA1 — 부모 연결 독립 재계산 (G-06 · V-02, spec §3.2 L-01~L-03) + 필수 필드 없는 줄 (G-05). 숫자 · 키만.
    .venv/bin/python -I outputs/qa1/link_check.py --db data/agentdash-qa1.db
L-01/L-02: meta toolUseId 와 같은 tool_use.id 를 가진 Agent/Task 호출 줄을 같은 세션 폴더에서 찾는다. 여러 곳이면
  (포크 사본) 세션 기록 > 얕은 기록 > 가장 이른 줄. L-03: 워크플로 에이전트 → W:<wf 폴더>, 워크플로 노드 → Workflow 결과 runId 를 받은 기록."""
import argparse, json, os, sqlite3
from collections import defaultdict
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
proj = Path(os.path.expanduser("~/.claude/projects"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
offs = dict(con.execute("SELECT path, offset FROM src_file"))
db_parent = dict(con.execute("SELECT agent_key, parent_key FROM agent"))
req_missing = 0; total_lines = 0
exp = {}
for sess in sorted(p for p in proj.glob("*/*") if p.is_dir() and (p / "subagents").is_dir() or (p / "workflows").is_dir()):
    main = sess.with_suffix(".jsonl")
    files = ([main] if main.exists() else []) + sorted(sess.glob("subagents/agent-*.jsonl")) + sorted(sess.glob("subagents/workflows/wf_*/agent-*.jsonl"))
    calls = defaultdict(list); runs = {}
    for f in files:
        k = f"S:{f.stem}" if f == main else f"A:{f.stem[6:]}"
        mp = f.with_name(f.name[:-6] + ".meta.json")
        dep = 0 if f == main else int((json.loads(mp.read_bytes()).get("spawnDepth") if mp.exists() else 1) or 1)
        for n, raw in enumerate(open(f, "rb").read(offs.get(str(f))).split(b"\n")):
            if not raw.strip(): continue
            d = json.loads(raw)
            for b in (d.get("message") or {}).get("content") or [] if d.get("type") == "assistant" else []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                    calls[b["id"]].append((dep, d.get("timestamp") or "", k))
            if d.get("type") == "user" and isinstance(d.get("toolUseResult"), dict):
                rid = d["toolUseResult"].get("runId")
                if isinstance(rid, str) and rid.startswith("wf_"):
                    runs.setdefault(rid, k)
    for mp in sorted(sess.glob("subagents/agent-*.meta.json")):
        m = json.loads(mp.read_bytes()); k = f"A:{mp.name[6:-10]}"
        c = calls.get(m.get("toolUseId")) or []
        exp[k] = min(c)[2] if c else None
    for mp in sorted(sess.glob("subagents/workflows/wf_*/agent-*.meta.json")):
        exp[f"A:{mp.name[6:-10]}"] = f"W:{mp.parent.name}"
    for wf in sorted(sess.glob("workflows/wf_*.json")):
        exp[f"W:{wf.stem}"] = runs.get(wf.stem)
for f in sorted(proj.glob("*/*.jsonl")) + sorted(proj.glob("*/*/subagents/agent-*.jsonl")) + sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl")):
    for raw in open(f, "rb").read(offs.get(str(f))).split(b"\n"):
        if not raw.strip(): continue
        total_lines += 1
        d = json.loads(raw)
        if d.get("type") in ("assistant", "user"):
            if not all(d.get(x) for x in ("uuid", "timestamp", "sessionId")) or not isinstance(d.get("message"), dict) \
                    or (d["type"] == "assistant" and "model" not in d["message"]):
                req_missing += 1
sub = [k for k in exp if k.startswith("A:")]
have = sum(1 for k in sub if exp[k]); same = sum(1 for k in exp if exp[k] == db_parent.get(k))
dbhave = sum(1 for k in sub if db_parent.get(k))
print(f"G-06 독립: 서브+워크플로 에이전트 {len(sub)} · 부모 찾음 {have} ({100*have/len(sub):.1f}%) · DB parent_key 있음 {dbhave} · 독립=DB 일치 {same}/{len(exp)} (워크플로 노드 포함)")
for k in exp:
    if exp[k] != db_parent.get(k): print("   불일치", k[:14], "독립", (exp[k] or "-")[:14], "DB", (db_parent.get(k) or "-")[:14])
print(f"G-05 독립: 줄 {total_lines} · assistant/user 필수 필드 없음 {req_missing} · 비율 {100*req_missing/total_lines:.4f}%")
