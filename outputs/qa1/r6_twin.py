#!/usr/bin/env python
"""QA1 r6 — G-32 / G-31 / T-08 독립 재계산 (twin.build 코드를 쓰지 않고 spec v0.4.1 §5.4 글자 + D-25~D-28 로 다시 계산).

    uv run python outputs/qa1/r6_twin.py --db <DB> [--since 24h|7d|6h|all] [--now ISO] [--width N] [--project P]

r5_twin.py 에서 바뀐 것:
  · 라인 이름 = D-28 (그 project_key 의 모든 에이전트 project_path 중 가장 짧은 것, 같으면 사전순 → 마지막 이름; 없으면 project_key)
  · 프로젝트 필터 = 라인 단위 (project_key 같음 또는 라인 이름에 포함 — D-02 와 같은 뜻)
  · T-08 격자: cols = width 안에 들어가는 최대 열 수(≥1), 열 너비 = 그 열 라인 중 최대, 행 높이 = 그 행 최대 → 라인 x · y · h 직접 계산
  · 상자 좌표는 라인 상자 원점 기준 상대값으로 비교 (열 · 행)
  · ended_ago_s = now − ended_at (DONE · FAILED 만) · last_ago_s = now − last_event_at · elapsed_s = now − state_since (초 내림, 미래 0)
  · 지금 도구: spec 글자(결과 없는 마지막 tool_call) 값과, 끝난 설비 null(DEF-QA2-404 구현) 을 따로 센다
본문은 읽지 않는다 — 키 · 숫자 · 시각 · 도구 이름 · 대상(저장값)만.
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


def ago(now, t):
    return None if t is None else max(0, int((now - t).total_seconds()))


def d28_names(con):
    """D-28 — 행 순서와 무관하게 (길이, 문자열) 최소 경로."""
    paths = {}
    for pk, pp in con.execute("SELECT project_key, project_path FROM agent"):
        paths.setdefault(pk, set())
        p = (pp or "").rstrip("/")
        if p:
            paths[pk].add(p)
    out = {}
    for pk, ps in paths.items():
        if ps:
            best = min(ps, key=lambda p: (len(p), p))
            out[pk] = best.rsplit("/", 1)[-1]
        else:
            out[pk] = pk
    return out


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


def since_delta(s):
    return {"h": timedelta(hours=1), "d": timedelta(days=1), "m": timedelta(minutes=1)}[s[-1]] * int(s[:-1])


def expected_layout(con, now, since, project=None):
    names = d28_names(con)
    since_t = None if since == "all" else now - since_delta(since)
    A = {}
    for r in con.execute("SELECT agent_key, kind, project_key, project_path, parent_key, name, started_at, last_event_at, "
                         "ended_at, state, state_since FROM agent"):
        a = dict(zip(("key", "kind", "pk", "pp", "parent", "name", "started", "last", "ended", "state", "ss"), r))
        if project and not (a["pk"] == project or project in names[a["pk"]]):
            continue
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

    # T-01: 살아 있음 → 가장 늦은 last 최근 순 → 이름 순 (튜플 정렬 3 번, 안정 정렬)
    order = sorted(lines, key=lambda pk: (names[pk], pk))
    order.sort(key=lambda pk: max((A[k]["last"] or "") for k in lines[pk]), reverse=True)
    order.sort(key=lambda pk: 0 if any(A[k]["state"] not in FINAL for k in lines[pk]) else 1)
    res = []
    unreached = 0
    for pk in order:
        mem = lines[pk]
        roots = sorted([k for k in mem if A[k]["kind"] == "SESSION" and not tparent(k)], key=sk)
        orph = sorted([k for k in mem if A[k]["kind"] != "SESSION" and not tparent(k)], key=sk)
        rows, folded, inlet_folded, seen = [], {}, 0, set()
        inlet_first = None

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
            before = len(rows)
            walk(o, 1, None)
            if len(rows) > before and inlet_first is None:
                inlet_first = before
        left = [k for k in mem if k not in seen]
        unreached += len(left)
        res.append({"pk": pk, "label": names[pk], "rows": rows, "folded": folded, "inlet_folded": inlet_folded,
                    "has_inlet": bool(orph), "inlet_row": inlet_first, "unreached": left})
    return A, res, unreached, names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--since", default="24h")
    ap.add_argument("--now", default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    from agentdash.core import twin

    now = dt(a.now) if a.now else datetime.now(timezone.utc).replace(microsecond=0)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    kw = {"now": now, "since": None if a.since == "24h" else a.since, "project": a.project}
    if a.width is not None:
        kw["width"] = a.width
    resp = twin.build(con, **kw)
    width = 1400 if a.width is None else a.width
    A, exp, unreached, names = expected_layout(con, now, a.since, a.project)
    bad = {}

    def err(kind, msg):
        bad.setdefault(kind, []).append(msg)

    BW, BH, GX, GY, HEAD, PAD, LG = twin.BOX_W, twin.BOX_H, twin.GAP_X, twin.GAP_Y, twin.LINE_HEAD, twin.LINE_PAD, twin.LINE_GAP
    sx, sy = BW + GX, BH + GY
    if resp["agents_in_scope"] != len(A):
        err("범위", f"응답 {resp['agents_in_scope']} ≠ 직접 {len(A)}")
    if [ln["key"] for ln in resp["lines"]] != [e["pk"] for e in exp]:
        err("T-01", "라인 순서 다름")
    # 라인 고유 크기 (격자 전) — 직접 계산
    sizes = []
    for ln, e in zip(resp["lines"], exp):
        if ln.get("folded_line"):
            sizes.append((BW + 2 * PAD, HEAD))
            continue
        maxc = max((c for _, c in e["rows"]), default=0)
        nrows = max(len(e["rows"]), (e["inlet_row"] + 1) if e["inlet_row"] is not None else (len(e["rows"]) + 1 if e["inlet_folded"] else 0), 1)
        sizes.append((2 * PAD + (maxc + 1) * BW + maxc * GX, HEAD + nrows * sy - GY + PAD))
    n = len(sizes)

    def colwidths(c):
        return [max(sizes[i][0] for i in range(j, n, c)) for j in range(c)]

    fits = [c for c in range(1, n + 1) if sum(colwidths(c)) + (c - 1) * LG <= width]
    cols = max(fits) if fits else 1
    fits_nogap = [c for c in range(1, n + 1) if sum(colwidths(c)) <= width]
    cw = colwidths(cols) if n else []
    rowh = [max(sizes[i][1] for i in range(r, min(n, r + cols))) for r in range(0, n, cols)]
    exp_box = []
    for i, (w, h) in enumerate(sizes):
        r, c = divmod(i, cols)
        exp_box.append({"x": sum(cw[:c]) + c * LG, "y": sum(rowh[:r]) + r * LG, "w": w, "h": rowh[r]})
    if resp.get("grid", {}).get("cols") != cols:
        err("T-08 cols", f"응답 {resp.get('grid')} 직접 {cols}")
    machines = []
    for idx, (ln, e) in enumerate(zip(resp["lines"], exp)):
        if ln["key"] != e["pk"]:
            continue
        if ln["name"] != e["label"]:
            err("라인 이름 D-28", f"{ln['key'][:30]} 응답 {ln['name']!r} 직접 {e['label']!r}")
        if ln["box"] != exp_box[idx]:
            err("T-08 라인 상자", f"{ln['key'][:30]} 응답 {ln['box']} 직접 {exp_box[idx]}")
        if ln.get("folded_line"):
            continue
        ms = ln["machines"]
        machines += [(m, ln) for m in ms]
        L = ln["box"]
        got_rows = [(m["key"], (m["box"]["x"] - L["x"] - PAD) // sx) for m in ms]
        if [k for k, _ in got_rows] != [k for k, _ in e["rows"]]:
            err("T-03 행 순서/칸 집합", ln["key"])
        if got_rows != e["rows"]:
            err("T-02 열", ln["key"])
        for i, m in enumerate(ms):
            if (m["box"]["x"] - L["x"] - PAD) % sx:
                err("T-02 x 칸 어긋남", m["key"])
            if (m["box"]["y"] - L["y"] - HEAD) != i * sy:
                err("T-03 행 y", m["key"])
            if m["folded"] != e["folded"].get(m["key"], 0):
                err("T-05 folded", f"{m['key']} 응답 {m['folded']} 직접 {e['folded'].get(m['key'], 0)}")
        inl = ln.get("inlet")
        if (inl or {}).get("folded", 0) != e["inlet_folded"]:
            err("T-05 반입구 folded", ln["key"])
        if e["has_inlet"] and inl is None:
            err("반입구 없음", ln["key"])
        if inl and inl["box"]["x"] != L["x"] + PAD:
            err("D-27 반입구 0 열", ln["key"])
    # 값
    keys = [m["key"] for m, _ in machines]
    cum = {k: (o, oe, c) for k, o, oe, c in con.execute(
        "SELECT agent_key, SUM(output_tokens), SUM(COALESCE(output_est, output_tokens)), SUM(cost_est_usd) FROM usage_event GROUP BY agent_key")}
    end = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=30)
    sp = {}
    for k, mm, v in con.execute(
            "SELECT agent_key, strftime('%Y-%m-%dT%H:%M', at), SUM(COALESCE(output_est, output_tokens)) FROM usage_event "
            "WHERE julianday(at) >= julianday(?) AND julianday(at) < julianday(?) AND (model IS NULL OR model != '<synthetic>') "
            "GROUP BY 1, 2", (start.isoformat(), end.isoformat())):
        i = int((dt(mm + ":00Z") - start).total_seconds() // 60)
        sp.setdefault(k, [0] * 30)[i] += v
    tool = {}
    for k, at, tid, tl, tg in con.execute("SELECT agent_key, at, tool_use_id, tool, target FROM tool_call WHERE ok IS NULL"):
        if k not in tool or (at or "", tid) > tool[k][:2]:
            tool[k] = (at or "", tid, tl, tg)
    final_with_open_tool = []
    for m, ln in machines:
        k = m["key"]
        ag = A[k]
        o, oe, c = cum.get(k, (0, 0, None))
        if (m["out_total"], m["out_est_total"]) != (o or 0, oe or 0):
            err("누적", k)
        if (c is None) != (m["cost_est_usd"] is None) or (c is not None and abs(c - m["cost_est_usd"]) > 1e-9):
            err("비용", k)
        if m["spark"] != sp.get(k, [0] * 30) or len(m["spark"]) != 30:
            err("스파크", k)
        t = tool.get(k)
        letter = (t[2], t[3]) if t else (None, None)
        final = ag["state"] in FINAL
        impl = (None, None) if final else letter
        if (m["tool"], m["target"]) != impl:
            err("지금 도구", k)
        if final and letter != (None, None):
            final_with_open_tool.append(k)
        if len(m["name"]) > 24:
            err("이름 24", k)
        if m["elapsed_s"] != ago(now, dt(ag["ss"])):
            err("elapsed_s", k)
        if m.get("ended_ago_s") != (ago(now, dt(ag["ended"])) if final else None):
            err("ended_ago_s", f"{k} 응답 {m.get('ended_ago_s')}")
        if m.get("last_ago_s") != ago(now, dt(ag["last"])):
            err("last_ago_s", f"{k} 응답 {m.get('last_ago_s')}")
    # 겹침 (전 쌍)
    boxes = [m["box"] for m, _ in machines] + [ln["inlet"]["box"] for ln in resp["lines"] if ln.get("inlet")]
    lb = [ln["box"] for ln in resp["lines"]]
    ov_m = sum(hit(boxes[i], boxes[j]) for i in range(len(boxes)) for j in range(i + 1, len(boxes)))
    ov_l = sum(hit(lb[i], lb[j]) for i in range(len(lb)) for j in range(i + 1, len(lb)))
    outside = 0
    for ln in resp["lines"]:
        L = ln["box"]
        for b in [m["box"] for m in ln["machines"]] + ([ln["inlet"]["box"]] if ln.get("inlet") else []):
            outside += not (L["x"] <= b["x"] and b["x"] + b["w"] <= L["x"] + L["w"] and L["y"] <= b["y"] and b["y"] + b["h"] <= L["y"] + L["h"])
    # 같은 행 높이 · y 정렬
    rows_bad = 0
    for r0 in range(0, n, cols):
        row = resp["lines"][r0:r0 + cols]
        rows_bad += len({ln["box"]["y"] for ln in row}) != 1 or len({ln["box"]["h"] for ln in row}) != 1
    longs = [(p, len(s)) for p, s in strings(resp) if len(s) > 300]
    folded = sum(m["folded"] for m, _ in machines) + sum((ln.get("inlet") or {}).get("folded", 0) for ln in resp["lines"])
    hidden = sum(ln.get("hidden", 0) for ln in resp["lines"])
    grid_w = max((b["x"] + b["w"] for b in lb), default=0)
    out = {
        "now": now.isoformat(), "since": a.since, "width": width, "project": a.project,
        "scope_direct": len(A), "scope_resp": resp["agents_in_scope"],
        "machines": len(machines), "lines": len(resp["lines"]), "folded_lines": resp["folded_lines"],
        "folded": folded, "hidden": hidden, "cells_plus_folded": len(machines) + folded + hidden,
        "unreached_direct": unreached, "overlap_machines": ov_m, "overlap_lines": ov_l, "outside_line_box": outside,
        "rows_misaligned": rows_bad, "long_strings": len(longs),
        "grid": {"resp": resp.get("grid"), "cols_direct": cols, "cols_fit_list": fits, "cols_fit_nogap_max": max(fits_nogap) if fits_nogap else 1,
                 "col_widths": cw, "row_heights": rowh, "used_width": grid_w, "line_sizes": sizes},
        "spark_sum": sum(sum(m["spark"]) for m, _ in machines), "spark_direct_sum": sum(sum(sp.get(k, [])) for k in keys),
        "cum_out": sum(m["out_total"] for m, _ in machines), "cum_est": sum(m["out_est_total"] for m, _ in machines),
        "cost_est": round(sum(m["cost_est_usd"] or 0 for m, _ in machines), 4),
        "machines_with_spark": sum(1 for m, _ in machines if any(m["spark"])),
        "final_machines_with_open_tool_spec_letter": len(final_with_open_tool),
        "elapsed_ms": resp["elapsed_ms"], "mismatch": {k: len(v) for k, v in bad.items()},
        "mismatch_examples": {k: v[:3] for k, v in bad.items()},
        "line_names": [e["label"] for e in exp],
    }
    ok = (not bad and ov_m == 0 and ov_l == 0 and outside == 0 and rows_bad == 0 and not longs
          and out["cells_plus_folded"] == len(A) == resp["agents_in_scope"] and unreached == 0)
    out["verdict"] = "PASS" if ok else "FAIL"
    if a.quiet:
        out["grid"].pop("line_sizes")
        out.pop("line_names")
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
