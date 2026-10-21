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
    assert "<title>에이전트 모니터링 · 멀티 에이전트 플랫폼 대시보드" in t and "D-01 에이전트 모니터링" in t
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


def test_tool_line_ellipsis_and_final_empty():
    """DEF-QA2-404: 「지금 도구」 는 상자 너비에 맞춰 말줄임(…) — SVG 글자 길이를 재서 자른다(+ 글자 수 상한).
    끝난 설비(DONE · FAILED)는 비운다 (서버도 tool/target = null)."""
    s = src("_twin.html")
    m = re.search(r"function fitText\(t, maxW\) \{[\s\S]*?\n  \}", s)
    assert m and "getComputedTextLength" in m.group(0) and "…" in m.group(0)
    assert re.search(r'data-role", "tool"', s) or "data-role\", \"tool\"" in s or '"data-role": "tool"' in s
    assert re.search(r"fitText\([^)]*w - 20\)", s)
    assert re.search(r"function toolText\(m\) \{[\s\S]{0,200}?FINAL\[m\.state\][\s\S]{0,40}?\"\"", s)


def test_done_transition_reverse_flow_once():
    """DEF-QA2-403: 다시 깨운 서브에이전트의 두 번째 반환은 edge.new 가 안 온다(엣지 count 만 늚) → agent.state DONE 전이
    때 부모 쪽 역흐름 1 회. 같은 반환이 edge.new(handback) 와 DONE 전이 둘로 와도 한 번만 흐른다(revAt 3 초)."""
    s = src("_twin.html")
    m = re.search(r"function revFlow\(child, parent\) \{[\s\S]*?\n  \}", s)
    assert m and "revAt[child]" in m.group(0) and "3000" in m.group(0)
    h = re.search(r'"agent\.state"\s*:\s*function[\s\S]*?\n    \},', s).group(0)
    assert re.search(r'd\.state === "DONE"[\s\S]{0,300}revFlow\(d\.agent_key', h)
    fl = re.search(r"function flowNow\(e\) \{[\s\S]*?\n  \}", s).group(0)
    assert re.search(r'e\.kind === "handback"[\s\S]{0,80}revFlow\(e\.src, e\.dst\)', fl)


def test_name_line_ellipsis():
    """DEF-QA2-501: 설비 이름 줄도 도구 줄(DEF-QA2-404)처럼 SVG 글자 길이를 재서 머리띠 폭(오른쪽 배지 자리 빼고)에 맞춰
    「…」 로 자른다 — clipPath 로 글자 중간이 잘리지 않게. 서버 24 자 자르기(NAME_MAX)는 그대로."""
    from agentdash.core import twin
    assert twin.NAME_MAX == 24
    s = src("_twin.html")
    dm = re.search(r"function drawMachine\(m, ln, layer, d, clips\) \{[\s\S]*?\n  \}", s).group(0)
    m = re.search(r'var (\w+) = txt\(\{"class": "m-name"[^;]*\}, m\.name, mc\);', dm)
    assert m, "이름 줄이 변수로 잡히지 않음"
    assert re.search(r"fitText\(" + m.group(1) + r", w - 52\)", dm), "이름 줄 말줄임 없음 (x 26 ~ 배지 자리 w − 26)"


def _js_fn(s: str, name: str) -> str:
    m = re.search(r"  function " + name + r"\([^)]*\) \{[\s\S]*?\n  \}", s)
    assert m, name
    return m.group(0)


def _node(js: str) -> str:
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_final_without_ended_at_uses_last_record():
    """DEF-QA2-502 / D-33: DONE · FAILED 이고 ended_at 이 없으면(ended_ago_s = null) 상태 지속(백필 시각부터)이 아니라
    마지막 기록부터 「기록 n 전」 — 상태줄은 「끝남 · 기록 1시간 56분 전」. ended_at 이 있으면 그대로 「n 전」."""
    s = src("_twin.html")
    js = "\n".join([
        "var FINAL = {DONE: 1, FAILED: 1}, fetchedAt = Date.now();",
        _js_fn(s, "dur"), _js_fn(s, "agoNow"), _js_fn(s, "timeText"),
        "var out = [",
        "  timeText({state: 'DONE', ended_ago_s: null, last_ago_s: 6960, elapsed_s: 68}),",
        "  timeText({state: 'FAILED', ended_ago_s: null, last_ago_s: 120, elapsed_s: 5}),",
        "  timeText({state: 'DONE', ended_ago_s: 1680, last_ago_s: 1680, elapsed_s: 68}),",
        "  timeText({state: 'DONE', ended_ago_s: null, last_ago_s: null, elapsed_s: 68}),",
        "  timeText({state: 'RUNNING', ended_ago_s: null, last_ago_s: 3, elapsed_s: 68}),",
        "];",
        "console.log(JSON.stringify(out));",
    ])
    import json
    out = json.loads(_node(js))
    assert out == ["기록 1시간 56분 전", "기록 2분 전", "28분 전", "1분 8초", "1분 8초"]


@pytest.mark.parametrize("card_w,card_h,content_w,content_h,cols", [
    (307, 340, 504, 1500, 1),
    (866, 700, 1152, 1400, 2),
    (866, 700, 504, 1500, 1),
    (2000, 700, 1152, 1400, 3),
    (307, 340, 1, 1, 1),
])
def test_fit_keeps_all_svg_text_at_least_12px(card_w, card_h, content_w, content_h, cols):
    """사용자 승인: 첫 표시/맞춤은 화면 폭·열 수에 관계없이 가장 작은 글자도 12px.
    서버 좌표는 그대로 두고 카드 내부에서 이동한다. 기존 10px 이름 하한을 대체한다."""
    s = src("_twin.html")
    constants = re.search(r"var MIN_TEXT_PX = 12, SMALLEST_TEXT_PX = 10,[^;]*;", s)
    assert constants
    assert "overflow:hidden" in re.search(r"\.tw-wrap \{[^}]*\}", s).group(0)
    js = "\n".join([
        constants.group(0),
        f"var vb = {{}}, content = {{x: 0, y: 0, w: {content_w}, h: {content_h}}};",
        f"var T = {{last: {{grid: {{cols: {cols}}}}}}}, C = {{w: {card_w}, h: {card_h}}};",
        "function size() { return C; }",
        "function applyVB() { T.scale = C.w / vb.w; }",
        _js_fn(s, "fit"),
        "fit(); console.log(JSON.stringify([T.scale, vb.x, vb.y]));",
    ])
    import json
    scale, x, y = json.loads(_node(js))
    for size in re.findall(r"#twin-svg[^{}]+\{[^}]*?font-size:\s*(\d+)px", s):
        assert int(size) * scale >= 12 - 1e-9, (size, scale)
    assert (x, y) == (-16, -16)


def test_grid_width_reserves_readable_scale_and_padding():
    """읽기 배율과 여백을 반영한 너비를 전달하고 격자 계산은 서버에 맡긴다."""
    s = src("_twin.html")
    constants = re.search(r"var MIN_TEXT_PX = 12, SMALLEST_TEXT_PX = 10,[^;]*;", s)
    assert constants
    js = "\n".join([
        constants.group(0), "var wrap = {};", _js_fn(s, "gridWidth"),
        "console.log(JSON.stringify([307,866,2000,0].map(function (w) { wrap.clientWidth = w; return gridWidth(); })));",
    ])
    import json
    widths = json.loads(_node(js))
    for card, width in zip([307, 866, 2000], widths):
        assert (width + 32) * 1.2 <= card + 1e-9
        assert (width + 33) * 1.2 > card
    assert widths[-1] == 1


def test_manual_zoom_can_zoom_out_and_fit_restores_readable_size():
    s = src("_twin.html")
    constants = re.search(r"var MIN_TEXT_PX = 12, SMALLEST_TEXT_PX = 10,[^;]*;", s)
    assert constants
    js = "\n".join([
        constants.group(0),
        "var T = {}, C = {w: 307, h: 340}, vb = {}, content = {x:0, y:0, w:504, h:1500};",
        "function size() { return C; } function applyVB() { T.scale = C.w / vb.w; }",
        _js_fn(s, "fit"), _js_fn(s, "zoomAt"),
        "fit(); zoomAt(0.8, 0, 0); var manual = T.scale; fit();",
        "console.log(JSON.stringify([manual, T.scale]));",
    ])
    import json
    manual, fitted = json.loads(_node(js))
    assert manual < 1.2 and fitted * 10 >= 12 - 1e-9


def test_fractional_svg_height_does_not_shrink_text_below_minimum():
    """62vh/72vh는 소수점 px: clientHeight 정수 반올림 때문에 meet 배율이 작아지지 않아야 한다."""
    s = src("_twin.html")
    js = "\n".join([
        re.search(r"var MIN_TEXT_PX = 12, SMALLEST_TEXT_PX = 10,[^;]*;", s).group(0),
        "var vb = {}, T = {}, content = {x:0, y:0, w:1152, h:1400}, attr;",
        "var svg = {getBoundingClientRect: function () { return {width:900, height:477.953125}; },",
        "setAttribute: function (k,v) { attr = v; }};",
        "var wrap = {clientWidth:900, clientHeight:478};",
        _js_fn(s, "size"), _js_fn(s, "applyVB"), _js_fn(s, "fit"),
        "fit(); var b = attr.split(' ').map(Number);",
        "console.log(Math.min(900/b[2], 477.953125/b[3]) * 10);",
    ])
    assert float(_node(js)) >= 12 - 1e-9
