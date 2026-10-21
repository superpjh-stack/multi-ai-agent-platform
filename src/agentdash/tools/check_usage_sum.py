#!/usr/bin/env python
"""V-03 check_usage_sum — 표본 세션 10 개의 토큰: 원천 직접 합산 ↔ DB (G-07).

    uv run python src/agentdash/tools/check_usage_sum.py [--db 경로] [--n 10] [--no-sync]

원천 직접 합산은 수집기 규칙(포크 사본 제외 목록 · skip_uuids · skip_rids)을 **복제하지 않고** 세션 단위로 따로 센다
(웨이브 D — DEF-QA1-001 을 수집기와 같은 규칙으로 가리던 문제, QA1 `outputs/qa1/fork_final.py` 방식). 원천은 읽기만:
  · 세션 폴더의 모든 기록(메인 · subagents · workflows) 의 `type == "assistant"` 줄 (D-11), DB `src_file.offset` 까지
    (DB 가 읽은 지점 — 같은 시각 비교) · `message.model == "<synthetic>"` 제외
  · requestId 하나는 **세션 전체에서 한 번**. 소유 = 그 requestId 가 처음 나온 기록(가장 이른 timestamp, 같으면 얕은 깊이,
    그다음 키), 값 = 세션의 모든 기록(포크 사본 포함)을 통틀어 output_tokens 가 가장 큰 줄 (D-01 의 최종본)
DB 쪽은 `usage.totals(세션, descendants=True)` (= 자기 + 자손). 그리고
  · 세션 합계 = 자기 + Σ 자손 각자 · 에이전트별 소유 합 = DB 에이전트 행 (불일치 에이전트 수)
  · 한 세션 안에서 같은 requestId 가 두 에이전트에 들어간 수 = 0 (이중 계산 없음)
표본: **원천 파일이 지금 다 있는 세션**(메인 기록이 있고, src_file 에 기록된 그 세션 에이전트들의 기록 경로가 전부 있음) 중
      에이전트가 많은 세션 5 + 나머지에서 고정 시드 무작위 5 (워크플로 · 포크 세션이 들어가게). Claude Code 가 지운 기록의
      세션은 DB 가 숫자를 보관할 뿐(problem.md Q10 · decisions.md D-22) 원천 직접 합을 낼 수 없으므로 후보에서 빼고 수를 찍는다.
출력: `G-07  토큰 합 (<세션 앞 8 자>)  PASS|FAIL  …` 10 행 + 요약 1 행.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

FIELDS = ("input_tokens", "cache_read", "cache_write", "output_tokens")


def _read(p: Path, limit: int | None) -> list[dict]:
    out = []
    with open(p, "rb") as fh:
        data = fh.read() if limit is None else fh.read(limit)
    for raw in data.split(b"\n"):
        if raw.strip():
            try:
                out.append(json.loads(raw))
            except ValueError:
                pass       # 깨진 줄 · 반쪽 줄은 V-07 이 센다
    return out


def _row(u: dict) -> dict:
    cc = u.get("cache_creation") or {}
    cw = (cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0)) if cc else \
        u.get("cache_creation_input_tokens", 0)
    return {"input_tokens": u.get("input_tokens", 0) or 0, "cache_read": u.get("cache_read_input_tokens", 0) or 0,
            "cache_write": cw or 0, "output_tokens": u.get("output_tokens", 0) or 0}


def session_files(sess_jsonl: Path) -> list[tuple[str, int, Path]]:
    """(agent_key, 깊이, 경로) — 메인 0 · 서브에이전트 meta spawnDepth(없으면 1)."""
    sess_dir = sess_jsonl.with_suffix("")
    out = [(f"S:{sess_jsonl.stem}", 0, sess_jsonl)]
    for f in sorted(sess_dir.glob("subagents/agent-*.jsonl")) + sorted(sess_dir.glob("subagents/workflows/wf_*/agent-*.jsonl")):
        meta = f.with_name(f.name[:-len(".jsonl")] + ".meta.json")
        dep = 1
        if meta.exists():
            try:
                dep = int(json.loads(meta.read_bytes()).get("spawnDepth") or 1)
            except (ValueError, TypeError):
                dep = 1
        out.append((f"A:{f.stem[len('agent-'):]}", dep, f))
    return out


SUSPECT_OUT, SUSPECT_LEN = 30, 400     # D-17 의심 요청: 기록 output 최대 < 30 이면서 content 블록 JSON 길이 > 400 (길이만)
suspect: dict[str, list[int]] = {"main": [0, 0], "sub": [0, 0]}   # 종류 → [요청, 의심]


def source_session_sum(sess_jsonl: Path, offsets: dict[str, int]) -> tuple[dict, dict, dict, int]:
    """→ (세션 합, 에이전트별 소유 합, 줄 단순 합, 파일 수). 세션 단위 독립 규칙 (위 docstring)."""
    occ: dict[str, list] = defaultdict(list)
    req: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])     # (기록, requestId) → [output 최대, 길이 합]
    raw = dict.fromkeys(FIELDS, 0)
    files = session_files(sess_jsonl)
    for key, dep, f in files:
        if not f.exists():
            continue
        for d in _read(f, offsets.get(str(f))):
            if d.get("type") != "assistant":
                continue
            m = d.get("message") or {}
            if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
                continue
            r = _row(m["usage"])
            for k in FIELDS:
                raw[k] += r[k]
            rid = d.get("requestId") or f"uuid:{key}:{d.get('uuid')}"
            occ[rid].append(((d.get("timestamp") or "", dep, key), r))
            q = req[(key, rid)]
            q[0] = max(q[0], r["output_tokens"])
            q[1] += sum(len(json.dumps(b)) for b in (m.get("content") or []))     # 길이만 — 내용은 보지 않는다
    for (key, _rid), (o, ln) in req.items():
        g = suspect["main" if key.startswith("S:") else "sub"]
        g[0] += 1
        g[1] += o < SUSPECT_OUT and ln > SUSPECT_LEN
    tot = dict.fromkeys(FIELDS, 0)
    per: dict[str, dict] = defaultdict(lambda: dict.fromkeys(FIELDS, 0))
    for L in occ.values():
        owner = min(x[0] for x in L)[2]
        best = max(L, key=lambda x: x[1]["output_tokens"])[1]
        for k in FIELDS:
            tot[k] += best[k]
            per[owner][k] += best[k]
    return tot, dict(per), raw, len(files)


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

    offsets = {r[0]: r[1] for r in con.execute("SELECT path, offset FROM src_file")}
    all_sess = [(r[0], r[1], r[2]) for r in con.execute(
        "SELECT a.session_id, a.project_key, (SELECT COUNT(*) FROM agent b WHERE b.session_id=a.session_id) n "
        "FROM agent a WHERE a.kind='SESSION' AND EXISTS (SELECT 1 FROM usage_event u WHERE u.agent_key=a.agent_key) "
        "ORDER BY n DESC, a.session_id")]
    from agentdash.tools.check_counts import recorded_paths

    recorded = recorded_paths(con, s.claude_home)
    members: dict[str, list[str]] = defaultdict(list)
    for k, sid in con.execute("SELECT agent_key, session_id FROM agent"):
        members[sid].append(k)
    sess, gone_all, gone_part = [], 0, 0
    for sid, pk, n in all_sess:
        paths = [s.claude_home / "projects" / pk / f"{sid}.jsonl"]
        paths += [p for k in members[sid] for p in recorded.get(k, [])]
        present = [p.exists() for p in paths]
        if all(present):
            sess.append((sid, pk, n))
        elif any(present):
            gone_part += 1
        else:
            gone_all += 1
    half = a.n // 2
    rule = (f"# 표본 선정 — 원천 파일이 지금 다 있는 세션 후보 {len(sess)} (토큰 있는 세션 {len(all_sess)} 중 제외 "
            f"{gone_all + gone_part}: 원천 전부 지움 {gone_all} · 일부 지움 {gone_part} — DB 보관 숫자, Q10 · D-22) · "
            f"에이전트 많은 순 {half} + 나머지에서 시드 20261017 무작위 {a.n - half}")
    if len(sess) < a.n:
        print(f"G-07  토큰 합  FAIL  원천 파일이 지금 다 있는 세션 {len(sess)} < 표본 {a.n}")
        print(rule)
        return 1
    sample = sess[:half] + random.Random(20261017).sample(sess[half:], a.n - half)
    ok_all = True
    dedupe_gain = 0
    for sid, pk, n_agents in sample:
        key = f"S:{sid}"
        jsonl = s.claude_home / "projects" / pk / f"{sid}.jsonl"
        src, per, raw, nfiles = source_session_sum(jsonl, offsets)
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
        agent_bad = 0
        for k in set(per) | {key, *kids}:
            t = U.totals(con, k)
            want = per.get(k, dict.fromkeys(FIELDS, 0))
            agent_bad += any(t[f] != want[f] for f in FIELDS)
        ok = same and sums and dup == 0 and agent_bad == 0
        ok_all &= ok
        dedupe_gain += raw["output_tokens"] - src["output_tokens"]
        diff = "" if same else " · 차이 " + ",".join(f"{f} {dbt[f] - src[f]:+d}" for f in FIELDS if src[f] != dbt[f])
        print(f"G-07  토큰 합 ({sid[:8]})  {'PASS' if ok else 'FAIL'}  원천 출력 {src['output_tokens']} · DB {dbt['output_tokens']} "
              f"· 입력 {src['input_tokens']}/{dbt['input_tokens']} · 캐시읽기 {src['cache_read']}/{dbt['cache_read']} "
              f"· 캐시쓰기 {src['cache_write']}/{dbt['cache_write']} · 자기+자손 {'=' if sums else '≠'} · 에이전트 {n_agents} "
              f"· 파일 {nfiles} · 에이전트별 소유 불일치 {agent_bad} · 세션 안 requestId 중복 {dup}{diff}")
    print(rule)
    print(f"# 표본 {len(sample)} 세션 · requestId 중복 제거(세션 단위 · 최종본)로 뺀 출력 토큰 {dedupe_gain} (D-01 근거) · "
          f"규칙 = 세션 안 requestId 한 번 · 소유 = 처음 나온 기록 · 값 = 사본 포함 output 최대 (수집기 규칙 복제 아님)")
    pct = {k: (100 * v[1] / v[0] if v[0] else 0.0) for k, v in suspect.items()}
    print(f"# D-17 (확정 — 추정 열은 G-24) 표본 안 출력 과소 의심 요청 (output < {SUSPECT_OUT} · content 길이 > {SUSPECT_LEN}): "
          f"메인 {suspect['main'][1]}/{suspect['main'][0]} ({pct['main']:.1f}%) · "
          f"서브·워크플로 {suspect['sub'][1]}/{suspect['sub'][0]} ({pct['sub']:.1f}%) — G-07 판정과 무관(숫자는 원천 그대로)")
    con.close()
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
