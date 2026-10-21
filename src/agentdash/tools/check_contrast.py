#!/usr/bin/env python
"""V-16 check_contrast — 두 테마 토큰의 상태 색 대비 (G-30 · spec.md v0.3 §7.3).

    uv run python src/agentdash/tools/check_contrast.py [base.html 경로]

base.html 의 `<style>` 에서 세 블록의 CSS 변수를 읽는다.
  · light      = `:root { … }`
  · dark       = `:root[data-theme="dark"] { … }`            (머리글 토글로 고른 다크)
  · dark_media = `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }`  (시스템 다크 — dark 와 같아야 한다)
판정 (light · dark 각각, WCAG 2.x 상대 휘도 대비)
  · 상태 8 의 글자색 `--st-<state>-fg` 대 `--bg` · `--surface` ≥ 4.5 (16 쌍)
  · 상태 8 의 도형색 `--st-<state>` 대 `--bg` ≥ 3.0 (8 쌍)
  · dark_media 토큰 = dark 토큰
색 값은 `#rgb` · `#rrggbb` 만 읽는다 (그 밖의 꼴은 FAIL — 조용히 넘기지 않는다).
출력: `G-30  디자인 대비  PASS|FAIL  최소 n.n:1 (<토큰>)`
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE_HTML = ROOT / "src" / "agentdash" / "app" / "templates" / "base.html"
STATES = ("RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "SLEEPING", "WAITING_CHILD", "DONE", "FAILED", "STALE")
TEXT_MIN, SHAPE_MIN = 4.5, 3.0
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass
class Pair:
    theme: str
    kind: str          # text | shape
    fg: str
    bg: str
    ratio: float
    need: float


def state_token(state: str) -> str:
    """RUNNING → --st-running · WAITING_INPUT → --st-waiting-input."""
    return "--st-" + state.lower().replace("_", "-")


def _vars(body: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;}]+)", body)}


def _block(css: str, selector_re: str) -> str | None:
    """선택자 뒤 `{ … }` 본문 (중괄호 짝 맞춤)."""
    m = re.search(selector_re + r"\s*\{", css)
    if not m:
        return None
    i, depth = m.end(), 1
    start = i
    while i < len(css) and depth:
        depth += css[i] == "{"
        depth -= css[i] == "}"
        i += 1
    return css[start:i - 1]


def themes(html: str) -> dict[str, dict[str, str]]:
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: dict[str, dict[str, str]] = {}
    light = _block(css, r"(?m)^\s*:root(?![\w:\[-])")
    dark = _block(css, r":root\[data-theme=\"dark\"\]")
    media = _block(css, r"@media\s*\(prefers-color-scheme:\s*dark\)")
    if light is not None:
        out["light"] = _vars(light)
    if dark is not None:
        out["dark"] = _vars(dark)
    if media is not None:
        inner = _block(media, r":root:not\(\[data-theme=\"light\"\]\)")
        if inner is not None:
            out["dark_media"] = _vars(inner)
    return out


def _rgb(hexv: str) -> tuple[float, float, float]:
    m = _HEX.match(hexv)
    if not m:
        raise ValueError(f"색 값 꼴을 읽지 못함: {hexv!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(hexv: str) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in _rgb(hexv))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def measure(html: str) -> dict[str, list[Pair]]:
    t = themes(html)
    res: dict[str, list[Pair]] = {}
    for theme in ("light", "dark"):
        toks = t.get(theme)
        if toks is None:
            continue
        pairs = []
        for st in STATES:
            tok = state_token(st)
            for bg in ("--bg", "--surface"):
                pairs.append(Pair(theme, "text", tok + "-fg", bg, ratio(toks[tok + "-fg"], toks[bg]), TEXT_MIN))
            pairs.append(Pair(theme, "shape", tok, "--bg", ratio(toks[tok], toks["--bg"]), SHAPE_MIN))
        res[theme] = pairs
    return res


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else BASE_HTML
    html = path.read_text(encoding="utf-8")
    problems: list[str] = []
    t = themes(html)
    for need in ("light", "dark", "dark_media"):
        if need not in t:
            problems.append(f"테마 블록 없음: {need}")
    if "dark" in t and "dark_media" in t and t["dark"] != t["dark_media"]:
        diff = sorted(k for k in set(t["dark"]) | set(t["dark_media"]) if t["dark"].get(k) != t["dark_media"].get(k))
        problems.append(f"시스템 다크 ≠ 선택 다크: {' '.join(diff[:5])}")
    try:
        res = measure(html)
    except (KeyError, ValueError) as e:
        print(f"G-30  디자인 대비  FAIL  토큰 읽기 실패: {e}")
        return 1
    pairs = [p for ps in res.values() for p in ps]
    for p in pairs:
        if p.ratio < p.need:
            problems.append(f"{p.theme} {p.fg} / {p.bg} = {p.ratio:.2f}:1 < {p.need}")
    if not pairs:
        problems.append("잰 쌍 0")
    worst_t = min((p for p in pairs if p.kind == "text"), key=lambda p: p.ratio, default=None)
    worst_s = min((p for p in pairs if p.kind == "shape"), key=lambda p: p.ratio, default=None)
    detail = (f"글자 최소 {worst_t.ratio:.1f}:1 ({worst_t.theme} {worst_t.fg}/{worst_t.bg}) · "
              f"도형 최소 {worst_s.ratio:.1f}:1 ({worst_s.theme} {worst_s.fg}) · 쌍 {len(pairs)}") if worst_t and worst_s else "쌍 0"
    for p in problems:
        print(f"  위반 {p}")
    print(f"G-30  디자인 대비  {'PASS' if not problems else 'FAIL'}  {detail}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
