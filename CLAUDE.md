# CLAUDE.md

**멀티 에이전트 대시보드** — 이 컴퓨터의 Claude Code 기록(`~/.claude`)을 **읽기만** 해서 세션 · 서브에이전트 · 워크플로 에이전트의 상태 · 관계 · 작업량 · 비용 · 파이프라인 진척을 `127.0.0.1:8095` 에 보여 준다. 패키지 `agentdash` (`src/agentdash`).
본체는 **부모 연결(`spec.md` §3.2 L-01~L-07) + 상태 판정(§4.2 R-01 · R-02a · R-02b · R-03~R-12)** 이다. 이 둘이 틀리면 구성도 · 관제판 · 작업량이 전부 틀린다.
**지금은 2차-T 디지털 트윈** (정본 `spec.md` **v0.4** · 계획 `docs/superpowers/plans/2026-10-21-agentdash-twin.md` Task 1~8). D-01 관제판을 공장 평면도(라인 = 프로젝트 · 설비 = 에이전트 · 배관 = spawn/handback · 표시등 · 스파크 · 흐름)로 바꾸고, 기존 관제판 항목은 패널로 옮긴다. 1차(G-01~G-22, 2026-10-17 EXIT)는 `goal-v1.md`, 2차-A(G-23~G-30, `1c33a63` EXIT)는 `goal-v2a.md` 에 보존 — 읽기만.
완료 기준 (2차-T, `goal.md` §4.4): **G-01~G-35 전부 PASS (G-01~G-30 회귀 포함 · G-17 은 API 14) · QA r5 2 종 + `e2e/twin` · `self-observe-r6` 치명 0 · 중대 0 · 연속 2 회전 변화 없음.** 새로 백필한 DB 에서 V-01~V-17 이 통과하고, 이 루프가 띄운 에이전트가 D-01 평면도 · D-02 에 실시간으로 나타났다 DONE 으로 흐려진다.

## 먼저 읽는다

1. **`goal.md`** (2차-T) — 목표 · 수용 게이트 G-01~G-35 · 팀 편성 · 루프 프로토콜 · 기동 프롬프트. **전원 필독. 사람만 고친다.** 1차 프로토콜 · 금지 사항(§4.3 · §5 · §8)은 `goal-v1.md`, 2차-A 프로토콜(§0.2 · §4 · G-23~G-30 정의)은 `goal-v2a.md` 가 그대로 유효 — 둘 다 읽기만.
2. **`intro.md` · `problem.md` · `spec.md` v0.4** — 정본. 테이블 11 · 화면 7 · API 14 · 상태 규칙 13 · 연결 규칙 7 · 배치 규칙 7 (§5.4 T-01~T-07) · 진척 규칙 7 · 검증 17 · 훅 이벤트 9 의 출처. **읽기만 한다.** 결함 · 모순은 고치지 말고 `decisions.md` 에 적는다.
3. `decisions.md` — 결정 대장 D-nn (`확정` / `가설` / `가설 반박` / `차단`). 여기 없는 것을 마음대로 정하지 않는다. `[가설]` 은 실제 기록(읽기만)으로 확인한 뒤 근거 파일 · 줄과 함께 `확정`.
4. `progress.md` — 검증된 현황의 유일한 진실. 실측값 + 검증 명령만. 맨 위 "지금 해야 할 것".
5. `progress-dev{1,2}.md` — 개발자별 진행 · 공표(§1, 공용 시그니처) · 요청(§3).

## 절대 규칙 (안전 게이트 G-13~G-16 — 하나라도 FAIL 이면 다른 일을 하지 않는다)

- **원천은 읽기 전용.** `~/.claude/**` 와 `~/Desktop/AI Coding/` 의 이 폴더 밖 전부. 코드는 원천 경로를 **`settings.get().claude_home` · `.agents_root`** 로만 받는다(환경변수 `AGENTDASH_CLAUDE_HOME` · `AGENTDASH_AGENTS_ROOT`, 기본값은 `config/settings.yaml`). **원천 경로 문자열을 코드에 쓰지 않는다** (`check_readonly` 가 `~/` · `/Users/` · `/.claude` 상수를 잡는다). 원천 아래를 쓰기 모드로 여는 코드 0 (`open(…,'w'/'a'/'x'/'+')` · `write_text` · `unlink` · `rename` · `shutil.*` · `sqlite3.connect`). 이 저장소가 `agents_root` 아래에 있으므로 쓰기는 저장소 안(`data/` · `outputs/` · `tests/fixtures/`)에서만 — `settings.is_source_path(p)` 로 확인한다.
- **테스트는 가짜 루트만.** `tests/conftest.py` 의 autouse `_isolate_sources` 가 테스트마다 원천 환경변수를 tmp 의 빈 폴더로 바꾼다. 원천이 필요한 테스트는 `fake_claude_home`(읽기 전용 모드 지원) · `fake_claude_home_ro` · `fake_agents_root` 를 쓴다. `fake_claude_home_rw` 는 **Claude Code 역할(새 세션 파일 쓰기)** 을 흉내 낼 때만. `check_readonly` 는 `chmod -R a-w` 한 가짜 루트로 pytest 전체를 다시 돌린다 — 원천에 쓰는 코드는 여기서 깨진다.
- **훅은 사람이 설치한다.** `make hooks-install` 을 실제 `~/.claude/settings.json` 에 대고 돌리지 않는다. 지금 있는 `PreToolUse` · `PostToolUse` · `Stop` 훅을 깨면 다른 프로젝트 전부가 영향을 받는다. 설치 스크립트 검증은 `--settings <tmp 경로>` 로만(G-15).
- **본문을 저장 · 복사하지 않는다.** 대화 본문 · thinking · 도구 결과 · 도구 입력의 `command`/`prompt`/`content` 는 DB · 픽스처 · 로그 · 문서 · 커밋 메시지에 넣지 않는다. 남기는 것은 이름 · 경로 · 도구 이름 · 숫자 · 설명 앞 120 자. DB TEXT 값 ≤ 300 자(V-04). 픽스처는 **`make fixtures`(`scripts/make_fixture.py`) 로만** 만든다 — 손으로 복사하지 않는다.
- **로컬 전용.** 서버는 `127.0.0.1` 만(`settings.py` 가 다른 host 를 거부). `requests` · `httpx` · `urllib.request` · `socket` 등 외부 전송 import 를 `src/` · `scripts/` 에 두지 않는다(`httpx` 는 테스트 전용). push · 배포 · 외부 전송 없음. CDN 스크립트는 고정 버전만.

## 환경

- `uv` / Python 3.12. **명령은 전부 `uv run …`.**
- SQLite(WAL). 기본 `data/agentdash.db`, 개발마다 `AGENTDASH_DB=data/agentdash-dev{N}.db` (아키텍트 0 · 개발1 1 · 개발2 2). `data/` 는 git 제외.
- 포트 **8095** · `127.0.0.1` 만. 개발 중 `AGENTDASH_PORT=8096` · `8097`. 다른 프로젝트 포트(8000 · 8020 · 8030 · 8090)를 피한다. 백그라운드 `make run` 은 회전 끝에 정지.
- **사람이 8095 에 띄운 개발 서버는 끄지 않는다.** 에이전트는 8096 · 8097 만 쓰고 **자기가 띄운 PID 만** kill 한다(`pkill` · 포트로 찾아 죽이기 금지). G-15 송신 항목이 8095 사용 중으로 `미검증` 이면 정상 — 사람에게 물어 잠깐 끄고 잰다(`goal.md` §0.2).
- 실측 게이트는 새로 백필한 DB 로 잰다: `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` (또는 새 파일).
- 이 폴더 밖에는 쓰지 않는다.

## 명령

`make setup`(uv sync · DB · schema) · `backfill` · `run` · **`gate`**(G-01~G-35 판정표) · `test` · `hooks-install` · `hooks-uninstall` · `hooks-check` · `pricing-check` · `reprice` · `export` · `fixtures`(픽스처 재생성 + 검사) · `check-fixtures` · `check-no-payload` · `check-readonly` · `check-hooks` · `check-bind` · `check-routes` · `check-decisions`(G-23) · `check-contrast`(G-30) · `check-twin`(G-32 · V-17 — 개발1, 없으면 종료코드 2).
미구현 타깃은 `미구현 — 담당 개발N` 을 찍고 **종료코드 2** 로 실패한다. 검사 도구는 `src/agentdash/tools/`(`uv run python src/agentdash/tools/<도구>.py`), 출력 행 형식은 `G-nn  항목  PASS|FAIL|WARN|BLOCKED|미검증  실측` — `gate.py` 가 이 행을 읽는다. 검사기가 없으면 그 게이트는 FAIL(개발 몫) 또는 미검증(QA · 사람 몫).

## QA 리포트 형식

- `gate.py` 는 QA 리포트(`outputs/qa*.md` · `outputs/e2e/self-observe.md`)에서 **표지 줄 `<!-- gate:G-nn -->` 바로 다음 줄 하나**만 그 게이트의 판정 행(`G-nn  항목  PASS|FAIL|WARN|BLOCKED|미검증  실측`)으로 읽는다 — 리포트의 다른 판정 꼴 줄(붙여 넣은 `make gate` 출력 등)은 읽지 않고, 표지가 없으면 `미검증 — QA 재검증 필요(리포트 형식)` (DEF-QA2-008).
- 모든 게이트에 대해 리포트 묶음(`outputs/qa*-*.md` · `outputs/e2e/{self-observe,alerts,design,twin}*.md`, 이름 끝 `-rN` 을 뗀 것)마다 그 표지가 있는 **가장 최근 회차**(N 큰 것, 없으면 원본) 하나를 읽고, 개발 도구 판정과 다르면 **더 나쁜 쪽**(PASS < 미검증 < WARN < FAIL, BLOCKED 은 FAIL 다음 · 출처 표시) — 실측 칸에 읽은 파일을 적는다 (DEF-QA1-103). 새 회차는 덮어쓰지 말고 `-r{N+1}` 로 낸다.

## 규모 (`spec.md` 에서 센 값 — `goal.md` §9 명령)

(`spec.md` v0.4) 테이블 **11** · 화면 **7** (D-01~D-07) · API **14** · 상태 **8** · 판정 규칙 **13** · 연결 규칙 **7** · 배치 규칙 **7** (T-01~T-07) · 진척 규칙 **7** · 검증 **17** (V-01~V-17) · 훅 이벤트 **9**. 게이트 **35** (G-01~G-35).

## 소유 파일 — 한 파일은 한 사람만 (`goal.md` §3 — 1차 표 + 2차-A · 2차-T 새 파일)

| 담당 | 웨이브 A | 웨이브 B | 소유 파일 |
|---|---|---|---|
| **아키텍트** | Phase 0 | — | `settings.py` · `db/{conn.py,schema.sql}` · `config/*.yaml` · `app/{main,templating,placeholders,__main__}.py` · `app/templates/base.html` · `tools/{gate,check_no_payload,check_readonly,check_bind,check_hooks,check_routes}.py` · `scripts/{make_fixture,check_fixtures_redacted}.py` · `tests/conftest.py` · `tests/fixtures/` · `Makefile` · `CLAUDE.md` |
| **개발1** 수집 · 숫자 | `collect/{watcher,tail}.py` · `collect/parsers/*` · `core/usage.py` · 비용 · 백필 · `pricing-check` · `reprice` | D-04 · D-05 · D-06 · `core/pipeline.py` · CSV | `collect/`(훅 수신 제외) · `core/{usage,pipeline,model}.py` · `app/routers/{usage,timeline,pipeline}.py` · `tools/{check_counts,check_parse_errors,check_usage_sum,check_cost,check_pipeline}.py` · `tests/test_{parsers,tail,cost,pipeline,usage_page}.py` |
| **개발2** 관계 · 상태 | `core/linker.py` · `core/state.py` · `collect/hooks_rx.py` · `scripts/{hook_send.sh,hooks_install.py}` · `app/sse.py` | D-01 · D-02 · D-03 · `core/graph.py` | `core/{linker,state,graph}.py` · `collect/hooks_rx.py` · `scripts/hook*` · `app/sse.py` · `app/routers/{pages,agents,graph,stream,hooks}.py` · `tools/check_link_rate.py` · `tests/test_{state,linker,realtime,graph}.py` |
| **QA1 / QA2** | — | 웨이브 C | `outputs/qa1-데이터안전*.md` · `outputs/qa2-상태대조*.md` · `outputs/e2e/` — **고치지 않는다** |

**2차-A 새 파일** (`goal.md` §3.2 · 계획 Global Constraints)

| 담당 | 새로 갖는 파일 |
|---|---|
| **아키텍트** | `config/budget.yaml` · `tools/check_decisions.py` · `tools/check_contrast.py` · `tests/test_design.py` · `goal-v1.md`(읽기만) |
| **개발1** | `core/budget.py` · `app/routers/insights.py` · `templates/insights.html` · `tools/check_{usage_est,budget,trend,efficiency}.py` · `tests/test_{usage_est,budget,insights,check_counts}.py` |
| **개발2** | `templates/_alerts.html` · `tests/test_alerts.py` |

**2차-T 새 파일** (`goal.md` §3 · 계획 Global Constraints)

| 담당 | 새로 갖는 파일 |
|---|---|
| **아키텍트** | `goal-v2a.md`(읽기만) · `tools/gate.py` G-31~G-35 · `Makefile` `check-twin` |
| **개발1** | `core/usage.py` 의 `spark` (Task 2) · `tools/check_twin.py` · `tests/test_check_twin.py` |
| **개발2** | `core/twin.py` · **`app/routers/twin.py`** (자리는 아키텍트 Phase 0 — placeholder `/api/v1/twin`, 이제 개발2 소유) · `templates/_twin.html` · `tests/test_{twin,twin_page}.py` |

- `main.py` `ROUTERS` 에 `twin` 등록 완료 (Phase 0). 개발2 가 Task 4 에서 `twin.build(...)` 를 연결하며 placeholder 를 지운다. 응답 키는 `progress-dev2.md` §1 에 공표.
- 새 JS · CSS 라이브러리 · CDN 0 (spec §7.4). 색은 `base.html` 토큰만. 배치는 서버가 결정적으로(T-07) — 브라우저가 좌표를 다시 계산하지 않는다.
- 기존 관제판 항목은 하나도 빼지 않는다 — `tests/test_dashboard.py` 가 회귀 기준(G-34). 테스트를 지워서 통과시키는 것은 게이트 낮추기다.

- `main.py` `ROUTERS` 에 `insights` 등록 완료 (Task 8 뒤 placeholder 분기 제거, R-2A-2). 공용 시그니처 `budget.status · worst · trend · efficiency` 는 개발1 이 Task 7 끝에 `progress-dev1.md` §1 에 공표.
- 색 · 간격 · 글꼴은 `base.html` 의 CSS 토큰 · 공통 클래스만 쓴다 (spec §7.3). 이름은 `progress.md` 「2차-A — Phase 0」 공표 칸.

- `core/model.py`(데이터 클래스 · DB 쓰기)는 개발1 소유. 개발2 가 필드가 더 필요하면 `progress-dev2.md` §3 에 요청.
- 공용 시그니처(`model.upsert_agent`, `state.evaluate(agent, now) -> (state, rule)`, `linker.resolve(agent)`)는 **먼저 정한 사람이 `progress-devN.md` §1 에 공표**.
- 아키텍트 소유 파일(`schema.sql` · `config/*.yaml` · `main.py` · `conftest.py` · 게이트 도구)을 바꿔야 하면 `progress-devN.md` §3 에 요청한다.

## 코드 규약

- 라우터: `app/routers/<영역>.py` 에 `router = APIRouter()`, `main.py` 의 `ROUTERS` 에 등록. 화면을 구현하면 그 함수의 `placeholders.label(...)` 호출을 지운다 — `check_routes` 가 남은 placeholder 수를 센다. API 응답의 `_placeholder` 키도 같다.
- 렌더: `templating.render(request, "x.html", ctx)` · 공통 틀 `templates/base.html`.
- 설정: `from agentdash import settings; s = settings.get()` — 매번 환경변수를 다시 읽는다(테스트가 monkeypatch 로 가짜 루트를 넣는다). 값이 빠지면 `SettingsError`(조용한 기본값 금지). `stale_after_sec` 300 · `slow_after_sec` 90.
- DB: `from agentdash.db import conn; conn.connect()` · `conn.init_db(path)`. 원천 아래 경로 · 이미 있는 하드 링크 파일(`st_nlink > 1`)은 거부한다. `init_db` 는 옛 DB 에 없는 열(spec v0.3 `output_est` · `cost_est_usd`)을 덧붙인다 — 값은 다시 백필해야 채워진다.
- 단가 · 회사 · 단계 · 예산은 `config/{pricing,companies,pipeline,budget}.yaml` 에서만 읽는다(코드에 숫자 · 회사명 · 금액을 박지 않는다). `budget.yaml` 금액은 사람만 넣는다 — 실제 파일에 금액 기입은 치명 결함. 길이 숫자(D-17)는 DB 에 남기지 않는다.
- **조용한 실패 금지** — 못 읽은 줄은 `parse_error`, 못 이은 부모는 "부모 미확인", 모르는 모델은 비용 `NULL`, 못 읽은 칸은 `UNKNOWN`. `try/except` 로 결과를 끼워 넣지 않는다.
- 훅 계약 (`check_hooks` 가 이대로 부른다): `uv run python scripts/hooks_install.py --settings <경로> --yes` (덧붙임) · `… --uninstall --yes` (제거) · `bash scripts/hook_send.sh < payload.json` (항상 exit 0 · ≤ 1 초 · 표준출력 0 바이트). 덧붙인 항목의 명령 문자열에 `hook_send.sh` 가 들어가야 식별된다.
- 픽스처 형식 메모: 기록에는 `assistant`/`user` 밖에도 `api-request-blob` · `api-request` · `attachment` · `ai-title` · `last-prompt` · `mode` 등 줄 종류가 많다(D-11). 모르는 종류는 무시하되 세지 않는다.

## 작업 원칙

- **지어내지 않는다.** 단가는 `spec.md` §6.1, 회사 · 패턴은 §7.1 그대로. 모르면 `미확정 (D-nn)`.
- **게이트를 낮추지 않는다.** 기준 시간 · 허용 오판 수 · 연결률 95% · 300 자 상한 · 검사 규칙을 바꿔 통과시키는 것도 낮추는 것이다.
- **막히면 우회한다.** 사람 확인이 필요한 값은 `decisions.md` 에 `차단`, 같은 실패 3 회째면 접근을 바꾼다.
- 실패한 테스트가 원천에 뭔가 남겼다면 즉시 멈추고 `차단` + 치명 결함.
