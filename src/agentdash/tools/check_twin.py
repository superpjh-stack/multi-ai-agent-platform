#!/usr/bin/env python
"""V-17 check_twin — 트윈 API (`twin.build` = `GET /api/v1/twin`) ↔ DB 직접 대조 (G-32, spec.md v0.4 §5.4 · §8 · §10).

    uv run python src/agentdash/tools/check_twin.py [--db 경로] [--since 24h] [--project 이름] [--width px] [--now ISO]

실제 DB(기본 settings.db_path = AGENTDASH_DB)에서 `twin.build` 를 한 번 부르고 같은 now 로 대조한다:
  · 누적: 설비마다 out_total · out_est_total · cost_est_usd = `usage.totals(con, key)` (자기 몫, 비용 차 ≤ $1e-6)
  · 스파크: `usage.spark` 를 쓰지 않는 독립 계산 — 범위 안 usage_event 를 전부 읽어 `at` 을 datetime 으로 바꾼 뒤
    UTC 분 단위로 COALESCE(output_est, output_tokens) 합 (`<synthetic>` 제외, 지금 분이 마지막 칸, 30 칸) ↔ 설비 spark
  · 겹침: `twin.overlaps` + 이 도구의 독립 쌍 검사(설비 · 반입구 상자 전체, 라인 상자 전체 — 닿기만 하면 0) 중 큰 값
  · 범위: 칸 수 + 접힌 수(`twin.scope_count`) = agents_in_scope = 이 도구가 agent 테이블에서 직접 센 범위 안 수
    (살아 있는 것(DONE · FAILED 아님) + max(last_event_at, started_at) ≥ since, 프로젝트 필터 = 라인 단위 — project_key 같음
    또는 라인 이름(D-28 을 이 도구가 따로 구현한 `direct_line_names`)에 포함, DEF-QA1-401) · 설비 키 중복 0
  · 시간 키: 설비 elapsed_s · last_ago_s · ended_ago_s ↔ agent 행 직접 (DEF-QA2-401) · 끝난 설비 tool · target = null
  · 격자 (T-08): grid.width = --width · cols = 들어가는 최대 열 수 · rows · 라인 상자 x · y · h 를 따로 계산해 대조
  · TEXT > 300: 응답 안의 모든 문자열 길이 · 응답 시간 elapsed_ms ≤ 300
출력: `G-32  트윈 API  PASS|FAIL  설비 n · 라인 n · 접힘 n+n · 누적 불일치 n · 스파크 불일치 n · 시간 키 불일치 n · 격자 불일치 n · 겹침 n · TEXT>300 n · n ms`
  (접힘 = 설비 · 반입구 folded 합 + 접힌 라인 hidden 합)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agentdash import settings as _settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

MAX_MS = 300.0
TEXT_MAX = 300
COST_TOL = 1e-6
FINAL = ("DONE", "FAILED")


def _dt(ts: str) -> datetime:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def direct_spark(con, keys: set[str], now: datetime, minutes: int) -> dict[str, list[int]]:
    """usage.spark 와 독립: 행마다 datetime 으로 바꿔 UTC 분 칸에 더한다."""
    end = now.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)
    out = {k: [0] * minutes for k in keys}
    for k, at, model, o, e in con.execute("SELECT agent_key, at, model, output_tokens, output_est FROM usage_event"):
        if k not in out or not at or model == "<synthetic>":
            continue
        t = _dt(at)
        if not (start <= t < end):
            continue
        out[k][int((t - start).total_seconds() // 60)] += (e if e is not None else (o or 0))
    return out


def direct_line_names(con) -> dict[str, str]:
    """D-28 독립 구현 (graph.project_names 를 부르지 않는다): project_key 마다 DB 전체 에이전트 project_path 중
    가장 짧은 것(길이 같으면 사전순 첫 번째)의 마지막 이름(앞 60 자), 경로가 하나도 없으면 project_key 앞 60 자.
    범위 · 행 순서와 무관."""
    paths: dict[str, list[str]] = {}
    for pk, pp in con.execute("SELECT project_key, project_path FROM agent"):
        if pk is None:
            continue
        lst = paths.setdefault(pk, [])
        p = (pp or "").rstrip("/")
        if p:
            lst.append(p)
    out = {}
    for pk, lst in paths.items():
        if not lst:
            out[pk] = pk[:60]
            continue
        best = sorted(lst, key=lambda x: (len(x), x))[0]
        out[pk] = best.split("/")[-1][:60] or pk[:60]
    return out


def direct_scope(con, since: str | None, project: str | None, now: datetime) -> int:
    """범위 안 에이전트 수 — 프로젝트 필터는 라인(project_key) 단위 (DEF-QA1-401): project_key 같음 또는 라인 이름에 포함."""
    from agentdash.core.graph import parse_since

    st = parse_since(since, now)
    names = direct_line_names(con)
    n = 0
    proj = (project or "").strip()
    for _k, pk, state, started, last in con.execute(
            "SELECT agent_key, project_key, state, started_at, last_event_at FROM agent"):
        if proj and not (pk == proj or proj in names.get(pk, "")):
            continue
        alive = state not in FINAL
        ts = [_dt(x) for x in (started, last) if x]
        recent = st is None or (bool(ts) and max(ts) >= st.replace(microsecond=0))
        n += alive or recent
    return n


def _ago(now: datetime, ts: str | None) -> int | None:
    return max(0, int((now - _dt(ts)).total_seconds())) if ts else None


def time_key_mismatches(con, machines: list[dict], now: datetime) -> list[str]:
    """설비 시간 키 (DEF-QA2-401) ↔ agent 행 직접: elapsed_s = now − state_since · last_ago_s = now − last_event_at ·
    ended_ago_s = now − ended_at (DONE · FAILED 만, 아니면 null) — 미래면 0, 시각 없으면 null.
    끝난 설비는 tool · target = null (DEF-QA2-404)."""
    row = {k: (st, ss, le, en) for k, st, ss, le, en in
           con.execute("SELECT agent_key, state, state_since, last_event_at, ended_at FROM agent")}
    bad = []
    for m in machines:
        st, ss, le, en = row.get(m["key"], (None, None, None, None))
        final = st in FINAL
        want = (_ago(now, ss), _ago(now, le), _ago(now, en) if final else None)
        got = (m.get("elapsed_s"), m.get("last_ago_s"), m.get("ended_ago_s"))
        if m["key"] not in row or got != want or (final and (m.get("tool") is not None or m.get("target") is not None)):
            bad.append(m["key"])
    return bad


def grid_mismatches(resp: dict, width: int) -> int:
    """T-08 격자 독립 대조: grid.width = 보낸 width · 라인 i 는 열 i % cols · 행 i // cols ·
    열 x = 앞 열들 최대 너비 합 + 열 수 × LINE_GAP · 행 y = 앞 행 높이 합 + 행 수 × LINE_GAP · 같은 행 h = 행 최대 높이 ·
    cols = width 에 들어가는 최대 열 수(≥ 1) · rows = ⌈라인 수 / cols⌉. 틀린 항목 수."""
    from agentdash.core.twin import LINE_GAP

    g = resp.get("grid") or {}
    boxes = [ln["box"] for ln in resp["lines"]]
    n = len(boxes)
    cols, rows = g.get("cols"), g.get("rows")
    bad = int(g.get("width") != width)
    if not isinstance(cols, int) or cols < 1 or not isinstance(rows, int):
        return bad + 1
    bad += rows != ((n + cols - 1) // cols if n else 0)
    if not n:
        return bad

    def colw(c: int) -> list[int]:
        return [max(boxes[i]["w"] for i in range(j, n, c)) for j in range(min(c, n))]

    def fits(c: int) -> bool:
        return sum(colw(c)) + (c - 1) * LINE_GAP <= width

    want_cols = next((c for c in range(n, 1, -1) if fits(c)), 1)
    bad += cols != want_cols
    cw = colw(cols)
    xs = [sum(cw[:j]) + j * LINE_GAP for j in range(len(cw))]
    y, place_bad = 0, 0
    for r0 in range(0, n, cols):
        row_b = boxes[r0:r0 + cols]
        rh = max(b["h"] for b in row_b)
        for i, b in enumerate(row_b):
            place_bad += b["x"] != xs[i] or b["y"] != y or b["h"] != rh
        y += rh + LINE_GAP
    return bad + int(place_bad > 0)


def _hit(a: dict, b: dict) -> bool:
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def own_overlaps(resp: dict) -> int:
    boxes, lines = [], []
    for ln in resp["lines"]:
        lines.append(ln["box"])
        boxes += [m["box"] for m in ln["machines"]]
        if ln.get("inlet"):
            boxes.append(ln["inlet"]["box"])
    n = 0
    for group in (boxes, lines):
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                n += _hit(group[i], group[j])
    return n


def long_texts(v) -> int:
    if isinstance(v, str):
        return int(len(v) > TEXT_MAX)
    if isinstance(v, dict):
        return sum(long_texts(x) for x in v.values()) + sum(long_texts(x) for x in v.keys())
    if isinstance(v, (list, tuple)):
        return sum(long_texts(x) for x in v)
    return 0


def check(con, *, since: str | None = None, project: str | None = None, now: datetime | None = None,
          width: int | None = None) -> tuple[bool, str]:
    from agentdash.core import twin, usage

    now = now or datetime.now(timezone.utc)
    width = twin.GRID_WIDTH if width is None else width
    resp = twin.build(con, since=since, project=project, now=now, width=width)
    machines = [m for ln in resp["lines"] for m in ln["machines"]]
    keys = [m["key"] for m in machines]
    dup = len(keys) - len(set(keys))

    cum_bad = []
    for m in machines:
        t = usage.totals(con, m["key"])
        c1, c2 = m["cost_est_usd"], t["cost_est_usd"]
        cost_ok = (c1 is None and c2 is None) or (c1 is not None and c2 is not None and abs(c1 - c2) <= COST_TOL)
        if m["out_total"] != t["output_tokens"] or m["out_est_total"] != t["output_est_total"] or not cost_ok:
            cum_bad.append(m["key"])

    want = direct_spark(con, set(keys), now, usage.SPARK_MINUTES)
    spark_bad = [m["key"] for m in machines if list(m["spark"]) != want[m["key"]]]

    ov = max(twin.overlaps(resp), own_overlaps(resp))
    folded = sum(m["folded"] for m in machines) + sum((ln.get("inlet") or {}).get("folded", 0) for ln in resp["lines"])
    hidden = sum(ln.get("hidden", 0) for ln in resp["lines"])
    scope_resp = twin.scope_count(resp)
    scope_db = direct_scope(con, since, project, now)
    scope_ok = scope_resp == resp["agents_in_scope"] == scope_db == len(machines) + folded + hidden
    time_bad = time_key_mismatches(con, machines, now)
    grid_bad = grid_mismatches(resp, width)
    texts = long_texts(resp)
    ms = float(resp["elapsed_ms"])

    ok = not cum_bad and not spark_bad and not time_bad and grid_bad == 0 and ov == 0 and scope_ok and dup == 0 and texts == 0 and ms <= MAX_MS
    detail = (f"설비 {len(machines)} · 라인 {len(resp['lines'])} (접힌 라인 {resp['folded_lines']}) · 접힘 {folded}+{hidden} · "
              f"범위 칸+접힘 {scope_resp} / 응답 {resp['agents_in_scope']} / DB 직접 {scope_db} · "
              f"누적 불일치 {len(cum_bad)} · 스파크 불일치 {len(spark_bad)} · 시간 키 불일치 {len(time_bad)} · "
              f"격자 불일치 {grid_bad} (width {width} · cols {(resp.get('grid') or {}).get('cols')} · "
              f"rows {(resp.get('grid') or {}).get('rows')}) · 겹침 {ov} · 키 중복 {dup} · "
              f"TEXT>300 {texts} · {ms:.1f} ms (≤ {MAX_MS:.0f}) · 스파크 합 {sum(sum(m['spark']) for m in machines)} "
              f"(now {now.astimezone(timezone.utc):%m-%d %H:%M}Z)")
    if cum_bad or spark_bad or time_bad:
        detail += " · 예: " + ", ".join((cum_bad + spark_bad + time_bad)[:3])
    return ok, detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--since", default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--now", default=None, help="ISO 시각 (기본 지금, UTC)")
    ap.add_argument("--width", type=int, default=None, help="평면도 너비 px (T-08, 기본 twin.GRID_WIDTH)")
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-32  트윈 API  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    now = _dt(a.now) if a.now else None
    con = conn.connect(db)
    try:
        ok, detail = check(con, since=a.since, project=a.project, now=now, width=a.width)
    finally:
        con.close()
    print(f"G-32  트윈 API  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
