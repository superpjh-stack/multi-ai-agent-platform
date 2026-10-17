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
    c = TestClient(app)
    assert "미구현 — 담당 개발2" in c.get("/").text
    assert c.get("/api/v1/usage").json()["_placeholder"] == "미구현 — 담당 개발1"
