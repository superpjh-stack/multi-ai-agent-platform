#!/usr/bin/env python
"""QA1 — 부모 기록의 <task-notification> 안 숫자(<subagent_tokens> · <tool_uses>)를 자식 DB 값과 대조. 숫자 · 키만 출력.
    .venv/bin/python -I outputs/qa1/notif_usage.py --db data/agentdash-qa1.db
"""
import argparse, json, os, re, sqlite3
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
proj = Path(os.path.expanduser("~/.claude/projects"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
spawn = {r[0]: r[1] for r in con.execute("SELECT spawn_tool_use, agent_key FROM agent WHERE spawn_tool_use IS NOT NULL")}
RX = {k: re.compile(rf"<{k}>\s*([^<\s]+)\s*</{k}>") for k in ("tool-use-id", "task-id", "subagent_tokens", "tool_uses", "total_tokens", "status")}
seen = {}
for f in list(proj.glob("*/*.jsonl")) + list(proj.glob("*/*/subagents/agent-*.jsonl")):
    for raw in open(f, "rb"):
        if b"<task-notification>" not in raw:
            continue
        d = json.loads(raw)
        if d.get("type") != "user":
            continue
        c = d.get("message", {}).get("content")
        texts = [c] if isinstance(c, str) else [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
        for s in texts:
            for blk in s.split("<task-notification>")[1:]:
                g = {k: (m.group(1) if (m := rx.search(blk)) else None) for k, rx in RX.items()}
                key = spawn.get(g["tool-use-id"]) or (f"A:{g['task-id']}" if g["task-id"] else None)
                if key and g["subagent_tokens"]:
                    seen[key] = g   # 마지막 알림
rows = []
for k, g in seen.items():
    r = con.execute("SELECT COALESCE(SUM(input_tokens+cache_read+cache_write_5m+cache_write_1h+output_tokens),0), "
                    "COALESCE(SUM(output_tokens),0), COALESCE(SUM(input_tokens+cache_write_5m+cache_write_1h+output_tokens),0) "
                    "FROM usage_event WHERE agent_key=?", (k,)).fetchone()
    last = con.execute("SELECT input_tokens+cache_read+cache_write_5m+cache_write_1h+output_tokens FROM usage_event "
                       "WHERE agent_key=? ORDER BY at DESC LIMIT 1", (k,)).fetchone()
    tc = con.execute("SELECT COUNT(*) FROM tool_call WHERE agent_key=?", (k,)).fetchone()[0]
    rows.append((k, int(g["subagent_tokens"]), g["tool_uses"] and int(g["tool_uses"]), r[0], r[1], last[0] if last else None, tc, g["status"]))
n = len(rows)
tool_eq = sum(1 for x in rows if x[2] is not None and x[2] == x[6])
tool_has = sum(1 for x in rows if x[2] is not None)
last_eq = sum(1 for x in rows if x[5] is not None and abs(x[5] - x[1]) <= max(50, 0.02 * x[1]))
print(f"알림 숫자 있는 자식 {n} · tool_uses = DB 도구 호출 {tool_eq}/{tool_has}")
print(f"  subagent_tokens ≈ DB 마지막 요청의 (입력+캐시+출력) (±2%): {last_eq}/{n}")
diff = sorted(rows, key=lambda x: -abs((x[2] or 0) - x[6]))[:8]
for x in diff:
    print(f"  {x[0][:12]} 알림 tool_uses {x[2]} · DB 도구 {x[6]} · 알림 tokens {x[1]} · DB 마지막요청 {x[5]} · status {x[7]}")
