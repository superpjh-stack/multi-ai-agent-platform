# QA1 — 데이터 · 비용 · 진척 · 안전 (재검증 r3 · 웨이브 D3)

> 2026-10-17 18:20~18:40 KST · 코드 = 커밋 `4b42f08` (웨이브 D3) · QA DB `data/agentdash-qa1.db` 를 지우고 다시 백필 (`AGENTDASH_DB=data/agentdash-qa1.db make backfill` 3.8 s · 원천 파일 590 · agent 77/248/1/6 · usage_event 27,806 · parse_error 0)
> 기대값은 QA1 독립 스크립트(`outputs/qa1/*`, agentdash 를 import 하지 않음 — `cost_edge` · `hook_payload` · `pipe_fake` 만 개발 함수를 직접 불러 시험)로 다시 센 값이다. DEF-101 경로 변형은 판정만(실제 경로) + 가짜 루트에서 실제 `init_db` 시도로 쟀다.
> 원천은 읽기만 했다(실제 `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22e8f5…` 전 = 후, `~/.claude` 의 `*agentdash*` · `newdir*` 0, `~/.claude` 아래 `*.db` · `*.db-wal` 0). 본문은 옮기지 않았다(숫자 · 키 · 경로만). 고치지 않았다. 이전 리포트 `outputs/qa1-데이터안전.md` · `-r2.md` 는 그대로 둔다.

## 요약 — 게이트별 QA1 판정

<!-- gate:G-04 -->
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)  PASS  세션 77/77 · 서브에이전트 248/248 · 워크플로 에이전트 6/6 · S6 1/1 · 원천만 0 · DB만 0 (recount.py, r3)

<!-- gate:G-05 -->
G-05  파싱 오류율 ≤ 0.1% (V-07)  PASS  줄 166,160 (offset 까지) · 깨진 JSON 0 · 필수 필드 없는 assistant/user 0 (link_check.py · recount.py, r3)

<!-- gate:G-06 -->
G-06  부모 연결 ≥ 95% (V-02)  PASS  독립 연결 254/254 = 100% · 독립 부모 = DB parent_key 255/255 (워크플로 노드 포함, r3)

<!-- gate:G-07 -->
G-07  토큰 합 — 표본 10 세션 (V-03)  PASS  최종본 규칙 독립 집계 = DB 329/329 에이전트 4 칸 일치 (출력 21,233,951) · 옛 규칙 대비 차이 = 포크 최종본 90,584 (5 에이전트, r2 와 같음) · D-21 회귀 0 · 서브에이전트 출력 과소는 D-17 차단(표기 확인)

<!-- gate:G-08 -->
G-08  비용 — 표본 20 건 손계산 (V-09)  PASS  실제 표본 20/20 · 합성 경계 10/10 · 단가표 config = spec §6.1 (12 모델 불일치 0) · 전 기간 손계산 $4,526.061386 + 사본 최종본 $1.811680 = DB $4,527.873066

<!-- gate:G-13 -->
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  TEXT 356,958 값 중 300 자 초과 0 (최장 tool_call.target 222 = Read 경로) · 픽스처 본문 키 원문 0 (25 파일) · 훅 URL 호스트만

<!-- gate:G-14 -->
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  DEF-QA1-101 해결 — 실제 경로 변형 판정 원천 16/16 · 비원천·정상 허용 14/14 · 가짜 루트 init_db 시도 거부 16/16 · 생긴 항목 0 · 실제 원천 쓰기 0 · 남은 것 경미 DEF-QA1-201 (미리 만든 하드 링크)

<!-- gate:G-15 -->
G-15  훅 설치 안전 — 가짜 settings (V-10)  PASS  가짜 settings 덧붙임 9 · 제거 후 바이트 동일 (indent 2 · 4) · 남의 hook_send.sh 남음 1 · is_real_target 변형 5/5 True · 가짜 2/2 False · 송신 8099 0.027 s exit 0 · 0 B

<!-- gate:G-16 -->
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)  PASS  실측 TCP 127.0.0.1:8096 (LISTEN, QA1 PID 42985) · 외부 전송 import 0 · 0.0.0.0 0 · 외부 URL 은 CDN 고정 버전 1 개

<!-- gate:G-19 -->
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)  PASS  88 칸 · 근거 없는 칸 0 · 55 칸 독립 find = DB 55/55 · 표본 10/10 · P-01 2 칸 · ↻ 9 = 9 · 고려솔더 01·02 DONE v1.0 · 05·08 UNKNOWN · 가짜 루트 P-05 · 별칭 · 제외 폴더 spec 대로

<!-- gate:G-20 -->
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice  PASS  /usage [추정] API 정가 환산 4 곳 · 단가 없음 0 건 · reprice 바뀐 행 0 · event = daily = API rows = API total = trend $4,527.873066 · 작성 파일 2,276 = 고유 (agent, path) 2,276

**이전 결함 3 (r2): 해결 3.** (r1 DEF-002 는 D-17 차단 그대로 — 표기 확인.) **새 결함 1 — 치명 0 · 중대 0 · 경미 1.** 치명 기준(원천 쓰기 · 본문 저장 · 기존 훅 손상 · 외부 전송)이 실제로 일어난 일은 0.

| ID | 등급 | 담당 | 한 줄 |
|---|---|---|---|
| DEF-QA1-201 | 경미 | 아키텍트 (`settings.same_or_under` / `db/conn._refuse_source`) | 저장소 `data/` 에 **이미 있는** 하드 링크가 원천 파일을 가리키면 거부하지 않고 그 inode 에 쓴다 (사람이 미리 `ln` 해야만 — 코드 경로로는 생기지 않음) |

---

## 1. 이전 결함 해결표 (r2 DEF-QA1-101~103)

| ID | 이전 등급 | 판정 | 재현 다시 돌림 → 실측 |
|---|---|---|---|
| DEF-QA1-101 원천 판정 대소문자 구분 | 중대 | **해결됨** | r2 재현 그대로: 가짜 루트 `$S/CASEHOME/newdir/x.db` (`-m agentdash.db.conn`) · `$S/CaseHome/projects/y.db` (`-m agentdash.collect.backfill`) → 둘 다 `RuntimeError`, `newdir` · `y.db` 안 생김. 더 찌른 변형은 §2 (실제 경로 판정 원천 16 · 비원천 14 전부 기대대로, 가짜 루트 시도 16 전부 거부) |
| DEF-QA1-102 handback 뒤 사용량이 last_event_at 뒤 | 경미 | **해결됨** | `SELECT … FROM usage_event u JOIN agent a … WHERE u.at > a.last_event_at` → **0 에이전트 · 0 행** (r2 60 · 61 · 34,334 · $11.5749). tool_call.at > last_event_at 0. 예 `A:a38273d11e7939c22` last_event_at = 마지막 usage = 05:54:28.523Z (r2 01:19:01). last_event_at 뒤 남는 것은 tool **결과** 시각뿐: SubagentHandback 결과 150 (최대 +10 s, D-20 「handback 뒤 결과 제외」 설계대로) · Bash 1 (같은 초). last_event_at NULL 0 |
| DEF-QA1-103 QA1 판정이 gate 에 안 들어감 | 경미 | **해결됨** | `gate.py` `QA_GLOBS = ("outputs/qa*-*.md", "outputs/e2e/self-observe*.md")` · `qa_latest` 가 모든 게이트에 더함. progress-dev1 D3 기록: r2 표지로 G-14 FAIL 반영(개발 PASS). 이 리포트 작성 후 결과는 §6 |

## 2. DEF-QA1-101 변형 찌르기

### 2.1 실제 경로 — 판정만 (`is_source_path`, 열지 않음)

| 경로 (`~` = 실제 홈) | 판정 | 기대 |
|---|---|---|
| `~/.claude/newdir/x.db` · `~/.CLAUDE/newdir/x.db` · `~/.Claude/projects/x.db` · `~/.claude/PROJECTS/nonex/a/b/x.db` | True ×4 | 원천 |
| `/USERS/<u>/.claude/x.db` (상위 대소문자) · `/System/Volumes/Data/Users/<u>/.claude/x.db` (APFS firmlink) | True ×2 | 원천 |
| `~/desktop/ai coding/Other/x.db` · `~/DESKTOP/AI CODING/x.db` | True ×2 | 원천 |
| 저장소`/../Other/x.db` · 저장소`/data/../../Other/x.db` · 저장소`/data/nonex/../../../x.db` (없는 폴더 뒤 `..`) | True ×3 | 원천 |
| `~/.claude/./newdir/../x.db` · `~/Desktop//AI Coding///Zzz/x.db` · 문자열 `~/.claude/x.db` · `~/.CLAUDE/x.db` (물결 그대로) | True ×4 | 원천 |
| 저장소 형제 `Multi-agent Dashboard2/x.db` (접두 같은 다른 폴더, agents_root 아래) | True | 원천 |
| 저장소 대소문자 변형 `~/desktop/ai coding/multi-agent dashboard/data/x.db` | False | 저장소 (정체성 같음 — r2 의 과잉 거부도 없어짐) |
| `~/.claude2/x.db` · `~/.claude-backup/x.db` (접두만 같은 다른 폴더) · 저장소`/data/nonex/../../../../.claude/x.db` (= `~/Desktop/.claude`) | False ×3 | 원천 아님 |
| 정상: 저장소 `data/agentdash-qa1.db` · 상대 `data/x.db` · `data/new/sub/x.db` (없는 꼬리) · `outputs/x.db` · `tempfile` tmp · `/tmp/x.db` · `/private/tmp/x.db` · `~/Documents/x.db` · `~/Desktop/x.db` · NFD 로 쓴 저장소 경로 | False ×10 | 막지 않음 |

### 2.2 가짜 루트 — 실제 `init_db` 시도 (`AGENTDASH_CLAUDE_HOME=$S/casehome` · `AGENTS_ROOT=$S/caseagents`)

| DB 경로 | 결과 |
|---|---|
| `CASEHOME/newdir/x.db` · `CaseHome/projects/y.db` (backfill) | RuntimeError ×2 |
| 심볼릭 링크 `links/hlink → casehome` 의 `hlink/new/x.db` · 대소문자 `links/HLINK/new.db` · 끊어진 링크 `links/dangling → casehome/projects/nonex` 의 `dangling/x.db` | RuntimeError ×3 |
| `links/../casehome/n/x.db` · `links/z/../../casehome/x.db` (없는 폴더 뒤 `..`) · `links/z/y/../../../CASEHOME/projects/q.db` · `links/hlink/../casehome/k.db` | RuntimeError ×4 |
| 없는 꼬리 `casehome/a/b/c/d.db` · 끝 슬래시 `casehome/` · agents 루트 자체 `CaseAgents/x.db` | RuntimeError ×3 |
| NFD `caseagents/<고려솔더 프로젝트 NFD>/x.db` · NFD+대문자 `CASEAGENTS/<NFD>/new/x.db` | RuntimeError ×2 |
| 저장소 안 심볼릭 링크로 예외 우회: `data/qa1r3-link → casehome` 의 `…/new/x.db` · `data/qa1r3-alink → caseagents` 의 `…/x.db` | RuntimeError ×2 (링크는 끝에 지움) |
| 저장소 `data/` 안 하드 링크 → 가짜 원천 파일 | **DB 생성 · 원천 inode 에 씀** → DEF-QA1-201 |
| 정상: 저장소 `data/qa1r3-ok.db` · 스크래치 `okdir/ok.db` | 생성됨 (지움) |

거부된 시도 16 회 뒤 `find $S -name '*.db*' -o -name new` 0 — 폴더도 만들지 않았다.

### 2.3 `hooks_install.is_real_target` (판정만)

`~/.claude/settings.json` · `~/.CLAUDE/SETTINGS.JSON` · `/System/Volumes/Data<홈>/.claude/settings.json` · 스크래치 심볼릭 링크 → 실제 settings.json · `~/.claude/x/../settings.json` → True 5/5. 가짜 `$S/casehome/settings.json` · `data/settings.json` → False 2/2.

## 3. 회귀 재집계 (D-21 `core/linker.py` · D3 `last_event_at`)

| 게이트 | r2 (8606bc8) | r3 (4b42f08) | 변화 해석 |
|---|---|---|---|
| G-04 | 77/245/6/1 | 77/248/6/1 · 빠짐 0 · 남음 0 | 원천 증가(이 루프의 서브에이전트) |
| G-05 | 줄 164,747 · 오류 0 | 166,160 · 오류 0 | 원천 증가 |
| G-06 | 251/251 · 252/252 | 254/254 · 255/255 | 같은 100% — D-21 linker 변경이 parent_key 를 바꾸지 않음 |
| G-07 | 326/326 · 출력 21,202,606 | 329/329 · 21,233,951 · 표본 10 세션 중 8 일치 + 2 (dbd09a2a +84,917 · 8f3a6abd +5,667) = 포크 최종본 몫 | 옛 규칙 차이 = fork_final 90,584 그대로 (5 에이전트 같음) |
| G-08 | $4,515.862501 + 1.811680 | $4,526.061386 + 1.811680 = $4,527.873066 · 표본 20/20 · 경계 10/10 | 같은 구조 |
| G-19 | 88 · 55/55 · 10/10 · ↻ 9 | 같음 | 진척은 `file_touch.at` 만 — last_event_at 무관 |
| G-20 | $4,517.674181 · 파일 2,272 | $4,527.873066 (event = daily = rows = total = trend) · 파일 2,276 = 고유 2,276 · reprice 바뀐 행 0 · 비용 NULL 0 | 같은 구조 |
| D-17 표기 | undercount_output 7,945,095 | 7,963,790 = DB 서브+워크플로 출력 합 7,963,790 | 표기 붙음 · 숫자 일치 |

`r2_last_event.py`: 기록 331 중 DB last_event_at = 모든 줄 최대 181 · 나머지 150 = handback 꼬리 제외(전부 SubagentHandback 결과만 뒤에 있음, §1). 세션 O-1(queue-operation 등으로 늘어남, 최대 155,389 s)은 r2 와 같음.

`stream_heuristic.py` (D-17 참고): 서브 12,272/17,831 (68.8%) · 워크플로 60/85 · 하한 추정 4,194,883 — 원천 증가분만큼 늘었을 뿐 같은 비율.

## 4. 새 결함

### DEF-QA1-201 · 경미 · 아키텍트 (`src/agentdash/settings.py` `same_or_under` · `db/conn.py` `_refuse_source`) — 미리 만든 하드 링크는 막지 못한다

- **재현 (가짜 루트만)**: `: > $S/casehome/projects/h.db; ln $S/casehome/projects/h.db data/qa1r3-hl.db; AGENTDASH_CLAUDE_HOME=$S/casehome AGENTDASH_AGENTS_ROOT=$S/caseagents AGENTDASH_DB=data/qa1r3-hl.db uv run python -m agentdash.db.conn` → 거부 없이 `DB …` · 가짜 원천 `h.db` 링크 수 2 · 크기 0 → 90,112 B (스키마가 원천 inode 에 쓰임). 링크는 지움.
- **원인**: 판정이 「경로가 어느 폴더 아래인가」(조상 inode)만 본다 — 파일 자체가 원천 파일과 같은 inode 인지는 모른다. 디렉터리 하드 링크는 APFS 에서 안 되므로 파일 하나에만 해당.
- **등급 근거**: 사람이 원천 파일을 저장소 안에 일부러 `ln` 해 둔 경우에만 열린다 — 코드 · 환경변수 오설정만으로는 생기지 않는다(DEF-003 · 101 은 환경변수 1 개로 열렸다). 그래서 경미.
- **기대(예)**: `_refuse_source` 에서 경로가 이미 있는 일반 파일이고 `st_nlink > 1` 이면 거부(또는 경고), `-wal` · `-shm` 도 같이.

### 관찰 (결함 아님)

- O-1 (r2 그대로): 세션 `last_event_at` 이 `queue-operation` 등 줄까지 따라감 — spec 「마지막 기록」 글자대로.
- O-2 (r2 그대로): `hooks_install` 제거는 식별 항목 통째로 지운다 · 저장소 이동 시 옛 항목 못 알아봄.
- O-3: 백필만으로는 `pipeline_cell` 이 0 — 서버가 첫 `/api/v1/pipeline` 에서 채운다(88). QA1 `pipe_check.py` 는 서버를 한 번 띄운 뒤에 돌려야 한다(스크립트 쪽 순서 문제, 제품 결함 아님).
- O-4: `hook_payload.py` Notification `message` 앞 120 자(필터) 는 spec 허용 — r1 · r2 와 같음.

## 5. 이번 회차 실행

`recount.py --seed 7` · `r2_final.py` · `link_check.py` · `fork_final.py` · `global_cost.py` · `cost_check.py --seed 3` · `cost_edge.py` · `stream_heuristic.py` · `text_scan.py` · `fixture_scan.py` · `pipe_check.py --seed 5` · `pipe_fake.py` · `r2_last_event.py` · `hook_payload.py` · `hooks_fake.sh` (가짜 settings 만) · `make reprice` (qa1 DB) · 서버 8096 (qa1 DB · `AGENTDASH_NO_WATCH=1`, PID 42980/42985 — 끝에 종료, 8096 LISTEN 0). 경로 변형 프로브는 스크래치(저장소 밖) 스크립트 — 판정만.

## 6. `make gate` 판정표 (기본 DB, 리포트 작성 뒤 — 붙여 넣은 출력, gate 는 위 표지 줄만 읽는다)

```
# make gate — 2026-10-17 18:38:18 (goal.md §2)
G-01  골격 — make setup · 테이블 11                   PASS  tests/test_schema.py: 5 passed in 0.03s ‖ agentdash.db 테이블 11
G-02  파서 회귀 — 픽스처 S1~S6 · S9 (V-08)              PASS  tests/test_parsers.py: 29 passed in 0.15s
G-03  증분 읽기 — 추가분 · 반쪽 줄 · inode                 PASS  tests/test_tail.py: 9 passed in 0.21s
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)           PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 세션 77/77 · 서브에이전트 248/248 · 워크플로 에이전트 6/6 · S6 1/1 · 원천만 0 · DB만 0 (recount.py, r3) ‖ 개발: 원천 77 · DB 77 · 빠짐 0 · 남음 0 (18:37:34 · 직전 증분 수집 바뀐 키 3) ‖ 원천 248 · DB 248 · 빠짐 0 · 남음 0 (18:37:34 · 직전 증분 수집 바뀐 키 3) ‖ 원천 6 · DB 6 · 빠짐 0 · 남음 0 (18:37:34 · 직전 증분 수집 바뀐 키 3)
G-05  파싱 오류율 ≤ 0.1% (V-07)                       PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 줄 166,160 (offset 까지) · 깨진 JSON 0 · 필수 필드 없는 assistant/user 0 (link_check.py · recount.py, r3) ‖ 개발: 오류 0 / 줄 167006 = 0.0000% (상한 0.1%) · 파일 590
G-06  부모 연결 ≥ 95% (V-02)                         PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 독립 연결 254/254 = 100% · 독립 부모 = DB parent_key 255/255 (워크플로 노드 포함, r3) ‖ 개발: 원천 서브에이전트+워크플로 에이전트 254 중 연결 254 = 100.0% · L-01=236 L-02=12 L-03=6 · 워크플로 노드 1 중 1 · 줄 166735 · 2.1s ‖ agentdash.db 서브에이전트 248 · 워크플로 에이전트 6 중 부모 있음 254 = 100.0% (기준 ≥ 95%) · 부모 미확인 0 · 워크플로 노드 1 중 1
G-07  토큰 합 — 표본 10 세션 (V-03)                     PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 최종본 규칙 독립 집계 = DB 329/329 에이전트 4 칸 일치 (출력 21,233,951) · 옛 규칙 대비 차이 = 포크 최종본 90,584 (5 에이전트, r2 와 같음) · D-21 회귀 0 · 서브에이전트 출력 과소는 D-17 차단(표기 확인) ‖ 개발: 원천 출력 1638439 · DB 1638439 · 입력 11598/11598 · 캐시읽기 1237354145/1237354145 · 캐시쓰기 20468291/20468291 · 자기+자손 = · 에이전트 65 · 파일 65 · 에이전트별 소유 불일치 0 · 세션 안 requestId 중복 0 ‖ 원천 출력 2126284 · DB 2126284 · 입력 44386/44386 · 캐시읽기 830382477/830382477 · 캐시쓰기 22981813/22981813 · 자기+자손 = · 에이
G-08  비용 — 표본 20 건 손계산 (V-09)                    PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 실제 표본 20/20 · 합성 경계 10/10 · 단가표 config = spec §6.1 (12 모델 불일치 0) · 전 기간 손계산 $4,526.061386 + 사본 최종본 $1.811680 = DB $4,527.873066 ‖ 개발: 일치 20/20 · 손계산 합 $2.555321 · 단가표 2026-10-06 · 표본 종류 1h,5m,claude-fable-5-1,claude-opus-4-8,claude-opus-5,claude-opus-5-5,claude-sonnet-5,speed 없음(옛 기록),무작위 · 기록에 speed=fast 0 건 (fast 는 tests/test_cost.py 로) ‖ 없음 (0 건) · 비용 NULL 행 0 · 기록 모델 5 ‖ tests/test_cost.py: 13 passed in 0.02s
G-09  판정 규칙 13 — 표 기반 테스트                        PASS  개발 PASS · QA PASS ‖ QA outputs/qa2-상태대조-r3.md PASS: r3 회귀 tests/test_state.py 55 passed (D-18 · D-19 · 90/300 초 정각 포함) · 전체 pytest 296 passed ‖ 개발: tests/test_state.py: 55 passed in 0.18s
G-10  연결 규칙 L-01~L-07 테스트                        PASS  개발 PASS · QA PASS ‖ QA outputs/qa2-상태대조-r3.md PASS: r3 회귀 tests/test_linker.py 26 passed (+ D-21 test_L07_billed_reply_after_handback_is_not_a_rewake) · 실제 반환 뒤 사용량 줄 에이전트 65 판정 일치 ‖ 개발: tests/test_linker.py: 26 passed in 0.19s
G-11  실시간 — SSE 5 초 · 훅 1 초                      PASS  개발 PASS · QA PASS ‖ QA outputs/qa2-상태대조-r3.md PASS: r3 회귀 tests/test_realtime.py 4 passed · 실제 서버 감시기/10 초 판정이 오케스트레이터 RUNNING→SLEEPING(09:34:41Z, 마지막 기록 + 304 초) · QA1 반환 → DONE (self-observe-r3) ‖ 개발: tests/test_realtime.py: 4 passed in 12.05s
G-12  상태 대조 — 표본 30 오판 ≤ 2                       PASS  r3 새 표본 30 (STALE 8 전부 · FAILED 4 새 · 재기상 4 새 · SLEEPING 오케스트레이터 1 · RUNNING 2 · WAITING_INPUT 2 · DONE 9 중 D-21 반환 뒤 사용량 줄 5) 가설(D-14·18·19) 기준 오판 0 · spec 글자 기준 오판 1 (S:2bee9170 SLEEPING vs STALE R-02b, D-18) · 전수 331 가설 0 / 글자 1 · D-21 회귀 없음 (QA outputs/qa2-상태대조-r3.md)
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)        PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: TEXT 356,958 값 중 300 자 초과 0 (최장 tool_call.target 222 = Read 경로) · 픽스처 본문 키 원문 0 (25 파일) · 훅 URL 호스트만 ‖ 개발: agentdash.db 테이블 11 · 행 64224 · TEXT 값 358832 · 상한 300 자 · 위반 0 ‖ 파일 23 · 줄 1284 · 문자열 42330 (그중 <redacted> 17576) · 위반 0
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: DEF-QA1-101 해결 — 실제 경로 변형 판정 원천 16/16 · 비원천·정상 허용 14/14 · 가짜 루트 init_db 시도 거부 16/16 · 생긴 항목 0 · 실제 원천 쓰기 0 · 남은 것 경미 DEF-QA1-201 (미리 만든 하드 링크) ‖ 개발: 파일 54 · 쓰기 호출 62 곳 · 원천 경로 대상 0 ‖ 읽기 전용 가짜 루트(파일 23) · pytest 296 passed in 19.36s · 트리 변경 0 · 19.5s ‖ 정적 위반 0 · 진입점 7 × 원천 아래 DB 경로 7 = 49 회 · 거부 49 · 생긴 항목 0 · 실제 루트 판정 OK · 2.4s
G-15  훅 설치 안전 — 가짜 settings (V-10)               미검증  개발 미검증 · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 가짜 settings 덧붙임 9 · 제거 후 바이트 동일 (indent 2 · 4) · 남의 hook_send.sh 남음 1 · is_real_target 변형 5/5 True · 가짜 2/2 False · 송신 8099 0.027 s exit 0 · 0 B ‖ 개발: 가짜 settings (기존 이벤트 3) · 덧붙임 9 · 실제 파일 가드 5/5 거부 · 함정 0 · 남의 같은 이름 훅 덧붙임 9 · 남음 1 · 송신 미검증 (8095 사용 중) · 위반 0 ‖ tests/test_hooks_install.py: 19 passed in 1.66s
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)         PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 실측 TCP 127.0.0.1:8096 (LISTEN, QA1 PID 42985) · 외부 전송 import 0 · 0.0.0.0 0 · 외부 URL 은 CDN 고정 버전 1 개 ‖ 개발: host 127.0.0.1:8095 · 스캔 py 54 · 기타 15 · 외부 전송/바인드 위반 0
G-17  화면 6 · API 10 — HTTP 200                   PASS  개발 PASS · QA PASS ‖ QA outputs/qa2-상태대조-r3.md PASS: r3 check_routes 16/16 HTTP 200 · placeholder 0 · 실제 DB 로 D-01~D-06 + D-03 열림 ‖ 개발: 화면 6 + API 10 = 16 중 HTTP 200 16 (빈 DB) · placeholder 0
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3          PASS  개발 PASS · QA PASS ‖ QA outputs/qa2-상태대조-r3.md PASS: r3 실제 DB 보기 3 (계층 · 협업 첫 그림 145 ms · 파이프라인) · 전체 368→137 접힘 231 "+N" 19 · /graph?project= 첫 로드 노드 18 = API 18 (DEF-QA2-103 해결) · 앱 콘솔 오류 0 ‖ 개발: tests/test_graph.py: 7 passed in 0.25s
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)            PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: 88 칸 · 근거 없는 칸 0 · 55 칸 독립 find = DB 55/55 · 표본 10/10 · P-01 2 칸 · ↻ 9 = 9 · 고려솔더 01·02 DONE v1.0 · 05·08 UNKNOWN · 가짜 루트 P-05 · 별칭 · 제외 폴더 spec 대로 ‖ 개발: 칸 88/88 · 근거(src) 없는 칸 0 · 원천 AI Coding/ 읽기만 ‖ 표본 10 일치 10 · 고려솔더/01 3/3 · 고려솔더/02 5/5 · 엘컴화인/00 5/5 · 와이엔프린팅/02 5/5 · 평창꽃순이김치/01 3/3 · 엘컴화인/01 3/3 · 평창꽃순이김치/04 7/7 · 엘컴화인/04 7/7 · 와이엔프린팅/04 7/7 · 광성정밀/04 7/7 ‖ 01 DONE v1.0 20261016-151506-all · 02 DONE v1.0 20261016-15402
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice          PASS  개발 PASS · QA PASS ‖ QA outputs/qa1-데이터안전-r3.md PASS: /usage [추정] API 정가 환산 4 곳 · 단가 없음 0 건 · reprice 바뀐 행 0 · event = daily = API rows = API total = trend $4,527.873066 · 작성 파일 2,276 = 고유 (agent, path) 2,276 ‖ 개발: tests/test_usage_page.py: 7 passed in 0.35s
G-21  브라우저 — 콘솔 오류 0 · 390px                     PASS  r3 D-01~D-06 + D-03 앱 콘솔 오류 0 · 390px iframe 6 화면 가로 스크롤 0 · D-01 · D-03 「가설 D-18」 표시 · D-03 「기록상 과소 (D-17)」 2 (QA outputs/qa2-상태대조-r3.md)
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE           PASS  서버 기동 09:01:56Z 뒤 QA1 A:aa6e2ae7 · QA2 A:a6b4391e RUNNING R-09 09:02:00Z (spawn 엣지 S:2bee9170) → QA1 handback 09:12:08.811Z → DONE R-08 09:12:09Z (< 1 초) · 오케스트레이터 SLEEPING R-03 깰 시각 09:30:46Z (09:06:05Z) → RUNNING 09:12:09Z · 기동 뒤 새 에이전트 A:a5b119ea meta 09:12:40.397Z → RUNNING 09:12:40Z (< 1 초) · 파 (QA outputs/e2e/self-observe-r2.md)
# 합계 PASS 21 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 1
```

QA1 판정과 다른 칸: **G-15** 하나 (`make gate` 미검증 = 개발 도구 송신 시험이 「8095 사용 중」 — 8095 LISTEN 은 QA1 프로세스가 아님(PID 41666, 건드리지 않음) ↔ QA1 PASS, 송신은 8099 로 따로 잼). gate 는 더 나쁜 쪽(미검증)을 냈다 — 규칙대로. QA1 r3 표지 11 게이트(G-04~G-08 · G-13~G-16 · G-19 · G-20) 전부 `QA outputs/qa1-데이터안전-r3.md PASS` 로 읽힘 → DEF-QA1-103 해결 확인. G-14 는 r2 FAIL → r3 PASS 로 바뀜.
