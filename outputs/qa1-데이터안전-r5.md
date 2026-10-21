# QA1 — 데이터 · 비용 · 안전 (r5 · 2차-T 웨이브 C · 계획 Task 7)

- 기준 커밋 `33d2d0a` · 정본 `spec.md` v0.4 (§5.4 T-01~T-07 · §8 `/api/v1/twin` · §10 V-17) · `decisions.md` D-25~D-27 · 2026-10-21 KST 13:10 ~ 13:25
- DB: `data/agentdash-qa1.db` 를 **처음부터 새로 백필** (`rm -f data/agentdash-qa1.db*; AGENTDASH_DB=data/agentdash-qa1.db make setup backfill` — 4.2 s · 원천 파일 579 · agent 73/245/1/6 · usage_event 26,326 · parse_error 0). 그 뒤 개발 검사 도구(`check_usage_est` 등)의 증분 수집으로 26,377 행이 됐다 — 트윈 대조(G-31 · G-32)는 그 전 26,326 행 상태에서 잼.
- 기대값은 `twin.build` · `usage.spark` 코드가 아니라 spec §5.4 글자 + D-25~D-27 로 QA1 스크립트가 다시 계산했다. DB 는 `mode=ro` 로만 열고, 숫자를 덧붙이는 경계 표본은 **메모리 사본**(`sqlite3.backup` → `:memory:`)에서만. 리포트에는 키 앞 14 자 · 숫자 · 시각만 적는다.
- 서버를 띄우지 않았다 — API 는 `TestClient`(lifespan 없이, 감시기 안 띄움)로 불렀다. 사람의 8095 서버 · QA2 의 서버는 건드리지 않음. `config/budget.yaml` 금액 null 그대로 · `~/.claude/settings.json` sha1 `8641eb22e8f5…` 시작 · 끝 같음 · 훅 설치 0.
- r4 의 나머지 게이트(G-04~G-08 · G-15 · G-25 등) 판정은 r4 그대로 쓰인다 — r5 에는 이번에 다시 잰 9 게이트만 표지를 단다.

QA1 스크립트 (새 이름, `outputs/qa1/`):
- `r5_twin.py` — G-32 독립 재계산 (범위 · 라인 순서 · 행/열 · 접힘 · 누적 · 비용 · 스파크 · 지금 도구 · 겹침 · 라인 상자 포함 · 문자열 ≤ 300)
- `r5_twin_edge.py` — 경계 표본 E1~E6 (스파크 분 경계 · `<synthetic>` · output_est · 비용 NULL · T-06 · API = build)
- `r5_twin_samples.py` — G-31 실제 DB 손 확인 S1~S5 (T-01 · T-03 · T-05 표본 5 · 반입구 · T-07 행 순서 뒤집은 사본)

## 요약 — 게이트별 QA1 판정

<!-- gate:G-13 -->
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  check_no_payload TEXT 337,047 값 중 300 자 초과 0 · 픽스처 23 파일 · 문자열 42,330 위반 0 · 트윈 응답 문자열 > 300 0 (24h · 7d · 6h · all, r5_twin.py) · Bash target 최장 120

<!-- gate:G-14 -->
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  check_readonly 정적 쓰기 호출 82 곳 중 원천 대상 0 · 읽기 전용 pytest 419 passed · 트리 변경 0 · DB 경로 씨앗 49/49 거부 · settings.json sha1 그대로 · QA1 스크립트는 DB mode=ro / 메모리 사본만

<!-- gate:G-16 -->
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)  PASS  check_bind host 127.0.0.1 · py 65 · 기타 17 위반 0 · `_twin.html` · `dashboard.html` · `_d01_body.html` · `base.html` 외부 URL · `<script src>` · `<link href>` 0 · fetch 는 `/api/v1/twin` · `/api/v1/agents/` 같은 출처만 · `1c33a63..33d2d0a` 새 외부 URL · 외부 전송 import 0 (CDN 은 2차-A 이전 graph · insights 고정 버전 2 그대로)

<!-- gate:G-24 -->
G-24  추정 열 — output_est · cost_est_usd (V-12)  PASS  check_usage_est 의심 DB 49.2% (12,969/26,377) = 원천 49.2% · 차 0.00%p · 위반 0 · test_usage_est PASS · 트윈 out_est_total 누적 = SUM(COALESCE(output_est, output_tokens)) 불일치 0

<!-- gate:G-26 -->
G-26  예산 — 80/100 % · KST 일/월 (V-13)  PASS  check_budget 칸 78 · 최대 차 $0.000000 · 위반 0 · 단계 unset 2 (한도 null) · test_budget PASS · config/budget.yaml 변경 0

<!-- gate:G-27 -->
G-27  추세 — 일·주·월 합 (V-14)  PASS  check_trend grain 3 × group 2 · 묶음 237 · 불일치 0 · usage_daily = usage_event (기록 $3,712.64 · 추정 보정 $3,842.88)

<!-- gate:G-28 -->
G-28  캐시 적중률 — 표본 10 손계산 (V-15)  PASS  check_efficiency 표본 10 (시드 20261021) · 최대 차 0.000000 · 불일치 0 · 정렬 위반 0

<!-- gate:G-31 -->
G-31  배치 규칙 T-01~T-07 + Review Focus 5  PASS  test_twin.py 24 passed · T-01~T-07 규칙마다 표 기반 테스트 ≥ 1 · Review Focus 5 전부 · D-25~D-27 반영 · 실제 DB 손 확인 T-01 라인 5 순서 · T-03 행 6 순서 · T-05 표본 5/5 · 독립 재계산 행/열/접힘 불일치 0 · 남은 것 경미 DEF-QA1-402 (라인 이름 T-07) · DEF-QA1-403 (테스트 빈칸)

<!-- gate:G-32 -->
G-32  트윈 API — 누적 · 스파크 · 겹침 0 (V-17)  PASS  독립 재계산 24h 설비 13 · 라인 5 · 접힘 11 · 칸+접힘 24 = 응답 24 = DB 직접 24 · 누적 · 비용 · 스파크 · 지금 도구 불일치 0 · 겹침 0 · 라인 상자 밖 0 · TEXT>300 0 · `--since all` 설비 85 · 라인 32 · 접힘 240 · 칸+접힘 325 = 325 불일치 0 · 경계 E1~E6 PASS · check_twin 같은 값 PASS · 남은 것 경미 DEF-QA1-401 (라벨 필터)

## 1. G-32 — `/api/v1/twin` 독립 재계산

### 1.1 방법 (`r5_twin.py`)
| 항목 | QA1 계산 (twin 코드 안 씀) | twin.build 쪽 |
|---|---|---|
| 범위 | agent 전체를 읽어 `state ∉ {DONE, FAILED}` 또는 `max(started_at, last_event_at)` 을 **datetime 으로** 바꿔 ≥ now − since | 문자열 비교 |
| 라인 · 행 · 열 · 접힘 | spec §5.4 T-01 · T-02 · T-03 · T-05 + D-25 · D-26 · D-27 을 재귀 깊이 우선으로 새로 구현 → 칸 목록 `(키, 열)` · 부모별 folded · 반입구 folded 기대값 | 스택 깊이 우선 |
| 누적 · 비용 | `SELECT agent_key, SUM(output_tokens), SUM(COALESCE(output_est, output_tokens)), SUM(cost_est_usd) FROM usage_event GROUP BY agent_key` (자기 몫) | 같은 뜻 다른 쿼리 |
| 스파크 | SQLite `strftime('%Y-%m-%dT%H:%M', at)` 분 버킷 · `julianday` 범위 [지금 분 − 29 분, 지금 분 + 1 분) · `model != '<synthetic>'` · 30 칸 | `substr(at,1,16)` 문자열 |
| 지금 도구 | `ok IS NULL` 인 tool_call 중 `(at, tool_use_id)` 최대 | — |
| 겹침 | 설비 + 반입구 상자 **전 쌍** · 라인 상자 전 쌍 (닿기만은 겹침 아님) + 설비가 자기 라인 상자 안인지 | `twin.overlaps` (정렬 가지치기) |
| 문자열 | 응답의 모든 키 · 값 문자열 길이 · 이름 ≤ 24 · elapsed_s ≥ 0 | — |

### 1.2 결과 (now `2026-10-21T04:17:19Z` 고정, 같은 now 로 check_twin 도)
| since / now | 범위 직접 = 응답 | 설비 | 라인 | 접힘 (+접힌 라인) | 칸+접힘 | 불일치 | 겹침 | 라인 상자 밖 | 문자열 > 300 | 스파크 합 (응답 = 직접) | 누적 출력 · 추정 · 비용 | ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24h (기본) | 24 = 24 | 13 | 5 | 11 + 0 | 24 | 0 | 0 | 0 | 0 | 64,183 = 64,183 | 849,347 · 910,503 · $100.6791 | 13.2 (첫 호출) |
| all | 325 = 325 | 85 | 32 | 240 + 0 | 325 | 0 | 0 | 0 | 0 | 64,183 = 64,183 | 12,129,394 · 12,235,103 · $2,120.0963 | 19.7 |
| 7d | 58 = 58 | 25 | 10 | 33 + 0 | 58 | 0 | 0 | 0 | 0 | 64,183 = 64,183 | — | 1.9 |
| 6h | 24 = 24 | 13 | 5 | 11 + 0 | 24 | 0 | 0 | 0 | 0 | 64,183 | — | 1.6 |
| 24h · now 10-21 02:00Z | 24 = 24 | 18 | 5 | 6 | 24 | 0 | 0 | 0 | 0 | 135,250 = 135,250 | — | 1.7 |
| 24h · now 10-20 12:00Z | 25 = 25 | 25 | 5 | 0 | 25 | 0 | 0 | 0 | 0 | 0 | — | 1.8 |
| 24h · now 10-14 18:00Z | 70 = 70 | 55 | 10 | 15 | 70 | 0 | 0 | 0 | 0 | 15,614 = 15,614 | — | 2.6 |

(과거 now 는 상태가 지금 값이라 실제 그 시각 화면은 아니다 — 배치 · 접기 · 스파크 계산을 다른 입력으로 한 번 더 돌린 것.) 스파크에 값이 있는 설비 6 (24h).

개발 도구 `check_twin` (같은 now):
```
G-32  트윈 API  PASS  설비 13 · 라인 5 (접힌 라인 0) · 접힘 11+0 · 범위 칸+접힘 24 / 응답 24 / DB 직접 24 · 누적 불일치 0 · 스파크 불일치 0 · 겹침 0 · 키 중복 0 · TEXT>300 0 · 1.4 ms (≤ 300) · 스파크 합 64183
--since all: 설비 85 · 라인 32 · 접힘 240+0 · 범위 325/325/325 · 불일치 0 · 겹침 0 · 4.1 ms · PASS
--since 7d: 설비 25 · 라인 10 · 접힘 33 · 58/58/58 · PASS   (과거 now 3 개도 QA1 값과 같은 숫자 · PASS)
```
QA1 독립 값과 check_twin 값이 모든 칸에서 같다.

### 1.3 경계 표본 (`r5_twin_edge.py`, 메모리 사본에 숫자 행만 덧붙임)
| # | 확인 | 기대 | 실제 | 판정 |
|---|---|---|---|---|
| E1 | 스파크 분 경계 — 지금 분 정각 행(포함) · 다음 분 정각(제외) · 맨 앞 분 정각(포함) · 그 1 ms 전(제외) | 칸 29 +1,000 · 칸 0 +3,500 · 그 밖 0 | 같음 | PASS |
| E2 | `<synthetic>` 5,000 — 스파크 제외 · 누적 포함 (누적 = §6 totals 그대로) | 스파크 증가 0 · out_total +15,000 | 같음 | PASS |
| E3 | output_est 3,500 이 output_tokens 3,000 대신 (COALESCE) | 칸 0 +3,500 · out_est_total +15,500 | 같음 | PASS |
| E4 | 비용이 전부 NULL 인 설비 | cost_est_usd `None` (0 으로 안 채움) | None | PASS |
| E5 | T-06 limit 84 · 40 · 10 · 1 (all) | 칸 ≤ limit · 접힌 라인은 T-01 순서 뒤쪽만 · 칸+접힘 = 325 · 겹침 0 | 81/1 · 31/24 · 8/31 · 0/32 접힌 라인 · 전부 뒤쪽 · 325 · 0 | PASS |
| E6 | `/api/v1/twin` (기본 · since=all · 7d) ↔ `twin.build` 같은 generated_at | 키 · 상자 · folded · 누적 같음 | 같음 (24 · 325 · 58) · `since=bad` → 422 + 이유 | PASS |

## 2. G-31 — 배치 규칙 테스트 표 ↔ spec §5.4 글자

### 2.1 규칙마다 어떤 테스트가 무엇을 확인하는가 (`tests/test_twin.py` 24 passed)
| 규칙 | spec 글자 (요지) | 테스트 · 확인 내용 | 빈칸 |
|---|---|---|---|
| T-01 | 살아 있는 라인 먼저 → 가장 늦은 `last_event_at` 최근 순 → 이름 순 | `test_T01_line_order` — 3 단 모두: 살아 있음(aaa · bbb) > 끝남, 끝난 것 중 최근(zzz 5 분) > 오래됨, 같은 시각 ccc · ddd 이름 순 · live · counts | — |
| T-02 | 열 = 라인 안 부모 사슬 길이 (`agent.depth` 아님) · 부모 없는 서브는 반입구 아래 1 열 | `test_T02_column_is_chain_depth` — depth 를 일부러 5 · 0 으로 틀리게 넣고 열 0/1/2 · 고아 1 열 · 반입구 0 열 · 같은 행 · `U:` 배관 | — |
| T-03 | 뿌리 started_at 순 · 자식 started_at 순(같으면 agent_key) 깊이 우선 · 한 설비 한 행 | `test_T03_rows_dfs_by_started` — C(먼저) > B > B 의 자식 D > E(B 와 같은 시각 → 키 순) · y 중복 0 | 뿌리(세션) 여럿의 started_at 순은 `test_T04` 합성 300 에만 간접 |
| T-04 | 칸 상수 · 설비 상자 · 라인 상자 겹침 0 | `test_T04_no_overlap_300` (300 설비 · 7 라인 · 4 열 · 겹침 0 · 라인 상자가 설비를 감쌈 · 정수) · `test_overlaps_counts_pairs` (닿기만 = 0) · `test_machine_values` (w/h = 상수) | — |
| T-05 | DONE · FAILED · `ended_at` 30 분 **넘게** 이전 → 부모 folded · 자손도 함께 · 부모 누적에 안 더함 | `test_T05_fold_done_after_30m` (31 분 DONE + 자손 접힘 · 29 분 FAILED 남음 · folded 2 · 부모 out_total 0 · 배관 없음) · `test_T05_live_descendant_keeps_parent` (D-26) · `test_T05_orphan_folds_into_inlet` · `test_root_never_folded` | 정확히 30 분 경계 · **30 분 넘은 FAILED** 가 접히는 경우는 테스트 없음 (DEF-QA1-403) |
| T-06 | T-05 뒤 > 300 이면 T-01 뒤 라인부터 라인 머리 한 줄 | `test_T06_fold_lines_over_limit` (limit 10 · 뒤 라인 p-l2 · hidden 5 · 머리 높이 · 칸+접힘 14 · 겹침 0) | T-05 접힘과 함께 있을 때(「T-05 뒤에도」) 는 테스트 없음 — QA1 E5 가 실제 DB 로 확인 |
| T-07 | 같은 DB 상태 · now · 필터 → 좌표까지 같음 | `test_T07_deterministic` (같은 연결로 두 번 부름) | **DB 행 물리 순서만 다른 같은 상태** 는 테스트 없음 → QA1 S5 에서 라인 이름 차이 발견 (DEF-QA1-402) |
| Review Focus | 라인 간 부모 · 순환 · 뿌리 안 접힘 · 24 자 · 경과 클램프 | `test_cross_line_parent` · `test_parent_cycle_terminates` (상호 순환 + 자기 부모 + 매달린 자식, 각 한 번) · `test_root_never_folded` · `test_name_clip_24` (한글 · 이모지 · 빈 이름 → 키) · `test_elapsed_clamped` (미래 → 0 · 빈 값 → None) | — |
| §5.4 설비 값 | 누적 = totals 자기 몫 · 스파크 30 칸 · `<synthetic>` 제외 · 지금 도구 = 결과 없는 마지막 | `test_machine_values` (totals 대조 · spark[-1] · [-6] · 결과 없는 마지막 Bash · 키 집합) · `test_sleeping_wake_at` · `test_handback_and_message` · `test_filters` · `test_workflow_children` | synthetic 칸(-3)이 0 인지는 직접 단언 없이 `usage.spark` 와 비교만 — QA1 E2 로 확인 |
| 성능 · API | 300 설비 ≤ 300 ms · 빈 DB 200 · build 와 같음 · 422 · TEXT ≤ 300 | `test_build_300_under_300ms` · `test_twin_api_*` 3 · `test_twin_text_le_300` | — |

### 2.2 D-25 ~ D-27 반영
| 결정 | 테스트 | 실제 DB |
|---|---|---|
| D-25 범위 밖 · 다른 라인 · 순환 부모 → 반입구 아래 1 열, 다른 라인은 links 로만 | `test_cross_line_parent` (links `spawn` count 1 · 배관 이중 0) · `test_parent_cycle_terminates` | 24h 반입구 아래 5 설비 전부 「부모 범위 밖」 (STALE 서브 — ML Platform 3 · MES Platform 1 · contracts 1) · 조상 끌어오지 않음 · 칸+접힘 = 범위 24. **「부모 범위 밖」 경우를 직접 만드는 테스트는 없다** (DEF-QA1-403) |
| D-26 살아 있는 자손이 있으면 접지 않음 | `test_T05_live_descendant_keeps_parent` | 독립 재계산(자손 전부 DONE/FAILED 일 때만 접기)과 folded 불일치 0 |
| D-27 반입구 0 열 · 첫 반입구 행 · 워크플로 = 설비 한 칸 | `test_T02_*` (반입구 x = LINE_PAD · 고아와 같은 y) · `test_workflow_children` (W 1 열 · 그 에이전트 2 열 · `workflow` 배관) | 반입구 3 개 모두 x = 16 (0 열) · since=all 워크플로 1 · 워크플로 에이전트 6 재계산 불일치 0 |

### 2.3 실제 DB 손 확인 (`r5_twin_samples.py`, now `04:17:19Z`)
**T-01 라인 순서** — 5 라인 모두 살아 있는 설비가 있어 둘째 단(최근 순)으로 정해진다:

| 순서 | 라인 | live | 가장 늦은 last_event_at |
|---|---|---|---|
| 0 | Multi-agent Dashboard | 3 | 2026-10-21T04:15:53Z |
| 1 | 00 PM Agent | 1 | 2026-10-21T03:14:48Z |
| 2 | Standard ML Platform | 4 | 2026-10-14T17:55:19Z |
| 3 | Standard MES Platform | 1 | 2026-10-09T03:56:32Z |
| 4 | contracts (= SongWol QR Platform 프로젝트, DEF-QA1-402) | 1 | 2026-09-28T01:23:26Z |

내림차순 맞음.

**T-03 행 순서** — 라인 Multi-agent Dashboard (칸 6): 행 0 열 0 `S:fa752590-2b3` (세션, folded 8) → 행 1~5 열 1 서브 `A:a01673009592` 03:41:04.194 · `A:a9fce3953264` 03:41:04.200 · `A:a770b69985c6` 03:51:07 · `A:a4a00befc95d` 04:15:31.063 · `A:a328106ffaca` 04:15:31.078 — started_at 오름차순 (ms 단위까지) · 한 행 한 설비 · y 간격 108 = BOX_H 92 + GAP_Y 16.

**T-05 접힘 표본 5** (24h 범위에서 칸 없는 11 중 가장 이른 2 · 가운데 1 · 가장 늦은 2):

| 키 | 상태 | ended_at | now − ended | 자식 | 접힌 곳 | 판정 |
|---|---|---|---|---|---|---|
| A:aaef4d6b5af3 | DONE | 10-21T00:34:07Z | 223.2 분 | 없음 | S:fc3908a3-be1 (00 PM Agent 세션) folded | 맞음 |
| A:a6fb649567d2 | DONE | 10-21T00:34:22Z | 222.9 분 | 없음 | S:fc3908a3-be1 | 맞음 |
| A:ad882f0fdff3 | DONE | 10-21T01:18:46Z | 178.5 분 | 없음 | S:fa752590-2b3 | 맞음 |
| A:a666066d0ca4 | DONE | 10-21T02:04:15Z | 133.1 분 | 없음 | S:fa752590-2b3 | 맞음 |
| A:a8e314a993aa | DONE | 10-21T03:45:27Z | 31.9 분 | 없음 | S:fa752590-2b3 | 맞음 (30 분 넘음) |

반대쪽: 칸에 남은 DONE 서브 3 (03:41 · 03:51 시작) 은 ended 가 30 분 안 — 접히지 않아 맞음. 세션 folded 8 + 00 PM folded 3 = 11 = 칸 없는 수.

**T-07** — 같은 DB 를 메모리에 복사하고 agent · usage_event · tool_call · edge · state_log 행을 **뒤집은 순서**로 다시 넣은 사본: 24h 응답 같음 · **since=all 응답 다름** (라인 17 의 `name` 이 「dev」 ↔ 「KyungDong Data Platform」) → DEF-QA1-402.

## 3. 회귀 (개발 도구 재실행, `AGENTDASH_DB=data/agentdash-qa1.db`)
| 도구 | 출력 (요지) |
|---|---|
| check_no_payload | `G-13  DB 본문 미저장  PASS  테이블 11 · 행 60575 · TEXT 값 337047 · 상한 300 자 · 위반 0` |
| check_fixtures_redacted | `G-13  픽스처 본문  PASS  파일 23 · 줄 1284 · 문자열 42330 · 위반 0` |
| check_readonly | 정적 PASS (쓰기 호출 82 곳 · 원천 대상 0) · 읽기 전용 pytest PASS (419 passed · 트리 변경 0) · DB 경로 씨앗 PASS (49/49 거부) |
| check_bind | `G-16  로컬 전용  PASS  host 127.0.0.1:8095 · 스캔 py 65 · 기타 17 · 위반 0` |
| check_usage_est | `G-24  추정 열  PASS  의심 DB 49.2% (12969/26377) · 원천 49.2% · 차 0.00%p · 위반 0` |
| check_budget | `G-26  예산  PASS  칸 78 · 최대 차 $0.000000 · 위반 0` |
| check_trend | `G-27  추세  PASS  묶음 237 · 불일치 0` |
| check_efficiency | `G-28  캐시 적중률  PASS  표본 10 · 최대 차 0.000000 · 불일치 0` |
| pytest 전체 | 419 passed · twin / check_twin / twin_page / usage_est / budget 70 passed |
| G-16 `_twin.html` 수동 | `<script src>` 0 · `<link href>` 0 · 외부 URL 0 · fetch 상대 경로 2 · `EventSource` 없음(공용 연결 사용) · 2차-A `1c33a63` 이후 diff 에 새 URL · 외부 import 0 |

## 4. 결함

| ID | 등급 | 내용 | 근거 · 재현 | 담당 |
|---|---|---|---|---|
| DEF-QA1-401 | 경미 | `/api/v1/twin?project=<이름 일부>` 가 **에이전트마다** `project_label` 로 거른다 — 같은 프로젝트 안에서 `project_path` 가 하위 폴더인 에이전트가 빠져 라인이 쪼개진다. spec §5.4 「필터 … 프로젝트 (D-02 와 같음)」 인데 D-02(`graph.build`)는 프로젝트 단위 라벨로 걸러 전부 낸다. | since=all: `project=SongWol QR` → 트윈 40 / 프로젝트 48 (D-02 48) · `project=KyungDong` → 트윈 KyungDong Data Platform 라인 1 (서브 3 빠짐) · 빠진 자식의 부모가 범위 밖이 되어 반입구 아래로 감. 화면(`dashboard.html`)은 `project_key` 를 보내 정확 일치라 영향 없음 → 경미. check_twin `direct_scope` 도 같은 에이전트 단위 식이라 못 잡는다. `core/twin.py` 범위 루프 | 개발2 (check_twin 은 개발1) |
| DEF-QA1-402 | 경미 | 라인 이름이 **DB 행 물리 순서**에 따라 바뀐다 (T-07 「같은 DB 상태 → 같은 응답」 위반) — 라인 안에서 `project_path` 가 있는 첫 에이전트(ORDER BY 없는 SELECT 순서)의 마지막 이름을 쓰기 때문. 실제 DB 에서 하위 폴더 cwd 의 서브에이전트가 먼저 읽혀 라인 이름이 「dev」 (KyungDong · OneTouch · PyoungChang Data Platform 3 라인) · 「contracts」 (SongWol QR Platform — 24h 화면 5 번째 라인) 로 보인다. D-02 `graph.py` 의 `all_projects` 도 같은 꼴(기존). | `r5_twin_samples.py` S5: 행을 뒤집어 넣은 사본에서 since=all 라인 17 이름 「dev」 ↔ 「KyungDong Data Platform」. 어느 에이전트의 경로를 라인 이름으로 할지(세션 우선 · 가장 짧은 경로 등)는 spec §5.4 대응표 글자로 안 정해짐 → `decisions.md` 에 올려 사람 확인 권장 | 개발2 (+ 사람 결정) |
| DEF-QA1-403 | 경미 | `test_twin.py` 빈칸 — ① T-05 정확히 30 분 경계(「넘게」 = 30:00 은 남음) ② 30 분 넘은 **FAILED** 접힘 ③ D-25 「부모가 범위(24h) 밖」 경우를 직접 만드는 테스트 ④ T-07 을 같은 연결 재호출로만 확인(행 순서 바꾼 같은 상태 없음 — 402 를 못 잡음) ⑤ T-06 을 T-05 접힘과 함께. 코드 동작은 QA1 독립 재계산 · E5 로 ①~③ · ⑤ 맞음 확인(경계는 `e < now − 1800s` 로 30:00 정각은 남음). | `tests/test_twin.py` §2.1 표 「빈칸」 칸 | 개발2 |

치명 0 · 중대 0 · 경미 3.

## 5. 관찰 (결함 아님)
- 응답은 spec §8 키의 상위 집합 — `links[].kind` · `machines[].wake_at` · `lines[].inlet / folded_line / hidden` · `agents_in_scope` · `filters` · `elapsed_ms` 추가. 빠진 spec 키 0.
- T-06 은 라인 단위로만 접어 limit 84 → 칸 81 처럼 limit 보다 꽤 적게 남을 수 있다 (spec 「300 이하가 될 때까지」 와 맞음).
- 트윈 범위는 `max(last_event_at, started_at) ≥ since` 를 문자열로 비교 (`…SS.sssZ` ≥ `…SS`) — 실제 DB 의 시각 형식이 24 자 `Z` 한 가지라 datetime 비교(QA1)와 7 가지 now/since 에서 모두 같은 범위.
