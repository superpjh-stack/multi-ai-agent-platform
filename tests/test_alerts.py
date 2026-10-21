"""WAITING 알림 스크립트 `_alerts.html` 정적 계약 (spec.md v0.3 §7.2 · G-29) — 담당 개발2.

JS 동작(첫 로드 0 · 전이 1 · 재전송 0 · 두 탭 1 · 권한 거부 시 배지만)은 브라우저 E2E(QA2 `outputs/e2e/alerts.md`)가 판정한다.
여기서는 서버 변경 없이 모든 화면이 스크립트를 한 번 싣고, 계약 문자열 · 호출 대상이 맞는지만 본다. 가짜 DB 만 쓴다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentdash.db import conn

TPL = Path(__file__).resolve().parents[1] / "src" / "agentdash" / "app" / "templates" / "_alerts.html"
MARK = 'id="agentdash-alerts"'
SCREENS = ["/", "/graph", "/agents/S:none", "/usage", "/timeline", "/pipeline", "/insights"]   # 화면 7 (D-01~D-07)


@pytest.fixture
def client():
    con = conn.connect(conn.init_db())
    con.close()
    from agentdash.app.main import app
    return TestClient(app)


def src() -> str:
    return TPL.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", SCREENS)
def test_every_screen_includes_alerts_once(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert r.text.count(MARK) == 1, path
    assert r.text.index(MARK) > r.text.index("</main>")          # 머리글 버튼 · 본문이 그려진 뒤
    assert 'id="alerts-btn"' in r.text
    assert r.text.count("new EventSource(") == 1, path             # 탭당 SSE 1 연결 — 화면은 openStream 으로 같이 쓴다 (R-2A-dev2-3)


def test_screens_share_one_stream():
    """화면 스크립트 구독(openStream)이 _alerts 의 EventSource 에 붙는다 — 먼저 부른 구독은 줄에 있다가 붙는다."""
    s = src()
    assert "A.subscribe = function" in s and "window.agentdashStreamQueue" in s
    for name in ("agent.new", "agent.usage", "edge.new"):
        assert f'"{name}"' in s, name
    live = (TPL.parent / "_live.html").read_text(encoding="utf-8")
    assert "new EventSource" not in live and "agentdashAlerts.subscribe" in live and "agentdashStreamQueue" in live


def test_partial_body_has_no_second_copy(client):
    assert MARK not in client.get("/?part=body").text            # D-01 부분 갱신 조각에는 싣지 않는다 (두 번 구독 방지)


def test_contract_strings():
    s = src()
    for w in ("agent.state", "WAITING_INPUT", "WAITING_PERMISSION", "BroadcastChannel", '"agentdash-alerts"', "tag:",
              "requestPermission", '"agentdash.alerts"', '"agentdash.seen"', "window.agentdashAlerts", "alerts-btn",
              "알림 불가 — 배지만", "권한 대기", "입력 대기", "/agents/", "state_since", "200"):
        assert w in s, w
    assert re.search(r"waiting:\s*new Set\(\)", s) and re.search(r"seen:\s*new Set\(\)", s)
    assert s.count("new EventSource(") == 1 and 'new EventSource("/api/v1/stream?follow=1")' in s
    assert s.count("addEventListener(\"agent.state\"") == 1


def test_fetch_targets_only_api_v1():
    s = src()
    calls = [m.start() for m in re.finditer(r"\bfetch\(", s)]
    assert calls, "fetch 호출 없음"
    for i in calls:
        assert re.match(r'fetch\(\s*"/api/v1/', s[i:]), s[i:i + 60]
    assert "XMLHttpRequest" not in s and "sendBeacon" not in s and "WebSocket" not in s


def test_no_external_url_or_dialog():
    s = src()
    assert not re.search(r"https?:|//[a-z0-9.-]+\.[a-z]{2,}", s, re.I)    # 외부 URL 0 (프로토콜 상대 포함)
    assert "<script src" not in s and "import(" not in s
    for d in ("alert(", "confirm(", "prompt("):                       # 브라우저 대화상자 0
        assert not re.search(r"(?<![\w.])" + re.escape(d), s), d


def test_first_load_and_once_rules_present():
    """첫 로드 = 대기 목록으로 채우고 알리지 않음 · (key|since) 1 회 · 리더 탭만 · 거부/미지원은 배지만."""
    s = src()
    assert 'fetch("/api/v1/agents?state=WAITING_INPUT,WAITING_PERMISSION' in s
    assert 'fetch("/api/v1/agents/" + encodeURIComponent(' in s
    assert "denied" in s and '"Notification" in window' in s
    assert re.search(r"document\.title\s*=", s) and '"(" + n + ") "' in s
