"""G-17 — 화면 7 + API 14 가 빈 DB 에서 200 (placeholder 포함) — spec.md v0.4 §7 · §8."""

from fastapi.testclient import TestClient

from agentdash.app.main import app
from agentdash.db import conn

PAGES = ["/", "/graph", "/agents/S:fixture", "/usage", "/timeline", "/pipeline", "/insights"]
APIS = ["/api/v1/summary", "/api/v1/agents", "/api/v1/agents/S:fixture", "/api/v1/agents/S:fixture/tools",
        "/api/v1/graph", "/api/v1/usage", "/api/v1/timeline", "/api/v1/pipeline", "/api/v1/budget",
        "/api/v1/trend", "/api/v1/efficiency", "/api/v1/twin", "/api/v1/stream"]


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


def test_spec_counts_7_pages_14_apis():
    """check_routes 가 spec.md v0.4 에서 화면 7 (D-01~D-07) · API 14 를 읽는다 (2차-T `/api/v1/twin`)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "agentdash" / "tools"))
    import check_routes

    pages, apis = check_routes.spec_routes()
    assert [c for c, _, _ in pages] == [f"D-0{i}" for i in range(1, 8)]
    assert ("GET", "/insights") in {("GET", p) for _, _, p in pages}
    assert len(apis) == 14 and check_routes.N_APIS == 14
    assert ("GET", "/api/v1/twin") in set(apis)
    assert {("GET", "/api/v1/budget"), ("GET", "/api/v1/trend"), ("GET", "/api/v1/efficiency")} <= set(apis)
    assert len(PAGES) == 7 and len(APIS) + 1 == 14          # + POST /hooks/event
