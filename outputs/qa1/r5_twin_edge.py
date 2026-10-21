#!/usr/bin/env python
"""QA1 r5 — G-32 경계 표본. 실제 DB 를 메모리로 복사(원본 · 원천 무변경)한 뒤 숫자 행만 덧붙여 twin.build 를 다시 잰다.

    uv run python outputs/qa1/r5_twin_edge.py --db data/agentdash-qa1.db

  E1 스파크 경계: 지금 분 시작 정각 행(포함) · 다음 분 정각 행(제외) · 30 칸 맨 앞 분 시작 정각(포함) · 그 1 ms 전(제외)
  E2 `<synthetic>` 행은 스파크에서 제외, 누적에는 포함(누적 = §6 totals 그대로)
  E3 output_est 있으면 그 값(COALESCE)
  E4 비용 NULL 만 있는 설비 → cost_est_usd None (0 으로 끼워 넣지 않음)
  E5 T-06: limit 을 낮춰 접힌 라인 · hidden · 칸+접힘 = 범위 확인
  E6 /api/v1/twin (TestClient, lifespan 없이 — 감시기 안 띄움) 응답 ↔ twin.build 같은 필드
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    a = ap.parse_args()
    from agentdash.core import twin

    src = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con = sqlite3.connect(":memory:")
    src.backup(con)
    src.close()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    base = twin.build(con, now=now)
    ms = [m for ln in base["lines"] for m in ln["machines"]]
    tgt = ms[0]["key"]
    cols = [r[1] for r in con.execute("PRAGMA table_info(usage_event)")]
    print("usage_event 열:", cols)
    cur_min = now.replace(second=0)
    first_min = cur_min - timedelta(minutes=29)
    f = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"
    rows = [  # (at, model, output_tokens, output_est, 기대 칸 index or None, 누적 포함)
        (f(cur_min), "claude-opus-5-5", 1000, None, 29),
        (f(cur_min + timedelta(minutes=1)), "claude-opus-5-5", 2000, None, None),
        (f(first_min), "claude-opus-5-5", 3000, 3500, 0),
        (f(first_min - timedelta(milliseconds=1)), "claude-opus-5-5", 4000, None, None),
        (f(cur_min + timedelta(seconds=30)), "<synthetic>", 5000, None, None),
    ]
    tmpl = con.execute("SELECT * FROM usage_event WHERE agent_key=? LIMIT 1", (tgt,)).fetchone() or \
        con.execute("SELECT * FROM usage_event LIMIT 1").fetchone()
    tmpl = dict(zip(cols, tmpl))
    for i, (at, model, o, e, _) in enumerate(rows):
        r = dict(tmpl)
        for c in cols:
            if c in ("id", "rowid"):
                r[c] = None
        r.update(agent_key=tgt, at=at, model=model, output_tokens=o, output_est=e)
        for c in ("request_id", "uuid", "message_id"):
            if c in r:
                r[c] = f"qa1-r5-edge-{i}"
        con.execute(f"INSERT INTO usage_event ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [r[c] for c in cols])
    out = twin.build(con, now=now)
    m0 = next(m for ln in out["lines"] for m in ln["machines"] if m["key"] == tgt)
    b0 = next(m for m in ms if m["key"] == tgt)
    diff = [x - y for x, y in zip(m0["spark"], b0["spark"])]
    exp = [0] * 30
    exp[29] += 1000
    exp[0] += 3500
    print("E1/E2/E3 스파크 증가분 기대", {i: v for i, v in enumerate(exp) if v}, "실제", {i: v for i, v in enumerate(diff) if v},
          "PASS" if diff == exp else "FAIL")
    d_out = m0["out_total"] - b0["out_total"]
    d_est = m0["out_est_total"] - b0["out_est_total"]
    print("E2 누적 증가분 out_total", d_out, "(기대 15000 — synthetic 포함)", "out_est_total", d_est, "(기대 15500)",
          "PASS" if (d_out, d_est) == (15000, 15500) else "FAIL")
    # E4 비용 NULL
    con.execute("UPDATE usage_event SET cost_est_usd=NULL WHERE agent_key=?", (tgt,))
    out = twin.build(con, now=now)
    m0 = next(m for ln in out["lines"] for m in ln["machines"] if m["key"] == tgt)
    print("E4 비용 전부 NULL → cost_est_usd", m0["cost_est_usd"], "PASS" if m0["cost_est_usd"] is None else "FAIL")
    # E5 T-06
    full = twin.build(con, now=now, since="all")
    n_cells = sum(len(ln["machines"]) for ln in full["lines"])
    for lim in (n_cells - 1, 40, 10, 1):
        r = twin.build(con, now=now, since="all", limit=lim)
        cells = sum(len(ln["machines"]) for ln in r["lines"])
        folded_tail = [ln.get("folded_line", False) for ln in r["lines"]]
        tail_ok = folded_tail == sorted(folded_tail)  # 접힌 라인은 뒤쪽에만
        print(f"E5 limit {lim}: 칸 {cells} (≤ limit {cells <= lim}) · 접힌 라인 {r['folded_lines']} · 뒤 라인부터 {tail_ok} · "
              f"칸+접힘 {twin.scope_count(r)} = 범위 {r['agents_in_scope']} · 겹침 {twin.overlaps(r)} · "
              + ("PASS" if (cells <= lim or r['folded_lines'] == len(r['lines'])) and tail_ok and twin.scope_count(r) == r['agents_in_scope'] and twin.overlaps(r) == 0 else "FAIL"))
    # E6 API
    os.environ["AGENTDASH_DB"] = str(Path(a.db).resolve())
    from fastapi.testclient import TestClient
    from agentdash.app.main import app
    c = TestClient(app)
    for q in ("", "?since=all", "?since=7d", "?since=bad"):
        r = c.get("/api/v1/twin" + q)
        if r.status_code != 200:
            print("E6", q or "(기본)", "HTTP", r.status_code, r.json())
            continue
        j = r.json()
        srcc = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
        b = twin.build(srcc, since=(q.split("=")[1] if q else None), now=datetime.fromisoformat(j["generated_at"] + "+00:00"))
        strip = lambda d: [(ln["key"], [(m["key"], m["box"], m["folded"], m["out_total"], m["out_est_total"]) for m in ln["machines"]]) for ln in d["lines"]]
        print("E6", q or "(기본)", "HTTP 200 · 라인", len(j["lines"]), "· 키/상자/누적 build 와 같음", strip(j) == strip(b),
              "· agents_in_scope", j["agents_in_scope"], b["agents_in_scope"])


if __name__ == "__main__":
    main()
