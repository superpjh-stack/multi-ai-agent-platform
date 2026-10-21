#!/usr/bin/env python
"""QA1 r6 — DEF-QA1-402 / D-28 라인 이름 · T-07 행 순서 무관 재검증.

    uv run python outputs/qa1/r6_names.py --db <DB> --now ISO

  N1 프로젝트마다 D-28 이름을 직접 계산 (모든 에이전트의 project_path 중 (길이, 문자열) 최소 → 마지막 이름, 없으면 project_key)
     ↔ twin since=all 라인 name · D-02 graph since=all PROJECT 노드 label. 경로가 둘 이상인 프로젝트 · 이름이 바뀐 것(r5 「dev」 · 「contracts」) 표시
  N2 T-07: 메모리 사본 3 개 — 행 역순 · 무작위 섞기(시드 20261021 · 7) — 에서 twin 응답(elapsed_ms 뺌)이 원본과 같은가
     since 24h · 7d · all × width 1400 · 360 · 4000 × project (없음 · "Platform" · "SongWol QR")
     + D-02 graph.build(since=all) 응답도 같은가
본문 없음.
"""
import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from r6_twin import d28_names, dt  # noqa: E402

from agentdash.core import graph, twin  # noqa: E402

TABLES = ("agent", "usage_event", "tool_call", "edge", "state_log", "file_touch")

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--now", required=True)
a = ap.parse_args()
now = dt(a.now)
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)

# N1
names = d28_names(con)
paths = {}
for pk, pp in con.execute("SELECT project_key, project_path FROM agent"):
    paths.setdefault(pk, set()).add((pp or "").rstrip("/"))
tw = {ln["key"]: ln["name"] for ln in twin.build(con, now=now, since="all")["lines"]}
gp = {n["data"]["project"]: n["data"]["label"] for n in graph.build(con, now=now, since="all", node_limit=10**6)["nodes"]
      if n["data"]["kind"] == "PROJECT" and n["data"]["project"]}
n1_bad = [pk for pk in names if (pk in tw and tw[pk] != names[pk]) or (pk in gp and gp[pk] != names[pk])]
multi = sorted((names[pk], len([p for p in ps if p])) for pk, ps in paths.items() if len([p for p in ps if p]) > 1)
print(json.dumps({"N1_projects": len(names), "twin_lines_all": len(tw), "graph_projects_all": len(gp),
                  "mismatch": len(n1_bad), "mismatch_keys": [k[:40] for k in n1_bad],
                  "no_path_projects": sum(1 for ps in paths.values() if not any(ps)),
                  "multi_path_projects (이름, 경로 수)": multi}, ensure_ascii=False))


def copy(order):
    mem = sqlite3.connect(":memory:")
    con.backup(mem)
    for t in TABLES:
        cols = [c[1] for c in mem.execute(f"PRAGMA table_info({t})")]
        rows = mem.execute(f"SELECT {','.join(cols)} FROM {t}").fetchall()
        rows = order(rows)
        mem.execute(f"DELETE FROM {t}")
        mem.executemany(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", rows)
    mem.commit()
    return mem


def shuffled(seed):
    def f(rows):
        rows = list(rows)
        random.Random(seed).shuffle(rows)
        return rows
    return f


copies = {"역순": copy(lambda r: r[::-1]), "섞기20261021": copy(shuffled(20261021)), "섞기7": copy(shuffled(7))}
# 사본이 실제로 순서가 다른지 (agent 첫 행 키)
first = {n: c.execute("SELECT agent_key FROM agent ORDER BY rowid LIMIT 1").fetchone()[0][:14] for n, c in copies.items()}
first["원본"] = con.execute("SELECT agent_key FROM agent ORDER BY rowid LIMIT 1").fetchone()[0][:14]
cases = 0
diff = []
for since in (None, "7d", "all"):
    for width in (1400, 360, 4000):
        for proj in (None, "Platform", "SongWol QR"):
            x = twin.build(con, now=now, since=since, width=width, project=proj)
            x.pop("elapsed_ms")
            for n, c in copies.items():
                y = twin.build(c, now=now, since=since, width=width, project=proj)
                y.pop("elapsed_ms")
                cases += 1
                if x != y:
                    diff.append((n, since, width, proj))
g0 = graph.build(con, now=now, since="all", node_limit=10**6)
gdiff = []
for n, c in copies.items():
    g1 = graph.build(c, now=now, since="all", node_limit=10**6)
    for g in (g0, g1):
        g.pop("elapsed_ms", None)
        g.get("stats", {}).pop("ms", None)          # 걸린 시간만 뺀다
    if g0 != g1:
        gdiff.append(n)
print(json.dumps({"N2_cases": cases, "twin_diff": len(diff), "diff_examples": diff[:5], "first_agent_row": first,
                  "graph_all_diff": gdiff}, ensure_ascii=False))
sys.exit(1 if (n1_bad or diff) else 0)
