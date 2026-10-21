# QA2 r7 — D-01 공장 평면도 짧은 재검증 (웨이브 D2 · G-33 · G-34 · G-35, 2026-10-21, 커밋 754db54, spec v0.4.1)

> **고치지 않았다** — 코드 · 테스트 · 설정 · 정본 · progress 변경 0. 쓴 곳: 이 파일 · `outputs/e2e/qa2-r7/`(스크린샷 8) · `outputs/qa2/`(새 이름: `twin_driver_r7.py` · `serve_fake_budget_r7.py` · `elapsed_r7.py` · `twin_measure_r7.js` · `*-r7*` 결과 · 서버 로그 · pid) · `data/agentdash-qa2.db`(증분 백필) · `data/agentdash-qa2-twin-fake-r7.db` · `data/qa2-fake-twin-r7/`.
> 원천은 읽기만. 훅 설치 0 — 훅 이벤트는 가짜 루트 서버에 `curl -X POST http://127.0.0.1:8097/hooks/event`. 본문 없음(가짜 사용자 줄 자리표 `x`, 도구 입력 `{}`). 실제 `config/budget.yaml` 은 읽지도 쓰지도 않음 — 가짜 한도는 `serve_fake_budget_r7.py` 프로세스 안에서만(`outputs/qa2/fake-budget-r7.json`, 측정 뒤 지움).
> 서버는 8097 만, 내가 띄운 PID 만 kill: 실제 DB 서버 uv 36528 / python 36533 (05:33:20Z ~ 05:40:26Z, 감시기 켬) → 가짜 루트 서버 uv 37473 / python 37478 (05:40:26Z ~ 05:44:20Z, 감시기 켬) · S1 용 `sleep 7200` (pid 파일 `outputs/qa2/sleep-r7.pid`). 끝에 8097 LISTEN 0. 사람 서버 8095 (pid 36343) 는 건드리지 않음 — 끝까지 LISTEN.
> 브라우저: Claude in Chrome 새 탭 1 개(1315153167, 끝에 닫음). 이번엔 창 안쪽 폭이 **1400** 이라 실제 창 = 1400 측정, 390 은 같은 출처 iframe. 대화상자 0 · 실제 Notification 권한 창 0 (가짜 루트 로드 뒤 기록용 가짜 `Notification` 클래스) · 테마는 끝에 light 로 되돌림.

## 요약

| 게이트 | 판정 | 한 줄 |
|---|---|---|
| G-33 실시간 | **PASS** | S1 → 세션 설비 1.22 s · transcript → RUNNING 0.18 s · 서브 2 → 1.26 s · 훅 → 표시등 21 ms · 첫 반환 역흐름 1 회 0.22 s → DONE 0.23 s · 두 번째 반환 역흐름 정확히 1 회 0.21 s |
| G-34 관제판 흡수 | **PASS** | v0.3 항목 전부 · `test_dashboard.py` 1c33a63..HEAD 커밋 0 · 74 + 456 passed · 알림 첫 로드 0 · 대기 전이 3 = 알림 3 · 예산 띠 over/warn/unset |
| G-35 시각 | **PASS** | 7 화면 × 390/1400 × 밝은/다크 28/28 가로 스크롤 0 · 넘친 요소 0 · reduced-motion 11 → 0 · 가짜 실시간 최대 0 · Tab → Enter D-03 · 콘솔 오류 0 |

지난 결함: DEF-QA2-501 **해결** · 502 **해결** · 503 **해결**. 새 결함: **0** (관찰 2).

## 게이트 판정 행 (gate.py 표지 형식)

<!-- gate:G-33 -->
G-33  실시간 — 가짜 루트 새 세션 + 서브 2 ≤ 5 초 · 훅 → 표시등 ≤ 1 초 · handback 역흐름 + DONE  PASS  r7 (twin-r3) 가짜 루트 감시기 켬: S1 → 세션 설비 1.22 s · transcript → RUNNING 0.18 s · Agent×2 → 서브 설비 2 1.26 s · flows 2 · flowMiss 0 · 훅 permission_prompt → data-state WAITING_PERMISSION 21 ms (다시 칠하기 7.4 ms · 경광등 twin-spin · 「!」) · 첫 반환 burst rev 1 회 0.22 s → DONE 0.23 s · opacity 0.5 · 도구 줄 "" · 다시 깨움 RUNNING 0.15 s → 두 번째 반환 burst 정확히 1 회 0.21 s (flows 3→4) · 자식 2 반환 rev 1 회 (flows 5) · reduced 두 번째 반환 flowsReduced 0→1 · burst 0 · 콘솔 오류 0
<!-- gate:G-34 -->
G-34  관제판 흡수 — v0.3 항목 전부 · test_dashboard 무삭제 · 알림 · 예산 띠  PASS  r7 (twin-r3) 실제 DB 증분 백필 D-01 글자 20 항목 빠짐 0 (상태 카드 7 · 내 차례 · cwd/이름 복사 · 살아 있는 · 선택한 설비 · 출력 · 요청 · 도구 호출 · 작성 파일 · 상위 5 · 최근 상태 변화 · 파싱 오류 · 알림 켜기) · git log 1c33a63..HEAD -- tests/test_dashboard.py 0 커밋 · test_dashboard+twin_page+twin 74 passed · 전체 456 passed · 알림 첫 로드 0 (WAITING_PERMISSION 인 채 새로고침해도 0) · 대기 전이 3 = 알림 3 · 예산 띠(프로세스 안 가짜 한도) over 「예산 초과 … 25310 %」 top 136 px < 평면도 266 px · href /insights · warn 「예산 경고 … 90 %」 · 파일 지움 → 띠 없음
<!-- gate:G-35 -->
G-35  시각 — 두 테마 · 390/1400 · reduced-motion 0 · 키보드 · 콘솔 0  PASS  r7 (twin-r3) 7 화면 × 390/1400 iframe × 밝은/다크 28/28 scrollWidth=clientWidth (375/375 · 1385/1385) · 넘친 요소 0 · 배경 rgb(245,246,248)/rgb(18,19,22) · D-01 390 cols 1 맞춤 0.833 · 1400 cols 2 rows 3 맞춤 0.76 · reduced-motion 실제 DB 11→0 (다시 받은 뒤도 0) · 가짜 실시간 최대 0 (281 표본) · Tab 축소→확대→맞춤→svg(role=group)→설비(role=button tabindex 0) · Enter → /agents/A%3Aa748170fabb688615 · 콘솔 오류 0 · 테마 토글 redraws +1

---

## 1. 지난 결함 재검증 (실제 DB `data/agentdash-qa2.db`, 05:33:12Z 증분 백필 0.9 s · 원천 592 · parse_error 0 · 감시기 켬)

| ID | r6 내용 | r7 실측 | 상태 |
|---|---|---|---|
| DEF-QA2-501 | 이름 줄이 clipPath 에서 글자 중간 잘림 (「…」 없음) | 390 · 1400 × 밝은 · 다크 4 조합 모두 설비 15 중 「…」 4 (`S:fa752590` 22/24 자 「multi-agent-dashboard…」 · `A:a39a8de1` 22/24 · `A:acfbcbea` 23/24 · `A:a2a00291` 22/24) · 이름 글자 오른쪽 끝 ≤ 배지 자리 경계(w − 26 = 182): 최대 179.6 · **넘침 0** · 확대 스크린샷에서 반쯤 잘린 글자 0 | **해결** |
| DEF-QA2-502 / D-33 | ended_at 없는 DONE → 「끝남 · 1분 8초」 (백필 경과) | `S:fc3908a3`(00 PM Agent) DONE · ended_at NULL · last_event_at 03:14:48.158Z · 화면 시각 05:35:12.056Z → 손계산 2:20:24 → 화면 **「끝남 · 기록 2시간 20분 전」** (네 조합 같음 · aria 「경과 기록 2시간 20분 전」) · API `ended_ago_s` null · `last_ago_s` 8319 = 손계산 8320 (05:33:28Z) | **해결** |
| DEF-QA2-503 / D-34 | 390 맞춤 배율 0.57 · 글자 5.7 ~ 7.5 px | 390 iframe 밝은 · 다크: 카드 307 px · 서버 격자 width 384 · **cols 1** · 맞춤 배율 **0.833** (getScreenCTM a = 0.833) · 실효 글자 이름 **10.0 px** · 상태줄 9.2 px · 종류 8.3 px · 페이지 가로 스크롤 0 (375/375) · 휠 세로 300 → viewBox y −16 → 344 · 가로 200 → x −16 → 224 (카드 안 이동, 페이지 scrollX/Y 0 그대로) · 확대 없이 이름 · 상태줄 읽힘 (`qa2-r7/real-light-390-name-ellipsis-zoom.png`) / 1400 (실제 창 + iframe 두 테마): 카드 900 → width 1125 · **cols 2 · rows 3** · 맞춤 0.76 — D-31 동작 그대로(하한 안 걸림) | **해결** |

### 1.1 경과 손계산 (`outputs/qa2/elapsed-r7.txt`, 응답 05:33:28Z) — 15 설비 전부 API = DB 손계산 (차 ≤ 1 s)

| 설비 | 상태 | 근거 | API | 손계산 |
|---|---|---|---|---|
| `S:fc3908a3` (00 PM Agent) | DONE · ended 없음 | last_event_at 03:14:48Z | last_ago_s 8319 | 8320 |
| `A:adc60434` | DONE | ended_at 05:07:31.974Z | ended_ago_s 1556 | 1556 |
| `A:ab83c419` | STALE | last_event_at 05:18:44Z | last_ago_s 883 | 884 |
| `S:dbd09a2a` | STALE | 10-14T17:55:19Z | 560288 | 560289 |
| `S:43970992` (lcomFine) | WAITING_INPUT | state_since 05:33:13Z | elapsed_s 15 | 15 |

---

## 2. G-33 실시간 (가짜 루트 · 감시기 켬)

환경: `data/qa2-fake-twin-r7/{claude_home,agents_root}` · 새 DB `data/agentdash-qa2-twin-fake-r7.db` · `AGENTDASH_CLAUDE_HOME=… AGENTDASH_AGENTS_ROOT=… AGENTDASH_DB=… AGENTDASH_PORT=8097 uv run python outputs/qa2/serve_fake_budget_r7.py`. 도우미 `twin_driver_r7.py` = r6 도우미 이름만 r7. 계측 = `MutationObserver`(설비 첫 등장 · `data-state` · `.burst` 추가) + `window.agentdashTwin`. 쓰기 시각은 `outputs/qa2/driver-r7.log`.

| 단계 | 쓰기 (UTC) | 화면 | 걸린 시간 | 기준 | 판정 |
|---|---|---|---|---|---|
| ① S1 idle | 05:40:54.788 | 세션 설비 등장 WAITING_INPUT · 알림 1 | **1.22 s** | ≤ 5 s | PASS |
| ② transcript 첫 줄 + S1 busy | 05:41:14.727 | 세션 RUNNING | **0.18 s** | ≤ 5 s | PASS |
| ③ Agent×2 + 자식 meta · jsonl | 05:41:24.830 | 서브 2 등장 RUNNING · flows 2 · flowMiss 0 | **1.26 s** | ≤ 5 s | PASS |
| ④ 훅 permission_prompt POST | 05:41:46.985 | WAITING_PERMISSION · 경광등 `twin-spin` · 「!」 · 내 차례 「권한 대기」 · 알림 2 | **21 ms** (다시 칠하기 7.4 ms) | ≤ 1 s | PASS |
| ⑤ 자식 1 첫 반환 | 05:42:12.713 | burst rev 1 (0.22 s) → DONE 0.23 s · opacity 0.5 · 도구 줄 "" · 「끝남 · 1초 전」 · flows 3 | 0.22 / 0.23 s | 역흐름 1 → DONE | PASS |
| ⑥ 자식 1 다시 깨움 | 05:42:21.740 | RUNNING | 0.15 s | — | — |
| ⑦ 자식 1 **두 번째 반환** | 05:42:29.862 | DONE + burst 1 같은 ms · flows 3→4 | **0.21 s** | 역흐름 정확히 1 | PASS |
| ⑧ 자식 2 첫 반환 | 05:42:41.456 | burst rev 1 · DONE 0.14 s · flows 5 | 0.12 / 0.14 s | 역흐름 1 → DONE | PASS |

- 첫 반환 중복 0: ⑤ 뒤 ⑦ 까지 burst 추가 0 (bursts 7 그대로), 끝까지 flows = spawn 2 + 반환 3 = 5.
- reduced-motion (앱 `@media (prefers-reduced-motion: reduce)` 규칙 조건 없이 주입 + `matchMedia` reduce 참): 자식 2 다시 깨움 05:43:17.703 → RUNNING 0.14 s → 두 번째 반환 05:43:30.815 → DONE 0.21 s · 50 ms 표본 281 개 running 애니메이션 **최대 0** · burst 요소 0 · `flowsReduced` 0→1 · flows 5 그대로.
  - 참고: 첫 시도(05:43:02 깨움 · 훅 · 반환을 66 ms 안에 연달아 씀)는 감시기 1 초 묶음에 같이 들어가 자식 2 가 RUNNING 을 거치지 않아 역흐름 없음 — 내 순서 문제(전이가 없으면 흐름도 없음 = 규칙대로)라 위처럼 간격을 두고 다시 잼. 이때도 애니메이션 최대 0.
- 스크린샷: `qa2-r7/fake-dark-permission-beacon.jpg` · `fake-light-two-returns-done-waiting.jpg`.

## 3. G-34 관제판 흡수

- 실제 DB D-01 글자 확인 20 항목 빠짐 0 (상태 카드 7 장 · 내 차례 · cwd 복사 · 이름 복사 · 살아 있는 목록 · 선택한 설비 · 오늘 출력 · 요청 · 도구 호출 · 작성 파일 · 상위 5 · 최근 상태 변화 · 파싱 오류 · 알림 켜기).
- `git log --oneline 1c33a63..HEAD -- tests/test_dashboard.py` **0 줄** · `uv run pytest -q tests/test_dashboard.py tests/test_twin_page.py tests/test_twin.py` **74 passed** · `uv run pytest -q` **456 passed**.
- 알림 (`agentdashAlerts.notified`): 가짜 루트 첫 로드 0 · WAITING_PERMISSION 인 채 새로고침해도 0 · 대기 전이 3 번(입력 대기 1 · 권한 대기 2) = 알림 3 · RUNNING / DONE 전이 0 건.
- 예산 띠 (가짜 한도, 오늘 추정 $0.0253): 일 0.0001 → 「예산 초과 오늘 전체 25310 % [추정] API 정가 환산 · D-07 비용 · 효율 →」 · class st-FAILED · top 136 px < 평면도 266 px · href `/insights` / 일 0.0281 → 「예산 경고 … 90 %」 / 파일 지움 → `#budget-band` 없음.

## 4. G-35 시각

### 4.1 폭 × 테마 (같은 출처 iframe, scrollWidth/clientWidth · 넘친 요소는 svg · 표 · pre · sr-only 제외)

| | 390 밝은 | 390 다크 | 1400 밝은 | 1400 다크 |
|---|---|---|---|---|
| D-01 `/` · D-02 `/graph` · D-03 `/agents/A:af589d60…` · D-04 `/usage` · D-05 `/timeline` · D-06 `/pipeline` · D-07 `/insights` | 375/375 × 7 · 넘침 0 | 375/375 × 7 · 넘침 0 | 1385/1385 × 7 · 넘침 0 | 1385/1385 × 7 · 넘침 0 |

28/28. 실제 창 1400 도 1385/1385 (두 테마).

### 4.2 D-01 배율 · 글자 (D-31 · D-34)

| 폭 | 카드 | 보낸 width | 격자 | 맞춤 배율 | 이름 실효 | 상태줄 실효 | 종류 실효 |
|---|---|---|---|---|---|---|---|
| 390 (밝은 · 다크) | 307 | 384 | 1 × 6 | **0.833** | **10.0 px** | 9.2 px | 8.3 px |
| 1400 (실제 창 · iframe 두 테마) | 900 | 1125 | 2 × 3 | 0.76 | 9.1 px | 8.4 px | 7.6 px |

1400 은 D-31(넓은 화면 폭 맞춤) 그대로 — 하한이 걸리지 않음은 D-34 「좁은 화면만」 대로. 확대 스크린샷(`qa2-r7/real-dark-1400-name-ellipsis-zoom.png`)에서 이름 · 상태줄 · 누적 읽힘.

### 4.3 reduced-motion · 키보드 · 콘솔 · 테마

- reduced-motion: 실제 DB `#twin-svg` running 애니메이션 **11 → 0** · 다시 받은 뒤(reload)도 0 / 가짜 루트 실시간(§2) 최대 0.
- 키보드 (실제 키, 다크): 축소 → 확대 → 맞춤 → svg(`role=group`, aria-label 「공장 평면도 — 라인 = 프로젝트 · 설비 = 에이전트 · 배관 = 띄움/반환」) → `S:fa752590` (role=button · tabindex 0 · 화면 안) → `A:a748170f` → Enter → `/agents/A%3Aa748170fabb688615` 「Dev1 check_twin project scope · 상세」.
- 콘솔 오류 0 (실제 DB 키보드 단계부터 가짜 루트 새로고침 5 번 · 실시간 · 테마 토글 끝까지). 테마 토글 → `data-theme=light` · redraws +1 · 배경 rgb(245,246,248).
- 서버 로그: 가짜 루트 페이지 로드 5 = `/api/v1/stream` 5 · 오류 0 (실제 DB 서버 로그의 ERROR 1 줄은 kill 할 때 열린 SSE 의 「ASGI callable returned without completing response」 — 종료 순간뿐).

---

## 5. 새 결함

없음 (치명 0 · 중대 0 · 경미 0).

관찰 (결함 아님):
- O-1 서버가 이름을 **앞 24 자로 자를 때는 「…」 가 없다** — `core/twin.py` `_name` 의 `[:NAME_MAX]`. 예: 「Dev1 check_twin project scope」 → 「Dev1 check_twin project 」 · 「Dev2 2T wave D defect fi」 처럼 단어 중간에서 「…」 없이 끝남 (24 h 15 설비 중 24 자 꽉 찬 것 8, 그 중 화면 「…」 는 폭 넘친 4 만). spec §7 D-01 「이름 앞 24 자」 그대로라 결함은 아님 — 사람이 원하면 서버 자르기에도 「…」 (개발2, spec 문구 판단 사람).
- O-2 1400 급 실효 글자(이름 9.1 · 종류 7.6 px)는 D-31 폭 맞춤 결과 — 읽히지만 작다. D-31 · D-34 사람 확인 항목 그대로.

## 6. 정리 · 안전

- 띄운 PID 만 kill (36528/36533 · 37473/37478 · sleep) → 8097 LISTEN 0. 8095 (pid 36343, 사람) 그대로 LISTEN · GET 도 안 함.
- 탭 닫음 · `agentdash-theme` light.
- 원천 쓰기 0 · 훅 설치 0 · 실제 `config/budget.yaml` 읽기 · 변경 0 · `git status` 에 `outputs/` 새 파일 외 변경 0.
- `~/.claude/settings.json` sha1 `8a539108c7d4a2263c92732dbb3b022d99673e04` · mtime 1792556826 — 시작 = 끝.
