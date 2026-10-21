# QA1 — 데이터 · 비용 · 안전 (r6 · 2차-T 웨이브 D 재검증)

- 기준 커밋 `710683f` (트윈 코드 `core/twin.py` · `core/graph.py` 는 `8ea4562` 와 같음 — 그 뒤 커밋은 개발1 의 `check_twin` 만) · 정본 `spec.md` **v0.4.1** (§5.4 라인 이름 · T-07 「DB 행의 물리 순서와 무관」 · T-08) · `decisions.md` D-28 · D-30 · D-31 · `progress-dev2.md` §11 · 2026-10-21 KST 14:09 ~ 14:20
- DB: `data/agentdash-qa1.db` 를 **처음부터 새로 백필** (`rm -f data/agentdash-qa1.db*; AGENTDASH_DB=data/agentdash-qa1.db make setup backfill` — 4.4 s · 원천 파일 588 · agent 74/249/1/6 · usage_event 26,606 · parse_error 0). 그 직후 `sqlite3.backup` 으로 스크래치 사본을 떠서(회귀 도구의 증분 수집으로 원본 DB 가 바뀌어도 대조가 흔들리지 않게) 트윈 대조를 **now `2026-10-21T05:10:00Z` 고정**으로 쟀다.
- 기대값은 `twin.build` · `graph.project_names` 코드가 아니라 spec §5.4 글자 + D-25~D-28 로 QA1 스크립트가 다시 계산했다. DB 는 `mode=ro` 로만 열었고, 행 순서를 바꾼 사본은 **메모리 사본**에서만 만들었다. 리포트에는 키 앞 14 자 · 숫자 · 시각만 적는다.
- 서버를 띄우지 않았다 — API 는 `TestClient`(lifespan 없이, 감시기 안 띄움)로 불렀다. 8095 (사람 서버) · QA2 의 서버 건드리지 않음. `config/budget.yaml` 변경 0 · `~/.claude/settings.json` sha1 `8a539108c7d4…` (D-29 기준값) 시작 · 끝 같음 · 훅 설치 0.
- 개발1 이 동시에 고친 `check_twin` 은 참고로만 돌렸다 (아래 §1.4) — 판정은 QA1 스크립트로.
- r6 에는 이번에 다시 잰 5 게이트(G-13 · G-14 · G-16 · G-31 · G-32)만 표지를 단다. 나머지(G-24 · G-26 · G-27 · G-28 등)는 r5 판정 그대로.

QA1 스크립트 (새 이름, `outputs/qa1/`):
- `r6_twin.py` — G-32 · T-08 독립 재계산 (범위 · D-28 이름 · 라인 순서 · 행/열 · 접힘 · **격자 cols · 라인 상자 x/y/h** · 누적 · 비용 · 스파크 · 지금 도구 · `elapsed_s`/`ended_ago_s`/`last_ago_s` · 겹침 전 쌍 · 라인 상자 포함 · 같은 행 정렬 · 문자열 ≤ 300)
- `r6_filter.py` — DEF-QA1-401 (필터 71 값 × since 2 = 142 경우 · D-02 `graph.build` 와 집합 대조)
- `r6_names.py` — DEF-QA1-402 / D-28 (32 프로젝트 이름 독립 계산 ↔ twin · D-02) · T-07 사본 3 개 × 27 조건 = 81 경우
- `r6_grid_api.py` — `/api/v1/twin?width=` (TestClient) · 이상 값 422 · 경계 값 200
- `r6_samples.py` — G-31 실제 DB 손 확인 (T-01 · T-03 · T-05 표본 5 · 시간 키 표본 5)
- (재사용) `r5_twin_edge.py` — 경계 E1~E6 을 새 사본에서 다시

## 요약 — 게이트별 QA1 판정

<!-- gate:G-13 -->
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  check_no_payload 테이블 11 · 행 61,207 · TEXT 340,617 값 중 300 자 초과 0 · 픽스처 23 파일 · 문자열 42,330 위반 0 · 트윈 응답 문자열 > 300 0 (24h · 7d · 6h · all × width 1400 · 360 · 4000 = 12 조합 + 필터 142 경우, r6_twin.py)

<!-- gate:G-14 -->
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest + DB 경로 (V-05)  PASS  check_readonly 정적 쓰기 호출 82 곳 중 원천 대상 0 · 읽기 전용 pytest 453 passed · 트리 변경 0 · DB 경로 씨앗 49/49 거부 · settings.json sha1 8a539108c7d4… 시작 = 끝 (D-29 기준) · QA1 스크립트는 DB mode=ro / 메모리 사본만

<!-- gate:G-16 -->
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)  PASS  check_bind host 127.0.0.1:8095 · py 65 · 기타 17 위반 0 · `33d2d0a..710683f` src · scripts 추가 줄에 외부 URL · `<script src>` · `<link href>` · 외부 전송 import 0 · 새 fetch 는 `/api/v1/twin?` 같은 출처 1 곳

<!-- gate:G-31 -->
G-31  배치 규칙 T-01~T-08 + Review Focus 5  PASS  test_twin · test_graph · test_twin_page 67 passed · DEF-QA1-403 새 테스트 5 가 spec 글자와 맞음 (30:00 남음/30:01 접힘 · FAILED+자손 접힘 · D-25 부모 24h 밖 · T-06+T-05 · 행 역순 사본) · T-08 테스트 8 · 실제 DB 손 확인 T-01 6 라인 · T-03 5 행 · T-05 표본 5/5 · 시간 키 표본 5/5 손계산 같음 · 남은 것 경미 DEF-QA1-501 (끝난 설비 「지금 도구」 null 이 spec · decisions 에 없음)

<!-- gate:G-32 -->
G-32  트윈 API — 누적 · 스파크 · 겹침 0 · 격자 (V-17)  PASS  독립 재계산 12 조합 불일치 0 — 24h 설비 13 · 라인 6 · 접힘 16 · 칸+접힘 29 = 응답 29 = DB 직접 29 · all 85 · 32 · 245 · 330 = 330 · T-08 cols 1400→2 · 360→1 · 4000→6 (all 10) 손계산과 같음 · 라인 상자 x/y/h 불일치 0 · 겹침 0 · 같은 행 어긋남 0 · 시간 키 불일치 0 · width 이상 12 값 422 · 필터 142 경우 D-02 와 같은 집합 · T-07 사본 81 경우 같음 · 경계 E1~E6 PASS

## 1. G-32 — `/api/v1/twin` 독립 재계산 (`r6_twin.py`, now `05:10:00Z`)

### 1.1 r5 에서 바뀐 계산
| 항목 | QA1 계산 (twin 코드 안 씀) |
|---|---|
| 라인 이름 | D-28: 그 `project_key` 의 **모든** 에이전트 `project_path`(끝 `/` 뗌) 중 `(길이, 문자열)` 최소 → 마지막 이름, 경로 0 이면 `project_key` (범위 · 필터와 무관) |
| 필터 | 라인 단위 — `project_key == f` 또는 `f` ∈ D-28 라인 이름 |
| T-08 격자 | 라인 고유 크기(열 수 · 행 수로 직접) → `cols` = `c ∈ [1, n]` 중 「열 j 너비 = j, j+c, … 번째 라인 최대 너비」 합 + (c − 1) × LINE_GAP ≤ width 인 **최대** c (없으면 1) → 라인 x = 앞 열 너비 합 + 간격, y = 앞 행 높이 합 + 간격, h = 그 행 최대 높이 |
| 설비 좌표 | 라인 상자 원점 기준 상대값으로 열 · 행 비교 (격자로 옮겨진 뒤에도) |
| 시간 키 | `elapsed_s` = now − state_since · `ended_ago_s` = now − ended_at (DONE · FAILED 만, 아니면 null) · `last_ago_s` = now − last_event_at (초 내림, 미래 0) |
| 지금 도구 | spec 글자(결과 없는 마지막 tool_call) 와 구현(끝난 설비 null, DEF-QA2-404) 을 따로 셈 |

### 1.2 결과
| since | width | 범위 직접 = 응답 | 설비 | 라인 | 접힘 | 칸+접힘 | cols 응답 = 직접 | 열 너비 | 행 높이 | 쓴 너비 | 불일치 | 겹침 설비/라인 | 같은 행 어긋남 | 문자열 > 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 24h | 1400 | 29 = 29 | 13 | 6 | 16 | 29 | 2 = 2 | 504 · 504 | 576 · 468 · 144 | 1032 | 0 | 0 / 0 | 0 | 0 |
| 24h | 360 | 29 = 29 | 13 | 6 | 16 | 29 | 1 = 1 | 504 | 6 행 | 504 | 0 | 0 / 0 | 0 | 0 |
| 24h | 4000 | 29 = 29 | 13 | 6 | 16 | 29 | 6 = 6 | 504·240·504·504·504·240 | 576 | 2616 | 0 | 0 / 0 | 0 | 0 |
| 7d | 1400 · 360 · 4000 | 63 = 63 | 25 | 11 | 38 | 63 | 2 · 1 · 11 | — | — | 1032 · 504 · 3936 | 0 | 0 / 0 | 0 | 0 |
| 6h | 1400 · 360 · 4000 | 29 = 29 | 13 | 6 | 16 | 29 | 2 · 1 · 6 | — | — | — | 0 | 0 / 0 | 0 | 0 |
| all | 1400 | 330 = 330 | 85 | 32 | 245 | 330 | 2 = 2 | 768 · 504 | 16 행 | 1296 | 0 | 0 / 0 | 0 | 0 |
| all | 360 | 330 = 330 | 85 | 32 | 245 | 330 | 1 = 1 | 768 | 32 행 | 768 | 0 | 0 / 0 | 0 | 0 |
| all | 4000 | 330 = 330 | 85 | 32 | 245 | 330 | 10 = 10 | 10 열 | 1224 · 684 · 792 · 468 | 3936 | 0 | 0 / 0 | 0 | 0 |

누적 · 비용 · 스파크 (모든 조합 불일치 0): 24h 출력 845,867 · 추정 보정 899,307 · $104.3650 · 스파크 합 55,527 (응답 = 직접, 값 있는 설비 6) / all 12,125,914 · 12,223,907 · $2,123.7821. 라인 상자 밖 설비 0 · 반입구 0 열(라인 x + 16) 위반 0 · 미도달 0. `build` 1.8 ~ 14.6 ms (첫 호출).

### 1.3 T-08 손계산 (24h · spec 글자 그대로)
T-01 순서 라인 너비 = [504, 240, 504, 504, 504, 240] (504 = 2×16 + 2×208 + 56 → 2 열짜리, 240 = 1 열짜리), LINE_GAP 24.
- **width 1400**: c = 3 → 열 너비 max(504,504) · max(240,504) · max(504,240) = 504·504·504 = 1512 + 48 = 1560 > 1400 ✗ · c = 2 → max(504,504,504) · max(240,504,240) = 504·504 = 1008 + 24 = **1032 ≤ 1400** → cols 2. 행 높이 max(576,144) = 576 · max(468,144) = 468 · max(144,144) = 144 → y 0 · 600 · 1092. 응답 (0,0) · (528,0) · (0,600) · (528,600) · (0,1092) · (528,1092), h 576 · 576 · 468 · 468 · 144 · 144 — 같음.
- **width 360**: c = 1 도 504 > 360 이지만 `cols ≥ 1` → 1 열 세로 쌓기 (v0.4 와 같음). y 누적 = 앞 h + 24 — 같음.
- **width 4000**: c = 6 (= 라인 수) → 2496 + 120 = **2616 ≤ 4000** → cols 6, 1 행, h 모두 576 — 같음.
- 「최대 열 수」: 응답 cols 보다 큰 c 가 들어가는 경우 0 (12 조합). 간격을 빼고 세면 all · 4000 에서 11 열이 들어가지만(아래 §5 관찰) 간격 포함 10 열이 맞다.
- T-06 과 함께 (all · limit 40 / 10 × width 360 · 1400 · 4000): 접힌 라인 23 / 30 · 겹침 0 · 같은 행 어긋남 0 · 칸+접힘 330 = 범위 330.

### 1.4 개발 도구 `check_twin` (참고, 같은 사본 · 같은 now)
```
G-32  트윈 API  PASS  설비 13 · 라인 6 · 접힘 16+0 · 범위 29/29/29 · 누적 0 · 스파크 0 · 시간 키 0 · 격자 0 (width 1400 · cols 2 · rows 3) · 겹침 0 · TEXT>300 0 · 1.6 ms
--since all: 설비 85 · 라인 32 · 접힘 245 · 330/330/330 · cols 2 · rows 16 · PASS
--since all --project "SongWol QR": 설비 5 · 라인 1 · 접힘 43 · 48/48/48 · PASS
```
QA1 독립 값과 같은 숫자 (R-2T-dev2-6 반영 뒤 `--project` 도 48 로 맞음).

### 1.5 API (`r6_grid_api.py`, TestClient)
| 확인 | 결과 |
|---|---|
| `width` 없음 · 1400 · 360 · 4000 · (since=all 로 1400 · 360 · 4000) — 응답 = `twin.build(now=generated_at)` | 7/7 같음 (초 단위 경과만 API now 의 소수점 때문에 0~1 초 차 — 허용) · 겹침 0 · grid 2/2/1/6 · 2/1/10 |
| `width` 없음 == `width=1400` | grid · 라인 상자 같음 |
| 이상 값 → 422 + `error` 에 `width` | `0` · `-1` · `abc` · `1.5` · `''` · `' '` · `1e3` · `1400px` · `100001` · `99999999` · `0x10` · `+5` — **12/12 422** (조용한 기본값 없음) |
| 경계 → 200 | `1` (cols 1) · `100000` (cols 6) · `' 1400'` (앞 공백 strip, cols 2) |
| `project=SongWol QR` · `Platform` (since=all) API = build | 같음 · 범위 48 · 210 |

### 1.6 경계 표본 (`r5_twin_edge.py` 를 새 사본에서 다시)
E1 스파크 분 경계 · E2 `<synthetic>` 제외(누적 포함) · E3 output_est 우선 · E4 비용 NULL → None · E5 T-06 limit 84/40/10/1 (칸 81/33/10/0 · 뒤 라인부터 · 330 = 330 · 겹침 0) · E6 API = build · `since=bad` 422 — **전부 PASS**.

## 2. 지난 결함 재검증

### 2.1 DEF-QA1-401 — 필터 = 라인 단위 (`r6_filter.py`)
필터 값 71 (프로젝트 키 32 · D-28 이름 32 · `SongWol QR` · `KyungDong` · `contracts` · `dev` · `MES` · `Platform` · 없는 값) × since 24h · all = **142 경우 실패 0**. 경우마다: 응답 `agents_in_scope` = 직접 기대 집합 E · 라인 키 집합 = E 의 project_key · `scope_count` = |E| · 겹침 0 · 필터 때문에 반입구로 밀려난 설비 0 · D-02 `graph.build(project=f)` 의 에이전트 노드 G ⊇ E 이고 G − E 는 전부 E 의 범위 밖 조상(D-02 는 조상을 붙인다).

| since · 필터 | E (트윈) | 옛 에이전트 단위 O | 하위 폴더로 새로 들어온 E − O | D-02 G (− 조상) |
|---|---|---|---|---|
| all · `SongWol QR` | 48 | 40 | 8 | 48 (0) |
| all · `KyungDong Data Platform` | 4 | 1 | 3 | 4 (0) |
| all · `OneTouch` · `PyoungChang Data Platform` | 4 · 4 | 1 · 1 | 3 · 3 | 4 · 4 |
| all · `Platform` | 210 | 192 | 18 | 210 (0) |
| all · `contracts` · `dev` (하위 폴더 이름) | 0 · 0 | 7 · 9 | — | 0 · 0 |
| 24h · `SongWol QR` | 1 | 0 | 1 | 2 (조상 1) |
| 24h · `Platform` | 6 | 5 | 1 | 10 (조상 4) |

r5 재현(`SongWol QR` 트윈 40 / D-02 48) → 48 = 48. **해결.**

### 2.2 DEF-QA1-402 / D-28 — 라인 이름 · T-07 (`r6_names.py`)
- N1: 프로젝트 32 의 D-28 이름 독립 계산 ↔ twin since=all 라인 32 · D-02 PROJECT 노드 32 — **불일치 0**. 경로가 여럿인 프로젝트 6: KyungDong · Limjingang · OneTouch · PyoungChang Data Platform (2) · SongWol QR Platform (3) · gerardo92 (2) — 전부 루트 이름. 24h 화면 5 번째 라인 「contracts」 → **「SongWol QR Platform」**, r5 의 「dev」 3 라인 → 각 「… Data Platform」. 경로 없는 프로젝트 0 (그 경우는 `test_line_name_shortest_path` 가 확인).
- N2 T-07: 메모리 사본 3 개 (agent · usage_event · tool_call · edge · state_log · file_touch 를 역순 · 시드 20261021 섞기 · 시드 7 섞기 — 사본마다 rowid 첫 행이 실제로 다름: `A:ac5bd434029a` / `S:e5d4d352-3a8` / `S:60d96f93-72c` / `A:ad84ae8b28ea`) × since 24h · 7d · all × width 1400 · 360 · 4000 × project 없음 · `Platform` · `SongWol QR` = **81 경우 응답 같음** (elapsed_ms 만 뺌). D-02 `graph.build(since=all)` 도 3 사본 같음 (`stats.ms` 만 뺌).

**해결.**

### 2.3 DEF-QA1-403 — 새 테스트가 spec 글자와 맞는가 (`tests/test_twin.py`, `c3043d9` · `feea67e`)
| r5 빈칸 | 테스트 | spec 글자 | 맞음? |
|---|---|---|---|
| ① T-05 정확히 30 분 | `test_T05_exactly_30m_stays` — ended = now − 30:00.000 은 칸 남음 · 30:01 은 접힘 · 부모 folded 1 | 「30 분 **넘게** 이전」 → 30:00 은 넘지 않음 | 맞음 |
| ② 30 분 넘은 FAILED | `test_T05_failed_after_30m_folds` — FAILED 45 분 + 그 자식 DONE 50 분 → 둘 다 세션 folded 2 · 범위 3 = 칸+접힘 3 | 「DONE · FAILED 이고 …」 · 「자손도 함께 접힌다」 | 맞음 |
| ③ D-25 부모 범위 밖 | `test_D25_parent_outside_24h` — 세션 · 중간 서브 30 h 전 DONE(범위 밖) · STALE 손자(살아 있음) → 손자만 반입구 아래 1 열 · 반입구와 같은 y · `U:` spawn 배관 · parent 키는 실제 부모 · links 0 · 범위 2 | D-25 「조상 끌어오지 않음 · 반입구 아래 1 열」 · T-02 「부모 없는 … 반입구 아래 1 열」 | 맞음 |
| ④ T-07 행 순서 | `test_T07_row_order_independent` — 11 테이블 rowid 역순 새 DB · 기본 · all · project | v0.4.1 「DB 행의 물리 순서와 무관」 | 맞음 (QA1 은 섞기 · width 까지 81 경우로 넓혀 확인) |
| ⑤ T-06 + T-05 | `test_T06_after_T05` — 라인 3 × (세션 + 살아 있는 4 + 끝난 3) · limit 10 → T-05 뒤 15 칸 > 10 → 마지막 라인 `-p-k2` 접힘 · hidden 8 · 남은 10 · 접힘 3 · 칸+접힘 24 · 겹침 0 | 「T-05 뒤에도 > 300 이면 T-01 순서 뒤 라인부터 … 300 이하가 될 때까지」 | 맞음 |

T-08 테스트 8 개도 글자와 대조: 1400 기본 · T-01 순서 왼→오른 · 위→아래 (`grid_1400`) · cols 1 세로 쌓기 (`narrow`) · 같은 행 y · h 같음 (`same_row_height`) · 열 너비 = 그 열 최대 (`column_width_is_widest`) · 300 설비 × width 1 · 360 · 1400 · 4000 겹침 0 · 라인 상자 포함 · ≤ 300 ms · 이상 값 (`bad_width` · `twin_api_width`). 「**최대** 열 수」 자체(cols + 1 이 안 들어감)를 직접 단언하는 테스트는 없다 — `column_width_is_widest` (width 1100 → 3 열이면 1296 > 1100) 에 간접으로만. QA1 이 실제 DB 12 조합으로 확인(§1.3)해 결함으로 올리지 않는다.

**해결.**

### 2.4 지난 결함 표
| ID | 등급 | 내용 | r6 | 근거 |
|---|---|---|---|---|
| DEF-QA1-401 | 경미 | `?project=` 가 에이전트 단위라 하위 폴더 에이전트가 빠짐 | **해결** | §2.1 — 142 경우 실패 0 · SongWol QR 48 = D-02 48 · 하위 폴더 이름(`contracts` · `dev`)은 라인 이름이 아니라 0 |
| DEF-QA1-402 | 경미 | 라인 이름이 DB 행 순서에 따라 바뀜 (T-07) | **해결** | §2.2 — D-28 독립 이름 32/32 · 사본 81 경우 같음 · D-02 라벨도 같은 규칙 |
| DEF-QA1-403 | 경미 | test_twin 빈칸 5 | **해결** | §2.3 — 새 테스트 5 모두 spec 글자와 맞음 |

## 3. G-31 — 실제 DB 손 확인 (`r6_samples.py`, now `05:10:00Z`)

**T-01 · T-08 라인 순서** (cols 2):
| 순서 | 격자 (행, 열) | 라인 | live | 가장 늦은 last_event_at | box |
|---|---|---|---|---|---|
| 0 | (0, 0) | Multi-agent Dashboard | 4 | 10-21T05:09:49Z | 0,0 504×576 |
| 1 | (0, 1) | lcomFine MES | 1 | 10-21T05:05:00Z | 528,0 240×576 |
| 2 | (1, 0) | Standard ML Platform | 4 | 10-14T17:55:19Z | 0,600 504×468 |
| 3 | (1, 1) | Standard MES Platform | 1 | 10-09T03:56:32Z | 528,600 504×468 |
| 4 | (2, 0) | SongWol QR Platform | 1 | 09-28T01:23:26Z | 0,1092 504×144 |
| 5 | (2, 1) | 00 PM Agent | **0** | 10-21T03:14:48Z | 528,1092 240×144 |

살아 있는 라인 5 가 최근 순, 살아 있는 설비 없는 00 PM Agent 는 더 최근이어도 맨 뒤 — 맞음.

**T-03** (Multi-agent Dashboard 5 칸): 행 0 열 0 `S:fa752590-2b3` (folded 13) → 행 1~4 열 1 `A:adc60434ce16` 04:50:10.998 · `A:a748170fabb6` 05:08:59.295 · `A:ab83c419570d` 05:08:59.305 · `A:af589d60fdce` 05:08:59.311 — started_at 오름차순(ms 까지) · 한 행 한 설비.

**T-05 접힘 표본 5** (24h 범위 칸 없는 16 중 ended 가장 이른 2 · 가운데 1 · 가장 늦은 2): `A:aaef4d6b5af3` DONE 275.9 분 · `A:a6fb649567d2` 275.6 분 (→ 00 PM 세션 칸) · `A:a19dae7c44b9` 194.4 분 · `A:a4a00befc95d` 46.3 분 · `A:a328106ffaca` 34.3 분 (→ `S:fa752590` 칸) — 전부 자식 없음 · 30 분 넘음 · 부모 칸 있음 → 맞음. 반대쪽: 칸에 남은 DONE `A:adc60434ce16` 은 ended 05:07:31 (2.5 분) — 접히지 않아 맞음.

**시간 키 표본 5** (손계산 = now − t 초 내림):
| 키 | 상태 | state_since | ended_at | last_event_at | 손 elapsed / ended_ago / last_ago | 응답 |
|---|---|---|---|---|---|---|
| A:adc60434ce16 | DONE | 05:09:52Z | 05:07:31.974Z | 05:07:31.974Z | 8 / 148 / 148 | 같음 · tool null |
| S:fc3908a3-be1 | DONE | 05:09:52Z | (없음) | 03:14:48.158Z | 8 / null / 6,911 | 같음 · tool null |
| A:a2a0029196a8 | STALE | 05:09:52Z | (없음) | 09-28T01:23:26.010Z | 8 / null / 2,000,793 | 같음 |
| A:a748170fabb6 | RUNNING | 05:09:52Z | (없음) | 05:09:37.036Z | 8 / null / 22 | 같음 |
| A:ab83c419570d | RUNNING | 05:09:52Z | (없음) | 05:09:47.766Z | 8 / null / 12 | 같음 · tool Bash |

(state_since 는 백필 시각이라 모두 8 초 — DEF-QA2-401 의 이유. ended_at 없는 DONE 세션의 `ended_ago_s` 는 null 로 지어내지 않음.) 독립 재계산 전체(12 조합 × 모든 칸)에서도 세 시간 키 불일치 0.

## 4. 회귀 (개발 도구 재실행, `AGENTDASH_DB=data/agentdash-qa1.db`)
| 도구 | 출력 (요지) |
|---|---|
| check_no_payload | `G-13  DB 본문 미저장  PASS  agentdash-qa1.db 테이블 11 · 행 61207 · TEXT 값 340617 · 상한 300 자 · 위반 0` |
| check_fixtures_redacted | `G-13  픽스처 본문  PASS  파일 23 · 줄 1284 · 문자열 42330 (그중 <redacted> 17576) · 위반 0` |
| check_readonly | 정적 PASS (파일 65 · 쓰기 호출 82 곳 · 원천 대상 0) · 읽기 전용 pytest PASS (**453 passed** · 트리 변경 0 · 16.6 s) · DB 경로 씨앗 PASS (49/49 거부 · 생긴 항목 0) |
| check_bind | `G-16  로컬 전용  PASS  host 127.0.0.1:8095 · 스캔 py 65 · 기타 17 · 외부 전송/바인드 위반 0` |
| G-16 diff 수동 | `git diff 33d2d0a..710683f -- src scripts` 추가 줄: `https?://` 0 · `<script src` 0 · `<link href` 0 · 외부 전송 import 0 · fetch 1 (`"/api/v1/twin?" + apiParams()` 같은 출처) |
| pytest 트윈 | `tests/test_twin.py tests/test_graph.py tests/test_twin_page.py` 67 passed |

## 5. 결함

| ID | 등급 | 내용 | 근거 · 재현 | 담당 |
|---|---|---|---|---|
| DEF-QA1-501 | 경미 | 끝난 설비(DONE · FAILED)의 `tool` · `target` 을 응답에서 **null** 로 비운다 (DEF-QA2-404 수정 `960f76b`). spec §5.4 글자는 「지금 도구(그 에이전트의 결과 없는 마지막 `tool_call` 의 `tool` · `target`)」 로 끝난 설비를 빼지 않고, `decisions.md` 에도 이 해석 항목이 없다 (D-31 은 경과만). 「여기 없는 것을 마음대로 정하지 않는다」 위반 — 동작 자체는 화면 의미상 합리적이라 경미. | 실제 DB since=all 에서 spec 글자로는 값이 있어야 하는 끝난 설비 1 (`r6_twin.py` `final_machines_with_open_tool_spec_letter` 1, 24h · 7d 0) · `test_final_machine_has_no_current_tool` 가 이 동작을 고정 | 개발2 (`decisions.md` 에 가설 등록 → 사람 확인, 필요하면 spec 문구) |

치명 0 · 중대 0 · 경미 1.

## 6. 관찰 (결함 아님)
- T-08 「width 에 들어가는 최대 열 수」 를 구현은 열 사이 `LINE_GAP` 24 를 포함해 센다 (spec 글자엔 간격 언급 없음). 간격을 빼면 all · 4000 에서 11 열이 들어가지만 라인 상자가 닿게 되어 T-04 「라인 상자끼리 겹침 0」 의 여유가 없어진다 — 간격 포함이 맞는 해석으로 본다.
- 같은 행 높이 맞춤 때문에 접힌 라인(머리 한 줄)이 높은 라인과 같은 행에 오면 상자 h 가 그 행 높이로 커진다 (limit 10 · 4000 에서 확인, 겹침 0). spec 글자 그대로.
- D-31 (화면이 보내는 width = 카드 ÷ 0.8) 은 가설 — 서버 T-08 규칙은 spec 그대로이고 API 기본 1400 확인. 화면 쪽은 QA2 / 사람 몫.
- `width` 는 앞뒤 공백을 strip 하고 받는다 (`' 1400'` → 200). 숫자가 아닌 것 · 소수 · 부호 · 범위 밖(1 ~ 100,000) 은 모두 422.
- `graph.project_label` 은 이름을 60 자로 자른다 — 실제 DB 에서 60 자 넘는 라인 이름 0 이라 D-28 독립 계산과 차이 없음.
- 백필 직후 `state_since` 가 전부 백필 시각이라 `elapsed_s` 는 모든 설비가 같다 (8 초) — DEF-QA2-401 로 화면은 `ended_ago_s` · `last_ago_s` 를 쓴다(D-31 가설).
