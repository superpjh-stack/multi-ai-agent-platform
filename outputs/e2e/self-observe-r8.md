# G-22 자기 관찰 r8 — D-01 공장 평면도에서 QA2 r6 (나) RUNNING (2026-10-21)

> 나 = `A:af589d60fdce13372` (「QA2 2T r6 re-verify」, 부모 `S:fa752590-2b31-4e52-8518-a10dfe99f988`, spawn 05:08:59.311Z). 고친 것 0.
> 실제 DB 서버: `data/agentdash-qa2.db` 를 지우고 처음부터 백필(05:10:12Z, 4.2 s · agent 330 · parse_error 0) → `AGENTDASH_DB=data/agentdash-qa2.db AGENTDASH_PORT=8097 uv run python -m agentdash.app` (감시기 켬, uv 31527 / python 31529, 05:10:15Z ~ 05:16:15Z). 훅 0 — 파일 감시만. 브라우저 Claude in Chrome 새 탭(닫음).

<!-- gate:G-22 -->
G-22  자기 관찰 — 평면도에서 서브에이전트 RUNNING → DONE (파일 감시만)  미검증  r8 RUNNING 확인: 05:13:47Z 실제 DB 8097 D-01 「Multi-agent Dashboard」 라인 보조 설비 A:af589d60fdce13372 data-state RUNNING R-09 · parent S:fa752590 · spawn 배관 (05:08:59Z) · 입자 흐름 on · box x280 y468 · aria 「QA2 2T r6 re-verify, 실행, 경과 3분 35초」 · 형제 QA1 · Dev1 도 같은 라인 (Dev1 은 반환 뒤 DONE 흐림 실화면) — 내 DONE 은 반환 뒤라 내가 볼 수 없음: 오케스트레이터가 증분 동기화 뒤 확인 필요

## 근거 (05:13:47Z, 페이지 안 `window.agentdashTwin` + DOM)

| 항목 | 값 |
|---|---|
| 라인 | 「Multi-agent Dashboard」 (24h 6 라인 중 첫 번째 · 격자 2 열 × 3 행) |
| 설비 | `A:af589d60fdce13372` · SUBAGENT 보조 설비 · `data-state` **RUNNING** · rule R-09 · box {x 280, y 468, w 208, h 92} |
| 배관 | spawn `S:fa752590… → A:af589d60…` at 05:08:59.311Z · `.flow.on` (입자 흐름) |
| 도구 줄 | 화면 「mcp__claude-in-chrome__java…」 / 「…comp…」 (내가 쓰는 도구, 말줄임) |
| 키보드 | Tab 순회로 내 설비에 포커스 → Enter → `/agents/A%3Aaf589d60fdce13372` 「QA2 2T r6 re-verify · 상세」 |
| 같은 라인 형제 | QA1 `A:ab83c419…` RUNNING · Dev1 `A:a748170f…` RUNNING → 반환 뒤 DONE 「끝남 · 1분 21초 전」 흐림 (실화면에서 RUNNING → DONE 전이 관찰) · Dev2 `A:adc60434…` DONE |

스크린샷: `outputs/e2e/qa2-r6/real-light-keyboard-focus-g22-running.jpg` (QA1 포커스 · 나 RUNNING) · `real-light-1448-first.jpg` · `real-dark-1400-iframe-tool-ellipsis.jpg` (Dev1 DONE · 나 RUNNING + 도구 말줄임).

## DONE 확인 방법 (오케스트레이터)

내 반환 뒤: `AGENTDASH_DB=data/agentdash-qa2.db make backfill` (증분) → `sqlite3 "file:data/agentdash-qa2.db?mode=ro" "select state,state_reason,ended_at from agent where agent_key='A:af589d60fdce13372'"` 이 `DONE|R-08|<반환 시각>` 이고, `edge` 에 handback `A:af589d60… → S:fa752590…` 가 있으면 PASS (r7 과 같은 방식). 서버를 띄워 둔 상태라면 평면도에서 역흐름 1 회 → 흐림.
