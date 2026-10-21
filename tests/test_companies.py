"""회사별 묶음 — 가짜 DB의 근거·부모·모호함·화면 갱신 회귀."""

from datetime import timedelta
from unicodedata import normalize

import pytest
from fastapi.testclient import TestClient

from agentdash.core import companies as C, pipeline as P
from agentdash.db import conn
from test_graph import NOW, Synth, iso


@pytest.fixture
def db(monkeypatch):
    dictionary = P.Dictionary(strip=[" ", "주식회사", "(주)"], names=["가나제조", "다라식품"],
                              norm={"가나제조": "가나제조", "가나": "가나제조", "다라식품": "다라식품"}, variants={})
    monkeypatch.setattr(P, "load_dictionary", lambda: dictionary)
    stages = [{"code": "01", "label": "분석", "folder": "01 Analyze Agent"},
              {"code": "02", "label": "설계", "folder": "02 Design Agent"}]
    cells = [P.Cell(co, code, status, status, "P-03", "P-03", 0, 1)
             for co in dictionary.names for code, status in [("01", "DONE"), ("02", "NOT_STARTED")]]
    result = P.Result(stages, dictionary.names, cells, {}, 0, iso(NOW), "fake")
    monkeypatch.setattr(P, "cached", lambda con: result)
    con = conn.connect(conn.init_db())
    yield con
    con.close()


def groups(db):
    return {g["key"]: g for g in C.overview(db, NOW)["groups"]}


def test_names_aliases_unicode_parent_and_workflow_not_double_counted(db):
    s = Synth(db)
    s.agent("S:p", "SESSION", "shared", "p", name="주식회사 가나 PM", state="RUNNING")
    s.agent("W:w", "WORKFLOW", "shared", "p", parent="S:p", state="RUNNING")
    s.agent("A:k", "WORKFLOW_AGENT", "shared", "p", parent="W:w", state="WAITING_PERMISSION")
    s.agent("S:food", "SESSION", "food", "food", path=normalize("NFD", "/x/다라식품 MES"), state="DONE")
    s.agent("S:other", "SESSION", "shared", "other", state="STALE")
    db.commit()
    g = groups(db)
    assert {a["agent_key"] for a in g["가나제조"]["agents"]} == {"S:p", "A:k"}
    assert g["가나제조"]["running"] == 1 and g["가나제조"]["waiting"] == 1
    assert g["가나제조"]["agents"][0]["basis"].startswith("부모 에이전트")
    assert g["다라식품"]["done"] == 1
    assert [a["agent_key"] for a in g[C.UNKNOWN]["agents"]] == ["S:other"]
    assert sum(len(x["agents"]) for x in g.values()) == 4
    assert C.overview(db, NOW)["groups"][0]["key"] == "가나제조"


def test_conflicts_cycles_and_child_evidence_stays_independent(db):
    s = Synth(db)
    s.agent("S:p", "SESSION", "p", "p", name="가나제조 다라식품", state="RUNNING")
    s.agent("A:k", "SUBAGENT", "p", "p", parent="S:p", state="RUNNING")
    s.agent("A:own", "SUBAGENT", "p", "p", parent="S:p", name="다라식품 QA", state="RUNNING")
    s.agent("A:cycle1", "SUBAGENT", "q", "q", parent="A:cycle2", state="RUNNING")
    s.agent("A:cycle2", "SUBAGENT", "q", "q", parent="A:cycle1", state="RUNNING")
    db.commit()
    g = groups(db)
    assert len(g[C.UNKNOWN]["agents"]) == 4
    assert {a["basis"] for a in g[C.UNKNOWN]["agents"]} == {"여러 회사 근거가 겹침", "회사 연결 근거 없음"}
    assert [a["agent_key"] for a in g["다라식품"]["agents"]] == ["A:own"]


def test_latest_recent_file_evidence_and_stale_future_ignored(db):
    s = Synth(db)
    for key in ("recent", "old", "future", "tie", "done"):
        s.agent("S:" + key, "SESSION", "shared", key, state="DONE" if key == "done" else "RUNNING")
    for key, minute, target in [("recent", -5, "/x/가나/a.py"), ("recent", -2, "/x/다라식품/b.py"),
                                ("old", -31, "/x/가나/a.py"), ("future", 1, "/x/가나/a.py"),
                                ("tie", -1, "/x/가나/a.py"), ("tie", -1, "/x/다라식품/b.py"),
                                ("done", -1, "/x/가나/a.py")]:
        db.execute("INSERT INTO file_touch VALUES (?,?,?,?)",
                   ("S:" + key, target, "Edit", iso(NOW + timedelta(minutes=minute))))
    # 이름·경로가 있는 에이전트는 작업 중 읽은 타 회사 파일로 바뀌지 않는다.
    s.agent("S:explicit", "SESSION", "p", "explicit", name="가나제조", state="RUNNING")
    db.execute("INSERT INTO tool_call (agent_key,tool_use_id,at,tool,target) VALUES (?,?,?,?,?)",
               ("S:explicit", "t", iso(NOW), "Read", "/x/다라식품/a.py"))
    db.commit()
    g = groups(db)
    assert [a["agent_key"] for a in g["다라식품"]["agents"]] == ["S:recent"]
    assert [a["agent_key"] for a in g["가나제조"]["agents"]] == ["S:explicit"]
    assert len(g[C.UNKNOWN]["agents"]) == 4


def test_company_selection_partial_refresh_next_role_and_escaping(db):
    from agentdash.app.main import app
    s = Synth(db)
    s.agent("S:a", "SESSION", "p&x", "a", name="가나제조 <script>bad()</script>", state="WAITING_INPUT",
            path="/x/가나 프로젝트")
    s.agent("S:b", "SESSION", "food", "b", name="다라식품 only", state="RUNNING")
    db.commit()
    c = TestClient(app)
    r = c.get("/", params={"company": "가나제조"})
    assert r.status_code == 200
    t = r.text
    assert 'aria-current="true"' in t and 'data-company="가나제조"' in t
    assert 'data-agent="S:a"' in t and 'data-agent="S:b"' not in t
    assert "다음에 필요한 역할 · 설계" in t and "02 Design Agent" in t
    assert "&lt;script&gt;bad()&lt;/script&gt;" in t and "<script>bad()" not in t
    assert "project=p%26x" in t and "구성도" in t
    body = c.get("/", params={"part": "body", "company": "가나제조"}).text
    assert 'data-company="가나제조"' in body and 'id="twin-svg"' not in body and "<script>" not in body
    assert 'params.set("part", "body")' in t and "window.location.search" in t
    assert "등록되지 않은 회사" in c.get("/", params={"company": "bad"}).text
    assert "회사 미확인" in c.get("/", params={"company": C.UNKNOWN}).text


def test_empty_company_and_config_error_are_visible(db, monkeypatch):
    from agentdash import settings
    from agentdash.app.main import app
    c = TestClient(app)
    assert "아직 수집된 에이전트가 없습니다" in c.get("/", params={"company": "가나제조"}).text

    def bad():
        raise settings.SettingsError("companies.yaml 오류")
    monkeypatch.setattr(P, "load_dictionary", bad)
    t = c.get("/").text
    assert "회사 현황을 불러오지 못했습니다" in t and "companies.yaml 오류" in t
    assert 'id="twin-svg"' in t and "살아 있는 에이전트 없음" in t


def test_unknown_pipeline_does_not_claim_completion(db, monkeypatch):
    from agentdash.app.main import app
    result = P.cached(db)
    for cell in result.cells:
        cell.status = cell.base_status = "UNKNOWN"
    c = TestClient(app)
    t = c.get("/", params={"company": "가나제조"}).text
    assert "진척을 확인할 수 없는 단계 2개" in t
    assert "다음 미완료 단계가 없습니다" not in t


def test_real_pipeline_role_and_company_anchor():
    from agentdash.app.main import app
    conn.init_db()
    P.clear_cache()
    c = TestClient(app)
    co = P.load_dictionary().names[0]
    t = c.get("/", params={"company": co}).text
    assert "다음에 필요한 역할 · 분석" in t and "01 Analyze Agent" in t
    pipe = c.get("/pipeline").text
    assert 'id="company-' + co + '"' in pipe


def test_refresh_reflects_state_changes_and_keeps_selection(db):
    from agentdash.app.main import app
    Synth(db).agent("S:a", "SESSION", "p", "a", name="가나제조", state="WAITING_PERMISSION")
    db.commit()
    c = TestClient(app)
    before = c.get("/", params={"company": "가나제조", "part": "body"}).text
    assert "활성 1 · 완료 0 · 누적 1" in before
    db.execute("UPDATE agent SET state='DONE' WHERE agent_key='S:a'")
    db.commit()
    after = c.get("/", params={"company": "가나제조", "part": "body"}).text
    assert 'data-company="가나제조"' in after and "활성 0 · 완료 1 · 누적 1" in after


def test_floor_filter_keeps_company_in_browser_url():
    from pathlib import Path
    from test_twin_page import _node
    import re
    script = (Path(__file__).resolve().parents[1] / "src/agentdash/app/templates/_twin.html").read_text()
    handler = re.search(r'getElementById\("twin-filter"\)\.addEventListener\("change", function \(\) \{([\s\S]*?)\n  \}\);', script).group(1)
    js = "\n".join([
        "var vbInit=true, loaded=false, dest;",
        "var location={search:'?company=%EA%B0%80%EB%82%98%EC%A0%9C%EC%A1%B0',hash:'#company-hub'};",
        "var history={replaceState:function(a,b,url){dest=url;}};",
        "function params(){return 'since=7d&project=shared';} function load(){loaded=true;}",
        handler,
        "console.log(JSON.stringify([new URL(dest,'http://localhost').searchParams.get('company'),loaded,vbInit]));",
    ])
    import json
    assert json.loads(_node(js)) == ["가나제조", True, False]


def test_old_running_server_can_render_updated_template():
    """운영 프로세스를 재시작하기 전에도 기존 관제판의 템플릿 갱신은 안전하다."""
    from agentdash.app.templating import TEMPLATES
    t = TEMPLATES.get_template("_companies.html").render({})
    assert "회사별 현황은 서버 업데이트 후 표시됩니다" in t
