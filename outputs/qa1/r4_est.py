#!/usr/bin/env python
"""QA1 r4 — G-24 · V-12 추정 출력 독립 재계산 (spec.md v0.3 §6.2 · §2.3 · D-23). agentdash 를 import 하지 않는다.

  요청 = 같은 기록(jsonl) · 같은 requestId 의 assistant 줄 묶음 (usage 있음, model <synthetic> 제외).
  의심 = 묶음 output_tokens 최대 < 30 이고 묶음 content 블록 json.dumps(블록) 길이 합 > 400.
  추정 = max(ceil((text 글자 + json.dumps(tool_use.input, ensure_ascii=False) 글자) / 4), 기록 output) — thinking 제외.
  원천은 'rb' 로만, DB src_file.offset 바이트까지만 (DB 가 읽은 지점). DB 는 mode=ro. 출력은 숫자 · 키뿐 (길이 숫자 개별값도 찍지 않음).

    .venv/bin/python -I outputs/qa1/r4_est.py --db data/agentdash-qa1.db [--home ~/.claude]
"""
import argparse, json, math, os, re, sqlite3
from collections import defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--home", default=os.path.expanduser("~/.claude"))
ap.add_argument("--pricing", default="config/pricing.yaml")
a = ap.parse_args()
proj = Path(a.home) / "projects"
con = sqlite3.connect(Path(a.db).resolve().as_uri() + "?mode=ro", uri=True)
offs = {p: o for p, o in con.execute("SELECT path, offset FROM src_file")}


def key_of(p: Path):
    rel = p.relative_to(proj).parts
    if len(rel) == 2:
        return "S:" + p.stem, p.stem
    sid = rel[1]
    return "A:" + p.name[len("agent-"):-len(".jsonl")], sid


files = sorted(proj.glob("*/*.jsonl")) + sorted(proj.glob("*/*/subagents/agent-*.jsonl")) \
    + sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl"))
kind_of = {}
groups = {}            # (file, rid) -> [max_out, json_len, est_chars]
synthetic = 0
for f in files:
    k, sid = key_of(f)
    kind_of[k] = "main" if "subagents" not in f.parts else ("wf" if "workflows" in f.parts else "sub")
    lim = offs.get(str(f))
    if lim is None:
        continue
    with open(f, "rb") as fh:
        data = fh.read(lim)
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        m = d.get("message") or {}
        if not isinstance(m.get("usage"), dict):
            continue
        if m.get("model") == "<synthetic>":
            synthetic += 1
            continue
        rid = d.get("requestId")
        if not rid:
            continue
        g = groups.setdefault((str(f), k, sid, rid), [0, 0, 0, d.get("timestamp")])
        g[0] = max(g[0], m["usage"].get("output_tokens") or 0)
        for b in m.get("content") or []:
            g[1] += len(json.dumps(b))
            if isinstance(b, dict) and b.get("type") == "text":
                g[2] += len(b.get("text") or "")
            elif isinstance(b, dict) and b.get("type") == "tool_use":
                g[2] += len(json.dumps(b.get("input"), ensure_ascii=False))

db = {(k, r): (o, oe, c, ce, mdl, sp, i, cr, w5, w1) for k, r, o, oe, c, ce, mdl, sp, i, cr, w5, w1 in con.execute(
    "SELECT agent_key, request_id, output_tokens, output_est, cost_usd, cost_est_usd, model, speed, input_tokens, cache_read,"
    " cache_write_5m, cache_write_1h FROM usage_event")}
db_sus = {kr for kr, v in db.items() if v[1] is not None}

# ── 모집단 A: spec 글자 (기록마다 · requestId 마다) ─────────────────────
fileA = [(f, k, sid, rid, g) for (f, k, sid, rid), g in groups.items()]
susA = sum(1 for *_, g in fileA if g[0] < 30 and g[1] > 400)
# ── 모집단 B: D-23 (세션 안 requestId 한 번 — 소유 = DB 행이 있는 (key, rid), 없으면 그 세션 첫 기록) ─────
by_sess = defaultdict(list)
for f, k, sid, rid, g in fileA:
    by_sess[(sid, rid)].append((f, k, g))
popB = susB = 0
own = {}
for (sid, rid), lst in by_sess.items():
    owner = [x for x in lst if (x[1], rid) in db] or lst[:1]
    f, k, g = owner[0]
    own[(k, rid)] = g
    popB += 1
    susB += (g[0] < 30 and g[1] > 400)
n_db = len(db)
r_db = 100 * len(db_sus) / n_db
rA, rB = 100 * susA / len(fileA), 100 * susB / popB
print(f"원천 기록 {len(files)} · 요청(기록별, spec 글자) {len(fileA)} · 의심 {susA} ({rA:.2f}%)")
print(f"원천 요청(세션 안 requestId 한 번, D-23) {popB} · 의심 {susB} ({rB:.2f}%)")
print(f"DB usage_event {n_db} · output_est 있음 {len(db_sus)} ({r_db:.2f}%)")
print(f"  차 (spec 글자 단위) {abs(r_db - rA):.2f}%p · 차 (D-23 단위) {abs(r_db - rB):.2f}%p · 허용 0.5%p")
print(f"  <synthetic> usage 줄 원천 {synthetic} · DB synthetic 행 {sum(1 for v in db.values() if v[4] == '<synthetic>')}")
by_kind = defaultdict(lambda: [0, 0])
for (k, rid), g in own.items():
    by_kind[kind_of.get(k, '?')][0] += 1
    by_kind[kind_of.get(k, '?')][1] += (g[0] < 30 and g[1] > 400)
print("  종류별 (D-23 단위) " + " · ".join(f"{t} {s}/{n} ({100*s/max(n,1):.1f}%)" for t, (n, s) in sorted(by_kind.items())))

# ── 행 단위 대조 ──────────────────────────────────────────────────────
import yaml  # noqa: E402  (단가표 읽기용 — config 만, agentdash 아님)
pr = yaml.safe_load(open(a.pricing, encoding="utf-8"))
models, aliases = pr["models"], pr.get("aliases") or {}


def out_rate(model, prompt, speed):
    m = models.get(aliases.get(model, model))
    if m is None:
        return None
    if "tiers" in m:
        t = next(t for t in m["tiers"] if t["max_prompt"] is None or prompt <= t["max_prompt"])
        o = t["out"]
    else:
        o = m["out"]
    if speed == "fast":
        if "fast_mult" not in m:
            return None
        o *= m["fast_mult"]
    return o


miss_db = miss_src = sus_mis = est_mis = lower_bad = nonsus_notnull = cost_bad = nonsus_cost_bad = 0
len_leak = 0
ex = []
for kr, g in own.items():
    v = db.get(kr)
    if v is None:
        miss_db += 1
        continue
    o, oe, c, ce, mdl, sp, i, cr, w5, w1 = v
    sus = g[0] < 30 and g[1] > 400
    exp = max(math.ceil(g[2] / 4), o or 0) if sus else None
    if sus != (oe is not None):
        sus_mis += 1
        if len(ex) < 5:
            ex.append((kr[0], "sus" if sus else "nonsus", "db_est" if oe is not None else "db_null", g[0], o))
    elif sus and oe != exp:
        est_mis += 1
        if len(ex) < 5:
            ex.append((kr[0], "est", oe, exp))
    if oe is not None and o is not None and oe < o:
        lower_bad += 1
    if oe is None:
        if ce != c:
            nonsus_cost_bad += 1
    else:
        rate = out_rate(mdl, (i or 0) + (cr or 0) + (w5 or 0) + (w1 or 0), sp)
        if c is None or rate is None:
            if ce is not None:
                cost_bad += 1
        else:
            want = c + (oe - (o or 0)) * rate / 1e6
            if abs(want - ce) > 1e-9:
                cost_bad += 1
    # 길이 숫자가 DB 숫자 칸 어디에든 그대로 들어갔는지 (개별값 출력 없음)
    if sus:
        for val in (o, oe, i, cr, w5, w1):
            if val is not None and val in (g[1], g[2]) and val != exp:
                len_leak += 1
for kr in db:
    if kr not in own and not kr[1].startswith("uuid:"):
        miss_src += 1
print(f"행 대조 (D-23 소유 행 {len(own)}): DB 에 없음 {miss_db} · 원천에 없는 DB 행 {miss_src}")
print(f"  의심 판정 불일치 {sus_mis} · output_est 값 불일치 {est_mis} · output_est < output_tokens {lower_bad}")
print(f"  비의심 행 cost_est_usd ≠ cost_usd {nonsus_cost_bad} · 의심 행 cost_est 손계산 불일치 {cost_bad}")
print(f"  길이 숫자(json 길이 · text+도구 입력 글자)가 DB 숫자 칸에 그대로 {len_leak}")
for e in ex:
    print("   예", e)
# 경계 분포 — 29/30 · 400/401 근처 요청 수 (판정이 경계를 지키는지)
edge = defaultdict(lambda: [0, 0])
for kr, g in own.items():
    v = db.get(kr)
    if v is None:
        continue
    for name, cond in (("out=29", g[0] == 29 and g[1] > 400), ("out=30", g[0] == 30 and g[1] > 400),
                       ("json=400", g[0] < 30 and g[1] == 400), ("json=401", g[0] < 30 and g[1] == 401)):
        if cond:
            edge[name][0] += 1
            edge[name][1] += v[1] is not None
print("  경계 요청 (원천 수 / DB 의심 수): " + " · ".join(f"{n} {t}/{s}" for n, (t, s) in sorted(edge.items())) if edge else "  경계 요청 0")
# 합계
s_out = sum(v[0] or 0 for v in db.values())
s_est = sum((v[1] if v[1] is not None else (v[0] or 0)) for v in db.values())
s_c = sum(v[2] or 0 for v in db.values()); s_ce = sum(v[3] or 0 for v in db.values())
print(f"DB 출력 기록 {s_out} · 추정 보정 {s_est} (+{s_est - s_out}) · 비용 기록 ${s_c:.6f} · 추정 보정 ${s_ce:.6f}")
# 스키마 — usage_event · usage_daily 열 = spec 블록 (길이 열 없음)
spec = open("spec.md", encoding="utf-8").read()
for t in ("usage_event", "usage_daily"):
    blk = re.search(r"CREATE TABLE %s \((.*?)\n\);" % t, spec, re.S).group(1)
    want = [w for w in re.findall(r"(?:^|,|\()\s*([a-z_0-9]+)\s+(?:TEXT|INTEGER|REAL)", re.sub(r"--[^\n]*", "", blk), re.M)]
    got = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
    print(f"스키마 {t}: spec 열 {len(want)} · DB 열 {len(got)} · 같음 {want == got} · 길이 꼴 열 {[c for c in got if re.search('len|char|json', c)]}")
