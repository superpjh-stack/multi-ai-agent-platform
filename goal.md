# /goal — 멀티 에이전트 대시보드 구축 (화면 6 · API 10 · 상태 규칙 13 · 검증 11 · 훅 이벤트 9)

> **이 문서가 메타프롬프트다.** `/loop` 가 매 회전마다 이 문서를 판정 기준으로 읽는다. 투입되는 에이전트(아키텍트 1 · 개발 2 · QA 2)도
> 작업 전에 이 문서와 `CLAUDE.md` · `decisions.md` · `progress.md` 를 먼저 읽는다.
> 여기 적힌 수치는 `spec.md` v0.2 에서 센 값이다. 세는 방법은 §9 에 있으므로 의심되면 다시 센다.

| 항목 | 값 | 출처 |
|---|---|---|
| 시스템 | 이 컴퓨터의 Claude Code 세션 · 서브에이전트 · 워크플로 에이전트를 읽어 상태 · 관계 · 작업량 · 비용 · 파이프라인 진척을 보여 주는 로컬 대시보드 | `intro.md` §1 |
| 정본 | `intro.md` · `problem.md` · `spec.md` (이 폴더 루트, **사람만 고친다**) | — |
| 원천 | `~/.claude/sessions` · `~/.claude/projects/**` · `~/Desktop/AI Coding/<NN> * Agent/{outputs,progress.md}` (**읽기 전용**) | `spec.md` §2.1 S1~S9 |
| 규모 | **화면 6** (D-01~D-06) · **API 10** · **상태 8** · **판정 규칙 13** (R-01 · R-02a · R-02b · R-03~R-12) · **연결 규칙 7** (L-01~L-07) · **진척 규칙 7** (P-01~P-07) · **검증 11** (V-01~V-11) · **훅 이벤트 9** · **테이블 11** | `spec.md` §3 · §4 · §7 · §8 · §9 · §10 |
| 핵심 | **부모 연결(linker) + 상태 판정(state)**. 이 둘이 틀리면 구성도 · 관제판 · 작업량이 전부 틀린다 | `spec.md` §3.2 · §4 |
| 확정 결정 | Q1 훅 연동 v1 포함 · Q2 `STALE` 5 분 · Q4 기본 단가표 · Q5 진척 규칙 (2026-10-17) | `problem.md` §8 |
| 기술 | Python 3.12 · `uv` · FastAPI · Jinja2 · SSE · SQLite(WAL) · `watchfiles` · Cytoscape.js(CDN 고정 버전) · pytest | `spec.md` §1.2 |
| 포트 | **8095** · `127.0.0.1` 만 | `spec.md` §1.3 |
| 범위 밖 | 에이전트 실행 · 중지 · 메시지 보내기 · 원격/클라우드 세션 · 대화 본문 저장 · 실제 청구 금액 | `problem.md` §5 |
| 완료 기준 | **이 컴퓨터의 실제 기록을 백필해 V-01~V-11 이 전부 PASS 이고, 이 루프가 띄운 에이전트들이 D-01 · D-02 에 실시간으로 나타났다 사라진다** | `spec.md` §13 |
| 코드 위치 | `/Users/gerardo92/Desktop/AI Coding/Multi-agent Dashboard` (이 폴더) | — |

---

## 0. 이 문서를 어떻게 쓰는가

### 0.1 루프 기동 — 이 한 줄을 붙여 넣는다

```
/loop goal.md 를 판정 기준으로 멀티 에이전트 대시보드를 만든다. §4.2 한 회전 절차를 그대로 따른다 —
progress.md·decisions.md 를 읽고(없으면 §3.1 Phase 0 부터), `make gate` 로 §2 게이트 G-01~G-22 를 실측하고,
FAIL 중 가장 앞선 웨이브의 항목 하나를 골라 §5 프롬프트로 담당 에이전트를 기동하고(병렬 가능한 것은 한 번에),
보고를 믿지 말고 게이트 명령을 직접 다시 돌려 확인한 뒤 실측값과 검증 명령을 progress.md 에 적고 로컬 커밋한다.
~/.claude 와 이 폴더 밖에는 절대 쓰지 않는다(훅 설치는 사람이 한다). 막히면 decisions.md 에 D-번호로 `차단`을 올리고
다음 항목으로 넘어간다 — 사람을 기다리며 멈추지 않는다. 게이트를 낮추거나 테스트를 건너뛰지 않는다.
§4.4 종료 조건을 만족하면 최종 보고를 쓰고 루프를 멈춘다.
```

중단 후 재개는 `/re-begin` 또는 위 한 줄을 다시 붙여 넣는다. 상태는 전부 파일에 있다(§4.5).

### 0.2 이 프로젝트가 직전 프로젝트(Standard MES · Data Hub)와 다른 점 — 먼저 알고 시작한다

- **관찰 대상이 이 루프 자신이다.** 대시보드가 읽는 `~/.claude/projects/-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard/` 에는 지금 이 루프의 세션과 서브에이전트 기록이 쌓인다. 이것이 가장 좋은 실측 자료이자 가장 위험한 자리다 — **원천 파일을 지우거나 고치면 루프가 자기 기억을 망가뜨린다.**
- **원천은 읽기 전용이고, 테스트는 원천을 쓰지 않는다.** 모든 코드는 원천 루트를 `AGENTDASH_CLAUDE_HOME`(기본 `~/.claude`) · `AGENTDASH_AGENTS_ROOT`(기본 `~/Desktop/AI Coding`) 로 받는다. 테스트 · 게이트의 쓰기 시나리오(새 세션 · 훅 설치 등)는 전부 `tmp_path` 의 가짜 루트에서 돈다.
- **훅 설치는 사람이 한다.** 루프 · 에이전트는 `make hooks-install` 을 실제 `~/.claude/settings.json` 에 대고 돌리지 않는다. 설치 스크립트는 `--settings <경로>` 로 가짜 설정 파일에서만 검증한다(G-15). 지금 있는 `PreToolUse` · `PostToolUse` · `Stop` 훅(이슈 자동 등록)을 깨면 사용자의 다른 프로젝트 전부가 영향을 받는다.
- **대화 본문은 민감 정보다.** 고객사 자료 · 경로 · 키가 섞여 있다. 픽스처는 실제 기록을 **복사하지 않고**, `scripts/make_fixture.py` 가 구조만 남기고 본문을 `"<redacted>"` 로 바꾼 사본으로 만든다. DB 에도 본문을 넣지 않는다(G-13).
- **형식은 Claude Code 버전에 따라 바뀐다.** 기록에서 본 필드(`spec.md` §2.1 `[실측]`)만 믿고, `[가설]` 로 적힌 것은 실제 기록에서 확인한 뒤 `decisions.md` 에 `확정` 으로 옮기고 쓴다.
- **숫자는 지어내지 않는다.** 단가표는 `spec.md` §6.1 그대로. 모르는 모델은 비용 `NULL`. 못 읽은 진척 칸은 `UNKNOWN`.

---

## 1. 목표

**`~/.claude` 기록을 증분으로 읽어 에이전트 · 관계 · 작업량 · 비용을 SQLite 에 정규화하고, 상태를 규칙대로 판정해 화면 6개와 SSE 로 실시간 보여 준다. 훅이 있으면 훅으로 상태를 확정한다.**

끝났다고 말할 수 있는 상태는 이것뿐이다.

1. 실제 `~/.claude` 를 백필한 DB 의 에이전트 수가 원천 파일 수와 같고(V-01), 서브에이전트의 95% 이상이 부모에 이어진다(V-02).
2. 표본 세션 10 개의 토큰 · 비용이 원천 직접 합산 · §6.1 손계산과 같다(V-03 · V-09).
3. 상태 판정 규칙 13 개가 각각 표 기반 테스트 하나 이상을 갖고, 표본 30 건 수동 대조 오판 ≤ 2 (G4).
4. 화면 6 · API 10 이 HTTP 200 이고, 이 루프가 띄운 서브에이전트가 5 초 안에 D-01 · D-02 에 `RUNNING` 으로 뜬다(가짜 루트 E2E + 실제 루프 관찰).
5. 고려솔더 `01` · `02` 칸이 `DONE` v1.0 으로, `05` · `08` 열이 `UNKNOWN` 으로 나온다(`spec.md` §13-7).
6. 훅 설치 → 제거 뒤 가짜 설정 파일이 바이트 단위로 원래와 같다(V-10).

### 재사용 자산 — 새로 짓기 전에 먼저 본다

| 자산 | 위치 | 가져올 것 |
|---|---|---|
| FastAPI + Jinja2 골격 · Makefile · 게이트 판정표 형식 | `../Standard Data Hub/src/datahub/app/` · `../Standard MES Platform/src/mescore/tools/gate.py` | `main` · `settings` · `templating` · `gate.py` 출력 형식(`G-nn  항목  PASS|FAIL|…  실측`) |
| 루프 문서 형식 | `../Standard MES Platform/{goal,CLAUDE,decisions,progress}.md` | 상태 파일 4종의 형식 |
| 원천 형식 실측 | 이 폴더 `spec.md` §2.1 · 이 대화에서 쓴 스캔 스크립트의 결과(세션 77 · 서브에이전트 232 · 모델 5 종) | 백필 기대값의 출발점 (숫자는 백필 시점에 다시 센다 — 계속 늘어난다) |

---

## 2. 수용 게이트

**루프는 매 회전마다 이 표를 실행한다.** 판정은 명령의 출력으로만 한다 (`make gate`). 실제 원천을 읽는 게이트는 `[실]`, 가짜 루트에서 도는 게이트는 `[가]` 로 표시한다.

### 2.1 수집 · 모델 게이트

| # | 항목 | 게이트 | 검증 |
|---|---|---|---|
| G-01 | 골격 | `make setup` 성공, `schema.sql` 의 테이블 **11** (`agent edge usage_event tool_call file_touch usage_daily state_log src_file parse_error pipeline_cell hook_event`) | `uv run pytest tests/test_schema.py` `[가]` |
| G-02 | 파서 회귀 | 픽스처(버전별 · 본문 제거)로 S1~S6 · S9 파서 전부 통과. 모르는 필드는 무시, 필수 필드 없으면 `parse_error` | V-08 `[가]` |
| G-03 | 증분 읽기 | 파일 끝에 줄 추가 → 추가분만 읽음 · 개행 없는 마지막 줄은 다음 회차 · inode 변경 시 처음부터 | `tests/test_tail.py` `[가]` |
| G-04 | 전체 수집 | 백필 후 `agent` 행 수 = 원천 파일 수 (세션 · 서브에이전트 · 워크플로 에이전트 각각) | V-01 `[실]` |
| G-05 | 파싱 오류율 | ≤ 0.1% 줄 | V-07 `[실]` |
| G-06 | 부모 연결 | 서브에이전트 `parent_key` 보유율 ≥ 95%, 나머지는 "부모 미확인" 노드 | V-02 `[실]` |
| G-07 | 토큰 합 | 표본 세션 10 개: DB 합 = 원천 직접 합 (`requestId` 중복 제거, `<synthetic>` 제외) · 세션 합계 = 자기 + 자손 | V-03 `[실]` |
| G-08 | 비용 | 표본 메시지 20 건 §6.1 손계산 = DB (5m/1h 캐시 쓰기 · fast · Haiku 구간 포함), 단가 없는 모델 목록 출력 | V-09 `[실]` + `tests/test_cost.py` `[가]` |

### 2.2 상태 · 관계 게이트 — 이 프로젝트의 본체

| # | 항목 | 게이트 | 검증 |
|---|---|---|---|
| G-09 | 판정 규칙 | R-01 · R-02a · R-02b · R-03~R-12 **13 개** 각각 표 기반 테스트 ≥ 1 (경계값: 89/91 초 · 299/301 초 · 훅 도구 실행 중) · `STALE` → 새 기록 시 `RUNNING` 회복 | `tests/test_state.py` `[가]` |
| G-10 | 연결 규칙 | L-01~L-07 각각 테스트 ≥ 1 (손자 깊이 2 · 워크플로 · 늦게 읽힌 부모 재시도 · `SendMessage` 미해결 → 외부 노드) | `tests/test_linker.py` `[가]` |
| G-11 | 실시간 | 가짜 루트에 새 세션 파일 + 서브에이전트 2 개를 쓰면 SSE `agent.new` 3 건이 **5 초 안에**, 훅 이벤트 POST 는 **1 초 안에** 상태 반영 | `tests/test_realtime.py` `[가]` |
| G-12 | 상태 대조 | 실제 기록 표본 30 건(실행 중 · 끝남 · 멈춤 섞어서)의 판정을 QA 가 원천을 직접 보고 대조, 오판 ≤ 2 | `outputs/qa2-상태대조.md` `[실]` |

### 2.3 안전 게이트 — 하나라도 FAIL 이면 다른 게이트를 고치지 않는다

| # | 항목 | 게이트 | 검증 |
|---|---|---|---|
| G-13 | 본문 미저장 | DB 의 모든 TEXT 값 ≤ 300 자, 본문 열 없음, 픽스처에 `<redacted>` 아닌 본문 0 | V-04 + `scripts/check_fixtures_redacted.py` |
| G-14 | 원천 무접촉 | 수집기 · 서버 · 테스트가 `AGENTDASH_CLAUDE_HOME` · `AGENTDASH_AGENTS_ROOT` 아래를 쓰기 모드로 여는 코드 0 (정적 스캔) + 읽기 전용 권한 가짜 루트에서 전체 테스트 통과 | V-05 |
| G-15 | 훅 설치 안전 | 가짜 `settings.json`(실제 파일의 `hooks` 구조를 본뜬 것)에 설치 → 기존 3 훅 바이트 동일 · 덧붙인 항목 9 · 제거 후 원본과 바이트 동일 · 송신 스크립트는 서버 꺼짐에서 exit 0 · ≤ 1 초 · 표준출력 0 바이트 | V-10 `[가]` |
| G-16 | 로컬 전용 | 서버 바인드 `127.0.0.1` · 외부 전송 코드 0 (`requests`/`httpx` 외부 호출 스캔) | V-06 |

### 2.4 화면 · 진척 게이트

| # | 항목 | 게이트 | 검증 |
|---|---|---|---|
| G-17 | 화면 · API | D-01~D-06 **6** + API **10** (`spec.md` §8) 전부 HTTP 200, 빈 DB 에서도 200 | `tools/check_routes.py` `[가]` |
| G-18 | 구성도 | 노드 300 개 합성 데이터에서 `/api/v1/graph` ≤ 300 ms, 브라우저 첫 그림 ≤ 2 초, 접기 "+N" 동작 · 보기 3 종 전환 | `tests/test_graph.py` + 브라우저 실측 `[가]` |
| G-19 | 진척 판정 | P-01~P-07 각각 테스트 ≥ 1 · 실제 폴더에서 근거(`src`) 없는 칸 0 · 표본 10 칸 `have/need` 손대조 일치 · 고려솔더 `01`·`02` = `DONE` v1.0 · `05`·`08` = `UNKNOWN` | V-11 `[실]` + `tests/test_pipeline.py` `[가]` |
| G-20 | 비용 화면 | D-04 에 `[추정] API 정가 환산` 표기 · 단가 없음 N 건 표시 · `make reprice` 뒤 합계 일치 | `tests/test_usage_page.py` |

### 2.5 E2E 게이트

| # | 항목 | 게이트 | 검증 |
|---|---|---|---|
| G-21 | 브라우저 | 실제 백필 DB 로 D-01~D-06 을 브라우저로 열어 콘솔 앱 오류 0 · 390px 폭에서 가로 스크롤 0 | `outputs/e2e/` 스크린샷 + 콘솔 로그 `[실]` |
| G-22 | 자기 관찰 | `make run` 상태에서 루프가 서브에이전트를 하나 띄우면 D-02 에 이 폴더 프로젝트 아래 `spawn` 엣지로 `RUNNING` 노드가 뜨고, 끝나면 `DONE` 이 된다 (훅 미설치 상태 — 파일 감시만으로) | `outputs/e2e/self-observe.md` (시각 · 스크린샷) `[실]` |

### 2.6 범위 밖 — 실패로 보지 않는다

- 훅을 **실제로 설치한 상태**의 측정(`WAITING_PERMISSION` 실측 · 1 초 지연) — 사람이 설치한 뒤 `미검증` → 실측. 설치 전에는 `미검증` 허용.
- `05 Open Agent` · `08 AI Agent Making Agent` 진척 규칙 — `UNKNOWN` 이 정답이다.
- 실제 청구 금액과의 일치.

---

## 3. 팀 편성과 웨이브

```
Phase 0  골격 · 스키마 11 · 설정 4종 · 픽스처 생성기 · 게이트 도구 · 안전 게이트 G-13~G-16 (아키텍트 단독)
   ↓
웨이브 A  개발 2 (병렬)   개발1 수집·모델·비용 (G-02~G-08) / 개발2 연결·상태·훅 수신 (G-09~G-11, G-15)
   ↓
웨이브 B  개발 2 (병렬)   개발1 D-04·D-05·D-06 + 진척 (G-19·G-20) / 개발2 D-01·D-02·D-03 + SSE (G-17·G-18)
   ↓
웨이브 C  QA 2 (병렬)     QA1 데이터·비용·진척·안전 / QA2 상태 대조·실시간·브라우저·자기 관찰
   ↓
웨이브 D  결함 수정 (담당 개발) — 안전 게이트 결함이 최우선
   └──── 게이트 전건 PASS 까지 C→D 반복
```

### 3.1 Phase 0 — 아키텍트. 여기가 가장 중요하다

1. `git init`(로컬만) · `.gitignore`(`data/` · `.env` · `outputs/e2e/*.png` 제외 대상 결정) · `uv`(Python 3.12) · `pyproject.toml` · 패키지 `agentdash`.
2. `src/agentdash/settings.py` — `AGENTDASH_CLAUDE_HOME` · `AGENTDASH_AGENTS_ROOT` · `AGENTDASH_DB` · 포트 8095 · `stale_after_sec: 300` · `slow_after_sec: 90`. **원천 경로를 코드에 박지 않는다.**
3. `db/schema.sql` — `spec.md` §3 의 11 테이블 그대로. `db/conn.py` (WAL).
4. `config/{settings,pricing,pipeline,companies}.yaml` — `spec.md` §6.1 · §7.1 표를 그대로 옮긴다. 단가 · 회사 · 패턴을 지어내지 않는다.
5. `scripts/make_fixture.py` — 실제 기록에서 세션 1 · 서브에이전트(깊이 1 · 2) · 워크플로 1 · `sessions/*.json` 1 을 골라 **본문을 `<redacted>` 로 바꾼** 사본을 `tests/fixtures/<cc_version>/` 에 만든다. `scripts/check_fixtures_redacted.py` 를 같이 만든다.
6. 안전 게이트 도구를 **기능보다 먼저** — `tools/{check_no_payload,check_readonly,check_bind,check_hooks}.py` (V-04 · V-05 · V-06 · V-10 골격). `tests/conftest.py` 에 가짜 루트 픽스처(`fake_claude_home`, 읽기 전용 모드 옵션).
7. `tools/gate.py` + `Makefile`(`setup backfill run gate test hooks-install hooks-uninstall hooks-check pricing-check reprice export`) · 화면 6 placeholder(HTTP 200 + "미구현 — 담당 개발N") · API 10 빈 응답.
8. `CLAUDE.md` · `decisions.md`(§7 의 D-01~D-08 옮김) · `progress.md` 첫 섹션 · `make gate` 판정표 첨부.

Phase 0 끝 = G-01 · G-13 · G-14 · G-16 PASS, G-17 은 placeholder 로 PASS(정상), 나머지는 FAIL(정상).

### 3.2 개발 2명 — 한 파일은 한 사람만 만진다

| 담당 | 웨이브 A | 웨이브 B | 소유 파일 |
|---|---|---|---|
| **개발1** 수집 · 숫자 | `collect/{watcher,tail}.py` · `collect/parsers/*` · `core/usage.py` · 비용 계산 · 백필 · `make pricing-check` · `make reprice` | D-04 작업량 · D-05 타임라인 · D-06 파이프라인 · `core/pipeline.py` · CSV | `collect/` (훅 수신 제외) · `core/{usage,pipeline,model}.py` · `routers/` 중 usage · timeline · pipeline |
| **개발2** 관계 · 상태 | `core/linker.py` · `core/state.py` · `collect/hooks_rx.py` · `scripts/{hook_send.sh,hooks_install.py}` · `app/sse.py` | D-01 관제판 · D-02 구성도(Cytoscape) · D-03 상세 · `core/graph.py` | `core/{linker,state,graph}.py` · `collect/hooks_rx.py` · `scripts/hook*` · `routers/` 중 pages(D-01~03) · graph · agents · stream · hooks |

- `core/model.py`(데이터 클래스 · DB 쓰기)는 개발1 소유. 개발2 가 필드가 더 필요하면 `progress-dev2.md` §3 에 요청한다.
- 공용 시그니처(`model.upsert_agent`, `state.evaluate(agent, now) -> (state, rule)`, `linker.resolve(agent)`)는 **먼저 정한 사람이 `progress-devN.md` §1 에 공표**하고 나머지가 그대로 쓴다.
- `[가설]` 을 만나면 실제 기록(읽기만)으로 확인 → `decisions.md` 에 `확정` · 근거 파일 · 줄 → `spec.md` 는 고치지 않는다(사람만). 반박되면 `차단` 이 아니라 `가설 반박` 으로 올리고 대안 규칙으로 진행.

### 3.3 QA 2명 — 서로 다른 관점으로 교차 검증

| 담당 | 범위 | 산출 |
|---|---|---|
| **QA1** 데이터 · 비용 · 진척 · 안전 | G-04~G-08 · G-13~G-16 · G-19 · G-20 — 원천을 **자기 스크립트로** 다시 세서 DB 와 대조 · 비용 손계산 · 진척 칸 손대조 · 쓰기 코드 사냥 · 픽스처 본문 누출 사냥 | `outputs/qa1-데이터안전.md` |
| **QA2** 상태 · 실시간 · 화면 | G-09~G-12 · G-17 · G-18 · G-21 · G-22 — 표본 30 건 상태 대조 · 경계 시각 · 브라우저 콘솔 · 390px · 자기 관찰 | `outputs/qa2-상태대조.md` · `outputs/e2e/` |

결함 ID 는 `DEF-QA{n}-nnn`, 등급은 치명/중대/경미. **치명 = 원천 쓰기 · 본문 저장 · 기존 훅 손상 · 외부 전송.** **QA 는 고치지 않는다.**

---

## 4. 루프 엔지니어링 프로토콜

### 4.1 상태 파일

| 파일 | 역할 | 쓰는 사람 |
|---|---|---|
| `goal.md` | 목표 · 게이트 (이 문서). **판정 기준** | 사람만 |
| `intro.md` · `problem.md` · `spec.md` | 정본. 수치 · 규칙의 출처 | 사람만 |
| `progress.md` | **검증된 현황의 유일한 진실.** `\| 항목 \| 실측 \| 검증 방법 \|` 3열 + 맨 위 "지금 해야 할 것" | 루프 오케스트레이터 |
| `decisions.md` | 결정 대장 `D-nn` — `확정` / `가설` / `가설 반박` / `차단` | 전원 |
| `progress-dev{1,2}.md` | 개발자별 진행 · 공표(§1) · 요청(§3) | 각 개발자 |
| `outputs/qa{1,2}-*.md` · `outputs/e2e/` | QA 리포트 · 증거 | 각 QA |

### 4.2 한 회전에서 하는 일 (순서를 바꾸지 않는다)

1. **읽기** — `progress.md` 최신 섹션 · `decisions.md` 미결 · 직전 QA 리포트. `progress.md` 가 없으면 Phase 0.
2. **판정** — `make gate`. FAIL 목록. **안전 게이트(G-13~G-16) 중 FAIL 이 있으면 그것이 무조건 다음 작업이다.**
3. **선택** — FAIL 중 **가장 앞선 웨이브의 항목 1개**. 웨이브를 건너뛰지 않는다.
4. **기동** — §5 프롬프트로 담당 에이전트를 띄운다. 병렬 가능한 것은 한 번에(동시에 3명 이하). 작은 수정은 직접.
5. **검증** — 보고를 믿지 않는다. 게이트 명령을 **직접 다시 실행**한다. 실제 원천을 읽는 게이트(`[실]`)는 숫자가 계속 늘어나므로 "같은 시각에 센 원천 vs DB" 로 비교한다.
6. **기록 · 커밋** — `progress.md` 에 실측과 명령, 새 결정은 `decisions.md`. `git add -A && git commit -m "<G-nn|웨이브>: <한 줄>"` (로컬만).
7. **다음 회전** — FAIL 이 남았으면 예약. 에이전트가 돌고 있으면 긴 대기(20분 이상). 서버를 띄워 둔 채 끝내지 않는다(백그라운드 `make run` 은 회전 끝에 정지).

### 4.3 멈추지 않기 위한 규칙

- **막히면 우회한다.** 사람 확인이 필요한 값은 `차단`, 화면에는 `미확정 (D-nn)`.
- **같은 실패를 2회 넘게 반복하지 않는다.** 3회째면 접근을 바꾸고, 그래도 안 되면 `차단`.
- **게이트를 낮추지 않는다.** 기준 시간 · 허용 오판 수 · 연결률 95% · 300 자 상한을 바꿔 통과시키는 것도 낮추는 것이다.
- **원천에 쓰지 않는다.** `~/.claude/**` · 에이전트 폴더 · 다른 프로젝트 폴더를 고치지 않는다. `~/.claude/settings.json` 에 훅을 설치하지 않는다. 실패한 테스트가 원천에 뭔가 남겼다면 즉시 멈추고 `차단` + 치명 결함으로 올린다.
- **본문을 옮기지 않는다.** 실제 대화 본문을 픽스처 · 로그 · `progress.md` · 커밋 메시지에 붙여 넣지 않는다. 숫자와 경로만.
- **한 파일은 한 사람만.** 동시에 3명 이하. DB 는 개발마다 `data/agentdash-dev{N}.db` 로 나눈다.
- **포트 8095 하나.** 개발 중 다른 포트가 필요하면 8096 · 8097. 다른 프로젝트 포트(8000 · 8020 · 8030 · 8090)를 피한다.
- **밖으로 내보내지 않는다.** push · 배포 · 외부 전송 없음. CDN 스크립트는 고정 버전만.

### 4.4 종료 조건 (EXIT) — 셋을 동시에 만족하면 멈춘다

1. G-01~G-22 **전건 PASS** (`차단` 은 D-번호와 사유가 있을 것. 훅 실설치 측정은 `미검증` 허용 — §2.6)
2. QA 리포트 2종이 있고 **치명 결함 0 · 중대 결함 0**
3. **연속 2회전 동안 `progress.md` 에 새 실측 변화가 없음**

멈출 때 `progress.md` 맨 위에 최종 보고 — 게이트 판정표, 사람이 정해야 할 D-목록, `[가설]` → `확정`/`반박` 결과표, **사람이 할 일**(① `make hooks-install` 실행과 diff 확인 ② 설치 후 `make hooks-check` ③ `WAITING_PERMISSION` 실측), 상시 실행(LaunchAgent) 방법.

### 4.5 중단 · 재개

세션이 끊기면 `progress.md` 최신 섹션 + `decisions.md` 미결만 읽고 **4.2 의 1번부터**. 대화 기록에 의존하지 않는다. (대시보드가 완성되면 끊긴 세션이 D-01 에 `STALE` 로 보일 것이다 — 그것도 G-12 표본으로 쓴다.)

---

## 5. 에이전트 기동 프롬프트 (그대로 복사해 쓴다)

모든 프롬프트는 아래 **공통 서두**로 시작한다.

> 너는 멀티 에이전트 대시보드 개발팀의 [역할]이다. 작업 폴더는 `/Users/gerardo92/Desktop/AI Coding/Multi-agent Dashboard`.
> 작업 전에 `CLAUDE.md` · `goal.md` · `decisions.md` · `progress.md` 를 읽는다. 정본은 `intro.md` · `problem.md` · `spec.md` 이며 읽기만 한다.
> 이 시스템은 **Claude Code 가 남긴 기록을 읽기만 하는** 로컬 대시보드다. 본체는 **부모 연결(`spec.md` §3.2 L-01~L-07)과 상태 판정(§4.2 R-01~R-12)** 이다.
> **원천에 쓰지 않는다** — `~/.claude/**` 와 `~/Desktop/AI Coding/` 의 다른 폴더는 읽기만. 코드는 원천 경로를 `AGENTDASH_CLAUDE_HOME` · `AGENTDASH_AGENTS_ROOT` 로 받고, 테스트는 `tests/conftest.py` 의 가짜 루트만 쓴다. `~/.claude/settings.json` 에 훅을 설치하지 않는다.
> **본문을 저장 · 복사하지 않는다** — 대화 본문 · 도구 결과 · 프롬프트는 DB · 픽스처 · 문서 · 커밋에 넣지 않는다. 남기는 것은 이름 · 경로 · 도구 이름 · 숫자 · 앞 120 자 설명뿐.
> **지어내지 않는다** — 단가는 `config/pricing.yaml`, 회사 · 패턴은 `config/{companies,pipeline}.yaml`. `[가설]` 은 실제 기록으로 확인한 뒤 `decisions.md` 에 근거와 함께 `확정` 으로 적고 쓴다. **조용한 실패 금지** — 못 읽은 줄은 `parse_error`, 못 이은 부모는 "부모 미확인", 모르는 모델은 비용 `NULL`, 못 읽은 칸은 `UNKNOWN`.
> 담당 밖 파일은 고치지 않는다. 끝나면 실측값과 검증 명령을 [본인 진행 파일]에 적는다.
> 환경: `uv` / Python 3.12 · 명령은 `uv run …` · SQLite `data/agentdash-dev{N}.db` · 포트 8095(개발 중 8096 · 8097) · `127.0.0.1` 만.

**아키텍트 (Phase 0)**
> §3.1 의 1~8 을 순서대로 한다. `spec.md` 에서 테이블 11 · 화면 6 · API 10 · 상태 규칙 13 · 검증 11 을 직접 세고 `progress.md` 에 실측으로 적는다.
> 가장 공들일 것은 **가짜 루트와 안전 게이트**다 — 이후 모든 개발 · 테스트가 원천을 건드리지 않도록 막는 울타리다. `check_readonly` 는 소스에서 원천 경로 변수로 `open(..., "w"/"a")` · `write_text` · `unlink` · `rename` · `shutil` 쓰기를 찾고, 읽기 전용 권한(`chmod -R a-w`) 가짜 루트에서 테스트 전체를 돌린다.
> 픽스처는 `make_fixture.py` 로만 만든다. 실제 기록에서 고를 때 이 폴더 프로젝트(`-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard`)의 기록을 쓰면 고객사 자료가 덜 섞인다. 끝나면 `make gate` 판정표를 `progress.md` 에 붙인다.

**개발1 (수집 · 숫자 → D-04 · D-05 · D-06)**
> 웨이브 A: `collect/tail.py`(파일별 offset · inode · 반쪽 줄) → `collect/parsers/{session_file,transcript,meta,workflow}.py` → `core/model.py` 쓰기 → `core/usage.py`(requestId 중복 제거 · `<synthetic>` 제외 · 자기/자손 합) → 비용(§6.1 공식, `cache_creation.ephemeral_5m/1h` 분리, `speed=fast`, Haiku 구간) → `make backfill` · `pricing-check` · `reprice`. `make_fixture.py` 픽스처로 G-02 · G-03, 실제 원천으로 G-04 · G-05 · G-07 · G-08 을 실측한다.
> 확인할 가설: A3(requestId 중복) · A4(자식 기록이 부모에 다시 안 적힘) · `thinking_tokens ⊂ output_tokens` · `active_seconds` 5 분 간격 규칙. 각각 실제 기록 표본으로 확인해 `decisions.md` 에.
> 웨이브 B: D-04 작업량 · 비용(`[추정] API 정가 환산`) · D-05 간트(`state_log`) · `core/pipeline.py`(§7.1 P-01~P-07 · 회사 이름 정규화 · `_구판_*` 제외 · 뒤처짐 ↻) · D-06. G-19 의 고려솔더 기대값을 테스트로 먼저 쓴다.

**개발2 (관계 · 상태 → D-01 · D-02 · D-03)**
> 웨이브 A: `core/linker.py`(L-01~L-07 · 늦게 읽힌 부모 재시도) → `core/state.py`(R-01~R-12 표 기반, 판정 근거 반환, 10 초 주기 + 이벤트 즉시) → `collect/hooks_rx.py`(필요 필드만 · 1 MB 제한) → `scripts/hook_send.sh`(항상 exit 0 · 1 초 · 무출력) · `scripts/hooks_install.py --settings <경로>`(백업 · 덧붙임 · 식별 표시 · diff · 확인 · 문법 검사 · 되돌림) → `app/sse.py`. G-09 · G-10 은 규칙마다 테스트를 먼저 쓴다(경계값 포함). G-15 는 가짜 `settings.json` 으로만.
> 확인할 가설: A1(`sessions/*.json` status 갱신) · A2(`toolUseId` ↔ `tool_use.id`) · L-07(handback ↔ 자식 종료 1:1) · 훅 페이로드 필드(설치 전이므로 공식 문서로 확인하고, 실측은 사람이 설치한 뒤로 미룬다 → `미검증`).
> 웨이브 B: D-01(상태 카드 · "내 차례" · 피드) · D-02(Cytoscape 고정 버전, 보기 3 종, 300 노드 접기) · D-03(계보 · 작업량 · 도구 타임라인 · "원본 보기"는 요청 시 읽기만, 저장 안 함).

**QA1 / QA2 (웨이브 C, 병렬)**
> §3.3 의 담당 범위를 §2 게이트로 검증한다. **고치지 않는다.** 결함은 `DEF-QA{n}-nnn` 으로 재현 절차 · 실측 · 기대값 · 담당을 `outputs/qa{n}-*.md` 에, 통과 항목도 실측과 명령을 함께.
> 기대값은 개발 코드가 아니라 `spec.md` · `config/*.yaml` · 원천 파일을 **자기 스크립트로** 센 값에서 끌어온다. QA1 은 원천 재집계 · 비용 손계산 · 쓰기 코드 사냥, QA2 는 표본 30 건 상태 대조(원천의 마지막 기록 시각 · `sessions/*.json` · 결과 반환 여부를 직접 보고) · 실제 브라우저 · 자기 관찰(G-22).

---

## 6. 원천 형식 기대값 (`spec.md` §2.1 `[실측]` — 파서 테스트의 기대값)

| 원천 | 반드시 읽어야 하는 필드 | 이 컴퓨터에서 본 값 (2026-10-17) |
|---|---|---|
| S1 `sessions/<pid>.json` | `pid` `sessionId` `cwd` `status` `updatedAt` `name` `kind` `version` | `status: "busy"` · `kind: "interactive"` · `version: "2.1.301"` |
| S2/S3 transcript 줄 | `type` `uuid` `parentUuid` `timestamp` `sessionId` `requestId` `isSidechain` `message.model` `message.content[]` `message.usage` | `usage` 에 `input_tokens` `cache_read_input_tokens` `cache_creation_input_tokens` `cache_creation.{ephemeral_5m,ephemeral_1h}_input_tokens` `output_tokens` `output_tokens_details.thinking_tokens` `server_tool_use` `speed` |
| S4 `agent-*.meta.json` | `agentType` `description` `toolUseId` `spawnDepth` `requestShape` | `general-purpose` 203 · `fork` 26 · `Explore` 3 |
| S5/S6 워크플로 | `subagents/workflows/wf_*/agent-*` · `workflows/wf_*.json` | Standard Data Hub 세션에 1 건 |
| 모델 | `message.model` | `claude-opus-5-5` 22,024 · `claude-fable-5-1` 15,348 · `claude-sonnet-5` 8,862 · `claude-opus-5` 7,872 · `claude-opus-4-8` 233 · `<synthetic>` 109 |

숫자는 기록이 늘어나므로 백필 시점에 다시 센다. 형식이 이 표와 다르면 `decisions.md` 에 버전과 함께 적는다.

---

## 7. 열려 있는 결정 — Phase 0 에서 `decisions.md` 로 옮긴다

| # | 결정 | 기본값 `[가설]` | 확인 방법 |
|---|---|---|---|
| D-01 | `requestId` 같은 줄의 중복 여부 (A3) | 같은 `requestId` 는 usage 한 번 | 표본 세션에서 중복 제거 전후 비교 |
| D-02 | 자식 기록의 부모 재기록 여부 (A4) | 없음 → 이중 계산 없음 | 부모 · 자식 토큰 합 비교 |
| D-03 | `thinking_tokens ⊂ output_tokens` | 포함 | 표본 메시지 대조 |
| D-04 | `SubagentHandback` ↔ 자식 종료 1:1 (L-07) | 1:1 | 260 회 띄움 · 220 회 반환의 차이 40 건 원인 조사 |
| D-05 | 훅 페이로드의 서브에이전트 식별 필드 | `transcript_path` 로 붙인다 | 공식 문서 → 사람이 설치한 뒤 실측 |
| D-06 | `active_seconds` 간격 기준 | 5 분 | 표본 세션 체감 대조 |
| D-07 | `.gitignore` 범위 (`data/` · `outputs/e2e/` 스크린샷에 경로 노출) | `data/` 제외, 스크린샷은 커밋하지 않음 | 사람 확인 |
| D-08 | Haiku 5.5 캐시 읽기 단가 (`[추정: 0.1 배]`) | 0.01 · 0.05 | 공식 단가 페이지 대조 (외부 전송 아님 — 읽기) |

---

## 8. 지켜야 할 것

- **읽기만 한다.** 원천 · 다른 프로젝트 · 실제 설정 파일에 쓰기 0. 훅 설치는 사람이.
- **숫자와 경로만 남긴다.** 본문은 DB · 픽스처 · 문서 · 커밋 어디에도 없다.
- **판정은 근거와 함께.** 상태 · 진척 칸 · 비용 모두 "어느 규칙 · 어느 파일" 을 같이 저장한다.
- **조용한 실패 금지 · 지어내지 않기 · 중복 만들지 않기.**
- 정본(`spec.md`)의 결함 · 모순은 고치지 말고 `decisions.md` 에 적고 최종 보고에 올린다.

## 9. 실측 방법

```bash
# spec.md 에서 직접 센다 — 테이블 11 · 상태 규칙 13 · 연결 규칙 7 · 진척 규칙 7 · 검증 11 · 화면 6 · API 10
grep -cE '^CREATE TABLE' spec.md                               # 11
grep -cE '^\| R-[0-9]+[ab]? \|' spec.md                         # 13
grep -cE '^\| L-0[1-7] \|' spec.md                              # 7
grep -cE '^\| P-0[1-7] \|' spec.md                              # 7
grep -cE '^\| V-[0-9]{2} `' spec.md                             # 11
grep -cE '^### D-0[1-6] ' spec.md                               # 6
grep -cE '^\| `(GET|POST) /' spec.md                            # 10

# 원천을 센다 (읽기만)
find ~/.claude/projects -maxdepth 2 -name '*.jsonl' | wc -l                       # 메인 세션
find ~/.claude/projects -path '*/subagents/agent-*.jsonl' -not -path '*/workflows/*' | wc -l   # 서브에이전트
find ~/.claude/projects -path '*/subagents/workflows/*/agent-*.jsonl' | wc -l     # 워크플로 에이전트

make gate          # 판정표
```
