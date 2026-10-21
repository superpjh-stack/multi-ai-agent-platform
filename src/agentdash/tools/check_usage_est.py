#!/usr/bin/env python
"""V-12 check_usage_est — 추정 열 (G-24, spec.md v0.3 §6.2).

    uv run python src/agentdash/tools/check_usage_est.py [--db 경로] [--no-sync]

원천을 §6.2 정의로 **다시 잰다** (QA1 `outputs/qa1/stream_heuristic.py` 와 같은 정의, 수집기 코드를 쓰지 않는다 · 읽기만):
  · 요청 = 같은 기록 파일 · 같은 requestId 의 `assistant` 줄 (requestId 없는 줄 · `<synthetic>` · usage 없는 줄 제외)
  · 의심 = 기록 output_tokens 최대 < 30 이고 content 블록 json.dumps 길이 합 > 400
  · 추정 = max(ceil((text 글자 + tool_use 입력 json.dumps(ensure_ascii=False) 글자) / 4), output 최대)
  · 원천 파일은 DB `src_file.offset` 까지 읽는다 (DB 가 읽은 지점 — 같은 시각 비교). 길이는 재고 버린다(출력은 숫자만).
  · 모집단 = **세션 안 requestId 한 번** (check_usage_sum 과 같은 독립 규칙 — 수집기 코드 복제 아님): 포크 기록은 부모 줄을
    requestId 그대로 다시 적으므로(D-02) 파일별로 세면 같은 요청이 두 번 들어간다. 소유 = 그 requestId 가 처음 나온 기록
    (가장 이른 timestamp → 얕은 깊이 → 키), 의심 · 추정은 소유 기록의 묶음으로 잰다. 참고로 QA1 파일별 비율도 찍는다.
DB 쪽: 원천 파일이 지금 있는 에이전트의 `usage_event` (requestId 있는 행). 의심 행 = `output_est IS NOT NULL`.
판정 (V-12): |의심 비율 DB − 원천| ≤ 0.5 %p · 위반 0. 위반 =
  ① output_est < output_tokens ② 비의심 행 cost_est_usd ≠ cost_usd ③ cost_usd 있는데 cost_est_usd NULL (또는 반대)
  ④ 같은 (에이전트, requestId) 에서 DB 추정값 ≠ 원천 추정값 — 단 DB output 이 그 기록의 최대보다 큰 행(포크 사본 최종값 반영,
     DEF-QA1-001)은 하한 = DB output 이므로 max(원천 추정, DB output) 과 비교한다.
출력: `G-24  추정 열  PASS|FAIL  의심 DB x.x% · 원천 y.y% · 위반 n …`
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

MAX_OUT, MIN_JSON = 30, 400
TOL_PP = 0.5


def _key(kind: str, p: Path) -> str:
    return f"S:{p.stem}" if kind == "S2" else f"A:{p.name[len('agent-'):-len('.jsonl')]}"


def measure_file(p: Path, limit: int | None) -> dict[str, list]:
    """requestId → [output 최대, json 길이 합, 추정 글자 수, 첫 timestamp]. 원천은 'rb' 로 읽기만."""
    req: dict[str, list] = defaultdict(lambda: [0, 0, 0, None])
    with open(p, "rb") as fh:
        data = fh.read() if limit is None else fh.read(limit)
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("type") != "assistant" or not d.get("requestId"):
            continue
        m = d.get("message") or {}
        if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
            continue
        r = req[d["requestId"]]
        ts = d.get("timestamp") or ""
        r[3] = ts if r[3] is None or ts < r[3] else r[3]
        r[0] = max(r[0], m["usage"].get("output_tokens") or 0)
        blocks = m.get("content") if isinstance(m.get("content"), list) else []
        r[1] += sum(len(json.dumps(b)) for b in blocks)
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "text":
                r[2] += len(b.get("text") or "")
            elif isinstance(b, dict) and b.get("type") == "tool_use":
                r[2] += len(json.dumps(b.get("input"), ensure_ascii=False))
    return req


def _session_depth(kind: str, p: Path) -> tuple[str, int]:
    """(세션 id, 깊이) — 경로 규칙 (spec §2.1) + meta spawnDepth (없으면 1)."""
    if kind == "S2":
        return p.stem, 0
    sid = p.parents[1].name if kind == "S3" else p.parents[3].name
    meta = p.with_name(p.name[:-len(".jsonl")] + ".meta.json")
    dep = 1
    if meta.exists():
        try:
            dep = int(json.loads(meta.read_bytes()).get("spawnDepth") or 1)
        except (ValueError, TypeError, AttributeError):
            dep = 1
    return sid, dep


def _est(o: int, j: int, c: int) -> int | None:
    return max(-(-c // 4), o) if (o < MAX_OUT and j > MIN_JSON) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--no-sync", action="store_true")
    a = ap.parse_args(argv)
    s = _settings.get()
    db = Path(a.db) if a.db else s.db_path
    if not db.exists():
        print(f"G-24  추정 열  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    con = conn.connect(db)
    from agentdash.collect import ingest

    if not a.no_sync:       # 원천이 계속 자라므로 같은 시각에 맞춘다 (DB 에만 쓴다)
        ingest.ingest_all(con)
        con.commit()
    offsets = {r[0]: r[1] for r in con.execute("SELECT path, offset FROM src_file")}
    src: dict[tuple[str, str], int | None] = {}        # (agent_key, requestId) → 원천 추정 (None = 비의심) — 소유 기록만
    src_max: dict[tuple[str, str], int] = {}
    keys: set[str] = set()
    occ: dict[tuple[str, str], list] = defaultdict(list)   # (세션, requestId) → [((ts, 깊이, 키), (o, j, c))]
    per_file_n = per_file_sus = 0
    for kind, p in ingest.source_files(s.claude_home):
        if kind not in ("S2", "S3", "S5"):
            continue
        k = _key(kind, p)
        keys.add(k)
        sid, dep = _session_depth(kind, p)
        for rid, (o, j, c, ts) in measure_file(p, offsets.get(str(p))).items():
            occ[(sid, rid)].append(((ts or "", dep, k), (o, j, c)))
            per_file_n += 1
            per_file_sus += _est(o, j, c) is not None
    for (_sid, rid), L in occ.items():
        (_ts, _dep, k), (o, j, c) = min(L)
        src[(k, rid)] = _est(o, j, c)
        src_max[(k, rid)] = o
    n_src = len(src)
    sus_src = sum(v is not None for v in src.values())

    n_db = sus_db = archived = 0
    bad = defaultdict(int)
    for k, rid, o, oe, c, ce in con.execute(
            "SELECT agent_key, request_id, output_tokens, output_est, cost_usd, cost_est_usd FROM usage_event "
            "WHERE request_id NOT LIKE 'uuid:%'"):
        if oe is not None and oe < (o or 0):
            bad["① 추정<기록"] += 1
        if oe is None and (c is None) != (ce is None):
            bad["③ NULL 불일치"] += 1
        elif oe is None and c is not None and abs(c - ce) > 1e-12:
            bad["② 비의심 비용≠기록"] += 1
        elif oe is not None and (c is None) != (ce is None):
            bad["③ NULL 불일치"] += 1
        if k not in keys:
            archived += 1           # 원천에서 지워진 기록 (D-22) — 비율 비교에서 뺀다
            continue
        n_db += 1
        sus_db += oe is not None
        if (k, rid) in src:
            want = src[(k, rid)]
            if want is not None and (o or 0) > src_max[(k, rid)]:
                want = max(want, o or 0)       # 포크 사본 최종값 반영 행 (DEF-QA1-001) — 하한 = DB output
            if want != oe:
                bad["④ 추정값≠원천"] += 1
    con.close()
    p_db = 100 * sus_db / n_db if n_db else 0.0
    p_src = 100 * sus_src / n_src if n_src else 0.0
    diff = abs(p_db - p_src)
    nbad = sum(bad.values())
    ok = n_src > 0 and diff <= TOL_PP and nbad == 0
    detail = (f"의심 DB {p_db:.1f}% ({sus_db}/{n_db}) · 원천 {p_src:.1f}% ({sus_src}/{n_src}) · 차 {diff:.2f}%p "
              f"(≤ {TOL_PP}) · 위반 {nbad}")
    if bad:
        detail += " (" + " · ".join(f"{k} {v}" for k, v in sorted(bad.items())) + ")"
    pf = 100 * per_file_sus / per_file_n if per_file_n else 0.0
    detail += (f" · 원천 삭제 보관 행 {archived} 비교 제외 · 참고 QA1 파일별 {pf:.1f}% ({per_file_sus}/{per_file_n}, "
               f"포크 사본 중복 포함)")
    if n_src == 0:
        detail += " · 원천 요청 0"
    print(f"G-24  추정 열  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
