#!/usr/bin/env python
"""QA1 진척 칸 독립 대조 (G-19 · V-11 · D-15). agentdash 코드를 import 하지 않는다.

    .venv/bin/python -I outputs/qa1/pipe_check.py --db data/agentdash-qa1.db [--seed 5]

원천(~/Desktop/AI Coding/<NN> * Agent/outputs)은 `find` 로 이름 · mtime 만 읽는다. run.json 은 `started` 와
회사 키(company · company_name · facts) 값 안의 회사 이름 '있음/없음' 만 본다. progress.md 는 줄 번호만 출력한다.
기대값 규칙 = spec §7.1 표 + decisions D-15(사업 칸 2 종 · NFC · 산출물별 항목) — 개발 코드가 아니라 문서에서.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
ROOT = Path(os.path.expanduser("~/Desktop/AI Coding"))
COMP = {"경동글로벌텍": ["경동"], "고려솔더": ["주식회사 고려솔더"], "광성정밀": ["광성"], "니즈푸드": ["니즈"],
        "브랜뉴머시너리": ["브랜뉴"], "송월타월서울상사": ["송월타월 서울상사", "송월타월", "송월"], "엘컴화인": ["lcomFine"],
        "와이엔프린팅": [], "원터치": ["OneTouch"], "임진강김치": ["임진강"], "평창꽃순이김치": ["평창"]}
BIZ = ["제조AI", "스마트공장"]
EXCL = re.compile(r"(^|/)(_구판_[^/]*|_preview[^/]*|scratch|tour)(/|$)")
STAGE = {"01": "01 Analyze Agent", "02": "02 Design Agent", "03": "03 UI Agent", "04": "04 QA Agent", "00": "00 PM Agent"}
DOCS04 = ["단위테스트결과서", "통합테스트결과서", "시스템전환결과서", "메뉴얼", "사용자테스트결과서", "운영지원계획서", "운영현황보고서"]


def nfc(s):
    return unicodedata.normalize("NFC", s)


def norm(s):
    s = nfc(s)
    for t in (" ", "주식회사", "(주)"):
        s = s.replace(t, "")
    return s


LOOK = {}
for std, al in COMP.items():
    for v in [std, *al]:
        LOOK[norm(v)] = std


def find_files(stage):
    base = ROOT / STAGE[stage] / "outputs"
    out = subprocess.run(["find", str(base), "-type", "f", "-print0"], capture_output=True, check=True).stdout
    res = []
    for p in out.split(b"\0"):
        if not p:
            continue
        s = p.decode("utf-8")
        rel = s[len(str(base)) + 1:]
        res.append((rel, os.stat(s).st_mtime, s))
    return res


def ver(name):
    m = re.search(r"_v(\d+(?:\.\d+)*)\.[^./]+$", name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def run_started(run_dir: Path):
    p = run_dir / "run.json"
    if p.is_file():
        try:
            s = json.loads(p.read_bytes()).get("started")
            if isinstance(s, str):
                return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp()
        except Exception:
            pass
    m = re.match(r"(\d{8}-\d{6})", run_dir.name)
    return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=KST).timestamp() if m else None


def run_company(run_dir: Path, files_in_run):
    p = run_dir / "run.json"
    if p.is_file():
        try:
            d = json.loads(p.read_bytes())
        except Exception:
            d = {}
        for k in ("company", "company_name", "facts"):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, str):
                hit = {std for n, std in LOOK.items() if n in norm(v)}
                if len(hit) == 1:
                    return hit.pop(), f"run.json:{k}"
    c = Counter(files_in_run)
    return (c.most_common(1)[0][0], "파일명") if c else (None, None)


def scan(stage, nfc_on=True, biz=BIZ):
    N = nfc if nfc_on else (lambda s: s)
    lk = (lambda x: LOOK.get(norm(x))) if nfc_on else (lambda x: LOOK.get(x.replace(" ", "").replace("주식회사", "").replace("(주)", "")))
    files = find_files(stage)
    have = defaultdict(dict)       # co -> item -> (ver, run, mtime, rel)
    slots = Counter()              # {회사} 자리 값 (미등록 사냥)
    runs = defaultdict(list)
    bz = "(?:" + "|".join(biz) + ")"
    if stage in ("01", "02"):
        code = "AD" if stage == "01" else "TD"
        n = 3 if stage == "01" else 5
        rx = re.compile(rf"^(?P<run>\d{{8}}-\d{{6}}-all)/[^/]*SF-{code}(?P<i>[1-{n}])_[^/]*_(?P<co>[^_/]+)_v[^/]*\.docx$")
        per_run = defaultdict(list)
        hits = []
        for rel, mt, _ in files:
            r = N(rel)
            if EXCL.search(r):
                continue
            m = rx.match(r)
            if m:
                slots[m["co"]] += 1
                std = lk(m["co"])
                if std:
                    per_run[m["run"]].append(std)
                    hits.append((m["run"], f"SF-{code}{m['i']}", std, ver(r), mt, r))
        rc = {}
        for run, cos in per_run.items():
            rc[run] = run_company(ROOT / STAGE[stage] / "outputs" / run, cos)[0]
            t = run_started(ROOT / STAGE[stage] / "outputs" / run)
            if rc[run]:
                runs[rc[run]].append((t, run))
        for run, item, std, v, mt, r in hits:
            if rc.get(run) != std:
                continue
            k = (v, run, mt)
            if item not in have[std] or k > have[std][item][:3]:
                have[std][item] = (v, run, mt, r)
    elif stage in ("03", "04"):
        if stage == "03":
            items = [("화면설명서", rf"화면설명서[^/]*_v[^/]*\.html"), ("화면정의서", rf"화면정의서[^/]*_v[^/]*\.pptx"),
                     ("영상", rf"화면설명서_영상[^/]*_v[^/]*\.mp4")]
        else:
            items = [(d, rf"{d}_v[^/]*\.docx") for d in DOCS04]
        for rel, mt, _ in files:
            r = N(rel)
            if "/" in r or EXCL.search(r):
                continue
            for item, tail in items:
                m = re.match(rf"^(?P<co>[^_/]+)_{bz}_{tail}$", r)
                if m:
                    slots[m["co"]] += 1
                    std = lk(m["co"])
                    if std:
                        k = (ver(r), "", mt)
                        if item not in have[std] or k > have[std][item][:3]:
                            have[std][item] = (ver(r), "", mt, r)
    else:  # 00
        rx_mid = re.compile(r"^(?P<run>\d{8}-\d{6}-midterm)/[^/]*중간보고서_(?P<co>[^_/]+)_v[^/]*\.docx$")
        rx_pm = re.compile(r"^pm-(?P<dir>[^_/]+)/[^/]*SF-PM(?P<i>[1-4])_[^/]*_(?P<co>[^_/]+)_v[^/]*\.docx$")
        mids = defaultdict(list)
        for rel, mt, _ in files:
            r = N(rel)
            if EXCL.search(r):
                continue
            m = rx_mid.match(r)
            if m:
                slots[m["co"]] += 1
                std = lk(m["co"])
                if std:
                    mids[m["run"]].append((std, ver(r), mt, r))
            m = rx_pm.match(r)
            if m:
                slots[m["co"]] += 1
                sd, sc = lk(m["dir"]), lk(m["co"])
                if sd and sd == sc:
                    k = (ver(r), "", mt)
                    it = f"SF-PM{m['i']}"
                    if it not in have[sd] or k > have[sd][it][:3]:
                        have[sd][it] = (ver(r), "", mt, r)
        for run, lst in mids.items():
            rc = run_company(ROOT / STAGE["00"] / "outputs" / run, [x[0] for x in lst])[0]
            for std, v, mt, r in lst:
                if std == rc:
                    k = (v, run, mt)
                    if "중간보고서" not in have[std] or k > have[std]["중간보고서"][:3]:
                        have[std]["중간보고서"] = (v, run, mt, r)
    return have, slots, runs, files


NEED = {"01": 3, "02": 5, "03": 3, "04": 7, "00": 5}


def progress_lines(stage):
    """`## 지금 해야 할 것` 절 안 표제 · 표 행 중 회사 + 판단 키워드 줄 번호 (내용 출력 없음)."""
    p = ROOT / STAGE[stage] / "progress.md"
    out = defaultdict(list)
    if not p.is_file():
        return out
    inside = False
    for no, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.startswith("## "):
            inside = line.strip() == "## 지금 해야 할 것"
        if not inside or not (line.startswith("## ") or line.startswith("### ") or line.lstrip().startswith("|")):
            continue
        if any(k in line for k in ("판단 필요", "사용자 판단", "확인 필요")):
            for n, std in LOOK.items():
                if n in norm(line):
                    out[std].append(no)
    return {k: sorted(set(v)) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    db = {(r[0], r[1]): r[2:] for r in con.execute(
        "SELECT company, stage, status, rule, have, need, version, run_id, last_file_at, note, src FROM pipeline_cell")}
    print(f"## DB pipeline_cell {len(db)} 칸 · src 빈 칸 {sum(1 for v in db.values() if not v[8])}")
    exp = {}
    unreg = Counter()
    nfd_names = 0
    allruns = {}
    for st in STAGE:
        have, slots, runs, files = scan(st)
        allruns[st] = runs
        nfd_names += sum(1 for rel, _, _ in files if nfc(rel) != rel)
        for s, n in slots.items():
            if LOOK.get(norm(s)) is None:
                unreg[s] += n
        for co in COMP:
            h = have.get(co, {})
            exp[(co, st)] = (len(h), NEED[st], max((x[0] for x in h.values()), default=()),
                             max((x[1] for x in h.values() if x[1]), default=None), max((x[2] for x in h.values()), default=None))
        # D-15 효과: NFC 끔 / 사업 칸 제조AI 만
        if st in ("00", "03", "04"):
            h2, *_ = scan(st, nfc_on=False)
            h3, *_ = scan(st, biz=["제조AI"])
            diff2 = {co: len(h2.get(co, {})) for co in COMP if len(h2.get(co, {})) != len(have.get(co, {}))}
            diff3 = {co: len(h3.get(co, {})) for co in COMP if len(h3.get(co, {})) != len(have.get(co, {}))}
            print(f"  D-15 {st}: NFC 없이 세면 달라지는 회사 {diff2 or 0} · 사업=제조AI 만이면 {diff3 or 0}")
    print(f"  NFD 로 저장된 파일 경로 (5 단계 outputs) {nfd_names}")
    print(f"  패턴 {{회사}} 자리의 사전 밖 이름: {dict(unreg) or 0}")

    bad = []
    for (co, st), (h, n, v, run, mt) in exp.items():
        d = db.get((co, st))
        vs = ("v" + ".".join(map(str, v))) if v else None
        lfa = datetime.fromtimestamp(mt, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt else None
        if d is None or (d[2], d[3], d[4], d[5], d[6]) != (h, n, vs, run, lfa):
            bad.append((co, st, (h, n, vs, run, lfa), d and (d[2], d[3], d[4], d[5], d[6])))
    print(f"\n## 55 칸 (01 · 02 · 03 · 04 · 00) have/need · 버전 · 실행 · 마지막 파일 시각 — 불일치 {len(bad)}")
    for b in bad[:20]:
        print("   ", b)
    rng = random.Random(a.seed)
    sample = rng.sample(sorted(exp), 10)
    print(f"\n## 무작위 10 칸 (시드 {a.seed})")
    for co, st in sample:
        e = exp[(co, st)]
        d = db[(co, st)]
        print(f"  {co} {st}: find {e[0]}/{e[1]} · DB {d[2]}/{d[3]} {d[0]} {d[1]} → {'일치' if (e[0], e[1]) == (d[2], d[3]) else '불일치'}")

    # NEEDS_DECISION
    print("\n## P-01 (판단 필요) — 각 단계 progress.md `## 지금 해야 할 것` 절")
    for st, folder in list(STAGE.items()) + [("06", "06 Coding Agent")]:
        if st == "06":
            continue
        pl = progress_lines(st)
        dbn = sorted(co for (co, s), v in db.items() if s == st and v[0] == "NEEDS_DECISION")
        print(f"  {st}: 독립 {dict(pl) or 0} · DB NEEDS_DECISION {dbn or 0}")
    # 뒤처짐
    print("\n## ↻ 뒤처짐 독립 계산 (02←01 · 03←02 · 04←03 · 00←01·02)")
    UP = {"02": ["01"], "03": ["02"], "04": ["03"], "00": ["01", "02"]}
    lag_exp = set()
    for (co, st), e in exp.items():
        if st not in UP or e[4] is None:
            continue
        for u in UP[st]:
            if u in ("01", "02"):
                rs = allruns[u].get(co) or []
                t = max((x[0] for x in rs if x[0]), default=None)
            else:
                t = exp[(co, u)][4]
            if t and t > e[4]:
                lag_exp.add((co, st))
                break
    lag_db = {(co, st) for (co, st), v in db.items() if v[7] and "↻" in v[7]}
    print(f"  독립 ↻ {len(lag_exp)} · DB ↻ {len(lag_db)} · 독립만 {sorted(lag_exp - lag_db) or 0} · DB만 {sorted(lag_db - lag_exp) or 0}")
    for co, st in sorted(lag_exp)[:20]:
        print(f"    ↻ {co} {st}")
    k = {(co, st): v for (co, st), v in db.items() if co == "고려솔더"}
    print(f"\n## 고려솔더 기대: 01 {k[('고려솔더','01')][:2]} {k[('고려솔더','01')][4:6]} · 02 {k[('고려솔더','02')][:2]} {k[('고려솔더','02')][4:6]}"
          f" · 05 {k[('고려솔더','05')][:2]} · 08 {k[('고려솔더','08')][:2]}")
    other = Counter((v[0], st) for (co, st), v in db.items() if st in ("05", "06", "08"))
    print(f"  05 · 06 · 08 열: {dict(other)}")


if __name__ == "__main__":
    sys.exit(main())
