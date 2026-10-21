# QA2 r5 — D-01 공장 평면도 E2E (G-33 · G-34 · G-35, 2026-10-21, 계획 Task 8, 커밋 33d2d0a)

> **고치지 않았다** — 코드 · 테스트 · 설정 · 정본 · progress 변경 0. 쓴 곳: 이 파일 · `outputs/qa2-상태대조-r5.md` · `outputs/e2e/self-observe-r6.md` · `outputs/e2e/qa2-r5/`(스크린샷 12) · `outputs/qa2/`(새 이름: `twin_driver_r5.py` · `serve_fake_budget_r5.py` · `table_r5.py` · `*-r5*` 중간 결과 · 서버 로그) · `data/agentdash-qa2.db`(새 백필) · `data/agentdash-qa2-twin-fake.db` · `data/qa2-fake-twin/`.
> 원천은 읽기만. 훅 설치 0 — 훅 이벤트는 가짜 루트 서버에 `curl -X POST http://127.0.0.1:8097/hooks/event`. 본문 없음(가짜 기록의 사용자 줄은 자리표 `x`, 도구 입력 `{}`). 실제 `config/budget.yaml` 은 읽지도 쓰지도 않음(`git status config/` 변경 0) — 가짜 한도는 `serve_fake_budget_r5.py` 프로세스 안에서 `settings.load_yaml("budget.yaml")` 만 바꿔 끼우고 `outputs/qa2/fake-budget-r5.json` 을 읽게 함(측정 뒤 지움).
> 서버는 8097 만, 내가 띄운 PID 만 kill: 실제 DB 서버 uv 22653 / python 22655 (04:16:39Z ~ 04:24:50Z, 감시기 켬) → 가짜 루트 서버 uv 24570 / python 24572 (04:24:55Z ~ 04:29:30Z, 감시기 켬) · S1 용 `sleep 7200` pid 24568. 끝에 8097 LISTEN 0. 사람이 띄운 8095 (pid 11764) 는 건드리지 않음 — 끝까지 LISTEN.
> 브라우저: Claude in Chrome 새 탭 1 개(1315153137, 끝에 닫음) · 창 1400×653→597 고정 — 390 px 는 같은 출처 iframe. 대화상자 0 · 실제 Notification 권한 창 0 (기록용 가짜 `Notification` 클래스 — 아래 §2.3).

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-33 실시간 | **PASS** | S1 → 세션 설비 1.22 s · transcript → RUNNING 0.16 s · 서브 2 → 설비 2 개 1.21 s · spawn 배관 2 · 흐름 2 · 훅 POST → `data-state` 19 ms · 경광등 + 「!」 · handback → 역흐름 1 회 148 ms → DONE 155 ms · 흐림 0.5 |
| G-34 관제판 흡수 | **PASS** | v0.3 항목 7 종 실제 화면에 모두 있음 · `test_dashboard.py` 2차-T 커밋 0 · 12 passed · 알림 첫 로드 0 · 전이 1 · 탭당 SSE 1 · 예산 띠 over/warn/unset |
| G-35 시각 | **PASS** (경미 4) | 7 화면 × 390/1400 × 밝은/다크/시스템 = 42 측정 가로 스크롤 0 · reduced-motion 움직임 13 → 0 · Tab 순회 → Enter D-03 · 콘솔 앱 오류 0 · 상태 색 8 토큰 두 테마 모두 서로 다름 |

결함: 치명 0 · 중대 0 · **경미 4** (DEF-QA2-401 ~ 404, §4).

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-33 -->
G-33  실시간 — 가짜 루트 새 세션 + 서브 2 ≤ 5 초 · 훅 → 표시등 ≤ 1 초 · handback 역흐름 + DONE  PASS  r5 가짜 루트(감시기 켬) S1 쓰기 → 세션 설비 등장 1.22 s (WAITING_INPUT R-05) · transcript 첫 줄 → RUNNING 0.16 s · Agent×2 + 자식 파일 → 서브 설비 2 등장 1.21 s · spawn 배관 2 · 흐름 2 · 입자 2 · flowMiss 0 · 훅 permission_prompt POST → data-state WAITING_PERMISSION 19 ms (다시 칠하기 5.4 ms) · 경광등 twin-spin + 「!」 · 내 차례 맨 위 · handback → burst.rev 1 회 148 ms · DONE 155 ms · opacity 0.5 · 콘솔 오류 0
<!-- gate:G-34 -->
G-34  관제판 흡수 — v0.3 항목 전부 · test_dashboard 무삭제 · 알림 · 예산 띠  PASS  r5 실제 DB D-01 패널: 상태 카드 7 · 내 차례 + cwd/이름 복사(복사 값 = cwd · 세션 이름) · 살아 있는 목록/선택한 설비 · 오늘 출력·요청·도구 호출·작성 파일 · 상위 5 · 최근 상태 변화 피드 · 파싱 오류 0 건 · git log 1c33a63..HEAD -- tests/test_dashboard.py 0 커밋 · 12 passed · 알림 첫 로드 0 · 전이 1 (입력 대기 · 권한 대기 각 1) · 탭당 SSE 1 (서버 로그 페이지 로드당 /api/v1/stream 1) · 예산 띠(가짜 한도 프로세스 안) over 「예산 초과」 · warn 「예산 경고」 · unset 띠 없음
<!-- gate:G-35 -->
G-35  시각 — 두 테마 · 390/1400 · reduced-motion 0 · 키보드 · 콘솔 0  PASS  r5 실제 DB 7 화면 × 390/1400 × 밝은·다크·시스템 42/42 scrollWidth=clientWidth · D-01 reduced-motion(@media 블록 그대로 주입 + matchMedia) 움직임 13→0 · 가짜 루트 RUNNING/WAITING/handback 동안 최대 0 · burst 0 · 배지는 정지 표시 · Tab 맞춤→svg→세션→서브…→QA2 · 포커스 3 px · Enter → /agents/A%3Aa328106ffaca540ab · 앱 콘솔 오류 0 (두 테마) · 상태 색 토큰 8 두 테마 각각 서로 다름 · 경미 4 (DEF-QA2-401~404)

---

## 1. G-33 실시간 (가짜 루트 · 감시기 켬)

### 1.1 환경

- 가짜 루트 `data/qa2-fake-twin/{claude_home,agents_root}` (저장소 `data/` 안 — 도우미가 `realpath` 로 확인). 새 DB `data/agentdash-qa2-twin-fake.db`.
- 서버 `AGENTDASH_CLAUDE_HOME=$PWD/data/qa2-fake-twin/claude_home AGENTDASH_AGENTS_ROOT=$PWD/data/qa2-fake-twin/agents_root AGENTDASH_DB=data/agentdash-qa2-twin-fake.db AGENTDASH_PORT=8097 uv run python outputs/qa2/serve_fake_budget_r5.py` (예산 손잡이만 다른 `python -m agentdash.app` 와 같은 uvicorn 기동, 감시기 켬).
- 도우미 `outputs/qa2/twin_driver_r5.py` — **실제 Claude Code 순서**: ① 프로세스 시작 = `sessions/<pid>.json` (status idle, transcript 아직 없음) ② 첫 프롬프트 = transcript 생김(user 줄 + assistant Read) → S1 busy ③ assistant `Agent`×2 줄 → `subagents/agent-<id>.meta.json` → `agent-<id>.jsonl` 첫 줄 ④ 반환 = 자식 `SubagentHandback` tool_use → 부모 `<task-notification>` completed. S1 pid = 내가 띄운 `sleep 7200`.
- 계측: 페이지 로드 뒤 `MutationObserver` 로 `#twin-svg [data-key]` 의 첫 등장 시각 · `data-state` 변화 시각(`Date.now()`)을 기록, 도우미가 찍은 쓰기 시각(같은 기계 시계)과 뺌. 개발2 손잡이 `window.agentdashTwin` 의 `flows` · `flowMiss` · `appeared` · `lastPaintMs` · `stateLog` · `machineEl` 같이 읽음.

### 1.2 결과

| 단계 | 쓰기 시각 (UTC) | 화면 반응 | 걸린 시간 | 기준 | 판정 |
|---|---|---|---|---|---|
| ① S1 (idle) 만 | 04:25:28.185 | 세션 설비 등장 `WAITING_INPUT` (R-05 「기록 없음」) · `appeared` 1 | **1.22 s** | ≤ 5 s | PASS |
| ② transcript 첫 줄 + S1 busy | 04:25:41.220 | 세션 `data-state` → `RUNNING` (R-02a) | **0.16 s** | ≤ 5 s | PASS |
| ③ Agent×2 + 자식 meta · jsonl | 04:25:52.196 | 서브 설비 2 등장 `RUNNING` (1 ms 차) · spawn 배관 2 (`data-kind=spawn` 세션→서브 1 · 2) · `flows` 0→2 · `flowMiss` 0 · 입자 `.flow.on` 2 · `appeared` 3 | **1.21 s** | ≤ 5 s | PASS |
| ④ 훅 `Notification` `permission_prompt` POST (세션) | 04:26:12.266 (curl 시작) | 서버 `state WAITING_PERMISSION · R-01 · changed:true` (응답 31 ms) · `data-state` → `WAITING_PERMISSION` · 다시 칠하기 `lastPaintMs` 5.4 ms · `.beacon` display inline + `twin-spin` · `.bang` 「!」 inline · 「내 차례」 맨 위 「권한 대기 R-01」 · 라인 머리 「가동 3 · 대기 1」 | **19 ms** | ≤ 1 s | PASS |
| ⑤ 자식 1 handback + 부모 알림 | 04:26:28.907 | 자식 1 `DONE` (R-08) · `flows` 2→3 · `.mbody` opacity 0.5 · 세션은 새 기록이 훅을 이겨 `RUNNING` (R-01 단서) | DONE 0.24 s | — | PASS (burst 요소는 관찰기를 늦게 걸어 못 봄 → ⑥ 에서 다시) |
| ⑥ 자식 2 handback + 부모 알림 (관찰기 먼저) | 04:26:41.038 | `path.burst.rev` **1 개** (자식 2 의 spawn 관을 거꾸로 — handback 관이 아직 없을 때의 경로) 148 ms · `DONE` 155 ms · `flows` 3→4 · opacity 0.5 · 그 뒤 다시 받기로 handback 배관 추가 · 둘 다 DONE → 입자 `.flow.on` 0 | **역흐름 0.15 s → DONE 0.16 s** | 역흐름 1 회 → DONE | PASS |

- 해석: 실제 Claude Code 순서에서는 세션 설비가 **S1(프로세스 시작) 때 이미** WAITING_INPUT 으로 나타나고(1.22 s), 첫 기록이 들어오면 0.16 s 에 RUNNING 이 된다. 개발2 가 「깨끗이 못 쟀다」 한 세션 등장은 이 두 시각으로 따로 쟀다 — 둘 다 5 초 안.
- 실제 기록에서도 같은 일이 일어났다: QA 중 사람이 새 Claude Code 세션 `S:43970992…` 를 열자 실제 DB 서버 피드에 「13:23:53 입력 대기 R-05 S1 status=idle · 기록 없음」 이 뜨고 평면도 라인이 5 → 6 이 됐다 (`qa2-r5/real-light-feed-qa1-done.jpg`).
- 스크린샷: `qa2-r5/fake-light-spawn-3machines.jpg` · `fake-light-waiting-permission-beacon.png` · `fake-light-handback-done.jpg`.

---

## 2. G-34 관제판 흡수

### 2.1 v0.3 관제판 항목 ↔ D-01 패널 (실제 DB 서버, 1400 px, 밝은 · 다크)

| v0.3 항목 (spec §7 D-01 · §13-16) | D-01 패널에서 본 것 | 판정 |
|---|---|---|
| 상태별 카드 숫자 | 카드 7: 실행 · 입력 대기 · 권한 대기 · 잠듦 · 자식 대기 · 멈춤 의심 · 오늘 끝남(+실패 n) — 실측 3 · 1 · 0 · 0 · 0 · 6 · 14 (04:17Z) / SLEEPING 전이 뒤 잠듦 1 | O |
| 「내 차례」 + 복사 버튼 | 「내 차례 — 권한 대기 먼저, 그다음 기다린 시간 긴 순」 · 행 = 상태 · 규칙 · 기다린 시간 · 이름 · 프로젝트 · 마지막 도구 · 버튼 「cwd 복사」 「이름 복사」. 클립보드를 기록용으로 바꿔 두 버튼 클릭 → 기록 = 그 세션의 cwd 경로 · 세션 이름, 버튼 글자 「복사됨」 | O |
| 선택한 설비 / 살아 있는 에이전트 목록 | 「선택한 설비」 카드 (선택 없을 때 「살아 있는 에이전트 9」 목록) · Tab 포커스 250 ms 뒤 요약 | O |
| 오늘 출력 · 도구 호출 · 작성 파일 | 「오늘 KST」 카드: 출력 토큰 556,015 · 요청 1,115 · 도구 호출 1,220 · 작성 파일 57 | O |
| 상위 5 에이전트 | 「상위 5 에이전트 오늘 출력」 막대 5 줄 + D-03 링크 | O |
| 최근 상태 변화 피드 (SSE) | 「최근 상태 변화」 — 실시간으로 QA1 끝남 R-08 · 오케스트레이터 잠듦 R-03 → 실행 R-02a · 새 세션 입력 대기 행이 들어옴 | O |
| 파싱 오류 건수 | 「파싱 오류 0 건」 | O |
| 예산 띠 | 아래 §2.4 — 맨 위 한 줄, 한도 없으면 행 자체 없음 | O |

- `git log --oneline 1c33a63..HEAD -- tests/test_dashboard.py` → **0 줄** (2차-T 동안 수정 · 삭제 0). `uv run pytest -q tests/test_dashboard.py` **12 passed**. 함께 `tests/test_dashboard.py tests/test_twin_page.py tests/test_realtime.py tests/test_state.py` 85 passed · 전체 `uv run pytest -q` **419 passed**.
- 스크린샷: `qa2-r5/real-light-panel-kpi-top5.jpg` · `real-light-feed-qa1-done.jpg` · `real-dark-1400-first.jpg`.

### 2.2 알림 회귀 (가짜 루트)

| 경우 | 기대 (spec §7.2) | 실측 | 판정 |
|---|---|---|---|
| 첫 로드 | 이미 대기 중이던 것은 알리지 않음 | 세션이 WAITING_PERMISSION 인 채 새로고침 → `agentdashAlerts.notified` 0 · 가짜 기록 0 · 제목 `(1) 공장 평면도 …` | PASS |
| 전이 1 | 대기로 바뀌는 순간 1 번 | 새 세션 S1 idle → 「입력 대기」 1 (tag `S:9999…0001\|04:25:28Z`, 본문 `qa2-twin-r5 · qa2-twin-r5`) · 훅 permission_prompt → 「권한 대기」 1 (tag `…\|04:26:12Z`, POST 뒤 33 ms) · RUNNING · DONE 전이 0 건 | PASS |
| 같은 대기 재전이 | 다른 `state_since` 면 다시 1 | RUNNING → WAITING_PERMISSION 을 두 번 더 → 각 1 (합 4 = 전이 수와 같음) | PASS |
| 탭당 SSE 1 | EventSource 1 (알림과 평면도 공유) | 서버 로그 `GET /api/v1/stream` 이 페이지 로드 1 번에 2 → 3 (+1) · 평면도는 `openStream` 공유(정적 계약 `test_twin_page.py`) | PASS |

Notification 계측 방법: 실제 권한 창을 띄우지 않으려고 로드 **뒤** `window.Notification` 을 기록용 가짜 클래스로 바꿈(`permission = "granted"`, 생성 시 `window.__notes` 에 제목 · tag · 시각만). `_alerts.html` 은 `Notification` 을 호출 때 전역에서 읽으므로 가짜가 쓰임. `localStorage agentdash.alerts=on`. 「첫 로드 0」 은 `notified` 카운터로 셈. 실제 OS 알림은 사람이 확인(r4 와 같음).

### 2.3 예산 띠 회귀 (가짜 한도 — 프로세스 안)

| 가짜 한도 (`fake-budget-r5.json`, 오늘 추정 $0.02004) | `/api/v1/budget` worst | D-01 | 판정 |
|---|---|---|---|
| 전체 일 0.018 · 월 0.024 · 프로젝트 `qa2-twin-r5` 월 0.0001 | over | 맨 위(평면도 카드 위, top 135 px < 평면도 265 px) 빨강 「**예산 초과** 오늘 전체 111 % · 이번 달 전체 83 % · qa2-twin-r5 이번 달 20040 % [추정] API 정가 환산 · D-07 비용 · 효율 →」 (href `/insights`) | PASS |
| 전체 일 0.024 (83 %) 만 | warn | 「예산 경고」 띠 | PASS |
| 파일 지움 = 전부 null | null | `#budget-band` 요소 없음 (CSS `:not(:has(#budget-band))` 격자로 행 자체 없음) — 실제 DB 서버도 같음 (실제 budget.yaml 전부 null) | PASS |

스크린샷: `qa2-r5/fake-light-budget-band-over.jpg`.

---

## 3. G-35 시각 (실제 DB — `data/agentdash-qa2.db` 새 백필, 감시기 켬)

### 3.1 테마 × 폭 (같은 출처 iframe 390 / 1400 — 창 크기 조절 대신)

| 화면 | 390 밝은 | 390 다크 | 390 시스템 | 1400 밝은 | 1400 다크 | 1400 시스템 |
|---|---|---|---|---|---|---|
| D-01 `/` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |
| D-02 `/graph` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |
| D-03 `/agents/A%3Aa328106ffaca540ab` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |
| D-04 `/usage` | 375/375 | 375/375 | 375/375 | 1385/1385 (다시 잼) | 1385/1385 | 1385/1385 |
| D-05 `/timeline` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |
| D-06 `/pipeline` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |
| D-07 `/insights` | 375/375 | 375/375 | 375/375 | 1385/1385 | 1385/1385 | 1385/1385 |

값 = `scrollWidth/clientWidth` (iframe 스크롤바 15 px). 42/42 같음, 넘친 요소(svg · 표 · sr-only 안 제외) 0. 배경 밝은 rgb(245,246,248) · 다크 rgb(18,19,22). 시스템 모드는 측정 중 OS 설정이 다크 → 밝은으로 바뀌어 **둘 다** 실측됨(처음 `prefers-color-scheme: dark` 참 → 뒤에 거짓). 390 px D-01 은 평면도가 자기 카드 안에서만 움직이고 페이지 가로 스크롤 0 (`qa2-r5/real-dark-390-iframe.png`).
테마 토글: `data-theme` 바꿈 → `agentdashTwin.redraws` +1 · 표시등 `.lamp.core` fill 이 그 테마 토큰 값으로 (RUNNING 밝은 rgb(30,142,78) / 다크 rgb(52,192,111)).

### 3.2 상태 색 구분

- 토큰 `--st-*` 8 개가 두 테마 각각 서로 다른 값(밝은 #1e8e4e · #a67c00 · #d9650a · #2f6fdb · #1a8fb8 · #80868f · #d93025 · #8e44ad / 다크 #34c06f · #e6b422 · #f08a2c · #4d8ef7 · #3bb6e0 · #8e939b · #f2564b · #b06ad6).
- 실제 화면 표시등: SLEEPING · DONE · RUNNING · WAITING_INPUT · STALE 5 종이 그 토큰 값으로 칠해짐 + 모양 단서(맥박 · 경광등+「!」 · 경보 삼각형 · z · 흐림). WAITING_PERMISSION 은 가짜 루트에서(주황 + 경광등 + 「!」). 대비는 개발 `check_contrast` G-30 PASS 를 그대로 둠(다시 재지 않음).

### 3.3 reduced-motion (에뮬레이션 대신 — 앱의 `@media (prefers-reduced-motion: reduce)` 블록 규칙 4 개를 스타일시트에서 그대로 꺼내 조건 없이 주입 + `matchMedia("(prefers-reduced-motion: reduce)")` 참)

| 장면 | 주입 전 `#twin-svg` 안 running 애니메이션 | 주입 뒤 |
|---|---|---|
| 실제 DB (RUNNING 맥박 · 광 4 · 경광등 1 · 경보 깜빡임 6 · 흐름 2) | 13 | **0** · CSS 전이 0 |
| 가짜 루트 — 다시 깨운 자식 RUNNING · 훅 WAITING_PERMISSION · handback (50 ms 간격 표본 최대값) | — | **최대 0** · burst 요소 0 · WAITING 배지(경광등 · 「!」) 는 display inline 으로 정지 표시 |

### 3.4 키보드 (실제 키 입력)

「맞춤」 클릭 → Tab: 평면도 svg(`role=group`, aria-label 「공장 평면도 — 라인 = 프로젝트 · 설비 = 에이전트 · 배관 = 띄움/반환」) → 세션 `S:fa752590` → 서브 `A:a770b699` → `A:a4a00bef` (QA1) → `A:a328106f` (나) 순. 포커스 테두리 3 px. Enter → `/agents/A%3Aa328106ffaca540ab` (D-03 「QA2 2T r5 twin E2E · 상세」). 설비마다 `role=button` · `tabindex=0` · aria-label(이름 · 상태 · 경과 · 도구 · 접힌 완료). 스크린샷 `qa2-r5/real-light-keyboard-focus.jpg` · `real-enter-d03.jpg`.

### 3.5 콘솔

7 화면 × 밝은(localStorage light) · 다크(localStorage dark) · 시스템 — 앱 콘솔 오류 **0**. 경고 2 는 확장 프로그램 content script(`chrome-extension://…/contentscript.js` MaxListenersExceeded) — 앱 아님. 가짜 루트 실시간 동안도 0.

### 3.6 「한눈에 가시성」 평가 (실제 DB 24 h — 라인 5→6 · 설비 11~13 · 반입구 3 · 배관 13 · 접힌 완료 10~13)

- 좋음: 라인 카드 머리(이름 · 가동 · 대기) · 주 설비/보조 설비 구분 · 굵은 배관과 둥근 꺾임 · 자식 RUNNING 동안 점 입자 · DONE 흐림이 한눈에 읽힌다. 설비끼리 겹침 0 (DOM 사각형 16 쌍 비교). 글자 겹침 후보 13 은 모두 「0/분」 위 · 「[추정]」 아래 두 줄 붙음(줄 상자만 닿음, 확대해 보면 읽힘).
- 아쉬움: DEF-QA2-401 ~ 404 (아래).

---

## 4. 결함

| ID | 심각도 | 내용 | 재현 · 근거 | 담당 제안 |
|---|---|---|---|---|
| DEF-QA2-401 | 경미 | 설비 상태줄 「경과」 가 `state_since` 기준이라, **새 백필 직후에는 모든 설비가 같은 경과**(백필 뒤 흐른 시간)를 보인다 — 30 분 전에 끝난 서브에이전트도 「끝남 · 1분 8초」, 이틀 전 기록이 끊긴 STALE 세션도 「멈춤 의심 · 1분 8초」. 오래 켜 둔 서버에서는 덜 보이지만 서버를 새 DB 로 띄우면 처음 몇 분 동안 오해를 준다. | 실제 DB 새 백필 04:16:39Z → 04:17:50Z D-01 aria-label 전부 「경과 1분 8초」 · twin 응답 `since` = 2026-10-21T04:16:39Z (백필 시각) — `ended_at` 03:51:12Z · `last_event_at` 10-14 와 무관 | 개발2 (twin `elapsed_s` 를 DONE/FAILED 는 `ended_at`, STALE 은 `last_event_at` 기준으로 하거나 백필 판정 때 `state_since` 를 근거 시각으로) |
| DEF-QA2-402 | 경미 | 넓은 화면에서 라인이 **세로로만** 쌓여(서버 배치 T-04) 평면도 오른쪽 약 40 % 가 빈 점 격자이고, 「맞춤」 이 폭 맞춤(배율 1)으로 떨어져 첫 화면에 라인 6 개 중 1 개만 보인다 — 「한눈에」 가 약하다. | 1400 px · vb 900×478 · 라인 박스 폭 504 / 평면도 폭 900 · 라인 y 0~1680 · `agentdashTwin.scale` 1 (`qa2-r5/real-dark-1400-floor.jpg`) — 개발2 해석 「배치는 T-04 대로 두고 브라우저에서 바꾸지 않았다(T-07)」 와 같은 관찰 | 사람(spec T-04 에 라인 여러 열 배치를 넣을지) · 개발2 |
| DEF-QA2-403 | 경미 | **다시 깨운 뒤 두 번째 반환**에는 역흐름이 없다 — handback 엣지가 이미 있어 `edge.new` 가 오지 않으므로 `flowNow` 가 불리지 않음. DONE 흐림은 된다. 실제 기록에 반환 ≥ 2 인 서브에이전트가 있다(linker 주석 「실측 16 건」). | 가짜 루트: 자식 2 활동 1 줄(RUNNING 04:27:51Z) → handback 04:27:54.957Z → DONE (state_log 04:27:55Z) 인데 `agentdashTwin.flows` 0→0 · burst 요소 0 (첫 반환 때는 1) | 개발2 (`agent.state` DONE R-08 전이 때도 역흐름 1 회, 또는 SSE 에 반환 이벤트) |
| DEF-QA2-404 | 경미 | 상태줄 아래 「지금 도구」 글자가 길면 상자 clipPath 에서 **글자 중간에 잘린다**(말줄임 없음): `mcp__claude-in-chrome__javasc|` 가 오른쪽 경계를 53.6 px 넘어 잘림. 또 DONE 설비에도 마지막 도구가 「지금 도구」 자리에 남는다(`Grep` · `SubagentHandback`). | 실제 DB 1400 · 390 의 `A:a328106f` 상자 (`qa2-r5/real-dark-390-iframe.png`) · 가짜 루트 DONE 자식 상자 (`fake-light-handback-done.jpg`) | 개발2 (24 자 규칙처럼 도구 이름도 잘라 「…」, 끝난 설비는 「마지막 도구」 또는 숨김) |

관찰 (결함 아님):
- O-1 라인 이름은 `project_path` 마지막 이름이라 `SongWol QR Platform/contracts` 에서 띄운 라인이 「contracts」 로 보인다(key 는 SongWol-QR-Platform). spec 「라인 = 프로젝트」 와 어긋나 보일 수 있음 — 사람 확인.
- O-2 STALE 서브에이전트 4 개가 같은 라인의 STALE 세션이 아니라 「부모 미확인 반입구(부모 범위 밖 3)」 아래에 있다 — 부모가 24 h 밖의 다른 서브에이전트(DONE)라서, D-25 가설 그대로(DB `parent_key` 대조 일치).
- O-3 「내 차례」 의 기다린 시간은 상태가 바뀐 때가 아니라 마지막 기록부터 센다(훅으로 막 WAITING_PERMISSION 이 된 행이 「21초」) — v0.3 동작 그대로, 2차-T 회귀 아님.
- O-4 숨은 탭 입자 정지는 확장 도구로 탭을 숨길 수 없어 실측 못 함(정적 계약 `test_twin_page.py` 만) — 개발2 와 같은 한계.

## 5. 정리 · 안전

- 띄운 PID 만 kill (실제 DB 서버 22653/22655 · 가짜 서버 24570/24572 · sleep 24568) → 8097 LISTEN 0. 8095 (pid 11764) 그대로. 탭 닫음.
- 원천 쓰기 0 · 훅 설치 0 · 실제 `config/budget.yaml` 변경 0 · `git status` 에 내 새 파일(outputs/) 외 변경 0.
- **`~/.claude/settings.json` 관찰**: 시작 sha1 `8641eb22e8f5…` · mtime 1792131308 → 끝 sha1 `8a539108c7d4…` · mtime **1792556826 (04:27:06Z)**. 같은 분에 `~/.claude/history.jsonl` · `~/.claude/backups/` 도 바뀜 → Claude Code 자신(사람 세션의 설정 저장 — 키에 `autoMode` · `theme` 등)으로 보인다. QA2 프로세스는 이 파일을 열지 않았다(내 쓰기는 `data/qa2-fake-twin/` · `outputs/` · `data/agentdash-qa2*.db` 뿐, 훅 POST 는 가짜 서버 DB 로만). 기존 훅 `PreToolUse` 1 · `PostToolUse` 3 · `Stop` 1 그대로 · `hook_send.sh` 항목 0. **오케스트레이터가 사람에게 바뀐 이유를 확인해 달라.**
