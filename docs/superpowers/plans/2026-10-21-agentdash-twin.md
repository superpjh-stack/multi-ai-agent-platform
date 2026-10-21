# 멀티 에이전트 대시보드 2차-T (디지털 트윈) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 이 저장소에서는 `goal.md` (2차-T) 루프가 이 계획을 실행한다 — 웨이브 · 소유자 · 게이트는 `goal.md`, 태스크 단위는 이 문서.

**Goal:** D-01 관제판을 디지털 트윈 공장 평면도로 바꾸고(라인 · 설비 · 배관 · 컨베이어, 실시간 표시등 · 스파크 · 흐름), G-01~G-35 전부 PASS.

**Architecture:** `core/twin.py` 가 §5.4 T-01~T-07 로 라인 · 설비 좌표를 결정적으로 계산하고, `routers/twin.py` 가 `/api/v1/twin` 으로 낸다. 스파크는 개발1 의 `usage.spark` 가 `usage_event` 에서 분 단위로 모은다. D-01 은 서버가 평면도 SVG 틀과 패널(기존 관제판 항목)을 렌더하고, `_twin.html` 스크립트가 API 를 받아 SVG 를 그리고 공유 SSE 로 표시등 · 배관 흐름을 갱신한다.

**Tech Stack:** Python 3.12 · FastAPI · Jinja2 · SQLite · pytest · SVG + CSS 애니메이션 + 순수 JS (새 라이브러리 없음)

**Spec:** `spec.md` v0.4 (§5.4 · §7 D-01 · §7.4 · §8 · §10 V-17 · §13 15~17) · 설계 `docs/superpowers/specs/2026-10-21-agentdash-twin-design.md`

## Global Constraints

- 원천 읽기 전용 · 본문 미저장 · TEXT ≤ 300 · 로컬 전용 · 외부 전송 0 · 명령 `uv run …` (CLAUDE.md 절대 규칙 그대로).
- 새 JS · CSS 라이브러리 · CDN 0 (spec §7.4). 색은 base.html 토큰(`--st-*` · `--bg` · `--surface` · `--fg` · `--muted` · `--line` · `--accent`)만.
- 배치 상수 (spec T-04 「상수」 — 값은 이 계획이 정한다): `BOX_W = 208` · `BOX_H = 92` · `GAP_X = 56` · `GAP_Y = 16` · `LINE_HEAD = 36` · `LINE_PAD = 16` · `LINE_GAP = 24`.
- 접기: `FOLD_AFTER_SEC = 1800` (T-05) · `MACHINE_LIMIT = 300` (T-06) · 범위 기본 `since = 24h` (core.graph.parse_since 재사용).
- 스파크: 30 칸 · 1 분 단위 · 값 = `COALESCE(output_est, output_tokens)` 합 · `model != '<synthetic>'` · 가장 오래된 칸 → 지금 분.
- 이름 앞 24 자 · 표기 `[추정]` · 「+N 완료」.
- 실시간: `agent.state` 즉시 · `agent.new`/`edge.new` 1 초 묶음 · `agent.usage` 5 초 묶음 · SSE 탭당 1 (`agentdashAlerts.subscribe` / `_live.html openStream` 공유).
- 애니메이션: RUNNING 2 s 맥박 · WAITING_* 경광등 + `!` · STALE 1 s 깜빡임 · DONE/FAILED 흐림 · spawn 흐름 · handback 역흐름 · `prefers-reduced-motion: reduce` → 0 · `document.hidden` → 입자 멈춤.
- 소유: `core/twin.py` · `routers/twin.py` · `templates/_twin.html` · `tests/test_{twin,twin_page}.py` = 개발2 · `usage.spark` (`core/usage.py`) · `tools/check_twin.py` = 개발1 · 게이트 · CLAUDE.md · main.py = 아키텍트.

## Review Focus

1. **부모가 다른 프로젝트(라인)에 있는 서브에이전트** — 그 자식은 자기 라인의 미확인 반입구 아래 1 열에 두고, 부모 쪽으로 라인 간 배관을 `links` 에 `kind="spawn"` 으로 낸다. 사라지거나 두 번 그려지면 안 된다 → Task 3 `test_cross_line_parent`.
2. **부모 사슬 순환 · 자기 부모 (깨진 데이터)** — 무한 루프 없이 한 번만 배치, 순환을 끊은 설비는 반입구 아래 → Task 3 `test_parent_cycle_terminates`.
3. **뿌리(세션)가 DONE 이고 30 분 넘음** — 뿌리는 T-05 로 접지 않는다(접을 부모가 없다). 자식만 접힌다 → Task 3 `test_root_never_folded`.
4. **긴 이름 · 한글 · 이모지 이름** — 24 자에서 자르고 상자 밖으로 안 넘친다(서버 자르기 + SVG clipPath) → Task 3 `test_name_clip_24` · Task 6 정적 계약.
5. **평면도에 없는 에이전트의 SSE 이벤트(필터 밖 · 접힘)** — 오류 없이 다시 받기만 → Task 6 정적 계약(`machineEl(key)` 없으면 `soon()`) + G-33 E2E.
6. (덤) **`state_since` 가 미래 · 시계 어긋남** — `elapsed_s` 는 0 으로 클램프 → Task 3 `test_elapsed_clamped`.

---

## Phase 0 — 아키텍트

### Task 1: 게이트 G-31~G-35 · 트윈 라우터 자리 · 문서

**Files:**
- Modify: `src/agentdash/tools/gate.py` (GATES 에 G-31~G-35 · G-17 항목명 `화면 7 · API 14` · QA_GLOBS 에 `outputs/e2e/twin*.md`)
- Create: `src/agentdash/app/routers/twin.py` — **자리만**: `router = APIRouter()` · `GET /api/v1/twin` → `placeholders.api("개발2", lines=[], links=[], folded_lines=0)`. 만든 뒤 **소유는 개발2** (CLAUDE.md 표에 기록).
- Modify: `src/agentdash/app/main.py` (`ROUTERS` 에 `twin`), `Makefile` (`check-twin`), `CLAUDE.md` (2차-T · 규모 API 14 · 검증 17 · 배치 규칙 7 · 게이트 35 · 새 소유 파일)
- Test: `tests/test_gate.py`

**Interfaces:**
- Produces: GATES — G-31 `[("test","test_twin.py")]` · G-32 `[("tool","check_twin")]` · G-33 `[("test","test_realtime.py"),("qa","")]` · G-34 `[("test","test_dashboard.py"),("qa","")]` · G-35 `[("test","test_twin_page.py"),("qa","")]`.

- [ ] **Step 1:** `test_gate.py::test_gates_cover_g01_to_g35` (G-01..G-35 연속 35 행) · `test_routes.py` 가 API 14 를 센다(spec 에서 읽으므로 자동).
- [ ] **Step 2:** FAIL 확인 → **Step 3:** 구현 → **Step 4:** `uv run pytest -q` PASS · `make gate` 35 행 (G-31 · G-32 FAIL, G-33~G-35 미검증/FAIL 정상, G-17 PASS · placeholder 1).
- [ ] **Step 5:** commit `Phase 0 (2차-T): gate G-31~G-35 · twin 라우터 자리 · API 14`

---

## 웨이브 A

### Task 2 (개발1): `usage.spark`

**Files:** Modify `src/agentdash/core/usage.py` · `tests/test_usage.py` · `progress-dev1.md` §1 공표

**Interfaces:**
- Produces: `usage.SPARK_MINUTES = 30` · `usage.spark(con, keys: list[str], now: datetime, minutes: int = SPARK_MINUTES) -> dict[str, list[int]]` — 키마다 길이 `minutes` 리스트, 칸 i = `[now_floor − (minutes−1−i) 분, +1 분)` 의 `COALESCE(output_est, output_tokens)` 합, `<synthetic>` 제외, 기록 없는 키도 0 리스트.

- [ ] **Step 1:** `test_spark_buckets` (now = 10:30:20Z, 이벤트 10:30:05 → 마지막 칸 · 10:01:00 → 첫 칸 · 10:00:59 → 제외 · output_est 있는 행은 그 값) · `test_spark_synthetic_excluded` · `test_spark_unknown_key_zeros` · `test_spark_sum_equals_events` (임의 50 행 합 = 직접 SQL 합).
- [ ] **Step 2:** FAIL → **Step 3:** 구현 (한 번의 GROUP BY 쿼리, `at` ISO 문자열 비교) → **Step 4:** `uv run pytest -q` PASS → **Step 5:** commit + 공표 `웨이브 A (2차-T): usage.spark`

### Task 3 (개발2): `core/twin.py` 배치

**Files:** Create `src/agentdash/core/twin.py` · `tests/test_twin.py`

**Interfaces:**
- Consumes: `core.graph.parse_since` · `core.graph.project_label` · `usage.totals` · `usage.spark` (Task 2 — 공표 전엔 같은 시그니처의 가짜로 테스트, 공표 뒤 실제로).
- Produces: `twin.build(con, *, since: str | None = None, project: str | None = None, now: datetime | None = None, limit: int = MACHINE_LIMIT) -> dict` — spec §8 `/api/v1/twin` 응답 그대로 (`box = {x, y, w, h}` 정수 · 라인 `box` 는 그 라인 설비를 감쌈 · `elapsed_ms` 별도 키로 계산 시간). 상수는 Global Constraints.
- Produces: `twin.overlaps(resp) -> int` (설비 상자 쌍 겹침 수 — check_twin · 테스트 공용).

- [ ] **Step 1: 표 기반 테스트** (가짜 DB 에 agent · edge · usage_event 직접 삽입)
  - `test_T01_line_order` — 살아 있는 라인 > 최근 last_event > 이름.
  - `test_T02_column_is_chain_depth` — 세션 0 · 자식 1 · 손자 2 (agent.depth 와 달라도 사슬 기준).
  - `test_T03_rows_dfs_by_started` — 부모 A 아래 자식 B(10:00) · C(09:00) · B 의 자식 D → 행 순서 A, C, B, D.
  - `test_T04_no_overlap_300` — 합성 300 설비(라인 7 · 깊이 ≤ 4) → `overlaps == 0`.
  - `test_T05_fold_done_after_30m` — DONE · ended 31 분 전 → 칸 없음 · 부모 `folded == 1` (자손 포함 수) · 29 분 전 → 칸 있음.
  - `test_T06_fold_lines_over_limit` — limit=10 · 설비 14 → 뒤 라인 접힘 · `folded_lines ≥ 1` · 남은 설비 ≤ 10.
  - `test_T07_deterministic` — 같은 DB · 같은 now 두 번 → 응답 dict 동일 (`elapsed_ms` 제외).
  - `test_machine_values` — `out_est_total` · `cost_est_usd` = `usage.totals(con, key)` 자기 몫 · `spark` = `usage.spark` · `tool`/`target` = 결과 없는 마지막 tool_call.
  - Review Focus: `test_cross_line_parent` · `test_parent_cycle_terminates` · `test_root_never_folded` · `test_name_clip_24` · `test_elapsed_clamped`.
  - `test_build_300_under_300ms` — 합성 300 설비 `elapsed_ms ≤ 300`.
- [ ] **Step 2:** `uv run pytest tests/test_twin.py -q` FAIL
- [ ] **Step 3:** 구현 — 에이전트 · 엣지 · 사용량을 쿼리 몇 번으로 읽고(설비마다 쿼리 금지), 라인별 트리를 `visited` 로 깊이 우선 배치.
- [ ] **Step 4:** PASS + `uv run pytest -q` 전체 PASS
- [ ] **Step 5:** commit `웨이브 A (2차-T): core/twin 배치 T-01~T-07`

### Task 4 (개발2): `/api/v1/twin`

**Files:** Modify `src/agentdash/app/routers/twin.py` (placeholder 제거) · `tests/test_twin.py`

**Interfaces:** `GET /api/v1/twin?since=&project=` → `twin.build(...)`. 잘못된 `since` → 422.

- [ ] **Step 1:** `test_twin_api_empty_db_200` (`_placeholder` 키 없음 · `lines == []`) · `test_twin_api_matches_build` · `test_twin_api_bad_since_422` · `test_twin_text_le_300` (응답의 모든 문자열 ≤ 300).
- [ ] **Step 2–4:** FAIL → 구현 → `uv run pytest -q` PASS · `check_routes` placeholder 0.
- [ ] **Step 5:** commit · `progress-dev2.md` §1 에 응답 키 공표 `웨이브 A (2차-T): /api/v1/twin`

### Task 5 (개발1, Task 4 공표 뒤): `check_twin` (V-17)

**Files:** Create `src/agentdash/tools/check_twin.py`

**Interfaces:** 출력 `G-32  트윈 API  PASS|FAIL  설비 n · 라인 n · 접힘 n+n · 누적 불일치 n · 스파크 불일치 n · 겹침 n · TEXT>300 n · n ms`. 실제 DB(AGENTDASH_DB)에서 `twin.build` 를 부르고, 설비마다 누적을 `usage.totals` 와, 스파크 칸 합을 **직접 SQL** 분 단위 합과(`usage.spark` 를 쓰지 않는 독립 계산) 비교, `twin.overlaps`, 범위 안 에이전트 수 = 칸 수 + 접힌 수.

- [ ] **Step 1:** `tests/test_check_twin.py` (가짜 DB 로 PASS 한 번 · 스파크 값 하나를 틀리게 만든 몽키패치로 FAIL 한 번).
- [ ] **Step 2–4:** FAIL → 구현 → 테스트 PASS · dev1 DB 로 실행 PASS.
- [ ] **Step 5:** commit `웨이브 A (2차-T): check_twin (V-17)`

---

## 웨이브 B — 개발2

### Task 6: D-01 공장 평면도 화면

**Files:**
- Modify: `src/agentdash/app/templates/dashboard.html` (평면도 카드 + 패널 배치) · `_d01_body.html` (패널 내용 — 기존 항목 그대로 + 「선택한 설비」 칸) · `src/agentdash/app/routers/pages.py` (title 「공장 평면도」)
- Create: `src/agentdash/app/templates/_twin.html` (SVG 그리기 · 갱신 · 애니메이션 · 확대/이동 · 키보드 · 화면 낭독기 표) · `tests/test_twin_page.py`

**Interfaces:**
- Consumes: `/api/v1/twin` (Task 4) · 공유 SSE (`_live.html` `openStream`) · base.html 토큰.
- Produces: 전역 `window.agentdashTwin = {render(resp), machineEl(key), redraws, flows}` (E2E 가 읽는다) · SVG `#twin-svg` · 설비 `g.machine[data-key][data-state]` · 배관 `path.pipe[data-kind]` · CSS 클래스 `.lamp` · `.beacon` · `.alarm` · `.flow` · `@media (prefers-reduced-motion: reduce)` 블록.

- [ ] **Step 1: 정적 계약 · 회귀 테스트** (`test_twin_page.py`)
  - `test_d01_has_floor_and_panel` — `/` HTML 에 `#twin-svg` · 패널 항목 전부(상태 카드 · 내 차례 · 복사 버튼 · 오늘 KPI · 상위 5 · 피드 · 파싱 오류 · 예산 띠 자리) · 「선택한 설비」.
  - `test_reduced_motion_block` — `prefers-reduced-motion: reduce` 안에서 `.lamp` · `.beacon` · `.alarm` · `.flow` 의 `animation: none`.
  - `test_no_external_script_and_one_eventsource` — 외부 `<script src=` 는 base.html 기존 것만 · `new EventSource(` 1.
  - `test_machine_accessibility_contract` — `_twin.html` 에 `role`,"button" · `tabindex` · `aria-label` · Enter 키 처리 · 숨김 표 `#twin-table`.
  - `test_unknown_key_event_refetches` — 스크립트에 `machineEl` 없음 → `soon()` 경로 문자열.
  - 기존 `tests/test_dashboard.py` 전부 회귀 PASS (G-34).
- [ ] **Step 2:** FAIL 확인
- [ ] **Step 3:** 구현 — 서버는 틀만, 그림은 클라이언트가 응답 좌표대로. 설비 상자 = 표시등 원 · 이름 · 상태줄 · 스파크 polyline · 누적줄 · 「+N 완료」. 배관 = 부모 상자 오른쪽 가운데 → 자식 상자 왼쪽 가운데 꺾은선. 흐름 = `stroke-dashoffset` 애니메이션. 확대/이동 = `viewBox` 조작. 테마 바뀜 → 다시 칠함(D-02 와 같은 신호).
- [ ] **Step 4:** `uv run pytest -q` PASS · `check_contrast` PASS. 브라우저(가짜 루트 서버 8097): 두 테마 · 390/1400 px · reduced-motion · 키보드 순회 · 새 서브에이전트 spawn → 흐름 · handback → 역흐름 + DONE 을 직접 보고 `progress-dev2.md` 에 숫자로. 스크린샷 `outputs/e2e/dev2-twin/` (커밋 안 함).
- [ ] **Step 5:** commit `웨이브 B (2차-T): D-01 공장 평면도`

---

## 웨이브 C — QA (고치지 않는다)

### Task 7: QA1 (`outputs/qa1-데이터안전-r5.md`)
- [ ] G-32 독립 재계산(자기 스크립트로 누적 · 스파크 · 접힘 수 · 겹침), G-31 테스트 표를 spec §5.4 글자와 대조, G-13~G-16 · G-24~G-28 회귀. 표지 `<!-- gate:G-nn -->`.

### Task 8: QA2 (`outputs/qa2-상태대조-r5.md` · `outputs/e2e/twin.md` · `outputs/e2e/self-observe-r6.md`)
- [ ] G-33 (가짜 루트: 새 세션 + 서브 2 → 평면도 ≤ 5 초 · 훅 상태 → 표시등 ≤ 1 초 · handback → 역흐름 + DONE) · G-34 (v0.3 관제판 항목 대조 · 알림 · 예산 띠 회귀) · G-35 (두 테마 · 390/1400 · reduced-motion 움직임 0 · 키보드 · 콘솔 0) · G-21 · G-22 (평면도에서 자기 관찰) · G-12 표본 재대조.

## 웨이브 D — 결함 수정 → C 반복 (goal.md §4)
