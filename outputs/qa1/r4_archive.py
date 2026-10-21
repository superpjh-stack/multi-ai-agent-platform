#!/usr/bin/env python
"""QA1 r4 — D-22 「원천 삭제 보관」 분류 독립 재계산 (G-04 · G-07 회귀). agentdash 를 import 하지 않는다.

    .venv/bin/python -I outputs/qa1/r4_archive.py --db <DB 사본> [--home ~/.claude]

보관 = DB 에만 있는 키 중 그 키의 기록(jsonl) 경로가 src_file 에 있고 그 경로가 전부 지금 디스크에 없음 (os.path.exists 만).
출력: 종류별 원천 · DB · 빠짐 · DB 전용 · 보관 · 확인 못 함, 보관 키의 기록 mtime 범위 · 세션 단위 영향. 숫자 · 키 앞 10 자만.
"""
import argparse, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--home", default=os.path.expanduser("~/.claude"))
a = ap.parse_args()
proj = Path(a.home) / "projects"
con = sqlite3.connect(Path(a.db).resolve().as_uri() + "?mode=ro", uri=True)
src = {"SESSION": {"S:" + p.stem for p in proj.glob("*/*.jsonl")},
       "SUBAGENT": {"A:" + p.name[6:-6] for p in proj.glob("*/*/subagents/agent-*.jsonl")},
       "WORKFLOW_AGENT": {"A:" + p.name[6:-6] for p in proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl")}}
rec: dict[str, list[tuple[str, float]]] = {}
for path, mtime in con.execute("SELECT path, mtime FROM src_file WHERE path LIKE '%.jsonl'"):
    p = Path(path)
    try:
        rel = p.relative_to(proj).parts
    except ValueError:
        continue
    if len(rel) == 2:
        k = "S:" + p.stem
    elif p.name.startswith("agent-") and "subagents" in rel:
        k = "A:" + p.name[6:-6]
    else:
        continue
    rec.setdefault(k, []).append((path, mtime))
total_arch = set()
for kind, sk in src.items():
    dbk = {r[0] for r in con.execute("SELECT agent_key FROM agent WHERE kind=?", (kind,))}
    miss, extra = sk - dbk, dbk - sk
    arch = {k for k in extra if rec.get(k) and not any(os.path.exists(p) for p, _ in rec[k])}
    unk = extra - arch
    no_path = {k for k in unk if not rec.get(k)}
    still = unk - no_path
    total_arch |= arch
    print(f"{kind:15s} 원천 {len(sk):4d} · DB {len(dbk):4d} · 빠짐 {len(miss)} · DB 전용 {len(extra)} · 보관 {len(arch)} · "
          f"확인 못 함 {len(unk)} (경로 기록 없음 {len(no_path)} · 경로 남아 있음 {len(still)})")
    # 거꾸로: 원천에 있는 키인데 src_file 경로가 사라진 것 (경로 바뀜) — 보관으로 세면 안 되는 쪽
    moved = {k for k in (sk & dbk) if rec.get(k) and not any(os.path.exists(p) for p, _ in rec[k])}
    print(f"{'':15s} 원천에도 있는데 기록 경로가 전부 없음 (경로 이동) {len(moved)}")
mt = [m for k in total_arch for _, m in rec[k] if m]
if mt:
    f = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%d")
    print(f"보관 키 {len(total_arch)} · 기록 경로 {sum(len(rec[k]) for k in total_arch)} · mtime {f(min(mt))} ~ {f(max(mt))}")
sess = {}
for k, s in con.execute("SELECT agent_key, session_id FROM agent"):
    sess.setdefault(s, []).append(k)
part = full = 0
for s, ks in sess.items():
    n = sum(1 for k in ks if k in total_arch)
    if n == len(ks) and n:
        full += 1
    elif n:
        part += 1
print(f"세션 단위: 전부 지움 {full} · 일부 지움 {part}")
ue = con.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0), COALESCE(SUM(output_tokens),0) FROM usage_event WHERE agent_key IN (%s)"
                 % ",".join("?" * len(total_arch)), sorted(total_arch)).fetchone() if total_arch else (0, 0, 0)
print(f"보관 키의 usage_event 행 {ue[0]} · 비용 ${ue[1]:.4f} · 출력 {ue[2]} (DB 에 남아 화면에 나온다 — Q10)")
