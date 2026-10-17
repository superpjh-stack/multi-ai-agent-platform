#!/usr/bin/env python
"""QA1 — 가짜 agents_root(스크래치)로 미등록 회사 · NFD · 별칭 · 제외 폴더 · P-05 처리를 개발 코드에 직접 먹여 본다.
    uv run python outputs/qa1/pipe_fake.py <빈 스크래치 폴더>
원천은 건드리지 않는다 (AGENTDASH_AGENTS_ROOT 를 스크래치로). DB 는 쓰지 않는다 (evaluate(con=None))."""
import os, sys, unicodedata
from pathlib import Path
root = Path(sys.argv[1]); assert not any(root.iterdir()) if root.exists() else True
os.environ["AGENTDASH_AGENTS_ROOT"] = str(root)
os.environ["AGENTDASH_CLAUDE_HOME"] = str(root / "_claude")
def touch(rel, nfd=False):
    p = root / (unicodedata.normalize("NFD", rel) if nfd else rel)
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"")
for n in ("00 PM Agent", "01 Analyze Agent", "02 Design Agent", "03 UI Agent", "04 QA Agent", "05 Open Agent", "06 Coding Agent", "08 AI Agent Making Agent"):
    (root / n / "outputs").mkdir(parents=True, exist_ok=True)
# 미등록 회사 두손푸드 — 03 파일명 · 00 pm 폴더
touch("03 UI Agent/outputs/두손푸드_제조AI_화면설명서_v1.0.html")
touch("00 PM Agent/outputs/pm-두손푸드/12.SF-PM1_월간보고서_두손푸드_v1.0.docx")
# NFD 파일 이름 (니즈푸드 04 7 개 중 3 개 NFD)
for i, d in enumerate(["단위테스트결과서", "통합테스트결과서", "시스템전환결과서", "메뉴얼", "사용자테스트결과서", "운영지원계획서", "운영현황보고서"]):
    touch(f"04 QA Agent/outputs/니즈푸드_스마트공장_{d}_v1.0.docx", nfd=i < 3)
# 별칭 · 법인격: '주식회사 고려솔더' 는 파일명 {회사} 자리에 공백 → 별칭 '송월' 로 03
touch("03 UI Agent/outputs/송월_제조AI_화면설명서_v1.0.html")
# 제외 폴더 안 파일은 세지 않음
touch("03 UI Agent/outputs/_구판_20260902/광성정밀_제조AI_화면설명서_v1.0.html")
touch("03 UI Agent/outputs/tour/광성정밀_제조AI_화면정의서_v1.0.pptx")
# P-05: 01 progress 표제 완료 · 파일 없음
(root / "01 Analyze Agent/progress.md").write_text("# x\n\n## 원터치 분석 — 완료 (2026-09-13)\n", encoding="utf-8")
# P-01: 03 progress 지금 해야 할 것 + 표 행
(root / "03 UI Agent/progress.md").write_text("# x\n\n## 지금 해야 할 것\n\n| 엘컴화인 | 화면 | 사용자 판단 |\n\n## 기록\n### 와이엔프린팅 — 확인 필요\n", encoding="utf-8")
from agentdash.core import pipeline as P
r = P.evaluate(con=None, root=root)
cell = {(c.company, c.stage): c for c in r.cells}
print("미등록", r.unregistered and sorted(r.unregistered), "· 건수", len(r.unregistered))
print("니즈푸드 04", cell[("니즈푸드", "04")].status, cell[("니즈푸드", "04")].have, cell[("니즈푸드", "04")].need)
print("송월타월서울상사 03 (별칭 송월)", cell[("송월타월서울상사", "03")].status, cell[("송월타월서울상사", "03")].have)
print("광성정밀 03 (제외 폴더만)", cell[("광성정밀", "03")].status, cell[("광성정밀", "03")].have)
print("원터치 01 (P-05)", cell[("원터치", "01")].status, cell[("원터치", "01")].rule, (cell[("원터치", "01")].note or "")[:30])
print("엘컴화인 03 (P-01 표 행)", cell[("엘컴화인", "03")].status, cell[("엘컴화인", "03")].rule)
print("와이엔프린팅 03 (지금 해야 할 것 밖 표제)", cell[("와이엔프린팅", "03")].status, cell[("와이엔프린팅", "03")].rule)
print("05 · 08", {c.status for c in r.cells if c.stage in ("05", "08")})
