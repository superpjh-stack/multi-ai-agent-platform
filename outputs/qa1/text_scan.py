#!/usr/bin/env python
"""QA1 — DB 의 모든 TEXT 값 길이 분포 · 상위 N · 본문 의심 패턴 (G-13 · V-04). 값은 출력하지 않는다 (--peek 은 QA 눈으로만).
    .venv/bin/python -I outputs/qa1/text_scan.py --db data/agentdash-qa1.db [--top 20] [--peek]
"""
import argparse, re, sqlite3
from collections import Counter
ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--top", type=int, default=20)
ap.add_argument("--peek", action="store_true"); a = ap.parse_args()
con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
allv = []
over = Counter(); cols = 0; rows = 0; vals = 0
mx = {}
SUS = {"개행 포함": re.compile(r"\n"), "코드/명령 꼴": re.compile(r"(\$\(|&&|\|\s*\w+|;\s*\w+\s*=|def |import |SELECT |curl )"),
       "프롬프트 꼴(지시문)": re.compile(r"(너는 |You are |다음을 |작업 폴더|읽는다\.)"), "키·토큰 꼴": re.compile(r"(sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|password\s*[:=])", re.I)}
sus = Counter(); sus_where = Counter()
for t in tabs:
    info = con.execute(f"PRAGMA table_info({t})").fetchall()
    rows += con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    for _, c, typ, *_ in info:
        cols += 1
        for (v,) in con.execute(f"SELECT {c} FROM {t} WHERE typeof({c})='text'"):
            vals += 1
            L = len(v)
            if L > 300:
                over[f"{t}.{c}"] += 1
            if L > mx.get(f"{t}.{c}", 0):
                mx[f"{t}.{c}"] = L
            allv.append((L, t, c, v))
            for name, rx in SUS.items():
                if rx.search(v):
                    sus[name] += 1; sus_where[(name, f"{t}.{c}")] += 1
print(f"테이블 {len(tabs)} · 열 {cols} · 행 {rows} · TEXT 값 {vals} · 300 자 초과 {sum(over.values())} {dict(over) or ''}")
print("열별 최대 길이:", {k: v for k, v in sorted(mx.items(), key=lambda x: -x[1]) if v >= 60})
allv.sort(key=lambda x: -x[0])
print(f"상위 {a.top}:")
for L, t, c, v in allv[:a.top]:
    print(f"  {L:4d} {t}.{c}" + (f"  | {v[:90]!r}" if a.peek else ""))
print("의심 패턴 (값 수):", dict(sus))
for (n, w), k in sorted(sus_where.items(), key=lambda x: -x[1]):
    print(f"  {n} @ {w}: {k}")
