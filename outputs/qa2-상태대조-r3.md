# QA2 재검증 (r3) — 상태 · 실시간 · 화면 (웨이브 C3, 2026-10-17, 커밋 4b42f08)

> 범위: DEF-QA2-101~103 재현 · D-21 회귀(G-12 새 표본 30 · 전수 · G-09~G-11) · G-17 · G-18 · G-21 빠른 재확인 · G-22 자기 관찰(`outputs/e2e/self-observe-r3.md`). **고치지 않았다** — 코드 · 설정 · 테스트 · 정본 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/`(self-observe-r3.md · r3-*.jpg · observe-transitions-r3.log) · `outputs/qa2/`(judge_r3.py = judge_r2.py 그대로 · table_r3.py · observe_r3.py · *-r3* 중간 결과 · server-r3.log) · `data/agentdash-qa2.db`.
> 원천은 읽기만(`open(...,"rb")` · `ps -p` · `stat`). 훅 설치 0 · `~/.claude/settings.json` 열지 않음. 본문 없음 — 키 · 시각 · 숫자 · 규칙 코드 · 도구 이름만.
> 서버: `data/agentdash-qa2.db` 삭제 → `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (uv PID 41663 · python PID 41666, **09:30:09Z 기동** → 09:30:12Z 백필 · 첫 판정). 끝날 때 이 PID 와 내 폴러만 정지. 브라우저: 새 탭 하나(1315152305)만 쓰고 닫음.

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-09 판정 규칙 | PASS (회귀) | `tests/test_state.py` 55 passed (r2 와 같음) |
| G-10 연결 규칙 | PASS (회귀) | `tests/test_linker.py` 26 passed (+1 `test_L07_billed_reply_after_handback_is_not_a_rewake`, D-21) |
| G-11 실시간 | PASS (회귀) + 실제 관찰 | `tests/test_realtime.py` 4 passed · 실제 감시기/10 초 판정이 오케스트레이터 RUNNING→SLEEPING 을 마지막 기록 + 304 초(09:34:41Z)에 바꿈 |
| **G-12 상태 대조** | **PASS** | 새 표본 30: **가설 기준 오판 0 · spec 글자 기준 1** (오케스트레이터 SLEEPING vs 글자 STALE, D-18). 전수 331 두 번: 오케스트레이터 RUNNING 때 0/0 · SLEEPING 때 가설 0 / 글자 1. D-21 영향 집단(반환 뒤 사용량 줄 65) 전부 일치 |
| G-17 화면 · API | PASS | check_routes 16/16 HTTP 200 · placeholder 0 |
| G-18 구성도 | PASS | 보기 3 첫 그림 (계층 24h project 거름 노드 18 · 협업 145 ms · 전체 167 ms) · 전체 368→137 접힘 231 "+N" 19 · `?project=` 첫 로드 = API 18 노드 |
| G-21 브라우저 | PASS | 앱 콘솔 오류 0 (D-01 · D-02 보기 3 · D-03 · D-04~D-06) · 390px iframe 6 화면 scrollWidth = clientWidth |
| G-22 자기 관찰 | PASS (`outputs/e2e/self-observe-r3.md`) | 기동 09:30:09Z → QA1 · QA2 RUNNING R-09 09:30:12Z → 오케스트레이터 SLEEPING 가설 D-18 09:34:41Z → QA1 handback 09:38:47.492Z → DONE R-08 09:38:47Z (< 1 초) |

이전 결함 3 건(DEF-QA2-101 · 102 · 103) **모두 해결**. 새 결함 1 건 경미(DEF-QA2-201). 치명 0 · 중대 0.

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-09 -->
G-09  판정 규칙 — 13 규칙 표 테스트 · 경계  PASS  r3 회귀 tests/test_state.py 55 passed (D-18 · D-19 · 90/300 초 정각 포함) · 전체 pytest 296 passed
<!-- gate:G-10 -->
G-10  연결 규칙 — L-01~L-07 테스트  PASS  r3 회귀 tests/test_linker.py 26 passed (+ D-21 test_L07_billed_reply_after_handback_is_not_a_rewake) · 실제 반환 뒤 사용량 줄 에이전트 65 판정 일치
<!-- gate:G-11 -->
G-11  실시간 — SSE 5 초 · 훅 1 초  PASS  r3 회귀 tests/test_realtime.py 4 passed · 실제 서버 감시기/10 초 판정이 오케스트레이터 RUNNING→SLEEPING(09:34:41Z, 마지막 기록 + 304 초) · QA1 반환 → DONE (self-observe-r3)
<!-- gate:G-12 -->
G-12  상태 대조 — 표본 30 오판 ≤ 2  PASS  r3 새 표본 30 (STALE 8 전부 · FAILED 4 새 · 재기상 4 새 · SLEEPING 오케스트레이터 1 · RUNNING 2 · WAITING_INPUT 2 · DONE 9 중 D-21 반환 뒤 사용량 줄 5) 가설(D-14·18·19) 기준 오판 0 · spec 글자 기준 오판 1 (S:2bee9170 SLEEPING vs STALE R-02b, D-18) · 전수 331 가설 0 / 글자 1 · D-21 회귀 없음
<!-- gate:G-17 -->
G-17  화면 · API  PASS  r3 check_routes 16/16 HTTP 200 · placeholder 0 · 실제 DB 로 D-01~D-06 + D-03 열림
<!-- gate:G-18 -->
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3  PASS  r3 실제 DB 보기 3 (계층 · 협업 첫 그림 145 ms · 파이프라인) · 전체 368→137 접힘 231 "+N" 19 · /graph?project= 첫 로드 노드 18 = API 18 (DEF-QA2-103 해결) · 앱 콘솔 오류 0
<!-- gate:G-21 -->
G-21  브라우저 — 콘솔 오류 0 · 390px  PASS  r3 D-01~D-06 + D-03 앱 콘솔 오류 0 · 390px iframe 6 화면 가로 스크롤 0 · D-01 · D-03 「가설 D-18」 표시 · D-03 「기록상 과소 (D-17)」 2

---

## 1. 이전 결함 해결표 (DEF-QA2-101~103)

| 결함 | 이전 | 재현 (r3) | 실측 | 결과 |
|---|---|---|---|---|
| DEF-QA2-101 gate.py QA 리포트 파일명 고정 | 경미 | `gate.qa_latest(g)` 직접 호출 (리포트 쓰기 전) · `gate.round_of('qa2-상태대조-r3.md')` | G-12 · G-18 · G-21 → `outputs/qa2-상태대조-r2.md` PASS, G-22 → `outputs/e2e/self-observe-r2.md` PASS (원본 `qa2-상태대조.md` 의 옛 G-12 FAIL 무시) · `('qa2-상태대조', 3)` · 이 r3 를 쓴 뒤 `make gate` 가 r3 를 읽음 (§6 코드 블록) | **해결** |
| DEF-QA2-102 D-18 가설 표시 없음 | 경미 | 오케스트레이터 SLEEPING 된 뒤 D-01 · D-03 | D-01 살아 있는 에이전트 카드 "잠듦 R-03 **가설 D-18**" (title: spec 글자로는 STALE R-02b) · D-03 판정(저장) "R-03 가설 D-18" · 판정(지금) "잠듦 R-03 가설 D-18" — `e2e/r3-d01-sleeping-d18.jpg` · `e2e/r3-d03-orchestrator-d18.jpg`. D-02 노드 패널 · D-03 머리 배지 · D-01 상단 개수 카드는 표시 없음(근거 문구의 "· D-18" 만) — 관찰, 결함 아님 | **해결** (D-18 자체는 사람 확인 대기) |
| DEF-QA2-103 `/graph?project=` 첫 로드 무시 | 경미 | 새 탭으로 `/graph?view=tree&since=24h&project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` | 첫 로드 select = 그 프로젝트(옵션 37 서버가 미리 채움) · 화면 "노드 18 (에이전트 17 / 전체 332)" = API 같은 질의 18 (거르지 않은 24 h 41) · 주소 유지 — `e2e/r3-d02-project-first-load.jpg` | **해결** |

---

## 2. G-12 상태 대조 (D-21 회귀)

### 2.1 방법

- 표본 시각 **2026-10-17T09:34:46Z** (오케스트레이터가 09:34:41Z 에 SLEEPING 이 된 직후). 대시보드 값 = 같은 초 `agent.state · state_reason` (`outputs/qa2/db-sample-r3.txt`).
- 기대값: `outputs/qa2/judge_r3.py` (= r2 판정기 그대로 · 대시보드 코드 import 0 · 원천 `rb`) — **spec 글자** / **가설(D-14 · D-18 · D-19)** 두 칸. 서브에이전트 반환은 D-04 대안 규칙: 가장 늦은 종료 신호(handback · 알림 completed/failed/killed · Agent 결과 is_error) ≥ 마지막 활동(tool_use 를 낸 assistant 줄 · 들어온 메시지 줄). **텍스트만 있는 assistant 줄(사용량 줄)은 활동이 아니다** — D-21 의 linker 쪽 규칙과 같은 뜻이지만 내 판정기는 대시보드 `last_event_at` 을 보지 않고 원천 줄을 직접 본다.
- 선정 (`outputs/qa2/sample-r3.txt`, r1 · r2 표본과 겹치지 않게 — STALE 은 8 건뿐이라 그대로):
  - STALE **8 전부** (세션 R-06 1 · 서브 R-11 7)
  - FAILED 4 새 (`a394ec40` · `a49e9544` · `ac51018a` · `a55f50d0` — 12 중 r1 · r2 표본 6 제외)
  - 재기상 4 새 — handback 2~4 번 (`aa4bc565` 2 · `a1da87e5` 4 · `a09caff3` 3 · `a9ee2a47` 알림 failed 뒤 handback 2)
  - SLEEPING 오케스트레이터 1 · RUNNING 2 (QA1 `a2384d32` · QA2 나 `a850fbc1`) · WAITING_INPUT 2 (S1 shell · idle)
  - DONE 9 — **D-21 집단(handback 뒤 사용량 줄이 있는 에이전트)** 5 (`a3cafc35` · `aed957fe` · `af55b53c` · `abf0cfa4` · `a0eea617`) · r2 때 RUNNING 이던 2 (`a5b119ea` Wave D3 · `a6b4391e` 이전 QA2) · 워크플로 에이전트 1 (`a5de9442`) · 세션 R-07 1
  - 재기상 4 와 D-21 5 를 합쳐 **9 건이 「마지막 기록 > 마지막 활동」**(반환 뒤 응답 줄) — D-21 이 바꾼 경로.
- 지금 기록에 WAITING_PERMISSION(훅 미설치) · WAITING_CHILD 는 0 건.
- 재현: `grep '^[AS]:' outputs/qa2/sample-r3.txt > outputs/qa2/sample-r3.keys` → `uv run python -I outputs/qa2/judge_r3.py outputs/qa2/sample-r3.keys outputs/qa2/judge-out-r3.json` → `uv run python -I outputs/qa2/table_r3.py`.

### 2.2 결과 — 가설 기준 오판 **0** · spec 글자 기준 오판 **1** → **PASS** (둘 다 ≤ 2)

| # | 키 | 종류 | 원천 근거 | spec 글자 | 가설 (D-14·18·19) | 대시보드 | 일치 (글자 / 가설) |
|---|---|---|---|---|---|---|---|
| 1 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (229167초 전) · 마지막 줄 assistant:tool_use · 마지막 tool_use AskUserQuestion · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z(지남) · 자식 64 (미종료 0) | STALE R-06 | STALE R-06 | STALE R-06 | O / O |
| 2 | `A:a3b3e327f20477922` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T20:23:12 (2466694초 전) · 마지막 활동 09-18T20:23:12 · 반환 notification:failed@09-18T18:34:34, handback@09-18T20:07:22 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 3 | `A:adb2bacd2ac16c31f` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T21:07:41 (2464025초 전) · 마지막 활동 09-18T21:07:41 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 4 | `A:a2a0029196a84aba3` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T01:23:26 (1671080초 전) · 마지막 활동 09-28T01:13:14 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 5 | `A:abca160dd070f2db8` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-09T03:56:32 (711493초 전) · 마지막 활동 10-09T03:08:06 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 6 | `A:a39a8de156b8640a4` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T16:21:27 (407599초 전) · 마지막 활동 10-12T16:21:12 · 반환 handback@10-12T16:21:02 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 7 | `A:abe5c570d21c89b2a` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:21 (403644초 전) · 마지막 활동 10-12T17:26:36 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 8 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T17:27:26 (403639초 전) · 마지막 활동 10-12T17:26:57 · 반환 없음 | STALE R-11 | STALE R-11 | STALE R-11 | O / O |
| 9 | `A:a394ec40b66b451b3` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T01:23:25 (1671080초 전) · 마지막 활동 09-28T01:14:02 · 반환 notification:failed@09-28T01:23:25 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 10 | `A:a49e954498bc7e130` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T18:41:09 (1608817초 전) · 마지막 활동 09-28T18:41:09 · 반환 notification:failed@09-28T18:41:09 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 11 | `A:ac51018a75fb63658` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 09-28T10:07:37 (1639628초 전) · 마지막 활동 09-28T10:00:46 · 반환 notification:failed@09-28T10:07:37 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 12 | `A:a55f50d06b587ce87` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 10-08T22:31:29 (730997초 전) · 마지막 활동 10-08T22:31:27 · 반환 notification:failed@10-08T22:31:29 | FAILED R-08 | FAILED R-08 | FAILED R-08 | O / O |
| 13 | `A:aa4bc5654ebfe770f` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 10-12T16:08:23 (408382초 전) · 마지막 활동 10-12T16:08:23 · 반환 handback@10-12T15:56:25, handback@10-12T16:08:23 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 14 | `A:a1da87e59d81ad2e5` | SUBAGENT | 세션 4c204b8c S1 없음 (프로세스 없음) · 마지막 기록 09-18T10:40:54 (2501632초 전) · 마지막 활동 09-18T10:40:38 · 반환 handback@09-17T22:50:17, handback@09-18T00:43:40, handback@09-18T00:57:24, handback@09-18T10:40:38 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 15 | `A:a09caff3108c75039` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:38:19 (1673786초 전) · 마지막 활동 09-28T00:38:11 · 반환 handback@09-27T22:33:46, handback@09-28T00:23:03, handback@09-28T00:38:11 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 16 | `A:a9ee2a4747ed0b102` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 09-18T23:45:33 (2454553초 전) · 마지막 활동 09-18T23:45:21 · 반환 notification:failed@09-18T19:05:51, handback@09-18T20:23:43, handback@09-18T23:45:21 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 17 | `S:2bee9170-9e95-4e4e-873d-8490f228ad20` | SESSION | S1 status=busy · pid 살아 있음 · 마지막 기록 2026-10-17T09:29:37Z (309초 전) · 마지막 줄 assistant:text · 마지막 tool_use ScheduleWakeup · ScheduleWakeup 2026-10-17T09:59:24Z(미래) · 자식 16 (미종료 2) | STALE R-02b | SLEEPING R-03 (D-18) | SLEEPING R-03 | **X** / O |
| 18 | `A:a2384d3236592c914` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:34:45 (0초 전) · 마지막 활동 10-17T09:34:45 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O / O |
| 19 | `A:a850fbc10924baf9b` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:34:46 (0초 전) · 마지막 활동 10-17T09:34:46 · 반환 없음 | RUNNING R-09 | RUNNING R-09 | RUNNING R-09 | O / O |
| 20 | `S:493d1a8d-6430-4776-95f1-f6b085637edd` | SESSION | S1 status=shell · pid 살아 있음 · 마지막 기록 2026-10-17T07:05:55Z (8931초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 0 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O / O |
| 21 | `S:47aedf14-c5b7-4450-a193-6612b438b1f2` | SESSION | S1 status=idle · pid 살아 있음 · 마지막 기록 2026-10-17T08:52:37Z (2528초 전) · 마지막 줄 user:message · 마지막 tool_use Bash · 자식 0 (미종료 0) | WAITING_INPUT R-05 | WAITING_INPUT R-05 | WAITING_INPUT R-05 | O / O |
| 22 | `A:a3cafc358465dbe30` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:28:13 (1674393초 전) · 마지막 활동 09-28T00:28:00 · 반환 handback@09-27T22:22:51, handback@09-28T00:28:00 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 23 | `A:aed957feccd6819df` | SUBAGENT | 세션 4c204b8c S1 없음 (프로세스 없음) · 마지막 기록 09-18T00:22:33 (2538733초 전) · 마지막 활동 09-18T00:22:23 · 반환 handback@09-17T22:44:49, notification:completed@09-17T22:45:06, handback@09-18T00:22:23 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 24 | `A:af55b53c2e51eee81` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:28:11 (1674395초 전) · 마지막 활동 09-28T00:28:00 · 반환 notification:completed@09-27T22:14:14, handback@09-27T22:17:14, handback@09-28T00:28:00 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 25 | `A:abf0cfa4d45771600` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:01:49 (1675976초 전) · 마지막 활동 09-28T00:01:41 · 반환 notification:failed@09-27T23:28:30, handback@09-28T00:01:41 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 26 | `A:a0eea61708f893889` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 09-28T00:12:20 (1675345초 전) · 마지막 활동 09-28T00:12:16 · 반환 notification:failed@09-27T23:28:30, notification:completed@09-28T00:05:42, notification:completed@09-28T00:07:12, handback@09-28T00:12:16 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 27 | `A:a5b119ea75c28d4c9` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:27:58 (407초 전) · 마지막 활동 10-17T09:27:58 · 반환 handback@10-17T09:27:58 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 28 | `A:a6b4391e741b5db27` | SUBAGENT | 세션 2bee9170 S1 busy · 마지막 기록 10-17T09:19:02 (944초 전) · 마지막 활동 10-17T09:19:01 · 반환 handback@10-17T09:19:01 | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 29 | `A:a5de9442449dd9e3f` | WORKFLOW_AGENT | 세션 8f3a6abd S1 없음 (프로세스 없음) · 마지막 기록 10-10T02:49:37 (629109초 전) · 마지막 활동 10-10T02:49:37 · 반환 없음 · S6 status=completed | DONE R-08 | DONE R-08 | DONE R-08 | O / O |
| 30 | `S:ae4ea40d-8f2c-47cd-ac22-b9c562f8ce86` | SESSION | S1 없음 · 마지막 기록 2026-10-16T09:04:39Z (88206초 전) · 마지막 줄 assistant:text · 마지막 tool_use Bash · 자식 1 (미종료 0) | DONE R-07 | DONE R-07 | DONE R-07 | O / O |

상태별 (가설 기준): STALE 8/8 · FAILED 4/4 · 재기상 4/4 · SLEEPING 1/1 · RUNNING 2/2 · WAITING_INPUT 2/2 · DONE 9/9.
**spec 글자 ≠ 가설**: #17 `S:2bee9170…` 하나 — r2 와 같은 건(D-18). 대시보드 SLEEPING. 사람이 D-18 을 확정하면 0, 반박하면 1 — 어느 쪽이든 ≤ 2.

### 2.3 전수 대조 + D-21 집단

- 전수 331 (WORKFLOW 노드 1 제외), 두 시점:
  - 09:31:08Z (오케스트레이터 RUNNING R-02a): **가설 0 · 글자 0** (`judge-all-r3.json` · `db-all-r3.txt`)
  - 09:34:57Z (오케스트레이터 SLEEPING): **가설 0 · 글자 1** (= #17) (`judge-all-r3b.json` · `db-all-r3b.txt`)
- D-21 불변식 (QA2 DB): `usage_event.at > agent.last_event_at` 에이전트 **0** · `tool_call.at > last_event_at` **0**.
- handback 뒤 사용량 줄이 있는 에이전트 **65** (`outputs/qa2/d21-post-handback-r3.txt`): DONE R-08 64 · STALE R-11 1 (`a39a8de1`, handback 뒤 들어온 메시지 2 — 반환 뒤 다시 깸, 판정기도 STALE) — 65 전부 판정기와 일치. 모두 `last_event_at` = 마지막 사용량 줄 시각.
- D-21 「한계」(반환 뒤 들어온 메시지에 tool_use 없이 답만 하고 끝 — 대시보드 「반환 그대로」 vs 내 판정기 「다시 깸」): 전수 불일치 0 → **실측 0 건** (decisions D-21 기록과 같음).

---

## 3. G-09 · G-10 · G-11 회귀

`uv run pytest -q tests/test_state.py` 55 passed · `tests/test_linker.py` 26 passed · `tests/test_realtime.py` 4 passed · `tests/test_graph.py tests/test_dashboard.py` 19 passed · 전체 `uv run pytest -q` **296 passed** (14.7 s).
G-11 실제: 재백필 없이 감시기 · 10 초 판정이 오케스트레이터 RUNNING R-02a → SLEEPING R-03 (09:34:41Z = 마지막 기록 09:29:37Z + 304 초, 근거 "깰 시각 09:59:24Z · D-18") · QA1 DONE (self-observe-r3).

---

## 4. G-17 · G-18 · G-21 브라우저 (Claude in Chrome · 새 탭 하나만 · 끝나고 그 탭만 닫음)

| 화면 | 확인 | 앱 콘솔 오류 | 스크린샷 |
|---|---|---|---|
| D-02 `?project=` 첫 로드 | select = Multi-agent Dashboard · 노드 18 (에이전트 17 / 332) · 서버 17.8 ms | 0 | `e2e/r3-d02-project-first-load.jpg` |
| D-04 · D-05 · D-06 | 열림 | 0 | — |
| D-02 협업 24 h | 노드 41 · 첫 그림 145 ms | 0 | — |
| D-02 파이프라인 · 계층 전체 | 접기 전 368 > 300 → 137 · 접힘 231 · "+N" 19 (예 "multi-agent-dashboard-ce · RUNNING +14") · 첫 그림 167 ms | 0 | — |
| D-01 `/` | 카드 실행 2 · 입력 대기 2 · 잠듦 1 · 멈춤 의심 8 · 오늘 끝남 15 · 머리 줄 "에이전트 331 (살아 있음 13 · 누적 끝남 306 · 실패 12)" · 오케스트레이터 카드 "잠듦 R-03 **가설 D-18**" | 0 | `e2e/r3-d01-sleeping-d18.jpg` |
| D-03 오케스트레이터 | 판정(저장) R-03 가설 D-18 · 판정(지금) 잠듦 R-03 가설 D-18 · 상태 이력 RUNNING → SLEEPING 09:34:41Z · 「기록상 과소 (D-17)」 2 · 원본 보기 버튼 | 0 | `e2e/r3-d03-orchestrator-d18.jpg` |

콘솔: `read_console_messages`(onlyErrors · 확장 URL 제외)로 화면 묶음마다 읽고 비움 — 0.
**390px** (같은 출처 iframe `width:390px`, innerWidth 390): `/` · `/graph?…project=` · `/agents/S:2bee9170…` · `/usage` · `/timeline` · `/pipeline` 모두 clientWidth 375 = scrollWidth 375 (세로 스크롤바 15) → 가로 스크롤 0.

---

## 5. 새 결함

### DEF-QA2-201 — D-18 가설 표시가 D-02 노드 패널 · D-03 머리 배지에는 없음 · 경미 · 개발2
- 실측: D-01 살아 있는 에이전트 카드 · D-03 판정 두 칸에는 「가설 D-18」 이 붙지만, D-03 제목 옆 상태 배지는 "잠듦" 만, D-02 노드 색 · 노드 패널은 근거 문구 끝 "· D-18" 만 있다(`templates/graph.html` · `core/graph.py` 에 hypothesis 사용 0 — grep). D-01 상단 「잠듦 SLEEPING 1」 개수 카드도 표시 없음.
- 기대(제안): 같은 판정이 보이는 모든 곳에 같은 표시, 또는 사람이 D-18 을 확정하면 닫음. G-12 · G-18 · G-21 판정 영향 없음.

치명 결함 0 · 중대 결함 0 — 원천 쓰기 · 본문 저장 · 훅 손상 · 외부 전송을 보지 못했다.

## 6. `make gate` (이 리포트 · self-observe-r3 를 쓴 뒤)

`make gate` 2026-10-17 18:40:17 KST (서버 정지 뒤) — 게이트 · 판정 · 읽은 QA 파일만 줄여 붙임:

```
G-01  PASS  
G-02  PASS  
G-03  PASS  
G-04  PASS  outputs/qa1-데이터안전-r3.md
G-05  PASS  outputs/qa1-데이터안전-r3.md
G-06  PASS  outputs/qa1-데이터안전-r3.md
G-07  PASS  outputs/qa1-데이터안전-r3.md
G-08  PASS  outputs/qa1-데이터안전-r3.md
G-09  PASS  outputs/qa2-상태대조-r3.md
G-10  PASS  outputs/qa2-상태대조-r3.md
G-11  PASS  outputs/qa2-상태대조-r3.md
G-12  PASS  outputs/qa2-상태대조-r3.md
G-13  PASS  outputs/qa1-데이터안전-r3.md
G-14  PASS  outputs/qa1-데이터안전-r3.md
G-15  PASS  outputs/qa1-데이터안전-r3.md
G-16  PASS  outputs/qa1-데이터안전-r3.md
G-17  PASS  outputs/qa2-상태대조-r3.md
G-18  PASS  outputs/qa2-상태대조-r3.md
G-19  PASS  outputs/qa1-데이터안전-r3.md
G-20  PASS  outputs/qa1-데이터안전-r3.md
G-21  PASS  outputs/qa2-상태대조-r3.md
G-22  PASS  outputs/e2e/self-observe-r3.md
# 합계 PASS 22 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0
```
