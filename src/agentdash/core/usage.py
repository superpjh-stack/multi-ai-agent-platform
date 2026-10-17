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


# ── 합계 ─────────────────────────────────────────────────────────────
_SUM = ("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(cache_read),0), "
        "COALESCE(SUM(cache_write_5m),0)+COALESCE(SUM(cache_write_1h),0), COALESCE(SUM(output_tokens),0), "
        "COALESCE(SUM(thinking_tokens),0), SUM(cost_usd), COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END),0), COUNT(*) "
        "FROM usage_event WHERE agent_key IN ({})")


def _sum(con: sqlite3.Connection, keys: list[str]) -> dict:
    out = dict(input_tokens=0, cache_read=0, cache_write=0, output_tokens=0, thinking_tokens=0, cost_usd=None,
               unpriced=0, requests=0)
    for i in range(0, len(keys), 500):
        part = keys[i:i + 500]
        r = con.execute(_SUM.format(",".join("?" * len(part))), part).fetchone()
        for j, k in enumerate(("input_tokens", "cache_read", "cache_write", "output_tokens", "thinking_tokens")):
            out[k] += r[j]
        if r[5] is not None:
            out["cost_usd"] = (out["cost_usd"] or 0.0) + r[5]
        out["unpriced"] += r[6]
        out["requests"] += r[7]
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
    keys = [agent_key]
    if descendants:
        keys += _descendants(con, agent_key)
    return _sum(con, keys)


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
        for at, mdl, i, cr, w5, w1, o, c in con.execute(
                "SELECT at, model, input_tokens, cache_read, cache_write_5m, cache_write_1h, output_tokens, cost_usd "
                "FROM usage_event WHERE agent_key=?", (k,)):
            if not at:
                continue
            key = (kst_day(at), mdl or "")
            r = rows.setdefault(key, [0, 0, 0, 0, 0, 0, 0, None])
            r[0] += i or 0
            r[1] += cr or 0
            r[2] += (w5 or 0) + (w1 or 0)
            r[3] += o or 0
            if c is not None:
                r[7] = (r[7] or 0.0) + c
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
                models = [("", rows.setdefault((day, ""), [0, 0, 0, 0, 0, 0, 0, None]))]
            # 도구 · 파일 · 시간은 모델 칸이 없으므로 그날 출력이 가장 많은 모델 행에 붙인다
            top = max(models, key=lambda x: x[1][3])[0]
            for m, r in models:
                if m == top:
                    r[4], r[5], r[6] = tools_by_day.get(day, 0), len(files_by_day.get(day, ())), act.get(day, 0)
                con.execute(
                    "INSERT INTO usage_daily (day, agent_key, model, input_tokens, cache_read, cache_write, output_tokens, "
                    "tool_calls, files_written, active_seconds, cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (day, k, m, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]))
                n += 1
    return n


def reprice(con: sqlite3.Connection, pricing: Pricing | None = None) -> dict:
    pricing = pricing or load_pricing()
    cur = con.execute("SELECT agent_key, request_id, at, model, speed, input_tokens, cache_read, cache_write_5m, "
                      "cache_write_1h, output_tokens FROM usage_event")
    upd, changed, nulls = [], 0, 0
    for r in cur.fetchall():
        ev = M.UsageEvent(agent_key=r[0], request_id=r[1], at=r[2], model=r[3], speed=r[4], input_tokens=r[5],
                          cache_read=r[6], cache_write_5m=r[7], cache_write_1h=r[8], output_tokens=r[9])
        c, ver = cost(ev, pricing)
        nulls += c is None
        upd.append((c, ver, r[0], r[1]))
    for c, ver, k, rid in upd:
        cc = con.execute("UPDATE usage_event SET cost_usd=?, pricing_ver=? WHERE agent_key=? AND request_id=? "
                         "AND (cost_usd IS NOT ? OR pricing_ver IS NOT ?)", (c, ver, k, rid, c, ver))
        changed += cc.rowcount
    daily = rebuild_daily(con)
    return {"rows": len(upd), "changed": changed, "null_cost": nulls, "pricing_ver": pricing.version, "daily_rows": daily}


def unpriced_models(con: sqlite3.Connection, pricing: Pricing | None = None) -> list[tuple[str, int]]:
    pricing = pricing or load_pricing()
    out = []
    for mdl, n in con.execute("SELECT model, COUNT(*) FROM usage_event GROUP BY model ORDER BY 2 DESC"):
        if pricing.resolve(mdl) is None:
            out.append((mdl, n))
    return out


def main(argv: list[str] | None = None) -> int:
    """`make pricing-check` · `make reprice` — DB 는 AGENTDASH_DB (원천은 건드리지 않는다)."""
    import argparse

    from agentdash.db import conn

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pricing-check", "reprice"])
    ap.add_argument("--db", default=None)
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
