# QA1 — 데이터 · 비용 · 진척 · 안전 (재검증 r2 · 웨이브 D/D2)

> 2026-10-17 18:01~18:12 KST · 코드 = 커밋 `8606bc8` (웨이브 D · D2) · QA DB `data/agentdash-qa1.db` 를 지우고 다시 백필 (`AGENTDASH_DB=data/agentdash-qa1.db make backfill` 3.9 s · 원천 파일 584 · agent 77/245/1/6 · usage_event 27,592 · parse_error 0)
> 기대값은 QA1 독립 스크립트(`outputs/qa1/*`, agentdash 를 import 하지 않음 — `cost_edge` · `hook_payload` · `pipe_fake` 만 개발 함수를 직접 불러 시험)로 다시 센 값이다. 이번 회차 새 스크립트 `r2_final.py` · `r2_last_event.py`.
> 원천은 읽기만 했다(실제 `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22…` 전 = 후, `~/.claude` 의 `bak-agentdash*` 0, 원천 아래 `*agentdash*` · `newdir*` · `*.db` 0). 본문은 옮기지 않았다(숫자 · 키 · 경로만). 고치지 않았다. 이전 리포트 `outputs/qa1-데이터안전.md` 는 그대로 둔다.

## 요약 — 게이트별 QA1 판정

<!-- gate:G-04 -->
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)  PASS  세션 77/77 · 서브에이전트 245/245 · 워크플로 에이전트 6/6 · S6 1/1 · 원천만 0 · DB만 0 (recount.py)

<!-- gate:G-05 -->
G-05  파싱 오류율 ≤ 0.1% (V-07)  PASS  줄 164,747 (offset 까지) · 깨진 JSON 0 · 필수 필드 없는 assistant/user 0 (link_check.py · recount.py)

<!-- gate:G-06 -->
G-06  부모 연결 ≥ 95% (V-02)  PASS  독립 연결 251/251 = 100% · 독립 부모 = DB parent_key 252/252 (워크플로 노드 포함)

<!-- gate:G-07 -->
G-07  토큰 합 — 표본 10 세션 (V-03)  PASS  최종본 규칙 독립 집계 = DB 326/326 에이전트 · 4 칸 합 일치 (출력 21,202,606) · DEF-QA1-001 해결 · 서브에이전트 출력 과소는 D-17 차단(사람 결정) — 표기 D-04 · D-03 · API 확인

<!-- gate:G-08 -->
G-08  비용 — 표본 20 건 손계산 (V-09)  PASS  실제 표본 20/20 · 합성 경계 10/10 · 단가표 config = spec §6.1 (12 모델 불일치 0) · 전 기간 손계산 $4,515.862501 + 사본 최종본 몫 $1.811680 = DB $4,517.674181

<!-- gate:G-13 -->
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  TEXT 354,321 값 중 300 자 초과 0 · 상위 20 전부 경로 · 픽스처 본문 키 원문 0 · 훅 URL 은 호스트만 (DEF-QA1-007 해결)

<!-- gate:G-14 -->
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  FAIL  실제 원천 쓰기 0 · DEF-003 · 008 해결. 그러나 is_source_path 가 대소문자를 구분 — 대소문자 다른 DB 경로로 원천 루트 안에 DB 생성(가짜 루트 재현) · check_readonly 미검출 → DEF-QA1-101 (중대)

<!-- gate:G-15 -->
G-15  훅 설치 안전 — 가짜 settings (V-10)  PASS  가짜 settings 설치 덧붙임 9 · 제거 후 바이트 동일 · 남의 hook_send.sh 남음 1 · 실제 파일 가드 True/True/True · 송신 8099 0.027 s exit 0 · 0 B (DEF-QA1-004 · 005 해결)

<!-- gate:G-16 -->
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)  PASS  실측 TCP 127.0.0.1:8096 (LISTEN) · 외부 전송 import 0 (urllib.parse 2 곳만) · 외부 URL 은 CDN 고정 버전 1 개

<!-- gate:G-19 -->
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)  PASS  88 칸 · 근거 없는 칸 0 · 55 칸 독립 find = DB 55/55 · 표본 10/10 · P-01 2 칸 · ↻ 9 = 9 · 고려솔더 01·02 DONE v1.0 · 05·08 UNKNOWN · 가짜 루트 P-05 · 미등록 · NFD · 별칭 spec 대로

<!-- gate:G-20 -->
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice  PASS  /usage [추정] API 정가 환산 4 곳 · 단가 없음 0 건 · reprice 바뀐 행 0 · event = daily = API = trend $4,517.674181 · 작성 파일 2,272 = 고유 (DEF-QA1-006 해결)

**이전 결함 8: 해결 7 · 차단 1 (DEF-002 → D-17, 표기 붙음 확인).** **새 결함 3 — 치명 0 · 중대 1 · 경미 2.** 열린 중대는 DEF-QA1-101 하나(+ 사람 결정 대기 DEF-002/D-17). 치명 기준(원천 쓰기 · 본문 저장 · 기존 훅 손상 · 외부 전송)이 실제로 일어난 일은 0.

| ID | 등급 | 담당 | 한 줄 |
|---|---|---|---|
| DEF-QA1-101 | 중대 | 아키텍트 (`settings.py` `is_source_path` · `tools/check_readonly.py`) | 원천 판정이 대소문자 구분 — macOS(APFS 대소문자 무시)에서 `~/.CLAUDE/…` · `~/desktop/ai coding/…` 를 원천 아님으로 봄 → `init_db` 가 원천 루트 안에 폴더 · DB 를 만든다 |
| DEF-QA1-102 | 경미 | 개발1 (`collect/ingest.py`, D-20) | handback 뒤 꼬리 제외가 「마지막 기록」 값까지 줄임 — 서브에이전트 60 의 `last_event_at` < 그 에이전트 마지막 usage 시각 (최대 16,527 s · 출력 34,334 · $11.57 가 「마지막 기록」 뒤에 있음) |
| DEF-QA1-103 | 경미 | 아키텍트 (`tools/gate.py`) | `GATES` 에 QA1 리포트 수단이 없다 — QA1 의 FAIL 판정(이번 G-14)이 `make gate` 에 반영되지 않음 |

---

## 1. 이전 결함 해결표 (DEF-QA1-001~008)

| ID | 이전 등급 | 판정 | 재현 다시 돌림 → 실측 |
|---|---|---|---|
| DEF-QA1-001 사본 최종 usage 버림 | 중대 | **해결됨** | `fork_final.py` (원천만 잼) 128 requestId · 출력 90,584 · $1.811680 그대로 — 이것은 원천의 차이라 그대로가 정상. `r2_final.py`(소유 = 처음 나온 기록, 값 = 사본 포함 output 최대) **326/326 에이전트 4 칸 일치**, 합 출력 21,202,606 = DB. 이전 소유 규칙(`recount.py`) 대비 DB 차이 = +90,584 · 다른 에이전트는 DEF-001 이 지목한 5 개뿐. 표본 dbd09a2a 1,553,522 → 1,638,439 (+84,917) · 8f3a6abd 1,352,668 → 1,358,335 (+5,667). 비용 `global_cost.py`(옛 규칙) $4,515.862501 + $1.811680 = DB $4,517.674181 |
| DEF-QA1-002 서브에이전트 출력 스트리밍 시작값 | 중대 | **차단 (D-17, 사람 결정)** — 표기 붙음 확인 | `stream_heuristic.py`: 메인 13/10,196 (0.1%) · 서브 12,080/17,596 (68.7%) · 워크플로 60/85 (70.6%) · 하한 추정 4,155,051 (이전 4,138,268 — 원천 증가). 표기: D-04 API `total.undercount=true` · `undercount_output` 7,945,095 (= DB 서브+워크플로 출력 합 7,945,095) · 행 326 중 251 (= 서브 245 + 워크플로 6) · `/usage` 「기록상 과소 (D-17)」 231 · 「과소 (D-17)」 687 · CSV 열 `output 기록상 과소 (D-17)`. D-03 API: dbd09a2a `own` false · `with_descendants` true (1,296,881) · 서브에이전트 own true · 자손 없는 세션 false · 워크플로 노드 with_descendants true. D-03 화면 `/agents/{key}` 「기록상 과소 (D-17)」 2 · 4 · 0 · 2 곳 (같은 4 키). 숫자는 원천 그대로 |
| DEF-QA1-003 init_db mkdir 먼저 | 중대 | **해결됨** | 가짜 루트에서 `AGENTDASH_DB=<home>/newdir/x.db … -m agentdash.db.conn` → `RuntimeError` · `newdir` 안 생김 (`<home>` 에 `projects` 만). 코드: `_refuse_source` → `mkdir` 순서. 단 대소문자 변형은 → DEF-101 |
| DEF-QA1-004 `--yes` 가드 우회 | 중대 | **해결됨** | `hooks_fake.sh` F: `is_real_target(~/.claude/settings.json)` 가짜 home True · 환경변수 없음 True · pytest 중 + 가짜 home True. 판정만 추가: `~/.CLAUDE/settings.json` True · `~/.claude/../.claude/settings.json` True (samefile) |
| DEF-QA1-005 남의 hook_send.sh 삭제 | 중대 | **해결됨** | `hooks_fake.sh` D: 덧붙임 9 · 제거 후 `/other/project/hook_send.sh` 남음 1. 식별 = `bash '<저장소>/scripts/hook_send.sh'` 정확 일치 |
| DEF-QA1-006 작성 파일 과다 | 경미 | **해결됨** | D-04 API 전 기간 `total.files_written` 2,272 = 행 합 2,272 = 고유 (agent, path) 2,272 (`usage_daily` 단순 합 2,287 — 이제 쓰지 않음) |
| DEF-QA1-007 훅 URL 쿼리 | 경미 | **해결됨** | `hook_payload.py` WebFetch 표지 False. 추가: `https://user:TOKEN@h/…?q=TOKEN` → `host h` · 스킴 없는 문자열 · `file:` → 저장 없음 · 표지 0 |
| DEF-QA1-008 실제 루트 미보호 | 경미 | **해결됨** (같은 대소문자 경로) | CLAUDE_HOME · AGENTS_ROOT 가짜일 때 `~/.claude/newdir/x.db` True · `~/Desktop/AI Coding/Other/x.db` True · 저장소 `data/` · `outputs/` · 상대 `data/x.db` False. 대소문자 변형은 False → DEF-101 |

## 2. 수정이 만든 회귀 사냥

### 2.1 D-20 (`last_event_at` = 모든 줄 · handback 뒤 꼬리 제외) — `r2_last_event.py`

| 항목 | 실측 |
|---|---|
| timestamp 꼴 | 줄 138,265 개 전부 `YYYY-MM-DDTHH:MM:SS.sssZ` 한 꼴 — 문자열 비교 안전. timestamp 없는 줄(`last-prompt` · `mode` · `ai-title` …)은 parser 가 건너뜀 |
| DB 값 = 독립 계산 | 기록 328 중 121 = 「모든 줄 최대」(그 시각을 정한 줄: assistant 52 · system 36 · user 15 · queue-operation 10 · frame-link 4 · attachment 3 · api-request 1) · 207 = handback 시각 (서브에이전트 handback 있는 210 중 207 — 나머지 3 은 다시 깨어남) |
| 증분 = 백필 | 같은 offset 기록 326 개에서 qa1 DB(새 백필) = 기본 DB(증분) last_event_at 326/326 같음 |
| **작업량 · 활동 시간** | 영향 0 — `rebuild_daily` · `active_by_day` 는 `usage_event.at` · `tool_call.at` · `result_at` 만 쓴다(코드 확인). D-04 전 기간 활동 578,386 s |
| **진척 「마지막 손댄 에이전트」** | 영향 0 — `pipeline._last_session` 은 `file_touch.at` 만. P-02 는 `state` 를 쓰므로 상태 판정을 통해서만 간접 영향(QA2 범위) |
| **영향 있는 곳** | `last_event_at` 을 쓰는 D-01 대기 · 멈춤 시간(`agents.py` idle · wait_basis) · `/api/v1/agents?since` 필터 · 정렬 · D-02 `recent` · D-03 「마지막」 · D-05 막대 끝(세션은 `ended_at` 이 77/77 NULL 이라 막대 끝 = last_event_at) |
| 세션: 모든 줄로 늘어난 폭 | 「모든 줄 최대 − assistant/user 최대」 > 0 54 기록 · > 300 s 8 · > 3600 s 3 · 최대 155,389 s (세션 0ec6acf7 — `queue-operation` enqueue/dequeue 줄이 43 시간 뒤). spec 「마지막 기록」 글자대로라 결함으로 올리지 않음 (관찰 O-1) |
| **서브에이전트: 꼬리 제외로 줄어든 값** | handback 뒤 isMeta `task-notification` 으로 다시 돌아 assistant 출력을 낸 서브에이전트 **60** — `last_event_at` < 그 에이전트 마지막 `usage_event.at` (최대 16,527 s). 그 뒤 usage 61 행 · 출력 34,334 · $11.5749 → **DEF-QA1-102** |

### 2.2 `is_source_path` 강화 — 정상 경로를 막는가

| 경로 (판정만, 열지 않음) | is_source_path |
|---|---|
| 저장소 `data/agentdash-qa1.db` (절대) · `data/x.db` (상대) · `outputs/x.db` | False (정상 — 막지 않음) |
| 가짜 claude_home 아래 · 실제 `~/.claude/newdir/x.db` · 실제 `~/Desktop/AI Coding/Other/x.db` | True |
| `~/.CLAUDE/newdir/x.db` · `~/.Claude/projects/x.db` · `~/desktop/ai coding/Other/x.db` | **False** (같은 폴더 — `os.path.exists(~/.CLAUDE)` True) → DEF-101 |
| `~/Desktop/AI Coding/multi-agent dashboard/data/x.db` (저장소 대소문자 변형) | True (과잉 거부, 무해) |

`make backfill` · `make gate` · 서버 기동 모두 저장소 `data/` 에서 정상 동작(이번 회차 실제 실행).

### 2.3 `check_usage_sum` 새 독립 계산은 정말 독립인가 — **예 (조건부)**

- 원천 쪽: 세션 폴더의 모든 기록을 `rb` 로 직접 읽어 requestId 세션 단위 · 소유 = 처음 나온 기록(시각 → 깊이 → 키) · 값 = 사본 포함 output 최대. 수집기의 `skip_uuids` · `skip_rids` · `_fork_pending` · `upgrade_owner_usage` 를 **쓰지 않는다**(코드 읽음). QA1 `r2_final.py` 와 같은 규칙이고 결과도 같다(326/326).
- DB 쪽은 개발 함수 `usage.totals` · `usage.descendants` 를 쓰지만, 에이전트별 소유 합을 원천 쪽과 따로 대조(「에이전트별 소유 불일치」)하므로 부모 연결 오류도 드러난다.
- 남는 한계: ① 두 쪽 모두 원천 숫자를 믿으므로 D-17(기록 자체 과소)은 못 본다 — 끝 줄에 의심 비율만 찍음(설계대로). ② 표본 선정(에이전트 많은 5 + 시드 무작위 5)이 고정이라 새 결함 유형이 표본 밖에 있으면 못 본다 — QA1 은 전 에이전트로 다시 셈. ③ 검사 전에 `ingest_all` 로 DB 를 증분 갱신(DB 에만 씀)한다.

## 3. 새 안전 사냥 (수정된 파일 위주)

| 파일 | 본 것 | 결과 |
|---|---|---|
| `db/conn.py` | `_refuse_source` → `mkdir` → `connect`(다시 거부) 순서 | 순서 OK. 거부 판정 자체의 대소문자 구멍 → DEF-101 |
| `settings.py` | `guard_roots` = 설정 루트 + 실제 `~/.claude` + yaml 기본 agents_root · `resolve()` 비교 | 심볼릭 링크 · `..` OK. 경로 비교가 대소문자 구분(`Path.__eq__` · `in parents`) — **가짜 루트 실측**: `AGENTDASH_CLAUDE_HOME=<s>/casehome AGENTDASH_DB=<s>/CASEHOME/newdir/x.db -m agentdash.db.conn` → 거부 없이 **테이블 11 DB 생성, 실제 위치 `<s>/casehome/newdir/x.db`**. `-m agentdash.collect.backfill` + `<s>/CaseHome/projects/y.db` → 원천 `projects/` 안에 `y.db` 생성. 같은 대소문자는 `RuntimeError` |
| `tools/check_readonly.py` | DB 씨앗 3 경로 × 진입점 7 | 경로가 전부 가짜 루트와 같은 대소문자 — DEF-101 을 못 봄 (G-14 PASS 오판) |
| `collect/ingest.py` | 포크 사본 반영(`_fork_pending`) · D-20 `others=True` 줄 | 쓰기는 DB 뿐 · 원천 `rb`. 다른 줄 종류는 `type`(40 자) · `uuid` · `timestamp` 만 꺼냄 — 본문 0. `_fork_pending` 은 프로세스 메모리(키 = DB id · 세션 · requestId) |
| `scripts/hooks_install.py` | `is_real_target` · `marked` · `main` 가드 순서 · `--check` | `--check` 는 가드 앞이지만 읽기만 + DB 연결. 관찰 O-2: 사람이 **우리 항목 안**(같은 `hooks` 배열)에 자기 명령을 넣으면 제거 때 항목째 지워진다(spec 「식별 표시 붙은 항목만」 글자대로) · 저장소를 옮기면 옛 항목을 못 알아봄 |
| `collect/hooks_rx.py` | `_host` · `filter_payload` · `target_of` | URL → `hostname` 만 · userinfo · 포트 · 경로 · 쿼리 버림 · IPv6 `::1` · 스킴 없으면 저장 안 함. Notification `message` 앞 120(필터) / 80(detail)은 spec 허용(이전과 같음) |
| `core/state.py` · `core/linker.py` 기록 읽기 | `record_activity_since` · `_ACT_CACHE` 삭제 확인, `build_ctx` → `return_of` 는 DB 만 | 상태 판정 경로에서 원천 파일을 여는 코드 0. `linker.scan_projects`(검사 도구용)는 meta `r` · 기록 `rb` 읽기만 |
| DB TEXT | `text_scan.py` | 300 자 초과 0. 「키 꼴」 3 = 오탐 (Bash description 2 · tool_use_id 1 — 눈으로 확인, 토큰 없음) |
| 외부 전송 · 바인드 | grep · `lsof` | `urllib.parse` 2 곳만 · `0.0.0.0` 0 · 서버 `127.0.0.1:8096` |

## 4. 새 결함

### DEF-QA1-101 · 중대 · 아키텍트 (`src/agentdash/settings.py` `is_source_path` · `tools/check_readonly.py`) — 원천 판정이 대소문자를 구분한다

- **재현 (가짜 루트만)**: `S=<스크래치>; mkdir -p $S/casehome/projects $S/caseagents; AGENTDASH_CLAUDE_HOME=$S/casehome AGENTDASH_AGENTS_ROOT=$S/caseagents AGENTDASH_DB=$S/CASEHOME/newdir/x.db uv run python -m agentdash.db.conn` → `DB …: 테이블 11` (거부 없음), `ls $S/casehome/newdir` → `x.db`. 같은 대소문자(`$S/casehome/newdir/x.db`)는 `RuntimeError`. backfill 진입점도 같음(`$S/CaseHome/projects/y.db` 생성).
- **실제 경로 판정(열지 않음)**: `is_source_path(~/.CLAUDE/newdir/x.db)` = False · `~/desktop/ai coding/Other/x.db` = False. 이 Mac 의 홈 볼륨은 대소문자 무시(`~/.CLAUDE` 존재 = True) → 그대로 `init_db` 하면 실제 `~/.claude` · 다른 프로젝트 폴더 안에 폴더 + DB(+WAL)가 생긴다.
- **기대**: CLAUDE.md 「원천 아래를 쓰기 모드로 여는 코드 0」 · spec V-05 — 경로 문자열 모양과 무관하게 같은 폴더면 거부. (예: 존재하는 가장 가까운 상위 폴더끼리 `os.path.samefile`/inode 비교, 또는 대소문자 무시 볼륨이면 casefold 비교.)
- **게이트 오판**: `check_readonly --db-seed` 의 3 경로가 모두 가짜 루트와 같은 대소문자라 이 길을 시험하지 않는다 → G-14 PASS. DEF-003 과 같은 부류(잠재 경로 · 환경변수 오설정 1 개로 열림 · 도구가 못 봄)라 같은 등급.

### DEF-QA1-102 · 경미 · 개발1 (`collect/ingest.py` D-20) — handback 뒤 꼬리 제외가 「마지막 기록」 값까지 줄인다

- **재현**: `.venv/bin/python -I outputs/qa1/r2_last_event.py --db data/agentdash-qa1.db` 와
  `SELECT COUNT(DISTINCT u.agent_key), COUNT(*), SUM(u.output_tokens), SUM(u.cost_usd) FROM usage_event u JOIN agent a USING(agent_key) WHERE u.at > a.last_event_at` → **60 · 61 · 34,334 · $11.5749**.
- **실측**: 예 `A:a38273d11e7939c22` — handback 01:19:01 뒤 isMeta `task-notification` 2 번(01:25 · 05:54)에 assistant 출력(text 97 · 198 토큰)을 냈지만 `last_event_at` = 01:19:01 (D-20 이전 코드라면 05:54:28). `A:a4078576c33d85060` 도 같은 꼴(+2,261 s). 상태 판정(DONE)은 L-07 「활동 = tool_use · 들어온 메시지」 대로라 맞다.
- **영향**: 같은 열을 「마지막 기록」 표시에도 쓰므로 D-03 「마지막」 · D-01 목록 정렬 · `/api/v1/agents?since=` 필터(그날 출력이 있는데 빠짐) · D-02 `recent` 가 실제 마지막 기록보다 이르다. 작업량 · 활동 시간 · 비용 합은 영향 없음.
- **기대**: D-20 의 목적(L-07 활동 판정)과 「마지막 기록」 값을 분리하거나, 최소한 usage 가 있는 assistant 줄은 마지막 기록에 넣는다(L-07 판정은 `linker._activity` 쪽에서 handback 이후 활동 여부만 따로).

### DEF-QA1-103 · 경미 · 아키텍트 (`src/agentdash/tools/gate.py` `GATES`) — QA1 판정이 `make gate` 에 들어가지 않는다

- **재현**: `grep -n '"qa"' src/agentdash/tools/gate.py` → `qa2-상태대조.md`(G-12 · G-18 · G-21) · `e2e/self-observe.md`(G-22) 뿐. QA1 범위(G-04~G-08 · G-13~G-16 · G-19 · G-20)에는 QA 리포트 수단이 없다.
- **실측**: 이전 회차 QA1 의 G-07 · G-14 · G-15 FAIL 이 `make gate` 에 PASS 로 나왔고, 이번 G-14 FAIL(DEF-101)도 `make gate` 는 PASS (아래 §6). goal.md §4.2 「판정은 `make gate` 출력으로만」 이라 QA1 FAIL 이 루프에서 안 보인다.
- **기대**: QA1 리포트(이 파일)의 표지 행을 해당 게이트의 수단으로 더한다(CLAUDE.md 「QA 리포트 형식」 은 `outputs/qa*.md` 를 읽는다고 적고 있다).

### 관찰 (결함 아님)

- O-1: D-20 으로 세션 `last_event_at` 이 `queue-operation` · `away_summary` · `frame-link` 줄까지 따라간다 — 3 세션 > 1 시간(최대 43 h). spec 「마지막 기록」 · QA2 judge 와 같은 정의라 그대로 둔다. 세션 `ended_at` 이 77/77 NULL 이라 D-05 막대가 그만큼 길어진다.
- O-2: `hooks_install` 제거는 식별 항목 **통째로** 지운다 — 사람이 그 항목의 `hooks` 배열에 자기 명령을 끼워 넣은 경우에만 문제. 저장소 경로가 바뀌면 옛 항목을 못 알아본다.
- O-3: G-15 `check_hooks` 송신은 이번에도 「8095 사용 중」 으로 미검증(8095 LISTEN 은 QA1 프로세스가 아님 — 건드리지 않음). QA1 이 8099 로 따로 쟀다: exit 0 · 0 B · 0.027 s.

## 5. QA1 스크립트 (`outputs/qa1/`, 원천 읽기 전용 · DB `mode=ro`)

이전 표(`outputs/qa1-데이터안전.md` §8) 그대로 + 이번 회차:

| 파일 | 하는 일 |
|---|---|
| `r2_final.py` | G-07 · DEF-001 — 최종본 규칙(소유 = 처음 나온 기록, 값 = 사본 포함 output 최대) 전 에이전트 4 칸 ↔ DB |
| `r2_last_event.py` | D-20 — 기록별 모든 줄 최대 · assistant/user 최대 ↔ DB `last_event_at`, 줄 종류 · timestamp 꼴 · 마지막 활동 대비 차이 |

이번 회차 실행: `recount.py --seed 7` · `fork_final.py` · `global_cost.py` · `link_check.py` · `stream_heuristic.py` · `cost_check.py --seed 3` · `cost_edge.py` · `text_scan.py` · `fixture_scan.py` · `pipe_check.py --seed 5` · `pipe_fake.py` · `hook_payload.py` · `hooks_fake.sh` (가짜 settings 만) · 서버 8096 (qa1 DB · `AGENTDASH_NO_WATCH=1`, PID 36437/36439 — 끝에 종료, 8096 LISTEN 0).

## 6. `make gate` 판정표 (기본 DB, 18:09:29 — 붙여 넣은 출력, gate 는 위 표지 줄만 읽는다)

```
# make gate — 2026-10-17 18:09:29 (goal.md §2)
G-01  골격 — make setup · 테이블 11                   PASS  tests/test_schema.py: 5 passed in 0.03s ‖ agentdash.db 테이블 11
G-02  파서 회귀 — 픽스처 S1~S6 · S9 (V-08)              PASS  tests/test_parsers.py: 29 passed in 0.20s
G-03  증분 읽기 — 추가분 · 반쪽 줄 · inode                 PASS  tests/test_tail.py: 9 passed in 0.07s
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)           PASS  원천 77 · DB 77 · 빠짐 0 · 남음 0 (18:08:52 · 직전 증분 수집 바뀐 키 3) ‖ 원천 245 · DB 245 · 빠짐 0 · 남음 0 (18:08:52 · 직전 증분 수집 바뀐 키 3) ‖ 원천 6 · DB 6 · 빠짐 0 · 남음 0 (18:08:52 · 직전 증분 수집 바뀐 키 3)
G-05  파싱 오류율 ≤ 0.1% (V-07)                       PASS  오류 0 / 줄 165564 = 0.0000% (상한 0.1%) · 파일 584
G-06  부모 연결 ≥ 95% (V-02)                         PASS  원천 서브에이전트+워크플로 에이전트 251 중 연결 251 = 100.0% · L-01=233 L-02=12 L-03=6 · 워크플로 노드 1 중 1 · 줄 165296 · 2.0s ‖ agentdash.db 서브에이전트 245 · 워크플로 에이전트 6 중 부모 있음 251 = 100.0% (기준 ≥ 95%) · 부모 미확인 0 · 워크플로 노드 1 중 1
G-07  토큰 합 — 표본 10 세션 (V-03)                     PASS  원천 출력 1638439 · DB 1638439 · 입력 11598/11598 · 캐시읽기 1237354145/1237354145 · 캐시쓰기 20468291/20468291 · 자기+자손 = · 에이전트 65 · 파일 65 · 에이전트별 소유 불일치 0 · 세션 안 requestId 중복 0 ‖ 원천 출력 2126284 · DB 2126284 · 입력 44386/44386 · 캐시읽기 830382477/830382477 · 캐시쓰기 22981813/22981813 · 자기+자손 = · 에이전트 52 · 파일 52 · 에이전트별 소유 불일치 0 · 세션 안 requestId 중복 0 ‖ 원천 출력 1080368
G-08  비용 — 표본 20 건 손계산 (V-09)                    PASS  일치 20/20 · 손계산 합 $2.570828 · 단가표 2026-10-06 · 표본 종류 1h,5m,claude-fable-5-1,claude-opus-4-8,claude-opus-5,claude-opus-5-5,claude-sonnet-5,speed 없음(옛 기록),무작위 · 기록에 speed=fast 0 건 (fast 는 tests/test_cost.py 로) ‖ 없음 (0 건) · 비용 NULL 행 0 · 기록 모델 5 ‖ tests/test_cost.py: 13 passed in 0.02s
G-09  판정 규칙 13 — 표 기반 테스트                        PASS  tests/test_state.py: 55 passed in 0.19s
G-10  연결 규칙 L-01~L-07 테스트                        PASS  tests/test_linker.py: 25 passed in 0.17s
G-11  실시간 — SSE 5 초 · 훅 1 초                      PASS  tests/test_realtime.py: 4 passed in 7.23s
G-12  상태 대조 — 표본 30 오판 ≤ 2                       미검증  — QA 재검증 필요(리포트 형식): outputs/qa2-상태대조.md 에 <!-- gate:G-12 --> 표지 판정 행 없음
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)        PASS  agentdash.db 테이블 11 · 행 63749 · TEXT 값 356064 · 상한 300 자 · 위반 0 ‖ 파일 23 · 줄 1284 · 문자열 42330 (그중 <redacted> 17576) · 위반 0
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  파일 54 · 쓰기 호출 62 곳 · 원천 경로 대상 0 ‖ 읽기 전용 가짜 루트(파일 23) · pytest 266 passed in 17.58s · 트리 변경 0 · 17.7s ‖ 정적 위반 0 · 진입점 7 × 원천 아래 DB 경로 3 = 21 회 · 거부 21 · 생긴 항목 0 · 실제 루트 판정 OK · 1.0s
G-15  훅 설치 안전 — 가짜 settings (V-10)               미검증  가짜 settings (기존 이벤트 3) · 덧붙임 9 · 실제 파일 가드 5/5 거부 · 함정 0 · 남의 같은 이름 훅 덧붙임 9 · 남음 1 · 송신 미검증 (8095 사용 중) · 위반 0 ‖ tests/test_hooks_install.py: 18 passed in 1.64s
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)         PASS  host 127.0.0.1:8095 · 스캔 py 54 · 기타 15 · 외부 전송/바인드 위반 0
G-17  화면 6 · API 10 — HTTP 200                   PASS  화면 6 + API 10 = 16 중 HTTP 200 16 (빈 DB) · placeholder 0
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3          미검증  tests/test_graph.py: 6 passed in 0.31s ‖ — QA 재검증 필요(리포트 형식): outputs/qa2-상태대조.md 에 <!-- gate:G-18 --> 표지 판정 행 없음
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)            PASS  칸 88/88 · 근거(src) 없는 칸 0 · 원천 AI Coding/ 읽기만 ‖ 표본 10 일치 10 · 고려솔더/01 3/3 · 고려솔더/02 5/5 · 엘컴화인/00 5/5 · 와이엔프린팅/02 5/5 · 평창꽃순이김치/01 3/3 · 엘컴화인/01 3/3 · 평창꽃순이김치/04 7/7 · 엘컴화인/04 7/7 · 와이엔프린팅/04 7/7 · 광성정밀/04 7/7 ‖ 01 DONE v1.0 20261016-151506-all · 02 DONE v1.0 20261016-154028-all · 05 · 08 UNKNOWN ‖ tests/test_pipeline.py: 16 passed in 0.30s
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice          PASS  tests/test_usage_page.py: 7 passed in 0.35s
G-21  브라우저 — 콘솔 오류 0 · 390px                     미검증  — QA 재검증 필요(리포트 형식): outputs/qa2-상태대조.md 에 <!-- gate:G-21 --> 표지 판정 행 없음
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE           미검증  — QA 재검증 필요(리포트 형식): outputs/e2e/self-observe.md 에 <!-- gate:G-22 --> 표지 판정 행 없음
# 합계 PASS 17 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 5
```

QA1 판정과 다른 칸: **G-14** (`make gate` PASS ↔ QA1 FAIL — DEF-QA1-101, 그리고 QA1 판정이 gate 에 안 들어감 DEF-QA1-103) · **G-15** (`make gate` 미검증 = 8095 를 다른 프로세스가 사용 중 ↔ QA1 PASS, 송신은 8099 로 따로 잼). G-12 · G-18 · G-21 · G-22 미검증은 QA2 리포트 표지 몫(QA1 범위 밖).
