#!/usr/bin/env python
"""G-19 check_pipeline (V-11) — 회사 × 단계 칸마다 근거(src)가 있고, 표본 10 칸의 have/need 가 독립 재계산과 같은가.

    uv run python src/agentdash/tools/check_pipeline.py [--db 경로] [--seed 11]

  1. core.pipeline.refresh 로 실제 에이전트 폴더(settings.agents_root, **읽기만**)를 판정해 pipeline_cell 에 저장한다(DB 에만 쓴다).
  2. DB 의 pipeline_cell 전 칸에 src 가 있는지 센다 (근거 없는 칸 0 이어야 PASS).
  3. 표본 10 칸(고려솔더 01 · 02 고정 + 시드 무작위 8)을 **도구와 독립된 방법** — 이 파일에 손으로 적은 산출물 목록과
     `find` 명령(-name / -path, 제외 폴더 -not -path) — 으로 다시 세서 DB 의 have/need 와 대조한다.
     macOS 파일 이름은 한글이 NFD 로 올 수 있어 -name 패턴을 NFC · NFD 두 벌로 준다.
  4. 고려솔더 기대값(spec §13-7): 01 · 02 = DONE v1.0 · 실행 20261016-151506-all · 20261016-154028-all, 05 · 08 = UNKNOWN.
출력: `G-19  항목  PASS|FAIL  실측` 행.
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

EXCLUDE = ["*/_구판_*", "*/_preview*", "*/scratch/*", "*/tour/*"]
# 독립 대조용 — spec.md §7.1 단계 사전 표를 손으로 옮긴 것 (core/pipeline · config/pipeline.yaml 을 읽지 않는다).
# (폴더, 찾을 하위 경로 -path, -name 패턴 목록) — {c} = 회사 표기, 산출물 하나에 패턴 여럿이면 하나라도 있으면 있음.
LABELS = ["제조AI", "스마트공장"]
QA = ["단위테스트결과서", "통합테스트결과서", "시스템전환결과서", "메뉴얼", "사용자테스트결과서", "운영지원계획서", "운영현황보고서"]
SPEC: dict[str, tuple[str, list[tuple[str, list[str]]]]] = {
    "01": ("01 Analyze Agent", [("*/outputs/*-all/*", [f"*SF-AD{n}_*_{{c}}_v*.docx"]) for n in (1, 2, 3)]),
    "02": ("02 Design Agent", [("*/outputs/*-all/*", [f"*SF-TD{n}_*_{{c}}_v*.docx"]) for n in range(1, 6)]),
    "03": ("03 UI Agent", [("*/outputs/*", [f"{{c}}_{lb}_화면설명서*_v*.html" for lb in LABELS]),
                           ("*/outputs/*", [f"{{c}}_{lb}_화면정의서*_v*.pptx" for lb in LABELS]),
                           ("*/outputs/*", [f"{{c}}_{lb}_화면설명서_영상*_v*.mp4" for lb in LABELS])]),
    "04": ("04 QA Agent", [("*/outputs/*", [f"{{c}}_{lb}_{d}_v*.docx" for lb in LABELS]) for d in QA]),
    "00": ("00 PM Agent", [("*/outputs/*-midterm/*", ["*중간보고서_{c}_v*.docx"])]
           + [("*/outputs/pm-{c}/*", [f"*SF-PM{n}_*_{{c}}_v*.docx"]) for n in (1, 2, 3, 4)]),
}
MAXDEPTH = {"01": 3, "02": 3, "03": 2, "04": 2, "00": 3}


def variants(company: str) -> list[str]:
    import yaml

    raw = yaml.safe_load((ROOT / "config" / "companies.yaml").read_text(encoding="utf-8"))
    for c in raw["companies"]:
        if c["name"] == company:
            return [c["name"], *(c.get("aliases") or [])]
    return [company]


def find_count(root: Path, stage: str, company: str) -> tuple[int, int, list[str]]:
    folder, items = SPEC[stage]
    base = root / folder
    have, hits_all = 0, []
    names = variants(company)
    for path_pat, name_pats in items:
        hit = []
        for nm in names:
            for np_ in name_pats:
                pats = {unicodedata.normalize(f, np_.replace("{c}", nm)) for f in ("NFC", "NFD")}
                ppats = {unicodedata.normalize(f, path_pat.replace("{c}", nm)) for f in ("NFC", "NFD")}
                for pp in ppats:
                    for p in pats:
                        cmd = ["find", str(base), "-maxdepth", str(MAXDEPTH[stage]), "-type", "f", "-path", pp, "-name", p]
                        for ex in EXCLUDE:
                            cmd += ["-not", "-path", ex]
                        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
                        hit += [ln for ln in out.splitlines() if ln]
        if hit:
            have += 1
            hits_all += hit
    return have, len(items), hits_all


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    from agentdash import settings
    from agentdash.core import pipeline as P
    from agentdash.db import conn

    s = settings.get()
    root = s.agents_root
    con = conn.connect(conn.init_db(a.db))
    try:
        res = P.refresh(con)
        con.commit()
        rows = con.execute("SELECT company, stage, status, rule, have, need, version, run_id, src FROM pipeline_cell").fetchall()
    finally:
        con.close()
    n = len(rows)
    nosrc = [f"{r[0]}/{r[1]}" for r in rows if not (r[8] or "").strip()]
    exp_cells = len(res.companies) * len(res.stages)
    ok = n == exp_cells and not nosrc
    print(f"G-19  진척 근거 (V-11)  {'PASS' if ok else 'FAIL'}  칸 {n}/{exp_cells} · 근거(src) 없는 칸 {len(nosrc)}"
          + (f" ({', '.join(nosrc[:5])})" if nosrc else "") + f" · 원천 {root.name}/ 읽기만")

    by = {(r[0], r[1]): r for r in rows}
    rule_cells = [k for k in by if k[1] in SPEC]
    rng = random.Random(a.seed)
    sample = [("고려솔더", "01"), ("고려솔더", "02")]
    rest = sorted(set(rule_cells) - set(sample))
    sample += rng.sample(rest, min(8, len(rest)))
    bad = []
    for co, st in sample:
        have, need, _ = find_count(root, st, co)
        r = by[(co, st)]
        if (have, need) != (r[4], r[5]):
            bad.append(f"{co}/{st} find {have}/{need} ≠ DB {r[4]}/{r[5]}")
    desc = " · ".join(f"{co}/{st} {by[(co, st)][4]}/{by[(co, st)][5]}" for co, st in sample)
    print(f"G-19  표본 have/need 대조 (find)  {'PASS' if not bad and len(sample) == 10 else 'FAIL'}  "
          f"표본 {len(sample)} 일치 {len(sample) - len(bad)}" + (f" — 불일치 {'; '.join(bad)}" if bad else "") + f" · {desc}"[:300])

    exp = {("고려솔더", "01"): ("DONE", "v1.0", "20261016-151506-all"),
           ("고려솔더", "02"): ("DONE", "v1.0", "20261016-154028-all")}
    miss = []
    for k, (stt, ver, run) in exp.items():
        r = by.get(k)
        got = (r[2], r[6], r[7]) if r else None
        if got != (stt, ver, run):
            miss.append(f"{k[1]} {got}")
    for st in ("05", "08"):
        r = by.get(("고려솔더", st))
        if not r or r[2] != "UNKNOWN":
            miss.append(f"{st} {r[2] if r else None}")
    print(f"G-19  고려솔더 기대값  {'PASS' if not miss else 'FAIL'}  "
          + ("01 DONE v1.0 20261016-151506-all · 02 DONE v1.0 20261016-154028-all · 05 · 08 UNKNOWN" if not miss
             else "어긋남 " + "; ".join(miss)))
    d = res.as_dict()
    print("# 참고 분포 " + " · ".join(f"{k} {v}" for k, v in d["counts"].items() if v)
          + f" · 미등록 회사 {d['unregistered']} {d['unregistered_names']} · UNKNOWN 칸 {d['unknown_cells']}")
    return 0 if ok and not bad and not miss else 1


if __name__ == "__main__":
    raise SystemExit(main())
