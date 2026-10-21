# QA1 — 데이터 · 비용 · 안전 (r4 · 2차-A 웨이브 C · 계획 Task 14)

- 기준 커밋 `fb7ab0b` · 정본 `spec.md` v0.3 · 2026-10-21 KST 10:41 ~ 10:55
- DB: `data/agentdash-qa1.db` 를 **처음부터 새로 백필** (`rm -f data/agentdash-qa1.db*; AGENTDASH_DB=data/agentdash-qa1.db make setup backfill` — 4.6 s · 원천 파일 567 · agent 73/239/1/6 · usage_event 25,905 · parse_error 0). 그 뒤 개발 검사 도구가 증분 수집을 돌려 25,955 → 26,019 행으로 늘었다 (원천이 계속 자람 — 각 숫자는 같은 시각의 DB · 원천 쌍).
- 기대값은 개발 코드가 아니라 `spec.md` §6 · §6.2 · §6.3 · §8 · `config/*.yaml` · 원천 파일에서 QA1 스크립트가 직접 계산했다. 원천은 `'rb'` / `os.path.exists` 로만 읽고 DB 는 `mode=ro` 로만 열었다. 리포트에는 숫자 · 키 · 경로만 적는다.
- 예산 한도는 **가짜**: `r4_budget.py` 프로세스 안에서만 `settings.load_yaml` 을 바꿔 끼웠다. 실제 `config/budget.yaml` 은 바이트 그대로 (null) · `git status` 에 변경 없음.

## 요약 — 게이트별 QA1 판정

<!-- gate:G-04 -->
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)  PASS  새 DB 세션 73/73 · 서브에이전트 239/239 · 워크플로 에이전트 6/6 · S6 1/1 · 원천만 0 · DB만 0 (recount.py) · D-22 기본 DB 사본 독립 분류 보관 27 (세션 8 · 서브 19) = check_counts 27 · 확인 못 함 0 · 변이 2/2 FAIL 검출 (r4_archive.py)

<!-- gate:G-05 -->
G-05  파싱 오류율 ≤ 0.1% (V-07)  PASS  줄 155,691 (offset 까지) · 깨진 JSON 0 · assistant/user 필수 필드 없음 0 (recount.py · link_check.py) · check_parse_errors 0/156,675

<!-- gate:G-06 -->
G-06  부모 연결 ≥ 95% (V-02)  PASS  독립 연결 245/245 = 100% · 독립 부모 = DB parent_key 246/246 (워크플로 노드 포함, link_check.py)

<!-- gate:G-07 -->
G-07  토큰 합 — 표본 10 세션 (V-03)  PASS  최종본 규칙 독립 집계 = DB 316/316 에이전트 4 칸 일치 (출력 17,497,274, r2_final.py) · 표본 10 (시드 11) 8 일치 + 2 = 포크 최종본 90,584 (옛 규칙 차이, fork_final 그대로) · check_usage_sum 10/10 · 기본 DB 사본 표본 후보 71 (보관 8 제외)

<!-- gate:G-08 -->
G-08  비용 — 표본 20 건 손계산 (V-09)  PASS  실제 표본 20/20 (시드 4) · 합성 경계 10/10 · 전 기간 손계산 $3,677.016825 + 사본 최종본 $1.811680 = DB $3,678.828505 · 비용 NULL 0 · 단가표 밖 모델 0

<!-- gate:G-13 -->
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 · 길이 숫자 (V-04 · §2.3)  PASS  TEXT 332,921 값 중 300 자 초과 0 (최장 tool_call.target 222) · 픽스처 23 파일 위반 0 · usage_event 17 열 · usage_daily 13 열 = spec 블록 · 길이 열 0 · 길이 값 저장 0

<!-- gate:G-14 -->
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  check_readonly 정적 원천 대상 0 · 읽기 전용 pytest 372 passed · 트리 변경 0 · 씨앗 49/49 거부 · 가짜 루트 DB 파일 하드 링크 · 심볼릭 링크 7/7 거부 · 원천 변화 0 · 남은 것 경미 DEF-QA1-301 (-wal · -shm 하드 링크)

<!-- gate:G-15 -->
G-15  훅 설치 안전 — 가짜 settings (V-10)  PASS  가짜 settings 덧붙임 9 · 제거 후 바이트 동일 (indent 2 · 4) · 남의 hook_send.sh 남음 1 · --yes 없이 취소 · 실제 파일 가드 5/5 · 송신 8099 0.021 s exit 0 · 0 B · 실제 ~/.claude/settings.json sha 그대로 · hook_send 0

<!-- gate:G-16 -->
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)  PASS  실측 TCP 127.0.0.1:8096 LISTEN (QA1 PID 4495, 끝에 종료) · 외부 전송 import 0 · 0.0.0.0 0 · 외부 URL 은 CDN 고정 버전 2 개 (cytoscape@3.30.2 · chart.js@4.4.1) · 알림은 브라우저 Notification 만

<!-- gate:G-19 -->
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)  PASS  88 칸 · 근거 없는 칸 0 · 55 칸 독립 find = DB 55/55 · 무작위 10/10 (시드 9) · P-01 2 칸 · ↻ 9 = 9 · 고려솔더 01·02 DONE v1.0 · 05·08 UNKNOWN · 가짜 루트 P-05 · 별칭 · 제외 폴더 spec 대로

<!-- gate:G-20 -->
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice  PASS  /usage [추정] API 정가 환산 4 곳 · 추정 보정 (D-17) 5 곳 · 단가 없음 0 건 · reprice 바뀐 행 0 · event = daily = API total $3,681.799481 (추정 보정 $3,811.059001) · CSV 기록 · 추정 열 나란히

<!-- gate:G-24 -->
G-24  추정 열 — V-12 원천 재측정  PASS  D-23 단위(세션 안 requestId 한 번) 원천 12,773/26,019 = DB 12,773/26,019 (49.09%) 차 0.00%p · spec 글자 단위(기록별, 포크 사본 280 중복) 48.57% 차 0.52%p · 행 대조 26,019 의심 판정 불일치 0 · output_est 값 불일치 0 · < output_tokens 0 · 비의심 NULL · cost_est = cost 위반 0 · 경계 29/30 · 400/401 원천대로 · test_usage_est 15 passed

<!-- gate:G-25 -->
G-25  하드 링크 — 이미 있는 DB 파일 st_nlink > 1 거부  PASS  가짜 루트: DB 파일 = 원천 하드 링크 init_db · connect · CLI(db.conn · backfill) 4/4 거부 · 유효 sqlite 원천 링크 거부 · 저장소 안 nlink 2 거부 · 심볼릭 링크 2/2 거부 · 원천 변화 0 · 정상 새 파일 허용 · 남은 것 경미 DEF-QA1-301 (곁 파일 -wal · -shm)

<!-- gate:G-26 -->
G-26  예산 — 80/100 % · KST 일/월 · 프로젝트 · unset · no_records · 단가 없음  PASS  합성 경계 DB 칸 10 손 단계 10/10 · 손 금액 6/6 · 비율 0.7999 ok · 0.8 warn · 0.9999 warn · 1.0 over · KST 00:00 · 1 일 경계 · 지금 포함 · 미래 제외 · 단가 없음 미합산 · 자손 자기 경로 · 실제 DB 칸 78 직접 합 최대 차 $0.000000 · 실제 budget.yaml 전부 unset

<!-- gate:G-27 -->
G-27  추세 — 일 · 주(KST 월요일) · 월  PASS  실제 DB 2026-07-01~10-21 · grain 3 × group 2 · 묶음 237 · API = usage_event = usage_daily 불일치 0 (기록 $3,681.799481 · 추정 보정 $3,811.059001 · 출력 17,506,269 · 추정 21,726,716) · 합성 일요일 23:59:59.999 / 월요일 00:00 · 10-31 / 11-01 경계 손 대조 일치

<!-- gate:G-28 -->
G-28  캐시 적중률 — 표본 10 손계산 · 분모 0  PASS  표본 10 (project 3 · session 3 · agent 4, 시드 4) + 전수 424 행 손계산 = API 최대 차 0.000000000 · 정렬 (1−적중률)×추정 보정 비용 위반 0 · 세션 묶음 = parent 사슬 뿌리 묶음 · 합성 분모 0 → API null · D-07 「—」

**이전 결함 (r3): DEF-QA1-201 해결됨** (DB 파일 자체의 하드 링크는 이제 거부 — §2). **새 결함 1 — 치명 0 · 중대 0 · 경미 1.** 치명 기준(원천 쓰기 · 본문 또는 길이 숫자 저장 · 기존 훅 손상 · 외부 전송 · 실제 budget.yaml 금액 기입)이 실제로 일어난 일은 0.

| ID | 등급 | 담당 | 한 줄 |
|---|---|---|---|
| DEF-QA1-301 | 경미 | 아키텍트 (`src/agentdash/db/conn.py` `_refuse_source`) | DB 본 파일은 정상인데 곁 파일 `-wal` · `-shm` 이 **이미** 원천 파일의 하드 링크면 거부하지 않고 SQLite 가 그 inode 에 쓴다 (사람이 미리 `ln` 해야만 — 코드 경로로는 생기지 않음) |

---

## 1. G-24 — 추정 열 (`outputs/qa1/r4_est.py`, agentdash import 없음)

정의 (spec §6.2 글자): 요청 = 같은 기록 · 같은 requestId 의 assistant 줄 묶음 (usage 있음 · `<synthetic>` 제외) · 의심 = output 최대 < 30 이고 `json.dumps(블록)` 길이 합 > 400 · 추정 = `max(ceil((text 글자 + json.dumps(tool_use.input, ensure_ascii=False) 글자) / 4), 기록 output)` · thinking 제외. 원천은 DB `src_file.offset` 까지.

| 항목 | 원천 (QA1) | DB | 판정 |
|---|---|---|---|
| 모집단 — **spec 글자** (기록마다 · requestId 마다, 포크 사본 280 요청 두 번) | 12,773 / 26,299 = 48.57 % | 12,773 / 26,019 = 49.09 % | 차 **0.52 %p** (> 0.5) |
| 모집단 — **D-23** (세션 안 requestId 한 번 = DB 행 단위) | 12,773 / 26,019 = 49.09 % | 같음 | 차 **0.00 %p** |
| 행 대조 (D-23 소유 행 26,019) | DB 에 없음 0 · 원천에 없는 DB 행 0 | | 일치 |
| 의심 판정 불일치 · output_est 값 불일치 · output_est < output_tokens | 0 · 0 · 0 | | 일치 |
| 비의심 행 output_est NULL · cost_est_usd = cost_usd | 위반 0 · 0 | | 일치 |
| 의심 행 cost_est 손계산 (cost_usd + (est − out) × 출력 단가 × fast, Haiku 구간 포함, 단가 `config/pricing.yaml`) | 불일치 0 (≤ 1e-9) | | 일치 |
| 실제 경계 요청 (원천 수 / DB 의심 수) | out=29 11/11 · out=30 16/0 · json=400 9/0 · json=401 6/6 | | 경계 그대로 |
| `<synthetic>` | usage 줄 87 | DB 행 0 | 제외됨 |
| 종류별 의심 (D-23 단위) | 메인 9/9,146 (0.1 %) · 서브 12,704/16,788 (75.7 %) · 워크플로 60/85 (70.6 %) | | 참고 |
| 합계 | | 출력 기록 17,538,258 · 추정 보정 21,766,125 (+4,227,867) · 비용 $3,685.602079 · 추정 보정 $3,815.009999 | 참고 |

- **모집단 판정 (D-23)**: spec §6.2 의 요청 행이 「(A3 중복 제거와 같은 단위)」 라고 적었고, A3 중복 제거의 실제 단위는 D-01 보완 · D-02 대로 「세션 안 requestId 한 번」 이다. 기록별로 세면 포크 사본(부모 몫, DB 행 없음)을 두 번 세어 분모가 DB 와 다른 모집단이 된다. 그래서 **QA1 은 D-23 단위를 맞다고 판정한다** — 비율 차 0.00 %p, 더 강한 행 단위 대조 26,019/26,019 일치. spec 글자 단위(0.52 %p) 는 위 표에 함께 적었다. V-12 문구를 「세션 안 requestId 단위」 로 고칠지는 사람이 정한다 (D-23 그대로).
- **길이 숫자 저장 0**: `usage_event` 17 열 · `usage_daily` 13 열이 spec §3 블록과 이름 · 순서까지 같고 `len/char/json` 꼴 열 0. 의심 행에서 json 길이 또는 text+도구 입력 글자 수와 값이 같은 칸 17 개는 전부 input · cache_write 칸이며 그 칸들은 원천 usage 와 4 칸 일치(r2_final 316/316) — 토큰 값의 우연 일치이지 길이 저장이 아니다. `output_est` 는 ceil(/4) 결과 또는 기록 output 이다.
- 개발 도구: `check_usage_est` PASS (49.1 % · 차 0.00 %p · 위반 0 · 참고 파일별 48.6 %) — QA1 숫자와 같다. `tests/test_usage_est.py` 15 passed.

## 2. G-25 · G-14 — 하드 링크 재현 (`outputs/qa1/r4_hardlink.py`, 가짜 루트만)

`AGENTDASH_CLAUDE_HOME=<스크래치>/hl/casehome` · `AGENTDASH_AGENTS_ROOT=<스크래치>/hl/caseagents`. 원천 파일은 그 가짜 루트에 만든 파일이고, 링크는 저장소 `data/qa1r4-*` 에 만든 뒤 전부 지웠다 (남은 것 0). **실제 `~/.claude` 파일로는 링크를 만들지 않았다.**

| 경우 | 결과 | 가짜 원천 변화 |
|---|---|---|
| DB 파일 = 원천 파일 하드 링크 — `init_db` · `connect` | RuntimeError ×2 | 없음 |
| 같은 링크로 `-m agentdash.db.conn` (make setup 경로) · `-m agentdash.collect.backfill` | exit 1 · RuntimeError ×2 | 없음 |
| 원천의 **유효한 sqlite 파일** 하드 링크 — `init_db` | RuntimeError | 없음 |
| 저장소 안 두 파일끼리 하드 링크 (원천 아님, st_nlink 2) | RuntimeError (spec 글자대로) | — |
| 심볼릭 링크 파일 `data/qa1r4-sym.db` → 원천 파일 — `init_db` · `connect` | RuntimeError ×2 | 없음 |
| **곁 파일** `data/qa1r4-sidewal.db-wal` = 원천 파일 하드 링크, 본 파일 정상 → connect + 쓰기 | **열림** | **바뀜 (223 B → 16,512 B)** → DEF-QA1-301 |
| **곁 파일** `-shm` = 원천 파일 하드 링크 → connect + 쓰기 | **열림** | **바뀜 (223 B → 32,768 B)** → DEF-QA1-301 |
| 정상 새 파일 `data/qa1r4-ok.db` · 다시 connect | 허용 | — |

`check_readonly`: 정적 파일 62 · 쓰기 호출 75 곳 · 원천 경로 대상 0 / 읽기 전용 가짜 루트 pytest 372 passed · 트리 변경 0 / 진입점 7 × 원천 아래 DB 경로 7 = 49 회 전부 거부 · 생긴 항목 0.

## 3. G-26 · G-27 · G-28 — 예산 · 추세 · 캐시 적중률 (`outputs/qa1/r4_budget.py`)

API 는 FastAPI TestClient (프로세스 안, 네트워크 없음) 로 불렀다. 시각은 `core.budget` · `routers.pages` 의 `datetime.now` 만 고정. 실제 DB 쪽은 `data/agentdash-qa1.db` 의 스크래치 사본(백업 API) 으로 고정했다.

### 3.1 합성 경계 DB (스크래치 `qa1r4-syn.db`) — 지금 = 2026-11-02 03:00:00Z (KST 11-02 월 12:00)

| 행 | 시각 (UTC) | KST | 추정 보정 / 기록 | 오늘 | 이번 달 |
|---|---|---|---|---|---|
| S:a ProjA | 10-31 14:59:59.999Z | 10-31 23:59:59.999 | 100 / 50 | — | — (지난달) |
| S:a | 10-31 15:00:00.000Z | 11-01 00:00 | 1 / 0.5 | — | ✓ |
| S:a | 11-01 14:59:59.999Z | 11-01 23:59:59.999 | 2 / 1 | — | ✓ |
| S:a | 11-01 15:00:00Z (소수점 없는 꼴) | 11-02 00:00 | 4 / 2 | ✓ | ✓ |
| S:a | 11-02 03:00:00.000Z (= 지금) | | 8 / 4 | ✓ | ✓ |
| S:a | 11-02 03:00:00.001Z (미래) | | 1000 / 500 | — | — |
| S:a 단가 없음 (NULL) | 11-02 01:00Z | | NULL | 건수 1 | 건수 1 |
| A:b 자손 · `project_path` `/x/y/ProjB/` | 11-02 02:00Z | | 16 / 8 | ✓ ProjB | ✓ ProjB |
| S:c `project_path` 없음 → `pk-c` | 11-02 02:30Z | | 32 / 16 | ✓ | ✓ |

손 기대: 전체 오늘 $60 (기록 $30, 단가 없음 1) · 이번 달 $63 ($31.5) · ProjA 12/15 · ProjB 16/16 · pk-c 32/32 → API **6/6 일치**. 가짜 한도 단계 손 대조 **10/10**: 전체 오늘 60/75 = 0.8 **warn** · 달 63/63 **over** · ProjA 12/15.0001 **ok** · 15/15 **over** · ProjB 16/20 **warn** · 16/16.0001 **warn** · pk-c null **unset** · 32/32 **over** · `NoSuchProj` (기록에 없는 이름) **no_records** · null **unset**. worst = over (1.0000). 같은 DB 로 한도 하나씩: 비율 0.7999 ok · 0.8 warn · 0.9999 warn · 1.0 over · warn_ratio 0.81 → ok · 0.5 → warn — 불일치 0.

화면: D-01 띠 있음 「예산 초과」 · 「오늘 전체 80 %」 · 「이번 달 전체 100 %」 · /insights 링크. D-07 게이지 단계 표지 ok · warn · over · unset · no_records 다섯 가지. 음수 한도 → `SettingsError` (D-01 은 「예산 설정 오류」 띠). 실제 `config/budget.yaml` → 칸 2 · 전부 unset · worst 없음.

합성 추세 (G-27): 주 묶음 `2026-10-26` (일요일 23:59:59.999 까지) · `2026-11-02` (월요일 00:00 부터), 월 묶음 `2026-10-01` · `2026-11-01` (KST 11-01 00:00 부터) — 기록 · 추정 보정 · 출력 · 추정 출력 4 값 손 대조 일치. 합성 적중률 (G-28): 토큰 0 행 에이전트 → API `hit: null` · D-07 표 「—」 · A:b 2/(1+2+3+4) = 0.2000 (5m + 1h 캐시 쓰기 합).

### 3.2 실제 백필 DB (사본, KST 10-21 10:49)

- **G-26**: 손 직접 합 오늘 추정 $46.8876 / 기록 $45.0444 · 이번 달 $1,985.4840 / $1,891.4933 · 단가 없음 0/0 · 프로젝트 38. 가짜 한도 (상위 3 프로젝트 + 없는 이름) 칸 10: 단계 손 기대와 일치 (Standard ML Platform 달 warn · lcomFine MES 달 over · NoSuchProj no_records · 전체 달 unset 등) · 최대 차 $0.000000. 전수 (38 프로젝트 × 2 + 전체 2 = 칸 78) 최대 차 $0.000000. 자손 중 세션과 `project_path` 가 다른 에이전트 17 — 각자 경로로 센 QA1 합과 API 같음. 개발 `check_budget` PASS (칸 78 · 차 $0.000000).
- **G-27**: 2026-07-01 ~ 10-21 · grain day/week/month × group total/project · 묶음 237 · API = `usage_event` 직접 합 = `usage_daily` 합 (cost_usd · cost_est_usd · output_tokens · 추정 출력, daily 의 output_est = 의심 행 합) **불일치 0**. 주 묶음 라벨 전부 월요일. 개발 `check_trend` PASS (묶음 237).
- **G-28**: 프로젝트 · 세션 · 에이전트 전수 424 행 손계산 = API 최대 차 0 · 정렬 위반 0 · 세션 묶음(session_id) = parent 사슬 뿌리 묶음, 다른 세션 0. 표본 10 (시드 4): project Songwol Data G… 0.9609 · gerardo92 0.9684 · KwangSung Data… 0.9433 · session S:82cd10e9 0.9676 · S:61adad31 0.9604 · S:ebe31ef9 0.9700 · agent A:abca160d 0.8665 · A:a4368081 0.9223 · S:6a44e325 0.9760 · A:a132525b 0.9879 — 전부 손 = API. 개발 `check_efficiency` PASS.

## 4. G-04~G-08 회귀 · D-22 엄밀성 (`outputs/qa1/r4_archive.py` 외)

- 새 DB: 보관 0 · 세션 73/73 · 서브 239/239 · 워크플로 에이전트 6/6 (QA1 recount · check_counts 둘 다). 원천에도 있는데 기록 경로가 전부 없는 키(경로 이동) 0.
- 기본 DB `data/agentdash.db` 의 **스크래치 사본**(백업 API, 원본 안 건드림) 독립 분류: DB 전용 27 = 보관 27 (세션 8 · 서브에이전트 19 · 워크플로 에이전트 0) · 확인 못 함 0 (경로 기록 없음 0 · 경로 남아 있음 0) · 기록 경로 27 · mtime 2026-09-17 ~ 09-21 · 세션 단위 전부 지움 8 · 일부 0 · 보관 키 usage_event 2,694 행 · $901.6741 · 출력 4,134,400 (Q10 대로 화면에 남음). `check_counts --no-sync` 보관 수 = QA1 과 같음. (사본은 동기화하지 않아 서브에이전트 「빠짐 2」 — 사본을 뜬 뒤 새로 생긴 이 루프의 서브에이전트, 시차이지 분류 오류 아님.)
- 변이 찌르기 (사본에서): ① 보관 세션 1 의 `src_file` 경로 행 삭제 → check_counts 세션 **FAIL 남음 1** · 보관 7 ② 보관 서브에이전트 1 의 경로 행 삭제 → **FAIL 남음 1** · 보관 18. 경로가 기록돼 있지 않으면 보관으로 넘기지 않는다 — D-22 규칙 1 그대로. 「경로가 아직 있으면 FAIL」 은 실제 원천 파일을 만들 수 없어 `tests/test_check_counts.py` (7 passed, `test_counts_recorded_path_still_exists_fails` 포함) 와 `split_extra` 코드(`any(p.exists())`) 로 확인.
- `check_usage_sum` 표본 선정: 새 DB 후보 71/71 · 기본 DB 사본 후보 71 (토큰 있는 세션 79 중 전부 지움 8 제외 · 일부 0) · 표본 10/10 PASS. QA1 r2_final 독립 316/316 4 칸 일치.
- G-08: `cost_check.py --seed 4` 20/20 · `cost_edge.py` 10/10 · `global_cost.py` 손 $3,677.016825 + `fork_final.py` 사본 최종본 $1.811680 (128 requestId · 5 에이전트, r3 와 같음) = DB $3,678.828505.

## 5. 새 결함

### DEF-QA1-301 · 경미 · 아키텍트 (`src/agentdash/db/conn.py` `_refuse_source`) — 곁 파일(-wal · -shm) 하드 링크는 막지 못한다

- **재현 (가짜 루트만)**: `uv run python outputs/qa1/r4_hardlink.py <빈 스크래치 폴더>` 의 「곁 파일」 두 줄. 손으로는: 가짜 원천 `$S/casehome/projects/p/side.jsonl` (223 B) · `AGENTDASH_CLAUDE_HOME=$S/casehome AGENTDASH_AGENTS_ROOT=$S/caseagents` 에서 `conn.init_db(data/x.db)` 로 정상 DB 를 만들고 닫은 뒤 `ln $S/casehome/projects/p/side.jsonl data/x.db-wal` → `conn.connect(data/x.db)` + INSERT · commit.
- **실측**: 거부 없이 열림 · 가짜 원천 파일 223 B → 16,512 B (WAL 프레임이 원천 inode 에 쓰임). `-shm` 도 같음 (→ 32,768 B). 링크는 SQLite 가 닫을 때 지워 nlink 1 로 돌아가 흔적이 남지 않는다.
- **기대**: `_refuse_source` 가 본 파일뿐 아니라 이미 있는 `<db>-wal` · `<db>-shm` (· `-journal`) 도 `st_nlink > 1` 또는 원천 판정이면 거부 (r3 DEF-QA1-201 의 기대 「`-wal` · `-shm` 도 같이」 중 남은 부분).
- **등급 근거**: r3 DEF-QA1-201 과 같은 부류 — 사람이 원천 파일을 저장소 `data/` 안 곁 파일 이름으로 일부러 `ln` 해 둔 경우에만 열린다. 코드 · 환경변수 오설정만으로는 생기지 않고 실제로 일어난 일 0. 그래서 경미. G-25 글자(「이미 있는 DB 파일 st_nlink > 1 거부」) 는 충족.

### 관찰 (결함 아님)

- O-1 (D-23): V-12 의 모집단 단위 — spec 글자(기록별) 0.52 %p · D-23(세션 안 requestId) 0.00 %p. QA1 판정은 D-23 이 맞다 (§1). spec 문구 정리는 사람 몫.
- O-2: `/api/v1/trend?grain=week&from=<월요일 아님>` 은 첫 묶음 라벨이 그 주 월요일이지만 합은 `from` 이후만 (예 from 10-15(목) → 첫 묶음 「2026-10-12」). 기간 선택과 합이 일치하므로 V-14 에는 영향 없음 — 화면에서 첫 주가 부분 주라는 표시는 없다.
- O-3: 예산 단계 `no_records` (한도가 있는데 그 이름의 기록 0 — 오타 방지) 는 spec §6.3 단계 4 종 밖의 개발 확장이다. 조용히 0 % 로 두지 않는 쪽이라 「조용한 실패 금지」 와 맞다.
- O-4: 한도에 음수를 넣으면 `/api/v1/budget` · `/insights` 는 `SettingsError` 로 500, D-01 은 「예산 설정 오류」 띠로 보인다 — 소리 나는 실패라 규약 위반 아님.
- O-5: `text_scan.py` 의 「키·토큰 꼴」 2 건은 Bash `description` 안의 `task-not…` 이 `sk-` 정규식에 걸린 오탐. 「코드/명령 꼴」 81 건은 전부 Bash `description` 앞 120 자 (spec §2.3 허용, 최대 120 자).

## 6. 이번 회차 실행

새 스크립트 (`outputs/qa1/`): `r4_est.py` (G-24) · `r4_hardlink.py` (G-25 · G-14, 가짜 루트) · `r4_budget.py` (G-26 · G-27 · G-28, TestClient · 가짜 한도 · 합성 DB 스크래치) · `r4_archive.py` (D-22).
다시 돌린 기존 스크립트: `recount.py --seed 11` · `r2_final.py` · `link_check.py` · `fork_final.py` · `global_cost.py` · `cost_check.py --seed 4` · `cost_edge.py` · `text_scan.py` · `fixture_scan.py` · `pipe_check.py --seed 9` · `pipe_fake.py` · `hooks_fake.sh` (가짜 settings 만).
개발 도구 (qa1 DB): `check_counts` · `check_usage_sum` · `check_parse_errors` · `check_link_rate` · `check_cost` · `check_usage_est` · `check_budget` · `check_trend` · `check_efficiency` · `check_pipeline` · `check_no_payload` · `check_fixtures_redacted` · `check_readonly` · `check_hooks` · `check_bind` 전부 PASS. `make reprice` (qa1 DB) 바뀐 행 0. pytest `test_usage_est · test_budget · test_insights · test_settings` 51 passed · `test_check_counts` 7 passed · 읽기 전용 전체 372 passed.
서버: 8096 (`AGENTDASH_DB=data/agentdash-qa1.db AGENTDASH_NO_WATCH=1`, PID 4492/4495) — 화면 6 + API 9 GET 200 확인 뒤 그 PID 만 kill, 8096 LISTEN 0.
기본 DB `data/agentdash.db` 는 읽기 전용(mode=ro)으로만 열어 백업 API 로 스크래치에 사본을 떠서 봤다. `make gate` 는 기본 DB 를 동기화하므로 이번 회차에는 돌리지 않았다.
