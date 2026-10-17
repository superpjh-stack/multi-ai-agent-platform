# G-22 자기 관찰 — QA2 (2026-10-17, 훅 미설치 · 파일 감시만)

서버: `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8095 uv run python -m agentdash.app` (17:06:43 KST 기동 · 빈 DB 백필 → 감시기 + 10 초 판정).
관찰 도구: `outputs/qa2/observe.py` — `GET /api/v1/agents?project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard` 를 20 초마다 읽어 상태 · 규칙이 바뀐 줄만 남김 (`outputs/e2e/observe-transitions.log`, 시각 KST). 정밀 시각은 `state_log.at`(UTC).

```
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE  PASS  QA1 A:a85b98ff · QA2 A:aa798b51 이 세션 S:2bee9170 아래 spawn 엣지 · RUNNING R-09 (08:06:51Z) → QA1 handback 08:29:23.312Z → DONE R-08 state_log 08:29:23Z (< 1 초) · 이전 웨이브 5 DONE R-08 · 파일 감시만
```

## 1. 이 프로젝트 아래 노드 (`/api/v1/agents?project=…`, 08:07:01Z 첫 조회)

| 키 | 이름 | 부모 (엣지) | 상태 | 시작 · 끝 (UTC) |
|---|---|---|---|---|
| `S:2bee9170-9e95-4e4e-873d-8490f228ad20` | multi-agent-dashboard-ce (오케스트레이터) | — | RUNNING R-02a | 02:23:21 · — |
| `A:ae52277140e6732bc` | Phase 0 architect scaffolding | S:2bee9170 (spawn 06:58:45) | DONE R-08 | 06:58:45 · 07:15:12 |
| `A:aa5e5b87a9c66359f` | Wave A dev1 collect/usage/cost | S:2bee9170 (spawn 07:16:19) | DONE R-08 | 07:16:19 · 07:39:51 |
| `A:a84175080a1a0ee6e` | Wave A dev2 linker/state/hooks | S:2bee9170 (spawn 07:16:19) | DONE R-08 | 07:16:19 · 07:42:39 |
| `A:aec649669ff2dc3df` | Wave B dev1 usage/timeline/pipeline | S:2bee9170 (spawn 07:41:07 · message 07:43:57) | DONE R-08 | 07:41:07 · 08:00:45 |
| `A:aa9a3c3d9bf2a1977` | Wave B dev2 dashboard/graph/detail | S:2bee9170 (spawn 07:44:28) | DONE R-08 | 07:44:28 · 08:03:54 |
| `A:a85b98ff6f908df54` | Wave C QA1 data/cost/safety | S:2bee9170 (spawn 08:05:31) | **RUNNING R-09** | 08:05:31 · — |
| `A:aa798b51a24f94adf` | Wave C QA2 state/realtime/browser (나) | S:2bee9170 (spawn 08:05:31) | **RUNNING R-09** | 08:05:31 · — |

이전 웨이브 서브에이전트 5 개(아키텍트 · 개발1 A/B · 개발2 A/B) 전부 DONE R-08 이고 오케스트레이터 세션에서 `spawn` 엣지로 이어진다 (`sqlite3 data/agentdash-qa2.db "SELECT dst_key,kind,at FROM edge WHERE src_key='S:2bee9170-9e95-4e4e-873d-8490f228ad20'"` → spawn 7 · message 1). D-02 계층 보기에서 이 프로젝트 묶음 = 세션 1 + 자식 7, 초록 2 (QA1 · QA2): `g22-self-observe-0813-qa1-qa2-running.png`.

## 2. 시각 기록

| 시각 (UTC) | 사건 | 대시보드 | 근거 |
|---|---|---|---|
| 08:05:31.03 / .04 | QA1 · QA2 meta 생성 (원천 파일 mtime 17:05:31 KST) | (서버 아직 안 뜸) | `ls -lT …/subagents/agent-a85b98…meta.json` |
| 08:06:51 | 서버 백필 직후 첫 판정 | QA1 · QA2 RUNNING R-09, 세션 RUNNING R-02a | `state_log` |
| 08:10:52 | 세션 마지막 기록(08:05:52) 뒤 5 분 · S1 busy · 미종료 자식 2 | 세션 RUNNING → **WAITING_CHILD R-04 (D-14)** | `state_log` · 10 초 판정 |
| 08:22:48 | QA2 가 긴 Bash 대기(무기록 302 초) | QA2 RUNNING → **STALE R-11** | spec §9.3 "훅 없이는 긴 도구 실행 5 분 뒤 STALE 오판 가능" — 규칙대로 |
| 08:26:48 | QA2 새 기록 | STALE → **RUNNING "R-09 회복"** (기록과 같은 초) | `state_log.reason` "R-09 회복" |
| 08:29:23.312 | **QA1 `SubagentHandback`** (자식 기록 · 4 번째 호출) | QA1 RUNNING → **DONE R-08** 08:29:23Z · ended_at 08:29:23.312Z · handback 엣지 | `state_log` — 원천 기록 → 판정 < 1 초 |
| 08:29:24 | 세션에 새 기록(08:29:23.666) | 세션 WAITING_CHILD → RUNNING R-02a | `state_log` |

D-02 에서 QA1 회색(DONE) · QA2 초록 · 세션 초록: `g22-self-observe-0830-qa1-done.png`. QA2 자신의 DONE 은 내가 반환한 뒤라 이 파일에 적을 수 없다(오케스트레이터가 확인).

## 3. 한계 · 관찰

- **새 에이전트 "5 초 안 출현" 은 이번에 못 쟀다** — QA1 · QA2 는 서버 기동(08:06:4x) 전에 생겨 백필로 처음 들어왔다. 실시간 출현 지연은 `tests/test_realtime.py`(가짜 루트, 0.19 s) 몫 · 다음 회전에 서버를 띄운 채 서브에이전트를 띄우면 잴 수 있다.
- 실시간 전이(08:10:52 · 08:22:48 · 08:26:48 · 08:29:23)는 모두 서버가 띄운 감시기 · 10 초 판정이 만든 것 — 재백필 아님.
- 08:22:48 의 QA2 STALE 은 spec 대로의 판정(훅 없음 · 5 분 무기록). 훅을 설치하면 PreToolUse 로 막힌다(R-01 · R-11 예외).
- 오케스트레이터는 ScheduleWakeup 08:35:38Z 도 걸어 두었다. 자식이 모두 끝나고 S1 이 busy 로 남은 채 5 분이 지나면 STALE R-02b 로 갈 수 있다 → DEF-QA2-004 (리포트 §4).
