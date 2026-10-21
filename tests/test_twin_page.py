"""G-35 · G-34 — D-01 공장 평면도 화면 정적 계약 (spec.md v0.4 §7 D-01 · §7.3 · §7.4). 담당 개발2.

서버는 평면도 틀(SVG · 도구 막대 · 숨김 표)과 패널(v0.3 관제판 항목 전부 + 「선택한 설비」)만 렌더하고,
그림은 `_twin.html` 스크립트가 `/api/v1/twin` 응답 좌표 그대로 그린다(T-07 — 브라우저에서 배치를 다시 계산하지 않는다).
움직임 · 실제 렌더는 브라우저 E2E (progress-dev2.md · QA2 outputs/e2e/twin.md) 몫 — 여기서는 계약 문자열만.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentdash.db import conn
from test_dashboard import _budget_cfg, _spend, seed_d01

TPL = Path(__file__).resolve().parents[1] / "src" / "agentdash" / "app" / "templates"


def src(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


@pytest.fixture
def db():
    con = conn.connect(conn.init_db())
    yield con
    con.close()


def client():
    from agentdash.app.main import app
    return TestClient(app)


def _media_block(css: str, query: str) -> str:
    m = re.search(r"@media\s*\(\s*" + re.escape(query) + r"\s*\)\s*\{", css)
    assert m, query
    i, depth = m.end(), 1
    while depth:
        depth += css[i] == "{"
        depth -= css[i] == "}"
        i += 1
    return css[m.end():i - 1]


def test_d01_has_floor_and_panel(db):
    seed_d01(db)
    t = client().get("/").text
    assert "<title>공장 평면도" in t and "D-01 공장 평면도" in t
    assert 'id="twin-svg"' in t and 'id="twin-table"' in t
    for ctl in ('id="twin-zoom-in"', 'id="twin-zoom-out"', 'id="twin-fit"', 'id="twin-since"', 'id="twin-project"'):
        assert ctl in t, ctl                                                  # 확대 · 축소 · 맞춤 · 필터 (spec D-01)
    # 패널 = v0.3 관제판 항목 전부 (G-34)
    for s in ("RUNNING", "WAITING_INPUT", "WAITING_PERMISSION", "SLEEPING", "WAITING_CHILD", "STALE"):
        assert f'data-state="{s}"' in t, s                                    # 상태별 카드
    assert 'data-state="DONE_TODAY"' in t and "오늘 끝남" in t
    assert "살아 있는 상태 분포" in t
    assert "내 차례" in t and 'class="copy"' in t and 'data-copy="/work/alpha"' in t
    assert "선택한 설비" in t and 'id="twin-sel"' in t and "살아 있는 에이전트" in t
    assert "출력 토큰" in t and "도구 호출" in t and "작성 파일" in t and "상위 5 에이전트" in t
    assert "파싱 오류" in t and 'id="feed"' in t and "최근 상태 변화" in t
    # 평면도 ≈ 70 % · 패널 ≈ 30 % (넓은 화면) · 1000 px 미만이면 평면도 아래
    assert "minmax(0, 7fr) minmax(0, 3fr)" in t and "min-width: 1000px" in t
    assert t.index('id="twin-svg"') < t.index('id="twin-sel"') or 'grid-area' in t
    # 부분 갱신 조각에는 평면도 · 스트림을 싣지 않는다 — 15 초 새로고침이 그림을 지우지 않게
    body = client().get("/?part=body").text
    assert 'id="twin-svg"' not in body and "new EventSource(" not in body and "선택한 설비" in body


def test_budget_band_stays_on_top(db, monkeypatch):
    """예산 띠 자리 — 맨 위 (평면도 · 패널보다 먼저)."""
    from agentdash.core import budget
    monkeypatch.setattr(budget, "load", lambda: _budget_cfg(daily=100))
    _spend(db, 85.0)
    t = client().get("/").text
    assert t.index('id="budget-band"') < t.index('id="twin-svg"')
    assert 'id="budget-band"' in src("_d01_body.html")


def test_empty_db_floor_message():
    conn.init_db()
    t = client().get("/").text
    assert 'id="twin-svg"' in t and "기다리는 세션 없음" in t and "살아 있는 에이전트 없음" in t
    assert "범위 안 에이전트 없음" in src("_twin.html")


def test_reduced_motion_block():
    s = src("_twin.html")
    block = _media_block(s, "prefers-reduced-motion: reduce")
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", block)
    off = [sel for sel, body in rules if re.search(r"animation\s*:\s*none", body)]
    joined = " ".join(off)
    for cls in (".lamp", ".beacon", ".alarm", ".flow", ".burst", ".appear"):
        assert cls in joined, cls
    assert any(re.search(r"transition\s*:\s*none", body) for _sel, body in rules)
    # 스크립트도 움직임을 만들지 않는다 — 1 회 흐름(burst)은 reduced 면 만들지 않음
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in s


def test_animation_contract():
    """spec §7.4 — RUNNING 2 초 맥박 · WAITING 경광등 + ! · STALE 1 초 깜빡임 · DONE/FAILED 흐림 · 숨은 탭 입자 멈춤."""
    s = src("_twin.html")
    assert re.search(r"\.st-RUNNING[^{]*\.lamp[^{]*\{[^}]*animation:[^;}]*\b2s\b", s)
    assert re.search(r"\.beacon[^{]*\{[^}]*animation:", s) and '"!"' in s
    assert re.search(r"\.alarm[^{]*\{[^}]*animation:[^;}]*\b1s\b", s)
    assert re.search(r"\.st-DONE[^{]*\{[^}]*opacity", s) and re.search(r"\.st-FAILED[^{]*\{[^}]*stroke:\s*var\(--st-failed\)", s)
    assert "document.hidden" in s and "visibilitychange" in s and "animation-play-state: paused" in s
    assert "깰" in s                                                             # SLEEPING 깰 시각


def test_tokens_only_no_new_colors():
    for name in ("_twin.html", "dashboard.html", "_d01_body.html"):
        s = src(name)
        assert not re.search(r"(:\s*|[\"'])#[0-9a-fA-F]{3,8}\b", s), name     # hex 색 0
        assert not re.search(r"\b(rgba?|hsla?)\(", s), name                     # 색 함수 0 — 토큰(var(--…))만
    s = src("_twin.html")
    assert "var(--st-" in s or "var(--c)" in s


def test_no_external_script_and_one_eventsource(db):
    seed_d01(db)
    t = client().get("/").text
    assert t.count("<script src") == 0                                          # base.html 은 외부 스크립트 0 — D-01 도 0
    assert t.count("new EventSource(") == 1
    s = src("_twin.html")
    assert "new EventSource" not in s and "openStream(" in s
    assert not re.search(r"https?:|//[a-z0-9.-]+\.[a-z]{2,}", s, re.I)          # 외부 URL 0 (SVG 이름공간도 문자열로 안 씀)
    assert "<script src" not in s and "import(" not in s
    for d in ("alert(", "confirm(", "prompt("):
        assert not re.search(r"(?<![\w.])" + re.escape(d), s), d
    for m in re.finditer(r"\bfetch\(", s):
        assert re.match(r'fetch\(\s*"/api/v1/(twin|agents/)', s[m.start():]), s[m.start():m.start() + 60]


def test_machine_accessibility_contract():
    s = src("_twin.html")
    assert re.search(r'"role",\s*"button"', s) and re.search(r'"tabindex",\s*"0"', s) and '"aria-label"' in s
    assert '"Enter"' in s and "dblclick" in s and '"/agents/"' in s           # 두 번 누르기 · Enter → D-03
    assert 'id="twin-table"' in s or 'id="twin-table"' in src("dashboard.html")
    assert "sr-only" in s
    assert "ctrlKey" in s and "pointerdown" in s and "wheel" in s               # Ctrl+휠 · 끌기


def test_window_api_and_classes():
    s = src("_twin.html")
    assert "window.agentdashTwin" in s
    for k in ("render:", "machineEl:", "redraws:", "flows:"):
        assert k in s, k
    for cls in ('"machine', '"pipe', "data-kind", "data-key", "data-state", "lamp", "beacon", "alarm", "flow"):
        assert cls in s, cls
    assert "onThemeChange(" in s                                                # 테마 바뀜 → 다시 칠함


def test_unknown_key_event_refetches():
    """Review Focus 5 — 평면도에 없는 에이전트의 agent.state 는 오류 없이 다시 받기만."""
    s = src("_twin.html")
    m = re.search(r'"agent\.state"\s*:\s*function[\s\S]{0,400}?machineEl\([\s\S]{0,300}?soon\(\)', s)
    assert m, "agent.state 처리기에 machineEl 없으면 soon() 경로가 없다"
    assert re.search(r'"agent\.new"\s*:', s) and re.search(r'"edge\.new"\s*:', s) and re.search(r'"agent\.usage"\s*:', s)
    assert re.search(r"setTimeout\([^;]*1000\)", s) and re.search(r"setTimeout\([^;]*5000\)", s)   # 1 초 · 5 초 묶음


def test_no_client_side_layout():
    """T-07 — 좌표는 응답의 box 그대로. 배치 상수 · 열/행 계산을 스크립트에 두지 않는다."""
    s = src("_twin.html")
    for c in ("BOX_W", "BOX_H", "GAP_X", "GAP_Y", "LINE_HEAD", "LINE_PAD", "LINE_GAP", "208", "92"):
        assert not re.search(r"\b" + c + r"\b", s), c
    assert ".box.x" in s and ".box.y" in s


def test_grid_width_sent_and_resize_refetch():
    """T-08 (D-30): 평면도 카드 실제 너비를 width 로 보내고, 크기가 바뀌면 1 초 묶음으로 다시 받는다 (격자는 서버가)."""
    s = src("_twin.html")
    assert re.search(r'p\.set\("width",', s)
    assert "wrap.clientWidth" in s
    m = re.search(r"new ResizeObserver\(function \(\) \{[\s\S]{0,600}?\}\)\.observe\(wrap\)", s)
    assert m and re.search(r"setTimeout\([\s\S]*?\}, 1000\)", m.group(0)) and "load()" in m.group(0)


def test_elapsed_text_by_state():
    """DEF-QA2-401: 살아 있는 설비 = 상태 지속(elapsed_s) · 끝난 설비 = 「끝남 · ended_at 로부터 n 전」(ended_ago_s) ·
    멈춤 의심 = 마지막 기록부터(last_ago_s). 상태줄 · aria · 숨김 표가 같은 글자를 쓴다."""
    s = src("_twin.html")
    m = re.search(r"function timeText\(m\) \{[\s\S]*?\n  \}", s)
    assert m, "timeText 없음"
    body = m.group(0)
    assert "ended_ago_s" in body and "last_ago_s" in body and "elapsed_s" in body and '" 전"' in body
    assert "FINAL[m.state]" in body and '"STALE"' in body
    assert s.count("timeText(m)") >= 3                                              # 상태줄 · aria · 표
