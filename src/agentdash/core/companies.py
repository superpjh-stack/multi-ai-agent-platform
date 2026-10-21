"""회사별 관찰 화면. 기존 회사 사전과 수집된 메타데이터만으로 묶는다.

소속은 화면용 분류이며 DB의 관계·상태는 변경하지 않는다. 여러 회사가
겹친 근거는 미확인으로 남기고, 공용 프로젝트 전체에 소속을 전파하지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

from agentdash.core import pipeline
from agentdash.core.graph import project_names

UNKNOWN = "__unknown__"
FINAL = {"DONE", "FAILED"}
HUMAN = {"WAITING_PERMISSION", "WAITING_INPUT"}


def overview(con, now: datetime, selected: str = "") -> dict:
    dictionary = pipeline.load_dictionary()
    rows = [dict(r) for r in con.execute(
        "SELECT agent_key, kind, name, agent_type, project_key, project_path, "
        "parent_key, state, last_event_at FROM agent"
    )]
    names = project_names([(r["project_key"], r["project_path"]) for r in rows])
    agents = {r["agent_key"]: r for r in rows}
    cutoff = (now - timedelta(minutes=30)).isoformat()
    # 최신 시각의 근거가 여럿이면 합쳐서 모호함을 보존한다. 질의 수는 고정.
    targets: dict[str, tuple[float, set[str]]] = {}
    for key, at, target in con.execute(
        "SELECT agent_key, julianday(at) AS event_time, target FROM tool_call WHERE tool IN ('Read','Write','Edit','NotebookEdit') "
        "AND julianday(at) >= julianday(?) AND julianday(at) <= julianday(?) "
        "UNION ALL SELECT agent_key, julianday(at), path FROM file_touch "
        "WHERE julianday(at) >= julianday(?) AND julianday(at) <= julianday(?) "
        "ORDER BY event_time DESC", (cutoff, now.isoformat(), cutoff, now.isoformat())
    ):
        hits = dictionary.find_in(target or "")
        if not hits:
            continue
        if key not in targets:
            targets[key] = (at, hits)
        elif targets[key][0] == at:
            targets[key][1].update(hits)

    direct: dict[str, tuple[set[str], str]] = {}
    for key, a in agents.items():
        hits = dictionary.find_in(" ".join((a["name"] or "", a["project_path"] or a["project_key"])))
        if hits:
            direct[key] = (hits, "이름·프로젝트 경로")
        elif key in targets and a["state"] not in FINAL:
            direct[key] = (targets[key][1], "최근 30분 작업 대상")

    def resolve(key: str) -> tuple[str, str]:
        seen: set[str] = set()
        current = key
        while current in agents and current not in seen:
            seen.add(current)
            if current in direct:
                hits, basis = direct[current]
                if len(hits) != 1:
                    return UNKNOWN, "여러 회사 근거가 겹침"
                return next(iter(hits)), basis if current == key else "부모 에이전트 · " + basis
            current = agents[current]["parent_key"]
        return UNKNOWN, "회사 연결 근거 없음"

    result = pipeline.cached(con)
    next_codes = result.next_stage()
    stage_by_code = {s["code"]: s for s in result.stages}
    groups = {co: {"key": co, "name": co, "agents": [], "projects": {}, "running": 0,
                   "waiting": 0, "check": 0, "alive": 0, "done": 0,
                   "next": stage_by_code.get(next_codes.get(co)),
                   "unknown_stages": sum(c.base_status == "UNKNOWN" for c in result.cells if c.company == co),
                   "decisions": [c for c in result.cells if c.company == co and c.status == "NEEDS_DECISION"]}
              for co in dictionary.names}
    groups[UNKNOWN] = {"key": UNKNOWN, "name": "회사 미확인", "agents": [], "projects": {},
                       "running": 0, "waiting": 0, "check": 0, "alive": 0, "done": 0,
                       "next": None, "decisions": [], "unknown_stages": 0}
    for key, a in agents.items():
        if a["kind"] == "WORKFLOW":
            continue  # 워크플로 묶음은 에이전트 수에서 제외 (기존 요약과 동일)
        company, basis = resolve(key)
        g = groups[company]
        a.update(basis=basis, project=names[a["project_key"]])
        g["agents"].append(a)
        g["projects"][a["project_key"]] = names[a["project_key"]]
        g["running"] += a["state"] == "RUNNING"
        g["waiting"] += a["state"] in HUMAN
        g["check"] += a["state"] in {"STALE", "FAILED", "UNKNOWN"}
        g["alive"] += a["state"] not in FINAL
        g["done"] += a["state"] == "DONE"
    for g in groups.values():
        g["url"] = "/?" + urlencode({"company": g["key"]}) + "#company-hub"
        g["agents"].sort(key=lambda a: (
            0 if a["state"] == "WAITING_PERMISSION" else 1 if a["state"] == "WAITING_INPUT" else
            2 if a["state"] in {"STALE", "FAILED", "UNKNOWN"} else 3 if a["state"] not in FINAL else 4,
            a["name"] or a["agent_key"], a["agent_key"]))
        g["projects"] = [{"name": label, "url": "/?" + urlencode({"project": key}) + "#floor",
                           "graph_url": "/graph?" + urlencode({"project": key})}
                          for key, label in sorted(g["projects"].items(), key=lambda p: (p[1], p[0]))]
    ordered = sorted(groups.values(), key=lambda g: (
        g["key"] == UNKNOWN, -g["waiting"], -len(g["decisions"]), -g["running"], -g["alive"], g["name"]))
    return {"groups": ordered, "selected": groups.get(selected),
            "invalid": bool(selected and selected not in groups), "evaluated_at": result.evaluated_at,
            "total": sum(len(g["agents"]) for g in ordered)}
