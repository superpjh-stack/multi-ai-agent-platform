# QA2 재검증 (r2) — 상태 · 실시간 · 화면 (웨이브 C2, 2026-10-17, 커밋 8606bc8)

> 범위 G-09~G-12 · G-17 · G-18 · G-21 · G-22 + DEF-QA2-001~008 재현. **고치지 않았다** — 코드 · 설정 · 테스트 · 정본 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/`(self-observe-r2.md · r2-*.jpg · observe-transitions-r2.log) · `outputs/qa2/`(judge_r2.py · table_r2.py · observe_r2.py · *-r2.* 중간 결과 · server-r2.log) · `data/agentdash-qa2.db`.
> 원천은 읽기만(`open(...,"rb")` · `ps -p` · `ls`). 훅 설치 0 · `~/.claude/settings.json` 읽지도 않음. 본문 없음 — 키 · 시각 · 숫자 · 규칙 코드만.
> 서버: `data/agentdash-qa2.db` 삭제 후 `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (uv PID 35076 · python PID 35084, 09:01:56Z 기동 → 09:02:00Z 백필 · 첫 판정 → 감시기 + 10 초 판정). 끝날 때 이 PID 와 내 폴러만 정지.
> **gate 가 읽는 파일**: `src/agentdash/tools/gate.py` 53 · 62 · 66 · 67 줄은 `outputs/qa2-상태대조.md` · `outputs/e2e/self-observe.md` 만 읽는다 — 이 r2 파일은 지시대로 새 파일에 썼으므로 **지금 `make gate` 는 r2 판정을 읽지 않는다** (gate 수정은 내 일 아님 · 오케스트레이터 판단).

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-09 판정 규칙 | PASS (회귀) | `tests/test_state.py` 55 passed (이전 39) — D-18 5 행 · D-19 4 행 · 90/300 초 정각 · DB 경로 FAILED · STALE 자식 · 예약 "마지막" 조건 추가 |
| G-10 연결 규칙 | PASS (회귀) | `tests/test_linker.py` 25 passed (이전 17) — task-id 재기상 · 옛 알림 덮기 방지 · 반환 뒤 들어온 메시지 · `S:` 접두 to |
| G-11 실시간 | PASS (회귀) + 실제 관찰 | `tests/test_realtime.py` 4 passed · 실제 감시기/10 초 판정이 RUNNING→SLEEPING 을 기록 뒤 302 초에 바꿈(09:06:05Z) |
| **G-12 상태 대조** | **PASS** | 표본 30: **가설 기준 오판 0** · spec 글자 기준 오판 1 (오케스트레이터 SLEEPING vs 글자 STALE, D-18) — 둘 다 ≤ 2. 전수 328: 가설 0 · 글자 1 (같은 건) |
| G-17 화면 · API | PASS | check_routes 16/16 HTTP 200 · placeholder 0 · 실제 DB 로 화면 6 + D-03 + 원본 보기 열림 |
| G-18 구성도 | PASS | 보기 3 첫 그림 47/132/34 ms · 전체 365→137 접힘 228 · "+N" 19 · 필터 state=FAILED 에이전트 14 · 노드 클릭 패널(잠듦 R-03 · 깰 시각) · 더블클릭 → D-03 |
| G-21 브라우저 | PASS | 앱 콘솔 오류 0 (D-01~D-06 · D-03 · 원본 보기 · 필터) · 390px iframe 8 화면 scrollWidth = clientWidth |
| G-22 자기 관찰 | PASS (`outputs/e2e/self-observe-r2.md`) | 서버 기동 09:01:56Z → QA1 · QA2 RUNNING R-09 09:02:00Z · 오케스트레이터 SLEEPING R-03 (깰 시각 09:30:46Z) 09:06:05Z · QA1 handback 09:12:08.811Z → DONE 09:12:09Z · 기동 뒤 새 에이전트 A:a5b119ea meta 09:12:40.397Z → RUNNING 09:12:40Z |

치명 0 · 중대 0 (새 결함 포함). 새 결함 3 건 모두 경미 (DEF-QA2-101 gate 파일명 · 102 D-18 가설 표시 · 103 D-02 `?project=` 첫 로드).

## 게이트 판정 행 (gate.py 표지 형식 — 단 gate.py 는 지금 이 파일을 읽지 않는다)

<!-- gate:G-12 -->
G-12  상태 대조 — 표본 30 오판 ≤ 2  PASS  r2 표본 30 (STALE 8 전부 · FAILED 4 · 재기상 2 · SLEEPING 오케스트레이터 1 · RUNNING 2 · WAITING_INPUT 2 · DONE 11) 가설(D-14·18·19) 기준 오판 0 · spec 글자 기준 오판 1 (S:2bee9170 SLEEPING vs STALE R-02b, D-18) · 전수 328 가설 0 / 글자 1 · DEF-QA2-001~003 해결

<!-- gate:G-18 -->
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3  PASS  실제 DB 보기 3 첫 그림 47/132/34 ms · 전체 365→137 접힘 228 "+N" 19 · 필터 state=FAILED · 노드 클릭 패널(잠듦 R-03 깰 시각) · 더블클릭 D-03 · 앱 콘솔 오류 0

<!-- gate:G-21 -->
G-21  브라우저 — 콘솔 오류 0 · 390px  PASS  D-01~D-06 + D-03 + 원본 보기 + 필터 앱 콘솔 오류 0 · 390px iframe 8 화면 가로 스크롤 0 · D-03 「기록상 과소 (D-17)」 2 칸 · D-01 누적 실패 12 표시

---

## 1. 이전 결함 해결표 (DEF-QA2-001~008)

| 결함 | 이전 | 재현 (r2) | 실측 | 결과 |
|---|---|---|---|---|
| DEF-QA2-001 failed/killed 알림 → DONE | 중대 | 새 DB `SELECT state,COUNT(*) … GROUP BY` · `A:a3a79ff5ebee2a7fa` · `A:a5a75228a8eaf44fc` | SUBAGENT **FAILED R-08 12** (judge 기대 12) · 두 키 FAILED R-08 근거 "반환 … 결과 is_error" · D-01 "누적 끝남 303 · 실패 12" · D-03 "실패 R-08" | **해결** |
| DEF-QA2-002 재기상 뒤 알림 못 이음 | 중대 | `A:adc075af0bd2072a0` | DONE R-08 · ended_at 09-28T00:17:39.927Z · handback 엣지 label notification:completed @00:17:39 (가장 늦은 알림) | **해결** |
| DEF-QA2-003 DB 경로 마지막 활동이 들어온 메시지 무시 | 중대 | `A:a3b3e327f20477922` | STALE R-11 (마지막 기록 09-18T20:23:12Z = 들어온 메시지) · judge 기대 STALE | **해결** |
| DEF-QA2-004 busy + 예약 미래 → STALE | 경미 | 실제 오케스트레이터 `S:2bee9170…` | 기록 뒤 302 초(09:06:05Z) **SLEEPING R-03** 근거 "S1 status=busy · ScheduleWakeup 깰 시각 2026-10-17T09:30:46Z · D-18" · D-01 잠듦 카드 1 · D-02 패널 · D-03 판정 칸에 깰 시각 | **해결 (D-18 가설 — 사람 확인 대기)** |
| DEF-QA2-005 S1 있음 · pid 소멸 | 경미 | `test_rule_table[D-19 …]` 4 행 | busy · pid 소멸 60 초 / 600 초 → R-07, idle · 예약 미래 → R-07, Stop 훅 무시 R-07 · decisions D-19 기록 | **해결 (D-19 가설 — 실제 해당 0 건)** |
| DEF-QA2-006 G-09 빈 경계 | 경미 | `pytest --collect-only tests/test_state.py` | 90 초 정각 R-12 · 300 초 정각 R-11/R-02b · `test_db_failed_notification_is_FAILED` · `test_db_stale_children_do_not_hold_parent` · `test_db_wakeup_must_be_last_assistant` · D-18 · D-19 행 | **해결** |
| DEF-QA2-007 G-10 빈 경계 + `S:` 비교 | 경미 | `resolve_message('A:x','S:2bee9170…', keys={…})` 직접 호출 | dst = `S:2bee9170…` external=False (이전 외부 노드) · 테스트 `test_L06_session_prefixed_target` · `test_L07_rewake_notification_matched_by_task_id` · `test_L07_incoming_message_after_handback_wakes_child` | **해결** |
| DEF-QA2-008 gate.py 가 모든 판정 꼴 줄 읽음 | 경미 | `gate.qa_rows(text,'G-12')` 에 옛 `G-12 … FAIL` 줄 + 표지 + `PASS` 줄 | `[('PASS','새줄')]` — 표지 없는 줄 무시 · 표지 없으면 빈 목록(→ 미검증) | **해결** (단 파일명 고정 → DEF-QA2-101) |

---

## 2. G-12 상태 대조

### 2.1 방법

- 표본 시각 **2026-10-17T09:06:09Z** (오케스트레이터가 09:06:05Z 에 SLEEPING 이 된 직후). 대시보드 값은 같은 초에 `agent.state · state_reason` 을 뜬 `outputs/qa2/db-sample-r2.txt`.
- 기대값: **내 판정기** `outputs/qa2/judge_r2.py` (이전 `judge.py` 에 두 판정 칸을 더함 · 대시보드 코드 import 0 · 원천 `rb`):
  - **spec 글자**: spec §4.2 그대로. S1 이 있으면 status 로 판정(R-02a 만 pid 생존 요구), busy · 5 분 넘게 무기록 = STALE R-02b, busy · pid 소멸 · 5 분 안 = "규칙 없음", idle R-03 = 마지막 assistant 줄의 ScheduleWakeup.
  - **가설 (결정 대장 현재 상태)**: D-14(busy · 5 분 · 미종료 자식 → WAITING_CHILD R-04) · D-18(busy · 5 분 · 가장 늦은 tool_use 가 ScheduleWakeup 이고 깰 시각 미래 → SLEEPING R-03) · D-19(pid 소멸 = S1 없음 → R-06/R-07). 반환(L-07)은 둘 다 D-04 대안 규칙 + failed/killed/is_error → FAILED.
  - 서브에이전트는 두 기준이 같다(D-14/18/19 는 세션 규칙).
- 선정 (`outputs/qa2/sample-r2.txt`): STALE **8 전부**(세션 R-06 1 · 서브 R-11 7) · FAILED 4 (무작위, 이전 표본 2 건 제외) · 다시 깨운 자식 2 (`adc075af` = DEF-002 · `aec64966` = 이 프로젝트, message 엣지 뒤 handback) · SLEEPING 1 (이 오케스트레이터) · RUNNING 2 (QA1 · QA2 자신) · WAITING_INPUT 2 (S1 shell · idle) · DONE 11 (알림 completed 깊이 1 ×2 · 깊이 2 ×1 · handback 깊이 1 ×2 · 깊이 2 ×1 · 워크플로 에이전트 1 · 세션 R-07 3 · 지난 예약이 있는 세션 1). 깊이 2 표본 5 (`a39a8de1` · `a5c396b2` · `abe5c570` · `acfbcbea` · `adf7af46`).
- 지금 기록에 WAITING_PERMISSION(훅 미설치) · WAITING_CHILD(오케스트레이터가 D-18 로 SLEEPING 이 먼저) 는 0 건.
- 재현: `uv run python -I outputs/qa2/judge_r2.py outputs/qa2/sample-r2.txt outputs/qa2/judge-out-r2.json` → `uv run python -I outputs/qa2/table_r2.py`.

### 2.2 결과 — 가설 기준 오판 **0** · spec 글자 기준 오판 **1** → **PASS** (둘 다 ≤ 2)

| # | 키 | 종류 | 원천 근거 | spec 글자 | 가설 (D-14·18·19) | 대시보드 | 일치 (글자 / 가설) |
|---|---|---|---|---|---|---|---|
| 1 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (227450초 전) · 마지막 줄 assistant:tool_use · 마지막 tool_use AskUserQuestion · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z(지남) · 자식 64 (미종료 0) | STALE R-06 | STALE R-06 | STALE R-06 | O / O |
| 2 | `A:a2a0029196a84aba3` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T01:23:26 (1669363초 전) · 마지막 활동 09-28T01:13:14 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 3 | `A:a39a8de156b8640a4` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T16:21:27 (405882초 전) · 마지막 활동 10-12T16:21:12 · 반환 handback@10-12T16:21:02 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 4 | `A:a3b3e327f20477922` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T20:23:12 (2464977초 전) · 마지막 활동 09-18T20:23:12 · 반환 notification:failed@09-18T18:34:34, handback@09-18T20:07:22 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 5 | `A:abca160dd070f2db8` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-09T03:56:32 (709776초 전) · 마지막 활동 10-09T03:08:06 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 6 | `A:abe5c570d21c89b2a` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:21 (401927초 전) · 마지막 활동 10-12T17:26:36 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 7 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:26 (401922초 전) · 마지막 활동 10-12T17:26:57 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 8 | `A:adb2bacd2ac16c31f` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T21:07:41 (2462308초 전) · 마지막 활동 09-18T21:07:41 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 9 | `A:a24b6a447d6e7fb9e` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:30 (729279초 전) · 마지막 활동 10-08T22:31:29 · 반환 notification:failed@10-08T22:31:30 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 10 | `A:a88b1630cfd5e75f1` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:21 (729287초 전) · 마지막 활동 10-08T22:31:20 · 반환 notification:failed@10-08T22:31:21 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 11 | `A:a167636f750fc2591` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:29 (729280초 전) · 마지막 활동 10-08T22:31:28 · 반환 notification:failed@10-08T22:31:29 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 12 | `A:adcce697adc4648df` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T23:08:36 (1591053초 전) · 마지막 활동 09-28T23:08:36 · 반환 notification:failed@09-28T23:08:36 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 13 | `A:adc075af0bd2072a0` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:17:37 (1673311초 전) · 마지막 활동 09-28T00:17:02 · 반환 notification:completed@09-27T16:18:14, notification:completed@09-27T16:44:18, notification:completed@09-27T17:57:31, notification:completed@09-28T00:17:39 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 14 | `A:aec649669ff2dc3df` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T08:00:46 (3923초 전) · 마지막 활동 10-17T08:00:45 · 반환 handback@10-17T08:00:45 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 15 | `S:2bee9170-9e95-4e4e-873d-8490f228ad20` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-17T09:01:03Z (306초 전) · 마지막 줄 assistant:text · 마지막 tool_use ScheduleWakeup · ScheduleWakeup 2026-10-17T09:30:46Z(미래) · 자식 13 (미종료 2) | STALE R-02b | SLEEPING R-03 (D-18) | SLEEPING R-03 | **X** / O |
| 16 | `A:aa6e2ae766643ef2c` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:06:10 (0초 전) · 마지막 활동 10-17T09:06:10 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O / O |
| 17 | `A:a6b4391e741b5db27` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:06:08 (0초 전) · 마지막 활동 10-17T09:06:08 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O / O |
| 18 | `S:493d1a8d-6430-4776-95f1-f6b085637edd` | SESSION | S1 status=shell · pid 살아 있음 · 마지막 기록 2026-10-17T07:05:55Z (7214초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O / O |
| 19 | `S:47aedf14-c5b7-4450-a193-6612b438b1f2` | SESSION | S1 status=idle · pid 살아 있음 · 마지막 기록 2026-10-17T08:52:37Z (811초 전) · 마지막 줄 user:message · 마지막 tool_use Bash · 자식 0 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O / O |
| 20 | `A:a0d040412061df433` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T16:30:12 (405357초 전) · 마지막 활동 10-12T16:30:11 · 반환 handback@10-12T16:30:11, notification:completed@10-12T16:30:13 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 21 | `A:a1c5db9b4e891278e` | SUBAGENT | 세션 dc8d7e0d S1 없음 (프로세스 없음) · 마지막 기록 09-25T18:19:54 (1867574초 전) · 마지막 활동 09-25T18:19:25 · 반환 notification:completed@09-25T18:19:56 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 22 | `A:adf7af46360396c37` | SUBAGENT | 세션 8f3a6abd S1 없음 (프로세스 없음) · 마지막 기록 10-09T18:36:15 (656993초 전) · 마지막 활동 10-09T18:35:58 · 반환 handback@10-09T18:35:58, notification:completed@10-09T18:36:17 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 23 | `A:a3c58600d2e9acc02` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T18:50:54 (2470515초 전) · 마지막 활동 09-18T18:50:50 · 반환 handback@09-18T18:50:50 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 24 | `A:a38273d11e7939c22` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-09T05:54:28 (702701초 전) · 마지막 활동 10-09T01:19:01 · 반환 handback@10-09T01:19:01 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 25 | `A:a5c396b22cb2e451d` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T12:48:48 (418640초 전) · 마지막 활동 10-12T12:48:40 · 반환 handback@10-12T12:48:40 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 26 | `A:a87cfd3e838743964` | WORKFLOW_AGENT | 세션 8f3a6abd S1 없음 (프로세스 없음) · 마지막 기록 10-10T02:49:18 (627410초 전) · 마지막 활동 10-10T02:49:18 · 반환 없음 · S6 status=completed | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 27 | `S:eaf9da7c-2e6d-4cd3-b157-cd0aa4182ab9` | SESSION | S1 없음 · 마지막 기록 2026-10-02T00:23:23Z (1327366초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O / O |
| 28 | `S:803c719b-613b-4562-a73c-ad9831ddd750` | SESSION | S1 없음 · 마지막 기록 2026-09-21T00:02:43Z (2279006초 전) · 마지막 줄 user:message · 마지막 tool_use Artifact · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O / O |
| 29 | `S:f6123745-046f-45d1-b5ee-988a56c97c7d` | SESSION | S1 없음 · 마지막 기록 2026-10-04T06:22:23Z (1133026초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O / O |
| 30 | `S:48969e43-c379-4e13-9121-4effbb9bc79d` | SESSION | S1 없음 · 마지막 기록 2026-09-30T04:29:09Z (1485419초 전) · 마지막 줄 assistant:text · 마지막 tool_use mcp__claude-in-chrome__tabs_close_mcp · ScheduleWakeup 2026-09-30T04:25:55Z(지남) · 자식 0 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O / O |

상태별 (가설 기준): STALE 8/8 · FAILED 4/4 · 재기상 2/2 · SLEEPING 1/1 · RUNNING 2/2 · WAITING_INPUT 2/2 · DONE 11/11.
**차이 나는 건 (spec 글자 ≠ 가설)**: #15 `S:2bee9170…` 하나 — spec 글자 STALE R-02b (D-14 대안이면 WAITING_CHILD R-04, 미종료 자식 2) vs D-18 SLEEPING R-03. 대시보드는 SLEEPING. 사람이 spec R-03 을 busy 까지 넓히면(D-18 확정) 오판 0, 아니면 1 — 어느 쪽이든 ≤ 2.
이전 표본 오판 3 건 중 표본 #18 · #19 (`a3a79ff5` · `a5a75228`) 은 이번 표본 밖이지만 §1 재현에서 FAILED, #4 (`adc075af`) 는 이번 #13 에서 DONE 일치.

### 2.3 전수 대조 (표본 밖, 참고)

09:06:30Z 에 DB 에이전트 328 (WORKFLOW 노드 1 제외) 전부 — **가설 기준 불일치 0 · spec 글자 기준 1** (`S:2bee9170…` SLEEPING vs STALE R-02b, 위와 같은 건). 이전(웨이브 C) 14 → 0.
재현: `sqlite3 data/agentdash-qa2.db "SELECT agent_key FROM agent WHERE kind!='WORKFLOW'" > outputs/qa2/all-r2.txt` → `uv run python -I outputs/qa2/judge_r2.py outputs/qa2/all-r2.txt outputs/qa2/judge-all-r2.json` → `db-all-r2.txt` 와 비교.

---

## 3. G-09 · G-10 · G-11 회귀

`uv run pytest -q tests/test_state.py tests/test_linker.py tests/test_realtime.py tests/test_graph.py tests/test_dashboard.py` → **99 passed** (8.1 s). 따로: test_state 55 · test_linker 25 · test_realtime 4. 전체 `uv run pytest -q` **266 passed** (12.9 s).
G-11 실제: 감시기 · 10 초 판정이 서버 기동 뒤 오케스트레이터 RUNNING→SLEEPING (09:06:05Z = 마지막 기록 09:01:03Z + 302 초) · QA2 RUNNING R-09→R-12→R-09 (긴 대기 동안 90 초 넘김, 기록 오자 2 초 안 회복) — 재백필 아님.

---

## 4. G-17 · G-18 · G-21 브라우저 (Claude in Chrome · 새 탭 하나만 · 끝나고 그 탭만 닫음)

| 화면 | 확인 | 앱 콘솔 오류 | 스크린샷 |
|---|---|---|---|
| D-01 `/` | 카드: 실행 2 · 입력 대기 2 · 권한 0 · **잠듦 1** · 자식 대기 0 · 멈춤 의심 8 · 오늘 끝남 12 (실패 0) · 머리 줄 "에이전트 328 (살아 있음 13 · 누적 끝남 303 · **실패 12**)" · 피드 "잠듦 multi-agent-dashboard-ce R-03 … 깰 시각 …" · "실시간: 연결됨" | 0 | `e2e/r2-d01-sleeping.jpg` |
| D-02 계층 24 h | 노드 38 (에이전트 30/329) · 첫 그림 47 ms · 오케스트레이터 파란(잠듦) · QA1 · QA2 초록 | 0 | `e2e/r2-d02-tree-24h-sleeping.jpg` |
| D-02 노드 클릭 | 패널: 잠듦 R-03 · 근거에 깰 시각 09:30:46Z · 직계 13 · 출력 토큰 · [추정] 비용 | 0 | `e2e/r2-d02-node-panel-sleeping.jpg` |
| D-02 더블클릭 → D-03 | `/agents/S%3A2bee9170…` · 판정(저장) R-03 · 판정(지금) 잠듦 R-03 · 상태 이력 09:02:00 실행 → 09:06:05 잠듦 · 직계 자식 13 | 0 | `e2e/r2-d03-orchestrator.jpg` |
| D-03 작업량 D-17 | 출력 토큰 · 추정 비용 "자손 포함" 칸 옆 **「기록상 과소 (D-17)」 2 곳** (title: 서브 · 워크플로 몫 출력 316,452) · 숫자 그대로 | 0 | `e2e/r2-d03-d17-note.jpg` |
| D-03 원본 보기 | 버튼 → `<details>` 200 · 펼친 것 0 | 0 | `e2e/r2-d03-raw-view.jpg` |
| D-03 실패 에이전트 `A:a24b6a44…` | "실패 R-08 반환 … 결과 is_error" | 0 | — |
| D-02 협업 · 파이프라인 | 첫 그림 132 · 34 ms | 0 | — |
| D-02 전체 기간 | 접기 전 365 > 300 → 노드 137 · 접힘 228 · "+N" 19 (예 "multi-agent-dashboard-ce · SLEEPING +11") · 첫 그림 166 ms | 0 | `e2e/r2-d02-tree-all-folded.jpg` |
| D-02 필터 state=FAILED | 노드 16 (에이전트 14 = FAILED 12 + 맥락 부모) · 첫 그림 33 ms | 0 | — |
| D-04 · D-05 · D-06 | 열림 | 0 · 0 · 0 | — |

콘솔: `read_console_messages`(onlyErrors · 확장 URL 제외 패턴)로 화면마다 읽고 비움. 이번에는 확장 경고도 잡히지 않았다.

**390px** (이전과 같은 iframe 방식 — 같은 출처 iframe `width:390px`, `innerWidth` 390 확인):

| 화면 | clientWidth | scrollWidth | 가로 스크롤 |
|---|---|---|---|
| `/` · `/graph` 계층 · 협업 · 파이프라인 · `/agents/S:2bee9170…` · `/usage` · `/pipeline` | 375 | 375 | 0 |
| `/timeline` | 390 | 390 | 0 |

(375 = 390 − 세로 스크롤바 15.)

---

## 5. 새 결함

### DEF-QA2-101 — gate.py 의 QA 리포트 경로가 파일명 고정 · 경미 · 아키텍트
- `src/agentdash/tools/gate.py` 53 · 62 · 66 줄 `("qa", "outputs/qa2-상태대조.md")`, 67 줄 `("qa", "outputs/e2e/self-observe.md")`. 재검증 리포트(`-r2`)를 새 파일로 쓰면 `make gate` 는 웨이브 C 의 옛 판정(G-12 FAIL)을 계속 읽는다 — 지금 `make gate` 의 G-12 는 이 r2 의 PASS 를 반영하지 않는다.
- 기대: 최신 리포트를 고르는 규칙(예: `qa2-상태대조*.md` 중 최신) 또는 재검증도 같은 파일에 쓰기로 정함. 어느 쪽이든 아키텍트 · 오케스트레이터 결정.

### DEF-QA2-102 — D-18 은 가설인데 대시보드 SLEEPING 판정에 가설 표시가 없음 · 경미 · 개발2 · 사람(spec)
- 실측: D-01 카드 · D-02 패널 · D-03 판정에 "R-03 … · D-18" 근거 문구는 있으나 화면 상태 배지 · 카드는 "잠듦 R-03" 으로 spec 규칙처럼 보인다. spec 글자로는 같은 세션이 STALE R-02b(멈춤 의심)다.
- 기대(제안): D-17 처럼 가설 규칙으로 바뀐 판정에는 배지 옆 "(D-18 가설)" 같은 표시 — 또는 사람이 D-18 을 확정하면 닫음. G-12 판정에는 영향 없음(가설 기준 0 · 글자 기준 1 둘 다 ≤ 2).

### DEF-QA2-103 — D-02 주소의 `?project=` 가 첫 로드에서 무시됨 (드롭다운은 그 프로젝트를 보여 줌) · 경미 · 개발2
- 재현: 브라우저로 `/graph?view=tree&since=24h&project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` 를 연다 → 드롭다운은 "Multi-agent Dashboard" 인데 그림은 노드 38 (필터 없는 24 h 와 같음) · 주소가 `?view=tree&since=24h` 로 바뀜. 같은 질의를 API 로 부르면 노드 15.
- 원인 (읽기만): `templates/graph.html` 60~62 줄이 `form.elements.project.value = q.get("project")` 를 하는 시점에 select 에 "전체" 옵션뿐이라 값이 "" 로 남고, `qs()` 가 project 를 빼서 첫 fetch 가 전체를 가져온다. 옵션은 fetch 뒤 178~181 줄에서 채워지며 그때 select 만 그 값으로 바뀐다 → 화면과 필터 표시가 어긋남. 드롭다운을 다시 고르면 정상.
- 영향: 프로젝트로 거른 D-02 링크 공유 · 새로 고침. G-18 필터 기준(상태 필터 · 보기 3)은 PASS 그대로.

치명 결함 0 · 중대 결함 0 — 원천 쓰기 · 본문 저장 · 훅 손상 · 외부 전송을 보지 못했다.

## 6. 메모

- 서버를 8095 에 띄운 동안 동시에 도는 QA1 의 `check_hooks` "서버 꺼짐 송신" 검사가 이전 회차처럼 미검증이 될 수 있다(웨이브 C 메모와 같음 — 결함 아님).
- 서버 기동 뒤 새로 생긴 에이전트 1 (`A:a5b119ea75c28d4c9`, Wave D3, 09:12:40Z) — meta 생성 → RUNNING 같은 초 (< 1 초, 5 초 기준 충족) (`self-observe-r2.md`).
- 관찰(결함 아님): D-02 계층 보기에서 자식이 13 개인 세션 아래 노드 이름표가 겹쳐 읽기 어렵다 (`e2e/r2-g22-d3-new-running.png`).
