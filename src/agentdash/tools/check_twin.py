#!/usr/bin/env python
"""V-17 check_twin — 트윈 API (`twin.build` = `GET /api/v1/twin`) ↔ DB 직접 대조 (G-32, spec.md v0.4 §5.4 · §8 · §10).

    uv run python src/agentdash/tools/check_twin.py [--db 경로] [--since 24h] [--project 이름] [--now ISO]

실제 DB(기본 settings.db_path = AGENTDASH_DB)에서 `twin.build` 를 한 번 부르고 같은 now 로 대조한다:
  · 누적: 설비마다 out_total · out_est_total · cost_est_usd = `usage.totals(con, key)` (자기 몫, 비용 차 ≤ $1e-6)
  · 스파크: `usage.spark` 를 쓰지 않는 독립 계산 — 범위 안 usage_event 를 전부 읽어 `at` 을 datetime 으로 바꾼 뒤
    UTC 분 단위로 COALESCE(output_est, output_tokens) 합 (`<synthetic>` 제외, 지금 분이 마지막 칸, 30 칸) ↔ 설비 spark
  · 겹침: `twin.overlaps` + 이 도구의 독립 쌍 검사(설비 · 반입구 상자 전체, 라인 상자 전체 — 닿기만 하면 0) 중 큰 값
  · 범위: 칸 수 + 접힌 수(`twin.scope_count`) = agents_in_scope = 이 도구가 agent 테이블에서 직접 센 범위 안 수
    (살아 있는 것(DONE · FAILED 아님) + max(last_event_at, started_at) ≥ since, 프로젝트 필터 = D-02) · 설비 키 중복 0
  · TEXT > 300: 응답 안의 모든 문자열 길이 · 응답 시간 elapsed_ms ≤ 300
출력: `G-32  트윈 API  PASS|FAIL  설비 n · 라인 n · 접힘 n+n · 누적 불일치 n · 스파크 불일치 n · 겹침 n · TEXT>300 n · n ms`
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


def direct_scope(con, since: str | None, project: str | None, now: datetime) -> int:
    from agentdash.core.graph import parse_since, project_label

    st = parse_since(since, now)
    n = 0
    proj = (project or "").strip()
    for _k, pk, pp, state, started, last in con.execute(
            "SELECT agent_key, project_key, project_path, state, started_at, last_event_at FROM agent"):
        if proj and not (pk == proj or proj in project_label(pk, pp)):
            continue
        alive = state not in FINAL
        ts = [_dt(x) for x in (started, last) if x]
        recent = st is None or (bool(ts) and max(ts) >= st.replace(microsecond=0))
        n += alive or recent
    return n


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


def check(con, *, since: str | None = None, project: str | None = None, now: datetime | None = None) -> tuple[bool, str]:
    from agentdash.core import twin, usage

    now = now or datetime.now(timezone.utc)
    resp = twin.build(con, since=since, project=project, now=now)
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
    texts = long_texts(resp)
    ms = float(resp["elapsed_ms"])

    ok = not cum_bad and not spark_bad and ov == 0 and scope_ok and dup == 0 and texts == 0 and ms <= MAX_MS
    detail = (f"설비 {len(machines)} · 라인 {len(resp['lines'])} (접힌 라인 {resp['folded_lines']}) · 접힘 {folded}+{hidden} · "
              f"범위 칸+접힘 {scope_resp} / 응답 {resp['agents_in_scope']} / DB 직접 {scope_db} · "
              f"누적 불일치 {len(cum_bad)} · 스파크 불일치 {len(spark_bad)} · 겹침 {ov} · 키 중복 {dup} · "
              f"TEXT>300 {texts} · {ms:.1f} ms (≤ {MAX_MS:.0f}) · 스파크 합 {sum(sum(m['spark']) for m in machines)} "
              f"(now {now.astimezone(timezone.utc):%m-%d %H:%M}Z)")
    if cum_bad or spark_bad:
        detail += " · 예: " + ", ".join((cum_bad + spark_bad)[:3])
    return ok, detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--since", default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--now", default=None, help="ISO 시각 (기본 지금, UTC)")
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _settings.get().db_path
    if not db.exists():
        print(f"G-32  트윈 API  FAIL  DB 없음 {db.name} — make backfill")
        return 1
    now = _dt(a.now) if a.now else None
    con = conn.connect(db)
    try:
        ok, detail = check(con, since=a.since, project=a.project, now=now)
    finally:
        con.close()
    print(f"G-32  트윈 API  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
