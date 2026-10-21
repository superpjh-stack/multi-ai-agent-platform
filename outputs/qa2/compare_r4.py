"""judge_r4 출력(json) ↔ DB 덤프(key|state|rule|since|last) 대조. 본문 없음 — 키 · 상태 · 규칙만."""
import json, sys
j = json.load(open(sys.argv[1]))
db = {}
for line in open(sys.argv[2]):
    p = line.rstrip("\n").split("|")
    db[p[0]] = (p[1], p[2])
bad = []; n = 0; dist = {}
for r in j["results"]:
    k = r["key"]
    if k not in db or "error" in r:
        print("SKIP", k, r.get("error")); continue
    n += 1
    exp = (r.get("v03_state"), r.get("v03_rule"))
    got = db[k]
    dist[exp[0]] = dist.get(exp[0], 0) + 1
    if exp[0] != got[0] or exp[1] != got[1]:
        bad.append((k, exp, got))
print("now", j["now"], "n", n, "mismatch", len(bad), "dist", dist)
for b in bad:
    print("X", *b)
