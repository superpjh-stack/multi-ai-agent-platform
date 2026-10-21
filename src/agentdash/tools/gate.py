#!/usr/bin/env python
"""수용 게이트 판정표 — `make gate` (goal.md §2 G-01~G-35 — 1차 G-01~G-22 는 goal-v1.md · 2차-A G-23~G-30 은 goal-v2a.md).

    uv run python src/agentdash/tools/gate.py            # 판정표 (종료코드 0)
    uv run python src/agentdash/tools/gate.py --strict   # PASS 아닌 행이 있으면 종료코드 1

판정은 **실제 명령의 출력으로만** 한다.
  · QA 리포트(outputs/…md)는 표지 `<!-- gate:G-nn -->` 바로 다음 줄 하나만 판정 행으로 읽는다 (DEF-QA2-008). 표지가 없으면
    `미검증 — QA 재검증 필요(리포트 형식)`. 리포트에 붙인 `make gate` 출력 같은 다른 판정 꼴 줄은 읽지 않는다.
  · 모든 게이트에 대해 QA 리포트 묶음(`outputs/qa*-*.md` · `outputs/e2e/self-observe*.md`, 묶음 = 이름에서 `-rN` 을 뗀 것)마다
    그 게이트 표지가 있는 **가장 최근 회차**(N 이 큰 것, 없으면 원본) 하나를 읽는다. 개발 도구 판정과 QA 판정이 다르면
    **더 나쁜 쪽** (PASS < 미검증 < WARN < FAIL, BLOCKED 은 FAIL 다음 · 출처 표시). 실측 칸에 읽은 파일을 적는다 (DEF-QA1-103).
    GATES 의 ("qa", "") 는 「QA 판정 필수」 — 표지가 하나도 없으면 미검증.
  · 검사기(src/agentdash/tools/check_*.py)가 있으면 돌려서 그 출력의 `G-nn  항목  PASS|FAIL|WARN|BLOCKED|미검증  실측` 행을 읽는다.
    한 게이트에 행이 여럿이면 FAIL > BLOCKED > WARN > 미검증 > PASS.
  · 게이트가 테스트 파일로 정의돼 있으면(goal.md §2 「검증」 열) 그 파일만 pytest 로 돌린다.
  · 검사기 · 테스트 파일이 아직 없으면 FAIL + "없음 — 담당 …" (개발 몫) 또는 미검증 + 사유 (QA · 사람 몫).
  · **통과한 것처럼 보이게 하지 않는다.** 증거가 없으면 FAIL/미검증. 기대값을 낮추지 않는다.
  · decisions.md 에 `상태: 차단` 인 D-번호가 언급한 게이트는 PASS/FAIL 이 아닐 때 BLOCKED.
  · 안전 게이트 G-13~G-16 은 Phase 0 부터 실제로 판정한다.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
SCRIPTS = ROOT / "scripts"

PASS, FAIL, WARN, BLOCKED, UNVERIFIED = "PASS", "FAIL", "WARN", "BLOCKED", "미검증"
_RANK = {FAIL: 4, BLOCKED: 3, WARN: 2, UNVERIFIED: 1, PASS: 0}
_ROW = re.compile(r"^\s*(G-\d{2})\s+(.*?)\s{2,}(PASS|FAIL|WARN|BLOCKED|미검증)(?=\s|$)\s*(.*)$")
#: QA 리포트 판정 블록 표지 (DEF-QA2-008, CLAUDE.md 「QA 리포트 형식」) — 이 줄 **바로 다음 줄 하나** 만 판정 행으로 읽는다.
_QA_MARK = re.compile(r"^\s*<!--\s*gate:(G-\d{2})\s*-->\s*$")
QA_FORMAT_NOTE = "— QA 재검증 필요(리포트 형식)"

#: QA 리포트 묶음 (DEF-QA1-103) — ROOT 기준 glob. 회차 = 파일 이름 끝 `-rN` (없으면 0).
QA_GLOBS = ("outputs/qa*-*.md", "outputs/e2e/self-observe*.md", "outputs/e2e/alerts*.md", "outputs/e2e/design*.md",
            "outputs/e2e/twin*.md")
_ROUND = re.compile(r"^(?P<base>.+?)(?:-r(?P<n>\d+))?\.md$")

#: (게이트, 항목, 담당, 판정 수단). 수단 = ("tool", 이름) | ("test", 파일) | ("qa", "" = QA 판정 필수 · 또는 리포트 경로)
#: 목록 — 전부 통과해야 PASS. QA 리포트 판정은 수단과 무관하게 모든 게이트에 더한다 (qa_latest).
GATES: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("G-01", "골격 — make setup · 테이블 11", "아키텍트", [("test", "test_schema.py"), ("db", "tables")]),
    ("G-02", "파서 회귀 — 픽스처 S1~S6 · S9 (V-08)", "개발1", [("test", "test_parsers.py")]),
    ("G-03", "증분 읽기 — 추가분 · 반쪽 줄 · inode", "개발1", [("test", "test_tail.py")]),
    ("G-04", "전체 수집 — agent 행 = 원천 파일 수 (V-01)", "개발1", [("tool", "check_counts")]),
    ("G-05", "파싱 오류율 ≤ 0.1% (V-07)", "개발1", [("tool", "check_parse_errors")]),
    ("G-06", "부모 연결 ≥ 95% (V-02)", "개발2", [("tool", "check_link_rate")]),
    ("G-07", "토큰 합 — 표본 10 세션 (V-03)", "개발1", [("tool", "check_usage_sum")]),
    ("G-08", "비용 — 표본 20 건 손계산 (V-09)", "개발1", [("tool", "check_cost"), ("test", "test_cost.py")]),
    ("G-09", "판정 규칙 13 — 표 기반 테스트", "개발2", [("test", "test_state.py")]),
    ("G-10", "연결 규칙 L-01~L-07 테스트", "개발2", [("test", "test_linker.py")]),
    ("G-11", "실시간 — SSE 5 초 · 훅 1 초", "개발2", [("test", "test_realtime.py")]),
    ("G-12", "상태 대조 — 표본 30 오판 ≤ 2", "QA2", [("qa", "")]),
    ("G-13", "본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)", "아키텍트", [("tool", "check_no_payload"),
                                                                    ("script", "check_fixtures_redacted")]),
    ("G-14", "원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)", "아키텍트", [("tool", "check_readonly")]),
    ("G-15", "훅 설치 안전 — 가짜 settings (V-10)", "개발2", [("tool", "check_hooks"),
                                                          ("test", "test_hooks_install.py")]),
    ("G-16", "로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)", "아키텍트", [("tool", "check_bind")]),
    ("G-17", "화면 7 · API 14 — HTTP 200", "개발1·2", [("tool", "check_routes")]),
    ("G-18", "구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3", "개발2", [("test", "test_graph.py"),
                                                                ("qa", "")]),
    ("G-19", "진척 판정 — P-01~P-07 · 고려솔더 (V-11)", "개발1", [("tool", "check_pipeline"),
                                                              ("test", "test_pipeline.py")]),
    ("G-20", "비용 화면 — [추정] 표기 · 단가 없음 · reprice", "개발1", [("test", "test_usage_page.py")]),
    ("G-21", "브라우저 — 콘솔 오류 0 · 390px", "QA2", [("qa", "")]),
    ("G-22", "자기 관찰 — 루프 서브에이전트 RUNNING → DONE", "QA2", [("qa", "")]),
    # ── 2차-A (goal.md §2.2 · 계획 docs/superpowers/plans/2026-10-20-agentdash-v2a.md) ──
    ("G-23", "결정 반영 — D-07·08·13·14·17·18·19 확정", "아키텍트·개발2", [("tool", "check_decisions")]),
    ("G-24", "추정 열 — output_est · cost_est_usd (V-12)", "개발1", [("test", "test_usage_est.py"),
                                                              ("tool", "check_usage_est")]),
    ("G-25", "하드 링크 DB 거부 (DEF-QA1-201 · V-05)", "아키텍트", [("test", "test_settings.py")]),
    ("G-26", "예산 — 80/100 % · KST 일/월 (V-13)", "개발1", [("test", "test_budget.py"), ("tool", "check_budget")]),
    ("G-27", "추세 — 일·주·월 합 (V-14)", "개발1", [("tool", "check_trend")]),
    ("G-28", "캐시 적중률 — 표본 10 손계산 (V-15)", "개발1", [("tool", "check_efficiency")]),
    ("G-29", "알림 — WAITING 전이 1 회", "개발2·QA2", [("test", "test_alerts.py"), ("qa", "")]),
    ("G-30", "디자인 — 두 테마 대비 · 390px (V-16)", "아키텍트·개발1·2·QA2", [("tool", "check_contrast"),
                                                                          ("test", "test_design.py"), ("qa", "")]),
    # ── 2차-T 디지털 트윈 (goal.md §2.2 · 계획 docs/superpowers/plans/2026-10-21-agentdash-twin.md) ──
    ("G-31", "배치 규칙 T-01~T-07 + Review Focus 5", "개발2", [("test", "test_twin.py")]),
    ("G-32", "트윈 API — 누적 · 스파크 · 겹침 0 (V-17)", "개발1·2", [("tool", "check_twin")]),
    ("G-33", "트윈 실시간 — 새 설비 5 초 · 표시등 1 초 · 역흐름", "개발2·QA2", [("test", "test_realtime.py"),
                                                                         ("qa", "")]),
    ("G-34", "관제판 흡수 — v0.3 항목 · test_dashboard 무삭제", "개발2·QA2", [("test", "test_dashboard.py"),
                                                                       ("qa", "")]),
    ("G-35", "트윈 시각 — 정적 계약 · 두 테마 · 390/1400 · 움직임 0", "개발2·QA2", [("test", "test_twin_page.py"),
                                                                            ("qa", "")]),
]


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout {timeout}s"


def last_line(out: str, n: int = 110) -> str:
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    return (lines[-1] if lines else "")[:n]


def rows_of(out: str, gid: str) -> list[tuple[str, str]]:
    res = []
    for ln in out.splitlines():
        m = _ROW.match(ln)
        if m and m.group(1) == gid:
            res.append((m.group(3), m.group(4).strip()))
    return res


def qa_rows(text: str, gid: str) -> list[tuple[str, str]]:
    """QA 리포트 → 그 게이트의 판정 행. 표지 `<!-- gate:G-nn -->` 바로 다음 줄이 같은 G-nn 판정 행일 때만 읽는다.
    리포트의 다른 판정 꼴 줄(붙여 넣은 `make gate` 출력 · 옛 판정)은 읽지 않는다 (DEF-QA2-008)."""
    lines = text.splitlines()
    res = []
    for i, ln in enumerate(lines):
        m = _QA_MARK.match(ln)
        if not m or m.group(1) != gid:
            continue
        r = _ROW.match(lines[i + 1]) if i + 1 < len(lines) else None
        if r and r.group(1) == gid:
            res.append((r.group(3), r.group(4).strip()))
        else:
            res.append((UNVERIFIED, f"{QA_FORMAT_NOTE}: <!-- gate:{gid} --> 다음 줄이 {gid} 판정 행 아님"))
    return res


def round_of(name: str) -> tuple[str, int]:
    """파일 이름 → (묶음, 회차). `qa1-데이터안전-r2.md` → ("qa1-데이터안전", 2) · 접미사 없으면 0."""
    m = _ROUND.match(name)
    if not m:
        return name, 0
    return m.group("base"), int(m.group("n") or 0)


def _rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def qa_latest(gid: str, extra: list[Path] | None = None) -> list[tuple[str, str, str]]:
    """그 게이트의 QA 판정 — 묶음마다 표지가 있는 가장 최근 회차 파일 하나. [(파일, 판정, 실측)]."""
    files = {p for g in QA_GLOBS for p in ROOT.glob(g) if p.is_file()} | set(extra or [])
    fams: dict[tuple[str, str], list[tuple[int, Path]]] = {}
    for p in files:
        base, n = round_of(p.name)
        fams.setdefault((p.parent.as_posix(), base), []).append((n, p))
    out = []
    for key in sorted(fams):
        for _, p in sorted(fams[key], key=lambda x: -x[0]):
            rows = qa_rows(p.read_text(encoding="utf-8"), gid)
            if rows:
                st, detail = combine(rows)
                out.append((_rel(p), st, detail))
                break
    return out


def combine(items: list[tuple[str, str]]) -> tuple[str, str]:
    st = max((s for s, _ in items), key=lambda s: _RANK[s])
    detail = " ‖ ".join(d for _, d in items if d)
    return st, detail[:400]


def judge(gid: str, owner: str, means: list[tuple[str, str]], cache: dict) -> tuple[str, str]:
    results: list[tuple[str, str]] = []
    explicit: list[Path] = []
    qa_required = False
    for kind, name in means:
        if kind == "db":
            from agentdash import settings as _s
            from agentdash.db import conn

            db = _s.get().db_path
            if not db.exists():
                results.append((FAIL, f"DB 없음 {db.name} — make setup"))
                continue
            c = conn.connect(db)
            n = len(conn.tables(c))
            c.close()
            results.append((PASS if n == 11 else FAIL, f"{db.name} 테이블 {n}"))
        elif kind == "test":
            path = TESTS / name
            if not path.exists():
                results.append((FAIL, f"tests/{name} 없음 — 담당 {owner}"))
                continue
            code, out = run(["uv", "run", "pytest", "-q", str(path)])
            results.append((PASS if code == 0 else FAIL, f"tests/{name}: {last_line(out, 80)}"))
        elif kind in ("tool", "script"):
            path = (TOOLS if kind == "tool" else SCRIPTS) / f"{name}.py"
            if not path.exists():
                results.append((FAIL, f"{path.relative_to(ROOT)} 없음 — 담당 {owner}"))
                continue
            if path not in cache:
                cache[path] = run(["uv", "run", "python", str(path)])
            code, out = cache[path]
            rows = rows_of(out, gid)
            if rows:
                results.extend(rows)
            else:
                results.append((FAIL, f"{name}: {gid} 행 없음 (종료코드 {code}) {last_line(out, 80)}"))
        elif kind == "qa":
            qa_required = True
            if name:
                path = ROOT / name
                if not path.exists():
                    results.append((UNVERIFIED, f"{name} 없음 — QA 리포트 대기 (웨이브 C)"))
                    continue
                explicit.append(path)
    # QA 리포트 판정 (DEF-QA1-103) — 모든 게이트, 묶음마다 최근 회차. 개발 판정과 더 나쁜 쪽.
    qa = qa_latest(gid, explicit)
    if qa_required and not qa:
        # QA 판정 필수 게이트는 개발 판정이 PASS 여도 표지가 없으면 미검증 (2차-A — G-29 · G-30 의 E2E 를 건너뛰지 않게)
        if not any(s == UNVERIFIED for s, _ in results):
            where = ", ".join(_rel(p) for p in explicit) or " · ".join(QA_GLOBS)
            results.append((UNVERIFIED, f"{QA_FORMAT_NOTE}: {where} 에 <!-- gate:{gid} --> 표지 판정 행 없음"))
    if not qa:
        return combine(results)
    qa_st, _ = combine([(s, d) for _, s, d in qa])
    qa_detail = " ‖ ".join(f"QA {f} {s}: {d}" for f, s, d in qa)
    if not results:                     # QA 몫 게이트 — 판정 실측 뒤에 읽은 파일
        return qa_st, " ‖ ".join(f"{d[:300]} (QA {f})" for f, s, d in qa)[:480]
    dev_st, dev_detail = combine(results)
    st = max((dev_st, qa_st), key=lambda s: _RANK[s])
    tag = f"개발 {dev_st} · QA {qa_st}" + (" (BLOCKED 쪽 있음)" if BLOCKED in (dev_st, qa_st) else "")
    return st, f"{tag} ‖ {qa_detail[:220]} ‖ 개발: {dev_detail}"[:480]


def blocked_gates() -> dict[str, str]:
    path = ROOT / "decisions.md"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    cur, blocked, body = None, False, []

    def flush() -> None:
        if cur and blocked:
            for m in re.finditer(r"\b(G-\d{2})\b", "\n".join(body)):
                out.setdefault(m.group(1), cur)

    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (D-\d+)\b", ln)
        if m:
            flush()
            cur, body, blocked = m.group(1), [ln], False
            continue
        if re.search(r"상태\W*\s*차단", ln):
            blocked = True
        body.append(ln)
    flush()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    blocked = blocked_gates()
    cache: dict = {}
    table = []
    for gid, item, owner, means in GATES:
        st, detail = judge(gid, owner, means, cache)
        if st not in (PASS, FAIL) and gid in blocked:
            st, detail = BLOCKED, f"{blocked[gid]} 차단 — {detail}"
        table.append((gid, item, st, detail))
    print(f"# make gate — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (goal.md §2)")
    w = max(len(i) for _, i, _, _ in table)
    for gid, item, st, detail in table:
        print(f"{gid}  {item.ljust(w)}  {st}  {detail}")
    cnt = {s: sum(1 for *_, x, _ in table if x == s) for s in (PASS, FAIL, WARN, BLOCKED, UNVERIFIED)}
    print("# 합계 " + " · ".join(f"{k} {v}" for k, v in cnt.items()))
    if a.strict and cnt[PASS] != len(table):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
