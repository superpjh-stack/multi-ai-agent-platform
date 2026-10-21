#!/usr/bin/env python
"""QA1 r6 — DEF-QA1-401 재검증: /api/v1/twin?project= 가 라인 단위인가 · D-02 와 같은 집합인가.

    uv run python outputs/qa1/r6_filter.py --db <DB> --now ISO

필터 값마다 (since 24h · all):
  · 직접 기대 집합 E = 범위 안 에이전트 중 project_key == f 또는 f ∈ D-28 라인 이름 (r6_twin.d28_names — twin 코드 안 씀)
  · 옛 방식(에이전트마다 project_path 마지막 이름) 집합 O — 하위 폴더 에이전트가 E 에만 있는 수 = E − O
  · twin 응답: agents_in_scope == |E| · 라인 키 집합 == E 의 project_key 집합 · 반입구로 밀려난 설비 수(필터 없을 때와 비교)
  · D-02 graph.build(project=f): 에이전트 노드 집합 G — E ⊆ G, G − E 는 전부 E 의 조상(범위 밖, D-02 는 조상을 붙인다)
본문 없음 — 키 앞 14 자 · 숫자.
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from r6_twin import d28_names, dt, since_delta, FINAL  # noqa: E402

from agentdash.core import graph, twin  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--now", required=True)
a = ap.parse_args()
now = dt(a.now)
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
names = d28_names(con)
A = {r[0]: dict(zip(("key", "kind", "pk", "pp", "parent", "started", "last", "state"), r)) for r in con.execute(
    "SELECT agent_key, kind, project_key, project_path, parent_key, started_at, last_event_at, state FROM agent")}


def in_range(k, since):
    x = A[k]
    if x["state"] not in FINAL or since == "all":
        return True
    ts = [t for t in (dt(x["started"]), dt(x["last"])) if t]
    return bool(ts) and max(ts) >= now - since_delta(since)


def old_label(x):
    pp = (x["pp"] or "").rstrip("/")
    return pp.rsplit("/", 1)[-1] if pp else x["pk"]


filters = sorted(set(names.values()) | set(names)) + ["SongWol QR", "KyungDong", "contracts", "dev", "MES", "Platform", "zzz-없음"]
rows = []
bad = 0
for since in ("24h", "all"):
    base = twin.build(con, now=now, since=None if since == "24h" else since)
    base_inlet = {ln["key"]: sum(1 for p in ln["pipes"] if p["src"].startswith("U:")) for ln in base["lines"]}
    for f in filters:
        E = {k for k in A if in_range(k, since) and (A[k]["pk"] == f or f in names[A[k]["pk"]])}
        O = {k for k in A if in_range(k, since) and (A[k]["pk"] == f or f in old_label(A[k]))}
        r = twin.build(con, now=now, since=None if since == "24h" else since, project=f)
        g = graph.build(con, now=now, since=None if since == "24h" else since, project=f, node_limit=10**6)
        G = {n["data"]["id"] for n in g["nodes"] if n["data"]["kind"] not in ("PROJECT", "EXTERNAL", "UNRESOLVED")
             and n["data"]["id"][:2] in ("S:", "A:", "W:")}
        extra = G - E

        def is_anc(k):
            for e in E:
                cur = A[e]["parent"]
                while cur and cur in A:
                    if cur == k:
                        return True
                    cur = A[cur]["parent"]
            return False
        anc_bad = [k for k in extra if not is_anc(k) or in_range(k, since)]
        tw_lines = {ln["key"] for ln in r["lines"]}
        inlet = {ln["key"]: sum(1 for p in ln["pipes"] if p["src"].startswith("U:")) for ln in r["lines"]}
        inlet_more = sum(max(0, inlet[k] - base_inlet.get(k, 0)) for k in inlet)
        ok = (r["agents_in_scope"] == len(E) and tw_lines == {A[k]["pk"] for k in E} and E <= G and not anc_bad
              and inlet_more == 0 and twin.scope_count(r) == len(E) and twin.overlaps(r) == 0)
        bad += not ok
        if f in ("SongWol QR", "KyungDong", "contracts", "dev", "MES", "Platform", "zzz-없음") or E != O or not ok:
            rows.append({"since": since, "filter": f[:32], "E": len(E), "old_O": len(O), "E-O": len(E - O), "O-E": len(O - E),
                         "twin_scope": r["agents_in_scope"], "twin_lines": len(tw_lines), "G": len(G), "G-E(조상)": len(extra),
                         "anc_bad": len(anc_bad), "inlet_more": inlet_more, "ok": ok})
print(json.dumps({"filters_checked": len(filters) * 2, "fail": bad, "rows": rows}, ensure_ascii=False, indent=0))
sys.exit(1 if bad else 0)
