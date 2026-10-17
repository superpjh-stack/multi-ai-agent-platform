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
