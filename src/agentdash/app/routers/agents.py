"""GET /api/v1/summary · /api/v1/agents · /api/v1/agents/{key} · /api/v1/agents/{key}/tools — 담당 개발2.

화면 D-01 · D-03 (routers/pages.py) 도 여기 질의 도우미를 쓴다. 전부 읽기만 한다(DB 쓰기 0).
· 상태 · 규칙 코드 · 근거(evidence)는 저장된 값과 "지금 판정"(state.evaluate — 쓰지 않음)을 둘 다 낸다.
· 비용은 늘 `[추정] API 정가 환산` 표기와 단가 없음 건수를 같이 낸다(spec §6.1).
· "원본 보기"(raw_messages)는 요청 때 원천 .jsonl 을 읽기 전용으로 열어 응답으로만 보낸다 — DB · 캐시 · 로그에 남기지 않는다.
  도구 입력은 경로와 첫 줄 120 자, 도구 결과 · thinking 은 크기만.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from agentdash import settings
from agentdash.db import conn

router = APIRouter()
KST = timezone(timedelta(hours=9))
FINAL = ("DONE", "FAILED")
HUMAN = ("WAITING_INPUT", "WAITING_PERMISSION")
CARD_STATES = ("RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "SLEEPING", "WAITING_CHILD", "STALE")
STATE_KO = {"RUNNING": "실행", "WAITING_INPUT": "입력 대기", "WAITING_PERMISSION": "권한 대기", "SLEEPING": "잠듦",
            "WAITING_CHILD": "자식 대기", "DONE": "끝남", "FAILED": "실패", "STALE": "멈춤 의심", "UNKNOWN": "판정 전"}
COST_LABEL = "[추정] API 정가 환산"
SHORT = 120


# ── 시각 ─────────────────────────────────────────────────────────────
def dt(s) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def kst(s) -> str:
    t = dt(s)
    return t.astimezone(KST).strftime("%m-%d %H:%M:%S") if t else "—"


def ago(s, now: datetime) -> int | None:
    t = dt(s)
    return int((now - t).total_seconds()) if t else None


def dur(sec) -> str:
    if sec is None:
        return "—"
    sec = int(sec)
    if sec < 0:
        return "0초"
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}일 {h}시간"
    if h:
        return f"{h}시간 {m}분"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


def today_start_utc(now: datetime) -> str:
    k = now.astimezone(KST)
    start = k.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    return start.strftime("%Y-%m-%dT%H:%M:%S")


def _con():
    return conn.connect()


def _rows(con, sql, args=()):
    cur = con.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _tokens(con, keys: list[str] | None = None) -> dict[str, int]:
    if keys is None:
        return {k: int(v or 0) for k, v in con.execute("SELECT agent_key, SUM(output_tokens) FROM usage_event GROUP BY 1")}
    out: dict[str, int] = {}
    for i in range(0, len(keys), 500):
        part = keys[i:i + 500]
        for k, v in con.execute(f"SELECT agent_key, SUM(output_tokens) FROM usage_event WHERE agent_key IN "
                                f"({','.join('?' * len(part))}) GROUP BY 1", part):
            out[k] = int(v or 0)
    return out


#: 가설 규칙으로 정한 판정 표시 (DEF-QA2-102) — D-18: S1 busy 인데 미래 ScheduleWakeup → SLEEPING R-03 (spec 글자로는 STALE R-02b)
D18_NOTE = "가설 D-18"


def hypothesis_note(state: str | None, rule: str | None, evidence: str | None) -> str | None:
    """판정이 사람 확인 전 가설(decisions.md D-18)에 기댄 것이면 표시 문구. 근거 문자열은 300 자에서 잘릴 수 있어
    앞쪽의 `S1 status=busy` 로도 본다 (idle 의 R-03 은 spec 그대로)."""
    if state != "SLEEPING" or rule != "R-03" or not evidence:
        return None
    return D18_NOTE if ("D-18" in evidence or "status=busy" in evidence) else None


def _last_evidence(con, keys: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in keys:
        r = con.execute("SELECT reason FROM state_log WHERE agent_key=? ORDER BY at DESC, rowid DESC LIMIT 1",
                        (k,)).fetchone()
        if r and r[0]:
            out[k] = r[0]
    return out


def project_label(project_key: str, project_path: str | None) -> str:
    from agentdash.core.graph import project_label as pl
    return pl(project_key, project_path)


# ── D-01 관제판 ─────────────────────────────────────────────────────
def summary_data(con, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = today_start_utc(now)
    by_state = {s: 0 for s in (*CARD_STATES, "DONE", "FAILED")}
    for st, n in con.execute("SELECT state, COUNT(*) FROM agent WHERE kind != 'WORKFLOW' GROUP BY state"):
        by_state[st] = n                       # 모르는 상태(UNKNOWN 등)도 그대로 센다 — 숨기지 않는다
    done_today = dict(con.execute(
        "SELECT state, COUNT(*) FROM agent WHERE kind != 'WORKFLOW' AND state IN ('DONE','FAILED') "
        "AND COALESCE(ended_at, last_event_at) >= ? GROUP BY state", (start,)).fetchall())
    out_tok = con.execute("SELECT COALESCE(SUM(output_tokens),0), COUNT(*) FROM usage_event WHERE at >= ?",
                          (start,)).fetchone()
    tools = con.execute("SELECT COUNT(*) FROM tool_call WHERE at >= ?", (start,)).fetchone()[0]
    files = con.execute("SELECT COUNT(DISTINCT path) FROM file_touch WHERE at >= ? AND op IN ('Write','Edit','NotebookEdit')",
                        (start,)).fetchone()[0]
    top = _rows(con, "SELECT u.agent_key, a.name, a.kind, a.project_key, a.project_path, a.state, "
                     "SUM(u.output_tokens) AS out FROM usage_event u LEFT JOIN agent a ON a.agent_key=u.agent_key "
                     "WHERE u.at >= ? GROUP BY u.agent_key ORDER BY out DESC LIMIT 5", (start,))
    for t in top:
        t["project"] = project_label(t["project_key"] or "", t["project_path"])
        t.pop("project_path", None)
    parse_errors = con.execute("SELECT COUNT(*) FROM parse_error").fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM agent WHERE kind != 'WORKFLOW'").fetchone()[0]
    alive = sum(n for s, n in by_state.items() if s not in FINAL)
    return {
        "states": by_state, "done_today": {"DONE": done_today.get("DONE", 0), "FAILED": done_today.get("FAILED", 0)},
        "today": {"since_utc": start, "output_tokens": int(out_tok[0]), "requests": out_tok[1], "tool_calls": tools,
                  "files_written": files, "top": top},
        "parse_errors": parse_errors, "agents_total": total, "alive": alive, "at": now.isoformat(timespec="seconds"),
    }


def _last_tools(con, keys: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for k in keys:
        r = con.execute("SELECT tool, target, ok, at, result_at FROM tool_call WHERE agent_key=? ORDER BY at DESC LIMIT 1",
                        (k,)).fetchone()
        if r:
            out[k] = {"tool": r[0], "target": (r[1] or "")[:SHORT], "ok": r[2], "at": r[3], "running": r[4] is None}
    return out


def my_turn(con, now: datetime | None = None) -> list[dict]:
    """`WAITING_INPUT` · `WAITING_PERMISSION` — 기다린 시간 긴 순. 기준 시각 = 마지막 기록(없으면 상태가 된 시각)."""
    now = now or datetime.now(timezone.utc)
    rows = _rows(con, "SELECT agent_key, kind, name, project_key, project_path, session_id, state, state_reason, "
                      "state_since, last_event_at FROM agent WHERE state IN ('WAITING_INPUT','WAITING_PERMISSION')")
    tools = _last_tools(con, [r["agent_key"] for r in rows])
    for r in rows:
        base = r["last_event_at"] or r["state_since"]
        r["wait_sec"] = ago(base, now)
        r["wait"] = dur(r["wait_sec"])
        r["wait_basis"] = "마지막 기록" if r["last_event_at"] else "상태 시각"
        r["project"] = project_label(r["project_key"], r["project_path"])
        r["last_tool"] = tools.get(r["agent_key"])
        r["cwd"] = r["project_path"] or ""
    rows.sort(key=lambda r: (0 if r["state"] == "WAITING_PERMISSION" else 1, -(r["wait_sec"] or 0)))
    return rows


def live_agents(con, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rows = _rows(con, "SELECT agent_key, kind, name, agent_type, project_key, project_path, state, state_reason, "
                      "started_at, last_event_at, depth FROM agent WHERE state NOT IN ('DONE','FAILED') "
                      "AND kind != 'WORKFLOW' ORDER BY last_event_at DESC")
    keys = [r["agent_key"] for r in rows]
    tok = _tokens(con, keys)
    tools = _last_tools(con, keys)
    kids = dict(con.execute("SELECT parent_key, COUNT(*) FROM agent WHERE parent_key IS NOT NULL GROUP BY 1").fetchall())
    evid = _last_evidence(con, [r["agent_key"] for r in rows if r["state"] == "SLEEPING"])
    for r in rows:
        r["hypothesis"] = hypothesis_note(r["state"], r["state_reason"], evid.get(r["agent_key"]))
        r["project"] = project_label(r["project_key"], r["project_path"])
        r["elapsed"] = dur(ago(r["started_at"], now))
        r["idle"] = dur(ago(r["last_event_at"], now))
        r["out"] = tok.get(r["agent_key"], 0)
        r["tool"] = tools.get(r["agent_key"])
        r["children"] = kids.get(r["agent_key"], 0)
    return rows


def feed(con, n: int = 30) -> list[dict]:
    rows = _rows(con, "SELECT l.agent_key, l.at, l.state, l.reason, a.name, a.kind FROM state_log l "
                      "LEFT JOIN agent a ON a.agent_key=l.agent_key ORDER BY l.at DESC, l.rowid DESC LIMIT ?", (n,))
    for r in rows:
        r["at_kst"] = kst(r["at"])
    return rows


# ── 목록 ────────────────────────────────────────────────────────────
def agent_list(con, *, state=None, project=None, kind=None, since=None, limit=500) -> list[dict]:
    q = ("SELECT agent_key, kind, name, agent_type, project_key, project_path, session_id, parent_key, depth, state, "
         "state_reason, started_at, last_event_at, ended_at FROM agent WHERE 1=1")
    args: list = []
    for col, v in (("state", state), ("kind", kind)):
        vals = [x.strip() for x in (v or "").split(",") if x.strip()]
        if vals:
            q += f" AND {col} IN ({','.join('?' * len(vals))})"
            args += vals
    if project:
        q += " AND (project_key = ? OR project_path LIKE ?)"
        args += [project, f"%{project}%"]
    if since:
        q += " AND last_event_at >= ?"
        args.append(since)
    q += " ORDER BY last_event_at DESC LIMIT ?"
    args.append(max(1, min(int(limit), 5000)))
    rows = _rows(con, q, args)
    tok = _tokens(con, [r["agent_key"] for r in rows])
    for r in rows:
        r["output_tokens"] = tok.get(r["agent_key"], 0)
        r["project"] = project_label(r["project_key"], r["project_path"])
    return rows


# ── D-03 상세 ───────────────────────────────────────────────────────
_AGENT_COLS = ("agent_key, kind, project_key, project_path, session_id, parent_key, spawn_tool_use, depth, agent_type, "
               "name, request_shape, model, cc_version, git_branch, started_at, last_event_at, ended_at, state, "
               "state_reason, state_since, pid")


def _agent(con, key: str) -> dict | None:
    r = _rows(con, f"SELECT {_AGENT_COLS} FROM agent WHERE agent_key=?", (key,))
    return r[0] if r else None


def live_verdict(con, a: dict, now: datetime) -> dict:
    """지금 판정 (쓰지 않음) — 규칙 코드 + 근거 값."""
    from agentdash.core import state as S
    row = (a["agent_key"], a["kind"], a["session_id"], a["last_event_at"], a["ended_at"])
    ctx = S.build_ctx(con, row, now, S.load_s1(), S._open_children(con))
    v = S.evaluate({"kind": a["kind"]}, ctx, now)
    return {"state": v.state, "rule": v.rule, "evidence": v.evidence, "slow": v.slow,
            "matches_db": v.state == a["state"], "hypothesis": hypothesis_note(v.state, v.rule, v.evidence)}


def ancestors(con, a: dict) -> list[dict]:
    out = []
    cur = a["parent_key"]
    seen = {a["agent_key"]}
    while cur and cur not in seen and len(out) < 30:
        seen.add(cur)
        p = _rows(con, "SELECT agent_key, kind, name, state, parent_key FROM agent WHERE agent_key=?", (cur,))
        if not p:
            out.append({"agent_key": cur, "kind": "?", "name": "DB 에 없는 부모", "state": None, "missing": True})
            break
        out.append(p[0])
        cur = p[0]["parent_key"]
    out.reverse()
    return out


def children_of(con, key: str) -> list[dict]:
    rows = _rows(con, "SELECT agent_key, kind, name, agent_type, state, state_reason, started_at, last_event_at, ended_at "
                      "FROM agent WHERE parent_key=? ORDER BY started_at", (key,))
    tok = _tokens(con, [r["agent_key"] for r in rows])
    for r in rows:
        r["output_tokens"] = tok.get(r["agent_key"], 0)
        r["started_kst"] = kst(r["started_at"])
    return rows


def workload(con, a: dict, now: datetime) -> dict:
    from agentdash.core import usage as U
    key = a["agent_key"]
    own = U.totals(con, key)
    desc_keys = U.descendants(con, key)
    allt = U.totals(con, key, descendants=True)

    def hit(t):
        den = t["input_tokens"] + t["cache_read"] + t["cache_write"]
        return round(t["cache_read"] / den, 4) if den else None

    tools = _rows(con, "SELECT tool, COUNT(*) AS n, SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS ok, "
                       "SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END) AS err, SUM(CASE WHEN ok IS NULL THEN 1 ELSE 0 END) AS pending "
                       "FROM tool_call WHERE agent_key=? GROUP BY tool ORDER BY n DESC", (key,))
    files = con.execute("SELECT COUNT(DISTINCT path) FROM file_touch WHERE agent_key=? AND op IN ('Write','Edit','NotebookEdit')",
                        (key,)).fetchone()[0]
    stamps = [r[0] for r in con.execute("SELECT at FROM usage_event WHERE agent_key=? UNION ALL "
                                        "SELECT at FROM tool_call WHERE agent_key=? UNION ALL "
                                        "SELECT result_at FROM tool_call WHERE agent_key=? AND result_at IS NOT NULL",
                                        (key, key, key)) if r[0]]
    active = U.active_seconds(stamps)
    end = dt(a["ended_at"]) or (now if a["state"] not in FINAL else dt(a["last_event_at"]))
    wall = int((end - dt(a["started_at"])).total_seconds()) if end and dt(a["started_at"]) else None
    direct = con.execute("SELECT COUNT(*) FROM agent WHERE parent_key=?", (key,)).fetchone()[0]
    # 시간대별 출력 토큰 (KST 시각 단위, 기록 있는 마지막 48 칸)
    hours: dict[str, int] = {}
    for at, out in con.execute("SELECT at, output_tokens FROM usage_event WHERE agent_key=? ORDER BY at", (key,)):
        t = dt(at)
        if t:
            h = t.astimezone(KST).strftime("%m-%d %H시")
            hours[h] = hours.get(h, 0) + int(out or 0)
    hourly = list(hours.items())[-48:]
    return {"own": own, "with_descendants": allt, "cache_hit_own": hit(own), "cache_hit_all": hit(allt),
            "tool_calls": sum(t["n"] for t in tools), "tools_by_name": tools, "files_written": files,
            "active_seconds": active, "active": dur(active), "wall_seconds": wall, "wall": dur(wall),
            "children_direct": direct, "descendants_all": len(desc_keys), "hourly_output": hourly,
            "cost_label": COST_LABEL, "unpriced_note": f"단가 없음 {allt['unpriced']} 건" if allt["unpriced"] else ""}


def agent_detail(con, key: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    a = _agent(con, key)
    if a is None:
        return {"found": False, "key": key[:120], "reason": "agent 테이블에 이 키가 없다 (수집 전이거나 잘못된 키)"}
    log = _rows(con, "SELECT at, state, reason FROM state_log WHERE agent_key=? ORDER BY at DESC, rowid DESC LIMIT 20",
                (key,))
    a["project"] = project_label(a["project_key"], a["project_path"])
    parent = None
    if a["parent_key"]:
        parent = _rows(con, "SELECT agent_key, kind, name, state FROM agent WHERE agent_key=?", (a["parent_key"],))
        parent = parent[0] if parent else {"agent_key": a["parent_key"], "missing": True}
    link_note = None
    if a["kind"] != "SESSION" and not a["parent_key"]:
        link_note = "부모 미확인 — L-04(부모 기록 아직 안 읽힘) 또는 L-05(끝까지 못 찾음). 구성도에서 U:<프로젝트> 노드에 붙는다"
    files = _rows(con, "SELECT path, op, at FROM file_touch WHERE agent_key=? ORDER BY at", (key,))
    for f in files:
        f["at_kst"] = kst(f["at"])
    return {
        "found": True, "agent": a, "state": {"db": a["state"], "rule": a["state_reason"], "since": a["state_since"],
                                             "evidence": log[0]["reason"] if log else None,
                                             "hypothesis": hypothesis_note(a["state"], a["state_reason"],
                                                                           log[0]["reason"] if log else None),
                                             "now": live_verdict(con, a, now)},
        "state_log": log, "parent": parent, "ancestors": ancestors(con, a), "link_note": link_note,
        "children": children_of(con, key), "usage": workload(con, a, now), "files": files,
        "started_kst": kst(a["started_at"]), "ended_kst": kst(a["ended_at"]), "last_kst": kst(a["last_event_at"]),
    }


def agent_tools(con, key: str, *, limit: int = 500, offset: int = 0) -> dict:
    total = con.execute("SELECT COUNT(*) FROM tool_call WHERE agent_key=?", (key,)).fetchone()[0]
    rows = _rows(con, "SELECT tool_use_id, at, tool, target, ok, result_at FROM tool_call WHERE agent_key=? "
                      "ORDER BY at LIMIT ? OFFSET ?", (key, max(1, min(limit, 5000)), max(0, offset)))
    for r in rows:
        a, b = dt(r["at"]), dt(r["result_at"])
        r["seconds"] = round((b - a).total_seconds(), 1) if a and b else None
        r["at_kst"] = kst(r["at"])
        r["result"] = "결과 없음" if r["ok"] is None else ("성공" if r["ok"] else "오류")
    return {"key": key[:120], "total": total, "offset": offset, "tools": rows}


# ── 원본 보기 (요청 시 읽기 · 저장 안 함) ─────────────────────────────
def source_path(con, key: str) -> Path | None:
    """agent 키 → 원천 .jsonl (src_file 에서). 원천 루트(claude_home) 아래만 허용."""
    if key.startswith("A:"):
        pat = f"%agent-{key[2:]}.jsonl"
    elif key.startswith("S:"):
        pat = f"%/{key[2:]}.jsonl"
    else:
        return None
    r = con.execute("SELECT path FROM src_file WHERE path LIKE ? ESCAPE '\\' ORDER BY length(path) LIMIT 1",
                    (pat,)).fetchone()
    if r is None:
        return None
    p = Path(r[0])
    home = settings.get().claude_home
    try:
        p.resolve().relative_to(home)
    except ValueError:
        return None
    return p


def _first_line(v, n: int = SHORT) -> str:
    s = str(v or "").strip().splitlines()
    return s[0][:n] if s else ""


def _tool_input_brief(inp) -> dict:
    if not isinstance(inp, dict):
        return {}
    out = {}
    for k in ("file_path", "notebook_path", "path", "url", "pattern"):
        if inp.get(k):
            out["path"] = str(inp[k])[:300]
            break
    for k in ("description", "command", "prompt", "query", "subagent_type", "to"):
        if inp.get(k):
            out["first"] = f"{k}: {_first_line(inp[k])}"
            break
    return out


def raw_messages(path: Path, *, offset: int = 0, limit: int = 200, text_cap: int = 20000) -> dict:
    """원천 .jsonl 을 읽기 전용으로 열어 user · assistant 메시지만 꺼낸다. 결과는 응답으로만 — 어디에도 저장하지 않는다."""
    msgs: list[dict] = []
    lines = 0
    with open(path, "rb") as f:                # 읽기 전용
        for raw in f:
            lines += 1
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("type") not in ("user", "assistant"):
                continue
            m = d.get("message") or {}
            content = m.get("content")
            blocks: list[dict] = []
            if isinstance(content, str):
                blocks.append({"t": "text", "text": content[:text_cap], "more": max(0, len(content) - text_cap)})
            elif isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text":
                        tx = str(b.get("text") or "")
                        blocks.append({"t": "text", "text": tx[:text_cap], "more": max(0, len(tx) - text_cap)})
                    elif bt == "thinking":
                        blocks.append({"t": "thinking", "size": len(str(b.get("thinking") or ""))})
                    elif bt == "tool_use":
                        blocks.append({"t": "tool_use", "name": str(b.get("name") or "?")[:60],
                                       **_tool_input_brief(b.get("input"))})
                    elif bt == "tool_result":
                        c = b.get("content")
                        size = len(c) if isinstance(c, str) else len(json.dumps(c, ensure_ascii=False)) if c else 0
                        blocks.append({"t": "tool_result", "size": size, "error": bool(b.get("is_error"))})
                    else:
                        blocks.append({"t": "other", "name": str(bt)[:30]})
            if not blocks:
                continue
            msgs.append({"n": lines, "role": d.get("type"), "at": kst(d.get("timestamp")),
                         "model": (m.get("model") or "")[:40], "blocks": blocks})
    total = len(msgs)
    if offset < 0:
        offset = max(0, total + offset)
    return {"lines": lines, "total": total, "offset": offset, "messages": msgs[offset:offset + max(1, min(limit, 1000))]}


# ── API ─────────────────────────────────────────────────────────────
@router.get("/api/v1/summary")
def summary():
    con = _con()
    try:
        now = datetime.now(timezone.utc)
        d = summary_data(con, now)
        d["my_turn"] = len(my_turn(con, now))
        return d
    finally:
        con.close()


@router.get("/api/v1/agents")
def agents(state: str | None = None, project: str | None = None, kind: str | None = None, since: str | None = None,
           limit: int = Query(500, ge=1, le=5000)):
    con = _con()
    try:
        rows = agent_list(con, state=state, project=project, kind=kind, since=since, limit=limit)
        return {"count": len(rows), "agents": rows,
                "filters": {"state": state, "project": project, "kind": kind, "since": since, "limit": limit}}
    finally:
        con.close()


@router.get("/api/v1/agents/{key}/tools")
def agent_tools_api(key: str, limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)):
    con = _con()
    try:
        return agent_tools(con, key, limit=limit, offset=offset)
    finally:
        con.close()


@router.get("/api/v1/agents/{key}")
def agent_detail_api(key: str):
    con = _con()
    try:
        return agent_detail(con, key)       # 없는 키도 200 + found=false · reason (G-17 빈 DB)
    finally:
        con.close()
