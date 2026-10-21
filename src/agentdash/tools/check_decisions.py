#!/usr/bin/env python
"""G-23 check_decisions — 결정 반영 (goal.md §2.2 · problem.md G16).

    uv run python src/agentdash/tools/check_decisions.py

판정
  1. decisions.md 의 D-07 · D-08 · D-13 · D-14 · D-17 · D-18 · D-19 `상태:` 줄이 `확정` 으로 시작한다
     (D-08 만 `차단` 허용 — 근거 날짜가 있을 때).
  2. D-08 본문에 대조 출처(`config/pricing.yaml` 의 `source_url`)와 날짜(YYYY-MM-DD)가 있다.
  3. `src/` (py · html) 에 `가설 D-18` · `D18_NOTE` 가 0 곳.
출력: `G-23  결정 반영  PASS|FAIL  실측`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = ("D-07", "D-08", "D-13", "D-14", "D-17", "D-18", "D-19")
LEFTOVER = ("가설 D-18", "D18_NOTE")
SELF = Path(__file__).resolve()
DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def sections(text: str) -> dict[str, str]:
    """`## D-nn …` 머리마다 본문(다음 `## ` 앞까지)."""
    out: dict[str, str] = {}
    parts = re.split(r"^(?=## D-\d\d )", text, flags=re.M)
    for part in parts:
        m = re.match(r"## (D-\d\d) ", part)
        if m:
            out[m.group(1)] = part.split("\n## ", 1)[0]
    return out


def status_of(body: str) -> str | None:
    m = re.search(r"^- 상태:\s*(\S+)", body, re.M)
    return m.group(1) if m else None


def evaluate(decisions_text: str, src_files: dict[str, str], source_url: str) -> tuple[bool, list[str], str]:
    """(통과?, 문제 목록, 실측 요약)."""
    secs = sections(decisions_text)
    problems: list[str] = []
    confirmed = 0
    for d in REQUIRED:
        body = secs.get(d)
        if body is None:
            problems.append(f"{d} 없음")
            continue
        st = status_of(body)
        if st == "확정":
            confirmed += 1
        elif d == "D-08" and st == "차단" and DATE.search(body):
            confirmed += 1                                   # 근거 날짜 있는 차단만 허용 (goal.md §1-5)
        else:
            problems.append(f"{d} 상태 {st}")
    d08 = secs.get("D-08", "")
    has_src = bool(source_url) and source_url in d08
    has_date = bool(DATE.search(d08))
    if not (has_src and has_date):
        problems.append(f"D-08 대조 출처 {'있음' if has_src else '없음'} · 날짜 {'있음' if has_date else '없음'}")
    hits = []
    for rel, text in src_files.items():
        for i, line in enumerate(text.splitlines(), 1):
            for w in LEFTOVER:
                if w in line:
                    hits.append(f"{rel}:{i} {w}")
    if hits:
        problems.append(f"src/ 남은 표시 {len(hits)} 곳 ({'; '.join(hits[:3])})")
    summary = (f"확정 {confirmed}/{len(REQUIRED)} · D-08 출처 {'있음' if has_src else '없음'} · "
               f"src/ 「가설 D-18」·D18_NOTE {len(hits)} 곳")
    if problems:
        summary += " — " + " · ".join(p for p in problems if not p.startswith("src/"))
        summary = summary.rstrip(" —")
    return (not problems), problems, summary


def main() -> int:
    text = (ROOT / "decisions.md").read_text(encoding="utf-8")
    url = yaml.safe_load((ROOT / "config" / "pricing.yaml").read_text(encoding="utf-8")).get("source_url", "")
    files = {}
    for p in sorted((ROOT / "src").rglob("*")):
        if p.suffix in (".py", ".html") and p.resolve() != SELF and "__pycache__" not in p.parts:
            files[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
    ok, problems, summary = evaluate(text, files, url)
    print(f"G-23  결정 반영  {'PASS' if ok else 'FAIL'}  {summary}")
    for p in problems:
        print(f"  - {p}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
