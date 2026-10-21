# QA2 r4 — 상태 · 실시간 · 화면 (웨이브 C, 2026-10-21, 계획 Task 15, 커밋 8c75bd1)

> 범위: G-12 재대조(spec v0.3 §4.2 글자) · G-09 · G-10 · G-11 · G-17 · G-18 · G-21 회귀. G-29 = `outputs/e2e/alerts.md`, G-30 = `outputs/e2e/design.md`, G-22 = `outputs/e2e/self-observe-r4.md`.
> **고치지 않았다** — 코드 · 테스트 · 설정 · 정본 · progress 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/{alerts,design,self-observe-r4}.md` · `outputs/e2e/qa2-r4/`(스크린샷 31, 커밋 안 됨) · `outputs/qa2/`(judge_r4.py · compare_r4.py · table_r4.py · make_fake_r4.py · *-r4* 중간 결과 · server-*.log) · `data/agentdash-qa2.db`(새 백필) · `data/agentdash-qa2-alerts.db` · `data/qa2-fake/`.
> 원천은 읽기만(`open(...,"rb")` · `ps -p` · `stat`). 훅 설치 0 · `~/.claude/settings.json` sha1 `8641eb22e8f5…` · mtime 1792131308 (시작 · 끝 같음). 본문 없음 — 키 · 시각 · 숫자 · 규칙 코드 · 도구 이름만. 실제 `config/budget.yaml` 변경 0.
> 서버: 실제 DB `rm -f data/agentdash-qa2.db*; AGENTDASH_DB=data/agentdash-qa2.db make setup backfill` (4.2 s · 원천 파일 567 · agent 319 · usage_event 25,924 · tool_call 29,352 · parse_error 0) → `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8097 uv run python -m agentdash.app` (uv 3213 / python 3215, 01:43:18Z ~ 01:54:28Z, 감시기 켬) · 알림 E2E 동안 가짜 루트 서버(6524/6526) · 재기동 (7222/7224, 01:57:44Z ~ 끝). 끝에 띄운 PID 만 kill.

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-09 판정 규칙 | PASS (회귀) | `tests/test_state.py` 58 passed — v0.3 세션 평가 순서 3 행(R-03 > R-04 · R-02b · pid 소멸 R-07) 포함 |
| G-10 연결 규칙 | PASS (회귀) | `tests/test_linker.py` 26 passed |
| G-11 실시간 | PASS (회귀) + 실제 관찰 | `tests/test_realtime.py` 4 passed · 실제 감시기/10 초 판정이 오케스트레이터 RUNNING → SLEEPING R-03 을 마지막 기록 + 301 초(01:47:02Z)에 · 훅 POST 상태 반영 30 ms (alerts.md) |
| **G-12 상태 대조** | **PASS** | 표본 30 (실행 3 · 잠듦 1 · 멈춤 6 · 실패 4 · 끝남 16) **spec v0.3 글자 기준 오판 0** (상태 + 규칙 코드). 전수 318 두 시점 오판 0 / 0 |
| G-17 화면 · API | PASS | check_routes 화면 7 + API 13 = 20/20 HTTP 200 (빈 DB) · placeholder 0 · 실제 DB 로 7 화면 열림 |
| G-18 구성도 | PASS | test_graph 포함 19 passed · 실제 DB 보기 3 첫 그림 89 / 61 / 70 ms · 전체 351 > 300 → 127 · 접힘 224 · "+N" 19 |
| G-21 브라우저 | PASS | D-01~D-07 × 밝은 · 다크 앱 콘솔 오류 0 · 390 px / 1400 px × 4 모드 56 측정 가로 스크롤 0 |

새 결함 1 건 경미(DEF-QA2-301). 치명 0 · 중대 0.

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-09 -->
G-09  판정 규칙 — 13 규칙 표 테스트 · 경계 · v0.3 순서  PASS  r4 tests/test_state.py 58 passed (v0.3 세션 평가 순서 R-03>R-04>R-02b · pid 소멸 R-07 행 포함) · 전체 pytest 372 passed
<!-- gate:G-10 -->
G-10  연결 규칙 — L-01~L-07 테스트  PASS  r4 tests/test_linker.py 26 passed · 실제 DB 표본 서브에이전트 spawn 엣지 = 부모 세션 (D-02 노드 패널)
<!-- gate:G-11 -->
G-11  실시간 — SSE 5 초 · 훅 1 초  PASS  r4 tests/test_realtime.py 4 passed · 실제 감시기 오케스트레이터 RUNNING→SLEEPING R-03 01:47:02Z (마지막 기록+301 초) · 가짜 루트 훅 POST→브라우저 알림 30 ms
<!-- gate:G-12 -->
G-12  상태 대조 — 표본 30 오판 ≤ 2 (spec v0.3 글자)  PASS  r4 표본 30 (RUNNING 3 · SLEEPING 1 · STALE 6 · FAILED 4 · DONE 16) v0.3 §4.2 글자 기준 오판 0 (상태+규칙) · 전수 318 두 시점 0/0 · 표본 시각 2026-10-21T01:47:10Z
<!-- gate:G-17 -->
G-17  화면 · API — 화면 7 · API 13  PASS  r4 check_routes 20/20 HTTP 200 (빈 DB) · placeholder 0 · 실제 DB 로 D-01~D-07 열림
<!-- gate:G-18 -->
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3  PASS  r4 tests/test_graph.py+test_dashboard.py 19 passed · 실제 DB 계층 89 ms · 협업 61 ms · 파이프라인 70 ms · 전체 351>300 → 127 접힘 224 "+N" 19 · 테마 토글 다시 그림 +1/+1
<!-- gate:G-21 -->
G-21  브라우저 — 콘솔 오류 0 · 390px · D-07 · 두 테마  PASS  r4 D-01~D-07 × (밝은 · 다크 토글 · 시스템 다크) 앱 콘솔 오류 0 · 390/1400 px × 4 모드 × 7 화면 = 56 측정 scrollWidth = clientWidth · 스크린샷 outputs/e2e/qa2-r4/

---

## 1. G-12 상태 대조 (spec v0.3 §4.2 글자)

### 1.1 방법

- 판정기 `outputs/qa2/judge_r4.py` — r3 판정기와 같은 코드(대시보드 `agentdash.*` import 0 · 원천 `rb` · `ps -p`), 출력 이름만 `v03_*` 로. r3 의 「가설(D-14 · D-18 · D-19)」 판정이 v0.3 에서 정본이 되었으므로 그것이 **v0.3 글자**다. 적용한 글자:
  - **세션 평가 순서** R-01 → R-02a → (훅 도구 실행 중이면 RUNNING) → R-03 → R-04 → R-02b → R-05 → R-06 → R-07.
  - **S1 살아 있음** = S1 파일 + pid 살아 있음(`ps -p`). **pid 소멸 = S1 없음** (R-06 / R-07).
  - **잠잠한 busy** = S1 살아 있음 · `busy` · 마지막 기록(모든 줄 종류, D-20) 300 초 넘음 · 훅 도구 실행 아님. 이것과 `idle` 이 R-03 · R-04 대상.
  - R-03 = 마지막 **tool_use** 가 `ScheduleWakeup` 이고 (호출 시각 + delaySeconds) 가 미래(D-18). R-04 = 미종료 자식(RUNNING · WAITING_*, STALE 제외) ≥ 1. R-05 = `idle` (S1 `shell` 은 D-09 대로 idle 계열).
  - 서브에이전트 R-08 ~ R-12: 반환 = 가장 늦은 종료 신호(handback · 알림 completed/failed/killed · Agent 결과 is_error) ≥ 마지막 활동(tool_use 를 낸 assistant 줄 · 들어온 메시지 줄) (D-04 · D-21). 워크플로 에이전트는 S6 status.
  - 실제 기록에 훅이 없으므로 R-01 · 훅 도구 실행은 해당 0 (훅 경로는 test_state · test_realtime · alerts.md 가짜 루트).
- 대시보드 값 = 같은 초 `agent.state · state_reason` 덤프(`outputs/qa2/db-sample-r4.txt`), 판정기 직후 다시 덤프(`db-sample-r4-after.txt`) — 상태 · 규칙 변화 0.
- 일치 = **상태와 규칙 코드 둘 다** 같을 때.
- 재현: `uv run python -I outputs/qa2/judge_r4.py outputs/qa2/sample-r4.keys outputs/qa2/judge-out-r4.json` → `uv run python -I outputs/qa2/compare_r4.py outputs/qa2/judge-out-r4.json outputs/qa2/db-sample-r4.txt` → `uv run python -I outputs/qa2/table_r4.py`.

### 1.2 표본 선정 (`outputs/qa2/sample-r4.keys`, 시각 2026-10-21T01:47:10Z)

- STALE **6 전부** (세션 R-06 1 · 서브 R-11 5)
- FAILED 4 — r1~r3 표본에 없던 `adcce697` · `a167636f` · `a3a79ff5` · `a5a75228`
- **SLEEPING 1** — 오케스트레이터 `S:fa752590` 가 잠잠한 busy 가 된 직후(01:47:02Z), 미종료 자식 2 도 있음 → **R-03 이 R-04 보다 먼저**인 v0.3 순서를 실제 기록으로 대조
- RUNNING 3 — 세션 `S:fc3908a3` R-02a · QA1 `a19dae7c` · QA2 나 `a666066d` R-09
- DONE 16 — 세션 R-07 5 (그중 지난 ScheduleWakeup 2 · 결과 있는 마지막 tool_use) · 웨이브 A/B 개발 · 아키텍트 서브 5 (S1 busy 인 세션의 반환된 자식, 하나는 알림 completed 뒤 handback) · `fc3908a3` 반환 자식 2 · 워크플로 에이전트 2 (S6 completed) · r3 의 QA 서브 2 (pid 소멸 세션)
- 지금 기록에 WAITING_PERMISSION(훅 미설치) · WAITING_CHILD · 「S1 파일 있음 + pid 소멸」 세션은 0 건 — 그 경로는 test_state(v0.3 3 행) 로만.
- 표본 시각에 `S:fc3908a3` 는 사람이 쓰는 중이라 `busy`(이전 덤프 01:43:56Z 에는 `idle` WAITING_INPUT R-05 — 전수 §1.4 에서 대조, 일치).

### 1.3 결과 — **오판 0 / 30 → PASS**

| # | 키 | 종류 | 원천 근거 (spec v0.3 §4.2 입력값) | 기대 v0.3 글자 | (참고) v0.2 글자 | 대시보드 | 일치 |
|---|---|---|---|---|---|---|---|
| 1 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (546711초 전) · 마지막 줄 assistant:tool_use · 마지막 tool_use AskUserQuestion · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z(지남) · 자식 64 (미종료 0) | STALE R-06 | STALE R-06 | STALE R-06 | O |
| 2 | `A:a2a0029196a84aba3` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T01:23:26 (1988624초 전) · 마지막 활동 09-28T01:13:14 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 3 | `A:abca160dd070f2db8` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-09T03:56:32 (1029037초 전) · 마지막 활동 10-09T03:08:06 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 4 | `A:a39a8de156b8640a4` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T16:21:27 (725143초 전) · 마지막 활동 10-12T16:21:12 · 반환 handback@10-12T16:21:02 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 5 | `A:abe5c570d21c89b2a` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:21 (721188초 전) · 마지막 활동 10-12T17:26:36 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 6 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:26 (721183초 전) · 마지막 활동 10-12T17:26:57 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 7 | `A:adcce697adc4648df` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T23:08:36 (1910314초 전) · 마지막 활동 09-28T23:08:36 · 반환 notification:failed@09-28T23:08:36 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 8 | `A:a167636f750fc2591` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:29 (1048541초 전) · 마지막 활동 10-08T22:31:28 · 반환 notification:failed@10-08T22:31:29 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 9 | `A:a3a79ff5ebee2a7fa` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:32:19 (1048490초 전) · 마지막 활동 10-08T22:32:19 · 반환 notification:failed@10-08T22:32:20 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 10 | `A:a5a75228a8eaf44fc` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:46 (1048523초 전) · 마지막 활동 10-08T22:31:45 · 반환 notification:failed@10-08T22:31:46 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 11 | `S:fa752590-2b31-4e52-8518-a10dfe99f988` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-21T01:42:01Z (308초 전) · 마지막 줄 assistant:text · 마지막 tool_use ScheduleWakeup · ScheduleWakeup 2026-10-21T02:11:22Z(미래) · 자식 7 (미종료 2) | SLEEPING R-03 | STALE R-02b | SLEEPING R-03 | O |
| 12 | `A:a19dae7c44b9897c4` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:47:09 (0초 전) · 마지막 활동 10-21T01:47:09 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 13 | `A:a666066d0ca4badc9` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:47:09 (0초 전) · 마지막 활동 10-21T01:47:09 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 14 | `S:fc3908a3-be19-4ec8-bbec-53711cb56817` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-21T01:47:08Z (2초 전) · 마지막 줄 user:tool_result · 마지막 tool_use Bash · 자식 3 (미종료 0) | RUNNING R-02a | RUNNING R-02a | RUNNING R-02a | O |
| 15 | `A:a6fb649567d2669d6` | SUBAGENT | 세션 fc3908a3 S1 busy · 마지막 기록 10-21T00:34:22 (4367초 전) · 마지막 활동 10-21T00:34:22 · 반환 handback@10-21T00:34:22 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 16 | `A:a9979459006514546` | SUBAGENT | 세션 fc3908a3 S1 busy · 마지막 기록 10-21T00:35:34 (4295초 전) · 마지막 활동 10-21T00:35:34 · 반환 handback@10-21T00:35:34 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 17 | `S:ad2fe3ca-d706-4a00-bba7-de949d9d065d` | SESSION | S1 없음 · 마지막 기록 2026-10-20T00:56:46Z (89423초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
| 18 | `S:5e628a6a-4945-4a67-8d30-9f7556e10372` | SESSION | S1 없음 · 마지막 기록 2026-10-19T04:53:11Z (161638초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
| 19 | `S:11ca1f26-f741-41b1-8811-2225b85e23a6` | SESSION | S1 없음 · 마지막 기록 2026-10-17T01:26:14Z (346855초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
| 20 | `S:8f3a6abd-0740-4164-9188-e5ac6af4cd37` | SESSION | S1 없음 · 마지막 기록 2026-10-11T15:31:32Z (814537초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · ScheduleWakeup 2026-10-09T18:57:13Z(지남) · 자식 8 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
| 21 | `S:64067a52-368e-47ae-bada-05cb87fc4a3c` | SESSION | S1 없음 · 마지막 기록 2026-10-04T05:53:10Z (1454039초 전) · 마지막 줄 assistant:text · 마지막 tool_use mcp__claude-in-chrome__tabs_context_mcp · ScheduleWakeup 2026-10-02T22:14:42Z(지남) · 자식 17 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |
| 22 | `A:ad57b6de4b4252afd` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:37:53 (557초 전) · 마지막 활동 10-21T01:37:52 · 반환 handback@10-21T01:37:52 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 23 | `A:aac8375972e3d6b26` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:31:03 (967초 전) · 마지막 활동 10-21T01:31:02 · 반환 handback@10-21T01:31:02 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 24 | `A:ad882f0fdff379a02` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:18:47 (1703초 전) · 마지막 활동 10-21T01:18:46 · 반환 handback@10-21T01:18:46 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 25 | `A:a4f084316ccac6ecc` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T01:16:02 (1868초 전) · 마지막 활동 10-21T01:16:01 · 반환 notification:completed@10-21T01:04:15, handback@10-21T01:16:01 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 26 | `A:a93da8f82902759fb` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T00:50:36 (3394초 전) · 마지막 활동 10-21T00:50:35 · 반환 handback@10-21T00:50:35 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 27 | `A:a7186b4827d0cb63f` | WORKFLOW_AGENT | 세션 8f3a6abd S1 없음 (프로세스 없음) · 마지막 기록 10-10T02:48:52 (946698초 전) · 마지막 활동 10-10T02:48:52 · 반환 없음 · S6 status=completed | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 28 | `A:a87cfd3e838743964` | WORKFLOW_AGENT | 세션 8f3a6abd S1 없음 (프로세스 없음) · 마지막 기록 10-10T02:49:18 (946671초 전) · 마지막 활동 10-10T02:49:18 · 반환 없음 · S6 status=completed | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 29 | `A:a850fbc10924baf9b` | SUBAGENT | 세션 2bee9170 S1 없음 (프로세스 없음) · 마지막 기록 10-17T09:40:30 (317200초 전) · 마지막 활동 10-17T09:40:29 · 반환 handback@10-17T09:40:29 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 30 | `A:a2384d3236592c914` | SUBAGENT | 세션 2bee9170 S1 없음 (프로세스 없음) · 마지막 기록 10-17T09:38:47 (317302초 전) · 마지막 활동 10-17T09:38:47 · 반환 handback@10-17T09:38:47 | DONE R-08 | DONE R-08 | DONE R-08 | O |

상태별: STALE 6/6 · FAILED 4/4 · SLEEPING 1/1 · RUNNING 3/3 · DONE 16/16.
**v0.2 글자 ≠ v0.3 글자**: #11 하나(v0.2 는 busy 면 R-03 을 보지 않아 STALE R-02b). r2 · r3 의 「spec 글자 오판 1」 은 v0.3 정본 개정으로 사라졌다 — 대시보드는 v0.3 글자대로.
#11 은 v0.3 평가 순서의 실측: 잠잠한 busy · 미래 Wakeup · **미종료 자식 2 (QA1 · QA2)** → R-04(WAITING_CHILD) 가 아니라 R-03(SLEEPING). 근거 문구 `R-03 S1 status=busy · ScheduleWakeup 깰 시각 2026-10-21T02:11:22Z · 마지막 기록 2026-10-21T01:42:01Z (301초 전) · D-18` (state_log).

### 1.4 전수 대조

| 시점 | 오케스트레이터 | 대상 | 오판 | 파일 |
|---|---|---|---|---|
| 01:43:56Z | RUNNING R-02a | 318 (WORKFLOW 노드 1 제외) | **0** (DONE 296 · RUNNING 3 · STALE 6 · FAILED 12 · WAITING_INPUT 1) | `judge-all-r4.json` · `db-all-r4.txt` |
| 01:47:11Z | SLEEPING R-03 | 318 | **0** (DONE 296 · RUNNING 3 · STALE 6 · FAILED 12 · SLEEPING 1) | `judge-all-r4b.json` · `db-all-r4b.txt` |

---

## 2. G-09 · G-10 · G-11 회귀

`outputs/qa2/regress-r4.txt`: `uv run pytest -q tests/test_state.py` **58 passed** · `tests/test_linker.py` **26 passed** · `tests/test_realtime.py` **4 passed** · `tests/test_graph.py tests/test_dashboard.py` **19 passed** · `tests/test_alerts.py tests/test_design.py` **18 passed** · 전체 `uv run pytest -q` **372 passed** (16.0 s).
G-11 실제: 재백필 없이 감시기 · 10 초 판정이 오케스트레이터 RUNNING R-02a (01:43:03Z) → SLEEPING R-03 (01:47:02Z = 마지막 기록 01:42:01Z + 301 초) → RUNNING R-02a (01:57:45Z, QA1 반환 알림 뒤 새 기록). QA1 RUNNING R-09 → DONE R-08 (반환 01:55:38Z, self-observe-r4). 훅 POST → 상태 반영 · 브라우저 알림 생성 30 ms (alerts.md §2).

## 3. G-17 · G-18 · G-21 브라우저 (Claude in Chrome · 새 탭 2 개만 쓰고 닫음)

- G-17: `uv run python src/agentdash/tools/check_routes.py` → `G-17  화면 · API  PASS  화면 7 + API 13 = 20 중 HTTP 200 20 (빈 DB) · placeholder 0`. 실제 DB 로 7 화면 모두 열림(design.md 스크린샷).
- G-18 (실제 DB, 노드 319): 계층 24 h 노드 27 · 첫 그림 100 ms → 계층 전체 「노드 127 (에이전트 95 / 전체 319) · 엣지 40 · 접힘 224 (접기 전 노드 351 > 300) · 첫 그림 89 ms」 · "+N" 노드 19 · 협업 24 h 27 노드 61 ms · 파이프라인 전체 127 노드 70 ms. `?project=` 첫 로드 노드 9 (이 폴더). 머리글 테마 토글마다 `__graphThemeRedraws` 0 → 1 → 2 (다시 칠함).
- G-21: D-01~D-07 을 밝은(시스템) · 다크(머리글 토글) · 다크(시스템) 로 열고 `read_console_messages onlyErrors` → **앱 오류 0** (경고 1 = cytoscape 라이브러리 wheelSensitivity 안내, 앱 오류 아님). 가로 스크롤 = 같은 출처 iframe 56 측정(390 / 1400 px × 밝은 토글 · 다크 토글 · 시스템 밝은 · 시스템 다크 × 7 화면) 전부 `scrollWidth == clientWidth` (375 / 1385), 바깥으로 삐져나온 요소 0 — 자세히 design.md §2.

## 4. 새 결함

### DEF-QA2-301 — D-02 계층 보기에서 형제 노드 이름표가 겹친다 · 경미 · 개발2
- 재현: 실제 DB `/graph?view=tree&since=24h&project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` (노드 9), 1400 px 기본 줌.
- 실측: 세션 아래 서브에이전트 7 개의 이름표(`[GP] QA1 r4 numbers & safety` · `[GP] Dev2 wa…` · `[GP] QA2 r4 state, alerts, de…` · `[GP] Architect Phase 0 …`)가 서로 겹쳐 읽기 어렵다 — `outputs/e2e/qa2-r4/g22-self-running-0145.jpg` · `g22-self-running-qa1-done-0158.jpg`. 노드 색 · 패널 · D-03 은 정상.
- 기대(제안): 형제 간격을 이름표 폭만큼 두거나 이름표를 줄바꿈 · 말줄임 · 확대 시만 표시. spec §7.3 「깔끔한 대시보드형」. 게이트 판정 영향 없음.

치명 결함 0 · 중대 결함 0 — 원천 쓰기 · 본문 저장 · 훅 손상 · 외부 전송 · 실제 budget.yaml 금액을 보지 못했다.

## 5. 정리 확인

- 띄운 프로세스만 kill: 실제 서버 3213/3215 · 가짜 서버 6524/6526 · `sleep` pid · 재기동 서버 7222/7224 → 8097 LISTEN 0 (self-observe-r4 §끝).
- `~/.claude/settings.json` sha1 `8641eb22e8f5…` · mtime 1792131308 그대로. `git status` 의 변경 = 이 리포트 묶음 · `outputs/qa2/` 뿐 (스크린샷은 .gitignore).
