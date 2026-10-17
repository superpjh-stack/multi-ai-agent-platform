# QA1 — 데이터 · 비용 · 진척 · 안전 (웨이브 C)

> 2026-10-17 17:06~17:30 KST · 코드 = 커밋 `10cbd18`(웨이브 B) · QA DB `data/agentdash-qa1.db` (`AGENTDASH_DB=data/agentdash-qa1.db make backfill` 3.8 s)
> 기대값은 `spec.md` · `config/*.yaml` · 원천을 **QA1 독립 스크립트**(`outputs/qa1/*`, agentdash 를 import 하지 않음 — 표시한 3 개만 예외)로 다시 센 값이다.
> 원천은 읽기만 했다. 본문은 옮기지 않았다(숫자 · 키 · 경로만). 고치지 않았다.

## 요약

| 게이트 | `make gate` (기본 DB · qa1 DB) | **QA1 판정** | 근거 한 줄 |
|---|---|---|---|
| G-04 전체 수집 | PASS · PASS | **PASS** | 세션 77/77 · 서브에이전트 239/239 · 워크플로 에이전트 6/6 · S6 1/1 (키 집합 동일) |
| G-05 파싱 오류율 | PASS · PASS | **PASS** | 줄 162,202 · 깨진 JSON 0 · 필수 필드 없는 assistant/user 0 |
| G-06 부모 연결 | PASS · PASS | **PASS** | 독립 연결 245/245 = 100% · 독립 부모 = DB parent_key 246/246 (워크플로 노드 포함) |
| G-07 토큰 합 | PASS · PASS | **FAIL** | 320 에이전트 전부 개발 규칙과는 일치. 그러나 포크 사본에 남은 최종 usage 를 버려 표본 세션 2 개(8f3a6abd · dbd09a2a)의 출력이 90,584 적다 → DEF-QA1-001. 서브에이전트 기록 자체의 출력 과소 → DEF-QA1-002 |
| G-08 비용 | PASS · PASS | **PASS** | 실제 표본 20/20 · 합성 경계 10/10 · 전 기간 전 에이전트 손계산 $4,492.862637 = DB (320/320) · 단가표 config = spec §6.1 |
| G-13 본문 미저장 | PASS · PASS | **PASS** (경미 1) | TEXT 350,234 값 중 300 자 초과 0 · 상위 20 은 전부 경로 · 픽스처 본문 0. 훅 detail 에 URL 쿼리 남음 → DEF-QA1-007 |
| G-14 원천 무접촉 | PASS · PASS | **FAIL** | 실제 원천 쓰기는 0. 그러나 `AGENTDASH_DB` 를 잘못 주면 `init_db` 가 거부하기 **전에** 원천 아래 폴더를 만든다(가짜 루트 재현) — `check_readonly` 가 못 잡음 → DEF-QA1-003 |
| G-15 훅 설치 안전 | 미검증 · 미검증 (8095 사용 중) | **FAIL** | 가짜 settings 설치 → 9 덧붙임 · 제거 후 바이트 동일 · 송신 0.03 s exit 0 · 0 B 는 통과. 그러나 `--yes` 가드 우회(DEF-QA1-004) · 남의 `hook_send.sh` 훅 삭제(DEF-QA1-005) |
| G-16 로컬 전용 | PASS · PASS | **PASS** | 실측 `TCP 127.0.0.1:8096 (LISTEN)` · 외부 전송 import 0 · 외부 URL 은 CDN 고정 버전 1 개 |
| G-19 진척 판정 | PASS · PASS | **PASS** | 55 칸(01·02·03·04·00) have/need · 버전 · 실행 · 마지막 시각 `find` 독립 = DB 55/55 · P-01 2 칸 · ↻ 9 칸 일치 · 고려솔더 01·02 DONE v1.0 · 05·08 UNKNOWN |
| G-20 비용 화면 | PASS · PASS | **PASS** (경미 1) | `[추정] API 정가 환산` 4 곳 · 「단가 없음 0 건」 · reprice 뒤 API = event = daily $4,492.8626. 작성 파일 열 과다 → DEF-QA1-006 |

**결함 8 — 치명 0 · 중대 5 · 경미 3.** 치명 기준(원천 쓰기 · 본문 저장 · 기존 훅 손상 · 외부 전송)에 해당하는 일이 **실제로 일어난 것은 0** 이다. DEF-003 · 004 · 005 는 환경변수 오설정 · 특정 설정에서만 열리는 **잠재 경로**이고, 안전 게이트 도구가 못 잡아 PASS 를 낸다(게이트 오판) → 중대로 올렸다.

| ID | 등급 | 담당 | 한 줄 |
|---|---|---|---|
| DEF-QA1-001 | 중대 | 개발1 | 포크 사본의 '더 최종인' usage 를 버림 — requestId 128 · 출력 −90,584 · −$1.811680 |
| DEF-QA1-002 | 중대 | 아키텍트 (D-01 재결정) · 개발1 | 서브에이전트 기록의 `output_tokens` 는 스트리밍 시작값 — 요청 68.4% 의심 · 하한 추정 ≈ 4.1M 출력 과소 |
| DEF-QA1-003 | 중대 | 아키텍트 (`db/conn.py`) | `init_db` 가 원천 거부 검사보다 먼저 `mkdir` — 원천 아래 폴더 생성 |
| DEF-QA1-004 | 중대 | 개발2 (`scripts/hooks_install.py`) | `--yes` · pytest 거부가 '설정된' claude_home 기준 — 가짜 home 환경에서 실제 settings.json 에 확인 없이 쓰기 가능 |
| DEF-QA1-005 | 중대 | 개발2 (`scripts/hooks_install.py`) | 식별 표시가 파일 이름 `hook_send.sh` 부분 문자열 — 남의 같은 이름 훅을 '내 것' 으로 보고 설치 건너뜀 · 제거 때 삭제 |
| DEF-QA1-006 | 경미 | 개발1 (`core/usage.py`) | D-04 `files_written` = 일별 고유 수의 합 — 전 기간 2,277 vs 고유 2,262 |
| DEF-QA1-007 | 경미 | 개발2 (`collect/hooks_rx.py`) | 훅 `detail.target` 에 WebFetch URL 전체(쿼리 포함 앞 80 자) 저장 |
| DEF-QA1-008 | 경미 | 아키텍트 (`settings.py`) | `is_source_path` 는 설정된 루트만 본다 — CLAUDE_HOME 과 DB 를 함께 잘못 주면 실제 `~/.claude` 아래 DB 를 막지 못함 |

---

## 1. 원천 재집계 — G-04 · G-05 · G-06 · G-07 · D-01 · D-02 · D-11

같은 시각 비교: 원천 각 파일은 **DB `src_file.offset` 바이트까지만** 읽는다(DB 가 읽은 지점). 이후 `make gate` 의 증분 수집 뒤 기본 DB · qa1 DB 둘 다 다시 돌려 같은 결론.

### 1.1 파일 수 (G-04) — PASS

`.venv/bin/python -I outputs/qa1/recount.py --db data/agentdash-qa1.db --seed 7`

| 종류 | 원천 (`glob`) | DB agent | 원천만 | DB만 |
|---|---|---|---|---|
| SESSION | 77 | 77 | 0 | 0 |
| SUBAGENT | 239 | 239 | 0 | 0 |
| WORKFLOW_AGENT | 6 | 6 | 0 | 0 |
| WORKFLOW (S6) | 1 | 1 | — | — |

`find ~/.claude/projects -name '*.jsonl' | wc -l` = 323 = 77 + 239 + 6 + journal 1 (분류 안 된 transcript 0). `--since 2026-08-01` 로 빠진 파일 0 (백필 원천 파일 572 = 전부).

### 1.2 파싱 · 줄 종류 (G-05 · D-11) — PASS

| 항목 | 실측 |
|---|---|
| 줄 종류 · 전체 줄 | 23 종 · 162,202 줄 (offset 까지) |
| 깨진 JSON · 필수 필드 없는 assistant/user | 0 · 0 (`outputs/qa1/link_check.py`) |
| `message.usage` 를 가진 줄 종류 | **assistant 만** (55,608 줄) — 다른 종류에서 빠뜨릴 토큰 없음 |
| `tool_use` 를 가진 줄 종류 | assistant 31,142 줄 · `api-request-blob` 121 줄 (id 178 개, **전부 assistant 에도 있음** → D-11 제외가 맞다, 빠뜨림 0) |
| `data.message` 안 usage (progress 류) | 0 |
| requestId 없는 assistant | 66 줄 — 전부 `<synthetic>` |
| `cache_creation_input_tokens` ≠ 5m + 1h | 0 줄 (DB 의 cache_write = 5m+1h 와 spec 정의 = 같은 값) |

### 1.3 부모 연결 (G-06) — PASS

`outputs/qa1/link_check.py`: meta `toolUseId` 와 같은 `Agent`/`Task` tool_use.id 를 같은 세션 폴더에서 찾음(여러 곳이면 세션 > 얕은 기록 > 이른 줄) · 워크플로 에이전트 → `W:<폴더>` · 워크플로 노드 → `toolUseResult.runId` 를 받은 기록.
결과: 245/245 연결 · 독립 부모 = DB `parent_key` **246/246** (qa1 DB · 기본 DB 둘 다).

### 1.4 토큰 · 도구 · 작성 파일 (G-07) — 독립 규칙

규칙(문서에서): assistant 줄만 · `<synthetic>` 제외 · 같은 requestId 는 **세션 전체에서 한 번**, 소유자 = 그 requestId 가 처음 나온 기록(가장 이른 timestamp, 같으면 얕은 깊이), 값 = 소유 기록 안 output 최대 줄. 도구 호출 = 세션 전체 고유 tool_use.id. 작성 파일 = Write · Edit · NotebookEdit 고유 `file_path`.

| 범위 | 결과 |
|---|---|
| 전 에이전트 320 | 토큰 4 칸 불일치 0 · 도구 호출 불일치 0 (30,846 = 30,846) · 작성 파일 불일치 0 · 합 입력 174,865 · 캐시 읽기 7,377,732,517 · 캐시 쓰기 185,019,222 · 출력 21,013,885 (원천 = DB) |
| D-01 | 같은 기록 안 같은 requestId 재등장 27,791 줄 · 그중 입력/캐시가 다른 묶음 0 · output 이 줄어든 줄 0 — '파일 안 최대' 규칙은 이중 계산을 막는다 |
| D-02 | 여러 기록에 걸친 requestId 중 포크와 무관한 것 0 — 부모 재기록 없음 확인 |

표본 10 세션 (시드 7 — 포크 세션 2 · 워크플로 세션 1 · 에이전트 최다 1 · 무작위 6, `F`=포크 `W`=워크플로)

| 세션 | 에이전트 | 입력 | 캐시 읽기 | 캐시 쓰기 | 출력 | 도구 | 작성 파일 | DB |
|---|---|---|---|---|---|---|---|---|
| bb4c0b68 F | 4 | 3,652 | 30,731,649 | 571,458 | 242,142 | 114 | 15 | 일치 |
| 8e810453 F | 4 | 2,058 | 20,322,028 | 867,367 | 161,843 | 112 | 3 | 일치 |
| 8f3a6abd FW | 15 | 3,012 | 398,527,253 | 5,383,760 | 1,352,668 | 1,557 | 76 | 일치 (단 DEF-001: 최종본 기준 출력 +5,667) |
| dbd09a2a F | 65 | 11,598 | 1,237,354,145 | 20,468,291 | 1,553,522 | 5,740 | 287 | 일치 (단 DEF-001: 최종본 기준 출력 +84,917) |
| ca14d7e7 | 1 | 32 | 984,254 | 86,661 | 12,449 | 22 | 1 | 일치 |
| 2bee9170 | 8 | 894 | 81,695,325 | 2,095,491 | 353,934 | 544 | 63 | 일치 |
| 30773d87 | 1 | 87 | 6,107,733 | 160,390 | 69,317 | 55 | 11 | 일치 |
| f6123745 | 1 | 93 | 10,008,234 | 362,501 | 56,067 | 56 | 0 | 일치 |
| 43a5ddd8 | 1 | 92 | 5,201,514 | 294,366 | 74,048 | 44 | 6 | 일치 |
| b6d22220 | 1 | 2,704 | 28,589,196 | 905,573 | 129,129 | 104 | 0 | 일치 |

**빠뜨리는 것 사냥 → DEF-QA1-001 · 002** (§6). D-02 사본 제외는 이중 계산은 막지만, 사본이 부모보다 **더 최종인** 값을 가진 경우 그 값을 버린다.

---

## 2. 비용 — G-08 · G-20

`.venv/bin/python -I outputs/qa1/cost_check.py --db data/agentdash-qa1.db --seed 3 --project=-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub` (단가는 spec §6.1 표를 스크립트에 옮겨 적은 값)

| 항목 | 실측 |
|---|---|
| config/pricing.yaml ↔ spec §6.1 | 모델 12 · 불일치 0 · spec 밖 모델 0 · 캐시 배수 5m 1.25 · 1h 2.0 · alias `claude-opus-5-5[1m]` · version 2026-10-06 |
| 실제 표본 20 건 (원천 줄 직접 손계산 vs DB `cost_usd`) | **20/20 일치** (≤ 1e-9) — 1h 3 · 5m 3 · speed 없음 2 · 모델 5 종 각 1 · 무작위 7. 예: opus-5 1h `in 2 · cr 527,716 · w1 6,687 · out 8` → 0.330938 = DB |
| 합성 경계 10 건 → 개발 `usage.cost()` (`uv run python outputs/qa1/cost_edge.py`) | **10/10 일치** — opus-5-5 fast ×2 (0.13) · opus-5 fast · opus-4-8 fast → NULL(spec 「빠른 모드 —」) · Haiku 5.5 프롬프트 100,000 → 1 구간 · 100,001 → 2 구간 (0.0060001 / 0.0300006 · 0.010005 / 0.0500255) · 모르는 모델 NULL · alias `[1m]` 0.0032 · 모델 None NULL |
| 전 기간 전 에이전트 손계산 (`outputs/qa1/global_cost.py`) | $4,492.862637 = DB $4,492.862637 · 에이전트 320 중 차이 > 1e-6 = 0 · 모델별 fable-5-1 1,958.2462 · opus-5 1,212.2787 · opus-5-5 906.7639 · sonnet-5 400.7338 · opus-4-8 14.8400 |
| 프로젝트 하나 (Standard-Data-Hub, 세션 1 · 기록 15 · 요청 1,477) | D-04 API `group=project` $145.2646126 · 출력 1,352,668 = 독립(소유 규칙) 값. 사본 최종본까지 쓰면 $145.298833 · 출력 1,354,379 (차 $0.034220 = 1,711 × $20/M — DEF-001) |
| 단가 없음 · NULL | 기록 모델 5 · 단가 없는 모델 0 · 비용 NULL 0 행 (`make pricing-check`) · 기록에 `speed=fast` 0 건 |
| G-20 화면 | 서버 8096 (qa1 DB · `AGENTDASH_NO_WATCH=1`) `/usage` 에 `[추정] API 정가 환산` 4 곳 · 「단가 없음 0 건」 · `make reprice` 행 27,227 · 바뀐 행 0 · event $4,492.8626 = daily = API total · `tests/test_usage_page.py` 7 passed |

---

## 3. 진척 — G-19 · D-15

`.venv/bin/python -I outputs/qa1/pipe_check.py --db data/agentdash-qa1.db --seed 5` — `find -type f` 이름 · mtime 만, run.json 은 `started` 와 회사 키 값 안 사전 이름 유무만, progress.md 는 줄 번호만. pipeline_cell 은 `AGENTDASH_DB=data/agentdash-qa1.db uv run python -m agentdash.core.pipeline` 로 채움(88 칸 · DONE 53 · NEEDS_DECISION 2 · UNKNOWN 33).

| 항목 | 실측 |
|---|---|
| 근거(src) 없는 칸 | 0 / 88 |
| 01·02·03·04·00 55 칸 have/need · 최고 버전 · 실행 폴더 · 마지막 파일 시각 | 독립 = DB **55/55** |
| 무작위 10 칸 (시드 5) | 10/10 — 와이엔프린팅 04 7/7 · 니즈푸드 01 3/3 · 임진강김치 02 5/5(P-01) · 브랜뉴머시너리 02 5/5 · 평창꽃순이김치 00 5/5 · 원터치 04 7/7 · 평창꽃순이김치 02 5/5 · 원터치 01 3/3 · 엘컴화인 03 3/3 · 경동글로벌텍 01 3/3 |
| NEEDS_DECISION 2 칸 | 02 니즈푸드 · 임진강김치 = 독립 (`02 Design Agent/progress.md` 911 행 `## 지금 해야 할 것` 절 안 913 · 921 (임진강) · 946 (니즈) 행 `### ` 표제에 키워드 있음 — awk 로 직접 확인). 다른 단계 0 = 0 |
| ↻ 뒤처짐 | 독립 9 = DB 9 (차이 0). 직접 확인 3 칸: 고려솔더 03 (03 최신 mtime 09-02 11:53 < 02 run.json started 10-16 15:40) · 송월타월서울상사 04 (04 최신 09-10 09:12 < 03 최신 09-10 09:24) · 임진강김치 03 (08-22 13:57 < 02 run 10-04 15:22) — `stat -f %Sm` |
| 고려솔더 | 01 DONE v1.0 `20261016-151506-all` · 02 DONE v1.0 `20261016-154028-all` · 05 · 08 UNKNOWN (P-07) · 05/06/08 열 UNKNOWN 각 11 |
| D-15 NFD | outputs 아래 NFD 이름 47 개. NFC 없이 세면 니즈푸드 04 → 6 · 경동글로벌텍 00 → 4 로 떨어짐 → NFC 처리가 맞다 |
| D-15 `{사업}` | `제조AI` 만 쓰면 니즈푸드 · 임진강김치 03 · 04 → 0 (NOT_STARTED 오판) → `스마트공장` 추가가 맞다 |
| 미등록 회사 | 5 단계 패턴의 `{회사}` 자리에 사전 밖 이름 0. 가짜 agents_root(`uv run python outputs/qa1/pipe_fake.py <빈 스크래치 폴더>`) 에 `두손푸드` 파일 · `pm-두손푸드/` 를 두면 칸 없이 미등록 1 건 · NFD 3 개 섞인 니즈푸드 04 → DONE 7/7 · 별칭 `송월` → 송월타월서울상사 · `_구판_*`/`tour/` 만 있는 칸 → NOT_STARTED · P-05 (표제 완료 · 파일 0) → DONE ⚠ · `## 지금 해야 할 것` 의 표 행 → P-01 · 그 절 밖 표제 → P-01 아님 — 전부 spec 대로 |

관찰(결함 아님): 「미등록 회사 N 건」 은 이름 수다(같은 이름 두 곳 = 1 건). 고려솔더 03 화면설명서 칸은 같은 v1.0 중 mtime 이 늦은 `…_화면설명서_신규3건포함_v1.0.html` 을 고른다(spec 「가장 높은 v · 가장 최근」 대로).

---

## 4. 안전 사냥 — G-13 · G-14 · G-15 · G-16

### 4(a) `src/` · `scripts/` 쓰기 경로 전수 (직접 읽음)

`grep -rnE "open\(|write_text|write_bytes|unlink|\.rename|os\.replace|shutil|sqlite3\.connect|mkdir|chmod|…" src scripts`

| 쓰기 지점 | 대상 | 원천으로 갈 길 |
|---|---|---|
| `db/conn.py` `init_db` `p.parent.mkdir` → `connect` `sqlite3.connect` | `AGENTDASH_DB` | **있음** — mkdir 이 `_refuse_source` 보다 먼저 (DEF-QA1-003). 거부는 설정된 루트 기준 (DEF-QA1-008) |
| `core/usage.py` export `write_text` | `ROOT/outputs/…` | 없음 — `is_source_path` + `ROOT in parents` 검사 뒤 mkdir |
| `scripts/hooks_install.py` `atomic_write` · 백업 `write_bytes` | `--settings` 경로 (사람이 실제 파일에) | 설계상 원천 쓰기. 가드 우회 (DEF-QA1-004) |
| `scripts/make_fixture.py` `rmtree` · `write_text` | `tests/fixtures/<ver>` | 없음 (저장소 안 확인 후) |
| `tools/check_hooks.py` `write_bytes` · `rmtree` | `mkdtemp` | 없음 (`is_source_path` 검사) |
| `tools/check_no_payload` · `check_link_rate` `sqlite3.connect` | DB `mode=ro` | 없음 |
| 그 밖 `open(…,"rb")` · `read_text` (ingest · tail · linker · pipeline · agents 원본 보기) | 원천 | 읽기만 |

가짜 루트 재현 (`AGENTDASH_CLAUDE_HOME=<스크래치>/home` · `AGENTDASH_AGENTS_ROOT=<스크래치>/agents`):

| 경우 | 결과 |
|---|---|
| `AGENTDASH_DB=<home>/newdir/x.db uv run python -m agentdash.db.conn` | RuntimeError(거부) — **그러나 `<home>/newdir` 폴더가 생김** |
| `AGENTDASH_DB=<home>/newdir2/y.db … agentdash.collect.backfill` | 거부 — `<home>/newdir2` 생김 |
| `AGENTDASH_DB=<agents>/Other Project/sub/x.db` (읽기 전용 폴더) | PermissionError — 원천 아래 mkdir 을 **시도**함 |
| CLAUDE_HOME 을 다른 곳으로 + DB 를 '진짜' 원천 자리(대역)로 | 거부 없이 테이블 11 생성 (DEF-QA1-008) |

### 4(b) DB TEXT 열 본문 여지 — PASS

`.venv/bin/python -I outputs/qa1/text_scan.py --db data/agentdash-qa1.db --top 20` (값은 QA 눈으로만 봤다)

| 항목 | 실측 |
|---|---|
| 테이블 · 열 · 행 · TEXT 값 | 11 · 94 · 62,750 · 350,234 · 300 자 초과 0 |
| 열별 최대 | tool_call.target 222 (Read 경로) · pipeline_cell.src 208 · src_file.path 193 · file_touch.path 161 · agent.project_key/path 85 · state_log.reason 77 · pipeline_cell.note 75 |
| 긴 값 상위 20 | tool_call.target 2 (Read 의 file_path) · pipeline_cell.src 1 (`config/pipeline.yaml …:줄` 근거) · src_file.path 17 — **전부 경로/근거, 본문 0** |
| 도구별 target 최대 | Bash 120 (description) · Agent 54 · Monitor 78 · Skill 31 · WebFetch 21 (호스트) · SendMessage 17 · ScheduleWakeup 25 · mcp__* 0 (target 없음) |
| 본문 의심 패턴 | '명령 꼴' 101 = 전부 Bash description(≤ 120, spec 허용) · '키 꼴' 1 = 오탐(`…sk-notification…`) · 프롬프트 꼴 0 |
| hook_event | qa1 DB 0 행. 합성 페이로드(`uv run python outputs/qa1/hook_payload.py`) — prompt · command · content · tool_response · last_assistant_message 의 표지 문자열이 detail 에 남은 것 0. 남는 것: Notification message 앞 80 자(spec 허용) · **WebFetch url 쿼리** (DEF-QA1-007) |
| state evidence | state_log.reason 최대 77 · 규칙 코드 + 숫자 |

### 4(c) 픽스처 본문 누출 — PASS

`.venv/bin/python -I outputs/qa1/fixture_scan.py` (검사기와 별도 — 키별 '<redacted> 아닌 문자열' 수 · 최대 길이)
파일 25 (README 2 포함) · JSON 단위 1,295 · JSON 아님 0. 원문으로 남은 키 중 30 자 이상: scriptPath 175 · file_path 154 · filePath 154 · hash/shapeHash/requestDigest 64 · cwd 56 · description 40 (도구 스키마 설명 앞 40 자) · name 34 (도구 이름) · id 류 36. 본문 키(text · thinking · content · command · prompt · result …) 원문 0. README 는 처리 표(경로 · 줄 수)만. `scripts/check_fixtures_redacted.py` PASS (위반 0) 와 같은 결론.

### 4(d) `hooks_install.py` — 가짜 settings 로만 (`bash outputs/qa1/hooks_fake.sh <빈 스크래치 폴더>`)

가짜 settings = 실제와 같은 구조(최상위 키 9 · PostToolUse 3 · PreToolUse 1 · Stop 1 · 한글 그대로 · indent 2). 실제 파일은 `json.dumps(indent=2, ensure_ascii=False)+"\n"` 와 **바이트 동일**함을 읽기로 확인(설치 때 재직렬화가 실제 파일의 다른 줄을 바꾸지 않음).

| 경우 | 결과 |
|---|---|
| A 설치 `--yes` | exit 0 · 덧붙임 9 · 기존 hooks 항목 동일 · hooks 밖 키 동일 · 원본 줄이 순서대로 전부 남음 · 백업 1 |
| A 두 번 설치 | 식별 항목 9 그대로 (중복 0) |
| A 제거 `--uninstall --yes` | **원본과 바이트 동일** (`cmp`) |
| B indent 4 파일 | 설치 → 제거 후 바이트 동일 |
| C 설치 뒤 사람이 Stop 훅 추가 → 제거 | 사람 훅 남음 1 · 식별 항목 0 |
| **D 남의 `/other/project/hook_send.sh` 훅이 이미 있음** | 설치: Stop 건너뜀 → 덧붙임 **8/9** · 제거: 남의 훅 **삭제됨** (DEF-QA1-005) |
| E `--yes` 없이 · stdin 닫힘 | diff 출력 뒤 `취소` · exit 1 · 파일 그대로 · 백업 0 |
| **F claude_home 이 가짜일 때 다른 settings.json `--yes`** | exit 0 로 씀. `is_real_target(~/.claude/settings.json)` = False (가짜 home) · True (환경변수 없음) · pytest 중 + 가짜 home = False (DEF-QA1-004) |
| G 송신 `hook_send.sh` (서버 꺼짐, 포트 8099) | exit 0 · stdout 0 B · 0.03 s |
| 관찰: 송신 — 응답 안 하는 127.0.0.1 서버 | 1.029 s · exit 0 · 0 B (`curl -m 1` + 프로세스 시작. 훅 timeout 5 s 라 영향 없음, G-15 기준은 '서버 꺼짐') |

**실제 경로가 기본값일 때 `--yes` 없이 실수로 실행되면 (코드 판정)**: `make hooks-install` → `--settings <claude_home>/settings.json` (yes 없음) → `install` 이 diff 를 표준출력에 찍고 `input()` 으로 `y` 를 기다린다. y/yes 외 입력 · EOF(에이전트 Bash 처럼 stdin 없음) → `취소 — 아무것도 바꾸지 않았다` · exit 1 · 백업도 안 만든다(백업은 확인 뒤). 즉 **사람이 y 를 치지 않는 한 쓰지 않는다** — 안전. `printf y | make hooks-install` 처럼 y 를 흘려 넣으면 저장된다(설계대로). `--yes` 를 붙이면 거부(exit 2) — 단 환경변수가 기본값일 때만 (DEF-004).
`make hooks-check` 는 읽기만(설치 0/9 · 다른 훅 5).

### 4(e) 외부 전송 · 바인드 — PASS

`grep -rnE "^(import|from) (requests|httpx|urllib|socket|http.client|aiohttp|smtplib|…)" src scripts` → `urllib.parse.urlsplit` 1 (전송 아님). `0.0.0.0` · `::` 바인드 0. `uvicorn.run(host=s.host)` 이고 `settings.get()` 이 127.0.0.1 밖을 거부. 코드 안 URL: `http://127.0.0.1:${port}/hooks/event` (hook_send.sh) · `https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/…` (고정 버전) 뿐. 실측 `lsof -nP -iTCP:8096 -sTCP:LISTEN` → `127.0.0.1:8096 (LISTEN)`.
관찰: `hook_send.sh` 는 훅 페이로드 **전체**(프롬프트 포함)를 127.0.0.1:8095 로 보낸다 — 걸러내기는 수신기 몫(spec §9.2 대로). 8095 에 다른 로컬 프로세스가 떠 있으면 그 프로세스가 원문을 받는다(외부 전송은 아님).

### 4(f) 원본 보기 — PASS

서버 8096 (qa1 DB · NO_WATCH) 에서 `GET /agents/S:8f3a6abd-…/raw?offset=-50&limit=50` 200 · `cache-control: no-store` · 32,544 B · `GET /agents/A:aca12685adbb11b9c/raw` 200 · `S:../../settings` 404.
요청 전후 DB 행 합(agent+usage_event+tool_call+state_log+hook_event+src_file+parse_error) 59,291 = 59,291 · DB 파일 mtime 같음 · 서버 로그 11 줄은 접근 줄(경로 · 상태)뿐 — 본문 0 · 저장소에 새로 생긴 파일은 DB `-wal/-shm` 뿐. 코드: `raw_messages` 는 `open(path,"rb")` 로 읽어 응답 dict 만 돌려준다(thinking · 도구 결과는 크기만). `source_path` 는 `src_file` 의 경로 중 claude_home 아래만.
관찰: 키의 `%` · `_` 는 LIKE 와일드카드로 먹는다(`S:%` → 가장 짧은 경로의 기록). 로컬 · 읽기 전용이라 결함으로 올리지 않음.

원천 무변경: 실제 `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22…` 작업 전 = 후 · `~/.claude` 에 `bak-agentdash*` 0 · `00~08 * Agent` 폴더 항목 184,519 · 17:05 이후 바뀐 파일 0. 띄운 서버(PID 22235) · 시험용 리스너(8098) 종료, 8096~8099 LISTEN 0.

---

## 5. `make gate` 판정표

### 5.1 기본 DB (`make gate`, 17:22:06)

```
G-01  골격 — make setup · 테이블 11             PASS  tests/test_schema.py: 5 passed in 0.05s ‖ agentdash.db 테이블 11
G-02  파서 회귀 — 픽스처 S1~S6 · S9 (V-08)        PASS  tests/test_parsers.py: 29 passed in 0.15s
G-03  증분 읽기 — 추가분 · 반쪽 줄 · inode           PASS  tests/test_tail.py: 9 passed in 0.10s
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)     PASS  원천 77 · DB 77 · 빠짐 0 · 남음 0 ‖ 원천 239 · DB 239 ‖ 원천 6 · DB 6
G-05  파싱 오류율 ≤ 0.1% (V-07)                 PASS  오류 0 / 줄 163183 = 0.0000% (상한 0.1%) · 파일 572
G-06  부모 연결 ≥ 95% (V-02)                   PASS  원천 245 중 연결 245 = 100.0% · L-01=227 L-02=12 L-03=6 · 워크플로 노드 1 중 1 ‖ agentdash.db 245 = 100.0% · 부모 미확인 0
G-07  토큰 합 — 표본 10 세션 (V-03)               PASS  원천 출력 1553522 · DB 1553522 · … · 세션 안 requestId 중복 0 (10 행)
G-08  비용 — 표본 20 건 손계산 (V-09)              PASS  일치 20/20 · 손계산 합 $5.986363 · 단가표 2026-10-06 · 기록에 speed=fast 0 건 ‖ 비용 NULL 행 0 · 기록 모델 5 ‖ tests/test_cost.py: 13 passed
G-09  판정 규칙 13 — 표 기반 테스트                  PASS  tests/test_state.py: 39 passed in 0.13s
G-10  연결 규칙 L-01~L-07 테스트                  PASS  tests/test_linker.py: 17 passed in 0.13s
G-11  실시간 — SSE 5 초 · 훅 1 초                PASS  tests/test_realtime.py: 4 passed in 7.10s
G-12  상태 대조 — 표본 30 오판 ≤ 2                 FAIL  표본 30 … 일치 27 · 오판 3 … — DEF-QA2-001·002·003
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  agentdash.db 테이블 11 · 행 62308 · TEXT 값 348959 · 위반 0 ‖ 파일 23 · 줄 1284 · 위반 0
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest (V-05)    PASS  파일 54 · 쓰기 호출 55 곳 · 원천 경로 대상 0 ‖ pytest 198 passed · 트리 변경 0
G-15  훅 설치 안전 — 가짜 settings (V-10)         미검증  가짜 settings (기존 이벤트 3) · 덧붙임 9 · 송신 미검증 (8095 사용 중) · 위반 0
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)   PASS  host 127.0.0.1:8095 · 스캔 py 54 · 기타 15 · 위반 0
G-17  화면 6 · API 10 — HTTP 200             PASS  16 중 HTTP 200 16 (빈 DB) · placeholder 0
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3    PASS  tests/test_graph.py: 6 passed ‖ (QA2 리포트)
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)      PASS  칸 88/88 · 근거 없는 칸 0 ‖ 표본 10 일치 10 ‖ 01 DONE v1.0 · 02 DONE v1.0 · 05 · 08 UNKNOWN ‖ tests/test_pipeline.py: 16 passed
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice    PASS  tests/test_usage_page.py: 7 passed in 0.38s
G-21  브라우저 — 콘솔 오류 0 · 390px               PASS  (QA2 리포트)
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE     미검증  outputs/e2e/self-observe.md 없음
# 합계 PASS 19 · FAIL 1 · WARN 0 · BLOCKED 0 · 미검증 2
```

### 5.2 qa1 DB (`AGENTDASH_DB=data/agentdash-qa1.db make gate`, 17:22:43)

```
G-01 PASS (agentdash-qa1.db 테이블 11) · G-02 PASS 29 · G-03 PASS 9
G-04  PASS  원천 77 · DB 77 ‖ 239 · 239 ‖ 6 · 6 · 빠짐 0 · 남음 0
G-05  PASS  오류 0 / 줄 163189 = 0.0000% · 파일 572
G-06  PASS  원천 245/245 = 100.0% ‖ agentdash-qa1.db 245/245 · 부모 미확인 0
G-07  PASS  표본 10 세션 4 칸 일치 · 세션 안 requestId 중복 0
G-08  PASS  일치 20/20 · 손계산 합 $2.455136 · 비용 NULL 0 · tests/test_cost.py 13 passed
G-09 PASS 39 · G-10 PASS 17 · G-11 PASS 4 · G-12 FAIL (QA2 DEF-QA2-001~003)
G-13  PASS  agentdash-qa1.db 행 62990 · TEXT 값 351641 · 위반 0 ‖ 픽스처 위반 0
G-14  PASS  쓰기 호출 55 곳 · 원천 경로 대상 0 ‖ pytest 198 passed · 트리 변경 0
G-15  미검증  덧붙임 9 · 송신 미검증 (8095 사용 중) · 위반 0
G-16 PASS · G-17 PASS 16/16 · G-18 PASS · G-19 PASS 88/88 · 표본 10/10 · G-20 PASS 7 · G-21 PASS · G-22 미검증
# 합계 PASS 19 · FAIL 1 · WARN 0 · BLOCKED 0 · 미검증 2
```

(G-15 미검증은 그 시각 QA2 서버가 8095 를 쓰고 있어서다 — `check_hooks` 가 포트를 쓰고 있으면 송신을 건너뛴다. QA1 은 8099 로 송신을 따로 쟀다: §4(d) G.)

---

## 6. 결함

### DEF-QA1-001 · 중대 · 개발1 (`collect/ingest.py` 포크 사본 제외) — 포크 사본에만 남은 최종 usage 를 버린다

- **재현**: `.venv/bin/python -I outputs/qa1/fork_final.py --db data/agentdash-qa1.db` (세션마다 requestId 별로 '소유 기록 안 output 최대' vs '세션 전체(사본 포함) output 최대').
- **실측**: 부모 기록보다 포크 사본의 output 이 큰 requestId **128** · 세션 2 (8f3a6abd 출력 −5,667 · dbd09a2a −84,917) · 부모 에이전트 5 (`A:a4b085f316d677042` 46 · `A:a03f9b57002234663` 36 · `A:ab90e2ed4b54aaf7c` 30 · `A:aca12685adbb11b9c` 8 · `A:a4e054a4e22af3d7c` 8). 빠진 양: 입력 · 캐시 0 · **출력 90,584 · $1.811680**. 예: `A:aca12685…` 의 요청 하나는 부모 기록 두 줄(uuid 197204ad · b4c799db) 모두 output 10, 포크 사본의 **같은 uuid 두 줄**은 178 — 내용 블록 길이 동일(925 · 353 자). 같은 부모의 마지막 requestId 하나는 사본 줄 timestamp 도 부모와 다르다(부모 18:27:51 vs 사본 3 개 18:28:03~25) — D-02 의 「시각 그대로」 가 모든 줄에 성립하지는 않는다(소유자를 시각으로 정하는 규칙에는 영향 없음 — 부모가 더 이르다).
- **기대**: requestId 하나는 세션에서 한 번, 값은 **가장 최종인 줄**(D-01 의 취지). 사본 줄을 '부모 몫' 으로 돌리되, 사본의 output 이 더 크면 부모 행을 그 값으로 바꿔야 한다 — 두 세션 출력 합 +90,584.
- **영향**: G-07 표본(8f3a6abd · dbd09a2a 둘 다 포함)이 PASS 로 보이는 것은 `check_usage_sum` 이 같은 제외 규칙을 복제했기 때문(§7).

### DEF-QA1-002 · 중대 · 아키텍트(D-01 재결정 · 화면 표기) · 개발1 — 서브에이전트 기록의 `output_tokens` 는 스트리밍 시작값이다

- **재현**: `.venv/bin/python -I outputs/qa1/stream_heuristic.py` — 요청(같은 기록 · 같은 requestId)의 output 최대 < 30 이면서 그 요청의 content 블록 JSON 길이 > 400 자인 비율 (내용은 길이만 잼).
- **실측**: 메인 세션 기록 77 · 요청 10,175 중 13 (**0.1%**) / 서브에이전트 기록 239 · 요청 17,299 중 **11,840 (68.4%)** / 워크플로 에이전트 85 중 60 (70.6%). 서브 · 워크플로 의심 요청 13,463 의 기록 output 합 121,024 vs text + tool 입력 길이 ÷ 4 합 4,226,667 → **하한 추정 ≈ 4.1M 출력 토큰 과소** (DB 서브에이전트 출력 합 8,184,185 의 절반 규모). DEF-001 의 사본 비교(같은 uuid · 같은 내용인데 부모 10 vs 사본 178)가 직접 증거.
- **기대**: D-01 확정 근거(「2,242/2,242 에서 output 단조 증가 → 마지막이 최종본」)는 **메인 세션에만** 성립한다. 서브에이전트 · 워크플로 기록에는 최종본이 없는 경우가 대부분이다. 원천으로 바로잡을 수 없으므로 사람 결정이 필요하다: decisions.md 에 D-01 반박(서브에이전트) 기록 · D-04 · D-03 에서 서브에이전트 출력 · 비용에 「기록상 과소」 표기 또는 다른 원천 검토 (`<task-notification>` 의 `subagent_tokens` 는 마지막 요청의 문맥 크기와 48/58 일치 — 누적 출력이 아니어서 대체 불가, `outputs/qa1/notif_usage.py`).
- G-07 의 글자 기준(DB = 원천 직접 합)은 이 결함만으로는 깨지지 않는다 — 숫자가 '원천과 같이' 틀린다.

### DEF-QA1-003 · 중대 · 아키텍트 (`src/agentdash/db/conn.py` `init_db`) — 원천 거부 검사 전에 `mkdir`

- **재현**: `AGENTDASH_CLAUDE_HOME=<스크래치>/home AGENTDASH_AGENTS_ROOT=<스크래치>/agents AGENTDASH_DB=<스크래치>/home/newdir/x.db uv run python -m agentdash.db.conn` → `RuntimeError: DB 경로가 원천 루트 아래` 이지만 `<스크래치>/home/newdir` 이 생긴다. `… -m agentdash.collect.backfill` 도 같다(`newdir2`). agents_root 의 읽기 전용 폴더 아래로 주면 `PermissionError` (쓰기 시도).
- **실측**: `init_db` 가 `p.parent.mkdir(parents=True, exist_ok=True)` 를 먼저 하고 `connect()` 안에서 `_refuse_source` 를 한다. `make run` lifespan · backfill · hooks-check · export 가 모두 `init_db` 를 거친다.
- **기대**: 원천 아래면 아무것도 만들지 않고 거부(CLAUDE.md 「원천 아래를 쓰기 모드로 여는 코드 0」 · spec V-05). 검사 → mkdir 순서.
- **게이트 오판**: `check_readonly` 정적 스캔은 `AGENTDASH_DB` 를 원천 씨앗으로 보지 않고, 런타임 검사는 DB 를 tmp 에 두므로 둘 다 이 길을 못 본다 → G-14 PASS.

### DEF-QA1-004 · 중대 · 개발2 (`scripts/hooks_install.py` `is_real_target`) — `--yes` · pytest 거부가 '설정된' claude_home 만 본다

- **재현(코드 판정 + 대역)**: `bash outputs/qa1/hooks_fake.sh <스크래치>` 의 F — `AGENTDASH_CLAUDE_HOME=<가짜>` 일 때 `is_real_target(Path("~/.claude/settings.json").expanduser())` = **False**, 환경변수 없을 때만 True. pytest 중(`PYTEST_CURRENT_TEST`) + 가짜 home 도 False. 대역 파일에 `--yes` → exit 0 로 저장. (실제 경로로는 실행하지 않았다.)
- **실측**: `tests/conftest.py` 의 autouse `_isolate_sources` 가 모든 테스트에서 `AGENTDASH_CLAUDE_HOME` 을 tmp 로 바꾸므로, **테스트 안에서** `main(["--settings", <실제 경로>, "--yes"])` 를 부르면 두 가드가 다 통과한다. 개발 셸에서 가짜 home 을 export 해 둔 채 실제 경로에 `--yes` 를 줘도 같다 → 실제 `~/.claude/settings.json` 에 확인 없이 덧붙임 + `~/.claude` 에 백업 파일.
- **기대**: 설정과 무관하게 실제 홈의 `~/.claude/settings.json`(`Path.home()/".claude"/"settings.json"`, 그리고 설정된 claude_home 의 것) 둘 다를 실제 파일로 보고 `--yes` 를 거부.
- **게이트 오판**: `check_hooks` 는 tmp 파일만 시험해 이 가드를 시험하지 않는다.

### DEF-QA1-005 · 중대 · 개발2 (`scripts/hooks_install.py` `MARK`) — 식별 표시가 너무 넓다: 남의 `hook_send.sh` 훅을 지운다

- **재현**: `bash outputs/qa1/hooks_fake.sh <스크래치>` 의 D — 가짜 settings 의 Stop 에 `bash /other/project/hook_send.sh` 항목을 두고 설치 → 제거.
- **실측**: 설치는 Stop 을 '이미 설치됨' 으로 건너뛰어 덧붙임 **8/9** (exit 0, 그러나 내부 검사 `식별 항목 n ≠ 9` 는 남의 항목까지 세어 9 로 통과). 제거는 남의 항목까지 지워 `/other/project/hook_send.sh` **0 개 남음** — 기존 훅 손상.
- **기대**: spec §9.1 — 「덧붙인 항목에는 명령 경로로 식별 표시(`…/agentdash/scripts/hook_send.sh`)」. 이 저장소의 `scripts/hook_send.sh` 절대 경로(또는 명령 문자열 전체 `bash '<저장소>/scripts/hook_send.sh'`) 일치로만 식별해야 한다.
- 지금 실제 `~/.claude/settings.json` 에는 `hook_send.sh` 가 0 번 나와(읽기로 셈) 실제 피해는 없다. `check_hooks` · `tests/test_hooks_install.py` 에 이 경우가 없다.

### DEF-QA1-006 · 경미 · 개발1 (`core/usage.py` `rebuild_daily` · `table`) — D-04 「작성 파일」 이 기간 합에서 과다

- **재현**: `sqlite3 data/agentdash-qa1.db "select (select sum(files_written) from usage_daily),(select count(*) from (select distinct agent_key,path from file_touch))"`.
- **실측**: 2,277 vs 2,262 (+15). Standard-Data-Hub 프로젝트 D-04 API 77 vs 고유 76. `file_touch` 가 (agent, path, op) 마다 `at` 하나라 같은 파일의 Write 와 Edit 가 다른 날이면 두 번 센다.
- **기대**: spec §6 「Write · Edit · NotebookEdit 의 서로 다른 file_path 수」 — 기간 · 묶음 합은 고유 경로 수.

### DEF-QA1-007 · 경미 · 개발2 (`collect/hooks_rx.py` `target_of`) — 훅 detail 에 URL 쿼리 문자열 저장

- **재현**: `uv run python outputs/qa1/hook_payload.py` 의 `WebFetch url` — `tool_input.url` 의 쿼리에 둔 표지가 `detail.target`(앞 80 자)에 남는다.
- **기대**: spec §9.2 수신기가 남기는 도구 입력은 `file_path` 뿐, `tool_call.target` 은 URL **호스트**(§3). 쿼리에 토큰이 실릴 수 있으므로 호스트만.

### DEF-QA1-008 · 경미 · 아키텍트 (`settings.py` `is_source_path`) — 원천 판정이 설정된 루트에만 묶임

- **재현**: `AGENTDASH_CLAUDE_HOME=<스크래치>/home AGENTDASH_DB=<'실제 원천' 대역>/x.db uv run python -m agentdash.db.conn` → 거부 없이 테이블 11 생성.
- **기대**: 환경변수 두 개를 함께 잘못 줘도 실제 `Path.home()/.claude` 와 기본 `agents_root`(`config/settings.yaml` 값) 아래는 늘 거부. DEF-004 와 같은 뿌리.

---

## 7. 개발 검사 도구(check_*) vs QA1 독립 집계

| 도구 | 개발 도구 결과 | QA1 독립 결과 | 어긋남 |
|---|---|---|---|
| `check_counts` (G-04) | 77 · 239 · 6 | 77 · 239 · 6 · S6 1 | 없음 |
| `check_parse_errors` (G-05) | 0 / 163,183 | 0 / 162,202 (offset 까지) · 필수 필드 0 | 없음 (분모 차이는 시각) |
| `check_link_rate` (G-06) | 245/245 | 245/245 · DB 와 246/246 | 없음 |
| `check_usage_sum` (G-07) | 표본 10 일치 | 개발 규칙과는 320/320 일치, **최종본 기준으로는 8f3a6abd −5,667 · dbd09a2a −84,917** | **있음** — 도구가 수집기와 같은 포크 제외 규칙(`skip_uuids` · `skip_rids`)을 복제해 DEF-001 을 못 본다. 서브에이전트 스트리밍 과소(DEF-002)는 두 쪽 다 못 본다 |
| `check_cost` (G-08) | 20/20 | 20/20 · 경계 10/10 · 전 기간 320/320 | 없음 (단, 비용도 DEF-001 · 002 만큼 같이 적다) |
| `check_no_payload` · `check_fixtures_redacted` (G-13) | 위반 0 | 위반 0 · 상위 20 경로 · 픽스처 본문 0 | 없음 (DEF-007 은 상한 안 값이라 두 쪽 다 위반 아님) |
| `check_readonly` (G-14) | 원천 대상 0 · 트리 변경 0 | 원천 아래 mkdir 재현 | **있음** — DEF-003 을 못 본다 |
| `check_hooks` (G-15) | 미검증 (8095 사용 중) · 덧붙임 9 · 위반 0 | 기본 경우 PASS 같음 · 가드 우회 · 넓은 식별 표시 | **있음** — DEF-004 · 005 를 시험하지 않는다. 포트를 쓰고 있으면 송신을 건너뛰어 미검증 |
| `check_bind` (G-16) | 위반 0 | 127.0.0.1 실측 · 외부 import 0 | 없음 |
| `check_pipeline` (G-19) | 88/88 · 표본 10/10 | 55/55 전 칸 · P-01 2 · ↻ 9 | 없음 |

## 8. QA1 스크립트 (`outputs/qa1/`, 원천 읽기 전용 · DB `mode=ro`)

| 파일 | 하는 일 |
|---|---|
| `recount.py` | G-04 파일 수 · D-11 줄 종류 · D-01/D-02 · 전 에이전트 토큰 · 도구 · 작성 파일 · G-07 표본 10 (`recount-seed7.json`) |
| `fork_final.py` | DEF-001 사본 최종본 비교 |
| `stream_heuristic.py` | DEF-002 기록 종류별 스트리밍 시작값 비율 · 하한 추정 |
| `notif_usage.py` | `<task-notification>` 숫자 ↔ DB (보조) |
| `link_check.py` | G-06 부모 연결 · G-05 필수 필드 |
| `cost_check.py` · `global_cost.py` · `cost_edge.py`* · `cost_cases.json` | G-08 단가표 대조 · 표본 20 · 전 기간 · 합성 경계 |
| `pipe_check.py` · `pipe_fake.py`* | G-19 독립 find 대조 · 가짜 agents_root 로 미등록 · NFD · 별칭 · 제외 · P-01/P-05 |
| `text_scan.py` · `fixture_scan.py` · `hook_payload.py`* | G-13 DB TEXT · 픽스처 · 훅 화이트리스트 |
| `hooks_fake.sh` | G-15 가짜 settings 설치 · 제거 · 바이트 비교 · 가드 · 송신 |

\* 개발 함수를 직접 불러 시험하는 것(기대값은 QA1 손계산 · spec).
