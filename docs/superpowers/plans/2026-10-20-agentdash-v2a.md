# 멀티 에이전트 대시보드 2차-A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 이 저장소에서는 `goal.md` (2차-A) 루프가 이 계획을 실행한다 — 웨이브 · 소유자 · 게이트는 `goal.md` §2 · §3, 태스크 단위는 이 문서.

**Goal:** 1차(G-01~G-22 PASS) 위에 결정 확정 · D-17 추정 출력 · 예산 · 추세 · 캐시 적중률 · D-07 · WAITING 알림 · 공통 화면 틀을 더해 G-01~G-30 전부 PASS.

**Architecture:** 수집기가 요청별 길이 숫자만 메모리에서 모아 `usage_event.output_est · cost_est_usd` 를 채우고, `usage_daily` 가 그것을 일자별로 합친다. 새 `core/budget.py` 가 예산 · 추세 · 효율을 `usage_event`/`usage_daily` 에서 계산하고 `routers/insights.py` 가 D-07 과 API 3 으로 낸다. 알림은 서버 변경 없이 `base.html` 이 포함하는 `_alerts.html` 스크립트가 SSE 를 받아 띄운다.

**Tech Stack:** Python 3.12 · uv · FastAPI · Jinja2 · sse-starlette · SQLite(WAL) · pytest · Cytoscape.js 3.30.2 · Chart.js 4.4.1 (jsdelivr 고정)

**Spec:** `spec.md` v0.3 · `problem.md` (2차-A) · 설계 `docs/superpowers/specs/2026-10-20-agentdash-v2a-design.md`

## Global Constraints

- 원천(`settings.get().claude_home` · `.agents_root`)은 읽기만. 원천 경로 문자열을 코드에 쓰지 않는다 (CLAUDE.md 절대 규칙).
- 본문 미저장: DB TEXT ≤ 300 자. 길이 숫자도 DB 에 저장하지 않고 `output_est` 계산에만 쓴다 (spec §2.3).
- 의심 = 요청 기록 `output_tokens` 최대 **< 30** 이고 content 블록 `json.dumps` 길이 합 **> 400** (spec §6.2).
- `output_est = ceil((text 글자 수 + tool_use 입력 json.dumps(ensure_ascii=False) 글자 수) / 4)`, thinking 제외, `max(output_est, output_tokens)`.
- `model == "<synthetic>"` 는 토큰 · 비용 · 추정에서 뺀다.
- KST = UTC+9. 일 = KST 00:00, 주 = KST 월요일 00:00, 월 = KST 1 일 00:00.
- 예산 금액은 `config/budget.yaml` 에서만. 기본 `null` = `unset`. 코드에 금액 · 회사명을 쓰지 않는다.
- 예산 단계: `ok` < `warn_ratio`(0.8) ≤ `warn` < 1.0 ≤ `over`, 한도 `null` → `unset`.
- 캐시 적중률 = cache_read ÷ (input + cache_read + cache_write), 분모 0 → `None`.
- 표기 문자열: `추정 보정 (D-17)` · `[추정] API 정가 환산` · `한도 미설정` · `단가 없음 N 건`.
- 알림: `WAITING_INPUT` · `WAITING_PERMISSION` 전이만, `(agent_key, state_since)` 1 회, 첫 로드 0, 탭 여럿이면 1 탭.
- 화면 7 · API 13 · 테이블 11 · 판정 규칙 13 · 연결 규칙 7 · 진척 규칙 7 · 검증 16.
- 서버 `127.0.0.1` · 외부 전송 import 0 · CDN 고정 버전만 · 명령은 전부 `uv run …`.
- 한 파일은 한 사람만 (CLAUDE.md 소유 표). 새 파일 소유: `core/budget.py` · `routers/insights.py` · `templates/insights.html` · `tools/check_{usage_est,budget,trend,efficiency}.py` · `tests/test_{usage_est,budget,insights}.py` = 개발1, `templates/_alerts.html` · `tests/test_alerts.py` = 개발2, `config/budget.yaml` · `tools/check_{decisions,contrast}.py` · `tests/test_design.py` = 아키텍트.

## Review Focus

1. **한 요청이 두 번의 증분 읽기에 걸쳐 들어옴** — 같은 프로세스 안에서는 두 번에 나눠 읽어도 한 번에 읽은 것과 같은 `output_est` 여야 한다 → Task 5 `test_split_request_same_as_single_pass`.
2. **KST 자정 · 월 경계** — `14:59:59Z` 는 전날, `15:00:00Z` 는 다음 날, 10-31T15:00Z 는 11 월 → Task 7 `test_kst_day_month_boundary`.
3. **budget.yaml 의 프로젝트 이름이 기록에 없음(오타)** — 조용히 0 % 가 아니라 `기록 없음` 표시 → Task 7 `test_project_not_in_records`.
4. **단가 없는 모델이 예산 기간에 섞임** — 0 원으로 더하지 않고 `unpriced` 건수를 낸다 → Task 7 `test_unpriced_not_summed`.
5. **SSE 재연결 · 두 탭 · 권한 거부** — 같은 전이로 알림이 두 번 뜨지 않고, 거부 시 배지만 → Task 10 정적 계약 테스트 + G-29 브라우저 E2E.
6. (덤) **v0.2 스키마의 기존 DB** — 열이 없어 깨지지 않고 `init_db` 가 열을 덧붙인다 → Task 1 `test_init_db_adds_v03_columns`.

---

## Phase 0 — 아키텍트

### Task 1: 스키마 v0.3 · 열 덧붙이기 · 하드 링크 거부

**Files:**
- Modify: `src/agentdash/db/schema.sql` (usage_event · usage_daily 블록을 spec §3 v0.3 과 글자까지 같게)
- Modify: `src/agentdash/db/conn.py` (`init_db` 열 덧붙이기, `_refuse_source` 하드 링크)
- Test: `tests/test_schema.py`, `tests/test_settings.py`

**Interfaces:**
- Produces: `conn.init_db(path) -> Path` — 기존 DB 에 없는 열을 `ALTER TABLE … ADD COLUMN` 으로 덧붙인다 (spec 블록에서 열 이름 · 형을 읽음). `conn.connect/init_db` 는 이미 있는 파일의 `st_nlink > 1` 이면 `RuntimeError("DB 파일이 하드 링크 …")`.

- [ ] **Step 1: 실패 테스트** — `test_schema.py::test_schema_sql_equals_spec_block`(기존, 이제 FAIL), `test_init_db_adds_v03_columns`: v0.2 `usage_event`(output_est 없음)로 만든 DB 에 `init_db` → `PRAGMA table_info(usage_event)` 에 `output_est`·`cost_est_usd`, `usage_daily` 에도 둘. `test_settings.py::test_hardlinked_db_refused`: `tmp/a.db` 를 만들고 `os.link(a, b)` → `conn.connect(b)` 가 `RuntimeError`; 링크 없는 새 경로는 통과.
- [ ] **Step 2:** `uv run pytest tests/test_schema.py tests/test_settings.py -q` → 3 FAIL
- [ ] **Step 3:** schema.sql 갱신 · `init_db` 에 `_add_missing_columns(con)` · `_refuse_source` 에 `p.exists() and p.stat().st_nlink > 1` 검사.
- [ ] **Step 4:** 같은 명령 PASS, `uv run pytest -q` 전체 PASS.
- [ ] **Step 5:** commit `Phase 0: schema v0.3 열 · init_db 열 덧붙이기 · 하드 링크 거부 (DEF-QA1-201)`

### Task 2: 설정 · 결정 대장 · D-08 대조

**Files:**
- Create: `config/budget.yaml` (spec §6.3 블록 그대로)
- Modify: `config/pricing.yaml` (D-08 대조 결과), `decisions.md` (D-07 · D-08 · D-13 · D-14 · D-17 · D-18 · D-19 → `확정`, 근거 = `spec.md` v0.3 절 · 줄)
- Create: `src/agentdash/tools/check_decisions.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config/budget.yaml` 키 `warn_ratio` · `total.{daily_usd,monthly_usd}` · `projects`. `check_decisions` 출력 `G-23  결정 반영  PASS|FAIL  <실측>` — 7 D 상태가 `확정` · `src/` 에 `가설 D-18` · `D18_NOTE` 0 · decisions.md D-08 에 대조 출처 URL 과 날짜.

- [ ] **Step 1:** `test_config.py::test_budget_yaml_defaults` — `warn_ratio == 0.8`, total 두 값 `None`, `projects == {}`.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** budget.yaml 작성. D-08: `https://platform.claude.com/docs/en/about-claude/pricing` 를 **읽어**(WebFetch, 코드 아님) Haiku 5.5 캐시 읽기 단가를 대조 — 같으면 `cache_read_estimated` 표시 제거, 다르면 값 고치고 `make reprice`. 페이지에 값이 없으면 D-08 을 `차단` 으로 두고 표시 유지(지어내지 않음). decisions.md 갱신, check_decisions 작성.
- [ ] **Step 4:** `uv run pytest tests/test_config.py -q` PASS. `uv run python src/agentdash/tools/check_decisions.py` → 개발2 Task 9 전이라 `D18_NOTE` 때문에 FAIL 이 정상.
- [ ] **Step 5:** commit `Phase 0: budget.yaml · D-08 대조 · 결정 확정 · check_decisions`

### Task 3: 게이트 G-23~G-30 · 라우트 7/13 · 문서 숫자

**Files:**
- Modify: `src/agentdash/tools/gate.py` (`GATES` 에 G-23~G-30, G-17 항목명 `화면 7 · API 13`, `QA_GLOBS` 에 `outputs/e2e/alerts*.md` · `outputs/e2e/design*.md`)
- Modify: `src/agentdash/tools/check_routes.py` (`D-0[1-7]`)
- Modify: `src/agentdash/app/main.py` (`ROUTERS` 에 `insights` — 파일이 없으면 import 실패하므로 Task 8 이 만들 때까지 `placeholders` 라우터로 `/insights` · API 3 빈 응답)
- Modify: `Makefile` (`gate` 주석 G-30 · `run` 주석 정정 · `check-decisions` · `check-contrast` 타깃), `CLAUDE.md` (규모 숫자 · 새 소유 파일)
- Test: `tests/test_gate.py`, `tests/test_routes.py`

**Interfaces:**
- Produces: GATES 행 — G-23 `[("tool","check_decisions")]` · G-24 `[("test","test_usage_est.py"),("tool","check_usage_est")]` · G-25 `[("test","test_settings.py")]` · G-26 `[("test","test_budget.py"),("tool","check_budget")]` · G-27 `[("tool","check_trend")]` · G-28 `[("tool","check_efficiency")]` · G-29 `[("test","test_alerts.py"),("qa","")]` · G-30 `[("tool","check_contrast"),("test","test_design.py"),("qa","")]`.
- Produces: `placeholders` 응답 `/insights` (HTML 200) · `/api/v1/{budget,trend,efficiency}` (`{"_placeholder": …}`) — Task 8 이 대체.

- [ ] **Step 1:** `test_gate.py::test_gates_cover_g01_to_g30` (G-01..G-30 연속 30 행), `test_routes.py` 가 화면 7 · API 13 을 센다.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** 위 변경.
- [ ] **Step 4:** `uv run pytest tests/test_gate.py tests/test_routes.py -q` PASS · `make gate` 가 30 행을 찍는다 (G-23~G-30 대부분 FAIL 정상, G-17 PASS).
- [ ] **Step 5:** commit `Phase 0: gate G-23~G-30 · 화면 7 · API 13`

### Task 4: 공통 화면 틀 · 대비 검사

**Files:**
- Modify: `src/agentdash/app/templates/base.html` — 토큰(`--bg --surface --fg --muted --line --accent` + 상태 8 `--st-running … --st-stale`, 각 `-fg` 글자색), 밝은 기본 · `@media (prefers-color-scheme: dark)` 를 `:root:not([data-theme="light"])` 로 막고 `:root[data-theme="dark"]` 도 정의, 공통 부품 클래스 `.card .grid .kpi .tbl .badge .st-<STATE> .chart`, 머리글 테마 토글 · 「알림 켜기」 버튼 자리(`#alerts-btn`), nav 에 `/insights` 「D-07 비용 · 효율」, `{% include "_alerts.html" ignore missing %}`.
- Create: `src/agentdash/tools/check_contrast.py`, `tests/test_design.py`

**Interfaces:**
- Produces: CSS 변수 이름 위 목록 · 클래스 이름 위 목록 (개발1 · 2 가 웨이브 B 에서 쓴다). `check_contrast` 는 base.html 에서 두 테마의 토큰을 읽어 `--st-*-fg` 대 `--bg`/`--surface` ≥ 4.5, `--st-*` 대 `--bg` ≥ 3.0 을 재고 `G-30  디자인 대비  PASS|FAIL  최소 n.n:1 (<토큰>)`.
- Produces: `test_design.py::test_no_dev_style_includes` — 템플릿에 `_dev1_style` · `_dev2_style` include 0 (웨이브 B 끝까지 FAIL 정상).

- [ ] **Step 1:** `test_design.py::test_contrast_both_themes`(check_contrast 함수 직접 호출, 16 쌍 × 2 테마 기준 충족) · `test_theme_tokens_defined`(두 테마에 같은 토큰 집합) · `test_no_dev_style_includes`.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** base.html · check_contrast 작성. 기존 화면이 깨지지 않게 이전 변수(`--warn` 등)는 별칭으로 남긴다.
- [ ] **Step 4:** 앞 두 테스트 PASS, `uv run pytest -q` 전체 PASS (`test_no_dev_style_includes` 는 `xfail(strict=True, reason="웨이브 B")` 로 두고 웨이브 B 가 xfail 표시를 뗀다 — 소유는 아키텍트이므로 개발자는 progress §3 에 요청).
- [ ] **Step 5:** commit `Phase 0: base.html 토큰 · 밝은/다크 · check_contrast`

Phase 0 끝 = G-01 · G-13~G-17 · G-25 PASS, G-01~G-22 회귀 PASS.

---

## 웨이브 A — 개발1 (수집 · 숫자)

### Task 5: 요청별 길이 · 추정 출력 · 추정 비용

**Files:**
- Modify: `src/agentdash/collect/parsers/transcript.py` (`Record.content_json_len: int = 0` · `Record.est_chars: int = 0`)
- Modify: `src/agentdash/core/model.py` (`UsageEvent.output_est: int | None = None` · `cost_est_usd: float | None = None`; `add_usage` 는 output 이 커지거나 `output_est` 가 바뀌면 갱신)
- Modify: `src/agentdash/core/usage.py` (`estimate`, `cost_est`)
- Modify: `src/agentdash/collect/ingest.py` (요청 누적기)
- Create: `tests/test_usage_est.py`; Modify: `tests/test_parsers.py`

**Interfaces:**
- Produces: `usage.SUSPECT_MAX_OUTPUT = 30` · `usage.SUSPECT_MIN_JSON = 400` · `usage.estimate(max_output: int, json_len: int, est_chars: int) -> int | None` (의심 아니면 `None`) · `usage.cost_est(ev: M.UsageEvent, pricing: Pricing) -> float | None` (`output_est` 가 없으면 `ev.cost_usd`).
- Produces: `ingest` 의 `_req_acc: dict[tuple[str, str], list[int]]` — 키 `(agent_key, request_id)`, 값 `[max_output, json_len, est_chars]`, 프로세스 수명 동안 유지 (Review Focus 1).

- [ ] **Step 1: 실패 테스트** (`test_usage_est.py`)
  - `test_estimate_table` 매개변수화: `(29, 401, 2000) → 500` · `(30, 401, 2000) → None` · `(29, 400, 2000) → None` · `(0, 401, 10) → 3`(ceil 10/4) · `(20, 401, 40) → 20`(하한 = 기록).
  - `test_parser_lengths`: text 블록 `"가"*100` + tool_use input `{"a":"b"}` → `est_chars == 100 + len('{"a": "b"}')`, `content_json_len == sum(len(json.dumps(b)) for b in blocks)`, thinking 블록은 `est_chars` 에 0.
  - `test_ingest_sets_output_est`: 가짜 루트 서브에이전트 기록에 같은 requestId 3 줄(output 1,1,1 · text 합 2,000 자) → `usage_event.output_est == 500`, `cost_est_usd > cost_usd`.
  - `test_not_suspect_is_null`: output 500 인 요청 → `output_est IS NULL`, `cost_est_usd == cost_usd`.
  - `test_synthetic_excluded`: `<synthetic>` 줄은 행 0.
  - `test_split_request_same_as_single_pass`: 같은 3 줄을 두 번의 tail 읽기(2 줄 · 1 줄)로 넣은 DB 와 한 번에 넣은 DB 의 `output_est` 같음.
  - `test_no_length_stored`: `usage_event` 의 열 이름 집합 = spec §3 블록, TEXT 열 값에 숫자 문자열 아닌 본문 없음 (V-04 재사용).
- [ ] **Step 2:** `uv run pytest tests/test_usage_est.py -q` → FAIL
- [ ] **Step 3:** 파서에 길이 두 칸(값만, 본문 버림) · `estimate` · `cost_est` · ingest 누적기 → `ev.output_est`, `ev.cost_est_usd` 채워 `add_usage`. 포크 사본 경로(`upgrade_owner_usage`)도 같은 열을 옮긴다.
- [ ] **Step 4:** `uv run pytest -q` 전체 PASS.
- [ ] **Step 5:** commit `웨이브 A: D-17 추정 출력 · 추정 비용 (spec §6.2)`

### Task 6: usage_daily · 합계 · 표기 · CSV · reprice

**Files:**
- Modify: `src/agentdash/core/usage.py` (`rebuild_daily` 두 열 · `_SUM` · `totals` · `table` · `CSV_COLS` · `reprice` 가 `cost_est_usd` 도 다시 계산; `UNDERCOUNT_NOTE = "추정 보정 (D-17)"`)
- Modify: `src/agentdash/app/templates/usage.html` · `src/agentdash/app/routers/usage.py`
- Create: `src/agentdash/tools/check_usage_est.py`
- Modify: `tests/test_usage.py` · `tests/test_usage_page.py`

**Interfaces:**
- Consumes: Task 5 열.
- Produces: `usage.totals(con, key, descendants=…) -> dict` 에 키 `output_est_total`(의심 행은 output_est, 나머지 output_tokens 의 합) · `cost_est_usd`. `usage.table(...)` 행 · 합계에 같은 두 키. CSV 열 `output_est_total` · `cost_est_usd` (머리 `추정 보정 (D-17)`).
- Produces: `check_usage_est` 출력 `G-24  추정 열  PASS|FAIL  의심 DB x.x% · 원천 y.y% · 위반 n` — 원천은 settings 경로로 다시 읽어 spec §6.2 정의로 잰다(QA1 스크립트와 같은 정의, 읽기만).

- [ ] **Step 1:** `test_usage.py::test_daily_est_columns`(두 요청 → usage_daily `output_est` · `cost_est_usd` 합), `test_totals_est_keys`, `test_reprice_recomputes_cost_est`; `test_usage_page.py::test_est_label_and_csv`(화면에 `추정 보정 (D-17)`, CSV 머리에 두 열, 「기록상 과소」 0).
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** 구현 · `check_usage_est`.
- [ ] **Step 4:** `uv run pytest -q` PASS. `rm -f data/agentdash-dev1.db && AGENTDASH_DB=data/agentdash-dev1.db make setup backfill && AGENTDASH_DB=data/agentdash-dev1.db uv run python src/agentdash/tools/check_usage_est.py` → `PASS` (차이 ≤ 0.5 %p).
- [ ] **Step 5:** commit `웨이브 A: usage_daily 추정 열 · 추정 보정 표기 · CSV · check_usage_est`

### Task 7: core/budget.py — 예산 · 추세 · 효율

**Files:**
- Create: `src/agentdash/core/budget.py`, `tests/test_budget.py`
- Create: `src/agentdash/tools/{check_budget,check_trend,check_efficiency}.py`

**Interfaces:**
- Produces:
  - `budget.load() -> dict` (budget.yaml, 키 빠지면 `SettingsError`)
  - `budget.status(con, now: datetime | None = None) -> list[dict]` — 칸마다 `{scope: "total"|"project", project: str|None, period: "day"|"month", limit: float|None, est_usd: float, rec_usd: float, ratio: float|None, level: "ok"|"warn"|"over"|"unset"|"no_records", unpriced: int}`. 한도가 있는 project 가 기록에 없으면 `level="no_records"`.
  - `budget.worst(rows) -> dict | None` — `over` > `warn` 중 ratio 큰 것 (D-01 띠용).
  - `budget.trend(con, grain: "day"|"week"|"month", frm: str, to: str, group: "total"|"project") -> list[dict]` — `{bucket: "YYYY-MM-DD"(주는 그 월요일, 월은 1 일), project, cost_usd, cost_est_usd, output_tokens, output_est_total}`.
  - `budget.efficiency(con, group: "project"|"session"|"agent", frm: str, to: str) -> list[dict]` — `{key, label, input_tokens, cache_read, cache_write, hit: float|None, cost_est_usd, waste: float}`; `waste = (1-hit)*cost_est_usd`(hit None → 0), `waste` 내림차순. session 은 자기 + 자손.
- 출력 행: `G-26  예산  …` · `G-27  추세  …` · `G-28  캐시 적중률  …`.

- [ ] **Step 1:** `test_budget.py`
  - `test_level_boundaries`: 한도 100, est 79.99 → ok · 80 → warn · 100 → over · 한도 None → unset.
  - `test_kst_day_month_boundary`: `2026-10-20T14:59:59Z` 는 10-20, `15:00:00Z` 는 10-21; `2026-10-31T15:00:00Z` 는 11 월.
  - `test_project_mapping`: `project_path=/x/Standard MES Platform` 의 서브에이전트 비용이 `projects["Standard MES Platform"]` 칸에.
  - `test_project_not_in_records`: budget 에 `"오타"` → `no_records`.
  - `test_unpriced_not_summed`: cost NULL 행 2 → `unpriced == 2`, est_usd 에 0 으로도 안 더함.
  - `test_trend_week_starts_monday_kst`: 10-25(일) 23:00 KST 와 10-26(월) 00:30 KST → 다른 주 버킷 `2026-10-19` · `2026-10-26`.
  - `test_trend_sums_equal_events`: 임의 20 행 → day · week · month 합 = `usage_event` 합 (기록 · 추정).
  - `test_efficiency_formula_and_zero`: 손계산 hit, 분모 0 → None, 정렬 = waste 내림차순.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** 구현 (`usage.kst_day` 재사용, 금액은 budget.yaml 에서만).
- [ ] **Step 4:** `uv run pytest tests/test_budget.py -q` PASS · 세 도구를 dev1 DB 로 실행해 PASS.
- [ ] **Step 5:** commit `웨이브 A: core/budget 예산 · 추세 · 캐시 적중률 + 검사 3`

### Task 8: D-07 화면 · API 3

**Files:**
- Create: `src/agentdash/app/routers/insights.py`, `src/agentdash/app/templates/insights.html`, `tests/test_insights.py`
- Request(아키텍트): `main.py` `ROUTERS` 의 placeholder 를 `insights` 로 교체 (progress-dev1.md §3)

**Interfaces:**
- Consumes: Task 7 함수.
- Produces: `GET /insights` · `GET /api/v1/budget` → `{"rows": status(), "label": "[추정] API 정가 환산"}` · `GET /api/v1/trend?grain&from&to&group` → `{"rows": trend()}` (grain 잘못되면 422) · `GET /api/v1/efficiency?group&from&to` → `{"rows": efficiency()}`.
- 화면: Chart.js `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`, 못 불러오면 Cytoscape 와 같은 문구로 표만 보여 준다.

- [ ] **Step 1:** `test_insights.py` — 빈 DB 에서 4 경로 200 · `_placeholder` 키 없음 · `한도 미설정` 문구 · `grain=year` → 422 · 가짜 데이터에서 `/api/v1/budget` rows = `budget.status`.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** 구현 (base.html 토큰 · 클래스만 사용).
- [ ] **Step 4:** `uv run pytest -q` PASS · `uv run python src/agentdash/tools/check_routes.py` → G-17 PASS (placeholder 0).
- [ ] **Step 5:** commit `웨이브 A: D-07 비용 · 효율 · API 3`

## 웨이브 A — 개발2 (상태 · 알림)

### Task 9: D-13 · D-14 · D-18 · D-19 확정 반영

**Files:**
- Modify: `src/agentdash/core/state.py` (머리 주석의 `[가설 …]` → `확정 spec v0.3 §4.2`; 근거 문자열에서 `가설` 표현 제거, 규칙 코드는 그대로)
- Modify: `src/agentdash/app/routers/agents.py` (`D18_NOTE` · `hypothesis` 필드 제거), `templates/_d01_body.html` · `templates/agent.html` (`data-hypothesis` span 제거)
- Modify: `tests/test_state.py` · `tests/test_dashboard.py`

**Interfaces:**
- Produces: `/api/v1/agents/{key}` 응답에 `hypothesis` 키 없음 (DEF-QA2-201 해소).

- [ ] **Step 1:** `test_dashboard.py::test_no_hypothesis_label`(D-01 · D-02 패널 · D-03 HTML 과 API 에 `가설 D-18` 0); `test_state.py` 표에 spec v0.3 순서 확인 행: busy·5 분+·미래 Wakeup·자식 1 → `SLEEPING R-03`(R-03 이 R-04 보다 먼저), busy·5 분+·자식 STALE 만 → `STALE R-02b`, S1 있음·pid 소멸·5 분 안 → `DONE R-07`.
- [ ] **Step 2:** FAIL 확인 (라벨 테스트).
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** `uv run pytest -q` PASS · `check_decisions` PASS.
- [ ] **Step 5:** commit `웨이브 A: D-18 등 확정 반영 · 가설 표시 제거 (DEF-QA2-201)`

### Task 10: WAITING 알림 스크립트

**Files:**
- Create: `src/agentdash/app/templates/_alerts.html`, `tests/test_alerts.py`

**Interfaces:**
- Consumes: SSE `agent.state {agent_key, state, reason}` · `GET /api/v1/agents?state=WAITING_INPUT` (·`WAITING_PERMISSION`) · `GET /api/v1/agents/{key}` 의 `state.since` · `name` · `project_path`.
- Produces: 전역 `window.agentdashAlerts = {waiting: Set, seen: Set}` (E2E 가 읽는다), `#alerts-btn` 동작, 탭 제목 접두 `(N) `, BroadcastChannel 이름 `agentdash-alerts`, localStorage 키 `agentdash.alerts`(`on`|`off`) · `agentdash.seen`(최근 200 개 `key|since`).
- 규칙: 첫 로드 때 지금 대기 목록으로 `waiting` 을 채우고 알리지 않는다 → 전이 이벤트마다 상세를 받아 `key|since` 가 `seen` 에 없고 이 탭이 리더(BroadcastChannel 로 먼저 잡은 탭)일 때만 `new Notification(제목, {body, tag: key|since})`. `tag` 로 브라우저 쪽 중복도 막는다. 누르면 `/agents/{key}`. 권한 `denied` · 미지원이면 버튼 문구 `알림 불가 — 배지만` · 배지만.

- [ ] **Step 1:** `test_alerts.py` (정적 계약 — JS 는 브라우저 E2E 가 판정): 모든 화면 HTML 에 `_alerts` 스크립트 1 회 · `agent.state` 구독 · 문자열 `WAITING_INPUT` `WAITING_PERMISSION` `BroadcastChannel` `agentdash-alerts` `tag:` `requestPermission` 존재 · `fetch(` 대상이 `/api/v1/` 만 · 외부 URL 0.
- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** `uv run pytest -q` PASS. 수동: `AGENTDASH_PORT=8097` 가짜 루트로 `make run`, 훅 POST(`Notification` 권한 요청) → 알림 1 · 재전송 0 · 새로고침 0 — 결과를 progress-dev2.md 에 (판정은 QA2 G-29).
- [ ] **Step 5:** commit `웨이브 A: WAITING 브라우저 알림 · 탭 배지`

### Task 11: D-01 예산 띠

**Files:**
- Modify: `src/agentdash/app/routers/pages.py` · `templates/_d01_body.html` · `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `budget.status` · `budget.worst` (Task 7 — 개발1 이 progress-dev1.md §1 에 공표한 뒤 시작).

- [ ] **Step 1:** `test_dashboard.py::test_budget_band` — budget.yaml 을 가짜(monkeypatch `budget.load`)로 total.daily 100 · 오늘 est 85 → D-01 에 띠 · `/insights` 링크 · `85 %`; 전부 unset → 띠 없음; 102 → 빨강 클래스 `st-FAILED`.
- [ ] **Step 2:** FAIL → **Step 3:** 구현 → **Step 4:** `uv run pytest -q` PASS → **Step 5:** commit `웨이브 A: D-01 예산 경고 띠`

---

## 웨이브 B — 디자인 적용

### Task 12: 개발1 화면 (D-04 · D-05 · D-06 · D-07)

**Files:** Modify `templates/{usage,timeline,pipeline,insights}.html` · Delete `templates/_dev1_style.html` · `routers/_svg.py` 색을 토큰 변수로.

- [ ] **Step 1:** 아키텍트에게 `test_no_dev_style_includes` xfail 해제 요청은 Task 13 과 함께. 지금은 `uv run pytest tests/test_design.py -q` 로 현재 상태 확인.
- [ ] **Step 2:** 네 화면을 `.card .grid .kpi .tbl .badge .st-*` 와 토큰만 쓰도록 바꾸고 `_dev1_style.html` 삭제.
- [ ] **Step 3:** `uv run pytest -q` PASS (기존 화면 테스트 회귀) · 390px · 두 테마 스크린샷을 `outputs/e2e/dev1-design/` (커밋 안 함, D-07).
- [ ] **Step 4:** commit `웨이브 B: D-04~D-07 공통 틀`

### Task 13: 개발2 화면 (D-01 · D-02 · D-03)

**Files:** Modify `templates/{dashboard,_d01_body,graph,agent,agent_raw}.html` · Delete `templates/_dev2_style.html` · Cytoscape 스타일 색은 `getComputedStyle` 로 토큰에서 읽는다(테마 전환 시 다시 그림).

- [ ] **Step 1:** 세 화면 전환 · `_dev2_style.html` 삭제.
- [ ] **Step 2:** progress-dev2.md §3 에 「`test_no_dev_style_includes` xfail 해제」 요청 → 아키텍트가 해제.
- [ ] **Step 3:** `uv run pytest -q` PASS · `uv run python src/agentdash/tools/check_contrast.py` PASS.
- [ ] **Step 4:** commit `웨이브 B: D-01~D-03 공통 틀`

---

## 웨이브 C — QA (고치지 않는다)

### Task 14: QA1 숫자 · 안전 (`outputs/qa1-데이터안전-r4.md` — 1차 묶음의 다음 회차, gate 는 가장 최근 회차만 읽는다)
- [ ] 원천을 **자기 스크립트로** 다시 재서 G-24(의심 비율 · 추정 하한) · G-26(칸별 직접 합) · G-27(일 · 주 · 월) · G-28(표본 10 손계산) 대조, G-13 · G-14 · G-25 재확인(하드 링크 재현).
- [ ] 게이트마다 `<!-- gate:G-nn -->` 다음 줄에 판정 행. 결함 `DEF-QA1-3nn`.

### Task 15: QA2 상태 · 화면 (`outputs/qa2-상태대조-r4.md` · `outputs/e2e/self-observe-r4.md` · `outputs/e2e/alerts.md` · `outputs/e2e/design.md`)
- [ ] G-12 재대조(표본 30, spec v0.3 규칙 글자로), G-29 브라우저 E2E(첫 로드 0 · 전이 1 · 재전송 0 · 두 탭 1 · 권한 거부 시 배지만), G-30 D-01~D-07 × 두 테마 스크린샷 · 390px · 콘솔 오류 0, G-21 · G-22 재실행. 결함 `DEF-QA2-3nn`.

## 웨이브 D — 결함 수정 → C 반복 (goal.md §4)
