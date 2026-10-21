#!/usr/bin/env python
"""QA1 r5 — G-31 실제 DB 손 확인 표본 (키 앞 14 자 · 상태 · 시각만, 본문 없음).

    uv run python outputs/qa1/r5_twin_samples.py --db data/agentdash-qa1.db --now ISO

  S1 T-01 라인 순서: 라인마다 (살아 있음, 가장 늦은 last_event_at, 이름)
  S2 T-03 행 순서: 가장 많은 칸을 가진 라인의 (행, 열, 키, started_at, 트윈 부모)
  S3 T-05 접힌 표본 5: 응답에 없는 범위 안 에이전트 — 상태 · ended_at · now−ended(분) · 자손 상태 · 접힌 곳
  S4 반입구 아래 설비: 부모 없음 / 부모 범위 밖 / 부모 다른 라인 (D-25)
  S5 T-07: 같은 DB 를 행 순서를 뒤집어 다시 넣은 사본에서 응답이 같은가
"""
import argparse, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agentdash.core import twin

ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--now", required=True)
a = ap.parse_args()
now = datetime.fromisoformat(a.now.replace("Z", "+00:00"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
r = twin.build(con, now=now)
A = {row[0]: dict(zip(("key","kind","pk","parent","started","last","ended","state"), row)) for row in con.execute(
    "SELECT agent_key, kind, project_key, parent_key, started_at, last_event_at, ended_at, state FROM agent")}
sh = lambda k: (k or "-")[:14]
print("S1 T-01")
for i, ln in enumerate(r["lines"]):
    mem = [k for k in A if A[k]["pk"] == ln["key"]]
    print(f"  {i} {ln['name'][:24]:24} live={ln['live']} counts={ln['counts']} 칸={len(ln['machines'])}")
big = max(r["lines"], key=lambda ln: len(ln["machines"]))
print("S2 T-03 라인", big["name"][:24])
step = twin.BOX_W + twin.GAP_X
for i, m in enumerate(big["machines"]):
    print(f"  행{i} 열{(m['box']['x']-twin.LINE_PAD)//step} {sh(m['key'])} {A[m['key']]['kind'][:8]:8} start={A[m['key']]['started']} parent={sh(m['parent'])} {m['state']} folded={m['folded']}")
shown = {m["key"] for ln in r["lines"] for m in ln["machines"]}
cut = now - timedelta(hours=24)
scope = [k for k in A if A[k]["state"] not in ("DONE","FAILED") or max(A[k]["last"] or "", A[k]["started"] or "") >= cut.strftime("%Y-%m-%dT%H:%M:%S")]
hidden = sorted([k for k in scope if k not in shown], key=lambda k: A[k]["ended"] or "")
print(f"S3 T-05 접힌 {len(hidden)} 중 표본 5")
pick = hidden[:2] + hidden[len(hidden)//2:len(hidden)//2+1] + hidden[-2:]
for k in pick:
    e = datetime.fromisoformat(A[k]["ended"].replace("Z","+00:00"))
    kids = [c for c in A if A[c]["parent"] == k]
    holder = A[k]["parent"] if A[k]["parent"] in shown else ("반입구" if A[k]["parent"] not in scope else f"조상({sh(A[k]['parent'])} 도 접힘)")
    print(f"  {sh(k)} {A[k]['kind'][:8]} {A[k]['state']} ended={A[k]['ended']} now-ended={(now-e).total_seconds()/60:.1f}분 자식={[A[c]['state'] for c in kids]} → {sh(holder) if holder in A else holder}")
print("S4 반입구 아래")
inl = 0
for ln in r["lines"]:
    for p in ln["pipes"]:
        if p["src"].startswith("U:"):
            k = p["dst"]; par = A[k]["parent"]
            why = "부모 없음" if not par else ("부모 범위 밖" if par not in scope else ("다른 라인" if A[par]["pk"] != A[k]["pk"] else "?"))
            print(f"  {ln['name'][:20]} {sh(k)} {A[k]['state']} parent={sh(par)} {why}")
    if ln.get("inlet"):
        print(f"  {ln['name'][:20]} 반입구 folded={ln['inlet']['folded']} x={ln['inlet']['box']['x']}")
# S5
mem = sqlite3.connect(":memory:")
con.backup(mem)
for t in ("agent", "usage_event", "tool_call", "edge", "state_log"):
    cols = [c[1] for c in mem.execute(f"PRAGMA table_info({t})")]
    rows = mem.execute(f"SELECT {','.join(cols)} FROM {t}").fetchall()
    mem.execute(f"DELETE FROM {t}")
    mem.executemany(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", rows[::-1])
for s in (None, "all"):
    x = twin.build(con, now=now, since=s); y = twin.build(mem, now=now, since=s)
    x.pop("elapsed_ms"); y.pop("elapsed_ms")
    print(f"S5 T-07 since={s or '24h'} 행 순서 뒤집은 사본과 응답 같음: {x == y}")
