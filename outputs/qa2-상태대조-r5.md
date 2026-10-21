# QA2 r5 — 상태 대조 · 브라우저 회귀 (웨이브 C 2차-T, 2026-10-21, 계획 Task 8, 커밋 33d2d0a)

> 범위: **G-12** 표본 10 재대조 (spec v0.4 §4.2 — `git diff 1c33a63 HEAD -- spec.md` 에서 §4.2 · R-01~R-12 줄 변경 0, 즉 v0.3 글자와 같다 · `src/agentdash/core/state.py` 변경 0) · **G-21** 화면 7 두 테마 콘솔 0 · 390 재확인. G-33 · G-34 · G-35 = `outputs/e2e/twin.md`, G-22 = `outputs/e2e/self-observe-r6.md`.
> **고치지 않았다.** 원천은 읽기만(판정기 `open(...,"rb")` · `ps -p`). 훅 설치 0. 본문 없음 — 키 · 시각 · 숫자 · 규칙 코드 · 도구 이름만.
> 실제 DB: `rm -f data/agentdash-qa2.db*; AGENTDASH_DB=data/agentdash-qa2.db make setup backfill` → 4.2 s · 원천 파일 579 (S1 2 · S2 73 · S3 245 · S4 245 · S5 6 · S5journal 1 · S5meta 6 · S6 1) · agent SESSION 73 · SUBAGENT 245 · WORKFLOW 1 · WORKFLOW_AGENT 6 · usage_event 26,337 · tool_call 29,809 · parse_error 0 (`outputs/qa2/backfill-r5.log`). 서버 `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8097 uv run python -m agentdash.app` (uv 22653 / python 22655, 04:16:39Z ~ 04:24:50Z, 감시기 켬) — 끝에 그 PID 만 kill. 사람 서버 8095 그대로.

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-12 상태 대조 | **PASS** | 표본 10 (RUNNING 3 · WAITING_INPUT 1 · STALE 2 · FAILED 1 · DONE 3) spec §4.2 글자 기준 **오판 0** (상태 + 규칙 코드) · 판정 전후 DB 덤프 같음 |
| G-21 브라우저 | **PASS** | D-01~D-07 × 밝은 · 다크 · 시스템 앱 콘솔 오류 0 · 390/1400 px × 3 모드 × 7 화면 = 42 측정 가로 스크롤 0 |

새 결함 이 파일 0 (트윈 화면 경미 4 는 `outputs/e2e/twin.md` DEF-QA2-401~404). 치명 0 · 중대 0.

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-12 -->
G-12  상태 대조 — 표본 10 재대조 (spec v0.4 §4.2 글자)  PASS  r5 표본 10 (RUNNING 3 · WAITING_INPUT 1 · STALE 2 · FAILED 1 · DONE 3) §4.2 글자 기준 오판 0 (상태+규칙) · 판정 전후 덤프 상태·규칙 변화 0 · 표본 시각 2026-10-21T04:17:09Z · 새 백필 data/agentdash-qa2.db · outputs/qa2/g12-table-r5.md
<!-- gate:G-21 -->
G-21  브라우저 — 화면 7 콘솔 오류 0 · 390px · 두 테마  PASS  r5 D-01 공장 평면도 포함 7 화면 × (밝은 · 다크 토글 · 시스템) 앱 콘솔 오류 0 (확장 content script 경고 2 제외) · 390/1400 px × 3 모드 × 7 화면 = 42 측정 scrollWidth=clientWidth · 스크린샷 outputs/e2e/qa2-r5/

---

## 1. G-12 상태 대조

### 1.1 방법

- 판정기 = r4 와 같은 `outputs/qa2/judge_r4.py` (대시보드 `agentdash.*` import 0 · 원천 `rb` · `ps -p`; `v03_*` = 지금 정본 글자 — v0.4 에서 §4.2 가 바뀌지 않았으므로 그대로). 세션 평가 순서 R-01 → R-02a → (훅 도구 실행) → R-03 → R-04 → R-02b → R-05 → R-06 → R-07 · 잠잠한 busy · pid 소멸 = S1 없음 · 마지막 tool_use 기준 ScheduleWakeup · 서브 R-08~R-12 (반환 = 가장 늦은 종료 신호 ≥ 마지막 활동).
- 대시보드 값 = 같은 초 `agent.state · state_reason` 덤프 `outputs/qa2/db-sample-r5.txt`, 판정기 직후 다시 `db-sample-r5-after.txt` — 상태 · 규칙 변화 0 (`diff` 같음).
- 일치 = 상태와 규칙 코드 **둘 다** 같을 때. 실제 기록에 훅이 없으므로 R-01 · 훅 도구 실행은 해당 0.
- 재현: `uv run python -I outputs/qa2/judge_r4.py outputs/qa2/sample-r5.keys outputs/qa2/judge-out-r5.json` → `uv run python -I outputs/qa2/compare_r4.py outputs/qa2/judge-out-r5.json outputs/qa2/db-sample-r5.txt` (`now 2026-10-21T04:17:09Z n 10 mismatch 0`) → `uv run python -I outputs/qa2/table_r5.py`.

### 1.2 표본 (`outputs/qa2/sample-r5.keys`)

- 이번 회전에 살아 있던 것 전부: 오케스트레이터 `S:fa752590` (RUNNING R-02a — 미래 ScheduleWakeup · 미종료 자식 2 가 있어도 busy · 82 초라 R-02a 가 먼저) · QA2 나 `A:a328106f` · QA1 `A:a4a00bef` (R-09) · 사람 세션 `S:fc3908a3` (idle → R-05).
- STALE 2 (세션 R-06 1 · 서브 R-11 1) · r4 표본에 없던 FAILED `A:a24b6a44` · 웨이브 B 개발 서브 DONE 2 (`a770b699` 반환 4 분 전 · `a0167300` 알림 completed 뒤 handback) · r1~r4 에 없던 세션 DONE R-07 `S:493d1a8d`.

### 1.3 결과 — **오판 0 / 10 → PASS**

(표 머리의 「v0.3 글자」 = §4.2 지금 글자. v0.4 에서 바뀐 줄 0.)

| # | 키 | 종류 | 원천 근거 (spec v0.3 §4.2 입력값) | 기대 v0.3 글자 | (참고) v0.2 글자 | 대시보드 | 일치 |
|---|---|---|---|---|---|---|---|
| 1 | `S:fa752590-2b31-4e52-8518-a10dfe99f988` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-21T04:15:47Z (82초 전) · 마지막 줄 assistant:text · 마지막 tool_use ScheduleWakeup · ScheduleWakeup 2026-10-21T04:45:34Z(미래) · 자식 13 (미종료 2) | RUNNING R-02a | RUNNING R-02a | RUNNING R-02a | O |
| 2 | `A:a328106ffaca540ab` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:17:09 (0초 전) · 마지막 활동 10-21T04:17:09 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 3 | `A:a4a00befc95de6a68` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:16:31 (38초 전) · 마지막 활동 10-21T04:16:25 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O |
| 4 | `S:fc3908a3-be19-4ec8-bbec-53711cb56817` | SESSION | S1 status=idle · pid 살아 있음 · 마지막 기록 2026-10-21T03:14:48Z (3741초 전) · 마지막 줄 user:message · 마지막 tool_use Bash · 자식 3 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O |
| 5 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (555710초 전) · 마지막 줄 assistant:tool_use · 마지막 tool_use AskUserQuestion · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z(지남) · 자식 64 (미종료 0) | STALE R-06 | STALE R-06 | STALE R-06 | O |
| 6 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:26 (730183초 전) · 마지막 활동 10-12T17:26:57 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O |
| 7 | `A:a24b6a447d6e7fb9e` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:30 (1057539초 전) · 마지막 활동 10-08T22:31:29 · 반환 notification:failed@10-08T22:31:30 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O |
| 8 | `A:a770b69985c666cbf` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T04:13:30 (219초 전) · 마지막 활동 10-21T04:13:29 · 반환 handback@10-21T04:13:29 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 9 | `A:a0167300959299bf6` | SUBAGENT | 세션 fa752590 S1 busy · 마지막 기록 10-21T03:51:13 (1556초 전) · 마지막 활동 10-21T03:51:12 · 반환 notification:completed@10-21T03:43:27, handback@10-21T03:51:12 | DONE R-08 | DONE R-08 | DONE R-08 | O |
| 10 | `S:493d1a8d-6430-4776-95f1-f6b085637edd` | SESSION | S1 없음 · 마지막 기록 2026-10-17T16:37:41Z (301168초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O |

상태별: RUNNING 3/3 · WAITING_INPUT 1/1 · STALE 2/2 · FAILED 1/1 · DONE 3/3.
참고: 표본 뒤 04:20:55 오케스트레이터가 잠잠한 busy + 미래 Wakeup + 미종료 자식 2 로 **SLEEPING R-03** 이 되고(근거 문구 「R-03 S1 status=busy · ScheduleWakeup 깰 시각 2026-10-21T04:45:34Z · 마지막 기록 04:15:47Z (308초 전) · D-18」, 피드에서 봄) 04:23:36 새 기록으로 RUNNING R-02a 로 돌아왔다 — r4 #11 과 같은 v0.3 순서 실측. QA1 은 04:23:35Z 반환 → DONE R-08 (피드 · 평면도 흐림).

## 2. G-21 브라우저 (Claude in Chrome 새 탭 1 개, 끝에 닫음)

- 가로 스크롤: 같은 출처 iframe 390 / 1400 px 에서 화면 7 × 밝은(`data-theme=light`) · 다크(`dark`) · 시스템(속성 없음) = **42/42** `scrollWidth == clientWidth` (390 → 375/375, 1400 → 1385/1385), 넘친 요소 0. 표 전체 · 배경색은 `outputs/e2e/twin.md` §3.1. 시스템 모드는 측정 동안 OS 가 다크 → 밝은으로 바뀌어 두 경우 모두 들어감.
- 콘솔: localStorage `agentdash-theme` = light 로 7 화면 차례로 연 뒤 `read_console_messages(onlyErrors)` 0 · dark 로 7 화면 0 · 시스템(값 지움) D-01 0. 경고 2 (MaxListenersExceeded) 는 `chrome-extension://…/contentscript.js` 출처 — 앱 아님.
- D-03 는 내 키 `A:a328106ffaca540ab` 로, Enter 경로(D-01 → D-03)로도 열림.
- 스크린샷 (`outputs/e2e/qa2-r5/`, 커밋 안 함): real-dark-1400-first · real-dark-1400-floor · real-light-1400-sleeping · real-light-keyboard-focus · real-enter-d03 · real-light-panel-kpi-top5 · real-light-feed-qa1-done · real-dark-390-iframe · fake-light-spawn-3machines · fake-light-waiting-permission-beacon · fake-light-handback-done · fake-light-budget-band-over.

## 3. 회귀 테스트

`uv run pytest -q tests/test_dashboard.py` 12 passed · `tests/test_dashboard.py tests/test_twin_page.py tests/test_realtime.py tests/test_state.py` 85 passed · 전체 `uv run pytest -q` **419 passed** (16.3 s).

## 4. 안전

원천 쓰기 0 · 훅 설치 0 · 실제 budget.yaml 변경 0. `~/.claude/settings.json` 은 내 작업 중 04:27:06Z 에 바뀌었다(sha1 `8641eb22…` → `8a539108…`) — QA2 가 연 적 없는 파일, 같은 분에 `history.jsonl` · `backups/` 도 바뀌어 Claude Code 자신의 설정 저장으로 보임, 기존 훅 그대로 · `hook_send.sh` 0. 자세한 것은 `outputs/e2e/twin.md` §5.
