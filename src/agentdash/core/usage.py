"""작업량 · 비용 (spec.md §6 · §6.1). 담당 개발1.

  · requestId 같은 줄은 한 번 (D-01) — model.add_usage 가 (agent_key, requestId) 로 한 행, 스트리밍 최종본(output 최대)을 남긴다.
  · `<synthetic>` (pricing.yaml exclude_models) 는 usage_event 에 넣지 않는다 → 토큰 · 비용에서 빠진다.
  · 비용 공식 (spec §6.1 그대로):
      cost = (input×in + cache_read×cr + cache_write_5m×in×1.25 + cache_write_1h×in×2.0 + output×out) / 1e6 × (fast ? fast_mult : 1)
    TTL 분리 값이 없으면 전부 5m (파서가 cache_write_5m 에 넣는다). thinking_tokens 는 output 안 (D-03) — 따로 더하지 않는다.
    Haiku 5.5 는 프롬프트(입력 + 캐시 읽기 + 캐시 쓰기) 크기 구간. 모르는 모델 · fast 단가 없는 모델 → NULL (지어내지 않는다).
  · 일자는 KST. active_seconds = 연속 기록 간격 ≤ 5 분 구간의 합 (D-06).
  · 세션 합계 = 자기 + 자손. 자손은 spawn/workflow 엣지 → parent_key → 메타 단서(parentAgentId · 워크플로 폴더 · 같은 세션 폴더) 순.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agentdash import settings
from agentdash.core import model as M

KST = timezone(timedelta(hours=9))
ACTIVE_GAP_SEC = 300
#: D-17 확정 (spec v0.3 §6.2 — 대안 ②): 기록값은 그대로, 의심 요청에 output_est · cost_est_usd. 표기 「추정 보정 (D-17)」.
UNDERCOUNT_NOTE = "추정 보정 (D-17)"


@dataclass
class Pricing:
    version: str
    models: dict
    aliases: dict
    exclude: set
    cache_mult: dict

    def resolve(self, model: str | None) -> str | None:
        if model is None:
            return None
        if model in self.models:
            return model
        alias = self.aliases.get(model)
        return alias if alias in self.models else None


def load_pricing() -> Pricing:
    raw = settings.load_yaml("pricing.yaml")
    for k in ("version", "models", "cache_write_mult"):
        if k not in raw:
            raise settings.SettingsError(f"config/pricing.yaml 에 {k} 없음")
    return Pricing(version=str(raw["version"]), models=raw["models"] or {}, aliases=raw.get("aliases") or {},
                   exclude=set(raw.get("exclude_models") or []), cache_mult=raw["cache_write_mult"])


def _rates(entry: dict, prompt: int) -> dict | None:
    if "tiers" in entry:
        for t in entry["tiers"]:
            if t.get("max_prompt") is None or prompt <= t["max_prompt"]:
                return t
        return None
    return entry


def cost(ev: M.UsageEvent, pricing: Pricing) -> tuple[float | None, str]:
    key = pricing.resolve(ev.model)
    if key is None:
        return None, pricing.version
    entry = pricing.models[key]
    w5, w1 = ev.cache_write_5m or 0, ev.cache_write_1h or 0
    prompt = (ev.input_tokens or 0) + (ev.cache_read or 0) + w5 + w1
    r = _rates(entry, prompt)
    if r is None:
        return None, pricing.version
    mult = 1.0
    if ev.speed == "fast":
        if "fast_mult" not in entry:
            return None, pricing.version          # 빠른 모드 단가 없음 — 지어내지 않는다
        mult = float(entry["fast_mult"])
    c = ((ev.input_tokens or 0) * r["in"]
         + (ev.cache_read or 0) * r["cache_read"]
         + w5 * r["in"] * float(pricing.cache_mult["5m"])
         + w1 * r["in"] * float(pricing.cache_mult["1h"])
         + (ev.output_tokens or 0) * r["out"]) / 1e6 * mult
    return c, pricing.version


# ── D-17 추정 출력 (spec §6.2, v0.3) ──────────────────────────────────
SUSPECT_MAX_OUTPUT = 30      # 요청의 기록 output 최대가 이보다 작고
SUSPECT_MIN_JSON = 400       # content 블록 json.dumps 길이 합이 이보다 크면 의심


def estimate(max_output: int, json_len: int, est_chars: int) -> int | None:
    """의심 요청이면 하한 추정 출력 = max(ceil(est_chars / 4), 기록 output 최대), 아니면 None.
    길이 숫자는 이 계산에만 쓰고 저장하지 않는다 (spec §2.3)."""
    if not (max_output < SUSPECT_MAX_OUTPUT and json_len > SUSPECT_MIN_JSON):
        return None
    return max(-(-est_chars // 4), max_output)


def cost_est(ev: M.UsageEvent, pricing: Pricing) -> float | None:
    """§6.1 공식에서 output_tokens 자리에 output_est 를 넣은 비용. output_est 가 없으면 ev.cost_usd (단가 없으면 None)."""
    if ev.output_est is None:
        return ev.cost_usd
    from dataclasses import replace

    c, _ = cost(replace(ev, output_tokens=ev.output_est), pricing)
    return c


def refresh_est(con: sqlite3.Connection, agent_key: str, request_id: str, pricing: Pricing) -> None:
    """저장된 행 기준으로 추정 두 칸을 다시 맞춘다 — 포크 사본 반영(output 이 커짐) · reprice 뒤.
    output_est 가 있으면 하한 = 기록 output, 없으면 cost_est_usd = cost_usd."""
    r = con.execute("SELECT at, model, speed, input_tokens, cache_read, cache_write_5m, cache_write_1h, output_tokens, "
                    "cost_usd, output_est FROM usage_event WHERE agent_key=? AND request_id=?",
                    (agent_key, request_id)).fetchone()
    if r is None:
        return
    est = None if r[9] is None else max(r[9], r[7] or 0)
    ev = M.UsageEvent(agent_key=agent_key, request_id=request_id, at=r[0], model=r[1], speed=r[2], input_tokens=r[3],
                      cache_read=r[4], cache_write_5m=r[5], cache_write_1h=r[6], output_tokens=r[7], cost_usd=r[8],
                      output_est=est)
    con.execute("UPDATE usage_event SET output_est=?, cost_est_usd=? WHERE agent_key=? AND request_id=?",
                (est, cost_est(ev, pricing), agent_key, request_id))


# ── 합계 ─────────────────────────────────────────────────────────────
_SUM = ("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(cache_read),0), "
        "COALESCE(SUM(cache_write_5m),0)+COALESCE(SUM(cache_write_1h),0), COALESCE(SUM(output_tokens),0), "
        "COALESCE(SUM(thinking_tokens),0), SUM(cost_usd), COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END),0), COUNT(*), "
        "COALESCE(SUM(COALESCE(output_est, output_tokens)),0), SUM(cost_est_usd) "
        "FROM usage_event WHERE agent_key IN ({})")


def _sum(con: sqlite3.Connection, keys: list[str]) -> dict:
    out = dict(input_tokens=0, cache_read=0, cache_write=0, output_tokens=0, thinking_tokens=0, cost_usd=None,
               unpriced=0, requests=0, output_est_total=0, cost_est_usd=None)
    for i in range(0, len(keys), 500):
        part = keys[i:i + 500]
        r = con.execute(_SUM.format(",".join("?" * len(part))), part).fetchone()
        for j, k in enumerate(("input_tokens", "cache_read", "cache_write", "output_tokens", "thinking_tokens")):
            out[k] += r[j]
        if r[5] is not None:
            out["cost_usd"] = (out["cost_usd"] or 0.0) + r[5]
        out["unpriced"] += r[6]
        out["requests"] += r[7]
        out["output_est_total"] += r[8]
        if r[9] is not None:
            out["cost_est_usd"] = (out["cost_est_usd"] or 0.0) + r[9]
    return out


def _meta_parent(a: M.Agent, extra: M.AgentExtra | None) -> str | None:
    """parent_key 가 아직 없을 때 메타의 직접 단서 (연결 판단이 아니라 합계용 대체 — linker 가 채우면 그것을 쓴다)."""
    if a.kind == "WORKFLOW":
        return M.key_session(a.session_id)
    if extra is None:
        return M.key_session(a.session_id) if a.depth == 1 else None
    if extra.wf_id and a.kind == "WORKFLOW_AGENT":
        return M.key_workflow(extra.wf_id)
    if extra.parent_agent_id:
        return M.key_agent(extra.parent_agent_id)
    if (extra.spawn_depth or a.depth) == 1:
        return M.key_session(a.session_id)
    return None


def children_map(con: sqlite3.Connection, session_id: str | None = None) -> dict[str, set[str]]:
    kids: dict[str, set[str]] = defaultdict(set)
    for src, dst in con.execute("SELECT src_key, dst_key FROM edge WHERE kind IN ('spawn','workflow')"):
        kids[src].add(dst)
    for a in M.list_agents(con, session_id=session_id):
        if a.kind == "SESSION":
            continue
        if a.parent_key:
            kids[a.parent_key].add(a.agent_key)
        else:
            p = _meta_parent(a, M.load_extra(con, a.agent_key))
            if p:
                kids[p].add(a.agent_key)
    return kids


def descendants(con: sqlite3.Connection, agent_key: str) -> list[str]:
    root = M.get_agent(con, agent_key)
    if root is None:
        return []
    kids = children_map(con, root.session_id)
    seen: set[str] = set()
    stack = [agent_key]
    while stack:
        x = stack.pop()
        for c in kids.get(x, ()):
            if c not in seen and c != agent_key:
                seen.add(c)
                stack.append(c)
    if root.kind == "SESSION":   # 세션 폴더 안의 에이전트는 전부 그 세션의 자손 (부모 미확인 포함)
        seen |= {a.agent_key for a in M.list_agents(con, session_id=root.session_id) if a.agent_key != agent_key}
    return sorted(seen)


_descendants = descendants


def totals(con: sqlite3.Connection, agent_key: str, *, descendants: bool = False) -> dict:
    """합계. D-17 (spec §6.2): output_est_total = 의심 행은 output_est · 나머지는 output_tokens 의 합, cost_est_usd = 추정 보정 비용
    (단가 없는 행은 더하지 않는다 — unpriced). est_note = 「추정 보정 (D-17)」 — D-03 · D-04 가 기록 칸 옆에 나란히 쓴다."""
    keys = [agent_key]
    if descendants:
        keys += _descendants(con, agent_key)
    out = _sum(con, keys)
    out["est_note"] = UNDERCOUNT_NOTE
    return out


# ── 스파크 (spec v0.4 §5.4 — 2차-T 디지털 트윈) ──────────────────────────
SPARK_MINUTES = 30
_SPARK = ("SELECT agent_key, substr(at,1,16) AS m, COALESCE(SUM(COALESCE(output_est, output_tokens)),0) FROM usage_event "
          "WHERE agent_key IN ({}) AND at >= ? AND at < ? AND COALESCE(model,'') != '<synthetic>' GROUP BY agent_key, m")


def spark(con: sqlite3.Connection, keys: list[str], now: datetime, minutes: int = SPARK_MINUTES) -> dict[str, list[int]]:
    """키마다 길이 minutes 리스트. 칸 i = [now_floor − (minutes−1−i) 분, +1 분) 의 COALESCE(output_est, output_tokens) 합
    (가장 오래된 칸 → 지금 분이 마지막). `<synthetic>` 제외. 기록 없는 키도 0 리스트.
    분은 UTC 기준 — usage_event.at 은 UTC ISO `YYYY-MM-DDTHH:MM:SS.sssZ` 문자열이라 문자열 비교 · 앞 16 자로 분을 자른다.
    now 는 시간대가 있어야 한다(없으면 ValueError — 조용한 기본값 금지)."""
    if now.tzinfo is None:
        raise ValueError("usage.spark: now 에 시간대가 없다")
    if minutes < 1:
        raise ValueError("usage.spark: minutes ≥ 1")
    end = now.astimezone(timezone.utc).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)
    idx = {(start + timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M"): i for i in range(minutes)}
    lo, hi = start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")
    out = {k: [0] * minutes for k in keys}
    uniq = list(out)
    for i in range(0, len(uniq), 500):
        part = uniq[i:i + 500]
        for key, m, v in con.execute(_SPARK.format(",".join("?" * len(part))), [*part, lo, hi]):
            out[key][idx[m]] += int(v)
    return out


# ── 일별 집계 ─────────────────────────────────────────────────────────
def kst_day(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST).strftime("%Y-%m-%d")


def active_seconds(timestamps: list[str], gap_sec: int = ACTIVE_GAP_SEC) -> int:
    return sum(active_by_day(timestamps, gap_sec).values())


def active_by_day(timestamps: list[str], gap_sec: int = ACTIVE_GAP_SEC) -> dict[str, int]:
    """연속 기록 간격 ≤ gap_sec 인 구간의 합을 뒤 기록의 KST 일자에 붙인다 (D-06)."""
    ts = sorted(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in timestamps if t)
    out: dict[str, int] = defaultdict(int)
    for a, b in zip(ts, ts[1:]):
        g = (b - a).total_seconds()
        if 0 < g <= gap_sec:
            out[b.astimezone(KST).strftime("%Y-%m-%d")] += int(round(g))
    return dict(out)


def rebuild_daily(con: sqlite3.Connection, agent_keys: list[str] | set[str] | None = None) -> int:
    if agent_keys is None:
        keys = [r[0] for r in con.execute("SELECT agent_key FROM agent")]
        con.execute("DELETE FROM usage_daily")
    else:
        keys = sorted(agent_keys)
        for k in keys:
            con.execute("DELETE FROM usage_daily WHERE agent_key=?", (k,))
    n = 0
    for k in keys:
        rows: dict[tuple[str, str], list] = {}
        for at, mdl, i, cr, w5, w1, o, c, oe, ce in con.execute(
                "SELECT at, model, input_tokens, cache_read, cache_write_5m, cache_write_1h, output_tokens, cost_usd, "
                "output_est, cost_est_usd FROM usage_event WHERE agent_key=?", (k,)):
            if not at:
                continue
            key = (kst_day(at), mdl or "")
            r = rows.setdefault(key, [0, 0, 0, 0, 0, 0, 0, None, 0, None])
            r[0] += i or 0
            r[1] += cr or 0
            r[2] += (w5 or 0) + (w1 or 0)
            r[3] += o or 0
            if c is not None:
                r[7] = (r[7] or 0.0) + c
            r[8] += oe or 0                         # 그날 의심 요청의 output_est 합 (없으면 0, spec §3)
            if ce is not None:
                r[9] = (r[9] or 0.0) + ce
        tools_by_day: dict[str, int] = defaultdict(int)
        stamps: list[str] = [r[0] for r in con.execute("SELECT at FROM usage_event WHERE agent_key=?", (k,)) if r[0]]
        for at, res in con.execute("SELECT at, result_at FROM tool_call WHERE agent_key=?", (k,)):
            if at:
                tools_by_day[kst_day(at)] += 1
                stamps.append(at)
            if res:
                stamps.append(res)
        files_by_day: dict[str, set] = defaultdict(set)
        for path, at in con.execute("SELECT path, at FROM file_touch WHERE agent_key=?", (k,)):
            if at:
                files_by_day[kst_day(at)].add(path)
        act = active_by_day(stamps)
        days = set(d for d, _ in rows) | set(tools_by_day) | set(files_by_day) | set(act)
        for day in days:
            models = [(m, r) for (d, m), r in rows.items() if d == day]
            if not models:   # 토큰 없는 날: 도구 · 파일 · 시간만 (모델 칸 '')
                models = [("", rows.setdefault((day, ""), [0, 0, 0, 0, 0, 0, 0, None, 0, None]))]
            # 도구 · 파일 · 시간은 모델 칸이 없으므로 그날 출력이 가장 많은 모델 행에 붙인다
            top = max(models, key=lambda x: x[1][3])[0]
            for m, r in models:
                if m == top:
                    r[4], r[5], r[6] = tools_by_day.get(day, 0), len(files_by_day.get(day, ())), act.get(day, 0)
                con.execute(
                    "INSERT INTO usage_daily (day, agent_key, model, input_tokens, cache_read, cache_write, output_tokens, "
                    "tool_calls, files_written, active_seconds, cost_usd, output_est, cost_est_usd) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (day, k, m, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]))
                n += 1
    return n


def reprice(con: sqlite3.Connection, pricing: Pricing | None = None) -> dict:
    pricing = pricing or load_pricing()
    cur = con.execute("SELECT agent_key, request_id, at, model, speed, input_tokens, cache_read, cache_write_5m, "
                      "cache_write_1h, output_tokens, output_est FROM usage_event")
    upd, changed, nulls = [], 0, 0
    for r in cur.fetchall():
        ev = M.UsageEvent(agent_key=r[0], request_id=r[1], at=r[2], model=r[3], speed=r[4], input_tokens=r[5],
                          cache_read=r[6], cache_write_5m=r[7], cache_write_1h=r[8], output_tokens=r[9], output_est=r[10])
        c, ver = cost(ev, pricing)
        ev.cost_usd = c
        nulls += c is None
        upd.append((c, ver, cost_est(ev, pricing), r[0], r[1]))     # 추정 보정 비용도 같은 단가로 (spec §6.2)
    est_changed = 0
    for c, ver, ce, k, rid in upd:
        cc = con.execute("UPDATE usage_event SET cost_usd=?, pricing_ver=? WHERE agent_key=? AND request_id=? "
                         "AND (cost_usd IS NOT ? OR pricing_ver IS NOT ?)", (c, ver, k, rid, c, ver))
        changed += cc.rowcount
        est_changed += con.execute("UPDATE usage_event SET cost_est_usd=? WHERE agent_key=? AND request_id=? "
                                   "AND cost_est_usd IS NOT ?", (ce, k, rid, ce)).rowcount
    daily = rebuild_daily(con)
    return {"rows": len(upd), "changed": changed, "est_changed": est_changed, "null_cost": nulls,
            "pricing_ver": pricing.version, "daily_rows": daily}


def unpriced_models(con: sqlite3.Connection, pricing: Pricing | None = None) -> list[tuple[str, int]]:
    pricing = pricing or load_pricing()
    out = []
    for mdl, n in con.execute("SELECT model, COUNT(*) FROM usage_event GROUP BY model ORDER BY 2 DESC"):
        if pricing.resolve(mdl) is None:
            out.append((mdl, n))
    return out


# ── D-04 작업량 표 (spec §6 · §7 D-04) ─────────────────────────────────
GROUPS = ("agent", "project", "type", "model", "day")
ESTIMATE_LABEL = "[추정] API 정가 환산"


def kst_today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def default_range(days: int = 30) -> tuple[str, str]:
    to = datetime.now(KST)
    return (to - timedelta(days=days - 1)).strftime("%Y-%m-%d"), to.strftime("%Y-%m-%d")


def _utc_bounds(frm: str, to: str) -> tuple[str, str]:
    a = datetime.strptime(frm, "%Y-%m-%d").replace(tzinfo=KST).astimezone(timezone.utc)
    b = (datetime.strptime(to, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)).astimezone(timezone.utc)
    return a.strftime("%Y-%m-%dT%H:%M:%S"), b.strftime("%Y-%m-%dT%H:%M:%S")


def _group_key(group: str, day: str, model: str | None, a: dict) -> tuple[str, str]:
    """(키, 표시 이름)."""
    if group == "agent":
        return a["agent_key"], a.get("name") or a["agent_key"]
    if group == "project":
        pk = a.get("project_key") or "(프로젝트 없음)"
        pp = a.get("project_path")
        return pk, (pp.rstrip("/").rsplit("/", 1)[-1] if pp else pk)
    if group == "type":
        t = a.get("agent_type") or a.get("kind") or "(유형 없음)"
        return t, t
    if group == "model":
        return model or "", model or "(모델 없음 — 도구 · 시간만)"
    return day, day


def _unique_files(con: sqlite3.Connection, group: str, agents: dict, rows: dict, tot: dict, ua: str, ub: str,
                  top_model: dict) -> None:
    """「작성 파일」 = 기간 안 고유 (agent, path) 수 (DEF-QA1-006 — spec §6 「서로 다른 file_path 수」). 일별 합을 더하지 않는다.

    묶음이 일자면 그날 고유 수. 그 밖 묶음은 (agent, path) 하나를 기간 안 첫 기록 일자의 묶음 하나에만 센다
    (모델 묶음은 그날 그 에이전트의 파일이 붙은 모델 행 — rebuild_daily 와 같은 자리).
    """
    first: dict[tuple[str, str], str] = {}
    per_day: dict[str, set] = defaultdict(set)
    for k, path, at in con.execute("SELECT agent_key, path, at FROM file_touch WHERE at >= ? AND at < ?", (ua, ub)):
        day = kst_day(at)
        per_day[day].add((k, path))
        if (k, path) not in first or day < first[(k, path)]:
            first[(k, path)] = day
    for r in rows.values():
        r["files_written"] = 0
    tot["files_written"] = len(first)
    if group == "day":
        for day, s in per_day.items():
            if day in rows:
                rows[day]["files_written"] = len(s)
        return
    for (k, _path), day in first.items():
        a = agents.get(k) or {"agent_key": k}
        gk, _ = _group_key(group, day, top_model.get((day, k), ""), a)
        if gk in rows:
            rows[gk]["files_written"] += 1


def table(con: sqlite3.Connection, frm: str | None = None, to: str | None = None, group: str | None = None) -> dict:
    """usage_daily(KST 일자) 를 묶음 기준으로 합친 순위 표 + 일별 추이 + 단가 없음 건수.

    비용은 usage_event.cost_usd 합(같은 값을 usage_daily 가 들고 있다) — 단가 없는 모델은 NULL 로 두고 건수만 센다.
    """
    group = group if group in GROUPS else "agent"
    d0, d1 = default_range()
    frm, to = (frm or d0)[:10], (to or d1)[:10]
    if frm > to:
        frm, to = to, frm
    agents = {r[0]: {"agent_key": r[0], "name": r[1], "kind": r[2], "agent_type": r[3], "project_key": r[4],
                     "project_path": r[5]}
              for r in con.execute("SELECT agent_key, name, kind, agent_type, project_key, project_path FROM agent")}
    rows: dict[str, dict] = {}
    days: dict[str, dict] = {}
    tot = dict(input_tokens=0, cache_read=0, cache_write=0, output_tokens=0, tool_calls=0, files_written=0,
               active_seconds=0, cost_usd=None, unpriced=0, requests=0, output_est_total=0, cost_est_usd=None)
    top_model: dict[tuple[str, str], str] = {}      # (일자, agent) → 그날 파일 · 도구가 붙은 모델 행 (rebuild_daily)
    for day, k, mdl, i, cr, cw, o, tc, fw, act, c, ce in con.execute(
            "SELECT day, agent_key, model, input_tokens, cache_read, cache_write, output_tokens, tool_calls, "
            "files_written, active_seconds, cost_usd, cost_est_usd FROM usage_daily WHERE day BETWEEN ? AND ?", (frm, to)):
        a = agents.get(k) or {"agent_key": k}
        if fw:
            top_model[(day, k)] = mdl or ""
        gk, label = _group_key(group, day, mdl, a)
        r = rows.setdefault(gk, dict(key=gk, label=label, input_tokens=0, cache_read=0, cache_write=0, output_tokens=0,
                                     tool_calls=0, files_written=0, active_seconds=0, cost_usd=None, unpriced=0,
                                     requests=0, kind=a.get("kind") if group == "agent" else None,
                                     output_est_total=0, cost_est_usd=None))
        dd = days.setdefault(day, dict(day=day, output_tokens=0, cost_usd=None, input_tokens=0, cache_read=0,
                                       cache_write=0, output_est_total=0, cost_est_usd=None))
        for tgt in (r, tot):
            tgt["input_tokens"] += i or 0
            tgt["cache_read"] += cr or 0
            tgt["cache_write"] += cw or 0
            tgt["output_tokens"] += o or 0
            tgt["tool_calls"] += tc or 0
            tgt["files_written"] += fw or 0
            tgt["active_seconds"] += act or 0
            if c is not None:
                tgt["cost_usd"] = (tgt["cost_usd"] or 0.0) + c
        for tgt in (r, tot, dd):
            if ce is not None:
                tgt["cost_est_usd"] = (tgt["cost_est_usd"] or 0.0) + ce
        dd["output_tokens"] += o or 0
        dd["input_tokens"] += i or 0
        dd["cache_read"] += cr or 0
        dd["cache_write"] += cw or 0
        if c is not None:
            dd["cost_usd"] = (dd["cost_usd"] or 0.0) + c
    # 요청 수 · 단가 없음 건수 — usage_event 에서 (KST 일자 경계)
    ua, ub = _utc_bounds(frm, to)
    _unique_files(con, group, agents, rows, tot, ua, ub, top_model)
    unpriced_models: dict[str, int] = {}
    for k, at, mdl, c, o, oe in con.execute("SELECT agent_key, at, model, cost_usd, output_tokens, output_est "
                                            "FROM usage_event WHERE at >= ? AND at < ?", (ua, ub)):
        if not at:
            continue
        a = agents.get(k) or {"agent_key": k}
        day = kst_day(at)
        gk, label = _group_key(group, day, mdl, a)
        r = rows.get(gk)
        est = oe if oe is not None else (o or 0)       # 추정 출력 = 의심 행은 output_est, 나머지는 기록 (spec §6)
        tot["requests"] += 1
        tot["output_est_total"] += est
        if day in days:
            days[day]["output_est_total"] += est
        if r is not None:
            r["requests"] += 1
            r["output_est_total"] += est
        if c is None:
            tot["unpriced"] += 1
            unpriced_models[mdl or ""] = unpriced_models.get(mdl or "", 0) + 1
            if r is not None:
                r["unpriced"] += 1
    for r in [*rows.values(), tot, *days.values()]:
        den = r["input_tokens"] + r["cache_read"] + r["cache_write"]
        r["cache_hit"] = (r["cache_read"] / den) if den else None
    ranked = sorted(rows.values(), key=lambda r: (-(r["output_tokens"]), r["key"])) if group != "day" \
        else sorted(rows.values(), key=lambda r: r["key"], reverse=True)
    trend = [days[d] for d in sorted(days)]
    ver = con.execute("SELECT pricing_ver, COUNT(*) FROM usage_event GROUP BY pricing_ver ORDER BY 2 DESC").fetchall()
    return {"from": frm, "to": to, "group": group, "groups": list(GROUPS), "rows": ranked, "total": tot,
            "trend": trend, "unpriced": tot["unpriced"], "unpriced_models": sorted(unpriced_models.items()),
            "pricing_ver": ver[0][0] if ver else None, "pricing_versions": [v[0] for v in ver],
            "estimate_label": ESTIMATE_LABEL, "est_note": UNDERCOUNT_NOTE}


CSV_COLS = ("key", "label", "requests", "input_tokens", "cache_read", "cache_write", "output_tokens", "output_est_total",
            "cache_hit", "tool_calls", "files_written", "active_seconds", "cost_usd", "cost_est_usd", "unpriced")


def to_csv(t: dict) -> str:
    """순위 표 CSV — 비용 열 이름에 [추정] 표기를 붙인다 (spec §6.1 운용 규칙)."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    head = list(CSV_COLS)
    head[head.index("cost_usd")] = f"cost_usd {ESTIMATE_LABEL} (단가표 {t.get('pricing_ver')})"
    head[head.index("output_est_total")] = f"output_est_total {UNDERCOUNT_NOTE} [추정]"
    head[head.index("cost_est_usd")] = f"cost_est_usd {UNDERCOUNT_NOTE} {ESTIMATE_LABEL}"
    w.writerow(head)

    def cell(r: dict, c: str):
        v = r.get(c)
        return "" if v is None else (round(v, 6) if isinstance(v, float) else v)

    for r in t["rows"]:
        w.writerow([cell(r, c) for c in CSV_COLS])
    tt = t["total"]
    w.writerow(["합계", f"{t['from']}~{t['to']} · group={t['group']} · 단가 없음 {t['unpriced']} 건"]
               + [cell(tt, c) for c in CSV_COLS[2:]])
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    """`make pricing-check` · `make reprice` — DB 는 AGENTDASH_DB (원천은 건드리지 않는다)."""
    import argparse

    from agentdash.db import conn

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pricing-check", "reprice", "export"])
    ap.add_argument("--db", default=None)
    ap.add_argument("--from", dest="frm", default=None)
    ap.add_argument("--to", default=None)
    ap.add_argument("--group", default="agent")
    ap.add_argument("--out", default=None, help="CSV 경로 (기본 outputs/usage_<from>_<to>_<group>.csv)")
    a = ap.parse_args(argv)
    db = a.db or settings.get().db_path
    con = conn.connect(conn.init_db(db))
    try:
        pricing = load_pricing()
        if a.cmd == "pricing-check":
            rows = unpriced_models(con, pricing)
            total = con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0]
            models = con.execute("SELECT COUNT(DISTINCT model) FROM usage_event").fetchone()[0]
            print(f"pricing-check — 단가표 {pricing.version} · 기록 모델 {models} · usage_event {total} · 제외 {sorted(pricing.exclude)}")
            if not rows:
                print("  단가 없는 모델 0 종 (비용 NULL 0 건)")
            for mdl, n in rows:
                print(f"  단가 없음: {mdl}  {n} 건 → 비용 NULL (config/pricing.yaml 에 추가 후 make reprice)")
            return 0
        if a.cmd == "export":
            t = table(con, a.frm, a.to, a.group)
            out = settings.ROOT / (a.out or f"outputs/usage_{t['from']}_{t['to']}_{t['group']}.csv")
            if settings.get().is_source_path(out) or settings.ROOT not in out.resolve().parents:
                raise SystemExit(f"내보내기 경로가 저장소 밖: {out}")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(to_csv(t), encoding="utf-8-sig")
            print(f"export — {out.relative_to(settings.ROOT)} · 행 {len(t['rows'])} · {t['from']}~{t['to']} · "
                  f"group={t['group']} · 비용 {ESTIMATE_LABEL} ${t['total']['cost_usd'] or 0:.4f} · 단가 없음 {t['unpriced']} 건")
            return 0
        r = reprice(con, pricing)
        con.commit()
        tot = con.execute("SELECT SUM(cost_usd), (SELECT SUM(cost_usd) FROM usage_daily) FROM usage_event").fetchone()
        print(f"reprice — 단가표 {r['pricing_ver']} · 행 {r['rows']} · 바뀐 행 {r['changed']} · 비용 NULL {r['null_cost']} · "
              f"usage_daily {r['daily_rows']} · 합계 event ${tot[0] or 0:.4f} = daily ${tot[1] or 0:.4f}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
