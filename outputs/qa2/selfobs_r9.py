"""QA2 r9 G-22 — twin.build(24h) 를 mode=ro DB 로 불러 내 설비 · 라인 상태를 찍는다 (이름 · 키 · 상태 · 숫자만)."""
import sqlite3, sys
from agentdash.core import twin
db, key = sys.argv[1], sys.argv[2]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
d = twin.build(con, since="24h")
for ln in d["lines"]:
    for m in ln["machines"]:
        if m["key"] == key:
            print("line", ln["name"], "| state", m["state"], m.get("rule"), "| parent", m.get("parent"), "| box", m["box"], "| ended_ago_s", m.get("ended_ago_s"), "| tool", m.get("tool"))
            print("pipes", [(p["kind"], p["src"][:14], p["dst"][:14]) for p in ln.get("pipes", []) if key in (p["src"], p["dst"])])
            print("siblings", [(x["key"][:12], x["state"]) for x in ln["machines"]])
