#!/usr/bin/env python
"""QA1 r6 — T-08 width API 확인 (TestClient, lifespan 없이 — 감시기 · 서버 안 띄움).

    uv run python outputs/qa1/r6_grid_api.py --db <DB>

  A1 /api/v1/twin?width=1400 · 360 · 4000 · (없음) · since=all — 응답 grid · 라인 상자 · 설비 상자가 twin.build(now=generated_at) 와 같은가,
     width 없음 == width=1400, 겹침 0 (r6_twin.hit 전 쌍)
  A2 이상 값 → 422 + error 에 'width': 0 · -1 · abc · 1.5 · '' · ' ' · 1e3 · 1400px · 100001 · 99999999 · 0x10 · +5
     경계 값 → 200: 1 · 100000 · ' 1400' (앞뒤 공백 — 구현이 strip)
  A3 project 필터 API = build (SongWol QR · Platform)
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
a = ap.parse_args()
os.environ["AGENTDASH_DB"] = str(Path(a.db).resolve())

import sqlite3  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from agentdash.app.main import app  # noqa: E402
from agentdash.core import twin  # noqa: E402
from r6_twin import dt, hit  # noqa: E402

c = TestClient(app)
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)


AGO = ("elapsed_s", "ended_ago_s", "last_ago_s")


def strip(r):
    """elapsed_ms 와 초 단위 경과(API now 는 마이크로초까지 — build(now=generated_at 초) 와 1 초 내림 차)를 뺀 사본."""
    r = json.loads(json.dumps(r))
    r.pop("elapsed_ms", None)
    for ln in r.get("lines", []):
        for m in ln["machines"]:
            for f in AGO:
                m.pop(f, None)
    return r


def ago_close(x, y):
    """같은 설비의 초 단위 경과 차가 0 또는 1 초 (API now 소수점 내림)."""
    for l1, l2 in zip(x["lines"], y["lines"]):
        for m1, m2 in zip(l1["machines"], l2["machines"]):
            for f in AGO:
                if (m1[f] is None) != (m2[f] is None) or (m1[f] is not None and not 0 <= m1[f] - m2[f] <= 1):
                    return False
    return True


def ov(r):
    bs = [m["box"] for ln in r["lines"] for m in ln["machines"]] + [ln["inlet"]["box"] for ln in r["lines"] if ln.get("inlet")]
    ls = [ln["box"] for ln in r["lines"]]
    return (sum(hit(bs[i], bs[j]) for i in range(len(bs)) for j in range(i + 1, len(bs)))
            + sum(hit(ls[i], ls[j]) for i in range(len(ls)) for j in range(i + 1, len(ls))))


out = {"A1": [], "A2": [], "A3": []}
bad = 0
for params in ({}, {"width": "1400"}, {"width": "360"}, {"width": "4000"}, {"width": "1400", "since": "all"},
               {"width": "360", "since": "all"}, {"width": "4000", "since": "all"}):
    for attempt in range(3):          # API now 는 마이크로초 — 초 경계에 걸리면 다시
        r = c.get("/api/v1/twin", params=params)
        j = r.json()
        b = twin.build(con, now=dt(j["generated_at"] + "Z"), since=params.get("since"),
                       width=int(params.get("width", 1400)))
        same = strip(j) == strip(b) and ago_close(j, b)
        if same:
            break
    o = ov(j)
    bad += (r.status_code != 200) or not same or o != 0
    out["A1"].append({"params": params, "status": r.status_code, "grid": j["grid"], "same_as_build": same, "overlaps": o,
                      "lines": len(j["lines"])})
d = strip(c.get("/api/v1/twin").json())
e = strip(c.get("/api/v1/twin", params={"width": "1400"}).json())
d.pop("generated_at"), e.pop("generated_at")
out["A1_default_eq_1400"] = d["grid"] == e["grid"] and [ln["box"] for ln in d["lines"]] == [ln["box"] for ln in e["lines"]]
bad += not out["A1_default_eq_1400"]
for w in ("0", "-1", "abc", "1.5", "", " ", "1e3", "1400px", "100001", "99999999", "0x10", "+5"):
    r = c.get("/api/v1/twin", params={"width": w})
    err = r.json().get("error", "") if r.status_code == 422 else ""
    ok = r.status_code == 422 and "width" in err
    bad += not ok
    out["A2"].append({"width": repr(w), "status": r.status_code, "error_has_width": "width" in err, "error_len": len(err), "ok": ok})
for w in ("1", "100000", " 1400"):
    r = c.get("/api/v1/twin", params={"width": w})
    ok = r.status_code == 200
    bad += not ok
    out["A2"].append({"width": repr(w), "status": r.status_code, "cols": r.json().get("grid", {}).get("cols"), "ok": ok})
for p in ("SongWol QR", "Platform"):
    for attempt in range(3):
        j = c.get("/api/v1/twin", params={"project": p, "since": "all"}).json()
        b = twin.build(con, now=dt(j["generated_at"] + "Z"), since="all", project=p)
        if strip(j) == strip(b):
            break
    same = strip(j) == strip(b) and ago_close(j, b)
    bad += not same
    out["A3"].append({"project": p, "scope": j["agents_in_scope"], "lines": len(j["lines"]), "same_as_build": same})
out["fail"] = bad
print(json.dumps(out, ensure_ascii=False, indent=0))
sys.exit(1 if bad else 0)
