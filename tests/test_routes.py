"""G-17 — 화면 6 + API 10 이 빈 DB 에서 200 (placeholder 포함)."""

from fastapi.testclient import TestClient

from agentdash.app.main import app
from agentdash.db import conn

PAGES = ["/", "/graph", "/agents/S:fixture", "/usage", "/timeline", "/pipeline"]
APIS = ["/api/v1/summary", "/api/v1/agents", "/api/v1/agents/S:fixture", "/api/v1/agents/S:fixture/tools",
        "/api/v1/graph", "/api/v1/usage", "/api/v1/timeline", "/api/v1/pipeline", "/api/v1/stream"]


def test_pages_and_apis_200_on_empty_db():
    conn.init_db()
    c = TestClient(app)
    for p in PAGES:
        r = c.get(p, headers={"accept": "text/html"})
        assert r.status_code == 200, p
        assert "미구현 — 담당 개발" in r.text or "data-placeholder" not in r.text
    for p in APIS:
        assert c.get(p).status_code == 200, p
    assert c.post("/hooks/event", json={}).status_code == 200


def test_placeholder_names_owner():
    """남은 placeholder 는 담당을 밝힌다 (웨이브 B 에서 화면이 하나씩 구현되며 줄어든다 — 개발2 가 D-01~D-03 구현 뒤 고침)."""
    conn.init_db()
    c = TestClient(app)
    for p in PAGES:
        t = c.get(p, headers={"accept": "text/html"}).text
        if "data-placeholder" in t:
            assert "미구현 — 담당 개발" in t, p
    for p in APIS[:-1]:
        j = c.get(p).json()
        if "_placeholder" in j:
            assert j["_placeholder"].startswith("미구현 — 담당 개발"), p
    for p in ("/", "/graph", "/agents/S:fixture"):          # D-01 · D-02 · D-03 은 구현됨 (개발2 웨이브 B)
        assert "data-placeholder" not in c.get(p).text, p
