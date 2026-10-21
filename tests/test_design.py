"""G-30 디자인 — base.html 토큰 · 두 테마 대비 (spec.md v0.3 §7.3 · V-16). 소유 아키텍트."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "agentdash" / "app" / "templates"
sys.path.insert(0, str(ROOT / "src" / "agentdash" / "tools"))

import check_contrast as cc  # noqa: E402

STATES = ["RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "SLEEPING", "WAITING_CHILD", "DONE", "FAILED", "STALE"]
BASE = ["--bg", "--surface", "--fg", "--muted", "--line", "--accent"]


def _base():
    return (TEMPLATES / "base.html").read_text(encoding="utf-8")


def test_contrast_both_themes():
    """두 테마 각각: 상태 글자색(`--st-*-fg`) 대 `--bg` · `--surface` ≥ 4.5 (8 × 2 = 16 쌍), 상태 도형색 대 `--bg` ≥ 3.0."""
    res = cc.measure(_base())
    assert set(res) == {"light", "dark"}
    for theme, pairs in res.items():
        text = [p for p in pairs if p.kind == "text"]
        shape = [p for p in pairs if p.kind == "shape"]
        assert len(text) == 16 and len(shape) == 8, theme
        bad = [f"{p.fg}/{p.bg} {p.ratio:.2f}" for p in pairs if p.ratio < p.need]
        assert not bad, (theme, bad)


def test_theme_tokens_defined():
    """밝은(:root) · 다크(:root[data-theme=dark]) · 시스템 다크(@media … :root:not([data-theme=light])) 가 같은 토큰 집합 ·
    시스템 다크 = 선택 다크 값."""
    t = cc.themes(_base())
    assert set(t) == {"light", "dark", "dark_media"}
    want = set(BASE) | {cc.state_token(s) for s in STATES} | {cc.state_token(s) + "-fg" for s in STATES}
    for name, toks in t.items():
        assert want <= set(toks), (name, sorted(want - set(toks)))
    assert set(t["light"]) == set(t["dark"]) == set(t["dark_media"])
    assert t["dark"] == t["dark_media"]


def test_common_classes_and_header():
    """공통 부품 클래스 · 머리글 테마 토글 · 알림 버튼 자리 · nav D-07 · _alerts include (계획 Task 4)."""
    s = _base()
    for cls in (".card", ".grid", ".kpi", ".tbl", ".badge", ".chart"):
        assert re.search(re.escape(cls) + r"\b", s), cls
    for st in STATES:
        assert f".st-{st}" in s, st
    assert 'id="theme-btn"' in s and 'id="alerts-btn"' in s
    assert '"/insights"' in s and "D-07 비용 · 효율" in s
    assert '{% include "_alerts.html" ignore missing %}' in s


def test_ratio_formula():
    """WCAG 2.x 상대 휘도 대비 — 흑/백 21:1, 같은 색 1:1."""
    assert round(cc.ratio("#000000", "#ffffff"), 2) == 21.0
    assert cc.ratio("#777777", "#777777") == 1.0


def test_no_dev_style_includes():
    """spec §7.3 — 화면별 스타일 조각을 따로 두지 않는다: 템플릿에 `_dev1_style` · `_dev2_style` include 0."""
    hits = [p.name for p in TEMPLATES.glob("*.html")
            if re.search(r"include\s+[\"']_dev[12]_style", p.read_text(encoding="utf-8"))]
    assert hits == []
