#!/usr/bin/env python
"""QA1 r2 — D-20 `agent.last_event_at` 독립 재계산 · 영향 범위. agentdash 를 import 하지 않는다.
    .venv/bin/python -I outputs/qa1/r2_last_event.py --db data/agentdash-qa1.db
기록마다 (DB src_file.offset 까지): 줄 종류별 top-level timestamp 의 꼴(정규식 모양) · 최대 시각.
  A = 모든 줄 최대 · B = assistant/user 최대 · 포크 사본(부모 기록에 같은 uuid) 제외 근사.
DB last_event_at 과 A 비교, A 를 정한 줄 종류 분포, A − B 분포, last_event_at 이 DB 의 마지막 tool_call/usage 보다 얼마나 늦은지.
원천 'rb' · DB mode=ro. 숫자 · 키 · 줄 종류 이름만.
"""
import argparse, json, os, re, sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); a = ap.parse_args()
proj = Path(os.path.expanduser("~/.claude/projects"))
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
offs = dict(con.execute("SELECT path, offset FROM src_file"))
files = (sorted(proj.glob("*/*.jsonl")) + sorted(proj.glob("*/*/subagents/agent-*.jsonl"))
         + sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl")))


def shape(ts):
    return re.sub(r"\d", "9", ts) if isinstance(ts, str) else type(ts).__name__


def read(p):
    lim = offs.get(str(p))
    with open(p, "rb") as fh:
        data = fh.read() if lim is None else fh.read(lim)
    for raw in data.split(b"\n"):
        if raw.strip():
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if isinstance(d, dict):
                yield d


def P(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


shapes = Counter(); none_ts = Counter()
db = {r[0]: r[1:] for r in con.execute("SELECT agent_key, last_event_at, ended_at, state, kind FROM agent")}
last_act = dict(con.execute("SELECT agent_key, MAX(at) FROM (SELECT agent_key, at FROM tool_call UNION ALL "
                            "SELECT agent_key, at FROM usage_event UNION ALL SELECT agent_key, result_at FROM tool_call) "
                            "GROUP BY agent_key"))
eqA = eqB = neither = 0; decider = Counter(); gapAB = []; neither_keys = []
later_than_act = []
for p in files:
    k = f"S:{p.stem}" if p.parent.parent == proj else f"A:{p.stem[6:]}"
    par = None
    mp = p.with_name(p.name[:-6] + ".meta.json")
    if mp.exists():
        try:
            m = json.loads(mp.read_bytes())
            if m.get("isFork"):
                sd = p.parent.parent
                pf = (sd / "subagents" / f"agent-{m['parentAgentId']}.jsonl") if m.get("parentAgentId") else sd.parent / f"{sd.name}.jsonl"
                par = {d.get("uuid") for d in read(pf)} if pf.exists() else set()
        except Exception:
            pass
    A = B = None; At = None
    for d in read(p):
        ts = d.get("timestamp"); t = d.get("type")
        if ts is None:
            none_ts[t] += 1
            continue
        shapes[(t if t in ("assistant", "user") else "기타", shape(ts))] += 1
        if par is not None and d.get("uuid") in par:
            continue
        if not isinstance(ts, str):
            continue
        if A is None or ts > A:
            A, At = ts, t
        if t in ("assistant", "user") and (B is None or ts > B):
            B = ts
    le = db.get(k, (None,))[0]
    if le == A:
        eqA += 1; decider[At] += 1
    elif le == B:
        eqB += 1
    else:
        neither += 1; neither_keys.append(k)
    if A and B:
        gapAB.append((P(A) - P(B)).total_seconds())
    la = last_act.get(k)
    if le and la:
        later_than_act.append(((P(le) - P(la)).total_seconds(), k, db[k][2]))
print(f"기록 {len(files)} · DB last_event_at = 모든 줄 최대 {eqA} · = assistant/user 최대(만) {eqB} · 둘 다 아님 {neither}")
print(f"  둘 다 아님(handback 꼬리 제외 등) 키 앞 10: {[x[:12] for x in neither_keys[:10]]}")
print(f"  모든 줄 최대를 정한 줄 종류: {dict(decider.most_common())}")
print(f"timestamp 꼴: {dict(shapes)}")
print(f"timestamp 없는 줄 종류: {dict(none_ts.most_common(12))}")
g = sorted(gapAB)
print(f"A−B (초) 분포: >0 {sum(1 for x in g if x > 0)} · >60 {sum(1 for x in g if x > 60)} · >300 {sum(1 for x in g if x > 300)} · "
      f">3600 {sum(1 for x in g if x > 3600)} · 최대 {g[-1] if g else 0:.0f}")
lt = sorted(later_than_act, reverse=True)
print(f"last_event_at − DB 마지막 활동(usage·tool·result) (초): >300 {sum(1 for x in lt if x[0] > 300)} · >3600 "
      f"{sum(1 for x in lt if x[0] > 3600)} · <0 {sum(1 for x in lt if x[0] < 0)}")
for s, k, st in lt[:8]:
    print(f"  {k[:14]} +{s:.0f}s 상태 {st}")
