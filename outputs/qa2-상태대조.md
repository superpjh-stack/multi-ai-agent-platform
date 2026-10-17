# QA2 — 상태 · 실시간 · 화면 (웨이브 C, 2026-10-17)

> 범위 G-09~G-12 · G-17 · G-18 · G-21 · G-22. **고치지 않았다** — 코드 · 설정 · 테스트 · 정본 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/` · `outputs/qa2/`(스크립트 · 중간 결과) · `data/agentdash-qa2.db`(서버 DB).
> 원천은 읽기만(`open(...,"rb")` · `ps -p`). 본문 없음 — 키 · 시각 · 숫자 · 규칙 코드만.
> 서버: `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (uv PID 19632 · python PID 19635, 17:06:43 KST 기동 → 빈 DB 백필 + 감시기). 끝날 때 이 PID 만 정지.

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-09 판정 규칙 | PASS (테스트) · 빈 경계 4 | `tests/test_state.py` 통과. 단 실패 알림 → FAILED · 재기상 뒤 알림 · busy+예약 · busy+pid 소멸 경계 없음 (DEF-QA2-006) |
| G-10 연결 규칙 | PASS (테스트) · 빈 경계 2 | `tests/test_linker.py` 통과. 다시 깨운 뒤 새 tool-use-id 알림 · `to="S:<id>"` 없음 (DEF-QA2-007) |
| G-11 실시간 | PASS (테스트) + 실제 관찰 | `tests/test_realtime.py` 통과 · 실제 감시기/10 초 판정이 RUNNING→WAITING_CHILD 를 바꿈(08:10:52Z) |
| **G-12 상태 대조** | **FAIL** | 표본 30 중 일치 27 · **오판 3** (R-08 실패 알림 2 · L-07/R-08 재기상 알림 1) > 허용 2. 전체 322 대조 오판 14 |
| G-17 화면 · API | PASS | 화면 6 + 상세 + 그래프 3 보기 실제 데이터로 열림 (gate 의 check_routes 16/16 200) |
| G-18 구성도 | PASS | 보기 3 · 필터 · 접기 359→125 ("+N" 19) · 노드 클릭 → 패널 · 더블클릭 → D-03 · 첫 그림 45~67 ms |
| G-21 브라우저 | PASS | 앱 콘솔 오류 0 (확장 경고 6 은 별도) · 390px 가로 스크롤 0 (8 화면, iframe 측정 — 창 크기 조절이 막힘) |
| G-22 자기 관찰 | `outputs/e2e/self-observe.md` | QA1 · QA2 가 이 프로젝트 세션 아래 `spawn` 엣지 · RUNNING R-09, 이전 웨이브 5 개 DONE R-08 |

| 결함 | 등급 | 담당 | 한 줄 |
|---|---|---|---|
| DEF-QA2-001 | 중대 | 개발2 | `<task-notification>` status failed/killed 로 끝난 서브에이전트가 FAILED 대신 DONE (전체 12 건, 표본 2) · D-01 "실패 0" |
| DEF-QA2-002 | 중대 | 개발2 | SendMessage 로 다시 깨운 뒤 온 알림(새 tool-use-id · task-id=agentId)을 못 이어 끝난 자식이 STALE (전체 1, 표본 1) |
| DEF-QA2-003 | 중대 | 개발2 | DB 연결 경로의 "마지막 활동"이 tool_call 만 봐서 반환 뒤 들어온 메시지를 무시 → D-04 규칙상 STALE 인 자식이 DONE (전체 1) |
| DEF-QA2-004 | 경미 | 개발2 · 사람(spec) | S1 busy · 5 분 무기록 · ScheduleWakeup 미래 · 자식 0 → STALE R-02b (잠든 오케스트레이터가 멈춤 의심으로) |
| DEF-QA2-005 | 경미 | 사람(spec) · 개발2 | S1 있음 · busy · pid 소멸 → 구현 R-07 DONE, spec R-02b 글자는 STALE · 5 분 안은 spec 규칙 없음 |
| DEF-QA2-006 | 경미 | 개발2 | G-09 표 기반 테스트에 빠진 경계 (001 · 004 · 005 · STALE 자식 제외) |
| DEF-QA2-007 | 경미 | 개발2 | G-10 테스트에 빠진 경계 + `resolve_message` 의 `S:<id>` 비교 오류 |
| DEF-QA2-008 | 경미 | 아키텍트 | `gate.py` 가 QA 리포트의 **모든** `G-nn  …  판정` 꼴 줄을 읽음 — 리포트에 `make gate` 출력을 그대로 붙이면 예전 판정이 섞인다 |

치명 결함 0 — 원천 쓰기 · 본문 저장 · 훅 손상 · 외부 전송을 이번 검사에서 보지 못했다(`~/.claude/settings.json` 은 QA1 범위, 나는 읽지도 않았다).

## 게이트 판정 행 (gate.py 가 읽는 줄)

```
G-12  상태 대조 — 표본 30 오판 ≤ 2  FAIL  표본 30 (STALE 8 · RUNNING 3 · WAITING_INPUT 2 · 실패 신호 6 · 끝남 11) 일치 27 · 오판 3 (R-08 failed→DONE 2 · L-07 재기상 알림 STALE 1) · 전체 322 대조 오판 14 — DEF-QA2-001·002·003
G-18  구성도 — 브라우저 보기 3 · 접기 · 패널  PASS  실제 DB 노드 359→125 접힘 234 · "+N" 19 · 보기 3 첫 그림 45/51/54 ms · 필터 state=STALE · 노드 클릭 패널 · 더블클릭 D-03 · 앱 콘솔 오류 0
G-21  브라우저 — 콘솔 오류 0 · 390px  PASS  D-01~D-06 + D-03 + 원본 보기 앱 콘솔 오류 0 (확장 경고 6 별도) · 390px iframe 8 화면 scrollWidth = clientWidth (가로 스크롤 0) · 창 390 조절은 브라우저가 막음
```

---

## 1. G-12 상태 대조 (가장 중요)

### 1.1 방법

- 표본 시각 **2026-10-17T08:09:50Z** (서버 백필 08:06:5xZ 직후). 대시보드 값은 `data/agentdash-qa2.db` 의 `agent.state · state_reason`(08:08Z 조회 · 이후 바뀐 오케스트레이터는 표본 시각 값).
- 기대값은 **내 스크립트** `outputs/qa2/judge.py` (대시보드 코드 import 0, 원천을 `rb` 로 읽음). spec §4.2 순서 그대로, 반환(L-07)은 `decisions.md` D-04 대안 규칙(확정 · 개발2 실측)을 따랐다:
  - 세션: `~/.claude/sessions/*.json` 의 `sessionId` · `status` · `pid` → `ps -p <pid>` 생존. 기록의 마지막 `timestamp` · 마지막 assistant/user 줄 종류 · 결과 없는 tool_use · 마지막 `ScheduleWakeup`(timestamp + delaySeconds) · 자식 meta 수와 그 판정.
  - 서브에이전트: 자기 기록의 마지막 시각 · 마지막 활동(tool_use 를 낸 assistant 줄 · 들어온 메시지 줄) · 자기 `SubagentHandback` · 같은 세션 폴더 모든 기록의 `<task-notification>`(tool-use-id = meta `toolUseId` **또는** task-id = agentId) status · Agent tool_result `is_error` · 소속 세션 S1 pid 생존 · 자기 자식.
  - failed · killed · is_error 는 FAILED (spec §4.1 FAILED "오류로 끝남 … 실패 보고", §4.2 R-08 "결과 is_error 면 FAILED", D-04 "failed · killed 는 오류").
- 선정: 대시보드 STALE **8 건 전부**(세션 R-06 1 · 서브에이전트 R-11 7 — 개발2 실측 8 과 같은 수), RUNNING 3(오케스트레이터 · QA1 · QA2), WAITING_INPUT 2(S1 `shell` 1 · `idle` 1), 실패 신호(`notification:failed` 엣지) 6, 끝남 11(알림 completed 2 · handback 3 · 깊이 2 손자 1 · 워크플로 에이전트 1 · 이 프로젝트 아키텍트 1 · 세션 R-07 3). WAITING_PERMISSION · SLEEPING 은 지금 기록에 0 건(훅 미설치 · 잠든 세션 없음).
- 재현: `uv run python -I outputs/qa2/judge.py outputs/qa2/sample.txt outputs/qa2/judge-out.json` → `uv run python -I outputs/qa2/table.py`.

### 1.2 결과 — 30 건 중 일치 27 · 오판 3 → **FAIL** (허용 ≤ 2)

| # | 키 | 종류 | 원천 근거 (S1 · pid · 마지막 기록 · 마지막 줄 · 반환 신호) | QA 판정 | 대시보드 | 일치 |
|---|---|---|---|---|---|---|
| 1 | `S:dbd09a2a-f7cb-4121-9a92-cf8d0352ad28` | SESSION | S1 없음 · 마지막 기록 2026-10-14T17:55:19Z (224071초 전) · 마지막 줄 assistant:tool_use · 결과 없는 tool_use ['AskUserQuestion'] · ScheduleWakeup 2026-10-14T17:34:00Z · 자식 64 (미종료 0) | **STALE** R-06 | STALE R-06 | O |
| 2 | `A:adb2bacd2ac16c31f` | SUBAGENT | 세션 09cc91b1 S1 없음 (프로세스 없음) · 마지막 기록 2026-09-18T21:07:41Z (2458929초 전) · 마지막 줄 user:message · 마지막 활동 09-18T21:07:41 · 반환 신호 없음 | **STALE** R-11 | STALE R-11 | O |
| 3 | `A:a2a0029196a84aba3` | SUBAGENT | 세션 6a44e325 S1 없음 (프로세스 없음) · 마지막 기록 2026-09-28T01:23:26Z (1665984초 전) · 마지막 줄 assistant:text · 마지막 활동 09-28T01:13:14 · 반환 신호 없음 | **STALE** R-11 | STALE R-11 | O |
| 4 | `A:adc075af0bd2072a0` | SUBAGENT | 세션 a82388db S1 없음 (프로세스 없음) · 마지막 기록 2026-09-28T00:17:37Z (1669933초 전) · 마지막 줄 assistant:text · 마지막 활동 09-28T00:17:02 · 반환 신호 notification:completed@09-27T16:18:14, notification:completed@09-27T16:44:18, notification:completed@09-27T17:57:31, notification:completed@09-28T00:17:39 | **DONE** R-08 | STALE R-11 | **X 오판** |
| 5 | `A:abca160dd070f2db8` | SUBAGENT | 세션 67760b59 S1 없음 (프로세스 없음) · 마지막 기록 2026-10-09T03:56:32Z (706397초 전) · 마지막 줄 assistant:text · 마지막 활동 10-09T03:08:06 · 반환 신호 없음 | **STALE** R-11 | STALE R-11 | O |
| 6 | `A:a39a8de156b8640a4` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 2026-10-12T16:21:27Z (402503초 전) · 마지막 줄 assistant:text · 마지막 활동 10-12T16:21:12 · 반환 신호 handback@10-12T16:21:02 (그 뒤 활동 → 다시 깨어남) | **STALE** R-11 | STALE R-11 | O |
| 7 | `A:abe5c570d21c89b2a` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 2026-10-12T17:27:21Z (398549초 전) · 마지막 줄 assistant:text · 마지막 활동 10-12T17:26:36 · 반환 신호 없음 | **STALE** R-11 | STALE R-11 | O |
| 8 | `A:acfbcbeabcb648847` | SUBAGENT | 세션 dbd09a2a S1 없음 (프로세스 없음) · 마지막 기록 2026-10-12T17:27:26Z (398544초 전) · 마지막 줄 assistant:text · 마지막 활동 10-12T17:26:57 · 반환 신호 없음 | **STALE** R-11 | STALE R-11 | O |
| 9 | `S:2bee9170-9e95-4e4e-873d-8490f228ad20` | SESSION | S1 85955.json status=busy · `ps -p 85955` 살아 있음 · 마지막 기록 2026-10-17T08:05:52Z (238초 전) · 마지막 줄 assistant:text · ScheduleWakeup 2026-10-17T08:35:38Z · 자식 7 (미종료 2) | **RUNNING** R-02a | RUNNING R-02a | O |
| 10 | `A:a85b98ff6f908df54` | SUBAGENT | 세션 2bee9170 S1 busy (살아 있음) · 마지막 기록 2026-10-17T08:09:50Z (0초 전) · 마지막 줄 user:tool_result · 반환 신호 없음 | **RUNNING** R-09 | RUNNING R-09 | O |
| 11 | `A:aa798b51a24f94adf` | SUBAGENT | 세션 2bee9170 S1 busy (살아 있음) · 마지막 기록 2026-10-17T08:09:50Z (0초 전) · 마지막 줄 assistant:tool_use · 반환 신호 없음 | **RUNNING** R-09 | RUNNING R-09 | O |
| 12 | `S:493d1a8d-6430-4776-95f1-f6b085637edd` | SESSION | S1 95593.json status=shell · `ps -p 95593` 살아 있음 · 마지막 기록 2026-10-17T07:05:55Z (3835초 전) · 마지막 줄 assistant:text · 자식 0 | **WAITING_INPUT** R-05 (D-09) | WAITING_INPUT R-05 | O |
| 13 | `S:47aedf14-c5b7-4450-a193-6612b438b1f2` | SESSION | S1 95787.json status=idle · `ps -p 95787` 살아 있음 · 마지막 기록 2026-10-17T07:58:15Z (695초 전) · 마지막 줄 assistant:text · 자식 0 | **WAITING_INPUT** R-05 | WAITING_INPUT R-05 | O |
| 14 | `A:a1be09e3359a3ca1b` | SUBAGENT | 세션 dbd09a2a S1 없음 · 마지막 기록 2026-10-14T15:25:40Z · 마지막 줄 user:tool_result · 반환 신호 notification:failed@10-14T00:01:57, handback@10-14T15:25:40 (가장 늦은 = handback) | **DONE** R-08 | DONE R-08 | O |
| 15 | `A:ac4e7216cbd09ab07` | SUBAGENT | 세션 df9fa7f8 S1 없음 · 마지막 기록 2026-10-11T07:56:58Z · 반환 신호 notification:failed@10-11T02:05:26, handback@10-11T07:56:58 | **DONE** R-08 | DONE R-08 | O |
| 16 | `A:a9afb7c7042020e72` | SUBAGENT | 세션 df9fa7f8 S1 없음 · 마지막 기록 2026-10-11T07:56:48Z · 반환 신호 notification:failed@10-11T02:05:26, handback@10-11T07:56:48 | **DONE** R-08 | DONE R-08 | O |
| 17 | `A:a92030bc3db0e0a8e` | SUBAGENT | 세션 df9fa7f8 S1 없음 · 마지막 기록 2026-10-11T07:56:25Z · 반환 신호 notification:failed@10-11T02:05:26, handback@10-11T07:56:24 | **DONE** R-08 | DONE R-08 | O |
| 18 | `A:a3a79ff5ebee2a7fa` | SUBAGENT | 세션 67760b59 S1 없음 · 마지막 기록 2026-10-08T22:32:19Z · 마지막 줄 assistant:text · 마지막 활동 10-08T22:32:19 · 반환 신호 **notification:failed**@10-08T22:32:20 (유일) | **FAILED** R-08 | DONE R-08 | **X 오판** |
| 19 | `A:a5a75228a8eaf44fc` | SUBAGENT | 세션 67760b59 S1 없음 · 마지막 기록 2026-10-08T22:31:46Z · 마지막 줄 assistant:text · 마지막 활동 10-08T22:31:45 · 반환 신호 **notification:failed**@10-08T22:31:46 (유일) | **FAILED** R-08 | DONE R-08 | **X 오판** |
| 20 | `A:af7afb54cf071f370` | SUBAGENT | 세션 dbd09a2a S1 없음 · 마지막 기록 2026-10-13T20:54:53Z · 반환 신호 notification:completed@10-13T20:43:53, handback@10-13T20:54:53 | **DONE** R-08 | DONE R-08 | O |
| 21 | `A:a09ca3114de33f070` | SUBAGENT | 세션 dbd09a2a S1 없음 · 마지막 기록 2026-10-13T20:54:08Z · 반환 신호 handback@10-13T20:54:07, notification:completed@10-13T20:54:17 | **DONE** R-08 | DONE R-08 | O |
| 22 | `A:adbcd6ddd172a1a37` | SUBAGENT | 세션 dbd09a2a S1 없음 · 마지막 기록 2026-10-12T18:47:48Z · 반환 신호 handback@10-12T18:47:48 | **DONE** R-08 | DONE R-08 | O |
| 23 | `A:a13d00c3ffcad4892` | SUBAGENT | 세션 dbd09a2a S1 없음 · 마지막 기록 2026-10-13T17:54:30Z · 반환 신호 handback@10-13T17:54:30 | **DONE** R-08 | DONE R-08 | O |
| 24 | `A:a6130eff62a5e5e2c` | SUBAGENT | 세션 67760b59 S1 없음 · 마지막 기록 2026-10-09T06:27:32Z · 반환 신호 handback@10-09T06:27:32 | **DONE** R-08 | DONE R-08 | O |
| 25 | `A:a76932516fc410131` | SUBAGENT (깊이 2) | 세션 8f3a6abd S1 없음 · 마지막 기록 2026-10-09T18:33:31Z · 마지막 활동 10-09T18:33:10 · 반환 신호 handback@10-09T18:33:05, notification:completed@10-09T18:33:34 | **DONE** R-08 | DONE R-08 | O |
| 26 | `A:a5de9442449dd9e3f` | WORKFLOW_AGENT | 세션 8f3a6abd S1 없음 · 마지막 기록 2026-10-10T02:49:37Z · 반환 신호 없음 · S6 `workflows/wf_*.json` status=completed | **DONE** R-08 | DONE R-08 | O |
| 27 | `A:ae52277140e6732bc` | SUBAGENT | 세션 2bee9170 S1 busy (살아 있음) · 마지막 기록 2026-10-17T07:15:13Z · 반환 신호 handback@10-17T07:15:12 | **DONE** R-08 | DONE R-08 | O |
| 28 | `S:11ca1f26-f741-41b1-8811-2225b85e23a6` | SESSION | S1 없음 · 마지막 기록 2026-10-17T01:26:14Z · 마지막 줄 assistant:text · 자식 0 | **DONE** R-07 | DONE R-07 | O |
| 29 | `S:ae4ea40d-8f2c-47cd-ac22-b9c562f8ce86` | SESSION | S1 없음 · 마지막 기록 2026-10-16T09:04:39Z · 마지막 줄 assistant:text · 자식 1 | **DONE** R-07 | DONE R-07 | O |
| 30 | `S:48969e43-c379-4e13-9121-4effbb9bc79d` | SESSION | S1 없음 · 마지막 기록 2026-09-30T04:29:09Z · 마지막 줄 assistant:text · ScheduleWakeup 2026-09-30T04:25:55Z (지남) | **DONE** R-07 | DONE R-07 | O |

상태별: STALE 8 중 일치 7 · RUNNING 3/3 · WAITING_INPUT 2/2 · 실패 신호 6 중 일치 4 (4 건은 failed 뒤 다시 깨어나 handback 으로 끝 → DONE 이 맞음) · 끝남 11/11.

### 1.3 전체 대조 (표본 밖, 참고)

같은 판정기로 DB 의 에이전트 322 건 전부(WORKFLOW 노드 1 제외)를 08:10Z 에 대조 — **불일치 14**: `DONE→FAILED` 12 (DEF-QA2-001, D-04 의 "failed 12" 와 같은 수) · `STALE→DONE` 1 (DEF-QA2-002, 표본 #4) · `DONE→STALE` 1 (`A:a3b3e327f20477922`, DEF-QA2-003). 나머지 308 일치.
재현: `sqlite3 data/agentdash-qa2.db "SELECT agent_key FROM agent WHERE kind!='WORKFLOW'" > outputs/qa2/all.txt` → `uv run python -I outputs/qa2/judge.py outputs/qa2/all.txt outputs/qa2/judge-all.json`.

### 1.4 D-14 와 표본 뒤 변화 (오판으로 세지 않음)

오케스트레이터 `S:2bee9170…` 는 표본 시각에 RUNNING R-02a(일치). 08:10:52Z 에 마지막 기록 뒤 5 분이 지나며 대시보드가 **WAITING_CHILD R-04 (D-14)** 로 바꿨다. spec R-02b 글자대로면 STALE 이지만 실제로는 QA1 · QA2 를 기다리는 중 — D-14(가설 반박 → 대안 규칙)가 맞게 작동했다. 다만 이 세션은 ScheduleWakeup 08:35:38Z 도 걸어 두었다 → 자식이 끝나면 DEF-QA2-004 경로(STALE R-02b)로 갈 수 있다 (`outputs/e2e/self-observe.md` 에서 계속 관찰).

---

## 2. G-09 · G-10 경계 재확인

`uv run pytest -q tests/test_state.py tests/test_linker.py tests/test_realtime.py tests/test_graph.py tests/test_dashboard.py` → **74 passed** (12.7 s). 규칙 13 전부 표 행 ≥ 1, 89/91 · 299/301 · 훅 도구 실행 중 · STALE→회복 있음.

순수 함수 탐침 (`uv run python outputs/qa2/probe_boundaries.py`, state.evaluate 만 부름 · DB · 원천 없음):

| 입력 | 결과 | spec 기대 | 판단 |
|---|---|---|---|
| 서브에이전트 정확히 90 초 | RUNNING R-12 | "< 90 초" R-09 아님 → R-12 | 맞음 (테스트 없음) |
| 서브에이전트 정확히 300 초 | STALE R-11 | "≥ 5 분" | 맞음 (테스트 없음) |
| 세션 busy 정확히 300 초 | STALE R-02b | "5 분 넘게" — 300 초 정각은 해석 여지 | 경계 테스트 없음 |
| 세션 S1 busy · pid 소멸 · 60 초 · 미결 없음 | DONE R-07 | R-02a(pid 필요) · R-02b(5 분) · R-06/R-07(S1 없음) 어디에도 안 걸림 | spec 빈칸 (DEF-QA2-005) |
| 세션 S1 busy · pid 소멸 · 600 초 | DONE R-07 | R-02b 글자(S1 있음 · busy · 5 분) → STALE | 다름 (DEF-QA2-005) |
| 세션 busy · 600 초 · ScheduleWakeup 미래 · 자식 0 | STALE R-02b | R-03 은 idle 만 → spec 도 STALE, 실제는 잠듦 | DEF-QA2-004 |
| 세션 idle · 예약 미래 + 자식 1 | SLEEPING R-03 | R-03 이 R-04 보다 먼저 | 맞음 |
| 서브에이전트 세션 소멸 · 훅 도구 실행 중 | STALE R-11 | R-11 "소멸 **또는** 무기록(훅 도구 실행 중 제외)" — 소멸 쪽은 예외 없음 | 맞음 |

DB 경로(빌드 `state.build_ctx`)에서 빠진 것 — 표 기반 테스트는 `Ctx` 를 손으로 만들어서 아래를 못 본다:
- `return_error` 는 spawn tool_use 의 `ok=0` 일 때만 참 — `linker.returned()` 가 계산한 failed/killed 오류를 받지 않는다 (DEF-QA2-001).
- `_open_children` 은 STALE 자식을 뺀다(D-14 문구) — R-04 · R-10 에서 STALE 자식만 남은 부모의 판정 테스트 없음.
- `wakeup_at` 은 "마지막 assistant 의 ScheduleWakeup" 이 아니라 "가장 최근 ScheduleWakeup 호출" — spec R-03 문구와 다르다(예약 뒤 다른 assistant 줄이 있어도 SLEEPING). 테스트 없음.

G-10: L-01~L-07 각 ≥ 1 확인. 빠진 경계는 DEF-QA2-007.

---

## 3. G-17 · G-18 · G-21 브라우저 (Claude in Chrome, 새 탭 하나만 사용)

| 화면 | 확인 | 앱 콘솔 오류 | 스크린샷 |
|---|---|---|---|
| D-01 `/` | 카드 7 (실행 2 · 입력 대기 2 · 권한 0 · 잠듦 0 · 자식 대기 1 · 멈춤 의심 8 · 오늘 끝남 6 "실패 0") · 내 차례 2 · 살아 있는 13 · "실시간: 연결됨" | 0 (확장 `chrome-extension://nkbih…` 경고 6 — MaxListeners · ObjectMultiplex, 앱 아님) | `e2e/d01-dashboard.jpg` |
| D-02 `/graph` 계층 | 노드 35 (에이전트 26/323) · 엣지 31 · 첫 그림 45 ms · 이 프로젝트 묶음에 세션 + 자식 7 (초록 2 = QA1 · QA2) | 0 | `e2e/d02-tree-24h.jpg` |
| D-02 노드 클릭 | 오른쪽 패널: 상태 R-04 근거 · 종류 · 부모 · 자식 직계 7 · 출력 토큰 · [추정] 비용 | 0 | `e2e/d02-node-panel.jpg` |
| D-02 더블클릭 → D-03 | 머리 · 판정(저장/지금) · 직계 자식 7 표 · 상태 이력 · 작성 파일 | 0 | `e2e/d03-detail-session.jpg` |
| D-03 "원본 보기" | 버튼 → `<details>` 200 개, 펼친 것 0 (접힌 상태) | 0 | `e2e/d03-raw-view-folded.jpg` |
| D-02 협업 · 파이프라인 | 첫 그림 51 · 54 ms | 0 | `e2e/d02-collab.jpg` · `e2e/d02-pipeline-view.jpg` |
| D-02 기간 전체 | 접기 전 359 > 300 → 노드 125 · 접힘 234 · API 라벨 "+N" 19 개 (+50 · +24 · +17 …) · 첫 그림 67 ms | 0 | `e2e/d02-tree-all-folded.jpg` |
| D-02 필터 상태=멈춤 의심 | 에이전트 14 (STALE 8 + 맥락 부모) | 0 | `e2e/d02-filter-stale.jpg` |
| D-04 `/usage` | `[추정] API 정가 환산` 표기 · 단가 없음 0 건 | 0 | `e2e/d04-usage.jpg` |
| D-05 `/timeline` | 에이전트 12 · state_log 13 · 동시 실행 최대 7 | 0 | `e2e/d05-timeline.jpg` |
| D-06 `/pipeline` | 칸 88 · 완료 53 · 판단 필요 2 · 규칙 없음 33 | 0 | `e2e/d06-pipeline.jpg` |

콘솔은 `read_console_messages`(pattern = 확장 URL 제외 · onlyErrors) 로 화면마다 읽고 비웠다. 확장 경고는 D-01 첫 로드에만 6 건(전부 `chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/scripts/contentscript.js`).

**390px**: `resize_window(390, 844)` 성공 응답에도 창이 1352 그대로(`innerWidth` 1352) — 브라우저가 최소 폭을 막음. 대안: 같은 출처 iframe `width:390px` 에 각 화면을 띄워 `documentElement.scrollWidth` vs `clientWidth` 측정.

| 화면 | clientWidth | scrollWidth | 가로 스크롤 | 넘치는 요소 |
|---|---|---|---|---|
| `/` | 375 | 375 | 0 | 표(381 px) — 자기 상자 안에서만 넘침 |
| `/graph` 계층 · 협업 · 파이프라인 | 375 | 375 | 0 | 없음 |
| `/agents/S:2bee9170…` | 375 | 375 | 0 | 자식 표(408 px) — 상자 안 |
| `/usage` | 375 | 375 | 0 | 표(904 px) — 상자 안 |
| `/timeline` | 390 | 390 | 0 | 없음 |
| `/pipeline` | 375 | 375 | 0 | 표 `.pipe`(954 px) — 상자 안 |

(375 = 390 − 세로 스크롤바 15.) 스크린샷 `e2e/w390-d01.png` · `e2e/w390-d02.png`.

관찰(결함 아님): 파이프라인 보기는 `NN` 이 없는 프로젝트(Multi-agent Dashboard · OneTouch 등)도 열에 끼워 넣는다 — spec §5.3 은 "00 → 08 열 고정" 만 말한다.

---

## 4. 결함

### DEF-QA2-001 — 실패 알림으로 끝난 서브에이전트가 DONE (FAILED 여야 함) · 중대 · 개발2
- 재현: `sqlite3 data/agentdash-qa2.db "SELECT a.state, COUNT(*) FROM edge e JOIN agent a ON a.agent_key=e.src_key WHERE e.kind='handback' AND e.label='notification:failed' GROUP BY 1"` → `DONE|23`. 그중 가장 늦은 반환이 failed 알림인 12 건(원천 대조) 예: `A:a3a79ff5ebee2a7fa` · `A:a5a75228a8eaf44fc` (반환 신호는 failed 알림 하나뿐).
- 실측: 대시보드 DONE R-08 · state_log 근거 "R-08 반환 …". D-01 카드 "오늘 끝남 (실패 0)" · "누적 … 실패 0".
- 기대: FAILED R-08 (spec §4.2 R-08 "결과 is_error 면 FAILED", §4.1 FAILED, D-04 "failed · killed 는 오류"). 전체 12 건.
- 원인: `core/state.py build_ctx` 의 `ctx.return_error` 는 `tool_call.ok=0`(Agent tool_result is_error)만 본다. `linker.returned()` 가 계산한 오류(마지막 신호가 failed/killed 알림)는 `ended_at` 만 남기고 오류 여부는 버려진다.

### DEF-QA2-002 — 다시 깨운 뒤 온 반환 알림을 못 이음 → 끝난 자식이 STALE · 중대 · 개발2
- 재현: `uv run python -I outputs/qa2/notif_ids.py adc075af0bd2072a0 toolu_01U8z6m7EavYzgJhQtUSgRR7` → 알림 4 건: 첫째만 tool-use-id = spawn, 나머지 3 건(09-27T16:44 · 17:57 · 09-28T00:17:39)은 **새 tool-use-id**(SendMessage 호출 id) · task-id = agentId.
- 실측: DB `edge` handback `at=2026-09-27T16:18:14` 하나 · `ended_at` NULL · STALE R-11 (메시지 엣지 16:36 로 다시 깨어난 뒤 반환을 못 봄).
- 기대: DONE R-08 (마지막 알림 00:17:39 > 마지막 활동 00:17:02).
- 원인: `core/linker.py note_notification` 이 `agent.spawn_tool_use = <tool-use-id>` 로만 자식을 찾는다. `<task-id>`(= agentId)로도 찾아야 한다.

### DEF-QA2-003 — DB 경로의 "마지막 활동"이 들어온 메시지를 무시 · 중대 · 개발2
- 재현: `A:a3b3e327f20477922` — 자기 기록 handback 2026-09-18T20:07:22 → tool_result 20:07:24 → **들어온 메시지(user text) 20:23:12** 가 마지막 줄, 그 뒤 응답 없음 · 소속 세션 S1 없음.
- 실측: DONE R-08 (ended_at 20:07:22).
- 기대: D-04 규칙("가장 늦은 종료 신호가 마지막 활동(… 들어온 메시지 줄) 이후면 끝") → 끝 아님 → R-11 STALE. 원천 스캔(`check_link_rate` 의 `scan_projects`)은 `is_activity` 로 들어온 메시지를 세지만, `resolve_all` 은 `SELECT agent_key, MAX(at) FROM tool_call` 만 쓴다(`linker.py` 576 줄 부근) — 같은 규칙의 두 구현이 다르다.

### DEF-QA2-004 — busy · 5 분 무기록 · ScheduleWakeup 미래 · 자식 0 → STALE · 경미 · 개발2 · 사람(spec)
- 재현: `probe_boundaries.py` 6 번째 줄 → STALE R-02b. 실제 오케스트레이터가 지금 이 모양(S1 busy · updatedAt 07:58:10Z · ScheduleWakeup 08:35:38Z)이라 자식이 끝나면 들어선다(관찰 결과는 `self-observe.md`).
- 기대: 잠든 루프는 SLEEPING(spec §4.1 · §13-5). spec R-03 은 `idle` 만 말하고 D-14 는 S1 busy 가 턴 뒤에도 남는다고 확인했다 → D-14 대안 규칙을 예약 시각까지 넓힐지 사람이 정한다.

### DEF-QA2-005 — S1 있음 · busy · pid 소멸 판정 · 경미 · 사람(spec) · 개발2
- 실측: 구현은 pid 소멸을 "S1 없음" 으로 보고 R-06/R-07. 5 분 안이면 spec 규칙 없음, 5 분 뒤면 spec R-02b 글자는 STALE.
- 기대: spec 이 정할 일 — 결정 대장(D-nn)에 해석을 남기고 테스트 행 추가. 지금 실제 S1 3 개는 모두 pid 살아 있어 영향 0.

### DEF-QA2-006 — G-09 테스트 빈 경계 · 경미 · 개발2
`tests/test_state.py` 에 없는 것: (a) DB 경로에서 failed/killed 알림 → FAILED (001 을 못 잡은 이유) (b) busy + 예약 미래 + 자식 0 (004) (c) busy + pid 소멸 (pending 없는 경우, 005) (d) STALE 자식만 남은 부모의 R-04 · R-10 (e) 90 · 300 초 정각 (f) `build_ctx` 의 ScheduleWakeup "마지막 assistant" 조건.

### DEF-QA2-007 — G-10 테스트 빈 경계 + L-06 비교 오류 · 경미 · 개발2
- (a) 다시 깨운 뒤 새 tool-use-id 알림(002) 테스트 없음 (b) 반환 뒤 들어온 메시지만 있고 응답 없음(003) 을 DB 경로로 확인하는 테스트 없음.
- (c) `linker.resolve_message` 206 줄: `raw[2:] in agent_ids | set(names.values())` — `names.values()` 는 `"S:<id>"` 꼴 키라 `raw[2:]`(접두 없는 id)와 같을 수 없다 → `to="S:<sessionId>"` 는 세션이 있어도 외부 노드. 테스트는 접두 없는 이름 · agentId 만 본다.

### DEF-QA2-008 — gate.py 가 QA 리포트 안의 모든 판정 꼴 줄을 읽음 · 경미 · 아키텍트
- `gate.py` `_ROW = ^\s*(G-\d{2})\s+(.*?)\s{2,}(PASS|FAIL|…)` 를 리포트 전체에 적용하고 `combine` 이 가장 나쁜 판정을 고른다. 리포트에 `make gate` 출력(예: `G-12 … 미검증 …`)을 원문 그대로 붙이면 그 옛 판정이 QA 판정과 섞인다(PASS + 미검증 → 미검증). 이 리포트는 판정표를 `|` 표로 붙여 피했다. 제안: QA 리포트에서는 "게이트 판정 행" 같은 지정 구역만 읽기.

---

## 5. `make gate` 판정표

아래 §5.1 에 붙인다 (gate.py 가 다시 읽지 않도록 `|` 표 꼴).

### 5.1 판정표 — make gate — 2026-10-17 17:31:44 (goal.md §2) (기본 DB `data/agentdash.db`, 8095 에 QA2 서버가 떠 있는 상태)

| 게이트 | 항목 | 판정 | 실측 (앞 220 자) |
|---|---|---|---|
| G-01 | 골격 — make setup · 테이블 11 | PASS | tests/test_schema.py: 5 passed in 0.02s ‖ agentdash.db 테이블 11 |
| G-02 | 파서 회귀 — 픽스처 S1~S6 · S9 (V-08) | PASS | tests/test_parsers.py: 29 passed in 0.17s |
| G-03 | 증분 읽기 — 추가분 · 반쪽 줄 · inode | PASS | tests/test_tail.py: 9 passed in 0.06s |
| G-04 | 전체 수집 — agent 행 = 원천 파일 수 (V-01) | PASS | 원천 77 · DB 77 · 빠짐 0 · 남음 0 (17:31:07 · 직전 증분 수집 바뀐 키 4) ‖ 원천 241 · DB 241 · 빠짐 0 · 남음 0 (17:31:07 · 직전 증분 수집 바뀐 키 4) ‖ 원천 6 · DB 6 · 빠짐 0 · 남음 0 (17:31:07 · 직전 증분 수집 바뀐 키 4) |
| G-05 | 파싱 오류율 ≤ 0.1% (V-07) | PASS | 오류 0 / 줄 163525 = 0.0000% (상한 0.1%) · 파일 576 |
| G-06 | 부모 연결 ≥ 95% (V-02) | PASS | 원천 서브에이전트+워크플로 에이전트 247 중 연결 247 = 100.0% · L-01=229 L-02=12 L-03=6 · 워크플로 노드 1 중 1 · 줄 163261 · 2.0s ‖ agentdash.db 서브에이전트 241 · 워크플로 에이전트 6 중 부모 있음 247 = 100.0% (기준 ≥ 95%) · 부모 미확인 0 · 워크플로 노드 1 중 1 |
| G-07 | 토큰 합 — 표본 10 세션 (V-03) | PASS | 원천 출력 1553522 · DB 1553522 · 입력 11598/11598 · 캐시읽기 1237354145/1237354145 · 캐시쓰기 20468291/20468291 · 자기+자손 = · 에이전트 65 · 파일 65 · 세션 안 requestId 중복 0 ‖ 원천 출력 2126284 · DB 2126284 · 입력 44386/44386 · 캐시읽기 830382477/830382477 |
| G-08 | 비용 — 표본 20 건 손계산 (V-09) | PASS | 일치 20/20 · 손계산 합 $2.661726 · 단가표 2026-10-06 · 표본 종류 1h,5m,claude-fable-5-1,claude-opus-4-8,claude-opus-5,claude-opus-5-5,claude-sonnet-5,speed 없음(옛 기록),무작위 · 기록에 speed=fast 0 건 (fast 는 tests/test_cost.py 로) ‖ 없음 (0 건) ·  |
| G-09 | 판정 규칙 13 — 표 기반 테스트 | PASS | tests/test_state.py: 39 passed in 0.12s |
| G-10 | 연결 규칙 L-01~L-07 테스트 | PASS | tests/test_linker.py: 17 passed in 0.13s |
| G-11 | 실시간 — SSE 5 초 · 훅 1 초 | PASS | tests/test_realtime.py: 4 passed in 12.06s |
| G-12 | 상태 대조 — 표본 30 오판 ≤ 2 | FAIL | 표본 30 (STALE 8 · RUNNING 3 · WAITING_INPUT 2 · 실패 신호 6 · 끝남 11) 일치 27 · 오판 3 (R-08 failed→DONE 2 · L-07 재기상 알림 STALE 1) · 전체 322 대조 오판 14 — DEF-QA2-001·002·003 |
| G-13 | 본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04) | PASS | agentdash.db 테이블 11 · 행 62416 · TEXT 값 349591 · 상한 300 자 · 위반 0 ‖ 파일 23 · 줄 1284 · 문자열 42330 (그중 <redacted> 17576) · 위반 0 |
| G-14 | 원천 무접촉 — 정적 + 읽기 전용 pytest (V-05) | PASS | 파일 54 · 쓰기 호출 55 곳 · 원천 경로 대상 0 ‖ 읽기 전용 가짜 루트(파일 23) · pytest 198 passed in 15.70s · 트리 변경 0 · 15.9s |
| G-15 | 훅 설치 안전 — 가짜 settings (V-10) | 미검증 | 가짜 settings (기존 이벤트 3) · 덧붙임 9 · 송신 미검증 (8095 사용 중) · 위반 0 |
| G-16 | 로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06) | PASS | host 127.0.0.1:8095 · 스캔 py 54 · 기타 15 · 외부 전송/바인드 위반 0 |
| G-17 | 화면 6 · API 10 — HTTP 200 | PASS | 화면 6 + API 10 = 16 중 HTTP 200 16 (빈 DB) · placeholder 0 |
| G-18 | 구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3 | PASS | tests/test_graph.py: 6 passed in 0.23s ‖ 실제 DB 노드 359→125 접힘 234 · "+N" 19 · 보기 3 첫 그림 45/51/54 ms · 필터 state=STALE · 노드 클릭 패널 · 더블클릭 D-03 · 앱 콘솔 오류 0 |
| G-19 | 진척 판정 — P-01~P-07 · 고려솔더 (V-11) | PASS | 칸 88/88 · 근거(src) 없는 칸 0 · 원천 AI Coding/ 읽기만 ‖ 표본 10 일치 10 · 고려솔더/01 3/3 · 고려솔더/02 5/5 · 엘컴화인/00 5/5 · 와이엔프린팅/02 5/5 · 평창꽃순이김치/01 3/3 · 엘컴화인/01 3/3 · 평창꽃순이김치/04 7/7 · 엘컴화인/04 7/7 · 와이엔프린팅/04 7/7 · 광성정밀/04 7/7 ‖ 01 DONE v |
| G-20 | 비용 화면 — [추정] 표기 · 단가 없음 · reprice | PASS | tests/test_usage_page.py: 7 passed in 0.35s |
| G-21 | 브라우저 — 콘솔 오류 0 · 390px | PASS | D-01~D-06 + D-03 + 원본 보기 앱 콘솔 오류 0 (확장 경고 6 별도) · 390px iframe 8 화면 scrollWidth = clientWidth (가로 스크롤 0) · 창 390 조절은 브라우저가 막음 |
| G-22 | 자기 관찰 — 루프 서브에이전트 RUNNING → DONE | PASS | QA1 A:a85b98ff · QA2 A:aa798b51 이 세션 S:2bee9170 아래 spawn 엣지 · RUNNING R-09 (08:06:51Z) → QA1 handback 08:29:23.312Z → DONE R-08 state_log 08:29:23Z (< 1 초) · 이전 웨이브 5 DONE R-08 · 파일 감시만 |

합계 PASS 20 · FAIL 1 · WARN 0 · BLOCKED 0 · 미검증 1

- G-15 의 `미검증` 은 `check_hooks` 의 송신 검사가 "서버 꺼짐" 조건을 8095 로 재는데 QA2 서버가 8095 를 쓰고 있어서다 — 덧붙임 9 · 위반 0 은 그대로. 서버를 끈 뒤 오케스트레이터가 다시 잴 것(개발2/QA1 범위, 결함으로 올리지 않음). 웨이브 C 는 서버를 띄우라는 지시와 이 검사가 충돌한다는 메모.
- G-12 FAIL 은 이 리포트 판정(오판 3 > 2). 다른 QA2 게이트는 PASS.
