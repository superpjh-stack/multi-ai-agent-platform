"""구성도 데이터 (spec.md §5) — Cytoscape 형식 `{nodes, edges}`. 담당 개발2.

    graph.build(con, since="24h", project=None, view="tree", states=None, kinds=None, min_tokens=0, expand=()) -> dict

노드 5 종 (`data.kind`)
  PROJECT     둥근 사각형 묶음(compound) — 라벨 = 폴더 마지막 이름
  SESSION     원 · 굵은 테두리 · 크기 √출력 토큰
  SUBAGENT    원 (WORKFLOW_AGENT 도 이 모양 — `data.agent_kind` 로 구분) · 라벨 = 유형 + 이름 앞 24 자
  WORKFLOW    육각형 · 라벨 = 이름 · 에이전트 N
  UNRESOLVED  점선 원 — L-05 "부모 미확인" (`U:<project>`) · L-06 "외부" (`X:<name>`) 는 kind EXTERNAL
엣지 4 종 (`data.kind`) — spawn(실선) · message(점선, 굵기 = 횟수) · handback(가는 실선, 기본 숨김) · workflow(실선)
  부모 미확인 노드 → 자식 엣지는 kind spawn + `data.unresolved = 1` (점선).

선택: 기간(`since`, 기본 최근 24 시간) 안에 기록이 있거나 살아 있는(DONE · FAILED 아님) 에이전트 + 그 조상(구조를 잇기 위해,
  필터에 안 맞는 조상은 `classes` 에 `ctx` — 흐리게). 노드가 `NODE_LIMIT`(300) 을 넘으면 DONE 서브에이전트(자손이 모두 접힌 것)를
  부모 안으로 접고 부모 라벨에 "+N" (`data.folded`). `expand` 에 준 키의 직계 자식은 접지 않는다.
보기 3 종: tree(breadthfirst — 프로젝트 묶음마다) · collab(cose — message 강조) · pipeline(프로젝트를 `NN` 열로 고정, `data.col`).
본문은 싣지 않는다 — 이름 · 키 · 상태 · 규칙 코드 · 숫자뿐.
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime, timedelta, timezone

NODE_LIMIT = 300
VIEWS = {"tree": "breadthfirst", "collab": "cose", "pipeline": "preset"}
FINAL = ("DONE", "FAILED")
HUMAN = ("WAITING_INPUT", "WAITING_PERMISSION")       # 사람 행동 필요 — 배지 !
CHECK = ("FAILED", "STALE")                           # 확인 필요 — 배지 ?
FOLDABLE_KINDS = ("SUBAGENT", "WORKFLOW_AGENT")
EXTERNAL_PROJECT = "P:__external__"
_TYPE_ABBR = {"general-purpose": "GP", "Explore": "EX", "fork": "FK", "workflow-subagent": "WF", "Plan": "PL"}
_COL = re.compile(r"^(\d{2})\s")


class GraphError(ValueError):
    """잘못된 필터 값 — API 가 422 로 돌려준다 (조용히 기본값으로 바꾸지 않는다)."""


def parse_since(since: str | None, now: datetime) -> datetime | None:
    """None/'' → 24 시간 전 · 'all' → None(전체) · '6h' · '7d' · '30m' · ISO 날짜/시각."""
    if since is None or since == "":
        return now - timedelta(hours=24)
    s = since.strip()
    if s.lower() == "all":
        return None
    m = re.fullmatch(r"(\d{1,5})([mhd])", s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return now - {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[u]
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise GraphError(f"since 형식 오류: {s[:40]!r} (24h · 7d · all · ISO 시각)") from None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _csv(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, (list, tuple, set)):
        items = [str(x) for x in v]
    else:
        items = str(v).split(",")
    return [x.strip() for x in items if x and x.strip()]


def project_label(project_key: str, project_path: str | None) -> str:
    """에이전트 한 행의 폴더 이름 (D-03 목록 등). 프로젝트(라인) 이름은 `project_names` — D-28."""
    if project_path:
        return project_path.rstrip("/").rsplit("/", 1)[-1][:60] or project_key[:60]
    return project_key.rsplit("-", 1)[-1][:60] or project_key[:60]


def project_names(rows) -> dict[str, str]:
    """D-28 (spec v0.4.1 §5.4): 프로젝트(= 라인) 이름 = 그 project_key 의 project_path 중 가장 짧은 것
    (길이가 같으면 사전순 첫 번째)의 마지막 이름, 경로가 하나도 없으면 project_key. rows = (project_key, project_path) 들.
    행 순서와 무관 (T-07). D-01 트윈 · D-02 구성도 · 프로젝트 필터가 같이 쓴다."""
    best: dict[str, str | None] = {}
    for pk, pp in rows:
        if pk is None:
            continue
        p = (pp or "").rstrip("/")
        cur = best.get(pk)
        if p and (cur is None or (len(p), p) < (len(cur), cur)):
            best[pk] = p
        else:
            best.setdefault(pk, None)
    return {pk: (project_label(pk, p) if p else pk[:60]) for pk, p in best.items()}


def project_match(proj_filter: str, project_key: str, name: str) -> bool:
    """프로젝트 필터 (D-01 · D-02 공통, DEF-QA1-401): project_key 와 같거나 라인 이름(`project_names`)에 들어 있으면."""
    return project_key == proj_filter or proj_filter in name


def pipeline_col(label: str) -> int | None:
    m = _COL.match(label or "")
    return int(m.group(1)) if m else None


def node_size(output_tokens: int) -> int:
    """√출력 토큰 비례 (spec §5.1) — 18 ~ 90 px."""
    return int(min(90, 18 + math.sqrt(max(0, output_tokens or 0)) / 8))


def _agent_label(a: dict) -> str:
    name = (a["name"] or "").strip()
    if a["kind"] == "SESSION":
        return f"{(name or a['agent_key'][2:10])[:32]} · {a['state']}"
    if a["kind"] == "WORKFLOW":
        return f"{(name or a['agent_key'][2:])[:24]} · 에이전트 {a['n_children']}"
    abbr = _TYPE_ABBR.get(a["agent_type"] or "", (a["agent_type"] or "?")[:2].upper())
    return f"[{abbr}] {(name or a['agent_key'][2:8])[:24]}"


_AGENT_SQL = ("SELECT agent_key, kind, project_key, project_path, session_id, parent_key, depth, agent_type, name, "
              "model, started_at, last_event_at, ended_at, state, state_reason, state_since FROM agent")
_COLS = ("agent_key", "kind", "project_key", "project_path", "session_id", "parent_key", "depth", "agent_type", "name",
         "model", "started_at", "last_event_at", "ended_at", "state", "state_reason", "state_since")


def build(con, *, since: str | None = None, project: str | None = None, view: str | None = None,
          states=None, kinds=None, min_tokens: int | None = 0, expand=(), now: datetime | None = None,
          node_limit: int = NODE_LIMIT, show_handback: bool = True) -> dict:
    t0 = time.perf_counter()
    now = now or datetime.now(timezone.utc)
    view = view or "tree"
    if view not in VIEWS:
        raise GraphError(f"view 는 {'/'.join(VIEWS)} 중 하나 (받은 값 {view[:20]!r})")
    since_t = parse_since(since, now)
    since_iso = _iso(since_t) if since_t else None
    want_states = set(_csv(states))
    want_kinds = set(_csv(kinds))
    try:
        min_tok = int(min_tokens or 0)
    except (TypeError, ValueError):
        raise GraphError(f"min_tokens 는 정수 (받은 값 {str(min_tokens)[:20]!r})") from None
    expand_set = set(_csv(expand))

    agents = {r[0]: dict(zip(_COLS, r)) for r in con.execute(_AGENT_SQL)}
    tokens = {k: int(v or 0) for k, v in con.execute(
        "SELECT agent_key, SUM(output_tokens) FROM usage_event GROUP BY agent_key")}
    children: dict[str, list[str]] = {}
    for k, a in agents.items():
        a["out"] = tokens.get(k, 0)
        if a["parent_key"]:
            children.setdefault(a["parent_key"], []).append(k)
    for k, a in agents.items():
        a["n_children"] = len(children.get(k, ()))

    proj_filter = (project or "").strip()
    all_projects = project_names((a["project_key"], a["project_path"]) for a in agents.values())   # D-28

    def proj_ok(a) -> bool:
        if not proj_filter:
            return True
        return project_match(proj_filter, a["project_key"], all_projects.get(a["project_key"], ""))

    def matches(a) -> bool:
        if not proj_ok(a):
            return False
        if want_states and a["state"] not in want_states:
            return False
        if want_kinds and a["kind"] not in want_kinds:
            return False
        if min_tok and a["kind"] in ("SESSION", "SUBAGENT", "WORKFLOW_AGENT") and a["out"] < min_tok:
            return False
        alive = a["state"] not in FINAL
        recent = since_iso is None or max(a["last_event_at"] or "", a["started_at"] or "") >= since_iso
        return alive or recent

    picked = {k for k, a in agents.items() if matches(a)}
    shown = set(picked)
    for k in picked:                      # 조상을 붙여 트리를 잇는다
        cur = agents[k]["parent_key"]
        seen = 0
        while cur and cur in agents and cur not in shown and seen < 50:
            shown.add(cur)
            cur = agents[cur]["parent_key"]
            seen += 1
    # 부모 미확인(parent_key 없음) 서브에이전트는 세션에 억지로 잇지 않고 U:<project> 노드에 붙인다 (L-05)

    # ── 엣지 후보 ──
    raw_edges = con.execute("SELECT src_key, dst_key, kind, at, count, label FROM edge ORDER BY src_key, dst_key, kind").fetchall()

    # ── 접기 ──
    def count_nodes(keys: set[str]) -> int:
        projs = {agents[k]["project_key"] for k in keys}
        unres = {agents[k]["project_key"] for k in keys if agents[k]["kind"] != "SESSION" and not agents[k]["parent_key"]}
        ext = {d for s, d, kd, *_ in raw_edges if kd == "message" and d.startswith("X:") and s in keys}
        return len(keys) + len(projs) + len(unres) + len(ext) + (1 if ext else 0)

    folded_into: dict[str, str] = {}
    folded_n: dict[str, int] = {}
    total_before = count_nodes(shown)
    if total_before > node_limit:
        order = sorted(shown, key=lambda k: (-(agents[k]["depth"] or 0), k))   # T-07 · 행 순서 무관
        remaining_children = {k: sum(1 for c in children.get(k, ()) if c in shown) for k in shown}
        for k in order:
            a = agents[k]
            if a["kind"] not in FOLDABLE_KINDS or a["state"] != "DONE":
                continue
            if remaining_children.get(k, 0) > 0:
                continue                   # 아직 펼친 자식이 있다 — 부모를 접으면 자식이 떠다닌다
            p = a["parent_key"]
            target = p if p in shown and p not in folded_into else (f"U:{a['project_key']}" if not p else None)
            if target is None or (p and p in expand_set):
                continue
            folded_into[k] = target
            folded_n[target] = folded_n.get(target, 0) + 1 + folded_n.pop(k, 0)
            if p in remaining_children:
                remaining_children[p] -= 1
        shown -= set(folded_into)

    # ── 노드 ──
    nodes: list[dict] = []
    proj_used: dict[str, str] = {}
    for k in shown:
        proj_used.setdefault(agents[k]["project_key"], all_projects[agents[k]["project_key"]])
    for pk, label in sorted(proj_used.items(), key=lambda x: (x[1], x[0])):
        col = pipeline_col(label)
        nodes.append({"data": {"id": f"P:{pk}", "kind": "PROJECT", "label": label, "project": pk,
                               "col": col, "col_label": f"{col:02d}" if col is not None else "기타", "size": 30, "depth": 0},
                      "classes": "project"})
    unresolved: set[str] = set()
    for k in sorted(shown, key=lambda x: (agents[x]["depth"] or 0, x)):
        a = agents[k]
        st = a["state"]
        cls = ["agent", a["kind"].lower(), f"st-{st}"]
        if a["kind"] == "WORKFLOW_AGENT":
            cls.append("subagent")
        if k not in picked:
            cls.append("ctx")
        badge = "!" if st in HUMAN else ("?" if st in CHECK else "")
        if badge:
            cls.append("badge")
        if a["state_reason"] == "R-12":
            cls.append("slow")
        fold = folded_n.get(k, 0)
        label = _agent_label(a) + (f"  +{fold}" if fold else "")
        kind = "SUBAGENT" if a["kind"] == "WORKFLOW_AGENT" else a["kind"]
        size = node_size(a["out"]) if kind in ("SESSION", "SUBAGENT") else 36
        nodes.append({"data": {
            "id": k, "kind": kind, "agent_kind": a["kind"], "label": label, "state": st, "rule": a["state_reason"],
            "project": a["project_key"], "parent": f"P:{a['project_key']}", "agent_type": a["agent_type"],
            "depth": a["depth"] or 0, "out": a["out"], "size": size, "badge": badge, "folded": fold,
            "children": a["n_children"], "last": a["last_event_at"], "name": (a["name"] or "")[:60],
        }, "classes": " ".join(cls)})
        if a["kind"] != "SESSION" and not a["parent_key"]:
            unresolved.add(a["project_key"])
    for pk in sorted(unresolved | {t[2:] for t in folded_n if t.startswith("U:")}):
        if pk not in proj_used:
            continue
        uk = f"U:{pk}"
        fold = folded_n.get(uk, 0)
        nodes.append({"data": {"id": uk, "kind": "UNRESOLVED", "label": "부모 미확인 (L-05)" + (f"  +{fold}" if fold else ""),
                               "project": pk, "parent": f"P:{pk}", "depth": 0, "size": 30, "folded": fold,
                               "state": "UNRESOLVED"}, "classes": "unresolved"})

    ids = {n["data"]["id"] for n in nodes}

    # ── 엣지 ──
    edges: list[dict] = []
    seen_e: set[tuple[str, str, str]] = set()
    dropped = 0
    ext_nodes: dict[str, str] = {}

    def add_edge(src, dst, kind, count=1, label=None, unresolved_edge=False):
        key = (src, dst, kind)
        if key in seen_e:
            return
        seen_e.add(key)
        d = {"id": f"{kind}:{src}>{dst}", "source": src, "target": dst, "kind": kind, "count": int(count or 1)}
        if label:
            d["label"] = str(label)[:40]
        if kind == "message":
            d["width"] = min(8, 1 + int(count or 1))
        if unresolved_edge:
            d["unresolved"] = 1
        cls = [f"e-{kind}"] + (["unresolved"] if unresolved_edge else [])
        edges.append({"data": d, "classes": " ".join(cls)})

    for k in sorted(shown):
        a = agents[k]
        if a["kind"] == "SESSION":
            continue
        p = a["parent_key"]
        if p and p in ids:
            add_edge(p, k, "workflow" if agents.get(p, {}).get("kind") == "WORKFLOW" else "spawn")
        elif not p and f"U:{a['project_key']}" in ids:
            add_edge(f"U:{a['project_key']}", k, "spawn", unresolved_edge=True)
    for src, dst, kind, at, count, label in raw_edges:
        if kind == "handback" and not show_handback:
            continue
        if kind == "message" and dst.startswith("X:") and src in ids:
            ext_nodes.setdefault(dst, label or dst[2:])
            add_edge(src, dst, kind, count, label)
            continue
        if src in ids and dst in ids:
            add_edge(src, dst, kind, count, label)
        elif src in folded_into or dst in folded_into:
            dropped += 1                   # 접힌 노드에 닿는 엣지 — 부모의 +N 안에 들어 있다
    if ext_nodes:
        nodes.append({"data": {"id": EXTERNAL_PROJECT, "kind": "PROJECT", "label": "외부 (L-06)", "project": "",
                               "col": None, "col_label": "기타", "size": 30, "depth": 0},
                      "classes": "project external-group"})
        for xk, lab in sorted(ext_nodes.items()):
            nodes.append({"data": {"id": xk, "kind": "EXTERNAL", "label": f"외부: {str(lab)[:24]}",
                                   "parent": EXTERNAL_PROJECT, "depth": 0, "size": 30, "state": "EXTERNAL"},
                          "classes": "unresolved external"})

    n_agent_nodes = sum(1 for n in nodes if n["data"]["kind"] in ("SESSION", "SUBAGENT", "WORKFLOW"))
    return {
        "nodes": nodes, "edges": edges, "view": view, "layout": VIEWS[view],
        "stats": {
            "nodes": len(nodes), "edges": len(edges), "agent_nodes": n_agent_nodes, "agents_total": len(agents),
            "agents_picked": len(picked), "folded": len(folded_into), "nodes_before_fold": total_before,
            "limit": node_limit, "edges_dropped_folded": dropped, "unresolved_groups": len(unresolved),
            "external": len(ext_nodes), "ms": round((time.perf_counter() - t0) * 1000, 1),
        },
        "filters": {"since": since_iso, "since_arg": since or "24h", "project": proj_filter or None,
                    "states": sorted(want_states), "kinds": sorted(want_kinds), "min_tokens": min_tok,
                    "expand": sorted(expand_set)},
        "projects": [{"key": k, "label": v, "col": pipeline_col(v)} for k, v in sorted(all_projects.items(),
                                                                                    key=lambda x: (x[1], x[0]))],
    }
