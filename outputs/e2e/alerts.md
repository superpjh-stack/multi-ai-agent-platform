# G-29 WAITING 알림 — 브라우저 E2E (QA2 r4, 2026-10-21, 커밋 8c75bd1)

> 정본: `spec.md` v0.3 §7.2. 구현: `src/agentdash/app/templates/_alerts.html` (개발2). **고치지 않았다.**
> 환경: 가짜 루트 `data/qa2-fake/` (저장소 안 — `outputs/qa2/make_fake_r4.py` 로 만듦: 프로젝트 `-tmp-qa2-alert-proj`, 세션 2 개 `S:bbbbbbbb-…-0001` (S1 idle) · `S:bbbbbbbb-…-0002` (S1 busy), S1 pid = 내가 띄운 `sleep 7200`), 새 DB `data/agentdash-qa2-alerts.db`, 서버 `AGENTDASH_CLAUDE_HOME=data/qa2-fake/claude_home AGENTDASH_AGENTS_ROOT=data/qa2-fake/agents_root AGENTDASH_DB=data/agentdash-qa2-alerts.db AGENTDASH_PORT=8097 uv run python -m agentdash.app` (uv 6524 / python 6526, 01:54:50Z ~ 01:57:20Z). 훅 = `curl -X POST http://127.0.0.1:8097/hooks/event` (실제 `~/.claude/settings.json` 에 설치 0).
> 브라우저: Claude in Chrome, 새 탭 A(`/` → 뒤에 D-03) · 탭 B(`/graph` → 뒤에 D-07). 시작 전에 이 출처의 `agentdash.alerts` · `agentdash.seen` · `agentdash-theme` localStorage 를 지움(개발2 시험 잔재 `agentdash.alerts=on` 이 있었음). 대화상자(alert/confirm) 0.
> **Notification 계측 방법**: 실제 권한 창을 띄우지 않으려고(세션 멈춤 위험), 각 탭이 로드된 뒤 `javascript_tool` 로 `window.Notification` 을 기록용 가짜 클래스로 바꿨다 — `new Notification(title, {body, tag})` 를 `window.__notes` 에 쌓고, `permission` 은 `granted`(권한 거부 단계에서만 `default` → 가짜 `requestPermission()` 이 `denied`). `_alerts.html` 은 `Notification` 을 호출 시점에 전역에서 읽으므로(`perm()` · `new Notification`) 가짜가 그대로 쓰인다. 가짜는 로드 **뒤**에 넣으므로 「첫 로드 0」 은 `agentdashAlerts.notified` · `events` · 가짜 기록 0 으로 셌다(첫 로드 동기화 `sync()` 는 원래 알리지 않는 경로).
> **실제 OS 알림 표시 · 실제 권한 창은 사람이 확인한다** (D-01 머리글 「알림 켜기」 → 브라우저 권한 허용 → 다른 세션을 입력 대기로 만들기).

<!-- gate:G-29 -->
G-29  알림 — 첫 로드 0 · 전이 1 · 재수신 0 · 새로고침 0 · 두 탭 1 · 거부 시 배지만  PASS  r4 가짜 루트 훅 POST: 첫 로드 0 · WAITING_PERMISSION 전이 1 · WAITING_INPUT 전이 1 · 같은 전이 재수신(서버 changed:false + SSE 중복 주입) 0 · 새로고침 0 · 두 탭 합 1/1 · 거부 → 「알림 불가 — 배지만」 알림 0 · 제목 (N) 1→2→1→2→없음 · RUNNING/DONE 전이 0 · 탭당 SSE 1 · 콘솔 오류 0 (Notification 은 기록용 가짜 — 실제 OS 알림은 사람 확인)

## 1. 결과표

| # | 단계 | 조작 | 기대 (spec §7.2) | 탭 A | 탭 B | 판정 |
|---|---|---|---|---|---|---|
| 1 | 첫 로드 | 세션 1 이 이미 WAITING_INPUT 인 채 A `/` · B `/graph` 열기 | 알림 0 · 배지 `(1)` | 제목 `(1) 관제판 …` · waiting {세션 1} · notified 0 · events 0 · 가짜 기록 0 · `leader` true · `mode` locks | 제목 `(1) 네트워크 구성도 …` · notified 0 · events 0 · `leader` false | PASS |
| 2 | 탭당 SSE | 서버(python 6526) ESTABLISHED 세기 | 탭 2 → 2 | `subscribers()` 1 | `subscribers()` 1 | PASS — 서버 쪽 ESTABLISHED **2** (3 초 간격 3 번 2 · 한 번 3 은 fetch keep-alive 순간값), D-03 · D-07 로 옮긴 뒤도 2 |
| 3 | 전이 1 | 세션 2 `Notification` `permission_prompt` → 서버 `state WAITING_PERMISSION · R-01 · changed:true` (01:55:14.423Z) | 리더 탭만 알림 1 · 제목 「권한 대기」 · 본문 프로젝트 · 이름 · tag `key\|since` | 알림 **1** (01:55:14.453Z, POST 뒤 30 ms) — 제목 「권한 대기」 · 본문 `qa2-alert-proj · qa2-alert-2` · tag `S:bbbbbbbb-…-0002\|2026-10-21T01:55:14Z` · 제목 `(2)` | 알림 0 · 제목 `(2)` · seen 에 같은 키(채널 공유) | PASS |
| 4 | 같은 전이 재수신 ① | 같은 훅 다시 POST | 알림 0 | 서버 `changed:false` → SSE 이벤트 0 · 알림 추가 0 | 0 | PASS |
| 5 | 같은 전이 재수신 ② | 리더 탭 A 의 공유 EventSource(`agentdashAlerts.stream`)에 같은 `agent.state` (세션 2 · WAITING_PERMISSION) 를 한 번 더 dispatch | `(agent_key, state_since)` 한 번 | events 1→2 · skipped 0→1 · 알림 1 그대로 | 0 | PASS |
| 6 | 새로고침 | 리더 탭 A 새로고침 (가짜 다시 넣음) | 알림 0 · 리더 넘어감 | 알림 0 · events 0 · 제목 `(2)` · `leader` false | `leader` **true** (Web Locks 넘겨받음) · 알림 0 | PASS |
| 7 | RUNNING 전이 | 세션 1 `UserPromptSubmit` (→ RUNNING changed:true) · `PreToolUse` · `PostToolUse` | 알림 0 · 배지 −1 | 알림 0 · 제목 `(1)` | 알림 0 · 제목 `(1)` | PASS |
| 8 | 두 탭 합 1 | 세션 1 `Notification` `idle_prompt` → WAITING_INPUT changed:true | 리더(B) 만 1 | 알림 **0** · 제목 `(2)` | 알림 **1** — 「입력 대기」 · `qa2-alert-proj · qa2-alert-1` · tag `S:bbbbbbbb-…-0001\|2026-10-21T01:56:02Z` | PASS (합 1) |
| 9 | 권한 거부 | 리더 B: 가짜 `permission=default` · `requestPermission()`→`denied` · `agentdash.alerts=off` 로 두고 머리글 「알림 켜기」 버튼을 **실제 클릭** | 버튼에 사실 표시 · 배지만 | — | 버튼 「알림 불가 — 배지만」 · disabled · `perm()` denied · `enabled()` false · requestPermission 호출 1 (`qa2-r4/g29-denied-button.png`) | PASS |
| 10 | 거부 뒤 전이 | 세션 2 `UserPromptSubmit` → `permission_prompt` (WAITING_PERMISSION changed:true) | 알림 0 · 배지 증가 | 알림 0 · 제목 `(2)` | 알림 0 (누적 1 그대로) · 제목 `(1)`→`(2)` · 파비콘 data URL(점 = 권한 대기 주황) | PASS |
| 11 | 다른 전이 0 · 배지 꺼짐 | B 권한 다시 granted · alerts on 으로 되돌린 뒤 세션 2 `SessionEnd` (DONE) · 세션 1 `UserPromptSubmit` (RUNNING) | 알림 0 · 대기 0 이면 접두 없음 | 알림 0 · 제목 `관제판 · 에이전트 대시보드` · waiting 0 | 알림 0 (누적 1) · 제목 `네트워크 구성도 · 에이전트 대시보드` · waiting 0 | PASS |
| 12 | 콘솔 | 두 탭 `read_console_messages onlyErrors` | 0 | 0 | 0 | PASS |

알림 합계: 전이 WAITING 3 번(권한 대기 · 입력 대기 · 거부 뒤 권한 대기) → 알림 2 (거부 상태 1 번은 배지만) · 두 탭 합 매번 ≤ 1 · RUNNING 3 · DONE 1 전이 → 0 · 첫 로드 · 새로고침 · 재수신 → 0.
`window.agentdashAlerts` 읽기 가능: `{waiting, seen, states, leader, mode, ready, notified, skipped, events, perm(), enabled(), stream, subscribe, subscribers()}`.

## 2. 근거 숫자

- 훅 응답(순서대로): permission_prompt `changed:true` · 같은 것 `changed:false` · UserPromptSubmit `changed:true` · PreToolUse / PostToolUse `changed:false` (RUNNING 유지) · idle_prompt `changed:true` · (거부 뒤) UserPromptSubmit · permission_prompt `changed:true` · SessionEnd `DONE changed:true` · UserPromptSubmit `changed:true`.
- `hook_event` 10 행, `detail` 최대 67 자 (≤ 300) — 메시지 앞부분 · 경로만. 프롬프트 본문 없음(보내지도 않음).
- 지연: POST 01:55:14.423Z → 알림 생성 01:55:14.453Z (30 ms ≤ 1 초).

## 3. 범위 밖 · 사람 확인

- 실제 `Notification.requestPermission()` 권한 창 · OS 알림 센터 표시 · 알림 클릭 → D-03 이동: **사람이 확인** (goal.md §4.4 「사람이 할 일 ② D-01 에서 「알림 켜기」」).
- 훅 실설치 상태의 권한 대기 알림 실측은 goal §2.3 범위 밖 — 여기서는 가짜 루트 훅 POST 로.

## 4. 정리

가짜 서버 6524/6526 · `sleep` pid kill → 8097 LISTEN 0 (그 뒤 실제 DB 서버를 G-22 용으로 다시 띄움 — self-observe-r4). 탭 2 개 닫음. `data/qa2-fake/` · `data/agentdash-qa2-alerts.db` 는 저장소 `data/` (git 제외).
