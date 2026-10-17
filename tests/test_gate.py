"""gate.py 가 QA 리포트에서 **지정 판정 블록만** 읽는가 (DEF-QA2-008).

형식 (CLAUDE.md 「QA 리포트 형식」): 표지 줄 `<!-- gate:G-nn -->` 바로 다음 줄 하나가 그 게이트의 판정 행
`G-nn  항목  PASS|FAIL|WARN|BLOCKED|미검증  실측`. 리포트 안의 다른 판정 꼴 줄(붙여 넣은 `make gate` 출력 등)은 읽지 않는다.
"""

from agentdash.tools import gate

FMT = "— QA 재검증 필요(리포트 형식)"


def _judge(tmp_path, text, gid="G-12"):
    p = tmp_path / "outputs" / "qa.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    old = gate.ROOT
    gate.ROOT = tmp_path
    try:
        return gate.judge(gid, "QA2", [("qa", "outputs/qa.md")], {})
    finally:
        gate.ROOT = old


def test_marker_row_is_read(tmp_path):
    st, detail = _judge(tmp_path, "# QA\n\n<!-- gate:G-12 -->\nG-12  상태 대조  PASS  표본 30 오판 1\n")
    assert st == "PASS" and "오판 1" in detail


def test_pasted_gate_output_is_ignored(tmp_path):
    """표지 행 PASS + 붙여 넣은 옛 make gate 출력(미검증 · FAIL) → PASS 그대로 (옛 판정이 섞이지 않는다)."""
    text = ("<!-- gate:G-12 -->\nG-12  상태 대조  PASS  오판 1\n\n## 붙인 make gate\n\n```\n"
            "G-12  상태 대조 — 표본 30 오판 ≤ 2  미검증  리포트 대기\nG-12  상태 대조  FAIL  옛 판정\n```\n")
    st, detail = _judge(tmp_path, text)
    assert st == "PASS" and "옛 판정" not in detail


def test_old_format_report_is_unverified(tmp_path):
    """표지 없는 옛 형식 리포트 — 판정 꼴 줄이 있어도 읽지 않고 `미검증 — QA 재검증 필요(리포트 형식)`."""
    st, detail = _judge(tmp_path, "## 게이트 판정 행\n\n```\nG-12  상태 대조  FAIL  오판 3\n```\n")
    assert st == "미검증"
    assert detail.startswith(FMT)


def test_marker_without_row_is_unverified(tmp_path):
    st, detail = _judge(tmp_path, "<!-- gate:G-12 -->\n\nG-12  상태 대조  PASS  빈 줄 뒤\n")
    assert st == "미검증" and detail.startswith(FMT)


def test_marker_row_for_other_gate_is_not_used(tmp_path):
    st, _ = _judge(tmp_path, "<!-- gate:G-12 -->\nG-18  구성도  PASS  x\n")
    assert st == "미검증"


def test_marker_for_one_gate_does_not_leak_to_another(tmp_path):
    text = "<!-- gate:G-21 -->\nG-21  브라우저  PASS  x\n\nG-12  상태 대조  PASS  표지 없음\n"
    assert _judge(tmp_path, text, "G-21")[0] == "PASS"
    assert _judge(tmp_path, text, "G-12")[0] == "미검증"


def test_two_markers_worst_wins(tmp_path):
    text = "<!-- gate:G-12 -->\nG-12  a  PASS  x\n<!-- gate:G-12 -->\nG-12  b  FAIL  y\n"
    assert _judge(tmp_path, text)[0] == "FAIL"


def test_missing_report_is_unverified(tmp_path):
    st, detail = gate.judge("G-12", "QA2", [("qa", "outputs/없는-리포트.md")], {})
    assert st == "미검증" and "없음" in detail


def test_tool_output_rows_still_read_whole(tmp_path):
    """검사기 출력(도구)은 지금처럼 모든 행을 읽는다 — 표지 형식은 QA 리포트에만."""
    assert gate.rows_of("x\nG-07  토큰 합  PASS  a\nG-07  토큰 합  FAIL  b\n", "G-07") == [("PASS", "a"), ("FAIL", "b")]


# ── 웨이브 D3 — DEF-QA1-103: QA 리포트 전부 · 가장 최근 회차 · 개발 판정과 더 나쁜 쪽 ──────────────
import pytest  # noqa: E402


@pytest.fixture
def qa_root(tmp_path, monkeypatch):
    (tmp_path / "outputs" / "e2e").mkdir(parents=True)
    monkeypatch.setattr(gate, "ROOT", tmp_path)

    def write(rel, text):
        (tmp_path / "outputs" / rel).write_text(text, encoding="utf-8")
    return write


def _row(gid, st, note=""):
    return f"<!-- gate:{gid} -->\n{gid}  항목  {st}  {note or st}\n"


def test_round_of():
    assert gate.round_of("qa1-데이터안전.md") == ("qa1-데이터안전", 0)
    assert gate.round_of("qa1-데이터안전-r2.md") == ("qa1-데이터안전", 2)
    assert gate.round_of("qa1-데이터안전-r10.md") == ("qa1-데이터안전", 10)
    assert gate.round_of("self-observe-r2.md") == ("self-observe", 2)


def test_latest_round_wins(qa_root):
    qa_root("qa1-데이터안전.md", _row("G-14", "FAIL", "원본 옛 판정"))
    qa_root("qa1-데이터안전-r2.md", _row("G-14", "PASS", "r2 판정"))
    rows = gate.qa_latest("G-14")
    assert [(f, s) for f, s, _ in rows] == [("outputs/qa1-데이터안전-r2.md", "PASS")]
    qa_root("qa1-데이터안전-r10.md", _row("G-14", "WARN", "r10"))       # 숫자 비교 (r10 > r2)
    assert [(f, s) for f, s, _ in gate.qa_latest("G-14")] == [("outputs/qa1-데이터안전-r10.md", "WARN")]


def test_original_used_when_no_round(qa_root):
    qa_root("qa1-데이터안전.md", _row("G-07", "FAIL", "원본"))
    assert [(f, s) for f, s, _ in gate.qa_latest("G-07")] == [("outputs/qa1-데이터안전.md", "FAIL")]


def test_each_family_read_and_e2e_included(qa_root):
    qa_root("qa1-데이터안전-r2.md", _row("G-15", "PASS"))
    qa_root("qa2-상태대조-r2.md", _row("G-15", "WARN"))
    qa_root("e2e/self-observe-r2.md", _row("G-22", "PASS"))
    assert sorted(s for _, s, _ in gate.qa_latest("G-15")) == ["PASS", "WARN"]
    assert [f for f, _, _ in gate.qa_latest("G-22")] == ["outputs/e2e/self-observe-r2.md"]
    assert gate.qa_latest("G-04") == []


@pytest.mark.parametrize("dev,qa,want", [
    ("PASS", "FAIL", "FAIL"), ("FAIL", "PASS", "FAIL"), ("PASS", "미검증", "미검증"),
    ("미검증", "PASS", "미검증"), ("WARN", "미검증", "WARN"), ("PASS", "PASS", "PASS"),
    ("PASS", "BLOCKED", "BLOCKED"), ("FAIL", "BLOCKED", "FAIL"),
])
def test_dev_and_qa_worse_wins(qa_root, monkeypatch, tmp_path, dev, qa, want):
    qa_root("qa1-데이터안전-r2.md", _row("G-14", qa, "QA 실측"))
    monkeypatch.setattr(gate, "run", lambda cmd, timeout=900: (0, f"G-14  도구  {dev}  개발 실측\n"))
    monkeypatch.setattr(gate, "TOOLS", tmp_path)
    (tmp_path / "check_readonly.py").write_text("", encoding="utf-8")
    st, detail = gate.judge("G-14", "아키텍트", [("tool", "check_readonly")], {})
    assert st == want
    assert "outputs/qa1-데이터안전-r2.md" in detail and "QA 실측" in detail and "개발 실측" in detail
    if qa == "BLOCKED":
        assert "BLOCKED" in detail


def test_dev_only_gate_without_qa_unchanged(qa_root, monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "run", lambda cmd, timeout=900: (0, "G-05  도구  PASS  개발 실측\n"))
    monkeypatch.setattr(gate, "TOOLS", tmp_path)
    (tmp_path / "check_parse_errors.py").write_text("", encoding="utf-8")
    assert gate.judge("G-05", "개발1", [("tool", "check_parse_errors")], {}) == ("PASS", "개발 실측")


def test_qa_required_gate_reads_latest_round(qa_root):
    """QA 몫 게이트(G-12 등)는 GATES 의 ("qa", "") — 리포트 묶음 중 최근 회차, 없으면 미검증."""
    assert gate.judge("G-12", "QA2", [("qa", "")], {})[0] == "미검증"
    qa_root("qa2-상태대조.md", "표지 없는 옛 형식\nG-12  x  PASS  y\n")
    qa_root("qa2-상태대조-r2.md", _row("G-12", "PASS", "r2"))
    st, detail = gate.judge("G-12", "QA2", [("qa", "")], {})
    assert st == "PASS" and "qa2-상태대조-r2.md" in detail


def test_gates_table_uses_qa_auto():
    assert all(name == "" for _, _, _, means in gate.GATES for k, name in means if k == "qa")
