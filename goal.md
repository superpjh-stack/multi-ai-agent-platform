# /goal — 멀티 에이전트 대시보드 2차-A (화면 7 · API 13 · 검증 16 · 게이트 G-01~G-30)

> **이 문서가 메타프롬프트다.** `/loop` 가 매 회전 이 문서를 판정 기준으로 읽는다. 투입되는 에이전트(아키텍트 1 · 개발 2 · QA 2)도
> 작업 전에 이 문서와 `CLAUDE.md` · `decisions.md` · `progress.md` 를 먼저 읽는다.
> 1차(G-01~G-22, 2026-10-17 EXIT)는 `goal-v1.md` 에 보존한다. 프로토콜 · 금지 사항은 1차와 같고, 다른 것만 여기 적는다 — 1차 문서의 §4.3 · §8 은 그대로 유효하다.
> 수치는 `spec.md` v0.3 에서 센 값이다(§9).

| 항목 | 값 | 출처 |
|---|---|---|
| 시스템 | 1차 대시보드 + 결정 확정 · D-17 추정 출력 · 예산 · 비용 추세 · 캐시 적중률 · D-07 · WAITING 브라우저 알림 · 공통 화면 틀 | `problem.md` §4.2 G11~G16 |
| 정본 | `intro.md` · `problem.md`(2차-A 개정) · `spec.md` v0.3 — **사람만 고친다** | — |
| 설계 · 계획 | `docs/superpowers/specs/2026-10-20-agentdash-v2a-design.md` · **`docs/superpowers/plans/2026-10-20-agentdash-v2a.md` (태스크 1~15 · 인터페이스 · 테스트 이름)** | — |
| 규모 | 화면 **7** · API **13** · 테이블 **11** · 상태 8 · 판정 규칙 **13** · 연결 규칙 7 · 진척 규칙 7 · 검증 **16** (V-01~V-16) · 훅 이벤트 9 | `spec.md` |
| 출발점 | `b91f5e6` 1차 완료 → `6e31d6d` 정본 개정 (G-01~G-22 PASS · pytest 296) | `git log` |
| 범위 밖 | 2차-B 제어(실행 · 중지 · 메시지) · 예산/멈춤 알림 · macOS/Slack · 화면에서 예산 편집 · 예산 **금액**(사람이 넣는다) | `problem.md` §5 |
| 완료 기준 | **G-01~G-30 전부 PASS · QA 치명 0 · 중대 0 · 연속 2 회전 변화 없음** | §4.4 |

---

## 0. 이 문서를 어떻게 쓰는가

### 0.1 루프 기동 — 이 한 줄을 붙여 넣는다

```
/loop goal.md 를 판정 기준으로 멀티 에이전트 대시보드 2차-A 를 만든다. §4.2 한 회전 절차를 그대로 따른다 —
progress.md·decisions.md 를 읽고(2차-A 섹션이 없으면 §3.1 Phase 0 부터), `make gate` 로 G-01~G-30 을 실측하고,
FAIL 중 가장 앞선 웨이브의 항목을 골라 계획(docs/superpowers/plans/2026-10-20-agentdash-v2a.md)의 해당 태스크를
§5 프롬프트로 담당 에이전트에게 맡기고(병렬 가능한 것은 한 번에), 보고를 믿지 말고 게이트 명령을 직접 다시 돌려
확인한 뒤 실측값과 검증 명령을 progress.md 에 적고 로컬 커밋한다. ~/.claude 와 이 폴더 밖에는 절대 쓰지 않는다.
막히면 decisions.md 에 D-번호로 `차단`을 올리고 다음 항목으로 넘어간다. 게이트를 낮추거나 테스트를 건너뛰지 않는다.
§4.4 종료 조건을 만족하면 최종 보고를 쓰고 루프를 멈춘다.
```

중단 후 재개는 `/re-begin` 또는 위 한 줄. 상태는 전부 파일에 있다.

### 0.2 1차와 다른 점 — 먼저 알고 시작한다

- **회귀가 먼저다.** G-01~G-22 는 이미 PASS 다. 2차 작업이 그중 하나라도 FAIL 로 만들면 그것이 다음 작업이다 (안전 게이트 G-13~G-16 은 무조건 최우선).
- **스키마가 바뀐다.** `usage_event` · `usage_daily` 에 열 2 개씩. 기존 DB 는 `init_db` 가 열을 덧붙이지만 `output_est` 는 원천을 다시 읽어야 채워진다 — 실측 게이트(G-24 · G-26~G-28)는 **새로 백필한 DB** 로 잰다 (`rm -f data/agentdash.db && make setup backfill`, `data/` 는 저장소 안).
- **길이는 재고 버린다.** D-17 추정은 text · 도구 입력의 글자 수만 쓴다. 본문은 물론 길이 숫자도 DB 에 남기지 않는다(spec §2.3).
- **금액을 지어내지 않는다.** `config/budget.yaml` 은 `null` 로 시작한다. 예산 경고의 실측은 테스트 · QA 의 가짜 한도로만 한다 — 실제 파일에 금액을 넣지 않는다.
- **알림은 브라우저 안에서 끝난다.** 서버는 외부 프로세스를 띄우지 않고 SSE 도 그대로다. G-16 검사 범위가 그대로 적용된다.
- **D-08 은 웹 페이지를 읽는다.** 공식 단가 페이지를 에이전트가 읽어(WebFetch) 대조한다 — 코드에 외부 전송을 넣는 것이 아니다. 값이 페이지에 없으면 `차단` 으로 두고 `[추정]` 표시를 유지한다.

---

## 1. 목표

**1차 대시보드를 그대로 지키면서, 기록이 틀린 숫자(D-17)를 기록값 옆에 추정으로 보이고, 한도 대비 사용 · 비용 흐름 · 캐시 효율을 D-07 한 화면에, 내 차례를 브라우저 알림으로, 일곱 화면을 한 틀로 보여 준다.**

끝났다고 말할 수 있는 상태는 이것뿐이다.

1. G-01~G-22 회귀 PASS (G-01 은 spec v0.3 블록 기준, G-17 은 화면 7 · API 13).
2. 새로 백필한 DB 에서 의심 요청 비율이 원천 재측정과 ±0.5 %p 안이고, 의심 행 `output_est ≥ output_tokens`, 비의심 행 `NULL` (V-12).
3. 예산 · 추세 · 캐시 적중률 숫자가 `usage_event` 직접 합 · 손계산과 같다 (V-13~V-15).
4. 알림이 전이마다 한 번만 뜨고(첫 로드 0 · 재전송 0 · 두 탭 1), 화면 7 이 두 테마에서 대비 기준 · 390 px · 콘솔 오류 0 (G-29 · G-30).
5. `decisions.md` 의 D-07 · D-08 · D-13 · D-14 · D-17 · D-18 · D-19 가 `확정`(또는 D-08 만 근거 있는 `차단`)이고 화면에 「가설」 표시가 없다.

---

## 2. 수용 게이트

### 2.1 회귀 (1차 G-01~G-22)

`goal-v1.md` §2 그대로. 바뀌는 것만:

| 게이트 | 바뀐 기준 |
|---|---|
| G-01 | `schema.sql` = `spec.md` v0.3 §3 블록 (열 4 추가), `init_db` 가 v0.2 DB 에 열을 덧붙임 |
| G-09 | 표에 spec v0.3 세션 평가 순서 행 추가 (R-03 > R-04 > R-02b · pid 소멸 = R-06/R-07) |
| G-17 | 화면 **7** (D-01~D-07) + API **13** 전부 200, 빈 DB 에서도 200, placeholder 0 |
| G-21 | D-07 포함, 밝은 · 다크 두 테마 |

### 2.2 2차-A 게이트

| # | 게이트 | 통과 기준 | 판정 수단 · 계획 태스크 |
|---|---|---|---|
| G-23 | 결정 반영 | D-07 · 08 · 13 · 14 · 17 · 18 · 19 `확정`(근거 = spec v0.3 절) · D-08 대조 출처 · `src/` 에 `가설 D-18` · `D18_NOTE` 0 | `check_decisions` · T2 · T9 |
| G-24 | 추정 열 | `test_usage_est.py` 전부(29/30 · 400/401 경계 · 하한 · synthetic · 두 번 나눠 읽기) + 실제 백필 V-12 | `test_usage_est.py` + `check_usage_est` · T5 · T6 |
| G-25 | 하드 링크 | 이미 있는 DB 파일 `st_nlink > 1` 거부 (DEF-QA1-201) | `test_settings.py` · T1 |
| G-26 | 예산 | 80/100 % 경계 · KST 일/월 · 프로젝트 매핑 · `unset` · `no_records` · 단가 없음 미합산 + 실제 DB 칸 = 직접 합 (≤ $0.01) | `test_budget.py` + `check_budget` · T7 |
| G-27 | 추세 | 일 · 주(KST 월요일) · 월 합 = `usage_daily` 합 = `usage_event` 합 (기록 · 추정) | `check_trend` · T7 |
| G-28 | 캐시 적중률 | 표본 10 손계산 = API (≤ 0.001) · 분모 0 → `—` | `check_efficiency` · T7 |
| G-29 | 알림 | 정적 계약 테스트 + 브라우저 E2E (가짜 루트 훅 POST → 알림 1 · 같은 전이 재수신 0 · 첫 로드 0 · 두 탭 1 · 권한 거부 시 배지만) | `test_alerts.py` + `outputs/e2e/alerts.md` (QA2) · T10 |
| G-30 | 디자인 | 두 테마 토큰 대비(글자 ≥ 4.5 · 도형 ≥ 3.0) · `_dev*_style` include 0 · D-01~D-07 × 두 테마 스크린샷 · 390 px · 콘솔 0 | `check_contrast` + `test_design.py` + `outputs/e2e/design.md` (QA2) · T4 · T12 · T13 |

### 2.3 범위 밖 — 실패로 보지 않는다

- 훅 실설치 상태의 `WAITING_PERMISSION` 알림 실측 (사람이 설치한 뒤) — 설치 전에는 `WAITING_INPUT` 알림만 실측, 권한 대기는 가짜 루트 훅 POST 로.
- 예산 실제 금액 · 실제 청구 금액과의 일치.
- 2차-B 제어 기능.

---

## 3. 팀 편성과 웨이브

```
Phase 0  아키텍트   T1 스키마 v0.3 · 하드 링크 / T2 budget.yaml · D-08 · decisions 확정 / T3 gate G-30 · 라우트 7·13 / T4 base.html 틀 · 대비
   ↓
웨이브 A  개발 2 (병렬)   개발1 T5 추정 출력 → T6 daily·표기·CSV → T7 budget → T8 D-07 / 개발2 T9 가설 표시 제거 → T10 알림 → T11 D-01 띠(T7 공표 뒤)
   ↓
웨이브 B  개발 2 (병렬)   개발1 T12 D-04~D-07 공통 틀 / 개발2 T13 D-01~D-03 공통 틀
   ↓
웨이브 C  QA 2 (병렬)     QA1 T14 숫자 · 안전 / QA2 T15 상태 · 알림 · 디자인 · 회귀 E2E
   ↓
웨이브 D  결함 수정 (담당 개발) — 안전 · 회귀 결함 최우선, C→D 반복
```

### 3.1 Phase 0 — 아키텍트

계획 T1 → T2 → T3 → T4 순서. 끝 = G-01 · G-13~G-17 · G-25 PASS, G-01~G-22 회귀 PASS, `make gate` 가 30 행. `spec.md` 에서 §9 숫자를 직접 세어 `progress.md` 2차-A 섹션에 적는다. `CLAUDE.md` 의 규모 · 소유 표 · 완료 기준을 2차-A 로 갱신한다(아키텍트 소유).

### 3.2 소유 — 1차 표(CLAUDE.md) + 새 파일

| 담당 | 새로 갖는 파일 |
|---|---|
| 아키텍트 | `config/budget.yaml` · `tools/check_decisions.py` · `tools/check_contrast.py` · `tests/test_design.py` · `goal-v1.md`(읽기만) |
| 개발1 | `core/budget.py` · `app/routers/insights.py` · `templates/insights.html` · `tools/check_{usage_est,budget,trend,efficiency}.py` · `tests/test_{usage_est,budget,insights}.py` |
| 개발2 | `templates/_alerts.html` · `tests/test_alerts.py` |

- 공용 시그니처 `budget.status · budget.worst · budget.trend · budget.efficiency` 는 개발1 이 T7 끝에 `progress-dev1.md` §1 에 공표한다. 개발2 T11 은 그 뒤 시작.
- `main.py` `ROUTERS` 교체(T8) · `test_design.py` xfail 해제(T13)는 아키텍트에게 `progress-devN.md` §3 으로 요청.

### 3.3 QA

| 담당 | 범위 | 산출 (같은 묶음 다음 회차) |
|---|---|---|
| QA1 | G-24 · G-26 · G-27 · G-28 원천 재집계 · 손계산, G-13 · G-14 · G-25 재확인(하드 링크 재현), G-04~G-08 회귀 | `outputs/qa1-데이터안전-r4.md` |
| QA2 | G-12 재대조(spec v0.3 글자 기준) · G-29 · G-30 · G-21 · G-22 | `outputs/qa2-상태대조-r4.md` · `outputs/e2e/alerts.md` · `outputs/e2e/design.md` · `outputs/e2e/self-observe-r4.md` |

결함 `DEF-QA{n}-3nn`. 치명 = 원천 쓰기 · 본문(또는 길이 숫자) 저장 · 기존 훅 손상 · 외부 전송 · **실제 `budget.yaml` 에 금액 기입**. QA 는 고치지 않는다. 리포트 판정 행은 `<!-- gate:G-nn -->` 표지 바로 다음 줄 (CLAUDE.md 「QA 리포트 형식」).

---

## 4. 루프 엔지니어링 프로토콜

`goal-v1.md` §4.1~§4.3 · §4.5 그대로. 바뀌는 것만:

### 4.2 한 회전 (추가)

- 2 번 판정에서 **회귀(G-01~G-22) FAIL 은 2차 게이트보다 먼저** 고친다 (안전 게이트가 그보다 먼저).
- 4 번 기동 때 계획의 태스크 번호를 프롬프트에 적는다 — 에이전트는 그 태스크의 Files · Interfaces · Step 을 그대로 따른다.
- 5 번 검증의 실측 게이트(G-24 · G-26~G-28)는 **같은 시각에 새로 백필한 DB** 로 잰다.

### 4.4 종료 조건 (EXIT)

1. G-01~G-30 **전건 PASS** (`차단` 은 D-번호 · 사유, 훅 실설치 측정만 `미검증` 허용)
2. QA 리포트 r4 2 종 + e2e 2 종, **치명 0 · 중대 0**
3. **연속 2 회전 새 실측 변화 없음**

최종 보고 (`progress.md` 맨 위): 게이트 판정표 · D-목록 결과 · **사람이 할 일** (① `config/budget.yaml` 에 금액 입력 ② D-01 에서 「알림 켜기」 ③ 원하면 `make hooks-install` 로 권한 대기 알림 활성화) · 2차-B 설계로 넘길 관찰.

---

## 5. 에이전트 기동 프롬프트

공통 서두는 `goal-v1.md` §5 그대로 쓰고, 그 끝에 이 두 줄을 붙인다.

> 이번은 **2차-A** 다. 정본은 `spec.md` **v0.3**, 할 일은 `docs/superpowers/plans/2026-10-20-agentdash-v2a.md` 의 **Task [번호]** — Files · Interfaces · Step 을 그대로 따르고, 테스트를 먼저 쓴 뒤 구현한다(TDD). 1차 게이트 G-01~G-22 를 깨면 끝난 것이 아니다 — `uv run pytest -q` 전체와 `make gate` 를 돌려 회귀가 없음을 확인한다.
> 길이 숫자 · 예산 금액은 DB · 코드 · 실제 설정 파일에 넣지 않는다 (금액은 테스트의 가짜 값만).

| 역할 | 맡길 태스크 |
|---|---|
| 아키텍트 | T1 · T2 · T3 · T4 (Phase 0) · 웨이브 중 요청 처리 (`main.py` ROUTERS · xfail 해제 · pricing.yaml) |
| 개발1 | T5 → T6 → T7 (공표) → T8 → T12 |
| 개발2 | T9 → T10 → T11 (T7 공표 뒤) → T13 |
| QA1 | T14 |
| QA2 | T15 |

---

## 9. 실측 방법

```bash
# spec.md v0.3 에서 직접 센다 — 테이블 11 · 상태 규칙 13 · 연결 규칙 7 · 진척 규칙 7 · 검증 16 · 화면 7 · API 13
grep -cE '^CREATE TABLE' spec.md                               # 11
grep -cE '^\| R-[0-9]+[ab]? \|' spec.md                         # 13
grep -cE '^\| L-0[1-7] \|' spec.md                              # 7
grep -cE '^\| P-0[1-7] \|' spec.md                              # 7
grep -cE '^\| V-[0-9]{2} `' spec.md                             # 16
grep -cE '^### D-0[1-7] ' spec.md                               # 7
grep -cE '^\| `(GET|POST) /' spec.md                            # 13

rm -f data/agentdash.db && make setup backfill   # 실측 게이트용 새 DB (저장소 안)
make gate                                        # 판정표 30 행
```
