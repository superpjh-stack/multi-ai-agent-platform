#!/usr/bin/env python
"""V-03 check_usage_sum — 표본 세션 10 개의 토큰: 원천 직접 합산 ↔ DB (G-07).

    uv run python src/agentdash/tools/check_usage_sum.py [--db 경로] [--n 10] [--no-sync]

원천 직접 합산은 수집기 코드를 쓰지 않고 이 파일 안에서 따로 센다 (원천은 읽기만):
  · 세션 폴더의 모든 기록(메인 · subagents · workflows) 의 `type == "assistant"` 줄 (D-11)
  · `message.model == "<synthetic>"` 제외 · 파일마다 같은 requestId 는 한 번, output_tokens 가 가장 큰 줄 (D-01)
  · isFork 기록의 부모 사본(부모 파일에 같은 uuid · 같은 assistant requestId) 제외 (D-02 가설 반박)
DB 쪽은 `usage.totals(세션, descendants=True)` (= 자기 + 자손). 그리고
  · 세션 합계 = 자기 + Σ 자손 각자 (G7) · 한 세션 안에서 같은 requestId 가 두 에이전트에 들어간 수 = 0 (이중 계산 없음)
표본: 에이전트가 많은 세션 5 + 나머지에서 고정 시드 무작위 5 (워크플로 · 포크 세션이 들어가게).
출력: `G-07  토큰 합 (<세션 앞 8 자>)  PASS|FAIL  …` 10 행 + 요약 1 행.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

FIELDS = ("input_tokens", "cache_read", "cache_write", "output_tokens")


def _read(p: Path) -> list[dict]:
    out = []
    with open(p, "rb") as fh:
        for raw in fh:
            if raw.strip():
                try:
                    out.append(json.loads(raw))
                except ValueError:
                    pass       # 깨진 줄은 V-07 이 센다
    return out


def file_sum(p: Path, skip_uuids: set, skip_rids: set) -> tuple[dict, dict, set]:
    best: dict[str, dict] = {}
    raw_sum = dict.fromkeys(FIELDS, 0)
    for d in _read(p):
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        if m.get("model") == "<synthetic>":
            continue
        if d.get("uuid") in skip_uuids or d.get("requestId") in skip_rids:
            continue
        u = m.get("usage") or {}
        cc = u.get("cache_creation") or {}
        cw = (cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0)) if cc else \
            u.get("cache_creation_input_tokens", 0)
        row = {"input_tokens": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
               "cache_write": cw, "output_tokens": u.get("output_tokens", 0)}
        for k in FIELDS:
            raw_sum[k] += row[k]
        rid = d.get("requestId") or f"uuid:{d.get('uuid')}"
        if rid not in best or row["output_tokens"] > best[rid]["output_tokens"]:
            best[rid] = row
    tot = dict.fromkeys(FIELDS, 0)
    for r in best.values():
        for k in FIELDS:
            tot[k] += r[k]
    return tot, raw_sum, set(best)


def source_session_sum(sess_jsonl: Path) -> tuple[dict, dict, int]:
    sess_dir = sess_jsonl.with_suffix("")
    files = [sess_jsonl] + sorted(sess_dir.glob("subagents/agent-*.jsonl")) + \
        sorted(sess_dir.glob("subagents/workflows/wf_*/agent-*.jsonl"))
    tot = dict.fromkeys(FIELDS, 0)
    raw = dict.fromkeys(FIELDS, 0)
    for f in files:
        if not f.exists():
            continue
        skip_u, skip_r = set(), set()
        meta = f.with_name(f.name[:-len(".jsonl")] + ".meta.json")
        if meta.exists():
            md = json.loads(meta.read_bytes())
            if md.get("isFork"):
                par = (sess_dir / "subagents" / f"agent-{md['parentAgentId']}.jsonl") if md.get("parentAgentId") \
                    else sess_jsonl
                if par.exists():
                    for d in _read(par):
                        if d.get("uuid"):
                            skip_u.add(d["uuid"])
                        if d.get("type") == "assistant" and d.get("requestId"):
                            skip_r.add(d["requestId"])
        t, r, _ = file_sum(f, skip_u, skip_r)
        for k in FIELDS:
            tot[k] += t[k]
            raw[k] += r[k]
    return tot, raw, len(files)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--no-sync", action="store_true")
    a = ap.parse_args(argv)
    s = _settings.get()
    db = Path(a.db) if a.db else s.db_path
    if not db.exists():
        print(f"G-07  토큰 합  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    con = conn.connect(db)
    if not a.no_sync:   # 원천이 계속 자라므로 같은 시각에 맞춘다 (DB 에만 쓴다)
        from agentdash.collect import ingest

        ingest.ingest_all(con)
        con.commit()
    from agentdash.core import usage as U

    sess = [(r[0], r[1], r[2]) for r in con.execute(
        "SELECT a.session_id, a.project_key, (SELECT COUNT(*) FROM agent b WHERE b.session_id=a.session_id) n "
        "FROM agent a WHERE a.kind='SESSION' AND EXISTS (SELECT 1 FROM usage_event u WHERE u.agent_key=a.agent_key) "
        "ORDER BY n DESC, a.session_id")]
    if len(sess) < a.n:
        print(f"G-07  토큰 합  FAIL  토큰 있는 세션 {len(sess)} < 표본 {a.n}")
        return 1
    half = a.n // 2
    sample = sess[:half] + random.Random(20261017).sample(sess[half:], a.n - half)
    ok_all = True
    dedupe_gain = 0
    for sid, pk, n_agents in sample:
        key = f"S:{sid}"
        jsonl = s.claude_home / "projects" / pk / f"{sid}.jsonl"
        src, raw, nfiles = source_session_sum(jsonl)
        dbt = U.totals(con, key, descendants=True)
        me = U.totals(con, key)
        kids = U.descendants(con, key)
        parts = dict(me)
        for k in kids:
            t = U.totals(con, k)
            for f in FIELDS:
                parts[f] += t[f]
        dup = con.execute(
            "SELECT COUNT(*) FROM (SELECT request_id FROM usage_event u JOIN agent g ON g.agent_key=u.agent_key "
            "WHERE g.session_id=? GROUP BY request_id HAVING COUNT(*)>1)", (sid,)).fetchone()[0]
        same = all(src[f] == dbt[f] for f in FIELDS)
        sums = all(parts[f] == dbt[f] for f in FIELDS)
        ok = same and sums and dup == 0
        ok_all &= ok
        dedupe_gain += raw["output_tokens"] - src["output_tokens"]
        diff = "" if same else " · 차이 " + ",".join(f"{f} {dbt[f] - src[f]:+d}" for f in FIELDS if src[f] != dbt[f])
        print(f"G-07  토큰 합 ({sid[:8]})  {'PASS' if ok else 'FAIL'}  원천 출력 {src['output_tokens']} · DB {dbt['output_tokens']} "
              f"· 입력 {src['input_tokens']}/{dbt['input_tokens']} · 캐시읽기 {src['cache_read']}/{dbt['cache_read']} "
              f"· 캐시쓰기 {src['cache_write']}/{dbt['cache_write']} · 자기+자손 {'=' if sums else '≠'} · 에이전트 {n_agents} "
              f"· 파일 {nfiles} · 세션 안 requestId 중복 {dup}{diff}")
    print(f"# 표본 {len(sample)} 세션 · requestId 중복 제거로 뺀 출력 토큰 {dedupe_gain} (D-01 근거)")
    con.close()
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
