#!/usr/bin/env python
"""QA1 독립 재집계 (G-04 · G-07 · D-01 · D-02 · D-11). agentdash 코드를 import 하지 않는다.

    .venv/bin/python -I outputs/qa1/recount.py --db data/agentdash-qa1.db [--seed 7] [--home ~/.claude]

원천은 'rb' 로만 연다. 같은 시각 비교를 위해 각 파일은 DB src_file.offset 바이트까지만 읽는다
(DB 가 읽은 지점 — 그 뒤에 붙은 줄은 아직 DB 몫이 아니다). 출력은 숫자 · 키 · 경로뿐 (본문 없음).

독립 규칙 (개발 규칙을 따라 하지 않고 '무엇이 참인가' 로 정의):
  · 토큰 · 도구 호출은 assistant 줄에서. 같은 requestId 는 세션 전체에서 한 번 — 소유자 = 그 requestId 가 처음 나온
    (가장 이른 timestamp, 같으면 얕은 기록: 메인 > 깊이 1 > 깊이 2) 기록. 값은 그 소유 기록 안 output 최대 줄.
  · 도구 호출 = 세션 전체 고유 tool_use.id, 소유자 = 같은 규칙. 작성 파일 = Write · Edit · NotebookEdit(+MultiEdit 별도) 고유 file_path.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

F4 = ("input", "cache_read", "cache_write", "output")
WRITE_TOOLS = {"Write": "file_path", "Edit": "file_path", "NotebookEdit": "notebook_path"}


def lines(p: Path, limit: int | None):
    with open(p, "rb") as fh:
        data = fh.read() if limit is None else fh.read(limit)
    for raw in data.split(b"\n"):
        if raw.strip():
            try:
                d = json.loads(raw)
            except ValueError:
                yield None
                continue
            yield d


def usage4(u: dict) -> dict:
    cc = u.get("cache_creation_input_tokens") or 0
    return {"input": u.get("input_tokens") or 0, "cache_read": u.get("cache_read_input_tokens") or 0,
            "cache_write": cc, "output": u.get("output_tokens") or 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--home", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", help="결과 숫자를 저장할 경로 (outputs/qa1/ 아래)")
    a = ap.parse_args()
    home = Path(a.home)
    proj = home / "projects"
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    offs = {r[0]: r[1] for r in con.execute("SELECT path, offset FROM src_file")}

    # ── 1. 파일 수 (G-04) ───────────────────────────────────────────
    sess_files = sorted(p for p in proj.glob("*/*.jsonl"))
    sub_files = sorted(p for p in proj.glob("*/*/subagents/agent-*.jsonl"))
    wf_files = sorted(p for p in proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl"))
    wf_json = sorted(proj.glob("*/*/workflows/wf_*.json"))
    src_keys = {"SESSION": {f"S:{p.stem}" for p in sess_files},
                "SUBAGENT": {f"A:{p.stem[len('agent-'):]}" for p in sub_files},
                "WORKFLOW_AGENT": {f"A:{p.stem[len('agent-'):]}" for p in wf_files}}
    db_keys = defaultdict(set)
    for k, kind in con.execute("SELECT agent_key, kind FROM agent"):
        db_keys[kind].add(k)
    print("## G-04 원천 파일 수 vs agent 행")
    for kind, ks in src_keys.items():
        d = db_keys.get(kind, set())
        print(f"  {kind:15s} 원천 {len(ks):4d}  DB {len(d):4d}  원천만 {len(ks - d)}  DB만 {len(d - ks)}")
    print(f"  WORKFLOW(S6)    원천 {len(wf_json):4d}  DB {len(db_keys.get('WORKFLOW', set())):4d}")

    # ── 2. 전체 줄 인벤토리 (D-11) ─────────────────────────────────
    all_files = sess_files + sub_files + wf_files
    type_n = Counter()
    usage_types = Counter()      # 줄 종류별 message.usage 보유 수
    tooluse_types = Counter()    # 줄 종류별 message.content tool_use 보유 수
    asst_rids, asst_tus = set(), set()
    other_rids, other_tus = defaultdict(set), defaultdict(set)
    broken = 0
    cc_mismatch = 0              # cache_creation_input_tokens ≠ ephemeral 5m+1h
    nested_usage = Counter()     # message 밖 다른 위치(data.message 등)에 usage 가 있는 줄 종류
    no_rid_asst = Counter()
    per_file = {}
    for p in all_files:
        lim = offs.get(str(p))
        recs = []
        for d in lines(p, lim):
            if d is None:
                broken += 1
                continue
            if not isinstance(d, dict):
                continue
            t = d.get("type")
            type_n[t] += 1
            m = d.get("message") if isinstance(d.get("message"), dict) else None
            if m and isinstance(m.get("usage"), dict):
                usage_types[t] += 1
            blocks = m.get("content") if m and isinstance(m.get("content"), list) else []
            tus = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
            if tus:
                tooluse_types[t] += 1
            if t != "assistant":
                if d.get("requestId"):
                    other_rids[t].add(d["requestId"])
                for b in tus:
                    other_tus[t].add(b.get("id"))
                dd = d.get("data")
                if isinstance(dd, dict) and isinstance(dd.get("message"), dict):
                    mm = dd["message"].get("message") if isinstance(dd["message"].get("message"), dict) else dd["message"]
                    if isinstance(mm, dict) and isinstance(mm.get("usage"), dict):
                        nested_usage[t] += 1
                continue
            if m is None:
                continue
            u = m.get("usage") if isinstance(m.get("usage"), dict) else None
            if u:
                cc = u.get("cache_creation")
                if isinstance(cc, dict):
                    s = (cc.get("ephemeral_5m_input_tokens") or 0) + (cc.get("ephemeral_1h_input_tokens") or 0)
                    if s != (u.get("cache_creation_input_tokens") or 0):
                        cc_mismatch += 1
            rid = d.get("requestId")
            if rid:
                asst_rids.add(rid)
            else:
                no_rid_asst[m.get("model")] += 1
            for b in tus:
                asst_tus.add(b.get("id"))
            recs.append(d)
        per_file[p] = recs
    print("\n## D-11 줄 종류 인벤토리 (DB offset 까지)")
    print(f"  줄 종류 {len(type_n)} · 전체 줄 {sum(type_n.values())} · 깨진 JSON {broken}")
    print(f"  usage 보유 줄 종류: {dict(usage_types)}")
    print(f"  tool_use 보유 줄 종류: {dict(tooluse_types)}")
    for t, s in other_tus.items():
        print(f"  {t}: tool_use id {len(s)} · 그중 assistant 에 없는 것 {len(s - asst_tus)}")
    for t, s in other_rids.items():
        print(f"  {t}: requestId {len(s)} · 그중 assistant 에 없는 것 {len(s - asst_rids)}")
    print(f"  data.message 안 usage (progress 류) 줄 종류: {dict(nested_usage)}")
    print(f"  requestId 없는 assistant 줄 (모델별): {dict(no_rid_asst)}")
    print(f"  cache_creation_input_tokens ≠ ephemeral 5m+1h 인 assistant 줄: {cc_mismatch}")

    # ── 3. 세션별 소유 규칙으로 독립 집계 ───────────────────────────
    def akey(p: Path) -> str:
        return f"S:{p.stem}" if p.parent.parent == proj else f"A:{p.stem[len('agent-'):]}"

    def depth_of(p: Path) -> int:
        if p.parent.parent == proj:
            return 0
        mp = p.with_name(p.name[:-len(".jsonl")] + ".meta.json")
        try:
            return int(json.loads(mp.read_bytes()).get("spawnDepth") or 1)
        except Exception:
            return 1

    by_session = defaultdict(list)
    for p in all_files:
        sid = p.stem if p.parent.parent == proj else p.parts[len(proj.parts) + 1]
        by_session[sid].append(p)

    exp_agent = defaultdict(lambda: dict.fromkeys(F4, 0))
    exp_tools = Counter()
    exp_files = defaultdict(set)
    exp_files_multi = defaultdict(set)
    exp_session = {}
    cross_rid_nonfork = 0
    io_diff_groups = 0
    nonmono = 0
    dup_lines_dropped = 0
    fork_info = {}
    for sid, files in by_session.items():
        order = {p: (0 if p.parent.parent == proj else depth_of(p)) for p in files}
        first = {}   # rid -> (ts, depth, key)
        first_tu = {}
        rid_files = defaultdict(set)
        for p in files:
            k = akey(p)
            for d in per_file[p]:
                m = d.get("message") or {}
                ts = d.get("timestamp") or ""
                rid = d.get("requestId")
                if rid and m.get("model") != "<synthetic>":
                    rid_files[rid].add(k)
                    c = (ts, order[p], k)
                    if rid not in first or c < first[rid]:
                        first[rid] = c
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        c = (ts, order[p], k)
                        if b["id"] not in first_tu or c < first_tu[b["id"]]:
                            first_tu[b["id"]] = c
        best = {}
        for p in files:
            k = akey(p)
            for d in per_file[p]:
                m = d.get("message") or {}
                if m.get("model") == "<synthetic>":
                    continue
                u = m.get("usage") if isinstance(m.get("usage"), dict) else None
                rid = d.get("requestId")
                if not rid or not u:
                    continue
                if first[rid][2] != k:
                    continue
                r = usage4(u)
                key = (k, rid)
                if key in best:
                    dup_lines_dropped += 1
                    o = best[key]
                    if (o["input"], o["cache_read"], o["cache_write"]) != (r["input"], r["cache_read"], r["cache_write"]):
                        io_diff_groups += 1
                    if r["output"] < o["output"]:
                        nonmono += 1
                    if r["output"] > o["output"]:
                        best[key] = r
                else:
                    best[key] = r
                for b in m.get("content") or []:
                    pass
        for (k, rid), r in best.items():
            for f in F4:
                exp_agent[k][f] += r[f]
        for tu, (_ts, _dp, k) in first_tu.items():
            exp_tools[k] += 1
        for p in files:
            k = akey(p)
            for d in per_file[p]:
                for b in (d.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and first_tu.get(b["id"], (0, 0, k))[2] == k:
                        nm = b.get("name")
                        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                        if nm in WRITE_TOOLS and isinstance(inp.get(WRITE_TOOLS[nm]), str):
                            exp_files[k].add(inp[WRITE_TOOLS[nm]])
                        if (nm in WRITE_TOOLS or nm == "MultiEdit") and isinstance(inp.get(WRITE_TOOLS.get(nm, "file_path")), str):
                            exp_files_multi[k].add(inp[WRITE_TOOLS.get(nm, "file_path")])
        for rid, ks in rid_files.items():
            if len(ks) > 1:
                forks = [kk for kk in ks if kk.startswith("A:")]
                is_fork_any = False
                for kk in forks:
                    mp = next((p for p in files if akey(p) == kk), None)
                    if mp is not None:
                        try:
                            is_fork_any |= bool(json.loads(mp.with_name(mp.name[:-6] + ".meta.json").read_bytes()).get("isFork"))
                        except Exception:
                            pass
                if not is_fork_any:
                    cross_rid_nonfork += 1
        exp_session[sid] = {f: sum(exp_agent[akey(p)][f] for p in files) for f in F4}
        exp_session[sid]["tools"] = sum(exp_tools[akey(p)] for p in files)
        exp_session[sid]["agents"] = len(files)

    print("\n## D-01 · D-02 독립 점검")
    print(f"  같은 기록 안 같은 requestId 재등장 줄 {dup_lines_dropped} · 그중 입력/캐시가 다른 묶음 {io_diff_groups} · output 이 줄어든 줄 {nonmono}")
    print(f"  여러 기록에 걸친 requestId 중 포크 아닌 것 {cross_rid_nonfork}")

    # ── 4. DB 대조 (전 에이전트 · 표본 세션) ────────────────────────
    db_agent = {}
    for r in con.execute("SELECT agent_key, SUM(input_tokens), SUM(cache_read), SUM(cache_write_5m+cache_write_1h), "
                         "SUM(output_tokens) FROM usage_event WHERE model IS NOT '<synthetic>' GROUP BY agent_key"):
        db_agent[r[0]] = dict(zip(F4, r[1:]))
    db_tools = dict(con.execute("SELECT agent_key, COUNT(*) FROM tool_call GROUP BY agent_key").fetchall())
    db_files = dict(con.execute("SELECT agent_key, COUNT(DISTINCT path) FROM file_touch WHERE op IN "
                                "('Write','Edit','NotebookEdit') GROUP BY agent_key").fetchall())
    db_files_all = dict(con.execute("SELECT agent_key, COUNT(DISTINCT path) FROM file_touch GROUP BY agent_key").fetchall())
    keys = set(exp_agent) | set(db_agent)
    tok_bad = [k for k in keys if any((exp_agent.get(k) or dict.fromkeys(F4, 0))[f] != ((db_agent.get(k) or {}).get(f) or 0) for f in F4)]
    tool_bad = [k for k in set(exp_tools) | set(db_tools) if exp_tools.get(k, 0) != db_tools.get(k, 0)]
    file_bad = [k for k in set(exp_files) | set(db_files) if len(exp_files.get(k, ())) != db_files.get(k, 0)]
    filem_bad = [k for k in set(exp_files_multi) | set(db_files_all) if len(exp_files_multi.get(k, ())) != db_files_all.get(k, 0)]
    tot_exp = {f: sum(v[f] for v in exp_agent.values()) for f in F4}
    tot_db = {f: sum((v[f] or 0) for v in db_agent.values()) for f in F4}
    print("\n## 전 에이전트 대조 (원천 독립 vs DB)")
    print(f"  토큰 4 칸 합 원천 {tot_exp}")
    print(f"  토큰 4 칸 합 DB   {tot_db}")
    print(f"  토큰 불일치 에이전트 {len(tok_bad)} · 도구 호출 불일치 {len(tool_bad)} (원천 {sum(exp_tools.values())} / DB {sum(db_tools.values())})"
          f" · 작성 파일(W/E/NE) 불일치 {len(file_bad)} · (+MultiEdit) 불일치 {len(filem_bad)}")
    for k in sorted(tok_bad)[:10]:
        print(f"    토큰 {k} 원천 {exp_agent.get(k)} DB {db_agent.get(k)}")
    for k in sorted(tool_bad)[:10]:
        print(f"    도구 {k} 원천 {exp_tools.get(k, 0)} DB {db_tools.get(k, 0)}")
    for k in sorted(file_bad)[:10]:
        print(f"    파일 {k} 원천 {len(exp_files.get(k, ()))} DB {db_files.get(k, 0)}")

    # 표본 10: 무작위 6 + 포크 세션 2 + 워크플로 세션 1 + 최다 에이전트 1
    sess_of = {}
    for r in con.execute("SELECT agent_key, session_id FROM agent"):
        sess_of[r[0]] = r[1]
    fork_sessions = sorted({p.parts[len(proj.parts) + 1] for p in sub_files
                            if json.loads(p.with_name(p.name[:-6] + ".meta.json").read_bytes()).get("isFork")})
    wf_sessions = sorted({p.parts[len(proj.parts) + 1] for p in wf_files})
    rng = random.Random(a.seed)
    pool = sorted(by_session)
    big = max(pool, key=lambda s: len(by_session[s]))
    pick = []
    for s in rng.sample(fork_sessions, min(2, len(fork_sessions))) + wf_sessions[:1] + [big]:
        if s not in pick:
            pick.append(s)
    rest = [s for s in pool if s not in pick]
    pick += rng.sample(rest, 10 - len(pick))
    print(f"\n## G-07 표본 10 세션 (시드 {a.seed}; 포크 세션 {len(fork_sessions)} · 워크플로 세션 {len(wf_sessions)})")
    print("  세션    에이전트  입력  캐시읽기  캐시쓰기  출력  도구  작성파일 | DB 일치")
    sample_out = []
    for s in pick:
        ks = [k for k, ss in sess_of.items() if ss == s and not k.startswith("W:")]
        e = exp_session[s]
        d = {f: sum(((db_agent.get(k) or {}).get(f) or 0) for k in ks) for f in F4}
        dt = sum(db_tools.get(k, 0) for k in ks)
        ef = sum(len(exp_files.get(k, ())) for k in ks)
        dfc = sum(db_files.get(k, 0) for k in ks)
        ok = all(e[f] == d[f] for f in F4) and e["tools"] == dt and ef == dfc
        tag = ("F" if s in fork_sessions else "") + ("W" if s in wf_sessions else "")
        print(f"  {s[:8]}{tag:2s} {e['agents']:3d}  {e['input']} {e['cache_read']} {e['cache_write']} {e['output']}  "
              f"{e['tools']}  {ef} | DB {d['input']} {d['cache_read']} {d['cache_write']} {d['output']} {dt} {dfc}  {'일치' if ok else '불일치'}")
        sample_out.append({"session": s, "tag": tag, "src": e, "db": d, "db_tools": dt, "src_files": ef, "db_files": dfc, "ok": ok})
    if a.json:
        Path(a.json).write_text(json.dumps({"sample": sample_out, "tot_src": tot_exp, "tot_db": tot_db}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
