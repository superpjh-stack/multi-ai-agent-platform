"""G-19 진척 판정 — spec.md §7.1 P-01~P-07 · 정규화 · 제외 · 뒤처짐 · 고려솔더 기대값 (가짜 루트만).

가짜 에이전트 폴더는 **파일 이름 + 빈 내용 + 짧은 표제**로만 만든다 (실제 산출물 · progress.md 본문을 복사하지 않는다).
실제 폴더 실측(고려솔더 기대값 포함)은 `src/agentdash/tools/check_pipeline.py` (V-11) 가 한다.
"""

from __future__ import annotations

import json
import os
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agentdash.core import pipeline as P
from agentdash.db import conn

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 17, 7, 0, 0, tzinfo=timezone.utc)
A01, A02, A03, A04, A00 = "01 Analyze Agent", "02 Design Agent", "03 UI Agent", "04 QA Agent", "00 PM Agent"
QA_DOCS = ["단위테스트결과서", "통합테스트결과서", "시스템전환결과서", "메뉴얼", "사용자테스트결과서", "운영지원계획서", "운영현황보고서"]
TD = ["개선업무설계서", "아키텍처설계서", "화면설계서", "프로그램설계서", "데이터베이스설계서"]


def touch(p: Path, mtime: datetime | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")
    if mtime is not None:
        t = mtime.timestamp()
        os.utime(p, (t, t))
    return p


def run_json(d: Path, started: str, **extra) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(json.dumps({"run_id": d.name, "started": started, **extra}), encoding="utf-8")


def analyze_run(root: Path, run: str, co: str, ver: str = "1.0", n: int = 3, mtime=None) -> Path:
    d = root / A01 / "outputs" / run
    run_json(d, f"{run[:4]}-{run[4:6]}-{run[6:8]} {run[9:11]}:{run[11:13]}:{run[13:15]}")
    names = ["현행업무분석서", "요구사항정의서", "기능대비표"]
    for i in range(n):
        touch(d / f"0{i + 1}.SF-AD{i + 1}_{names[i]}_{co}_v{ver}.docx", mtime)
    return d


def design_run(root: Path, run: str, co: str, ver: str = "1.0", mtime=None) -> Path:
    d = root / A02 / "outputs" / run
    run_json(d, f"{run[:4]}-{run[4:6]}-{run[6:8]} {run[9:11]}:{run[11:13]}:{run[13:15]}")
    for i, name in enumerate(TD, 1):
        touch(d / f"0{i + 3}.SF-TD{i}_{name}_{co}_v{ver}.docx", mtime)
    return d


def ui_files(root: Path, co: str, label: str = "제조AI", mtime=None, video=True, pptx=True) -> None:
    out = root / A03 / "outputs"
    touch(out / f"{co}_{label}_화면설명서_v1.0.html", mtime)
    if pptx:
        touch(out / f"{co}_{label}_화면정의서_v1.0.pptx", mtime)
    if video:
        touch(out / f"{co}_{label}_화면설명서_영상_요약_v1.0.mp4", mtime)


def qa_files(root: Path, co: str, label: str = "제조AI", docs=QA_DOCS, mtime=None) -> None:
    for doc in docs:
        touch(root / A04 / "outputs" / f"{co}_{label}_{doc}_v1.0.docx", mtime)


def pm_files(root: Path, co: str, run: str = "20261016-161007-midterm", facts_co: str | None = None) -> None:
    d = root / A00 / "outputs" / run
    run_json(d, "2026-10-16 16:10:07", facts=f"notes/{facts_co or co}_확정값.yaml")
    touch(d / f"11.중간보고서_{co}_v1.0.docx")
    touch(d / f"11-1.중간보고서_검수의견_{co}_v1.0.docx")
    for i, name in ((4, "요구사항추적표"), (1, "월간보고서"), (2, "회의록"), (3, "변경관리내역서")):
        touch(root / A00 / "outputs" / f"pm-{co}" / f"1{i}.SF-PM{i}_{name}_{co}_v1.0.docx")


def progress(root: Path, folder: str, lines: list[str]) -> None:
    p = root / folder / "progress.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    r = tmp_path / "agents"
    for f in (A00, A01, A02, A03, A04, "05 Open Agent", "06 Coding Agent", "08 AI Agent Making Agent"):
        (r / f).mkdir(parents=True)
    (r / A01 / "outputs").mkdir()
    monkeypatch.setenv("AGENTDASH_AGENTS_ROOT", str(r))
    P.clear_cache()
    return r


@pytest.fixture
def db():
    path = conn.init_db()
    con = conn.connect(path)
    yield con
    con.close()


def ev(root, con=None):
    return P.evaluate(con, NOW, root)


# ── 고려솔더 기대값 (G-19 · spec §13-7) ───────────────────────────────
def test_koreasolder_expected(root):
    old = datetime(2026, 9, 13, 1, 40, tzinfo=KST)
    new = datetime(2026, 10, 16, 16, 10, tzinfo=KST)
    analyze_run(root, "20260913-013208-all", "고려솔더", mtime=old)
    analyze_run(root, "20261016-151506-all", "고려솔더", mtime=new)
    design_run(root, "20260913-015935-all", "고려솔더", mtime=old)
    design_run(root, "20261016-154028-all", "고려솔더", mtime=new)
    r = ev(root)
    c1, c2 = r.cell("고려솔더", "01"), r.cell("고려솔더", "02")
    assert (c1.status, c1.rule, c1.have, c1.need, c1.version, c1.run_id) == ("DONE", "P-03", 3, 3, "v1.0", "20261016-151506-all")
    assert (c2.status, c2.rule, c2.have, c2.need, c2.version, c2.run_id) == ("DONE", "P-03", 5, 5, "v1.0", "20261016-154028-all")
    for st in ("05", "08"):
        c = r.cell("고려솔더", st)
        assert (c.status, c.rule, c.have, c.need) == ("UNKNOWN", "P-07", None, None)
    assert len(r.cells) == 11 * 8 and r.companies[1] == "고려솔더"


# ── P-01 ~ P-07 ───────────────────────────────────────────────────────
def test_p01_needs_decision_only_in_section(root):
    design_run(root, "20260811-182448-all", "니즈푸드")
    design_run(root, "20260812-131655-all", "엘컴화인")
    progress(root, A02, ["# 02", "## 지금까지 끝난 것", "### 엘컴화인 설계 5종 — 사용자 판단 필요 (옛 기록)",
                         "## 지금 해야 할 것", "### (B) 니즈푸드 프로그램 수 — 사용자 판단 필요", "## 알아둘 것"])
    r = ev(root)
    c = r.cell("니즈푸드", "02")
    assert (c.status, c.rule, c.base_status, c.base_rule) == ("NEEDS_DECISION", "P-01", "DONE", "P-03")
    assert c.progress == [f"{A02}/progress.md:5"] and f"{A02}/progress.md:5" in c.src
    assert r.cell("엘컴화인", "02").status == "DONE"      # 절 밖 표제는 배지 아님


def test_p01_table_row(root):
    progress(root, A03, ["## 지금 해야 할 것", "| 회사 | 일 |", "|---|---|", "| 원터치 | 색상 확인 필요 |"])
    c = ev(root).cell("원터치", "03")
    assert c.status == "NEEDS_DECISION" and c.base_status == "NOT_STARTED" and c.progress == [f"{A03}/progress.md:4"]


def test_p02_in_progress(root, db):
    ui_files(root, "원터치")
    db.execute("INSERT INTO agent (agent_key, kind, project_key, project_path, session_id, depth, state, name) "
               "VALUES ('S:x', 'SESSION', 'p', ?, 'x', 0, 'RUNNING', '세션')", (str(root / A03),))
    db.execute("INSERT INTO file_touch VALUES ('S:x', ?, 'Write', '2026-10-17T06:50:00Z')",
               (str(root / A03 / "outputs" / "원터치_제조AI_화면설명서_v1.0.html"),))
    db.execute("INSERT INTO agent (agent_key, kind, project_key, project_path, session_id, depth, state, name) "
               "VALUES ('S:y', 'SESSION', 'p', ?, 'y', 0, 'WAITING_INPUT', '광성정밀 화면')", (str(root / A03),))
    db.execute("INSERT INTO agent (agent_key, kind, project_key, project_path, session_id, depth, state, name) "
               "VALUES ('S:z', 'SESSION', 'p', ?, 'z', 0, 'DONE', '엘컴화인 화면')", (str(root / A03),))
    db.execute("INSERT INTO agent (agent_key, kind, project_key, project_path, session_id, depth, state, name) "
               "VALUES ('S:w', 'SESSION', 'p', ?, 'w', 0, 'RUNNING', '세션2')", (str(root / A03),))
    db.execute("INSERT INTO tool_call (agent_key, tool_use_id, at, tool, target) VALUES ('S:w', 't1', '2026-10-17T05:00:00Z', "
               "'Read', '평창꽃순이김치_x')", ())   # 30 분 밖
    r = ev(root, db)
    c = r.cell("원터치", "03")
    assert (c.status, c.rule) == ("IN_PROGRESS", "P-02") and "S:x RUNNING" in c.src
    assert c.last_session == "S:x"                          # 마지막 손댄 에이전트 (file_touch)
    assert r.cell("광성정밀", "03").rule == "P-02"          # 이름에 회사
    assert r.cell("엘컴화인", "03").rule == "P-06"          # DONE 에이전트는 진행 중 아님
    assert r.cell("평창꽃순이김치", "03").rule == "P-06"    # 30 분 밖 대상


def test_p03_p04_p06(root):
    ui_files(root, "광성정밀")
    ui_files(root, "원터치", video=False)
    r = ev(root)
    assert (r.cell("광성정밀", "03").status, r.cell("광성정밀", "03").have) == ("DONE", 3)
    c = r.cell("원터치", "03")
    assert (c.status, c.rule, c.have, c.need, c.missing) == ("PARTIAL", "P-04", 2, 3, ["영상"])
    c = r.cell("엘컴화인", "03")
    assert (c.status, c.rule, c.have) == ("NOT_STARTED", "P-06", 0) and "패턴 0 건" in c.src


def test_p05_done_without_files(root):
    progress(root, A03, ["## 광성정밀 (2026-08-21) — 완료", "## 지금 해야 할 것"])
    c = ev(root).cell("광성정밀", "03")
    assert (c.status, c.rule, c.have) == ("DONE", "P-05", 0) and "파일 없음" in c.note and f"{A03}/progress.md:1" in c.src


def test_p07_unknown_and_wave(root):
    progress(root, "06 Coding Agent", ["# 06", "## 웨이브 A — 아키텍트 ✅", "## 웨이브 B — 기획 🔄 진행 중", "## 메모"])
    r = ev(root)
    c = r.cell("고려솔더", "06")
    assert (c.status, c.rule) == ("UNKNOWN", "P-07") and c.wave == "웨이브 A ✅ · 웨이브 B 🔄"
    assert "06 Coding Agent/progress.md:2" in c.src
    assert r.cell("원터치", "06").wave is None
    assert all(r.cell(co, st).status == "UNKNOWN" for co in r.companies for st in ("05", "06", "08"))


# ── 정규화 · 미등록 · 제외 · 버전 · 실행 회사 ─────────────────────────
def test_normalize_aliases_and_nfd(root):
    d = P.load_dictionary()
    assert d.lookup("주식회사 고려솔더") == "고려솔더" and d.lookup("(주)광성정밀") == "광성정밀"
    assert d.lookup("송월타월 서울상사") == "송월타월서울상사" and d.lookup("lcomFine") == "엘컴화인"
    assert d.lookup("두손푸드") is None
    assert d.lookup(unicodedata.normalize("NFD", "니즈푸드")) == "니즈푸드"
    assert d.find_in("### (B) 니즈푸드 프로그램") == {"니즈푸드"}
    qa_files(root, unicodedata.normalize("NFD", "니즈푸드"), label="스마트공장")      # macOS NFD 파일 이름 · 스마트공장 표기
    analyze_run(root, "20260810-225739-all", "주식회사 고려솔더")
    r = ev(root)
    assert r.cell("니즈푸드", "04").status == "DONE" and r.cell("고려솔더", "01").have == 3


def test_unregistered_company(root):
    analyze_run(root, "20260901-000000-all", "두손푸드")
    touch(root / A04 / "outputs" / "두손푸드_제조AI_메뉴얼_v1.0.docx")
    r = ev(root)
    d = r.as_dict()
    assert d["unregistered"] == 1 and d["unregistered_names"] == ["두손푸드"]
    assert "두손푸드" not in r.companies and all(c.company != "두손푸드" for c in r.cells)


def test_excluded_folders(root):
    out = root / A03 / "outputs"
    for sub in ("_구판_20260902", "tour", "scratch", "_preview_img"):
        touch(out / sub / "원터치_제조AI_화면설명서_v1.0.html")
    touch(out / "_preview_원터치_제조AI_화면정의서_v1.0.pptx")
    d = analyze_run(root, "20260913-013212-all", "원터치", n=1)
    touch(d / "scratch" / "02.SF-AD2_요구사항정의서_원터치_v1.0.docx")
    (root / A01 / "outputs" / "_구판_x-all").mkdir()
    touch(root / A01 / "outputs" / "_구판_x-all" / "03.SF-AD3_기능대비표_원터치_v1.0.docx")
    r = ev(root)
    assert r.cell("원터치", "03").have == 0
    assert r.cell("원터치", "01").have == 1


def test_highest_version_then_latest_run(root):
    analyze_run(root, "20261001-000000-all", "와이엔프린팅", ver="1.1")
    analyze_run(root, "20261010-000000-all", "와이엔프린팅", ver="1.0")
    c = ev(root).cell("와이엔프린팅", "01")
    assert (c.version, c.run_id) == ("v1.1", "20261001-000000-all")


def test_run_company_from_run_json_then_filename(root):
    pm_files(root, "원터치")
    d = root / A00 / "outputs" / "20260822-000000-midterm"
    run_json(d, "2026-08-22 00:00:00", facts="notes/엘컴화인_확정값.yaml")
    touch(d / "11.중간보고서_평창꽃순이김치_v1.0.docx")      # run.json 회사(엘컴화인)와 다른 파일 → 세지 않는다
    d2 = root / A00 / "outputs" / "20260823-000000-midterm"
    d2.mkdir(parents=True)
    touch(d2 / "11.중간보고서_임진강김치_v1.0.docx")         # run.json 없음 → 파일명으로
    r = ev(root)
    c = r.cell("원터치", "00")
    assert (c.status, c.have, c.need, c.run_id) == ("DONE", 5, 5, "20261016-161007-midterm")
    assert r.cell("평창꽃순이김치", "00").have == 0 and r.mismatch == 1
    assert r.cell("임진강김치", "00").have == 1


def test_lag_marker(root):
    design_run(root, "20261016-154028-all", "고려솔더", mtime=datetime(2026, 10, 16, 16, 10, tzinfo=KST))
    ui_files(root, "고려솔더", mtime=datetime(2026, 10, 4, 12, 0, tzinfo=KST))
    ui_files(root, "원터치", mtime=datetime(2026, 10, 4, 12, 0, tzinfo=KST))
    design_run(root, "20260913-015432-all", "원터치", mtime=datetime(2026, 9, 13, 2, 0, tzinfo=KST))
    r = ev(root)
    c = r.cell("고려솔더", "03")
    assert c.lag and "↻" in c.lag_note and "02 20261016-154028-all" in c.lag_note and "run.json" in c.src
    assert not r.cell("원터치", "03").lag


# ── 저장 · API ───────────────────────────────────────────────────────
def test_store_every_cell_has_src_and_short_text(root, db):
    analyze_run(root, "20261016-151506-all", "고려솔더")
    progress(root, A02, ["## 지금 해야 할 것", "### (T) 임진강김치 " + "가" * 400 + " — 사용자 판단 필요"])
    r = P.refresh(db, NOW)
    db.commit()
    rows = db.execute("SELECT company, stage, status, rule, src, note FROM pipeline_cell").fetchall()
    assert len(rows) == 88 and all(row[4] for row in rows)
    assert all(len(v) <= 300 for row in rows for v in row if isinstance(v, str))
    assert {row[2] for row in rows} <= set(P.STATUSES)
    assert r.cell("임진강김치", "02").status == "NEEDS_DECISION"


def test_api_and_page_empty_root(root):
    from fastapi.testclient import TestClient

    from agentdash.app.main import app

    conn.init_db()
    c = TestClient(app)
    j = c.get("/api/v1/pipeline").json()
    assert len(j["cells"]) == 88 and j["unknown_cells"] == 33 and j["unregistered"] == 0
    assert all(x["src"] for x in j["cells"])
    h = c.get("/pipeline")
    assert h.status_code == 200 and "미등록 회사 0 건" in h.text and 'data-status="UNKNOWN"' in h.text


def test_pipeline_never_writes_source(root):
    analyze_run(root, "20261016-151506-all", "고려솔더")
    before = sorted((str(p), p.stat().st_mtime) for p in root.rglob("*"))
    for p in [root, *root.rglob("*")]:
        os.chmod(p, 0o555 if p.is_dir() else 0o444)
    try:
        r = ev(root)
        assert r.cell("고려솔더", "01").status == "DONE"
    finally:
        for p in [root, *root.rglob("*")]:
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
    assert sorted((str(p), p.stat().st_mtime) for p in root.rglob("*")) == before
