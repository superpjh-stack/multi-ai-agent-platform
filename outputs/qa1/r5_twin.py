#!/usr/bin/env python
"""QA1 r5 — G-32 / G-31 독립 재계산 (twin.build 코드를 쓰지 않고 spec v0.4 §5.4 글자 + D-25~D-27 로 다시 계산).

    uv run python outputs/qa1/r5_twin.py --db data/agentdash-qa1.db [--since 24h|all] [--now ISO] [--json out.json]

대조 항목 (twin.build 응답 ↔ 이 스크립트):
  1 범위: 살아 있는 것 + max(started_at,last_event_at) ≥ now-since (datetime 비교)
  2 칸 집합 · 라인 순서(T-01) · 라인 안 행 순서(T-03) · 열(T-02) · folded 수(T-05 + D-26) · 반입구 folded
  3 누적: SUM(output_tokens) · SUM(COALESCE(output_est,output_tokens)) · SUM(cost_est_usd) 직접 SQL
  4 스파크: SQLite strftime('%Y-%m-%dT%H:%M', at) 분 단위 UTC, model != '<synthetic>', 30 칸
  5 상자 겹침 (설비+반입구 전체 쌍, 라인 전체 쌍) · 모든 문자열 ≤ 300 · 이름 ≤ 24 · elapsed_s ≥ 0
  6 지금 도구: ok IS NULL 인 tool_call 중 (at, tool_use_id) 가장 큰 것
본문은 읽지 않는다 — agent · usage_event · tool_call 의 키 · 숫자 · 시각 · 도구 이름만.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

FINAL = ("DONE", "FAILED")
FOLD = timedelta(minutes=30)


def dt(s):
    if not s:
        return None
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def label(pk, pp):  # spec §5.4 대응표: project_path 마지막 이름, 없으면 project_key
    if pp:
        return pp.rstrip("/").rsplit("/", 1)[-1][:60] or pk[:60]
    return pk.rsplit("-", 1)[-1][:60] or pk[:60]


def strings(v, path="$"):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from strings(k, path + ".<key>")
            yield from strings(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from strings(x, f"{path}[{i}]")


def hit(a, b):
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def expected_layout(con, now, since):
    since_t = None if since == "all" else now - {"h": timedelta(hours=1), "d": timedelta(days=1), "m": timedelta(minutes=1)}[since[-1]] * int(since[:-1])
    A = {}
    for r in con.execute("SELECT agent_key, kind, project_key, project_path, parent_key, name, started_at, last_event_at, "
                         "ended_at, state FROM agent"):
        a = dict(zip(("key", "kind", "pk", "pp", "parent", "name", "started", "last", "ended", "state"), r))
        ts = [t for t in (dt(a["started"]), dt(a["last"])) if t]
        if a["state"] not in FINAL or since_t is None or (ts and max(ts) >= since_t):
            A[a["key"]] = a
    lines = {}
    for k, a in A.items():
        lines.setdefault(a["pk"], []).append(k)

    def tparent(k):
        p = A[k]["parent"]
        return p if p and p != k and p in A and A[p]["pk"] == A[k]["pk"] else None

    kids = {}
    for k in A:
        p = tparent(k)
        if p:
            kids.setdefault(p, []).append(k)
    sk = lambda k: (A[k]["started"] or "", k)
    for v in kids.values():
        v.sort(key=sk)

    def desc(k):
        out, st = [], list(kids.get(k, []))
        while st:
            x = st.pop()
            out.append(x)
            st.extend(kids.get(x, []))
        return out

    def foldable(k):
        a = A[k]
        if a["state"] not in FINAL or not dt(a["ended"]) or not (dt(a["ended"]) < now - FOLD):
            return False
        return all(A[d]["state"] in FINAL for d in desc(k))  # D-26

    # T-01
    def lab(pk):
        pp = next((A[k]["pp"] for k in lines[pk] if A[k]["pp"]), None)
        return label(pk, pp)
    order = sorted(lines, key=lambda pk: (
        0 if any(A[k]["state"] not in FINAL for k in lines[pk]) else 1,
        "".join(chr(0x10FFFF - ord(c)) for c in max((A[k]["last"] or "") for k in lines[pk])),  # 최근 순
        lab(pk), pk))
    res = []
    unreached = 0
    for pk in order:
        mem = lines[pk]
        roots = sorted([k for k in mem if A[k]["kind"] == "SESSION" and not tparent(k)], key=sk)
        orph = sorted([k for k in mem if A[k]["kind"] != "SESSION" and not tparent(k)], key=sk)
        rows, folded, inlet_folded, seen = [], {}, 0, set()

        def walk(k, col, holder):
            nonlocal inlet_folded
            if col > 0 and foldable(k):  # 뿌리(세션 0 열)는 접지 않는다
                n = 1 + len(desc(k))
                seen.update([k, *desc(k)])
                if holder is None:
                    inlet_folded += n
                else:
                    folded[holder] = folded.get(holder, 0) + n
                return
            seen.add(k)
            rows.append((k, col))
            for c in kids.get(k, []):
                walk(c, col + 1, k)

        for r in roots:
            walk(r, 0, None)
        for o in orph:
            walk(o, 1, None)
        left = [k for k in mem if k not in seen]
        unreached += len(left)
        res.append({"pk": pk, "label": lab(pk), "rows": rows, "folded": folded, "inlet_folded": inlet_folded,
                     "has_inlet": bool(orph), "unreached": left})
    return A, res, unreached


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--since", default="24h")
    ap.add_argument("--now", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    from agentdash.core import twin

    now = dt(a.now) if a.now else datetime.now(timezone.utc).replace(microsecond=0)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    resp = twin.build(con, since=None if a.since == "24h" else a.since, now=now)
    A, exp, unreached = expected_layout(con, now, a.since)
    bad = {}

    def err(kind, msg):
        bad.setdefault(kind, []).append(msg)

    step_x, step_y = twin.BOX_W + twin.GAP_X, twin.BOX_H + twin.GAP_Y
    # 범위 · 라인 순서
    if resp["agents_in_scope"] != len(A):
        err("범위", f"응답 {resp['agents_in_scope']} ≠ 직접 {len(A)}")
    got_order = [ln["key"] for ln in resp["lines"]]
    if got_order != [e["pk"] for e in exp]:
        err("T-01", "라인 순서 다름")
    machines = []
    for ln, e in zip(resp["lines"], exp):
        if ln["key"] != e["pk"]:
            continue
        if ln["name"] != e["label"]:
            err("라인 이름", ln["key"])
        if ln.get("folded_line"):
            continue
        ms = ln["machines"]
        machines += ms
        top = ln["box"]["y"] + twin.LINE_HEAD
        got_rows = [(m["key"], (m["box"]["x"] - twin.LINE_PAD) // step_x) for m in ms]
        if [k for k, _ in got_rows] != [k for k, _ in e["rows"]]:
            err("T-03 행 순서/칸 집합", ln["key"])
        if got_rows != e["rows"]:
            err("T-02 열", ln["key"])
        for i, m in enumerate(ms):
            if (m["box"]["y"] - top) != i * step_y:
                err("T-03 행 y", m["key"])
            if m["folded"] != e["folded"].get(m["key"], 0):
                err("T-05 folded", f"{m['key']} 응답 {m['folded']} 직접 {e['folded'].get(m['key'], 0)}")
        inl = ln.get("inlet")
        if (inl or {}).get("folded", 0) != e["inlet_folded"]:
            err("T-05 반입구 folded", ln["key"])
        if e["has_inlet"] and inl is None:
            err("반입구 없음", ln["key"])
        if inl and inl["box"]["x"] != twin.LINE_PAD:
            err("D-27 반입구 0 열", ln["key"])
    # 누적 · 비용 · 스파크 · 도구
    keys = [m["key"] for m in machines]
    cum = {k: (o, oe, c) for k, o, oe, c in con.execute(
        "SELECT agent_key, SUM(output_tokens), SUM(COALESCE(output_est, output_tokens)), SUM(cost_est_usd) FROM usage_event GROUP BY agent_key")}
    end = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=30)
    sp = {}
    for k, m, v in con.execute(
            "SELECT agent_key, strftime('%Y-%m-%dT%H:%M', at), SUM(COALESCE(output_est, output_tokens)) FROM usage_event "
            "WHERE julianday(at) >= julianday(?) AND julianday(at) < julianday(?) AND (model IS NULL OR model != '<synthetic>') "
            "GROUP BY 1, 2", (start.isoformat(), end.isoformat())):
        i = int((dt(m + ":00Z") - start).total_seconds() // 60)
        sp.setdefault(k, [0] * 30)[i] += v
    tool = {}
    for k, at, tid, tl, tg in con.execute("SELECT agent_key, at, tool_use_id, tool, target FROM tool_call WHERE ok IS NULL"):
        if k not in tool or (at or "", tid) > tool[k][:2]:
            tool[k] = (at or "", tid, tl, tg)
    ex = {}
    for m in machines:
        o, oe, c = cum.get(m["key"], (0, 0, None))
        if (m["out_total"], m["out_est_total"]) != (o or 0, oe or 0):
            err("누적", m["key"])
        if (c is None) != (m["cost_est_usd"] is None) or (c is not None and abs(c - m["cost_est_usd"]) > 1e-9):
            err("비용", m["key"])
        if m["spark"] != sp.get(m["key"], [0] * 30) or len(m["spark"]) != 30:
            err("스파크", m["key"])
        t = tool.get(m["key"])
        if (m["tool"], m["target"]) != ((t[2], t[3]) if t else (None, None)):
            err("지금 도구", m["key"])
        if len(m["name"]) > 24:
            err("이름 24", m["key"])
        if m["elapsed_s"] is not None and m["elapsed_s"] < 0:
            err("경과 음수", m["key"])
        if m["out_est_total"] < m["out_total"]:
            ex.setdefault("est<rec", []).append(m["key"])
    # 겹침 (전 쌍)
    boxes = [m["box"] for m in machines] + [ln["inlet"]["box"] for ln in resp["lines"] if ln.get("inlet")]
    lb = [ln["box"] for ln in resp["lines"]]
    ov = sum(hit(boxes[i], boxes[j]) for i in range(len(boxes)) for j in range(i + 1, len(boxes)))
    ov += sum(hit(lb[i], lb[j]) for i in range(len(lb)) for j in range(i + 1, len(lb)))
    # 설비가 자기 라인 상자 안에 있는지
    outside = 0
    for ln in resp["lines"]:
        L = ln["box"]
        for b in [m["box"] for m in ln["machines"]] + ([ln["inlet"]["box"]] if ln.get("inlet") else []):
            outside += not (L["x"] <= b["x"] and b["x"] + b["w"] <= L["x"] + L["w"] and L["y"] <= b["y"] and b["y"] + b["h"] <= L["y"] + L["h"])
    longs = [(p, len(s)) for p, s in strings(resp) if len(s) > 300]
    folded = sum(m["folded"] for m in machines) + sum((ln.get("inlet") or {}).get("folded", 0) for ln in resp["lines"])
    hidden = sum(ln.get("hidden", 0) for ln in resp["lines"])
    out = {
        "now": now.isoformat(), "since": a.since, "scope_direct": len(A), "scope_resp": resp["agents_in_scope"],
        "machines": len(machines), "lines": len(resp["lines"]), "folded_lines": resp["folded_lines"],
        "folded": folded, "hidden": hidden, "cells_plus_folded": len(machines) + folded + hidden,
        "unreached_direct": unreached, "overlaps": ov, "outside_line_box": outside, "long_strings": len(longs),
        "spark_sum": sum(sum(m["spark"]) for m in machines), "spark_direct_sum": sum(sum(sp.get(k, [])) for k in keys),
        "cum_out": sum(m["out_total"] for m in machines), "cum_est": sum(m["out_est_total"] for m in machines),
        "cost_est": round(sum(m["cost_est_usd"] or 0 for m in machines), 4),
        "machines_with_spark": sum(1 for m in machines if any(m["spark"])),
        "elapsed_ms": resp["elapsed_ms"], "mismatch": {k: len(v) for k, v in bad.items()},
        "mismatch_examples": {k: v[:3] for k, v in bad.items()}, "notes": {k: len(v) for k, v in ex.items()},
        "line_order": [(e["label"], any(A[k]["state"] not in FINAL for k in A if A[k]["pk"] == e["pk"]),
                        max((A[k]["last"] or "") for k in A if A[k]["pk"] == e["pk"])) for e in exp],
    }
    ok = (not bad and ov == 0 and outside == 0 and not longs and out["cells_plus_folded"] == len(A) == resp["agents_in_scope"]
          and unreached == 0)
    out["verdict"] = "PASS" if ok else "FAIL"
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(s)
    print(s)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
