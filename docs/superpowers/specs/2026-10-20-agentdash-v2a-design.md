# 멀티 에이전트 대시보드 2차-A 설계 — 읽기 전용 고도화

- 날짜: 2026-10-20 · 상태: 사람 승인 (설계 3 절 모두) · 다음: spec v0.3 · problem 개정 · 새 goal.md 초안
- 출발점: 1차 완료 `b91f5e6` (G-01~G-22 PASS 22 · pytest 296 · QA 치명 0 중대 0)
- 2차-B (에이전트 실행 · 중지 · 메시지 = 원천 쓰기)는 **이 설계 밖**. 2차-A 가 끝난 뒤 안전 모델부터 별도 설계한다.

## 1. 정한 것 (사람 답)

| 항목 | 결정 |
|---|---|
| 진행 방식 | 1차 코드 위에 개선 · 정본 개정(spec v0.3 · problem 2차 범위 · 새 goal.md, 구 판은 `goal-v1.md`) |
| D-17 | ② 길이 기반 `[추정]` 열 추가 (`usage_event` 스키마 변경) |
| D-13 · D-18 · D-19 | 지금 구현대로 spec 에 확정 |
| D-07 | 현재 `.gitignore` 확정 |
| D-08 | 루프에서 공식 단가 페이지 대조 후 `[추정]` 해제 (다르면 값 수정 + `make reprice`) |
| 경미 결함 | DEF-QA1-201 (하드 링크) · DEF-QA2-201 (D-18 표시, 확정으로 해소) · Makefile `run` 주석 |
| 알림 | 브라우저 Notification + 화면 배지, **WAITING(입력 · 권한) 전이만** |
| 예산 | 전체 일 · 월 + 프로젝트(cwd)별 일 · 월. 80% · 100% **화면 경고만**(알림 아님). 금액은 사람이 나중에 입력 — 기본 `null` |
| 추세 | 일 · 주 · 월 비용 추세 |
| 효율 | 캐시 적중률 |
| 디자인 | 깔끔한 대시보드형 — 밝은 기본 + 다크 모드, 여백 넓게, 차트 중심 |

가정(사람 확인함): 안전 게이트 G-13~G-16 그대로 · G-01~G-22 회귀 유지 · 설정은 파일(`config/budget.yaml`), 화면 편집 없음.

## 2. 데이터 모델 · 결정 반영

### 2.1 D-17 추정 열 (spec §3 · §6)
- `usage_event` 에 `output_est INTEGER` (의심 요청만 하한 추정, 아니면 NULL) · `cost_est_usd REAL` (output_est 반영 비용) 추가.
- `usage_daily` 에 `output_est INTEGER` · `cost_est_usd REAL` 추가. 테이블 수 11 그대로.
- 의심 판정 (QA1 `outputs/qa1/stream_heuristic.py` 를 spec 으로 승격): 같은 `requestId` 의 기록 output 최대 < 30 **이고** content 블록 JSON 길이 > 400 자.
- 추정값: (text 길이 + 도구 입력 길이) ÷ 4. 수집 때 **길이 숫자만** 재고 본문은 저장하지 않는다 (G-13 유지).
- 화면 · API · CSV: 「기록」 과 「[추정] 보정 포함」 을 나란히. 표기 `기록상 과소 (D-17)` → `추정 보정 (D-17)`.

### 2.2 결정 확정 (decisions.md `확정` + spec 문구)
- D-13 → §3.1 세션 이름: S1 `name` → 마지막 `agent-name` 줄 → `cwd` 마지막 이름.
- D-18 → §4.2 R-03 조건: `status = idle` **또는** (`busy` · 5 분 넘게 기록 없음). 순서 R-02a → 훅 도구 실행 중 → R-03 → R-04(D-14) → R-02b. 화면 「가설 D-18」 표시 전부 제거.
- D-19 → R-06 · R-07 의 「S1 없음」 을 「S1 없음 또는 pid 소멸」 로.
- 판정 규칙 13 · 연결 규칙 7 수는 그대로.

### 2.3 경미 결함
- DEF-QA1-201: DB 파일이 이미 있고 `st_nlink > 1` 이면 거부 (`settings.py` / `db/conn.py`, 아키텍트).
- Makefile `run` 주석 정정.

## 3. 새 기능 · 화면

### 3.1 D-07 비용 · 효율 `/insights` (신규)
- 예산 게이지: 전체 오늘 · 이번 달, 프로젝트별 오늘 · 이번 달. ≥ 80% 주황 · ≥ 100% 빨강. 기준 `cost_est_usd`, 기록 기준 병기. KST.
- 비용 추세: 일 · 주(KST 월요일 시작) · 월 전환. 선 2 (기록 · 추정 보정) + 프로젝트별 쌓은 막대.
- 캐시 적중률: §6 공식 그대로. 프로젝트 · 세션 · 에이전트 순위(낮은 적중률 × 큰 비용 순) + 일별 추세.
- D-04 는 표 · CSV 중심으로 유지.
- D-01: 예산 ≥ 80% 면 맨 위 경고 띠 → D-07 링크.

### 3.2 설정 `config/budget.yaml` (아키텍트)
```yaml
warn_ratio: 0.8
total:    {daily_usd: null, monthly_usd: null}
projects: {}        # "<project_path 마지막 이름>": {daily_usd: …, monthly_usd: …}
```
`null` 이면 게이지 대신 「한도 미설정」. 금액을 지어내지 않는다.

### 3.3 알림
- 서버 변경 없음. `base.html` 공통 스크립트가 SSE `agent.state` 를 받아 `WAITING_INPUT` · `WAITING_PERMISSION` 으로 **바뀌는 순간**만 Notification (프로젝트 · 이름 · 대기 종류, 누르면 D-03).
- 탭 제목 · 파비콘 배지 `(N)`.
- 처음 열 때 이미 대기 중인 것은 알리지 않음 · `agent_key + state_since` 1 회 · BroadcastChannel 로 여러 탭 중 1 탭만.
- 권한은 「알림 켜기」 버튼(사용자 동작)으로 요청, 켜짐/꺼짐은 localStorage.
- 훅 미설치면 권한 대기 구분 불가(§9.3) — 입력 대기로 묶어 알림.

### 3.4 API (10 → 13)
- `GET /api/v1/budget`
- `GET /api/v1/trend?grain=day|week|month&from=&to=&group=total|project`
- `GET /api/v1/efficiency?group=project|session|agent&from=&to=`

### 3.5 디자인
- `base.html` 에 색 · 간격 · 글꼴 토큰, 밝은 기본 + `prefers-color-scheme` 다크 + 수동 토글.
- §4.1 상태 색 8 을 두 테마에서 대비 확보되게 재정의.
- D-01~D-07 같은 카드 · 표 · 차트 틀. 390px 가로 스크롤 0 유지.
- 차트: Chart.js 고정 버전 (jsdelivr, Cytoscape 와 같은 출처).
- `_dev1_style.html` · `_dev2_style.html` 을 공통 스타일 하나로.

규모: 화면 7 · API 13 · 테이블 11 · 상태 8 · 판정 규칙 13 · 연결 규칙 7 · 진척 규칙 7 · 훅 이벤트 9.

## 4. 게이트 · 루프

### 4.1 회귀
G-01~G-22 계속 PASS. 바뀌는 것: G-01 스키마 대조 기준 = spec v0.3 · G-09 R-03/06/07 경계 행 추가 · G-17 화면 7 · API 13 · G-21 D-07 포함 · 두 테마.

### 4.2 신규

| 게이트 | 항목 | 기준 | 판정 |
|---|---|---|---|
| G-23 | 결정 반영 | D-07 · 08 · 13 · 17 · 18 · 19 `확정`(근거 줄) · 템플릿/API 「가설 D-18」 0 · D-08 대조 결과 기록 | `check_decisions` |
| G-24 | 추정 열 | 의심 판정 · 추정 공식 표 기반 테스트 (29/30 · 400/401 경계) · 실제 백필 의심 비율 = `stream_heuristic` ±0.5%p · 의심 행 `output_est ≥ output_tokens` · 비의심 NULL · 본문 0 | `test_usage_est` + `check_usage_est` |
| G-25 | 하드 링크 | `st_nlink>1` DB 거부 테스트 · DEF-QA1-201 재현 → 거부 | `test_settings` |
| G-26 | 예산 | 80/100% 경계 · KST 일 · 월 · 프로젝트 매핑 · `null` → 미설정 · 실제 DB API = `usage_event` 직접 합 | `test_budget` + `check_budget` |
| G-27 | 추세 | 일 · 주 · 월 합 = `usage_daily` 합 = `usage_event` 합 (기록 · 추정 각각) · 주 = KST 월요일 | `check_trend` |
| G-28 | 캐시 적중률 | 표본 10 §6 공식 손계산 = API | `check_efficiency` |
| G-29 | 알림 | 브라우저 E2E: 가짜 루트 훅 POST → Notification 1 회 · 같은 전이 재수신 0 · 첫 로드 0 · 탭 2 개여도 1 | `outputs/e2e/alerts.md` |
| G-30 | 디자인 | D-01~D-07 × 밝은 · 다크 스크린샷 · 상태 색 대비 ≥ 4.5:1 · 390px 가로 스크롤 0 · 콘솔 오류 0 | `check_contrast` + `outputs/e2e/` |

### 4.3 팀 · 웨이브 (1차 소유 규칙 유지)
- Phase 0 아키텍트: spec v0.3 · problem 개정 **초안 → 사람 승인 → 반영** · `schema.sql` 열 · `config/budget.yaml` · `base.html` 토큰 + 공통 스타일 · 새 검사 도구 · `gate` G-30 까지 · 하드 링크 거부 · Makefile 주석.
- 웨이브 A — 개발1: D-17 수집(길이 · 추정) · `usage_daily` · 예산/추세/효율 계산 + API 3 · D-07 · D-04 표기 · D-08 대조. 개발2: D-18 표시 제거 · 알림 스크립트 · D-01 예산 띠.
- 웨이브 B — 디자인 적용: 개발1 D-04~D-07 · 개발2 D-01~D-03.
- 웨이브 C — QA1 데이터 안전 · 숫자 (G-24 · 26 · 27 · 28) · QA2 상태 · 화면 (G-29 · 30 · G-12 재대조). 리포트 `-r1` 부터.

### 4.4 EXIT
G-01~G-30 전부 PASS · QA 치명 0 · 중대 0 · 연속 2 회전 변화 없음.

### 4.5 보존
1차 `goal.md` → `goal-v1.md`. 1차 QA 리포트는 그대로 두고, 2차 QA 는 같은 묶음의 다음 회차(`-r4`)로 낸다 — `gate.py` 는 묶음마다 가장 최근 회차만 읽는다.
