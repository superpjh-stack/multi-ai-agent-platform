"""D-05 타임라인 화면 + GET /api/v1/timeline — 담당 개발1 (spec.md §7 D-05).

가로축 시간, 세로축 에이전트(부모 아래 자식 들여쓰기). 막대 = started_at → ended_at(없으면 last_event_at, 살아 있으면 지금).
막대 색 = 그 시점 상태(state_log). state_log 첫 기록보다 앞 구간은 「판정 기록 없음」(NONE) 으로 칠한다 — 백필로 처음
판정된 과거 에이전트는 기록 시각이 막대 끝보다 뒤이므로 막대 전체가 NONE 이고 끝에 지금 상태 표시만 붙는다 (지어내지 않는다).
위쪽 면적 = 같은 시각에 열려 있던 막대 수.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Query, Request

from agentdash.app.routers import _svg
from agentdash.app.templating import render
from agentdash.db import conn

router = APIRouter()
OWNER = "개발1"
KST = timezone(timedelta(hours=9))
LIVE = ("RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "WAITING_CHILD", "SLEEPING")
MAX_LANES = 200
BUCKETS = 120


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=KST)


def _range(frm: str | None, to: str | None, now: datetime) -> tuple[datetime, datetime]:
    def one(s: str | None, end: bool) -> datetime | None:
        if not s:
            return None
        if len(s) == 10:      # YYYY-MM-DD (KST)
            d = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=KST)
            return d + timedelta(days=1) if end else d
        return _parse(s)
    b = one(to, True) or now
    a = one(frm, False) or (b - timedelta(hours=24))
    if a >= b:
        a = b - timedelta(hours=1)
    return a, b


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(con, frm: str | None = None, to: str | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    a, b = _range(frm, to, now)
    rows = con.execute("SELECT agent_key, kind, name, parent_key, depth, started_at, last_event_at, ended_at, state, "
                       "state_reason FROM agent WHERE started_at IS NOT NULL").fetchall()
    lanes: dict[str, dict] = {}
    for k, kind, name, parent, depth, st, last, end, state, reason in rows:
        s = _parse(st)
        e = _parse(end) or (now if state in LIVE else _parse(last)) or s
        if s is None or e is None:
            continue
        if state in LIVE:
            e = max(e, now)
        if s > b or e < a:
            continue
        lanes[k] = {"agent_key": k, "kind": kind, "name": name or k, "parent_key": parent, "depth": 0,
                    "start": _iso(s), "end": _iso(e), "state": state, "rule": reason, "_s": s, "_e": e, "segments": []}
    # 부모 아래 자식 (선택된 것 안에서만)
    children: dict[str | None, list[str]] = {}
    for k, ln in lanes.items():
        p = ln["parent_key"] if ln["parent_key"] in lanes else None
        children.setdefault(p, []).append(k)
    for v in children.values():
        v.sort(key=lambda k: (lanes[k]["_s"], k))
    order: list[str] = []

    def walk(k: str, d: int) -> None:
        lanes[k]["depth"] = d
        order.append(k)
        for c in children.get(k, []):
            if c not in order:
                walk(c, d + 1)

    for r in children.get(None, []):
        walk(r, 0)
    truncated = max(0, len(order) - MAX_LANES)
    order = order[:MAX_LANES]
    # state_log 구간
    keys = list(order)
    logs: dict[str, list[tuple[datetime, str, str]]] = {}
    for i in range(0, len(keys), 500):
        part = keys[i:i + 500]
        for k, at, st, reason in con.execute(
                f"SELECT agent_key, at, state, reason FROM state_log WHERE agent_key IN ({','.join('?' * len(part))}) "
                "ORDER BY at", part):
            d = _parse(at)
            if d:
                logs.setdefault(k, []).append((d, st, (reason or "")[:120]))
    for k in order:
        ln = lanes[k]
        s, e = ln["_s"], ln["_e"]
        cur, cur_state, cur_reason = s, "NONE", "판정 기록 없음 (state_log 이전)"
        segs = []
        for at, st, reason in logs.get(k, []):
            if at <= s:
                cur_state, cur_reason = st, reason
                continue
            if at >= e:
                break
            segs.append({"from": _iso(cur), "to": _iso(at), "state": cur_state, "reason": cur_reason})
            cur, cur_state, cur_reason = at, st, reason
        segs.append({"from": _iso(cur), "to": _iso(e), "state": cur_state, "reason": cur_reason})
        ln["segments"] = segs
    # 동시 실행 수
    step = (b - a) / BUCKETS
    conc = []
    for i in range(BUCKETS):
        x0, x1 = a + step * i, a + step * (i + 1)
        n = sum(1 for k in order if lanes[k]["_s"] < x1 and lanes[k]["_e"] > x0)
        conc.append({"at": _iso(x0), "n": n})
    out_lanes = [{kk: v for kk, v in lanes[k].items() if not kk.startswith("_")} for k in order]
    return {"from": _iso(a), "to": _iso(b), "lanes": out_lanes, "concurrency": conc, "truncated": truncated,
            "state_log_rows": sum(len(v) for v in logs.values())}


def _kst(ts: str) -> str:
    return _parse(ts).astimezone(KST).strftime("%m-%d %H:%M")


def gantt_svg(data: dict, width: int = 960, label_w: int = 220, row_h: int = 16) -> str:
    a, b = _parse(data["from"]), _parse(data["to"])
    span = (b - a).total_seconds() or 1
    w = width - label_w
    lanes = data["lanes"]
    height = max(1, len(lanes)) * row_h + 22
    out = [f'<svg class="chart gantt" viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="간트">']
    for i in range(5):    # 시각 눈금
        x = label_w + w * i / 4
        t = a + (b - a) * i / 4
        out.append(f'<line class="grid" x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height - 18}"/>')
        out.append(f'<text class="tick" x="{x:.1f}" y="{height - 4}" text-anchor="{"start" if i == 0 else "end" if i == 4 else "middle"}">'
                   f'{t.astimezone(KST).strftime("%m-%d %H:%M")}</text>')
    for i, ln in enumerate(lanes):
        y = i * row_h
        indent = min(ln["depth"], 6) * 10
        label = escape((ln["name"] or "")[:34])
        out.append(f'<a href="/agents/{escape(ln["agent_key"])}"><text class="lane" x="{4 + indent}" y="{y + row_h - 4}">{label}'
                   f'<title>{escape(ln["agent_key"])} · {escape(ln["kind"] or "")} · 지금 {escape(ln["state"] or "")} '
                   f'({escape(ln["rule"] or "")})</title></text></a>')
        for sg in ln["segments"]:
            s = max(_parse(sg["from"]), a)
            e = min(_parse(sg["to"]), b)
            if e <= s:
                e = s + timedelta(seconds=span / w)    # 최소 1 px
            x0 = label_w + (s - a).total_seconds() / span * w
            x1 = label_w + (e - a).total_seconds() / span * w
            out.append(f'<rect class="seg" x="{x0:.1f}" y="{y + 3}" width="{max(1.0, x1 - x0):.1f}" height="{row_h - 6}" rx="2" '
                       f'style="fill:var(--st-{escape(sg["state"])}, var(--st-UNKNOWN))"><title>{label} · {escape(sg["state"])} · '
                       f'{_kst(sg["from"])} → {_kst(sg["to"])} · {escape(sg["reason"] or "")}</title></rect>')
        # 지금 상태 표시 (막대 끝 4 px)
        e = min(_parse(ln["end"]), b)
        xe = label_w + (e - a).total_seconds() / span * w
        out.append(f'<rect x="{max(label_w, xe - 4):.1f}" y="{y + 2}" width="4" height="{row_h - 4}" '
                   f'style="fill:var(--st-{escape(ln["state"] or "UNKNOWN")}, var(--st-UNKNOWN))"><title>지금 {escape(ln["state"] or "")}</title></rect>')
    if not lanes:
        out.append(f'<text class="tick" x="{width / 2}" y="14" text-anchor="middle">기간 안 에이전트 없음</text>')
    out.append("</svg>")
    return "".join(out)


@router.get("/timeline")
def timeline_page(request: Request, frm: str | None = Query(None, alias="from"), to: str | None = None):
    con = conn.connect(conn.init_db())
    try:
        data = build(con, frm, to)
    finally:
        con.close()
    a, b = _parse(data["from"]).timestamp(), _parse(data["to"]).timestamp()
    pts = [(_parse(c["at"]).timestamp(), c["n"]) for c in data["concurrency"]]
    ctx = {"title": "타임라인", "active": "/timeline", "d": data,
           "svg_area": _svg.area(pts, a, b, left=220, label_fmt=lambda t: datetime.fromtimestamp(t, KST).strftime("%m-%d %H:%M")),
           "svg_gantt": gantt_svg(data), "from_v": frm or "", "to_v": to or "",
           "states": ["RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "SLEEPING", "WAITING_CHILD", "DONE", "FAILED",
                      "STALE", "UNKNOWN", "NONE"],
           "range_kst": f"{_kst(data['from'])} → {_kst(data['to'])}"}
    return render(request, "timeline.html", ctx)


@router.get("/api/v1/timeline")
def timeline_api(frm: str | None = Query(None, alias="from"), to: str | None = None):
    con = conn.connect(conn.init_db())
    try:
        return build(con, frm, to)
    finally:
        con.close()
