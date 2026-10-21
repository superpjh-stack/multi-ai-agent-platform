#!/usr/bin/env python
"""QA1 r6 — G-31 실제 DB 손 확인 표본 (키 앞 14 자 · 상태 · 시각만, 본문 없음).

    uv run python outputs/qa1/r6_samples.py --db <DB> --now ISO

  S1 T-01 라인 순서 (살아 있음, 가장 늦은 last_event_at, 이름) + 격자 칸(행, 열)
  S2 T-03 행 순서: 칸이 가장 많은 라인의 (행, 열, 키, started_at)
  S3 T-05 접힌 표본 5 (범위 안 · 칸 없음 — ended 가장 이른 2 · 가운데 1 · 가장 늦은 2)
  S4 시간 키 표본 5 — DONE/FAILED 2 · STALE 1 · 살아 있는 것 2 : 원시 시각과 손계산(now − t, 초 내림) ↔ 응답
본문 없음.
"""
import argparse
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from r6_twin import dt  # noqa: E402

from agentdash.core import twin  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--now", required=True)
a = ap.parse_args()
now = dt(a.now)
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
r = twin.build(con, now=now)
A = {row[0]: dict(zip(("key", "kind", "pk", "parent", "started", "last", "ended", "state", "ss"), row)) for row in con.execute(
    "SELECT agent_key, kind, project_key, parent_key, started_at, last_event_at, ended_at, state, state_since FROM agent")}
sh = lambda k: (k or "-")[:14]
cols = r["grid"]["cols"]
print("S1 T-01 · T-08 (cols", cols, ")")
for i, ln in enumerate(r["lines"]):
    mem = [k for k in A if A[k]["pk"] == ln["key"] and (A[k]["state"] not in ("DONE", "FAILED")
           or max(A[k]["last"] or "", A[k]["started"] or "") >= (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"))]
    print(f"  {i} 격자({i // cols},{i % cols}) {ln['name'][:24]:24} live={ln['live']} 최근={max(A[k]['last'] or '' for k in mem)} "
          f"칸={len(ln['machines'])} box={ln['box']}")
big = max(r["lines"], key=lambda ln: len(ln["machines"]))
print("S2 T-03 라인", big["name"][:24])
step = twin.BOX_W + twin.GAP_X
for i, m in enumerate(big["machines"]):
    print(f"  행{i} 열{(m['box']['x'] - big['box']['x'] - twin.LINE_PAD) // step} {sh(m['key'])} start={A[m['key']]['started']} "
          f"{m['state']} folded={m['folded']}")
shown = {m["key"] for ln in r["lines"] for m in ln["machines"]}
cut = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
scope = [k for k in A if A[k]["state"] not in ("DONE", "FAILED") or max(A[k]["last"] or "", A[k]["started"] or "") >= cut]
hidden = sorted([k for k in scope if k not in shown], key=lambda k: A[k]["ended"] or "")
print(f"S3 T-05 접힌 {len(hidden)} 중 표본 5")
for k in hidden[:2] + hidden[len(hidden) // 2:len(hidden) // 2 + 1] + hidden[-2:]:
    e = dt(A[k]["ended"])
    kids = [c for c in A if A[c]["parent"] == k]
    print(f"  {sh(k)} {A[k]['state']} ended={A[k]['ended']} now-ended={(now - e).total_seconds() / 60:.1f}분 "
          f"자식={[A[c]['state'] for c in kids]} 부모={sh(A[k]['parent'])}{'(칸)' if A[k]['parent'] in shown else ''}")
M = {m["key"]: m for ln in r["lines"] for m in ln["machines"]}
fin = sorted([k for k in M if M[k]["state"] in ("DONE", "FAILED")])
stale = sorted([k for k in M if M[k]["state"] == "STALE"])
live = sorted([k for k in M if M[k]["state"] not in ("DONE", "FAILED", "STALE")])
pick = fin[:2] + stale[:1] + live[:2]
print("S4 시간 키 표본", len(pick))
for k in pick:
    m, x = M[k], A[k]
    hand = {f: (None if t is None else max(0, int((now - t).total_seconds())))
            for f, t in (("elapsed_s", dt(x["ss"])), ("ended_ago_s", dt(x["ended"]) if x["state"] in ("DONE", "FAILED") else None),
                         ("last_ago_s", dt(x["last"])))}
    got = {f: m[f] for f in hand}
    print(f"  {sh(k)} {x['state']} state_since={x['ss']} ended={x['ended']} last={x['last']} 손={hand} 응답={got} "
          f"{'같음' if hand == got else '다름'} tool={m['tool']}")
