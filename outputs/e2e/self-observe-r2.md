# G-22 자기 관찰 r2 — QA2 재검증 (2026-10-17, 커밋 8606bc8 · 훅 미설치 · 파일 감시만)

서버: `data/agentdash-qa2.db` 삭제 → `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (uv 35076 · python 35084). **기동 09:01:56Z** · startup complete(백필 끝 · 감시기 · 10 초 판정 시작) 09:02:00~01Z.
관찰 도구: `outputs/qa2/observe_r2.py` — `GET /api/v1/agents?project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` 를 **2 초**마다 읽어 바뀐 줄만 `outputs/e2e/observe-transitions-r2.log` (KST). 정밀 시각은 `state_log.at` · `edge.at` (UTC). 원천 시각은 `stat` mtime · 기록 timestamp (읽기만).
**gate 메모**: `gate.py` 67 줄은 `outputs/e2e/self-observe.md` 만 읽는다 — 이 파일은 지시대로 새 파일 (DEF-QA2-101).

<!-- gate:G-22 -->
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE  PASS  서버 기동 09:01:56Z 뒤 QA1 A:aa6e2ae7 · QA2 A:a6b4391e RUNNING R-09 09:02:00Z (spawn 엣지 S:2bee9170) → QA1 handback 09:12:08.811Z → DONE R-08 09:12:09Z (< 1 초) · 오케스트레이터 SLEEPING R-03 깰 시각 09:30:46Z (09:06:05Z) → RUNNING 09:12:09Z · 기동 뒤 새 에이전트 A:a5b119ea meta 09:12:40.397Z → RUNNING 09:12:40Z (< 1 초) · 파일 감시만

## 1. 시각 기록

| 시각 (UTC) | 사건 (원천) | 대시보드 | 근거 |
|---|---|---|---|
| 09:00:46.651 / .661 | QA1 `A:aa6e2ae766643ef2c` · QA2 `A:a6b4391e741b5db27` 띄움 (spawn tool_use, meta mtime 18:00 KST) | (서버 아직 안 뜸) | `edge` spawn at · meta mtime |
| 09:01:56 | 서버 기동 (빈 DB) | — | 내 명령 시각 |
| **09:02:00** | 백필 직후 첫 판정 | **QA1 · QA2 RUNNING R-09** (spawn 엣지 ← `S:2bee9170…`) · 오케스트레이터 RUNNING R-02a | `state_log` · 폴러 18:02:11 KST |
| 09:01:03 → **09:06:05** | 오케스트레이터 마지막 기록 09:01:03Z · 가장 늦은 tool_use = ScheduleWakeup (깰 시각 09:30:46Z) · S1 busy · pid 85955 살아 있음 · 미종료 자식 2 | RUNNING → **SLEEPING R-03** "ScheduleWakeup 깰 시각 2026-10-17T09:30:46Z · … (302초 전) · D-18" | `state_log` · D-01 잠듦 카드 1 · D-02 파란 노드 · 패널 · D-03 판정(저장/지금) 에 깰 시각 |
| 09:04:2x~09:06:01 | QA2 (나) 100 초 대기 | RUNNING R-09 → R-12(응답 느림) → R-09 (기록 오자 회복) | 폴러 18:05:59 · 18:06:01 KST |
| **09:12:08.811** | **QA1 `SubagentHandback`** (자식 기록) | QA1 RUNNING → **DONE R-08** 09:12:09Z · ended_at 09:12:08.811Z · handback 엣지 | `state_log` — 원천 → 판정 < 1 초 |
| 09:12:09 | 오케스트레이터에 새 기록 (handback 알림 받음) | SLEEPING → **RUNNING R-02a** | `state_log` |
| **09:12:40.368** | **서버 기동 뒤 새 서브에이전트** `A:a5b119ea75c28d4c9` (Wave D3) spawn · meta mtime 09:12:40.397Z | **RUNNING R-09 09:12:40Z** · spawn 엣지 ← `S:2bee9170…` · 폴러 18:12:42 KST (2 초 주기 안) | `state_log` · `edge` · `stat` |

- 새 에이전트 출현: meta 파일 생성(09:12:40.397Z) → DB · `state_log` RUNNING 09:12:40Z (초 단위 같은 초 → **< 1 초**), API 폴러에 2 초 주기 안에 보임 → **5 초 기준 충족**. 지난 회차에 못 쟀던 항목.
- QA2 자신의 DONE 은 내가 반환한 뒤라 이 파일에 적을 수 없다 (오케스트레이터 확인 몫). `A:a5b119ea…` 의 DONE 도 이 파일을 쓸 때 아직 실행 중이면 아래 §3 에 적는다.

## 2. 화면

| 파일 | 내용 |
|---|---|
| `r2-d01-sleeping.jpg` | D-01 잠듦 SLEEPING 1 · 실행 2 (QA1 · QA2) |
| `r2-d02-tree-24h-sleeping.jpg` · `r2-d02-node-panel-sleeping.jpg` | D-02 오케스트레이터 파란(잠듦) · 패널 "잠듦 R-03 … 깰 시각 2026-10-17T09:30:46Z · D-18" |
| `r2-d03-orchestrator.jpg` | D-03 판정(저장 · 지금) 잠듦 R-03 · 상태 이력 실행 → 잠듦 |
| `r2-g22-qa1-done.jpg` | QA1 회색(DONE) · QA2 초록 · 오케스트레이터 초록 (09:12:2x) |
| `r2-g22-d3-new-running.png` | 이 프로젝트 묶음 — 새 Wave D3 · QA2 초록 2 · 나머지 회색 |

## 3. 한계

- `A:a5b119ea75c28d4c9` (Wave D3) 는 09:18:40Z 까지 RUNNING R-09 (끝나지 않음) — 그 DONE 전이는 이 회차에 못 봤다. 서버를 끈 뒤라 오케스트레이터가 다음 회전에 확인.
- 관찰 중 전이는 모두 서버의 감시기 · 10 초 판정이 만든 것 (재백필 아님). 훅 미설치.
- 오케스트레이터 SLEEPING 은 D-18 (가설) 적용 결과 — spec 글자로는 STALE R-02b (`qa2-상태대조-r2.md` §2.2 #15).
