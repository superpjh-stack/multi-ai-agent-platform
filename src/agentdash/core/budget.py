"""예산 · 추세 · 캐시 적중률 (spec.md v0.3 §6.3 · §6). 담당 개발1. 시그니처는 progress-dev1.md §1 에 공표.

  · 금액은 config/budget.yaml 에서만 읽는다 (null = 「한도 미설정」 = unset). 코드에 금액 · 회사명을 쓰지 않는다.
  · 기준 금액 = 기간 안 usage_event.cost_est_usd 합 (추정 보정), 기록 기준 cost_usd 합을 함께. 단가 없음(NULL)은 0 으로 더하지 않고
    `unpriced` 건수로 센다.
  · 기간 (KST = UTC+9): 일 = 오늘 00:00 ~ 지금, 월 = 이번 달 1 일 00:00 ~ 지금. 추세 묶음: 일 · 주(월요일 00:00) · 월(1 일).
  · 프로젝트 = agent.project_path 의 마지막 이름 (없으면 project_key). 자손의 비용은 그 자손의 project_path 로 센다.
  · 단계: ok (< warn_ratio) · warn (≥ warn_ratio) · over (≥ 1.0) · unset (한도 null) · no_records (한도가 있는데 그 프로젝트 기록 0).
  · 캐시 적중률 = cache_read ÷ (input + cache_read + cache_write), 분모 0 → None. 낭비 = (1 − 적중률) × cost_est_usd 내림차순.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from agentdash import settings
from agentdash.core.usage import KST, kst_day

LEVELS = ("ok", "warn", "over", "unset", "no_records")
GRAINS = ("day", "week", "month")
TREND_GROUPS = ("total", "project")
EFF_GROUPS = ("project", "session", "agent")
PERIODS = (("day", "daily_usd"), ("month", "monthly_usd"))


# ── 설정 ─────────────────────────────────────────────────────────────
def load() -> dict:
    """config/budget.yaml — 키가 빠지면 SettingsError (조용한 기본값 금지). 금액은 null 또는 양수."""
    raw = settings.load_yaml("budget.yaml")
    for k in ("warn_ratio", "total", "projects"):
        if k not in raw:
            raise settings.SettingsError(f"config/budget.yaml 에 {k} 없음")
    wr = raw["warn_ratio"]
    if not isinstance(wr, (int, float)) or isinstance(wr, bool) or not 0 < wr <= 1:
        raise settings.SettingsError(f"config/budget.yaml warn_ratio 가 0~1 숫자가 아님: {wr!r}")
    total = raw["total"]
    projects = raw["projects"] if raw["projects"] is not None else {}
    if not isinstance(total, dict) or not isinstance(projects, dict):
        raise settings.SettingsError("config/budget.yaml total · projects 형식 오류")
    blocks = {"total": total, **{f"projects.{n}": v for n, v in projects.items()}}
    for where, b in blocks.items():
        if not isinstance(b, dict):
            raise settings.SettingsError(f"config/budget.yaml {where} 형식 오류")
        for _p, field in PERIODS:
            if field not in b:
                raise settings.SettingsError(f"config/budget.yaml {where}.{field} 없음")
            v = b[field]
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0):
                raise settings.SettingsError(f"config/budget.yaml {where}.{field} 는 null 또는 양수: {v!r}")
    return {"warn_ratio": float(wr), "total": total, "projects": projects}


def level(est: float, limit: float | None, warn_ratio: float) -> str:
    if limit is None:
        return "unset"
    r = est / limit
    return "over" if r >= 1.0 else ("warn" if r >= warn_ratio else "ok")


# ── 시각 ─────────────────────────────────────────────────────────────
def _dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def kst_bucket(ts_or_day: str, grain: str) -> str:
    """UTC 시각(…Z) 또는 KST 일자(YYYY-MM-DD) → 묶음 시작 일자 (일 · 그 주 월요일 · 그 달 1 일)."""
    if grain not in GRAINS:
        raise ValueError(f"grain 은 {GRAINS} 중 하나: {grain!r}")
    day = ts_or_day if len(ts_or_day) == 10 else kst_day(ts_or_day)
    d = datetime.strptime(day, "%Y-%m-%d")
    if grain == "week":
        d -= timedelta(days=d.weekday())
    elif grain == "month":
        d = d.replace(day=1)
    return d.strftime("%Y-%m-%d")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def period_start(now: datetime, period: str) -> str:
    """기간 시작(KST 오늘 00:00 · 이번 달 1 일 00:00)의 UTC `YYYY-MM-DDTHH:MM:SS` — usage_event.at(`…Z`) 과 문자열로
    「이상」 비교가 맞는다(같은 초면 더 긴 쪽이 크다). 끝(지금 이하)은 시각으로 비교한다 — 소수점 자리 수가 섞여도 맞게."""
    k = now.astimezone(KST)
    start = k.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        start = start.replace(day=1)
    return _utc(start)


def _day_bounds(frm: str, to: str) -> tuple[str, str]:
    a = datetime.strptime(frm, "%Y-%m-%d").replace(tzinfo=KST)
    b = datetime.strptime(to, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
    return _utc(a), _utc(b)


# ── 프로젝트 ─────────────────────────────────────────────────────────
def project_name(project_path: str | None, project_key: str | None) -> str:
    if project_path:
        name = project_path.rstrip("/").rsplit("/", 1)[-1]
        if name:
            return name
    return project_key or "(프로젝트 없음)"


def _agents(con: sqlite3.Connection) -> dict[str, dict]:
    return {r[0]: {"project": project_name(r[1], r[2]), "session_id": r[3], "name": r[4], "kind": r[5]}
            for r in con.execute("SELECT agent_key, project_path, project_key, session_id, name, kind FROM agent")}


# ── 예산 ─────────────────────────────────────────────────────────────
def status(con: sqlite3.Connection, now: datetime | None = None, cfg: dict | None = None) -> list[dict]:
    """예산 칸 목록 — 전체 오늘 · 이번 달, 그다음 budget.yaml projects 의 프로젝트마다 오늘 · 이번 달.
    칸 = {scope, project, period, limit, est_usd, rec_usd, ratio, level, unpriced}. cfg 는 테스트 · 검사 도구용(기본 load())."""
    cfg = cfg if cfg is not None else load()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    agents = _agents(con)
    known = {a["project"] for a in agents.values()}
    rows: list[dict] = []
    for period, field in PERIODS:
        a = period_start(now, period)
        tot = [0.0, 0.0, 0]
        per: dict[str, list] = defaultdict(lambda: [0.0, 0.0, 0])
        for k, at, c, ce in con.execute("SELECT agent_key, at, cost_usd, cost_est_usd FROM usage_event WHERE at >= ?", (a,)):
            if _dt(at) > now:
                continue
            proj = (agents.get(k) or {}).get("project")
            for t in (tot, per[proj]):
                if ce is None:
                    t[2] += 1                   # 단가 없음 — 0 으로 더하지 않는다
                else:
                    t[0] += ce
                if c is not None:
                    t[1] += c
        rows.append(_cell("total", None, period, cfg["total"].get(field), tot, cfg["warn_ratio"], True))
        for name, lim in cfg["projects"].items():
            rows.append(_cell("project", name, period, (lim or {}).get(field), per.get(name, [0.0, 0.0, 0]),
                              cfg["warn_ratio"], name in known))
    order = {"total": 0, "project": 1}
    rows.sort(key=lambda r: (order[r["scope"]], r["project"] or "", 0 if r["period"] == "day" else 1))
    return rows


def _cell(scope, project, period, limit, t, warn_ratio, known: bool) -> dict:
    est, rec, unpriced = t
    if limit is None:
        lv, ratio = "unset", None
    elif not known:
        lv, ratio = "no_records", None          # budget.yaml 의 이름이 기록에 없다(오타) — 조용히 0 % 로 두지 않는다
    else:
        lv, ratio = level(est, float(limit), warn_ratio), est / float(limit)
    return {"scope": scope, "project": project, "period": period, "limit": None if limit is None else float(limit),
            "est_usd": est, "rec_usd": rec, "ratio": ratio, "level": lv, "unpriced": unpriced}


def worst(rows: list[dict]) -> dict | None:
    """over > warn 중 비율이 가장 큰 칸 (D-01 띠). 없으면 None."""
    rank = {"over": 2, "warn": 1}
    cand = [r for r in rows if r.get("level") in rank]
    if not cand:
        return None
    return max(cand, key=lambda r: (rank[r["level"]], r.get("ratio") or 0.0))


# ── 추세 ─────────────────────────────────────────────────────────────
def trend(con: sqlite3.Connection, grain: str, frm: str, to: str, group: str) -> list[dict]:
    """usage_daily(KST 일자) → 묶음별 {bucket, project, cost_usd, cost_est_usd, output_tokens, output_est_total,
    input_tokens, cache_read, cache_write, hit}. 추정 출력 합 = 기록 출력 + 의심 행의 (output_est − output_tokens)
    (usage_daily 의 output_est 는 의심 행만의 합이라 기록 출력 몫은 usage_event 에서 뺀다)."""
    if grain not in GRAINS:
        raise ValueError(f"grain 은 {GRAINS} 중 하나: {grain!r}")
    if group not in TREND_GROUPS:
        raise ValueError(f"group 은 {TREND_GROUPS} 중 하나: {group!r}")
    if frm > to:
        frm, to = to, frm
    agents = _agents(con)
    out: dict[tuple[str, str | None], dict] = {}

    def row(day: str, key: str) -> dict:
        proj = (agents.get(key) or {}).get("project", "(프로젝트 없음)") if group == "project" else None
        b = kst_bucket(day, grain)
        return out.setdefault((b, proj), dict(bucket=b, project=proj, cost_usd=None, cost_est_usd=None, output_tokens=0,
                                              output_est_total=0, input_tokens=0, cache_read=0, cache_write=0))

    for day, k, i, cr, cw, o, c, ce in con.execute(
            "SELECT day, agent_key, input_tokens, cache_read, cache_write, output_tokens, cost_usd, cost_est_usd "
            "FROM usage_daily WHERE day BETWEEN ? AND ?", (frm, to)):
        r = row(day, k)
        r["input_tokens"] += i or 0
        r["cache_read"] += cr or 0
        r["cache_write"] += cw or 0
        r["output_tokens"] += o or 0
        r["output_est_total"] += o or 0
        if c is not None:
            r["cost_usd"] = (r["cost_usd"] or 0.0) + c
        if ce is not None:
            r["cost_est_usd"] = (r["cost_est_usd"] or 0.0) + ce
    a, b = _day_bounds(frm, to)
    for k, at, o, oe in con.execute("SELECT agent_key, at, output_tokens, output_est FROM usage_event "
                                    "WHERE output_est IS NOT NULL AND at >= ? AND at < ?", (a, b)):
        row(kst_day(at), k)["output_est_total"] += oe - (o or 0)
    rows = sorted(out.values(), key=lambda r: (r["bucket"], r["project"] or ""))
    for r in rows:
        den = r["input_tokens"] + r["cache_read"] + r["cache_write"]
        r["hit"] = r["cache_read"] / den if den else None
    return rows


# ── 캐시 적중률 ──────────────────────────────────────────────────────
def efficiency(con: sqlite3.Connection, group: str, frm: str, to: str) -> list[dict]:
    """usage_event(KST 기간) → 묶음별 {key, label, input_tokens, cache_read, cache_write, hit, cost_est_usd, waste,
    unpriced, requests}. session = 그 세션 폴더의 모든 에이전트(자기 + 자손 — usage.descendants 의 세션 규칙),
    agent = 자기만. waste = (1 − hit) × cost_est_usd (hit None → 0) 내림차순."""
    if group not in EFF_GROUPS:
        raise ValueError(f"group 은 {EFF_GROUPS} 중 하나: {group!r}")
    if frm > to:
        frm, to = to, frm
    agents = _agents(con)
    a, b = _day_bounds(frm, to)
    acc: dict[str, dict] = {}
    for k, i, cr, w5, w1, ce in con.execute(
            "SELECT agent_key, input_tokens, cache_read, cache_write_5m, cache_write_1h, cost_est_usd FROM usage_event "
            "WHERE at >= ? AND at < ?", (a, b)):
        ag = agents.get(k) or {"project": "(프로젝트 없음)", "session_id": None, "name": None}
        if group == "project":
            key, label = ag["project"], ag["project"]
        elif group == "session":
            key = f"S:{ag['session_id']}" if ag.get("session_id") else k
            label = (agents.get(key) or {}).get("name") or key
        else:
            key, label = k, ag.get("name") or k
        r = acc.setdefault(key, dict(key=key, label=label, input_tokens=0, cache_read=0, cache_write=0,
                                     cost_est_usd=None, unpriced=0, requests=0))
        r["input_tokens"] += i or 0
        r["cache_read"] += cr or 0
        r["cache_write"] += (w5 or 0) + (w1 or 0)
        r["requests"] += 1
        if ce is None:
            r["unpriced"] += 1
        else:
            r["cost_est_usd"] = (r["cost_est_usd"] or 0.0) + ce
    rows = list(acc.values())
    for r in rows:
        den = r["input_tokens"] + r["cache_read"] + r["cache_write"]
        r["hit"] = r["cache_read"] / den if den else None
        r["waste"] = (1 - r["hit"]) * (r["cost_est_usd"] or 0.0) if r["hit"] is not None else 0.0
    rows.sort(key=lambda r: (-r["waste"], r["key"]))
    return rows
