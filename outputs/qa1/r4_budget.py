#!/usr/bin/env python
"""QA1 r4 — G-26 예산 · G-27 추세 · G-28 캐시 적중률 독립 대조 (spec.md v0.3 §6 · §6.3 · §8).

    AGENTDASH_NO_WATCH=1 uv run python outputs/qa1/r4_budget.py --db <백필 DB 사본> --scratch <빈 스크래치 폴더>

  · API 는 FastAPI TestClient(프로세스 안, 네트워크 없음)로 부른다. 예산 한도는 **가짜** — settings.load_yaml 을 이 프로세스
    안에서만 바꿔 끼운다 (실제 config/budget.yaml 은 읽기만, 금액을 쓰지 않는다). 시각은 core.budget · pages 의 datetime 을 고정.
  · 기대값은 개발 코드가 아니라 spec 글자로 이 파일이 직접 계산한다 (KST = UTC+9, 주 = KST 월요일, 프로젝트 = project_path 마지막 이름).
  · 합성 경계 DB 는 스크래치에 만든다. 출력은 숫자 · 키 · 프로젝트 이름뿐.
"""
import argparse, os, random, sqlite3, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--scratch", required=True)
ap.add_argument("--seed", type=int, default=4)
a = ap.parse_args()
DB = Path(a.db).resolve()
SCR = Path(a.scratch).resolve()
SCR.mkdir(parents=True, exist_ok=True)
assert os.environ.get("AGENTDASH_NO_WATCH") == "1"
os.environ["AGENTDASH_DB"] = str(DB)
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402
from agentdash import settings  # noqa: E402
from agentdash.core import budget as B  # noqa: E402
from agentdash.app.routers import pages as PG  # noqa: E402
from agentdash.app.main import create_app  # noqa: E402

KST = timezone(timedelta(hours=9))
REAL_YAML = settings.load_yaml
FAKE = {"cfg": None}
real_budget_bytes = (REPO / "config" / "budget.yaml").read_bytes()


def fake_load_yaml(name):
    if name == "budget.yaml" and FAKE["cfg"] is not None:
        return FAKE["cfg"]
    return REAL_YAML(name)


settings.load_yaml = fake_load_yaml
NOW = {"t": None}


class FixedDT(datetime):
    @classmethod
    def now(cls, tz=None):
        t = NOW["t"]
        if t is None:
            return datetime.now(tz)
        return t if tz is None else t.astimezone(tz)


B.datetime = FixedDT
PG.datetime = FixedDT
client = TestClient(create_app())
fails = []


def chk(gate, cond, msg):
    if not cond:
        fails.append((gate, msg))
    return cond


def ro(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def pname(path, key):
    if path:
        n = path.rstrip("/").split("/")[-1]
        if n:
            return n
    return key


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def kday(ts):
    return parse(ts).astimezone(KST).strftime("%Y-%m-%d")


def bucket(day, grain):
    d = datetime.strptime(day, "%Y-%m-%d")
    if grain == "week":
        d -= timedelta(days=d.weekday())        # 월요일 = 0
    elif grain == "month":
        d = d.replace(day=1)
    return d.strftime("%Y-%m-%d")


def my_budget(con, now):
    """spec §6.3: 기간 = KST 오늘 00:00 ~ 지금 · 이번 달 1 일 00:00 ~ 지금, 기준 = cost_est_usd 합, NULL 은 더하지 않고 센다."""
    ag = {k: pname(p, pk) for k, p, pk in con.execute("SELECT agent_key, project_path, project_key FROM agent")}
    k = now.astimezone(KST)
    starts = {"day": k.replace(hour=0, minute=0, second=0, microsecond=0)}
    starts["month"] = starts["day"].replace(day=1)
    out = {}
    for key, at, c, ce in con.execute("SELECT agent_key, at, cost_usd, cost_est_usd FROM usage_event"):
        t = parse(at)
        for per, st in starts.items():
            if st <= t <= now:
                for scope in (("total", None), ("project", ag.get(key))):
                    r = out.setdefault((scope, per), [0.0, 0.0, 0])
                    if ce is None:
                        r[2] += 1
                    else:
                        r[0] += ce
                    if c is not None:
                        r[1] += c
    return out, set(ag.values())


def api_budget(cfg, now):
    FAKE["cfg"] = cfg
    NOW["t"] = now
    r = client.get("/api/v1/budget")
    assert r.status_code == 200, r.text
    return r.json()


def lv(ratio, wr):
    return "over" if ratio >= 1.0 else ("warn" if ratio >= wr else "ok")


def compare_budget(tag, con, cfg, now, expect_levels=None):
    js = api_budget(cfg, now)
    mine, known = my_budget(con, now)
    n = maxd = 0.0
    for row in js["rows"]:
        scope = ("total", None) if row["scope"] == "total" else ("project", row["project"])
        est, rec, unp = mine.get((scope, row["period"]), [0.0, 0.0, 0])
        blk = cfg["total"] if row["scope"] == "total" else cfg["projects"][row["project"]]
        lim = (blk or {}).get("daily_usd" if row["period"] == "day" else "monthly_usd")
        if lim is None:
            want = "unset"
        elif row["scope"] == "project" and row["project"] not in known:
            want = "no_records"
        else:
            want = lv(est / lim, cfg["warn_ratio"])
        d = max(abs(row["est_usd"] - est), abs(row["rec_usd"] - rec))
        maxd = max(maxd, d)
        n += 1
        chk("G-26", d <= 0.01, f"{tag} {row['scope']} {row['project']} {row['period']} 금액 차 {d:.6f}")
        chk("G-26", row["unpriced"] == unp, f"{tag} {row['project']} {row['period']} 단가 없음 {row['unpriced']} ≠ {unp}")
        chk("G-26", row["level"] == want, f"{tag} {row['project']} {row['period']} 단계 {row['level']} ≠ {want}")
        if expect_levels is not None:
            ek = expect_levels.get((row["project"], row["period"]))
            if ek is not None:
                chk("G-26", row["level"] == ek, f"{tag} {row['project']} {row['period']} 단계 {row['level']} ≠ 손 {ek}")
    return js, int(n), maxd


# ════ 1. 합성 경계 DB (스크래치) ════════════════════════════════════
syn = SCR / "qa1r4-syn.db"
for x in (syn, Path(str(syn) + "-wal"), Path(str(syn) + "-shm")):
    if x.exists():
        x.unlink()
os.environ["AGENTDASH_DB"] = str(syn)
from agentdash.db import conn as C  # noqa: E402
from agentdash.core import usage as U  # noqa: E402
C.init_db(syn)
sc = C.connect(syn)
agents = [("S:a", "SESSION", "pk-a", "/x/y/ProjA", "a", None, 0),
          ("A:b", "SUBAGENT", "pk-a", "/x/y/ProjB/", "a", "S:a", 1),      # 자손 — 자기 project_path 로 센다 (끝 슬래시)
          ("S:c", "SESSION", "pk-c", None, "c", None, 0),                 # project_path 없음 → project_key
          ("S:z", "SESSION", "pk-z", "/x/ZeroProj", "z", None, 0)]        # 분모 0 (토큰 0 행)
for k, kind, pk, pp, sid, par, dep in agents:
    sc.execute("INSERT INTO agent (agent_key, kind, project_key, project_path, session_id, parent_key, depth, state) "
               "VALUES (?,?,?,?,?,?,?,'DONE')", (k, kind, pk, pp, sid, par, dep))
# 지금 = 2026-11-02 03:00:00Z = KST 11-02(월) 12:00. 오늘 시작 = 11-01T15:00:00Z, 이번 달 시작 = 10-31T15:00:00Z.
# 11-01 = 일요일 → 11-01T14:59:59.999Z(KST 일 23:59)은 주 10-26, 11-01T15:00Z(KST 월 00:00)은 주 11-02.
ev = [  # key, at, cost_usd, cost_est_usd, input, cache_read, w5, w1, out, out_est
    ("S:a", "2026-10-31T14:59:59.999Z", 50.0, 100.0, 10, 0, 0, 0, 5, None),       # 지난달 (KST 10-31 23:59:59.999)
    ("S:a", "2026-10-31T15:00:00.000Z", 0.5, 1.0, 10, 30, 0, 0, 5, 40),           # 이번 달 첫 순간
    ("S:a", "2026-11-01T14:59:59.999Z", 1.0, 2.0, 10, 30, 0, 0, 5, None),         # 어제 마지막 순간
    ("S:a", "2026-11-01T15:00:00Z", 2.0, 4.0, 10, 30, 0, 0, 5, 50),               # 오늘 첫 순간 (소수점 없는 꼴)
    ("S:a", "2026-11-02T03:00:00.000Z", 4.0, 8.0, 10, 30, 0, 0, 5, None),         # 지금과 같은 시각 (포함)
    ("S:a", "2026-11-02T03:00:00.001Z", 500.0, 1000.0, 10, 30, 0, 0, 5, None),    # 미래 (제외)
    ("S:a", "2026-11-02T01:00:00.000Z", None, None, 10, 30, 0, 0, 5, None),       # 단가 없음 (더하지 않고 센다)
    ("A:b", "2026-11-02T02:00:00.000Z", 8.0, 16.0, 1, 2, 3, 4, 7, 70),
    ("S:c", "2026-11-02T02:30:00.000Z", 16.0, 32.0, 5, 15, 0, 0, 1, None),
    ("S:z", "2026-11-02T02:40:00.000Z", 0.0, 0.0, 0, 0, 0, 0, 0, None),
]
for i, (k, at, c, ce, inp, cr, w5, w1, o, oe) in enumerate(ev):
    sc.execute("INSERT INTO usage_event (agent_key, request_id, at, model, input_tokens, cache_read, cache_write_5m, "
               "cache_write_1h, output_tokens, cost_usd, output_est, cost_est_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
               (k, f"r{i}", at, "claude-opus-5-5" if c is not None else "claude-unknown-x", inp, cr, w5, w1, o, c, oe, ce))
U.rebuild_daily(sc)
sc.commit()
sc.close()
now = datetime(2026, 11, 2, 3, 0, 0, tzinfo=timezone.utc)
cfg = {"warn_ratio": 0.8,
       "total": {"daily_usd": 75.0, "monthly_usd": 63.0},                  # 오늘 60/75 = 0.8 → warn · 달 63/63 = 1.0 → over
       "projects": {"ProjA": {"daily_usd": 15.0001, "monthly_usd": 15.0},  # 12/15.0001 ok · 15/15 over
                    "ProjB": {"daily_usd": 20.0, "monthly_usd": 16.0001},  # 16/20 = 0.8 warn · 16/16.0001 warn
                    "pk-c": {"daily_usd": None, "monthly_usd": 32.0},      # unset · 32/32 over
                    "NoSuchProj": {"daily_usd": 10.0, "monthly_usd": None}}}  # no_records · unset
hand = {(None, "day"): "warn", (None, "month"): "over", ("ProjA", "day"): "ok", ("ProjA", "month"): "over",
        ("ProjB", "day"): "warn", ("ProjB", "month"): "warn", ("pk-c", "day"): "unset", ("pk-c", "month"): "over",
        ("NoSuchProj", "day"): "no_records", ("NoSuchProj", "month"): "unset"}
hand_amt = {(None, "day"): (60.0, 30.0, 1), (None, "month"): (63.0, 31.5, 1), ("ProjA", "day"): (12.0, 6.0, 1),
            ("ProjA", "month"): (15.0, 7.5, 1), ("ProjB", "day"): (16.0, 8.0, 0), ("pk-c", "month"): (32.0, 16.0, 0)}
con = ro(syn)
js, n, maxd = compare_budget("합성", con, cfg, now, hand)
for row in js["rows"]:
    h = hand_amt.get((row["project"], row["period"]))
    if h:
        chk("G-26", (abs(row["est_usd"] - h[0]) < 1e-9 and abs(row["rec_usd"] - h[1]) < 1e-9 and row["unpriced"] == h[2]),
            f"합성 손계산 {row['project']} {row['period']} {row['est_usd']},{row['rec_usd']},{row['unpriced']} ≠ {h}")
print(f"[G-26 합성] 칸 {n} · 손 단계 대조 {len(hand)} · 손 금액 대조 {len(hand_amt)} · worst = {js['worst']['level']} "
      f"{js['worst']['project']} {js['worst']['period']} ({js['worst']['ratio']:.4f})")
chk("G-26", js["worst"]["level"] == "over", "worst 가 over 아님")
# D-01 띠 · D-07 게이지 표시 (화면 표시만)
d01 = client.get("/").text
chk("G-26", 'id="budget-band"' in d01 and "예산 초과" in d01 and "/insights" in d01, "D-01 띠 없음")
d07 = client.get("/insights").text
chk("G-26", 'data-budget-level="no_records"' in d07 and 'data-budget-level="unset"' in d07, "D-07 unset/no_records 게이지 없음")
print(f"  D-01 띠 {'있음' if 'id=\"budget-band\"' in d01 else '없음'} · 띠 문구 '오늘 전체 80 %' {'오늘 전체 80 %' in d01} · "
      f"'이번 달 전체 100 %' {'이번 달 전체 100 %' in d01} · D-07 게이지 단계 표지 "
      f"{sorted(set(x.split('\"')[0] for x in d07.split('data-budget-level=\"')[1:]))}")
# 경계 비율 한 칸씩: 0.7999 ok · 0.8 warn · 0.9999 warn · 1.0 over · warn_ratio 바꿈
for lim, wr, want in ((60 / 0.7999, 0.8, "ok"), (75.0, 0.8, "warn"), (60 / 0.9999, 0.8, "warn"), (60.0, 0.8, "over"),
                      (75.0, 0.81, "ok"), (75.0, 0.5, "warn")):
    js2 = api_budget({"warn_ratio": wr, "total": {"daily_usd": lim, "monthly_usd": None}, "projects": {}}, now)
    got = next(r for r in js2["rows"] if r["period"] == "day")["level"]
    chk("G-26", got == want, f"경계 lim={lim:.4f} wr={wr} → {got} ≠ {want}")
print("[G-26 경계] 0.7999 ok · 0.8 warn · 0.9999 warn · 1.0 over · warn_ratio 0.81/0.5 — 불일치",
      sum(1 for g, m in fails if m.startswith("경계")))
# 설정 오류 → SettingsError (조용한 기본값 금지) · 실제 budget.yaml (null) → 전부 unset · worst None
bad = {"warn_ratio": 0.8, "total": {"daily_usd": -1, "monthly_usd": None}, "projects": {}}
FAKE["cfg"] = bad
try:
    rbad = client.get("/api/v1/budget")
    bad_res = f"HTTP {rbad.status_code}"
except settings.SettingsError:
    bad_res = "SettingsError 올라옴"
d01bad = client.get("/").text
print(f"  음수 한도 → API {bad_res} · D-01 '예산 설정 오류' {'예산 설정 오류' in d01bad}")
FAKE["cfg"] = None
js_real = api_budget(None, now)
FAKE["cfg"] = None
chk("G-26", all(r["level"] == "unset" for r in js_real["rows"]) and js_real["worst"] is None, "실제 설정 unset 아님")
print(f"  실제 config/budget.yaml → 칸 {len(js_real['rows'])} · 단계 {sorted(set(r['level'] for r in js_real['rows']))} · worst {js_real['worst']}")
con.close()

# 합성 추세 — 주 경계(KST 월요일) · 월 경계
FAKE["cfg"] = None
syn_tr = {}
for grain in ("day", "week", "month"):
    j = client.get("/api/v1/trend", params={"grain": grain, "from": "2026-10-01", "to": "2026-11-30", "group": "total"}).json()
    syn_tr[grain] = {r["bucket"]: (round(r["cost_usd"] or 0, 6), round(r["cost_est_usd"] or 0, 6), r["output_tokens"], r["output_est_total"])
                     for r in j["rows"]}
want_week = {"2026-10-26": (51.5, 103.0, 15, 15 + 35), "2026-11-02": (530.0, 1060.0, 28, 28 - 5 - 7 + 50 + 70)}
want_month = {"2026-10-01": (50.0, 100.0, 5, 5), "2026-11-01": (531.5, 1063.0, 38, 38 - 5 - 5 - 7 + 40 + 50 + 70)}
chk("G-27", syn_tr["week"] == want_week, f"합성 주 {syn_tr['week']} ≠ {want_week}")
chk("G-27", syn_tr["month"] == want_month, f"합성 월 {syn_tr['month']} ≠ {want_month}")
print(f"[G-27 합성] 주 묶음 {sorted(syn_tr['week'])} · 월 묶음 {sorted(syn_tr['month'])} · 일 묶음 {sorted(syn_tr['day'])} · "
      f"손 대조 주 {syn_tr['week'] == want_week} · 월 {syn_tr['month'] == want_month}")
# 합성 적중률 — 분모 0 → None · D-07 '—'
ej = client.get("/api/v1/efficiency", params={"group": "agent", "from": "2026-10-01", "to": "2026-11-30"}).json()
z = next(r for r in ej["rows"] if r["key"] == "S:z")
bh = next(r for r in ej["rows"] if r["key"] == "A:b")
chk("G-28", z["hit"] is None, "분모 0 hit 가 None 아님")
chk("G-28", abs(bh["hit"] - 2 / (1 + 2 + 3 + 4)) < 1e-12, "A:b 적중률 (5m+1h 캐시 쓰기) 불일치")
pg = client.get("/insights", params={"eff": "agent", "from": "2026-10-01", "to": "2026-11-30"}).text
seg = pg[pg.find("S:z") - 0: pg.find("S:z") + 1200] if "S:z" in pg else ""
print(f"[G-28 합성] 분모 0 → API hit {z['hit']} · 화면 '—' {'—' in seg} · A:b 2/(1+2+3+4) = {bh['hit']:.4f}")

# ════ 2. 실제 백필 DB ═════════════════════════════════════════════
os.environ["AGENTDASH_DB"] = str(DB)
con = ro(DB)
real_now = datetime.now(timezone.utc).replace(microsecond=0)
mine, known = my_budget(con, real_now)
proj_day = sorted(((v[0], s[1]) for (s, per), v in mine.items() if s[0] == "project" and per == "month"), reverse=True)
top = [p for _, p in proj_day[:3]]
cfg = {"warn_ratio": 0.8, "total": {"daily_usd": 1e9, "monthly_usd": None}, "projects": {}}
for i, p in enumerate(top):
    m = mine[(("project", p), "month")][0]
    d = mine.get((("project", p), "day"), [0.0])[0]
    cfg["projects"][p] = {"daily_usd": (d / 0.9) if d > 0 else 1.0, "monthly_usd": m / (0.5, 0.85, 1.2)[i]}
cfg["projects"]["NoSuchProj"] = {"daily_usd": 1.0, "monthly_usd": 1.0}
js, n, maxd = compare_budget("실제", con, cfg, real_now)
lvls = {(r["project"], r["period"]): r["level"] for r in js["rows"]}
print(f"[G-26 실제 DB] 칸 {n} (전체 2 + 프로젝트 {len(cfg['projects'])}×2) · 최대 차 ${maxd:.6f} · 단계 "
      + " · ".join(f"{p or '전체'}/{per}={l}" for (p, per), l in sorted(lvls.items(), key=lambda x: (x[0][0] or '', x[0][1]))))
tot_d = mine.get((("total", None), "day"), [0, 0, 0]); tot_m = mine.get((("total", None), "month"), [0, 0, 0])
print(f"  손 직접 합 (KST {real_now.astimezone(KST):%m-%d %H:%M}) 오늘 추정 ${tot_d[0]:.4f} / 기록 ${tot_d[1]:.4f} · "
      f"이번 달 ${tot_m[0]:.4f} / ${tot_m[1]:.4f} · 단가 없음 {tot_d[2]}/{tot_m[2]} · 프로젝트 수 {len(known)}")
# 모든 기록 프로젝트를 한도 칸으로 (전수)
cfg_all = {"warn_ratio": 0.8, "total": {"daily_usd": None, "monthly_usd": None},
           "projects": {p: {"daily_usd": 1.0, "monthly_usd": 1.0} for p in sorted(known)}}
js, n_all, maxd_all = compare_budget("실제 전수", con, cfg_all, real_now)
print(f"  전수: 프로젝트 {len(known)} × 2 + 전체 2 = 칸 {n_all} · 최대 차 ${maxd_all:.6f}")
FAKE["cfg"] = None
NOW["t"] = None

# ── G-27 추세 (실제) ──
today = real_now.astimezone(KST).strftime("%Y-%m-%d")
frm = "2026-07-01"
ag = {k: pname(p, pk) for k, p, pk in con.execute("SELECT agent_key, project_path, project_key FROM agent")}
ev_rows = list(con.execute("SELECT agent_key, at, cost_usd, cost_est_usd, output_tokens, output_est FROM usage_event"))
daily_rows = list(con.execute("SELECT day, agent_key, cost_usd, cost_est_usd, output_tokens, output_est FROM usage_daily"))
nb = mism = 0
ev_tot = [0.0, 0.0, 0, 0]
for grain in ("day", "week", "month"):
    for group in ("total", "project"):
        exp = {}
        for k, at, c, ce, o, oe in ev_rows:
            day = kday(at)
            if not (frm <= day <= today):
                continue
            b = (bucket(day, grain), ag.get(k) if group == "project" else None)
            r = exp.setdefault(b, [0.0, 0.0, 0, 0])
            r[0] += c or 0; r[1] += ce or 0; r[2] += o or 0; r[3] += oe if oe is not None else (o or 0)
        dexp = {}
        for day, k, c, ce, o, oe in daily_rows:
            if not (frm <= day <= today):
                continue
            b = (bucket(day, grain), ag.get(k) if group == "project" else None)
            r = dexp.setdefault(b, [0.0, 0.0, 0, 0])
            r[0] += c or 0; r[1] += ce or 0; r[2] += o or 0; r[3] += oe or 0
        evsus = {}
        for k, at, c, ce, o, oe in ev_rows:
            day = kday(at)
            if oe is not None and frm <= day <= today:
                b = (bucket(day, grain), ag.get(k) if group == "project" else None)
                evsus[b] = evsus.get(b, 0) + oe
        j = client.get("/api/v1/trend", params={"grain": grain, "from": frm, "to": today, "group": group}).json()
        got = {(r["bucket"], r["project"]): [r["cost_usd"] or 0, r["cost_est_usd"] or 0, r["output_tokens"], r["output_est_total"]]
               for r in j["rows"]}
        keys = set(exp) | set(got)
        for b in keys:
            e, g, d = exp.get(b, [0, 0, 0, 0]), got.get(b, [0, 0, 0, 0]), dexp.get(b, [0, 0, 0, 0])
            nb += 1
            bad = (abs(e[0] - g[0]) > 1e-6 or abs(e[1] - g[1]) > 1e-6 or e[2] != g[2] or e[3] != g[3]
                   or abs(d[0] - e[0]) > 1e-6 or abs(d[1] - e[1]) > 1e-6 or d[2] != e[2] or d[3] != evsus.get(b, 0))
            if bad:
                mism += 1
                chk("G-27", False, f"추세 {grain}/{group} {b} event {e} · API {g} · daily {d}")
        if grain == "day" and group == "total":
            ev_tot = [sum(v[i] for v in exp.values()) for i in range(4)]
            wk_ok = all(datetime.strptime(b[0], "%Y-%m-%d").weekday() == 0 for b in got) if False else None
        if grain == "week":
            chk("G-27", all(datetime.strptime(b[0], "%Y-%m-%d").weekday() == 0 or b[0] == frm for b in got),
                f"주 묶음이 월요일 아님 ({group})")
print(f"[G-27 실제 DB] {frm}~{today} · grain 3 × group 2 · 묶음 {nb} · 불일치 {mism} · 합 기록 ${ev_tot[0]:.6f} · "
      f"추정 보정 ${ev_tot[1]:.6f} · 출력 {ev_tot[2]} · 추정 출력 {ev_tot[3]}")
# trend 첫 묶음이 from 이 월요일이 아닐 때 어떻게 잘리는지 (참고)
jw = client.get("/api/v1/trend", params={"grain": "week", "from": "2026-10-15", "to": today, "group": "total"}).json()
print(f"  참고: from=2026-10-15(목) 주 묶음 시작 {[r['bucket'] for r in jw['rows']][:3]} — 첫 묶음 = 그 주 월요일 라벨, 합은 from 이후만")

# ── G-28 캐시 적중률 (실제, 표본 10 + 전수) ──
rnd = random.Random(a.seed)
sess_of = {k: s for k, s in con.execute("SELECT agent_key, session_id FROM agent")}
par = {k: p for k, p in con.execute("SELECT agent_key, parent_key FROM agent")}
ffrom = "2026-07-01"
ua = datetime.strptime(ffrom, "%Y-%m-%d").replace(tzinfo=KST)
ub = datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
evs = [(k, i or 0, cr or 0, (w5 or 0) + (w1 or 0), ce) for k, at, i, cr, w5, w1, ce in con.execute(
    "SELECT agent_key, at, input_tokens, cache_read, cache_write_5m, cache_write_1h, cost_est_usd FROM usage_event")
    if ua <= parse(at) < ub]


def root_of(k):
    seen = set()
    while par.get(k) and k not in seen:
        seen.add(k)
        k = par[k]
    return k


sample_n = all_n = maxd = 0.0
sess_parent_diff = 0
picked = []
for group in ("project", "session", "agent"):
    acc = {}
    acc2 = {}
    for k, i, cr, cw, ce in evs:
        key = ag.get(k) if group == "project" else (f"S:{sess_of.get(k)}" if group == "session" else k)
        r = acc.setdefault(key, [0, 0, 0, 0.0])
        r[0] += i; r[1] += cr; r[2] += cw; r[3] += ce or 0
        if group == "session":
            r2 = acc2.setdefault(root_of(k), [0, 0, 0])
            r2[0] += i; r2[1] += cr; r2[2] += cw
    j = client.get("/api/v1/efficiency", params={"group": group, "from": ffrom, "to": today}).json()
    rows = j["rows"]
    chk("G-28", len(rows) == len(acc), f"{group} 행 수 API {len(rows)} ≠ 손 {len(acc)}")
    # 정렬: (1 − 적중률) × cost_est_usd 큰 순
    w = [r["waste"] for r in rows]
    chk("G-28", all(w[i] >= w[i + 1] - 1e-12 for i in range(len(w) - 1)), f"{group} 정렬 위반")
    for r in rows:
        m = acc.get(r["key"])
        if m is None:
            chk("G-28", False, f"{group} {r['key']} 손계산에 없음")
            continue
        den = m[0] + m[1] + m[2]
        hit = m[1] / den if den else None
        all_n += 1
        if (hit is None) != (r["hit"] is None) or (hit is not None and abs(hit - r["hit"]) > 0.001):
            chk("G-28", False, f"{group} {r['key']} hit {r['hit']} ≠ {hit}")
        elif hit is not None:
            maxd = max(maxd, abs(hit - r["hit"]))
        wexp = (1 - hit) * m[3] if hit is not None else 0.0
        chk("G-28", abs(wexp - r["waste"]) < 1e-6, f"{group} {r['key']} waste")
        if group == "session" and r["key"] in acc2:
            m2 = acc2[r["key"]]
            if m2 != m[:3]:
                sess_parent_diff += 1
    for r in rnd.sample(rows, min(len(rows), {"project": 3, "session": 3, "agent": 4}[group])):
        picked.append((group, r["key"][:14], r["hit"]))
print(f"[G-28 실제 DB] 전수 행 {int(all_n)} (프로젝트·세션·에이전트) · 최대 차 {maxd:.9f} · 세션 = parent 사슬 뿌리 묶음과 다른 세션 {sess_parent_diff}")
print("  표본 10 손계산 (시드 %d): " % a.seed + " · ".join(f"{g}:{k} {h:.4f}" for g, k, h in picked))

# ════ 끝 ════
chk("안전", (REPO / "config" / "budget.yaml").read_bytes() == real_budget_bytes, "실제 budget.yaml 바뀜")
print(f"실제 config/budget.yaml 바이트 그대로 {(REPO / 'config' / 'budget.yaml').read_bytes() == real_budget_bytes}")
print(f"불일치 {len(fails)}")
for g, m in fails[:30]:
    print("  FAIL", g, m)
