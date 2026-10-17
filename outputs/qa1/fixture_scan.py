#!/usr/bin/env python
"""QA1 — 픽스처 본문 누출 독립 사냥 (G-13 픽스처 쪽). 키별로 '<redacted> 아닌 문자열' 수 · 최대 길이. --peek 은 QA 눈으로만.
    .venv/bin/python -I outputs/qa1/fixture_scan.py [--peek KEY]"""
import json, sys
from collections import defaultdict
from pathlib import Path
root = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
peek = sys.argv[sys.argv.index("--peek") + 1] if "--peek" in sys.argv else None
st = defaultdict(lambda: [0, 0, 0])   # key -> [n non-redacted, max len, n redacted]
files = 0; lines = 0; nonjson = 0
def walk(o, k):
    if isinstance(o, dict):
        for kk, v in o.items(): walk(v, kk)
    elif isinstance(o, list):
        for x in o: walk(x, k)
    elif isinstance(o, str):
        s = st[k]
        if o == "<redacted>": s[2] += 1
        else:
            s[0] += 1; s[1] = max(s[1], len(o))
            if peek and k == peek and len(o) > 20: print("   PEEK", k, len(o), repr(o[:70]))
for p in sorted(root.rglob("*")):
    if not p.is_file(): continue
    files += 1
    if p.suffix == ".md": continue
    txt = p.read_text(encoding="utf-8")
    chunks = txt.splitlines() if p.suffix == ".jsonl" else [txt]
    for c in chunks:
        if not c.strip(): continue
        lines += 1
        try: walk(json.loads(c), None)
        except ValueError: nonjson += 1
print(f"파일 {files} · JSON 단위 {lines} · JSON 아님 {nonjson}")
for k, (n, mx, r) in sorted(st.items(), key=lambda x: -x[1][1]):
    if n and mx >= 30:
        print(f"  {str(k):28s} 원문 {n:5d} · 최대 {mx:4d} 자 · redacted {r}")
