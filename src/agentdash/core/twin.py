"""디지털 트윈 — 공장 평면도 배치 (spec.md v0.4 §5.4 T-01~T-07 · §8 `/api/v1/twin`). 담당 개발2.

    twin.build(con, *, since=None, project=None, now=None, limit=MACHINE_LIMIT) -> dict
    twin.overlaps(resp) -> int          설비 상자 쌍 + 라인 상자 쌍 겹침 수 (check_twin · 테스트 공용)
    twin.scope_count(resp) -> int       칸 + 접힌 수 (설비 folded · 반입구 folded · 접힌 라인 hidden) = 범위 안 에이전트 수

라인 = 프로젝트(`project_label`), 설비 = 에이전트(SESSION · SUBAGENT · WORKFLOW_AGENT · WORKFLOW).
범위 = D-02 와 같다: 살아 있는 것(DONE · FAILED 아님) + `since`(기본 24h) 안에 기록이 있는 것, 프로젝트 필터.
조상은 끌어오지 않는다 — 부모가 범위 밖이거나 다른 라인이면 그 설비는 자기 라인의 미확인 반입구(`U:<project_key>`) 아래 1 열.
  · 다른 라인의 부모(범위 안) → `links` 에 {src: 부모, dst: 자식, kind: "spawn", count} (배관 `pipes` 에는 안 넣는다 — 이중 0)
  · 부모 사슬 순환 · 자기 부모 → 깊이 우선 탐색에서 닿지 않는 설비를 키 순으로 반입구 아래에 뿌리로 세워 끊는다 (각 한 번)
T-05 접기: DONE · FAILED · ended_at 이 now − FOLD_AFTER_SEC 보다 이전 · 자손이 전부 DONE/FAILED → 그 설비와 자손을 부모 칸의
  `folded` 에 더한다 (반입구 아래 뿌리면 반입구 `folded`). 뿌리(세션)는 접지 않는다. 살아 있는 자손이 있으면 접지 않는다.
T-06: 그 뒤에도 칸 > limit 이면 T-01 순서 뒤 라인부터 `folded_line = True` · `machines = []` · `hidden = n` 머리 한 줄.
누적 · 비용 = usage.totals(con, key) 자기 몫과 같은 SQL 합, 스파크 = usage.spark (개발1, progress-dev1 §1).
본문은 싣지 않는다 — 이름 앞 24 자 · 키 · 상태 · 규칙 코드 · 도구 이름 · 대상(저장값 ≤ 300) · 숫자뿐.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from agentdash.core import usage
from agentdash.core.graph import GraphError, parse_since, project_label

# 배치 상수 (spec T-04 「상수」 — 값은 계획 docs/superpowers/plans/2026-10-21-agentdash-twin.md Global Constraints)
BOX_W = 208
BOX_H = 92
GAP_X = 56
GAP_Y = 16
LINE_HEAD = 36
LINE_PAD = 16
LINE_GAP = 24
FOLD_AFTER_SEC = 1800      # T-05
MACHINE_LIMIT = 300        # T-06
NAME_MAX = 24
FINAL = ("DONE", "FAILED")
INLET_NAME = "부모 미확인"

TwinError = GraphError     # 잘못된 필터 값 — API 가 422 로 돌려준다


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _name(a: dict) -> str:
    n = (a["name"] or "").strip()
    return (n or a["agent_key"][2:])[:NAME_MAX]


_AGENT_SQL = ("SELECT agent_key, kind, project_key, project_path, parent_key, name, started_at, last_event_at, ended_at, "
              "state, state_reason, state_since FROM agent")
_COLS = ("agent_key", "kind", "project_key", "project_path", "parent_key", "name", "started_at", "last_event_at",
         "ended_at", "state", "state_reason", "state_since")
# usage.totals 의 _SUM 과 같은 식 (자기 몫) — 설비마다 쿼리하지 않고 한 번에 묶는다
_USAGE_SQL = ("SELECT agent_key, COALESCE(SUM(output_tokens),0), COALESCE(SUM(COALESCE(output_est, output_tokens)),0), "
              "SUM(cost_est_usd) FROM usage_event WHERE agent_key IN ({}) GROUP BY agent_key")
_TOOL_SQL = ("SELECT agent_key, at, tool_use_id, tool, target FROM tool_call WHERE ok IS NULL AND agent_key IN ({})")
# SLEEPING 깰 시각 (spec §7.4) — 마지막 state_log 근거의 「ScheduleWakeup [깰 시각] <ISO>」 (core.state 가 남기는 꼴)
_WAKE_SQL = ("SELECT agent_key, reason FROM state_log WHERE agent_key IN ({}) ORDER BY agent_key, at DESC, rowid DESC")
_WAKE_RE = re.compile(r"ScheduleWakeup (?:깰 시각 )?(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?)")


def _chunks(keys: list[str], n: int = 500):
    for i in range(0, len(keys), n):
        yield keys[i:i + n]


def _box(x: int, y: int, w: int = BOX_W, h: int = BOX_H) -> dict:
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}


def build(con, *, since: str | None = None, project: str | None = None, now: datetime | None = None,
          limit: int = MACHINE_LIMIT) -> dict:
    t0 = time.perf_counter()
    now = now or _now()
    since_t = parse_since(since, now)                      # 형식 오류 → GraphError(= TwinError)
    since_iso = _iso(since_t) if since_t else None
    fold_before = now - timedelta(seconds=FOLD_AFTER_SEC)
    proj_filter = (project or "").strip()

    # ── 범위 ──
    agents: dict[str, dict] = {}
    for r in con.execute(_AGENT_SQL):
        a = dict(zip(_COLS, r))
        if proj_filter:
            label = project_label(a["project_key"], a["project_path"])
            if not (a["project_key"] == proj_filter or proj_filter in label):
                continue
        alive = a["state"] not in FINAL
        recent = since_iso is None or max(a["last_event_at"] or "", a["started_at"] or "") >= since_iso
        if alive or recent:
            agents[a["agent_key"]] = a

    # ── 라인 묶기 ──
    lines: dict[str, dict] = {}
    for k, a in agents.items():
        ln = lines.setdefault(a["project_key"], {"key": a["project_key"], "label": None, "members": []})
        ln["members"].append(k)
        if ln["label"] is None and a["project_path"]:
            ln["label"] = project_label(a["project_key"], a["project_path"])
    for pk, ln in lines.items():
        ln["label"] = ln["label"] or project_label(pk, None)

    # 자식 목록 (같은 라인 · 범위 안 · 자기 자신 아님)
    def tree_parent(k: str) -> str | None:
        p = agents[k]["parent_key"]
        if p and p != k and p in agents and agents[p]["project_key"] == agents[k]["project_key"]:
            return p
        return None

    order_key = {k: (a["started_at"] or "", k) for k, a in agents.items()}
    children: dict[str, list[str]] = {}
    for k in agents:
        p = tree_parent(k)
        if p:
            children.setdefault(p, []).append(k)
    for v in children.values():
        v.sort(key=order_key.__getitem__)

    # ── T-01 라인 순서 ──
    ordered = sorted(lines.values(), key=lambda ln: (ln["label"], ln["key"]))          # 이름 순
    ordered.sort(key=lambda ln: max((agents[k]["last_event_at"] or "" for k in ln["members"]), default=""),
                 reverse=True)                                                        # 최근 순 (안정 정렬)
    ordered.sort(key=lambda ln: 0 if any(agents[k]["state"] not in FINAL for k in ln["members"]) else 1)

    # ── T-02 · T-03 · T-05 라인마다 깊이 우선 ──
    def finished_old(k: str) -> bool:
        a = agents[k]
        if a["state"] not in FINAL:
            return False
        e = _parse(a["ended_at"])
        return e is not None and e < fold_before

    sub_all_final: dict[str, bool] = {}

    def all_final(k: str, guard: set) -> bool:          # 자손 전부 DONE/FAILED (순환 안전)
        if k in sub_all_final:
            return sub_all_final[k]
        guard.add(k)
        ok = agents[k]["state"] in FINAL and all(all_final(c, guard) for c in children.get(k, ()) if c not in guard)
        sub_all_final[k] = ok
        return ok

    def subtree(k: str, seen: set) -> int:
        n = 0
        stack = [k]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            n += 1
            stack.extend(children.get(x, ()))
        return n

    plans = []
    for ln in ordered:
        members = ln["members"]
        roots = sorted((k for k in members if agents[k]["kind"] == "SESSION" and tree_parent(k) is None),
                       key=order_key.__getitem__)
        orphans = sorted((k for k in members if agents[k]["kind"] != "SESSION" and tree_parent(k) is None),
                         key=order_key.__getitem__)
        seen: set[str] = set()
        rows: list[tuple[str, int, str | None]] = []   # (key, col, 깊이 우선 부모 — 반입구 아래 뿌리면 None)
        folded: dict[str, int] = {}
        inlet_rows: list[int] = []
        inlet_folded = 0

        def dfs(start: str, col0: int, parent_is_inlet: bool) -> int:
            """start 를 col0 에 두고 깊이 우선. 접힌 수를 돌려준다(start 자신이 접혔을 때)."""
            if start in seen:
                return 0
            if (parent_is_inlet or col0 > 0) and finished_old(start) and all_final(start, set()):
                return subtree(start, seen)
            stack = [(start, col0, None)]
            while stack:
                k, c, par = stack.pop()
                if k in seen:
                    continue
                seen.add(k)
                rows.append((k, c, par))
                kids = [x for x in children.get(k, ()) if x not in seen]
                push = []
                for x in kids:
                    if finished_old(x) and all_final(x, set()):
                        folded[k] = folded.get(k, 0) + subtree(x, seen)
                    else:
                        push.append((x, c + 1, k))
                stack.extend(reversed(push))
            return 0

        for r in roots:
            dfs(r, 0, False)
        pending = list(orphans)
        # 순환 · 자기 부모: 뿌리에서 닿지 않은 설비를 키 순으로 반입구 아래에 세운다
        for k in sorted((k for k in members if k not in roots and k not in orphans), key=order_key.__getitem__):
            if k not in seen and _in_cycle(k, agents, tree_parent):
                pending.append(k)
        for k in pending:
            if k in seen:
                continue
            start_row = len(rows)
            n = dfs(k, 1, True)
            if n:
                inlet_folded += n
            elif len(rows) > start_row:
                inlet_rows.append(start_row)
        # 남은 것(순환 아래 매달린 설비 — 위 루프의 순환 뿌리에서 닿는다)이 있으면 키 순으로 끊는다
        for k in sorted(members, key=order_key.__getitem__):
            if k not in seen:
                start_row = len(rows)
                n = dfs(k, 1, True)
                if n:
                    inlet_folded += n
                elif len(rows) > start_row:
                    inlet_rows.append(start_row)
        has_inlet = bool(inlet_rows) or inlet_folded > 0
        plans.append({"ln": ln, "rows": rows, "folded": folded, "inlet_row": min(inlet_rows) if inlet_rows else None,
                      "inlet_folded": inlet_folded, "has_inlet": has_inlet})

    # ── T-06 라인 접기 ──
    total = sum(len(p["rows"]) for p in plans)
    for p in reversed(plans):
        if total <= limit:
            break
        if p["rows"]:
            total -= len(p["rows"])
            p["folded_line"] = True

    # ── 값 읽기 (설비마다 쿼리 금지 — 키 묶음으로) ──
    vis = [r[0] for p in plans if not p.get("folded_line") for r in p["rows"]]
    tot: dict[str, tuple] = {}
    tools: dict[str, tuple] = {}
    for part in _chunks(vis):
        q = ",".join("?" * len(part))
        for k, o, oe, c in con.execute(_USAGE_SQL.format(q), part):
            tot[k] = (int(o), int(oe), c)
        for k, at, tid, tool, target in con.execute(_TOOL_SQL.format(q), part):
            cur = tools.get(k)
            if cur is None or (at or "", tid) > (cur[0] or "", cur[1]):
                tools[k] = (at, tid, tool, target)
    sparks = usage.spark(con, vis, now) if vis else {}
    wake: dict[str, str | None] = {}
    sleepers = [k for k in vis if agents[k]["state"] == "SLEEPING"]
    for part in _chunks(sleepers):
        for k, reason in con.execute(_WAKE_SQL.format(",".join("?" * len(part))), part):
            if k not in wake:                       # 키마다 가장 최근 한 줄만
                m = _WAKE_RE.search(reason or "")
                wake[k] = m.group(1) if m else None

    # ── 엣지 ──
    edge_at: dict[tuple, str | None] = {}
    raw_edges = con.execute("SELECT src_key, dst_key, kind, at, count FROM edge").fetchall()
    for s, d, kd, at, _c in raw_edges:
        edge_at[(s, d, kd)] = at

    # ── 좌표 ──
    out_lines = []
    y = 0
    folded_lines = 0
    for p in plans:
        ln = p["ln"]
        members = ln["members"]
        counts: dict[str, int] = {}
        for k in members:
            counts[agents[k]["state"]] = counts.get(agents[k]["state"], 0) + 1
        live = sum(1 for k in members if agents[k]["state"] not in FINAL)
        base = {"key": ln["key"], "name": ln["label"], "live": live, "counts": dict(sorted(counts.items()))}
        if p.get("folded_line"):
            folded_lines += 1
            out_lines.append({**base, "box": _box(0, y, BOX_W + 2 * LINE_PAD, LINE_HEAD), "machines": [], "pipes": [],
                              "inlet": None, "folded_line": True, "hidden": len(members)})
            y += LINE_HEAD + LINE_GAP
            continue
        mach = []
        pipes = []
        max_col = 0
        top = y + LINE_HEAD
        for row, (k, c, tp) in enumerate(p["rows"]):
            a = agents[k]
            max_col = max(max_col, c)
            o, oe, cost = tot.get(k, (0, 0, None))
            tl = tools.get(k)
            since_dt = _parse(a["state_since"])
            mach.append({
                "key": k, "kind": a["kind"], "name": _name(a), "parent": a["parent_key"], "state": a["state"],
                "rule": a["state_reason"], "since": a["state_since"] or None,
                "elapsed_s": max(0, int((now - since_dt).total_seconds())) if since_dt else None,
                "tool": tl[2] if tl else None, "target": tl[3] if tl else None,
                "out_total": o, "out_est_total": oe, "cost_est_usd": cost,
                "spark": sparks.get(k, [0] * usage.SPARK_MINUTES), "folded": p["folded"].get(k, 0),
                "wake_at": wake.get(k) if a["state"] == "SLEEPING" else None,
                "box": _box(LINE_PAD + c * (BOX_W + GAP_X), top + row * (BOX_H + GAP_Y)),
            })
            if tp:
                kd = "workflow" if agents[tp]["kind"] == "WORKFLOW" else "spawn"
                pipes.append({"src": tp, "dst": k, "kind": kd, "at": edge_at.get((tp, k, kd)) or a["started_at"]})
            elif a["kind"] != "SESSION" and not _cross_line(k, agents):   # 다른 라인 부모는 links 로만
                pipes.append({"src": f"U:{ln['key']}", "dst": k, "kind": "spawn", "at": a["started_at"]})
        inlet = None
        if p["has_inlet"]:
            r0 = p["inlet_row"] if p["inlet_row"] is not None else len(p["rows"])
            inlet = {"key": f"U:{ln['key']}", "name": INLET_NAME, "folded": p["inlet_folded"],
                     "box": _box(LINE_PAD, top + r0 * (BOX_H + GAP_Y))}
        n_rows = max(len(p["rows"]), (p["inlet_row"] + 1) if p["inlet_row"] is not None else (
            len(p["rows"]) + 1 if inlet else 0), 1)
        h = LINE_HEAD + n_rows * (BOX_H + GAP_Y) - GAP_Y + LINE_PAD
        w = 2 * LINE_PAD + (max_col + 1) * BOX_W + max_col * GAP_X
        out_lines.append({**base, "box": _box(0, y, w, h), "machines": mach, "pipes": pipes, "inlet": inlet,
                          "folded_line": False, "hidden": 0})
        y += h + LINE_GAP

    # 같은 라인 안 handback → pipes · message 와 라인 간 spawn/workflow/handback → links
    line_of = {m["key"]: ln for ln in out_lines for m in ln["machines"]}
    links: dict[tuple, int] = {}
    for s, d, kd, at, cnt in raw_edges:
        if s not in line_of:
            continue
        if kd == "message":
            if d in line_of or d.startswith("X:"):
                links[(s, d, kd)] = links.get((s, d, kd), 0) + int(cnt or 1)
            continue
        if d not in line_of:
            continue
        if line_of[s] is line_of[d]:
            if kd == "handback":
                line_of[s]["pipes"].append({"src": s, "dst": d, "kind": kd, "at": at})
            continue
        links[(s, d, kd)] = max(links.get((s, d, kd), 0), int(cnt or 1))
    for k, ln in line_of.items():                      # 다른 라인의 부모 — edge 표에 없어도 parent_key 로
        p = agents[k]["parent_key"]
        if p and p != k and p in line_of and line_of[p] is not ln:
            kd = "workflow" if agents[p]["kind"] == "WORKFLOW" else "spawn"
            links.setdefault((p, k, kd), 1)
    for ln in out_lines:
        ln["pipes"].sort(key=lambda x: (x["kind"], x["src"], x["dst"]))

    return {
        "generated_at": _iso(now),
        "lines": out_lines,
        "links": [{"src": s, "dst": d, "kind": kd, "count": c} for (s, d, kd), c in sorted(links.items())],
        "folded_lines": folded_lines,
        "agents_in_scope": len(agents),
        "filters": {"since": since_iso, "since_arg": since or "24h", "project": proj_filter or None},
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }


def _cross_line(k: str, agents: dict) -> bool:
    p = agents[k]["parent_key"]
    return bool(p and p != k and p in agents and agents[p]["project_key"] != agents[k]["project_key"])


def _in_cycle(k: str, agents: dict, tree_parent) -> bool:
    """k 에서 부모 사슬을 따라 올라가 다시 k 에 닿으면 순환."""
    seen = set()
    cur = tree_parent(k)
    while cur and cur not in seen:
        if cur == k:
            return True
        seen.add(cur)
        cur = tree_parent(cur)
    return False


def _boxes_overlap(a: dict, b: dict) -> bool:
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def _pairs(boxes: list[dict]) -> int:
    boxes = sorted(boxes, key=lambda b: (b["y"], b["x"]))
    n = 0
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if b["y"] >= a["y"] + a["h"]:
                break
            if _boxes_overlap(a, b):
                n += 1
    return n


def overlaps(resp: dict) -> int:
    """설비 상자(반입구 포함) 쌍 겹침 수 + 라인 상자 쌍 겹침 수 (T-04). 닿기만 하면 겹침 아님."""
    mboxes = []
    lboxes = []
    for ln in resp.get("lines", []):
        if "box" in ln:
            lboxes.append(ln["box"])
        mboxes.extend(m["box"] for m in ln.get("machines", []))
        if ln.get("inlet"):
            mboxes.append(ln["inlet"]["box"])
    return _pairs(mboxes) + (_pairs(lboxes) if len(lboxes) > 1 else 0)


def scope_count(resp: dict) -> int:
    """칸 수 + 접힌 수 (설비 folded · 반입구 folded · 접힌 라인 hidden). V-17: = 범위 안 에이전트 수 (`agents_in_scope`)."""
    n = 0
    for ln in resp.get("lines", []):
        n += len(ln.get("machines", [])) + sum(m.get("folded", 0) for m in ln.get("machines", []))
        n += (ln.get("inlet") or {}).get("folded", 0) + ln.get("hidden", 0)
    return n
