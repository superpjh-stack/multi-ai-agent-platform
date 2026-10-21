# G-22 자기 관찰 r5 (QA2, 2026-10-21) — r4 의 DONE 단계 확인

> r4 (`outputs/e2e/self-observe-r4.md`) 는 RUNNING 단계만 확인하고 DONE 을 미검증으로 남겼다. 오케스트레이터가 내 반환 뒤 `AGENTDASH_DB=data/agentdash-qa2.db make backfill` (증분, 파일 감시와 같은 수집 경로 · 훅 없음)으로 동기화했고, 나는 DB 를 **읽기만**(`sqlite3 "file:data/agentdash-qa2.db?immutable=1"`) 해서 확인했다. 서버는 띄우지 않았다. 원천은 `open(...,"rb")` 로 handback 시각만 읽음. 본문 없음.

<!-- gate:G-22 -->
G-22  자기 관찰 — 서브에이전트 RUNNING → DONE (파일 감시만)  PASS  r5 A:a666066d0ca4badc9 RUNNING R-09 01:43:03Z~ (D-02 이 폴더 프로젝트 아래 · spawn 엣지 S:fa752590→ 01:41:12Z) → DONE R-08 02:03:15Z · 원천 handback 02:03:04.031Z (+11 초 = 오케스트레이터 증분 백필 시각) · handback 엣지 → S:fa752590 · ended_at 02:03:04Z · hook_event 0 (파일만) · QA1 A:a19dae7c 도 반환 01:55:38Z → DONE R-08

## 실측

| 항목 | 값 | 출처 |
|---|---|---|
| agent 행 | `A:a666066d0ca4badc9` · **DONE · R-08** · state_since 2026-10-21T02:03:15Z · ended_at 2026-10-21T02:03:04.031Z · last_event_at 02:03:04.031Z · parent `S:fa752590-2b31-4e52-8518-a10dfe99f988` | `agent` |
| state_log | 01:43:03Z RUNNING `R-09 90초 안 · 마지막 기록 01:42:59Z` → 02:03:15Z DONE `R-08 반환 2026-10-21T02:03:04Z · 마지막 기록 02:03:04Z (11초 전)` | `state_log` |
| 엣지 | `S:fa752590… → A:a666066d0ca4badc9 spawn` at 01:41:12.925Z · `A:a666066d0ca4badc9 → S:fa752590… handback` at 02:03:04.031Z | `edge` |
| 원천 handback | SubagentHandback tool_use 1 회, 02:03:04.031Z (= DB 반환 시각) | 원천 `…/fa752590…/subagents/agent-a666066d0ca4badc9.jsonl` (읽기만) |
| 반환 → DONE | **11 초** — 판정 시각은 서버 실시간 감시가 아니라 오케스트레이터가 증분 백필을 돌린 시각(서버는 r4 끝에 내림). 같은 수집 · 판정 코드(감시기 증분 = 백필 증분) | — |
| 훅 | `hook_event` 0 행 — 파일만 | `hook_event` |
| RUNNING 구간 | 01:43:03Z ~ 02:03:15Z, D-02 화면 확인 01:45:07Z · 01:58:00Z (r4 스크린샷 `qa2-r4/g22-self-running-*.jpg`) | r4 |

## 주의 (관찰, 결함 아님)

- 이 확인 작업은 반환 **뒤** 오케스트레이터 메시지로 내가 다시 깨어 한 것이라, 원천에 handback(02:03:04Z) 뒤 tool_use 줄이 더 생겼다(마지막 기록 02:03:45Z~). D-21 · R-08 글자대로라면 다음 판정에서 나는 「반환 뒤 다시 깸」 → RUNNING R-09 로 돌아갔다가 이번 두 번째 반환 뒤 다시 DONE R-08 이 되는 것이 맞다. 위 DONE 판정은 02:03:15Z 시점 원천 기준으로 옳다.
- 실시간(서버 감시기 켠 상태) 반환 → DONE ≤ 1 초는 이번 회차에서 재지 않았다 (r3 에서 QA1 반환 → DONE < 1 초 실측).
