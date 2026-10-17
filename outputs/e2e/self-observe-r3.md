# G-22 자기 관찰 r3 — QA2 재검증 (2026-10-17, 커밋 4b42f08 · 훅 미설치 · 파일 감시만)

서버: `data/agentdash-qa2.db` 삭제 → `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (uv 41663 · python 41666). **기동 09:30:09Z** · 백필 · 첫 판정 09:30:12Z.
관찰 도구: `outputs/qa2/observe_r3.py` — `GET /api/v1/agents?project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` 를 2 초마다 읽어 바뀐 줄만 `outputs/e2e/observe-transitions-r3.log` (KST). 정밀 시각은 `state_log.at` · `edge.at` · `agent.ended_at` (UTC). 원천은 `stat` · 기록 timestamp 만 (읽기만).

<!-- gate:G-22 -->
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE  PASS  r3 서버 기동 09:30:09Z 뒤 QA1 A:a2384d32 · QA2 A:a850fbc1 RUNNING R-09 09:30:12Z (spawn 엣지 S:2bee9170 09:29:24Z) → QA1 SubagentHandback 09:38:47.492Z → DONE R-08 09:38:47Z (< 1 초, handback 엣지) · 오케스트레이터 SLEEPING R-03 가설 D-18 09:34:41Z → RUNNING 09:38:48Z · 파일 감시만

## 1. 시각 기록

| 시각 (UTC) | 사건 (원천) | 대시보드 | 근거 |
|---|---|---|---|
| 09:29:24.634 / .644 | QA1 `A:a2384d3236592c914` · QA2(나) `A:a850fbc10924baf9b` 띄움 (meta 생성 18:29:24 KST) | (서버 아직 안 뜸) | `edge` spawn at · meta `stat` |
| 09:29:37 | 오케스트레이터 마지막 기록 · 가장 늦은 tool_use = ScheduleWakeup (깰 시각 09:59:24Z) · S1 busy · pid 살아 있음 | — | 판정기 `judge-all-r3.json` |
| 09:30:09 | 서버 기동 (빈 DB) | — | 내 명령 시각 |
| **09:30:12** | 백필 직후 첫 판정 | **QA1 · QA2 RUNNING R-09** (spawn 엣지 ← `S:2bee9170…`) · 오케스트레이터 RUNNING R-02a | `state_log` · 폴러 18:30:16 KST |
| **09:34:41** | 마지막 기록 + 304 초 | 오케스트레이터 RUNNING → **SLEEPING R-03 「가설 D-18」** (깰 시각 09:59:24Z) | `state_log` · D-01 카드 · D-03 (`r3-d01-sleeping-d18.jpg` · `r3-d03-orchestrator-d18.jpg`) |
| 09:38:34~09:38:50 | QA2 (나) 긴 대기 (폴러 18:38:34~18:38:50 KST) | RUNNING R-09 → R-12(응답 느림) → R-09 | 폴러 |
| **09:38:47.492** | **QA1 `SubagentHandback`** (자식 기록 · 파일 mtime 같은 초) | QA1 RUNNING → **DONE R-08 09:38:47Z** · ended_at 09:38:47.492Z · handback 엣지 → `S:2bee9170…` · 폴러 18:38:48 KST | `state_log` · `edge` — 원천 → 판정 **< 1 초** |
| 09:38:48 | 오케스트레이터에 새 기록 (반환 알림) | SLEEPING → **RUNNING R-02a** | `state_log` |

- D-02 (`?project=` 이 폴더, 24 h) 09:39Z: QA1 `st-DONE`(회색) · QA2 `st-RUNNING`(초록) · 오케스트레이터 RUNNING — `r3-g22-qa1-done.jpg`.
- QA2 자신의 DONE 은 내가 반환한 뒤라 이 파일에 적을 수 없다 (오케스트레이터 확인 몫). 이 리포트를 쓸 때까지 QA2 는 RUNNING R-09/R-12.

## 2. 한계

- 관찰 중 전이는 모두 서버의 감시기 · 10 초 판정이 만든 것 (재백필 아님). 훅 미설치.
- 오케스트레이터 SLEEPING 은 D-18(가설) 결과 — spec 글자로는 STALE R-02b (`qa2-상태대조-r3.md` §2.2 #17).
