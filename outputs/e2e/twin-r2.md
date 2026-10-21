# QA2 r6 — D-01 공장 평면도 E2E 재검증 (G-33 · G-34 · G-35, 2026-10-21, 웨이브 D 뒤 커밋 8ea4562, spec v0.4.1)

> **고치지 않았다** — 코드 · 테스트 · 설정 · 정본 · progress 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/self-observe-r8.md` · `outputs/e2e/qa2-r6/`(스크린샷 7) · `outputs/qa2/`(새 이름: `twin_driver_r6.py` · `serve_fake_budget_r6.py` · `elapsed_r6.py` · `*-r6*` 결과 · 서버 로그) · `data/agentdash-qa2.db`(지우고 처음부터 새 백필) · `data/agentdash-qa2-twin-fake-r6.db` · `data/qa2-fake-twin-r6/`.
> 원천은 읽기만. 훅 설치 0 — 훅 이벤트는 가짜 루트 서버에 `curl -X POST http://127.0.0.1:8097/hooks/event`. 본문 없음(가짜 사용자 줄 자리표 `x`, 도구 입력 `{}`). 실제 `config/budget.yaml` 은 읽지도 쓰지도 않음 — 가짜 한도는 `serve_fake_budget_r6.py` 프로세스 안에서만(`outputs/qa2/fake-budget-r6.json`, 측정 뒤 지움).
> 서버는 8097 만, 내가 띄운 PID 만 kill: 실제 DB 서버 uv 31527 / python 31529 (05:10:15Z ~ 05:16:15Z, 감시기 켬) → 가짜 루트 서버 uv 33172 / python 33174 (05:16:20Z ~ 05:20:50Z, 감시기 켬) · S1 용 `sleep 7200` pid 33171. 끝에 8097 LISTEN 0. 사람 서버 8095 (pid 30962) 는 건드리지 않음 — 끝까지 LISTEN.
> 브라우저: Claude in Chrome 새 탭 1 개(1315153154, 끝에 닫음). **창 크기 조절이 먹지 않음** — `resize_window` 1400 · 1100 요청 뒤에도 안쪽 폭 1448 × 779 그대로. 그래서 실제 창 1448 + 같은 출처 iframe 1400 · 390 · 1100 으로 쟀다. 대화상자 0 · 실제 Notification 권한 창 0 (로드 뒤 기록용 가짜 `Notification` 클래스).

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-33 실시간 | **PASS** | S1 → 세션 설비 2.09 s · transcript → RUNNING 0.26 s · 서브 2 → 1.96 s · 훅 → 표시등 22 ms · 첫 반환 역흐름 1 회 0.21 s → DONE 0.22 s · **두 번째 반환 역흐름 1 회 0.15 s** (DEF-QA2-403 해결) |
| G-34 관제판 흡수 | **PASS** | v0.3 항목 전부 · `test_dashboard.py` 1c33a63..HEAD 커밋 0 · 알림 첫 로드 0 · 전이 4 = 4 · 예산 띠 over/warn/unset |
| G-35 시각 | **PASS** (경미 3) | 7 화면 × 390/1400 × 밝은/다크 28/28 가로 스크롤 0 · reduced-motion 15 → 0 · 실시간 중 최대 0 · Tab → Enter D-03 · 콘솔 오류 0 · 라인 이름 사람이 읽는 이름 |

지난 결함: DEF-QA2-401 **해결 (잔여 1 → DEF-QA2-502)** · 402 **해결** · 403 **해결** · 404 **해결**. 새 결함: 치명 0 · 중대 0 · **경미 3** (DEF-QA2-501 ~ 503).

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-33 -->
G-33  실시간 — 가짜 루트 새 세션 + 서브 2 ≤ 5 초 · 훅 → 표시등 ≤ 1 초 · handback 역흐름 + DONE  PASS  r6 (twin-r2) 가짜 루트 감시기 켬: S1 → 세션 설비 2.09 s · transcript → RUNNING 0.26 s · Agent×2 → 서브 설비 2 1.96 s · spawn 흐름 2 · flowMiss 0 · 훅 permission_prompt → data-state WAITING_PERMISSION 22 ms (다시 칠하기 7.6 ms · 경광등 twin-spin · 「!」) · 첫 반환 burst.rev 1 회 0.21 s → DONE 0.22 s · opacity 0.5 · 다시 깨움 RUNNING 0.23 s → 두 번째 반환 역흐름 정확히 1 회 0.15 s (flows 3→4) · 첫 반환 중복 0 · 자식 2 반환 1 회 (flows 5) · 콘솔 오류 0
<!-- gate:G-34 -->
G-34  관제판 흡수 — v0.3 항목 전부 · test_dashboard 무삭제 · 알림 · 예산 띠  PASS  r6 (twin-r2) 실제 DB 새 백필 D-01: 상태 카드 7 · 내 차례 + cwd/이름 복사 · 살아 있는 목록/선택한 설비 · 오늘 출력·요청·도구 호출·작성 파일 · 상위 5 · 최근 상태 변화 · 파싱 오류 · git log 1c33a63..HEAD -- tests/test_dashboard.py 0 커밋 · test_dashboard+twin_page+twin 71 passed · 전체 453 passed · 알림 첫 로드 0 · 전이 4 = 알림 4 (입력 대기 1 · 권한 대기 3) · 예산 띠(프로세스 안 가짜 한도) over 맨 위 136 px < 평면도 266 px · warn · unset 띠 없음
<!-- gate:G-35 -->
G-35  시각 — 두 테마 · 390/1400 · reduced-motion 0 · 키보드 · 콘솔 0  PASS  r6 (twin-r2) 7 화면 × 390/1400 iframe × 밝은/다크 28/28 scrollWidth=clientWidth · 넘친 요소 0 · D-01 1400 격자 2 열 3 행 · 390 1 열 · 창 폭 바꿈 390→1100 → 1.05 s 뒤 다시 받기 1 회 · reduced-motion 실제 DB 15→0 · 가짜 루트 실시간 동안 최대 0 · burst 0 · flowsReduced 1 · Tab 맞춤→svg→설비 순 · Enter → /agents/A%3Aaf589d60fdce13372 · 콘솔 오류 0 · 테마 토글 redraws +1 · 라인 이름 「contracts」「dev」 0 · 경미 3 (DEF-QA2-501~503)

---

## 1. 지난 결함 재검증

| ID | r5 내용 | r6 실측 | 상태 |
|---|---|---|---|
| DEF-QA2-401 | 새 백필 직후 모든 설비 같은 경과 | 표본 5 손계산 일치(§1.1) — 끝난 설비 「끝남 · n 전」(ended_at) · STALE 「기록 n 전」(last_event_at) · 살아 있는 것은 상태 지속. 단 **ended_at 없는 DONE 1** 은 여전히 백필 경과 「끝남 · 1분 8초」 | **해결** (잔여 → DEF-QA2-502) |
| DEF-QA2-402 | 1400 px 라인 세로로만 · 오른쪽 ≈ 40 % 빈칸 · 첫 화면 라인 1 | 1400 iframe: 격자 2 열 × 3 행 · 첫 화면 라인 4 (온전히 2 · 머리만 2) · 내용 오른쪽 빈칸 1.5 % (첫 행만 26.3 % — 좁은 라인 240 px 이 504 px 열에 있어서) · 390: 1 열 · 가로 스크롤 0 · 폭 바꿈 1 회 다시 받기 | **해결** |
| DEF-QA2-403 | 다시 깨운 뒤 두 번째 반환에 역흐름 없음 | 가짜 루트: 첫 반환 역흐름 1 · 두 번째 반환 역흐름 정확히 1 (flows 3→4) · 첫 반환이 다시 흐르지 않음 · reduced 에서도 정확히 1 (flowsReduced 0→1, burst 0) | **해결** |
| DEF-QA2-404 | 긴 도구 이름 글자 중간 잘림 · DONE 에 마지막 도구 | 가짜 루트 66 자 도구 → 「mcp__claude-in-chrome__java…」 · 글자 오른쪽 끝이 상자 안쪽 여백 안 5.1 px · 실제 DB 의 내 설비도 「mcp__claude-in-chrome__java…」 · 실제 13 설비 상태줄 · 도구 줄 넘침 0 · DONE 설비 도구 줄 "" (실제 3 · 가짜 2) | **해결** |
| O-1 (r5 관찰) | 라인 이름 「contracts」 | 24h 6 라인: Multi-agent Dashboard · lcomFine MES · Standard ML Platform · Standard MES Platform · **SongWol QR Platform** · 00 PM Agent / `since=all` 32 라인에 「contracts」「dev」 0 · D-02 graph 응답에도 0 | **해결** (D-28) |

### 1.1 DEF-QA2-401 표본 5 — DB 값으로 손계산 (`outputs/qa2/elapsed-r6.txt`, 응답 시각 05:10:32Z, 백필 05:10:12Z)

| 설비 | 상태 | DB 근거 시각 | 손계산 | API | 화면 글자 |
|---|---|---|---|---|---|
| `A:adc60434…` (Dev2 웨이브 D) | DONE | ended_at 05:07:31.974Z | 180 s | ended_ago_s 180 | 「끝남 · 3분 34초 전」 (화면 시각 기준) |
| `S:dbd09a2a…` (Standard ML) | STALE | last_event_at 10-14T17:55:19Z | 558,913 s = 6일 11시간 15분 | last_ago_s 558913 | 「멈춤 의심 · 기록 6일 11시…」 (상태줄 말줄임) / aria 「기록 6일 11시간 전」 |
| `A:a2a00291…` (SongWol) | STALE | 09-28T01:23:26Z | 2,000,826 s = 23일 3시간 | 2000826 | 「멈춤 의심 · 기록 23일 3시간 전」 |
| `A:abca160d…` (Standard MES) | STALE | 10-09T03:56:32Z | 1,041,239 s = 12일 1시간 | 1041239 | 「멈춤 의심 · 기록 12일 1시간 전」 |
| `S:fa752590…` (오케스트레이터) | RUNNING | state_since 05:10:12Z | 20 s | elapsed_s 20 | 「실행 · 54초」 (화면 시각 기준, 상태 지속) |

13 설비 전부 API 값 = 손계산 (차 ≤ 1 s, 반올림). 살아 있는 설비 5 (RUNNING 4 · WAITING_INPUT 1) 는 상태 지속이라 백필 직후 서로 같다 — spec 대로(상태가 바뀌면 각자 달라짐: lcomFine 이 「입력 대기 · 1분 56초」 → 「실행 · 15초」 로 바뀌는 것을 실화면에서 봄).

---

## 2. G-33 실시간 (가짜 루트 · 감시기 켬)

환경: `data/qa2-fake-twin-r6/{claude_home,agents_root}` · 새 DB `data/agentdash-qa2-twin-fake-r6.db` · 서버 `AGENTDASH_CLAUDE_HOME=… AGENTDASH_AGENTS_ROOT=… AGENTDASH_DB=data/agentdash-qa2-twin-fake-r6.db AGENTDASH_PORT=8097 uv run python outputs/qa2/serve_fake_budget_r6.py`. 도우미 `outputs/qa2/twin_driver_r6.py` = r5 도우미 + `handback2`(다시 깨운 뒤 두 번째 반환: 자식 SubagentHandback 다시 + 부모 task-notification 다시, 같은 tool-use-id) · `longtool`(결과 없는 66 자 도구). 계측 = `MutationObserver`(설비 첫 등장 · `data-state` · `path.burst` 추가) + `window.agentdashTwin`. 쓰기 시각은 도우미가 쓰기 직후 찍은 시각(`outputs/qa2/driver-r6.log`).

| 단계 | 쓰기 (UTC) | 화면 | 걸린 시간 | 기준 | 판정 |
|---|---|---|---|---|---|
| ① S1 idle | 05:17:03.772 | 세션 설비 등장 WAITING_INPUT · 알림 「입력 대기」 1 | **2.09 s** | ≤ 5 s | PASS |
| ② transcript 첫 줄 + S1 busy | 05:17:11.820 | 세션 RUNNING | **0.26 s** | ≤ 5 s | PASS |
| ③ Agent×2 + 자식 meta · jsonl | 05:17:19.893 | 서브 2 등장 RUNNING · spawn 배관 2 · burst 2 · flowMiss 0 · 입자 2 | **1.96 s** | ≤ 5 s | PASS |
| ④ 훅 permission_prompt POST | 05:17:41.302 | WAITING_PERMISSION · 경광등 `twin-spin` · 「!」 · 내 차례 맨 위 「권한 대기 R-01」 · 알림 「권한 대기」 | **22 ms** (다시 칠하기 7.6 ms) | ≤ 1 s | PASS |
| ⑤ 자식 1 결과 없는 긴 도구 | 05:17:50.279 | 「mcp__claude-in-chrome__java…」 (§1 404) | — | — | PASS |
| ⑥ 자식 1 첫 반환 | 05:18:07.872 | burst.rev 1 (spawn 관 거꾸로) 0.21 s → DONE 0.22 s · opacity 0.5 · 도구 줄 "" · 「끝남 · 15초 전」 · 다시 받은 뒤 handback 배관 | **0.21 s / 0.22 s** | 역흐름 1 → DONE | PASS |
| ⑦ 자식 1 다시 깨움 (활동 1 줄) | 05:18:17.922 | RUNNING (R-09 회복) | 0.23 s | — | — |
| ⑧ 자식 1 **두 번째 반환** | 05:18:25.972 | DONE + burst 1 (handback 관 따라 자식→부모) 같은 ms · flows 3→4 | **0.15 s** | 역흐름 정확히 1 | PASS |
| ⑨ 자식 2 첫 반환 | 05:18:52.967 | burst.rev 1 · DONE · flows 4→5 · 입자 0 | 1.08 s | 역흐름 1 → DONE | PASS |

- 첫 반환 중복 0: ⑥ 뒤 ⑧ 까지 18 s 동안 자식 1 burst 추가 0, 끝까지 `flows` = spawn 2 + 반환 3 = 5 (반환마다 정확히 +1).
- reduced-motion 에서 같은 흐름(⑩ 자식 2 다시 깨움 05:19:18 → 훅 05:19:24 → 두 번째 반환 05:19:27.372 → DONE 05:19:27.590): 50 ms 표본 running 애니메이션 **최대 0** · burst 요소 0 · `flowsReduced` 0→1 · `flows` 5 그대로.
- 스크린샷: `qa2-r6/fake-light-permission-beacon-long-tool.jpg` · `fake-light-budget-over-two-returns-done.jpg` · `fake-dark-budget-over-waiting.jpg`.

---

## 3. G-34 관제판 흡수

| v0.3 항목 | D-01 실제 DB (새 백필, 8097) | 판정 |
|---|---|---|
| 상태 카드 | 실행 · 입력 대기 · 권한 대기 · 잠듦 · 자식 대기 · 멈춤 의심 · 오늘 끝남(실패 n) 7 장 | O |
| 내 차례 + 복사 | 「내 차례 — 권한 대기 먼저…」 · 행마다 「cwd 복사」「이름 복사」 (가짜 루트 · 실제 lcomfine-mes-39) | O |
| 살아 있는 목록 / 선택한 설비 | 둘 다 · Tab 포커스 250 ms 뒤 「선택한 설비」 요약 | O |
| 오늘 출력 · 요청 · 도구 호출 · 작성 파일 | 네 글자 모두 | O |
| 상위 5 · 최근 상태 변화 · 파싱 오류 | 모두 | O |
| 예산 띠 | 아래 | O |

- `git log --oneline 1c33a63..HEAD -- tests/test_dashboard.py` **0 줄**. `uv run pytest -q tests/test_dashboard.py tests/test_twin_page.py tests/test_twin.py` 71 passed · `uv run pytest -q` **453 passed**.
- 알림 (가짜 `Notification`): 첫 로드 `agentdashAlerts.notified` 0 (세션이 WAITING_PERMISSION 인 채 새로고침해도 0) · 전이 4 번(입력 대기 1 · 권한 대기 3) = 알림 4 · RUNNING / DONE 전이 0 건.
- SSE: 서버 로그에서 브라우저 페이지 로드 3 번 각각 뒤에 `/api/v1/stream` 1 (그 밖 2 = 서버 바꿔 띄울 때 열려 있던 페이지의 재연결).
- 예산 띠 (오늘 추정 $0.022555): 전체 일 0.02 + 프로젝트 월 0.0001 → worst over · 띠 「예산 초과 오늘 전체 112 % · qa2-twin-r6 이번 달 22555 % [추정] API 정가 환산 · D-07 비용 · 효율 →」 (href `/insights`) · 띠 top 136 px < 평면도 266 px / 일 0.027 (84 %) → 「예산 경고」 / 파일 지움 → `#budget-band` 0.

## 4. G-35 시각

### 4.1 폭 × 테마 (같은 출처 iframe, 값 = scrollWidth/clientWidth)

| | 390 밝은 | 390 다크 | 1400 밝은 | 1400 다크 |
|---|---|---|---|---|
| D-01 · D-02 · D-03 · D-04 · D-05 · D-06 · D-07 | 375/375 × 7 | 375/375 × 7 | 1385/1385 × 7 | 1385/1385 × 7 |

28/28, 넘친 요소(svg · 표 · sr-only · pre 제외) 0, 창 오류 0. 배경 밝은 rgb(245,246,248) · 다크 rgb(18,19,22). 실제 창 1448 도 1433/1433.

### 4.2 T-08 격자 · D-31 가독성

| 폭 | 카드 | 보낸 width (÷ 0.8) | 격자 | 맞춤 배율 | 첫 화면 라인 | 오른쪽 빈칸 |
|---|---|---|---|---|---|---|
| 실제 창 1448 | 934 | 1168 | 2 열 × 3 행 | 0.88 | 4 (온전히 2) | 내용 끝 1.5 % · 첫 행 26.3 % |
| iframe 1400 (밝은 · 다크) | 900 | 1125 | 2 × 3 | 0.85 | 4 (온전히 2) | 같음 |
| iframe 1100 (390 에서 바꿈) | 690 | 863 | 1 × 6 | — | — | 다시 받기 **1 회 1.05 s** 뒤 |
| iframe 390 (밝은 · 다크) | 307 | 384 | 1 × 6 | 0.57 | 3 (온전히 2) | 3 % |

D-31 가독성 (1400 iframe, 배율 0.85 의 실효 글자 크기): 설비 이름 10.2 px · 상태줄 · 누적 · 분당 9.4 px · 종류 · 지금 도구 8.5 px. 확대 스크린샷에서 이름 · 상태줄 · 누적은 읽힌다. 종류 · 지금 도구(8.5 px) 는 작지만 읽힘 — 「글자 ≈ 9.6 px」 추정과 맞다. 1400 급에서 2 열과 이 크기의 맞바꿈은 받아들일 만하다(판정: 가독 가능, 사람 확인은 D-31 그대로). **390 은 배율 0.57 → 실효 5.7 ~ 7.5 px 로 확대 없이 못 읽는다** (DEF-QA2-503).

### 4.3 reduced-motion · 키보드 · 콘솔 · 테마

- reduced-motion (앱의 `@media (prefers-reduced-motion: reduce)` 블록 규칙 3 개를 조건 없이 주입 + `matchMedia` reduce 참): 실제 DB `#twin-svg` running 애니메이션 **15 → 0** · 전이 0 / 가짜 루트 실시간(§2) 최대 0.
- 키보드 (실제 키): 「맞춤」 → Tab → svg(`role=group`, aria-label 「공장 평면도 — 라인 = 프로젝트 · 설비 = 에이전트 · 배관 = 띄움/반환」) → 세션 `S:fa752590` (role=button · tabindex 0 · aria-label 「…, 실행, 경과 3분 19초, 접힌 완료 13」 · 화면 안 · 250 ms 뒤 선택한 설비) → 서브 … → 나 `A:af589d60` → Enter → `/agents/A%3Aaf589d60fdce13372` 「QA2 2T r6 re-verify · 상세」. 포커스 테두리 파랑 (`qa2-r6/real-light-keyboard-focus-g22-running.jpg`).
- 콘솔: 가짜 루트 새로고침 · 테마 토글 · 실시간 동안 오류 0. 테마 토글 → `data-theme=dark` · `redraws` +1 · 배경 rgb(18,19,22).

---

## 5. 새 결함

| ID | 심각도 | 내용 | 재현 · 근거 | 담당 제안 |
|---|---|---|---|---|
| DEF-QA2-501 | 경미 | 설비 **이름**이 24 자 clipPath 에서 글자 중간에 잘린다(「…」 없음) — 404 에서 도구 줄은 고쳤지만 이름 줄은 같은 문제. 「multi-agent-dashboard-b6」 → 「multi-agent-dashboard-b」 + 반쯤 잘린 「6」. | 실제 DB 1448 · 390 의 `S:fa752590` 상자 (`qa2-r6/real-light-1448-first.jpg`, 확대해 봄). 24 자 이하 이름도 머리띠 폭(오른쪽 「!」 자리)보다 길면 잘림 | 개발2 (이름도 `fitText` 로 「…」) |
| DEF-QA2-502 | 경미 | DEF-QA2-401 잔여 — **ended_at 이 없는 DONE** 은 새 백필 직후 「끝남 · 1분 8초」(백필 뒤 흐른 시간, 「전」 없음)로 보여 방금 끝난 것처럼 읽힌다. last_event_at 은 있다. | 실제 DB `S:fc3908a3…` (00 PM Agent) DONE · ended_at NULL · last_event_at 03:14:48Z (1시간 56분 전) · state_since 05:10:12Z (백필) → 화면 「끝남 · 1분 8초」 | 개발2 (D-31 「지어내지 않음」 유지하되 「끝남 · 기록 n 전」 으로 last_event_at 기준 표기 — 사람 확인) |
| DEF-QA2-503 | 경미 | 390 px 에서 평면도 맞춤 배율 0.57 → 설비 글자 실효 5.7 ~ 7.5 px, 확대(＋) 없이는 못 읽는다. D-31 의 0.8 하한은 넓은 화면 격자에만 적용. 가로 스크롤 · 겹침은 없음. | iframe 390 밝은 · 다크: 카드 307 px · 라인 504 px · `scale` 0.57 · 상태줄 높이 7.5 px (`qa2-r6/real-light-390-iframe-small-text.jpg`) | 개발2 · 사람 (좁은 화면은 배율 ≥ 0.8 에서 위부터 · 가로는 평면도 안 이동으로) |

관찰 (결함 아님):
- O-1 실제 창 크기 조절이 확장 도구로 안 됨(1448 고정) — 1400 · 390 · 1100 은 같은 출처 iframe 으로 잼(개발2 와 같은 방식).
- O-2 1448 창 첫 행 오른쪽 26 % 빈칸은 T-08 「열 너비 = 그 열의 가장 넓은 라인」 때문(240 px 라인이 504 px 열에) — 규칙대로.
- O-3 「지금 도구」 는 결과가 아직 없는 도구 호출만(`ok IS NULL`) — 실제 RUNNING 설비가 조회 순간 「지금 도구 없음」 인 것은 정상.
- O-4 숨은 탭 입자 정지는 여전히 정적 계약만(r5 O-4 와 같음).

## 6. 정리 · 안전

- 띄운 PID 만 kill (31527/31529 · 33172/33174 · sleep 33171) → 8097 LISTEN 0. 8095 (pid 30962, 사람) 그대로 LISTEN. 탭 닫음 · `agentdash-theme` 는 light 로 되돌림.
- 원천 쓰기 0 · 훅 설치 0 · 실제 `config/budget.yaml` 변경 0 · `git status` 에 `outputs/` 새 파일 외 변경 0.
- `~/.claude/settings.json` sha1 `8a539108c7d4a2263c92732dbb3b022d99673e04` · mtime 1792556826 — 시작 = 끝 (D-29 기준값과 같음).
