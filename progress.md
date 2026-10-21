# progress.md — 검증된 현황의 유일한 진실

> 실측값 + 검증 명령만 적는다. 본문은 붙여 넣지 않는다(숫자 · 경로만). 상태 파일 형식은 `goal.md` §4.1.

## 회사별 에이전트 화면 — 2026-10-22 (사용자 설계 승인, D-39)

- D-01 회사별 요약·선택 회사 에이전트·프로젝트 링크·필요 역할·판단 필요 안내 추가. 기존 평면도·패널·피드 유지. 회사 분류는 기존 사전·메타데이터 기반, DB 소속/관계/상태/스키마 변경 없음. D-06 회사 행 앵커 추가.
- 회귀: 최종 `uv run pytest -q` **484 passed in 18.18s**. 회사 분류/선택/갱신/예외/파이프라인/필터 URL 및 운영 구버전 템플릿 호환 테스트 **10개**. 직전 관련 묶음 `uv run pytest tests/test_companies.py tests/test_dashboard.py tests/test_twin_page.py tests/test_pipeline.py -q` **62 passed** (호환 테스트 추가 전). `git diff --check` PASS.
- 새 백필: `AGENTDASH_DB=data/agentdash-company-review-20261022.db uv run --no-sync --no-cache python -m agentdash.collect.backfill` — 원천 679 파일 · 에이전트 377(워크플로 묶음 1 포함) · 사용량 28,451 · 파싱 오류 0 · 10.0초.
- 수용 게이트: 위 검증 DB로 `uv run --no-sync --no-cache python src/agentdash/tools/gate.py --strict` — **PASS 34 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 1**, strict exit 1. G-15 송신은 운영 8095 사용 중으로 미검증. 운영 서비스를 중단하지 않았다. G-14 읽기 전용 가짜 루트 pytest **483 passed**, 원천 트리 변경 0, DB 경로 거부 49/49. 최종 정적 `check_readonly.py --static` 원천 대상 0.
- 브라우저: 임시 8096·검증 DB·감시 끔. Chrome 1400×900/390×844 밝은·어두운 테마, scrollWidth/clientWidth **1385/1385 · 375/375**. 모바일 목록 가로 넘침 **294/294**, 이름·상태·프로젝트·근거 세로 표시. 앱 콘솔 error **0**, SSE 연결됨. 회사 선택 후 목록 접힘, 기간 7d 변경 후 회사 URL·상세 유지 확인.
- 실제 분류: 전체 에이전트 376 = 등록 회사 연결 71 + 미확인 305. 기존 사전에 없는 영문 프로젝트명 등은 임의 연결하지 않았다. 회사 사전·예산·정본 변경 없음.
- 화면 캡처: `outputs/e2e/companies-20261022/{desktop,mobile}-{light,dark}.jpg` · `overview-light.jpg` (Git 제외). 운영 8095 재시작·서비스 변경 없음. 8095 브라우저에서 기존 화면·SSE 연결됨·재시작 전 회사 현황 안내 표시를 확인했다. 운영의 새 Python 라우터 반영에는 추후 서비스 재시작이 필요하다. 검증용 PID 62433 종료 완료·검증 탭 닫음·viewport 초기화.

## Hostinger 현재 Mac 기록 배포 — 2026-10-21 (사용자 「1번」, D-38)

- 주소: `https://srv1934103.hstgr.cloud:8443/`. VPS 프로젝트 `/docker/multi-ai-agent-platform`, `gateway` 컨테이너 **healthy**. Hostinger Docker Manager 3페이지에서도 프로젝트 실행 중 확인.
- Mac `local.agentdash.hostinger-tunnel` **running**, VPS listen `127.0.0.1:18095`. 데스크톱의 키를 LaunchAgent가 읽지 못해 전용 키를 `~/.ssh/agentdash_hostinger_ed25519`에 설치한 후 재연결 성공. 기존 dashboard 서비스는 유지.
- 공개 HTTPS 검증: 비인증 `/` **401**, 인증 `/`·summary·twin **200**, 원격 hooks·raw **404**, 루트 POST **403**. TLS 인증서 검증 생략 없이 실행.
- SSE: `Accept: text/event-stream`, 25초 관찰에서 **200 · hello · ping** 확인. 최초 7초 검증은 실패했으며 시간 여유를 늘려 재검증 PASS. summary는 시각 필드 `at` 제외 **Mac과 완전 일치**.
- 이미지: `nginx@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5`. `docker compose config --quiet`, nginx `-t`, `git diff --check`, `check_decisions.py` PASS. 앱 코드 변경 없음.
- 비밀번호·키는 Git 제외, 로컬 `data/hostinger/access.txt` 권한 600. DB/원천 파일 복사 없음. 기존 Caddy 설정 변경 없음. Mac 중지/잠자기 시 원격 화면 사용 불가. 실제 재부팅·로그아웃·인증서 갱신은 미시험.
- 운영 안내: `deploy/hostinger/README.md`. 실행 확인 화면: `outputs/e2e/hostinger-20261021/docker-manager.png` (Git 제외).

## 화면 명칭·시스템 제목 변경 — 2026-10-21 (사용자 요청)

- 공통 상단 첫 줄 왼쪽: **멀티 에이전트 플랫폼 대시보드**. 데스크톱 32px · 390px 화면 24px, 왼쪽 여백 16px. 메뉴 위에 배치하고 좁은 화면에서 줄바꿈 허용.
- D-01 메뉴/페이지 제목/모니터링 영역/접근성 이름: **에이전트 모니터링**. 브라우저 제목도 새 시스템 이름 사용.
- 검증: `uv run pytest tests/test_design.py tests/test_twin_page.py tests/test_dashboard.py tests/test_routes.py -q` **45 passed** · `git diff --check` PASS. 1400/390 화면 가로 넘침 0 (1385/1385 · 375/375).
- 운영 반영: 승인된 `local.agentdash.dashboard` 서비스만 `launchctl kickstart -k gui/501/local.agentdash.dashboard`로 재시작. 8095 브라우저 새 제목·실시간 연결 확인, viewport 초기화, 사용자 탭 유지.
- 스크린샷: `outputs/e2e/title-20261021/{desktop,mobile}.png` (git 제외). 데이터 모델·수집·관계·배치 변경 없음.

## 운영 전환 완료 — 2026-10-21 (사용자 「승인함」, D-37)

| 항목 | 실측 | 검증 |
|---|---|---|
| 설치 | `~/Library/LaunchAgents/local.agentdash.dashboard.plist` · 준비 파일과 동일 · 문법 OK | plistlib 비교 · `plutil -lint` |
| 서비스 | `gui/501/local.agentdash.dashboard` **running** · 관리 PID 3421 · Python 3438 · runs 1 · last exit never | `launchctl print gui/501/local.agentdash.dashboard` |
| 운영 설정 | 기존 `data/agentdash.db` · 127.0.0.1:8095 · uv frozen/offline · RunAtLoad/KeepAlive true · 로그 data/ | 설치 설정/launchctl 출력/기동 로그 |
| HTTP/화면 | HTTP **200** · Chrome 기존 8095 탭 새로고침 · 「실시간: 연결됨」 · 콘솔 오류 **0** | curl · 브라우저 DOM · dev logs |
| 데이터 | 사용량 **30,404** · 추정 비용 NULL **0** · parse_error **0** · integrity **ok**. 최신 원천 시각 10:20:45Z → 점검 10:20:56Z (19:20 KST) | SQLite `mode=ro` 검사 |
| 화면 저장 | `outputs/e2e/operations-20261021/production-8095.png` (git 제외) | 브라우저 캡처 |

설치 직후 상태 확인 스크립트에서 HTTP 모듈 변수 이름 충돌이 있었지만 서비스 등록 자체는 완료됐으며, 별도 curl/launchctl/브라우저로 정상 기동을 확인했다. 실제 로그아웃/재로그인 시험은 하지 않았으며 자동 실행 등록을 확인했다. 운영 서비스와 사용자 브라우저 탭은 유지한다. 아래 설치 승인 대기는 이 완료 기록으로 대체한다.

## 운영 전환 준비 — 2026-10-21 (실제 설치·8095 기동 승인 대기)

| 항목 | 실측 | 검증 |
|---|---|---|
| 운영 DB | 기존 `data/agentdash.db` 유지. 첫 동기화 사용량 28,566→30,040 · SESSION 83 · SUBAGENT 287 · WORKFLOW_AGENT 6 · WORKFLOW 1 · parse_error 0 · integrity ok · foreign_key 위반 0 | `backfill.run(since=settings.get().backfill_since)` · SQLite 검사 |
| 보존 | 동기화 전 에이전트 344/344 · 요청 28,566/28,566 유지. G-04 보관 SESSION 8 · SUBAGENT 19, 빠짐/남음 0 | 백업/현재 DB 키 집합 독립 비교 · G-04 |
| 동기화 전 백업 | `data/agentdash.before-sync-20261021T090949059669Z.db` | SQLite backup API |
| 보관 비용 칸 | 첫 운영 DB 게이트 G-24 FAIL (NULL 계약 위반 2,694). 사본 검증 후 기존 `usage.reprice` 적용: 기록 비용/단가 버전 변경 0 · 추정 비용 칸 보완 2,694 · 남은 비용 NULL 0. 출력 추정값은 복원하지 않음 | 메모리 사본/운영 DB 전후 기록 비용 비교 · `check_usage_est.py` PASS |
| 비용 보완 전 백업 | `data/agentdash.before-reprice-20261021T092252220128Z.db` | SQLite backup API |
| 운영 DB 전체 게이트 | **PASS 35 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0**, 18:27 KST · strict exit 0. 읽기 전용 pytest **474 passed** · 원천 트리 변경 0. QA 필수 항목은 기존 보고서 포함 | `uv run python src/agentdash/tools/gate.py --strict` (기본 운영 DB) |
| 운영 명령 실기동 | `uv run --frozen --offline python -m agentdash.app` · 기본 운영 DB · 임시 8096 · PID 66692. 브라우저 「실시간: 연결됨」 · 콘솔 오류 0 | 실제 기동 · Chrome D-01 |
| 자동 실행 준비 | `data/local.agentdash.dashboard.plist` · 운영 DB 절대 경로 · 8095 · 로그인 시작/종료 시 재시작 · 로그 data/ · 실제 설치 없음 | `plistlib` 재읽기 동일 · `plutil -lint` OK |
| 운영 절차 | `docs/operations.md`: 수동 기동·중지·재시작·자동 실행 설치·검사 명령 | 문서 확인 · `git diff --check` |
| 정리 | 직접 띄운 8096 PID 66692 종료 · exit 0, 검증 탭 닫음. 8095 HTTP 연결 거부 상태를 확인했고 새로 기동하지 않음 | 실행 세션 종료 · 사전 curl exit 7 |

남은 단계는 준비된 plist의 사용자 LaunchAgent 설치와 8095 운영 기동에 대한 명시적 승인이다. `CLAUDE.md`의 에이전트 8096/8097 제한과 기존 LaunchAgent 사람 전용 지침에 따라 이 작업만 대기한다. 운영 DB와 실행 명령 검증은 완료했다.

## D-35 평면도 가독성 완료 — 2026-10-21 (사용자 「12 오케」)

| 항목 | 실측 | 검증 |
|---|---|---|
| 표시 기준 | 첫 표시/맞춤: 모든 화면의 최소 실효 글자 **12px**, 배율 1.2. 이름 14.4px · 상태/도구/누적 13.2px · 종류/접힘 12px. 수동 축소 허용, 맞춤 시 복원 | `_twin.html` · `dashboard.html` · `decisions.md` D-35 |
| 격자 | 전달 width = `floor(카드 너비 / 1.2 - 32)`, 최소 1. 서버 좌표 그대로, 카드 내부 이동 유지 | `test_grid_width_reserves_readable_scale_and_padding` |
| 회귀 | 화면 테스트 **25 passed**, 기존 관제판 포함 **37 passed**. 전체 **474 passed** (읽기 전용 가짜 루트 · 트리 변경 0 포함) | `uv run pytest tests/test_twin_page.py tests/test_dashboard.py -q` · `make gate` G-14 |
| 브라우저 | Chrome 390×844 · 1400×900, 밝은/어두운 테마. 최소 실효 글자 12px (부동소수점 오차 < 1e-9). 가로 scrollWidth/clientWidth 375/375 · 1385/1385. 앱 콘솔 오류 0 | SVG viewBox/실제 표시 크기/계산된 font-size 독립 측정 |
| 조작 | 390px 수동 축소 후 맞춤 배율 1.2 복원. 카드 휠 이동 viewBox y -16→1390.67, 페이지 scrollX/Y 0 | 브라우저 버튼·휠 직접 조작 |
| 소수점 보정 | 1400×653에서 종전 clientHeight 반올림 사용 시 11.99865px → 실제 SVG 경계 크기 사용 후 12px | 브라우저 실측 · `test_fractional_svg_height_does_not_shrink_text_below_minimum` |
| 수용 게이트 | 최종 **PASS 35 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0**, 17:48 KST. 앞선 17:43 측정은 34 PASS/1 FAIL이었고 임시 감시 서버 종료 후 재측정에서 재현되지 않음(첫 실패 원인 미확정). QA 필수 항목은 기존 보고서도 포함 | `AGENTDASH_DB=data/agentdash-review-20261021.db make gate` |
| 스크린샷 | `outputs/e2e/readability-20261021/{light,dark}-{390,1400}.png` 4장 (git 제외) | CUA 브라우저 캡처 |
| 정리 | 임시 서버 PID 57329 종료 · exit 0. 브라우저 viewport 초기화 · 생성한 검증 탭 닫음 | 실행 세션 종료 · 브라우저 정리 |

종전 D-31/D-34 배율 해석은 D-35로 대체했다. 정본·데이터 모델·서버 배치 규칙·실제 훅·예산 변경 없음. 다음 순서는 **운영 실행 DB와 서버 실행 방식 정리**다.

## D-24 보완 완료 — 2026-10-21 (사용자 설계 승인 · Codex)

| 항목 | 실측 | 검증 |
|---|---|---|
| 구현 | `make reestimate` · `collect/reestimate.py` · 메모리 재수집 → 기존 요청의 추정 두 칸만 갱신 · 자동 백업 · 일 집계와 트랜잭션 적용 | `tests/test_reestimate.py` |
| 신규 회귀 | **11 passed**: 보관 보존 · 기록값 유지 · 재실행 동일성 · 포크 소유권 · 읽기 전용 원천 · 단가 없음 · 새/불일치 요청 건너뜀 · 파싱/백업/집계 실패 · 원천 DB 경로/하드 링크 거부 | `uv run pytest tests/test_reestimate.py -q` |
| 전체 회귀 | **467 passed**, 22.03 s (기존 456 + 신규 11) | `uv run pytest -q` |
| 수용 게이트 | **PASS 35 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0**, 17:26 KST (QA 필수 항목은 기존 보고서 포함) | `AGENTDASH_DB=data/agentdash-review-20261021.db make gate` |
| 기본 DB 적용 | 기존 사용량 **28,566건 유지** · 추정값 갱신 **25,494건** · 기록 일치 25,872 · 원천 미확인 2,694 · 기록 불일치 0 · 추정 비용 NULL **28,188 → 2,694** | `make reestimate` |
| 백업 | 적용 전 SQLite 스냅샷 `data/agentdash.reestimate-20261021T082354683403Z.db` | SQLite backup API |
| 실제 DB 독립 비교 | 백업 ↔ 적용 후 기록 열 전부 동일 · 기타 9 테이블 동일 (에이전트/관계/상태/오프셋 포함) · 기록 비용 합 동일 | SQLite `mode=ro` 전체 행 비교 |
| 기본 DB 재실행 | 갱신 **0** · 백업 추가 없음 · 테이블 전체 행 동일 · 남은 추정 비용 NULL 2,694 | `reestimate.run()` + 읽기 전용 비교 |

원천 미확인 2,694건의 추정값은 복원하지 못했으며 기존 행/숫자를 보존했다. 원천에만 있는 새 요청은 이 명령에서 넣지 않는다(기본 DB 적용 시 1,270건, 원천은 계속 증가). 새 기록 수집은 기존 백필/감시기 몫이다. 예산·실제 훅·운영 서버 설정·정본 변경 없음.

다음 작업: **D-31 · D-34 평면도 가독성** 검토 후 설계 확정 → 운영 실행 DB/서버 재기동 정리. D-24의 종전 설계 확인 대기는 아래 재개 점검 당시 기록이며 위 완료 내역으로 대체한다.

## 재개 점검 — 2026-10-21 (Codex)

| 항목 | 실측 | 검증 |
|---|---|---|
| 전체 테스트 | 샌드박스: 449 PASS · 3 FAIL · 4 ERROR (로컬 bind 거부 · 감시기 미반영). 제한 밖 재실행: **456 passed**, 21.46 s | `uv run pytest -q` |
| 새 검증 DB | `data/agentdash-review-20261021.db` · 최초 백필 10.8 s · SESSION 75 · SUBAGENT 254 · WORKFLOW_AGENT 6 · WORKFLOW 1 · parse_error 0 | `uv run python -m agentdash.collect.backfill --db data/agentdash-review-20261021.db` |
| 수용 게이트 | **PASS 35 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0** (17:03 KST). QA 필수 항목은 기존 리포트 재사용; 이번 회차 브라우저 E2E 전체 재측정은 아님 | `AGENTDASH_DB=data/agentdash-review-20261021.db make gate` |
| 트윈 검증 | 15 설비 · 7 라인 · 범위 35/35 · 누적/스파크/시간/격자 불일치 0 · 겹침 0 · TEXT>300 0 · 1.7 ms | 위 명령 G-32 |
| 기존 서비스 | 8095 기존 탭에 갱신 실패 표시 · HTTP 연결 거부 (응답 000, exit 7) | `curl --max-time 3 -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8095/` |
| 임시 화면 | 검증 DB · 8096 · PID 51929 기동. 브라우저 D-01 「실시간: 연결됨」 · 라인 7 · 설비 17 · 접힘 20 · 범위 37 (감시 중 수량 변동) 확인 | `AGENTDASH_DB=data/agentdash-review-20261021.db AGENTDASH_PORT=8096 uv run python -m agentdash.app` · Chrome D-01 관찰 |
| 임시 서버 정리 | 직접 띄운 실행 세션에 Ctrl+C · exit 0. 기존 8095 서버 및 기본 DB 변경 없음 | 실행 세션 종료 결과 |
| D-24 현황 | 기본 DB usage_event 28,566 · cost_est_usd NULL 28,188. 검증 DB 27,022 · NULL 0 (측정 시각별 수량 변동). output_est NULL 자체는 비의심 요청에 정상 허용 | 각 DB SQLite `mode=ro`: `SELECT COUNT(*), SUM(output_est IS NULL), SUM(cost_est_usd IS NULL) FROM usage_event` |

### 다음 작업 순서

1. **D-24 설계 확인 대기:** 보관 데이터를 유지하면서 현재 원천을 재처리하는 `make reestimate` 추가 제안. 아직 구현·기본 DB 변경 없음. 삭제 원천 보존·중복 방지·추정 재계산·재실행 동일성 검증 필요.
2. **D-31 · D-34 가독성:** 넓은 화면의 작은 글자와 맞춤 배율을 사람과 확인한 뒤 수정 범위 결정.
3. **운영 재기동:** 기본 8095 서비스 실행 DB와 실행 방법 정리. 상시 실행 설정·실제 훅 설치는 기존 사람 전용 규칙 유지.
4. **사람 결정:** D-23 · D-25~27 · D-32~34 가설 해소, 실제 예산 금액·OS 알림 확인. 기존 정본은 변경하지 않음.

## 2차-T 최종 보고 — 2026-10-21 · 루프 종료 (`goal.md` §4.4 EXIT 3 조건 충족)

| EXIT 조건 | 실측 | 검증 |
|---|---|---|
| 1. G-01~G-35 전건 PASS | 회전 1 · 2 모두 **PASS 34 · FAIL 0 · 미검증 1** — 미검증 G-15 는 사람이 8095 에 띄운 개발 서버 때문에 「서버 꺼짐」 조건을 못 만든 것(검사기 설계대로). 서버를 끈 웨이브 D 재측정에서 **G-15 PASS** (송신 0.01 s · exit 0 · 0 B), 그 뒤 바뀐 파일은 `_twin.html` 뿐 — 훅 코드 변경 0. QA1 r4 G-15 PASS | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` · `check_hooks.py` |
| 2. QA 치명 0 · 중대 0 | QA1 r5 · r6, QA2 r5 · r6 · r7 (twin · twin-r2 · twin-r3) · self-observe r7 · r9 — 치명 0 · 중대 0 · 마지막 회차 새 결함 0 | `outputs/qa1-데이터안전-r6.md` · `outputs/e2e/twin-r3.md` · `outputs/e2e/self-observe-r9.md` |
| 3. 연속 2 회전 변화 없음 | pytest 456 동일 · 게이트 판정 35 개 동일 · 코드 변경 0 (`909ffdc` 그대로) | 회전 기록 |

### 2차-T 로 바뀐 것 (`1643cbc` 설계 → `909ffdc`)
- 정본: `spec.md` v0.4 → v0.4.1 (§5.4 디지털 트윈 배치 T-01~T-08 · 라인 이름 규칙 · §7 D-01 공장 평면도 · §7.4 애니메이션 · API 14 · V-17) · `problem.md` 2차-T (F16 · G17 · Q17~Q19) · `goal.md` 2차-T (2차-A 는 `goal-v2a.md`)
- D-01 = 공장 평면도: 프로젝트 = 생산 라인(격자), 세션 = 주 설비, 서브에이전트 = 보조 설비, spawn/handback = 배관(입자 흐름 · 역흐름), message = 컨베이어 · 상태 표시등(RUNNING 맥박 · WAITING 경광등 · STALE 알람) · 30 분 스파크 `[추정]` · 누적 · 비용 · 「+N 완료」 · 기존 관제판 항목 전부 패널로 (`test_dashboard.py` 무수정)
- 실측: 새 서브에이전트 등장 1.26 s · 훅 → 표시등 21 ms · 반환 → 역흐름 → DONE 0.23 s · 실제 DB 설비 14 · 라인 6 · 2 열 × 3 행 · 1.6 ms · 300 설비 ≤ 300 ms · 겹침 0 · 7 화면 × 390/1400 × 두 테마 가로 스크롤 0 · reduced-motion 움직임 0 · 콘솔 오류 0
- 새 라이브러리 0 (SVG · CSS · 순수 JS) · 원천 쓰기 0 · settings.json 은 사람 변경(D-29) 뒤 기준 sha1 `8a539108c7d4…` 그대로

### 사람이 할 일
1. http://127.0.0.1:8095 (지금 떠 있음, 새 코드 · `data/agentdash-v2a-verify.db`) 에서 평면도를 직접 보고 가독성 판단 — 특히 **D-31** (넓은 화면 글자 ≈ 9 px) · **D-34** (좁은 화면 상태줄 9.2 px).
2. 결정 (모두 가설로 적용 중): D-25 (범위 밖 · 다른 라인 부모 → 반입구) · D-26 (살아 있는 자손 있으면 안 접음) · D-27 (반입구 0 열 — spec 대응표 「맨 오른쪽」 과 어긋남) · D-31 · D-32 (끝난 설비 「지금 도구」 비움) · D-33 (ended_at 없는 DONE → 「끝남 · 기록 n 전」) · D-34 · 관찰 O-1 (서버 24 자 자르기에 「…」 붙일지) · 2차-A 의 D-23 · D-24.
3. 이전 회차와 같이: `config/budget.yaml` 금액 · 실제 OS 알림 확인 · (선택) `make hooks-install`.

## 2차-T — 웨이브 B · C · D (2026-10-21) — EXIT 판정 회전 1

### 지금 해야 할 것
- **EXIT 판정 회전 2** — 같은 명령으로 다시 재서 판정 35 개 · pytest 수가 같으면 최종 보고 후 정지.
- 사람 확인 대기 (게이트 영향 없음): D-23 · D-24 · D-25 · D-26 · D-27 · D-31 · D-32 · D-33 · D-34.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 웨이브 B | `62e73c6` D-01 공장 평면도 · `33d2d0a` nav 「D-01 공장 평면도」 | `git log` |
| 웨이브 C (QA r5) | QA1 9 게이트 PASS · 경미 3 (401 필터 · 402 라인 이름 · 403 테스트) · QA2 G-33~G-35 · G-12 · G-21 PASS · 경미 4 (401 경과 · 402 세로 쌓임 · 403 두 번째 역흐름 · 404 도구 넘침) | `outputs/qa1-데이터안전-r5.md` · `outputs/e2e/twin.md` |
| 사람 결정 (2026-10-21) | spec v0.4.1: 라인 이름 = 가장 짧은 project_path (D-28) · T-08 라인 격자 (D-30) · settings.json 변경은 사람 (D-29, 기준 sha1 `8a539108c7d4…`) | `decisions.md` |
| 웨이브 D | `feea67e` · `cae284e` · `fa337d3` · `c3043d9` · `1caf4e1` · `bc82a4e` · `960f76b` · `734cf60` (결함 7) · `710683f` check_twin 라인 단위 · D2 `b92a624` · `50e60ec` · `80c910d` (QA2 501~503) | `git log` |
| 재검증 | QA1 r6 5 게이트 PASS · 지난 3 해결 · 경미 1 → D-32 · QA2 r6 G-33~G-35 PASS · 지난 4 해결 · 경미 3 → D2 수정 → QA2 r7 G-33~G-35 PASS · 3 해결 · **새 결함 0** | `outputs/qa1-데이터안전-r6.md` · `outputs/e2e/twin-r2.md` · `outputs/e2e/twin-r3.md` |
| G-22 자기 관찰 | QA2 서브에이전트 RUNNING → 반환 → DONE R-08 · 평면도 이 저장소 라인 보조 설비 (r7 · r9) | `outputs/e2e/self-observe-r9.md` |
| 전체 테스트 | **456 passed** | `uv run pytest -q` |
| make gate (새 DB) | **PASS 34 · FAIL 0 · 미검증 1** — G-15 = 사람 8095 서버 켜짐(설계대로). 서버를 끈 14:4x 재측정 G-15 PASS (송신 0.01 s · exit 0 · 0 B), 이후 훅 코드 변경 0 | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` · `check_hooks.py` |
| G-32 실제 DB | 설비 14 · 라인 6 · 범위 30=30=30 · 격자 2 열 × 3 행 · 겹침 0 · 1.6 ms | `check_twin.py` |
| 원천 무접촉 | settings.json sha1 `8a539108c7d4…` (D-29 기준) 그대로 · budget.yaml 변경 0 · 사람 서버 8095 새 코드로 재시작(사람 승인) | `shasum` |

## 2차-T — 웨이브 A (개발1 Task 2 · 5, 개발2 Task 3 · 4, 2026-10-21) — 오케스트레이터 재검증

### 지금 해야 할 것
- 웨이브 B 진행 중 — 개발2 Task 6 (D-01 공장 평면도 화면). 끝나면 웨이브 C (QA1 Task 7 · QA2 Task 8).
- 사람 확인 대기: D-25 · D-26 · D-27 (트윈 배치 해석) · D-23 · D-24.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 커밋 | `5f916b1` usage.spark · `2f942e1` core/twin T-01~T-07 · `b6e3746` /api/v1/twin · `791c33c` check_twin (V-17) · `3dda2b2` D-25~D-27 | `git log` |
| 전체 테스트 | **407 passed** (2차-A 375 → +32) | `uv run pytest -q` |
| G-31 배치 규칙 | `tests/test_twin.py` 24 passed (T-01~T-07 · Review Focus 5 · 300 설비 겹침 0 · ≤ 300 ms · API 4) | `uv run pytest tests/test_twin.py -q` |
| G-32 트윈 API (새 DB) | 설비 12 · 라인 5 · 접힘 10 · 칸+접힘 22 = 응답 22 = DB 직접 22 · 누적 · 스파크 불일치 0 · 겹침 0 · TEXT>300 0 · 1.4 ms · `--since all` 설비 83 · 범위 322 · 4.5 ms | `AGENTDASH_DB=data/agentdash-v2a-verify.db uv run python src/agentdash/tools/check_twin.py` |
| G-17 | 화면 7 + API 14 = 21/21 · placeholder 0 | `check_routes` |
| 사람 개발 서버 | 8095 그대로 (2차-T 이전 코드라 `/api/v1/twin` 404 — 화면 완성 뒤 사람 확인 후 재시작) | `lsof -iTCP:8095` |

## 2차-T — Phase 0 (아키텍트 · 계획 Task 1, 2026-10-21)

### 지금 해야 할 것
- **웨이브 A** — 개발1 Task 2 `usage.spark` (공표) → Task 5 `check_twin` (Task 4 공표 뒤) / 개발2 Task 3 `core/twin.py` 배치 → Task 4 `/api/v1/twin` (placeholder 제거 · 응답 키 공표).
- G-15 송신 항목은 사람이 8095 에 띄운 개발 서버 때문에 `미검증` — 서버를 끄지 않았다. EXIT 판정 때 사람에게 물어 잠깐 끄고 잰다 (`goal.md` §0.2).

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 게이트 표 | GATES G-01..G-35 연속 35 행 · G-17 「화면 7 · API 14」 · G-31 `test_twin.py` · G-32 `check_twin` · G-33 `test_realtime.py`+QA · G-34 `test_dashboard.py`+QA · G-35 `test_twin_page.py`+QA · QA_GLOBS 에 `outputs/e2e/twin*.md` | `uv run pytest -q tests/test_gate.py` (`test_gates_cover_g01_to_g35`) |
| 트윈 라우터 자리 | `app/routers/twin.py` `GET /api/v1/twin` → `placeholders.api("개발2", lines=[], links=[], folded_lines=0)` · `main.py` `ROUTERS` 에 `twin` · **소유 개발2** (CLAUDE.md 2차-T 표) | `uv run pytest -q tests/test_routes.py` |
| 화면 · API | `check_routes` N_APIS 14 · 화면 7 + API 14 = 21 중 HTTP 200 21 (빈 DB) · placeholder 1 (`/api/v1/twin`) | `uv run python src/agentdash/tools/check_routes.py` |
| Makefile | `make check-twin` — `tools/check_twin.py` 없으면 `미구현 — 담당 개발1` · 종료코드 2 | `make check-twin; echo $?` → 2 |
| 전체 테스트 | **380 passed** (`tests/test_twin.py` 는 개발2 작업 중 · 제외해도 380) | `uv run pytest -q` |
| 판정표 | **35 행 · PASS 29 · FAIL 3 · WARN 0 · BLOCKED 0 · 미검증 3** — FAIL G-31 (test_twin.py 없음 — 개발2) · G-32 (check_twin.py 없음 — 개발1) · G-35 (test_twin_page.py 없음 — 개발2 · QA 표지 없음) / 미검증 G-15 (송신 미검증 — 8095 사용 중 · QA r4 PASS) · G-33 · G-34 (개발 테스트 PASS · QA 표지 대기). G-01~G-30 회귀: G-15 외 전부 PASS | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |
| CLAUDE.md | 2차-T 로 갱신 — 완료 기준 G-01~G-35 · 규모 API 14 · 검증 17 · 배치 규칙 7 · 게이트 35 · 2차-T 새 소유 파일 · `goal-v2a.md` 보존 · 8095 사람 서버 끄지 않음 | `grep -n "2차-T" CLAUDE.md` |

### spec v0.4 에서 센 숫자 (`goal.md` §9)

| 항목 | 값 | 명령 |
|---|---|---|
| 테이블 | 11 | `grep -cE '^CREATE TABLE' spec.md` |
| 판정 규칙 | 13 | `grep -cE '^\| R-[0-9]+[ab]? \|' spec.md` |
| 연결 규칙 | 7 | `grep -cE '^\| L-0[1-7] \|' spec.md` |
| 배치 규칙 | 7 | `grep -cE '^\| T-0[1-7] \|' spec.md` |
| 진척 규칙 | 7 | `grep -cE '^\| P-0[1-7] \|' spec.md` |
| 검증 | 17 | `grep -cE '^\| V-[0-9]{2} `' spec.md` |
| 화면 | 7 | `grep -cE '^### D-0[1-7] ' spec.md` |
| API | 14 | `grep -cE '^\| `(GET\|POST) /' spec.md` |
| 게이트 | 35 | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |

## 2차-A 최종 보고 — 2026-10-21 · 루프 종료 (`goal.md` §4.4 EXIT 3 조건 충족)

| EXIT 조건 | 실측 | 검증 |
|---|---|---|
| 1. G-01~G-30 전건 PASS | **회전 1: PASS 30 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0** · 회전 2: PASS 29 · 미검증 1 (G-15 — 사람 요청으로 띄운 개발 서버가 8095 를 써서 「서버 꺼짐」 조건을 못 만듦, 검사기 설계대로) → 서버를 10 초 끄고 `check_hooks` 재측정 **G-15 PASS** (송신 0.01 s · exit 0 · 0 B) | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` · `check_hooks.py` |
| 2. QA 리포트 · 치명 0 · 중대 0 | QA1 r4 (16 게이트) · QA2 r4 + e2e alerts · design · self-observe r5 — 치명 0 · 중대 0 · 경미 2 (DEF-QA1-301 수정 완료 · DEF-QA2-301 남음) | `outputs/qa1-데이터안전-r4.md` · `outputs/qa2-상태대조-r4.md` · `outputs/e2e/{alerts,design,self-observe-r5}.md` |
| 3. 연속 2 회전 새 실측 변화 없음 | 회전 1 · 2 pytest 375 passed 동일 · 게이트 판정 30 개 동일(G-15 는 환경 요인 · 재측정 PASS) · 그 사이 코드 변경 0 (`d180c47` 그대로) | 회전 기록 |

### 2차-A 로 바뀐 것 (커밋 `0a98dc8` 설계 → `d180c47`)
- 정본: `problem.md` 2차-A · `spec.md` v0.3 (사람 승인 2026-10-20) · 새 `goal.md` (1차 `goal-v1.md` 보존) · 계획 `docs/superpowers/plans/2026-10-20-agentdash-v2a.md`
- 결정 확정 D-07 · D-08 (공식 단가 대조 — 값 같음) · D-13 · D-14 · D-17 · D-18 · D-19 · D-22 · 화면 「가설」 표시 0
- D-17 추정 출력 · 추정 보정 비용 (의심 48.9 % · 이번 기간 기록 $3,667.78 → 추정 보정 $3,796.48 · 출력 기록 17.43M → 추정 21.62M)
- 예산 (`config/budget.yaml` — 금액 null) · 일/주/월 추세 · 캐시 적중률 · 새 화면 D-07 `/insights` · API 13 · D-01 예산 띠
- WAITING 브라우저 알림 + 탭 배지 (서버 변경 없음 · 탭당 SSE 1)
- 공통 화면 틀 (밝은 기본 · 다크 · 대비 글자 ≥ 5.6:1) · 개발자별 스타일 조각 0
- 안전: 하드 링크 DB 와 옆 파일(-wal · -shm · -journal) 거부 · `~/.claude/settings.json` sha1 `8641eb22e8f5…` 처음부터 끝까지 같음 · push 없음

### 사람이 할 일
1. **`config/budget.yaml` 에 한도 금액 입력** (전체 일 · 월, 프로젝트별) — 넣기 전에는 「한도 미설정」.
2. **D-01 「알림 켜기」 → 브라우저 권한 허용 → 실제 OS 알림 확인** (QA 는 가짜 Notification 으로만 셌다).
3. (선택) `make hooks-install` — 권한 대기(`WAITING_PERMISSION`)를 입력 대기와 구분해 알리려면.
4. 결정: **D-23** spec §10 V-12 모집단 문구(세션 안 requestId 단위로 고칠지 — QA1 지지) · **D-24** 기본 DB `data/agentdash.db` 의 옛 행 `output_est` 채우기 (① 새 DB 재백필 — 원천 삭제 보관 27 키 손실 ② `make reestimate` 신설 ③ 그대로). 지금 개발 서버는 새 DB `data/agentdash-v2a-verify.db` 로 떠 있다.

### 남은 경미 · 관찰 (EXIT 를 막지 않음)
- DEF-QA2-301 D-02 계층 보기 형제 라벨 겹침 (개발2).
- QA1 관찰: 주 추세의 첫 버킷이 `from` 이 월요일이 아니면 부분 주임을 표시하지 않음 · 음수 예산 한도 → API 500 (조용하진 않음) · `no_records` 는 spec 4 단계 밖 추가 단계.
- QA2 관찰: D-07 프로젝트 막대 색이 상태 색과 비슷함 · D-01 「기다린 시간」 머리 두 줄.
- 제안 R-2A-5: `.filters` · `.stack` 을 base.html 공통 부품으로.
- 2차-B (에이전트 제어) 는 안전 모델부터 별도 설계.

## 2차-A — 웨이브 C · D (QA1 · QA2 r4 · DEF-QA1-301 수정, 2026-10-21) — EXIT 판정 회전 1

### 지금 해야 할 것
- **EXIT 판정 회전 2** — 같은 명령으로 다시 재서 판정 30 개 · pytest 수가 같으면 최종 보고 후 루프 정지 (goal.md §4.4).
- 사람 결정 대기 (게이트 영향 없음): D-23 · D-24.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| QA1 r4 | 16 게이트 PASS (G-04~G-08 · G-13~G-16 · G-19 · G-20 · G-24~G-28) · 치명 0 · 중대 0 · 경미 1 (DEF-QA1-301) · D-23 단위 지지 (파일별 0.52 %p · 세션 안 requestId 0.00 %p) · 행 대조 26,019 | `outputs/qa1-데이터안전-r4.md` |
| DEF-QA1-301 수정 | DB 옆 파일 `-wal` · `-shm` · `-journal` 이 이미 하드 링크면 거부 — 테스트 3 (먼저 FAIL 확인) · QA1 재현 스크립트 거부 · 원천 변화 없음 · 정상 경로 허용 | `uv run pytest tests/test_settings.py -q` · `uv run python outputs/qa1/r4_hardlink.py <빈 폴더>` |
| QA2 r4 | G-09 · G-10 · G-11 · G-12 (표본 30 spec v0.3 글자 오판 0 · 전수 318 0) · G-17 · G-18 · G-21 · G-29 (첫 로드 0 · 전이 1 · 재수신 0 · 두 탭 1 · 거부 → 배지만 · 탭당 SSE 1) · G-30 (7 화면 × 밝은/다크 토글/다크 시스템 · 상태 색 ΔE ≥ 27.9) PASS · 치명 0 · 중대 0 · 경미 1 (DEF-QA2-301 D-02 계층 보기 라벨 겹침) | `outputs/qa2-상태대조-r4.md` · `outputs/e2e/{alerts,design}.md` |
| G-22 자기 관찰 | QA2 `A:a666066d…` RUNNING R-09 01:43:03Z~ (spawn 엣지, 이 폴더 프로젝트) → 반환 02:03:04Z → DONE R-08 (증분 동기화 02:03:15Z) · 파일 감시만 (hook_event 0) · QA1 `A:a19dae7c…` 도 DONE R-08 | `outputs/e2e/self-observe-r5.md` |
| 전체 테스트 | **375 passed** | `uv run pytest -q` |
| make gate (새 DB) | **PASS 30 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0** | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |
| 원천 무접촉 | `~/.claude/settings.json` sha1 `8641eb22e8f5…` · `config/budget.yaml` 변경 0 · 서버 0 | `shasum` · `git diff config/budget.yaml` |

## 2차-A — 웨이브 B (개발1 Task 12 · 개발2 Task 13 · 요청 처리, 2026-10-21) — 오케스트레이터 재검증

### 지금 해야 할 것
- **웨이브 C 기동** — QA1 Task 14 (`outputs/qa1-데이터안전-r4.md`) · QA2 Task 15 (`outputs/qa2-상태대조-r4.md` · `outputs/e2e/{alerts,design,self-observe-r4}.md`). G-29 · G-30 은 QA 표지가 있어야 PASS.
- 사람 결정 대기 (게이트 영향 없음): D-23 · D-24.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 커밋 | 개발1 `7639db1` (D-04~D-07 공통 틀 · `_dev1_style.html` 삭제 · undercount 키 삭제) · 개발2 `4728e6e` (D-03 「추정 보정 (D-17)」) · `3c95c71` (D-01~D-03 공통 틀 · `_dev2_style.html` 삭제 · SSE 탭당 1) | `git log` |
| 아키텍트 요청 처리 (오케스트레이터) | R-2A-4 · R-2B-dev2-1 `test_no_dev_style_includes` xfail 해제 · R-2B-dev2-2 base.html 세 테마 블록에 `color-scheme` · `.gitignore` 에 `outputs/e2e/**/*.{png,jpg,jpeg}` (D-07 — 하위 폴더 스크린샷) | `uv run pytest tests/test_design.py -q` (5 passed) |
| 전체 테스트 | **372 passed** (xfail 0) | `uv run pytest -q` |
| make gate (새 DB) | **PASS 28 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 2** (G-29 · G-30 QA 표지 대기) · G-14 읽기 전용 pytest 다시 전체 통과 | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |
| 대비 | 48 쌍 · 글자 최소 5.6:1 · 도형 최소 3.3:1 | `check_contrast` |
| 개발자 실측 (QA 가 다시 잴 것) | 390 px · 1400 px × 두 테마 화면 7 가로 스크롤 0 (iframe scrollWidth) · 콘솔 오류 0 · SSE 탭당 1 연결 · D-02 테마 전환 다시 그림 1 · 알림 첫 로드 0 / 전이 1 / 재전송 0 / 두 탭 1 | `progress-dev1.md` §2B2 · `progress-dev2.md` §8 |
| 남은 제안 (선택, 게이트 무관) | R-2A-5 `.filters` · `.stack` 을 base.html 공통 부품으로 (화면 4 곳 반복) | — |
| 원천 무접촉 | `~/.claude/settings.json` sha1 `8641eb22e8f5…` · `config/budget.yaml` 변경 0 · agentdash 서버 0 | `shasum` · `pgrep -fl agentdash.app` |

## 2차-A — 웨이브 A (개발1 Task 5~8 · D-22, 개발2 Task 9~11, 2026-10-21) — 오케스트레이터 재검증

### 지금 해야 할 것
- **웨이브 B 기동.** 개발1 Task 12 (D-04~D-07 공통 틀) · 개발2 Task 13 (D-01~D-03 공통 틀 + R-2A-1 D-03 「추정 보정 (D-17)」 + SSE 연결 하나로 합치기 R-2A-dev2-3). 둘 다 끝나면 아키텍트가 `test_no_dev_style_includes` xfail 해제, 개발1 이 옛 `undercount*` 키 정리.
- 사람 결정 대기 (게이트 영향 없음): **D-23** V-12 모집단 문구 · **D-24** 기본 DB `output_est` 채우기 방법.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 새 DB 백필 | `data/agentdash-v2a-verify.db` 처음부터 — usage_event 25,729 · tool_call 29,147 · file_touch 2,296 · usage_daily 352 · parse_error 0 | `AGENTDASH_DB=data/agentdash-v2a-verify.db make setup backfill` |
| 전체 테스트 | **370 passed · 1 xfailed** (Phase 0 308 → +62) | `uv run pytest -q` |
| make gate (새 DB) | **PASS 28 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 2** (G-29 · G-30 = QA 표지 대기) | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |
| 회귀 G-04 · G-07 (D-22 확정) | 새 DB 세션 · 서브 · 워크플로 빠짐 0 · 남음 0 · 표본 10/10 · 기본 DB 는 원천 삭제 보관 세션 8 · 서브 19 를 따로 셈 | `check_counts` · `check_usage_sum` |
| G-23 결정 | 확정 7/7 · D-08 출처 · `가설 D-18`·`D18_NOTE` 0 | `uv run python src/agentdash/tools/check_decisions.py` |
| G-24 추정 열 | 의심 DB 48.9 % (12,583/25,730) = 원천 48.9 % · 차 0.00 %p · 위반 0 (모집단 = 세션 안 requestId, D-23) | `check_usage_est` |
| G-26 예산 | 칸 78 · 최대 차 $0.000000 · 단가 없음 0 · 한도 unset 2 (실제 budget.yaml 금액 0 — git diff 없음) | `check_budget` |
| G-27 추세 | 3 grain × 2 group · 묶음 237 · 불일치 0 · 기록 $3,667.78 · 추정 보정 $3,796.48 · 출력 기록 17,430,313 · 추정 21,622,553 | `check_trend` |
| G-28 캐시 적중률 | 표본 10 · 최대 차 0.000000 · 정렬 위반 0 | `check_efficiency` |
| G-17 라우트 | 화면 7 + API 13 = 20/20 · placeholder 0 (오케스트레이터가 R-2A-2 처리: insights 를 ROUTERS 로, stub 제거) | `check_routes` |
| 알림 (개발2 수동, 가짜 루트) | 첫 로드 0 · 전이 1 · 재전송 0 · 새로고침 0 · 두 탭 1 · 권한 거부 → 배지만 · 콘솔 오류 0 (Notification 은 가짜 객체로 셈 — 실제 권한 창 · OS 알림은 QA2 G-29) | `progress-dev2.md` §7 |
| 원천 무접촉 | `~/.claude/settings.json` sha1 `8641eb22e8f5…` 그대로 · `config/budget.yaml` 변경 0 | `shasum` · `git diff config/budget.yaml` |

## 2차-A — Phase 0 (아키텍트, 2026-10-21 · Task 1~4)

### 지금 해야 할 것
- **웨이브 A 기동 가능.** 개발1 Task 5 (추정 출력) → 6 → 7 (공표) → 8, 개발2 Task 9 (D-18 표시 제거 = G-23) → 10 → 11.
- **회귀 G-04 · G-07 FAIL = D-22 (가설)** — 원천에서 지워진 기록 26 키가 DB 에 보관된 채 V-01 · V-03 비교에 들어간다. 검사기는 개발1 소유 → 개발1 이 D-22 제안 ①② 반영(웨이브 A 첫 일), 사람은 Q10 해석 승인. 수집 · 숫자 결함은 아니다(남은 표본 8 세션 4 칸 일치).
- 실측 게이트(G-24 · G-26~G-28)는 새로 백필한 DB 로 잰다 — `output_est` 는 기존 DB 에 열만 있고 값은 NULL.

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| T1 스키마 v0.3 | `schema.sql` = spec v0.3 §3 블록 (usage_event · usage_daily 에 `output_est INTEGER` · `cost_est_usd REAL`) · v0.2 DB 에 `init_db` 가 열 4 덧붙임(두 번 돌려도 같음) · 기본 DB · dev0 DB 열 덧붙임 완료 | `uv run pytest tests/test_schema.py -q` (7 passed) |
| T1 하드 링크 거부 (G-25 · DEF-QA1-201) | 이미 있는 DB 파일 `st_nlink > 1` → `connect` · `init_db` 둘 다 `RuntimeError("DB 파일이 하드 링크 …")`, 새 경로 통과 | `uv run pytest tests/test_settings.py -q` (16 passed) |
| T1 G-14 회복 | 읽기 전용 pytest 1 failed(spec v0.3 스키마) → 0 · 트리 변경 0 · DB 경로 씨앗 49/49 거부 | `uv run python src/agentdash/tools/check_readonly.py` |
| T2 budget.yaml | spec §6.3 블록 그대로 — `warn_ratio 0.8` · total 두 값 `null` · `projects {}` (금액 0 개) | `uv run pytest tests/test_config.py -q` (6 passed) |
| T2 D-08 | 공식 단가 페이지(2026-10-21 WebFetch 읽기) Haiku 5.5 캐시 읽기 $0.01 (≤100K) · $0.05 (>100K) = 기존 값 → **확정**, `cache_read_estimated` 표시 제거 · 값 변경 0 → reprice 불필요 | `decisions.md` D-08 · `config/pricing.yaml` |
| T2 결정 확정 | D-07 · D-08 · D-13 · D-14 · D-17 · D-18 · D-19 `확정` (근거 spec v0.3 §3.1 · §4.2 · §6.1 · §6.2 · 2026-10-20 사람 승인), 1차 관찰 글 유지 | `uv run python src/agentdash/tools/check_decisions.py` → G-23 FAIL **정상** (`routers/agents.py:100 · 108` `D18_NOTE` 3 곳 — 개발2 Task 9) |
| T3 게이트 30 행 | GATES G-01~G-30 · G-17 「화면 7 · API 13」 · QA_GLOBS 에 `outputs/e2e/{alerts,design}*.md` · QA 필수 게이트(`("qa","")`)는 개발 PASS 여도 QA 표지 없으면 미검증 (G-29 · G-30 의 E2E 를 건너뛰지 않게) | `uv run pytest tests/test_gate.py -q` (26 passed) · `make gate` |
| T3 라우트 | spec 화면 7 (D-01~D-07) · API 13 → 20/20 HTTP 200 (빈 DB) · **placeholder 4** (`/insights` · `/api/v1/{budget,trend,efficiency}` — Task 8 이 없앤다) | `uv run python src/agentdash/tools/check_routes.py` |
| T3 문서 | CLAUDE.md 2차-A (완료 기준 · G-01~G-30 · 규모 화면 7 · API 13 · 검증 16 · 새 소유 파일 · `goal-v1.md`) · Makefile `gate` 주석 G-30 · `run` 주석 정정 · `check-decisions` · `check-contrast` | `make -n check-decisions check-contrast` |
| T4 화면 틀 | base.html 토큰 3 블록(밝은 `:root` · `:root[data-theme="dark"]` · 시스템 다크 `@media … :root:not([data-theme="light"])`, 두 다크 값 같음) · 대비 48 쌍 최소 글자 5.6:1 · 도형 3.3:1 | `uv run python src/agentdash/tools/check_contrast.py` · `uv run pytest tests/test_design.py -q` (4 passed · 1 xfailed = `test_no_dev_style_includes`, 웨이브 B) |
| 전체 테스트 | **308 passed · 1 xfailed** (1차 296 → +12, 실패 0) | `uv run pytest -q` |
| 원천 무접촉 | `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22e8f5…` (1차와 같음) · 훅 설치 0 | `stat -f %m ~/.claude/settings.json` · `shasum` |

### `make gate` 판정표 요약 (2026-10-21, 기본 DB `data/agentdash.db`)

**합계 PASS 21 · FAIL 8 · WARN 0 · BLOCKED 0 · 미검증 1**

| 판정 | 게이트 | 실측 한 줄 |
|---|---|---|
| PASS | G-01~G-03 · G-05 · G-06 · G-08~G-22 · G-25 | 회귀 20 + G-25 (G-17 개발 20/20 · placeholder 4) |
| FAIL (회귀) | G-04 | 세션 원천 74 · DB 81 (남음 7) · 서브에이전트 233 · 252 (남음 19) — 남은 26 전부 원천 삭제 (D-22) |
| FAIL (회귀) | G-07 | 표본 10 중 `09cc91b1` · `cd6db165` 원천 합 0 vs DB 합 (원천 삭제, D-22) · 나머지 8 일치 |
| FAIL (정상 — 개발2 T9) | G-23 | 확정 7/7 · D-08 출처 있음 · src/ `D18_NOTE` 3 곳 |
| FAIL (정상 — 개발1 T5~T7) | G-24 · G-26 · G-27 · G-28 | 검사기 · 테스트 파일 없음 |
| FAIL (정상 — 개발2 T10) | G-29 | `tests/test_alerts.py` 없음 · QA 표지 없음 |
| 미검증 | G-30 | 개발 PASS (대비 48 쌍 · test_design 4 + xfail 1) · QA2 `outputs/e2e/design.md` 대기 |

### spec.md v0.3 에서 센 숫자 (`goal.md` §9 명령)

| 항목 | 값 | 명령 |
|---|---|---|
| 테이블 | 11 | `grep -cE '^CREATE TABLE' spec.md` |
| 판정 규칙 | 13 | `grep -cE '^\| R-[0-9]+[ab]? \|' spec.md` |
| 연결 규칙 | 7 | `grep -cE '^\| L-0[1-7] \|' spec.md` |
| 진척 규칙 | 7 | `grep -cE '^\| P-0[1-7] \|' spec.md` |
| 검증 | 16 | `grep -cE '^\| V-[0-9]{2} `' spec.md` |
| 화면 | 7 | `grep -cE '^### D-0[1-7] ' spec.md` |
| API | 13 | `grep -cE '^\| `(GET\|POST) /' spec.md` |
| 상태 · 훅 이벤트 | 8 · 9 | spec §4.1 표 · §9.2 표 (손으로 셈) |

### 공표 — 개발자가 쓰는 것 (아키텍트 소유 파일)

- **D-07 자리 (`main.py` · `placeholders.py`)**: `main._insights_router()` 가 `importlib.util.find_spec("agentdash.app.routers.insights")` 로 **파일이 있으면 그 모듈의 `router`**, 없으면 `placeholders.INSIGHTS_STUB` (`GET /insights` HTML placeholder · `/api/v1/budget` `{"_placeholder", cells: []}` · `/api/v1/trend` `{grain, group, series: []}` · `/api/v1/efficiency` `{group, rows: []}`) 를 `EXTRA_ROUTERS` 로 단다. 파일이 있는데 import 가 깨지면 예외 그대로(숨기지 않음). **개발1 은 Task 8 에서 `routers/insights.py` (`router = APIRouter()`, 위 네 경로)만 만들면 바로 바뀐다** — main.py 수정 요청 불필요. 끝나면 아키텍트가 stub 과 분기를 지우고 `insights` 를 `ROUTERS` 로 옮긴다 (progress-dev1 §3 에 「T8 끝」 한 줄).
- **CSS 토큰 (base.html, 두 테마 자동)**: `--bg --surface --fg --muted --line --accent` · 상태 8 `--st-running --st-waiting-input --st-waiting-permission --st-sleeping --st-waiting-child --st-done --st-failed --st-stale` (도형 · 테두리 · 막대) + 각 `-fg` (글자) · 간격 `--sp-1`(4) … `--sp-6`(32) · `--radius --radius-sm --font --font-mono --shadow`. 1차 이름 별칭(웨이브 B 끝까지): `--warn --card --soft --st-RUNNING … --st-STALE --st-UNKNOWN --st-NONE`.
- **공통 클래스**: `.card` · `.grid` (자동 열, `<g class="grid">` 에는 안 걸림) · `.kpi` (`.k` 이름 · `.n` 숫자) · `.tbl` (표 감싸개 — 칸 안 가로 밀기, `td.num`) · `.badge` · `.st-<STATE>` (`--c` · `--c-fg` 를 그 상태 색으로 — 예 `<span class="badge st-RUNNING">`) · `.chart` (차트 감싸개). 머리글: `#theme-btn` (localStorage `agentdash-theme`) · **`#alerts-btn`** (지금 `disabled` 「알림 켜기」 — 개발2 `_alerts.html` 이 켠다) · nav 에 `/insights` 「D-07 비용 · 효율」 · `</body>` 앞 `{% include "_alerts.html" ignore missing %}`.
- **웨이브 B**: `_dev1_style.html` · `_dev2_style.html` include 를 걷어 내면 `tests/test_design.py::test_no_dev_style_includes` 가 XPASS(strict) 로 깨진다 → progress-devN §3 로 요청하면 아키텍트가 xfail 을 뗀다.

커밋: `27d2f86` T1 → `18af221` T2 → `97cd253` T3 → `d08a3de` T4 → `ca0fa7c` gate QA 필수 · D-22 (로컬만).

---

## 최종 보고 — 2026-10-17 21:58 · 루프 종료 (`goal.md` §4.4 EXIT 3 조건 충족)

| EXIT 조건 | 실측 | 검증 |
|---|---|---|
| 1. G-01~G-22 전건 PASS | **PASS 22 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0** (회전 17 · 18 · 19 세 번 같음) | `make gate` |
| 2. QA 리포트 2 종 · 치명 0 · 중대 0 | QA1 r3 · QA2 r3 치명 0 · 중대 0 (남은 경미 2) | `outputs/qa1-데이터안전-r3.md` · `outputs/qa2-상태대조-r3.md` · `outputs/e2e/self-observe-r3.md` |
| 3. 연속 2 회전 새 실측 변화 없음 | 회전 18 · 19 게이트별 판정 22 개 동일 · pytest 296 passed 동일 · 코드 변경 0 | 회전 기록 표 |

### 게이트 판정표 (회전 19, 기본 DB)

| 묶음 | 게이트 | 판정 |
|---|---|---|
| 수집 · 모델 | G-01 골격 · G-02 파서 · G-03 증분 · G-04 전체 수집 · G-05 오류율 · G-06 연결 · G-07 토큰 합 · G-08 비용 | 전부 PASS |
| 상태 · 관계 | G-09 판정 규칙 13 · G-10 연결 규칙 7 · G-11 실시간 · G-12 상태 대조 (r3 표본 30 가설 기준 오판 0) | 전부 PASS |
| 안전 | G-13 본문 미저장 · G-14 원천 무접촉 (inode 기준 · 49/49 거부) · G-15 훅 설치 안전 · G-16 로컬 전용 | 전부 PASS |
| 화면 · 진척 | G-17 화면 6 · API 10 · G-18 구성도 · G-19 진척 (88 칸) · G-20 비용 화면 | 전부 PASS |
| E2E | G-21 브라우저 (콘솔 앱 오류 0 · 390px) · G-22 자기 관찰 (반환 → DONE ≤ 1 s) | 전부 PASS |

커밋: `faac37c` Phase 0 → `de84747` A → `10cbd18` B → `7c45503` D → `8606bc8` D2 → `4b42f08` D3 → `e141412` C3 (로컬만, push 없음). 실제 `~/.claude/settings.json` sha1 `8641eb22e8f5…` 처음부터 끝까지 같음.

### 사람이 정해야 할 것 (decisions.md)

| D | 내용 | 지금 적용 중인 것 |
|---|---|---|
| D-07 | `.gitignore` 범위 (`outputs/e2e/` 스크린샷에 경로 노출) | `data/` 제외 |
| D-08 | Haiku 5.5 캐시 읽기 단가 | 입력의 0.1 배 `[추정]` (기록에 Haiku 사용 0 건 — 지금 숫자 영향 없음) |
| D-13 | 세션 이름 2 순위를 첫 사용자 메시지(본문) 대신 `agent-name` 줄로 (spec §3.1 과 다름) | `agent-name` |
| **D-17 (차단)** | 서브에이전트 · 워크플로 기록의 출력 토큰이 스트리밍 시작값 — 요청 68.6 %, 하한 ≈ 4.1M 과소. ① 표기만 ② 길이 기반 `[추정]` 열 ③ 다른 원천 | ① 「기록상 과소 (D-17)」 표기 (D-03 · D-04 · API · CSV) |
| D-18 | S1 `busy` + 미래 `ScheduleWakeup` → `SLEEPING` (spec R-03 은 `idle` 만 명시) | 가설 채택 · 화면에 「가설 D-18」 표시 |
| D-19 | S1 있음 + pid 소멸 → S1 없음으로 판정 (R-06/R-07) | 가설 채택 |

### 남은 경미 결함 (EXIT 를 막지 않음)

- **DEF-QA1-201** — 사람이 `data/` 에 원천 파일의 하드 링크를 미리 만들어 두면 거부하지 못한다(가짜 루트에서 재현). 대응안: DB 파일이 이미 있으면 `st_nlink > 1` 일 때 거부.
- **DEF-QA2-201** — D-02 노드 패널 · D-03 머리 배지에 「가설 D-18」 표시가 없다(D-01 카드 · D-03 판정 칸에는 있다).
- (오케스트레이터 관찰) `Makefile` 의 `run` 주석이 아직 "화면 placeholder 만" — 문구만 낡음.

### 사람이 할 일

1. **훅 설치 (선택이지만 권장 — 권한 대기 구분 · 1 초 반영)**: `make hooks-install HOOK_SETTINGS=~/.claude/settings.json` → 보여 주는 diff 확인 → `y`. 기존 `PreToolUse` · `PostToolUse` · `Stop` 훅은 그대로 두고 9 개를 덧붙인다. 되돌리기는 `make hooks-uninstall HOOK_SETTINGS=~/.claude/settings.json`.
2. 설치 후 **`make hooks-check HOOK_SETTINGS=~/.claude/settings.json`** — 설치 여부 · 최근 수신 시각 · 이벤트별 건수.
3. 설치 후 실측(지금 `미검증` 인 범위 밖 항목, `goal.md` §2.6): 아무 세션에서 권한 승인 요청을 띄워 D-01 "내 차례" 맨 위에 `WAITING_PERMISSION` 이 1 초 안에 뜨는지 확인. D-05 훅 페이로드 필드도 이때 `decisions.md` 에 확정.
4. **쓰기**: `make run` → http://127.0.0.1:8095 (빈 DB 면 기동 때 백필). 상시 실행은 macOS LaunchAgent (`~/Library/LaunchAgents/` 에 `uv run python -m agentdash.app` 를 이 폴더에서 실행하는 plist) — 사람이 만든다.
5. 위 D-목록을 정하면 다음 `/loop goal.md` 회전이 반영한다.

## 회전 기록 (오케스트레이터)

| 회전 | 시각 | 한 일 | 직접 재검증 |
|---|---|---|---|
| 1 | 2026-10-17 15:59 | Phase 0 아키텍트 기동 | — |
| 2 | 2026-10-17 16:15 | Phase 0 보고 재검증 → 웨이브 A 개발1 · 개발2 병렬 기동 | `make gate` PASS 5 · FAIL 13 · 미검증 4 (G-01 · G-13 · G-14 · G-16 · G-17 PASS — 보고와 일치) · `uv run pytest -q` 30 passed · `git log` `faac37c` · `stat ~/.claude/settings.json` 수정 시각 2026-10-16 15:15 (변경 없음) |

| 3 | 2026-10-17 16:40 | 개발1 웨이브 A 보고 재검증 → 개발1 웨이브 B 기동 (개발2 웨이브 A 계속) | `AGENTDASH_DB=data/agentdash-dev1.db make gate`: G-02~G-08 PASS · G-06 PASS (연결 241/241 = 100%) · G-13 PASS (행 62,100 · 위반 0) · G-14 PASS (pytest 161 · 트리 변경 0) · 합계 PASS 16 · FAIL 3 · 미검증 3 ‖ `sqlite3 … agent` SESSION 77 · SUBAGENT 235 · WORKFLOW_AGENT 6 · WORKFLOW 1 · usage_event 27,010 ‖ `stat ~/.claude/settings.json` 2026-10-16 15:15 (변경 없음) ‖ 커밋은 개발2 웨이브 A 종료 후 |

| 4 | 2026-10-17 17:05 | 개발2 웨이브 A 보고 재검증 → 웨이브 A 커밋 `de84747` → 개발1 에 R3 전달 · 개발2 웨이브 B 기동(R5 포함) | dev2 테스트 4 파일 70 passed ‖ `AGENTDASH_DB=data/agentdash-dev1.db make gate`: G-06 PASS (원천 242/242 · DB 241/242 = 99.6%, 부모 미확인 1 — 방금 생긴 서브에이전트) · G-09 39 · G-10 17 · G-11 4 passed · G-15 PASS (덧붙임 9 · 송신 0.01s · stdout 0B) · 합계 PASS 16 · FAIL 3 · 미검증 3 ‖ 기본 DB `make gate` G-06 FAIL (부모 0/241, R3) · 합계 PASS 15 · FAIL 4 ‖ `stat ~/.claude/settings.json` mtime 1792131308 (변경 없음) ‖ 커밋에 DB 파일 0 |

| 5 | 2026-10-17 17:25 | 개발1 웨이브 B (+R3) 보고 재검증 · 개발2 웨이브 B 계속 | 기본 DB `make gate`: PASS 18 · FAIL 0 · 미검증 4 (G-12 · G-18 · G-21 · G-22) · G-06 243/243 (R3 해결) · G-17 placeholder 0 · G-19 칸 88/88 근거 · 표본 10/10 · G-20 7 passed ‖ `sqlite3 data/agentdash.db pipeline_cell`: DONE 53 · NEEDS_DECISION 2 · UNKNOWN 33 · 고려솔더 01 DONE v1.0 `20261016-151506-all` · 02 DONE v1.0 `20261016-154028-all` · 05 · 08 UNKNOWN ‖ settings.json mtime 1792131308 (변경 없음) ‖ 미처리: R4(선택, 개발1 미처리) · D-15 · D-16 가설 |

| 6 | 2026-10-17 17:50 | 개발2 웨이브 B 보고 재검증 → 웨이브 B 커밋 `10cbd18` → 웨이브 C QA1 · QA2 병렬 기동 | `uv run pytest -q` 198 passed ‖ 기본 DB `make gate` PASS 18 · FAIL 0 · 미검증 4 · G-13 행 62,010 위반 0 · G-14 트리 변경 0 · G-17 16/16 placeholder 0 · G-18 test_graph 6 passed (QA 대기) ‖ 실제 settings.json mtime 1792131308 · hooks 키 PostToolUse · PreToolUse · Stop (3, 그대로) ‖ 포트 8095~8097 LISTEN 0 ‖ 커밋에 DB 파일 0 |

| 7 | 2026-10-17 18:15 | QA1 리포트 확인 → 웨이브 D 수정 2 기동 (개발1+아키텍트: DEF-QA1-001 · 002 · 003 · 006 · 008 / 개발2: DEF-QA1-004 · 005 · 007) · QA2 계속 | `outputs/qa1-데이터안전.md` 결함 8 (치명 0 · 중대 5 · 경미 3) · G-07 · G-14 · G-15 QA 판정 FAIL ‖ 실제 settings.json mtime 1792131308 (변경 없음) ‖ `find ~/.claude ~/Desktop/AI\ Coding -maxdepth 4 -name '*agentdash*'` 이 폴더 밖 0 |

| 8 | 2026-10-17 18:35 | QA2 리포트 확인 → 웨이브 D 상태 수정(개발2: DEF-QA2-001~007) 기동 · DEF-QA2-008(gate.py) 은 G-14/G-15 수정 끝난 뒤 | `outputs/qa2-상태대조.md`: G-12 FAIL (30 중 오판 3, 전수 불일치 14) · G-09~G-11 · G-17 · G-18 · G-21 · G-22 PASS · 결함 8 (중대 3 · 경미 5) ‖ 자기 관찰: QA1 handback 08:29:23Z → 같은 초 DONE R-08 (`outputs/e2e/self-observe.md`) ‖ settings.json mtime 1792131308 |

| 9 | 2026-10-17 18:45 | 개발2 훅 수정(DEF-QA1-004 · 005 · 007) 보고 재검증 · 나머지 수정 2 계속 | `tests/test_hooks_install.py` 18 passed ‖ `check_hooks.py` G-15 PASS (실제 파일 가드 5/5 거부 · 함정 0 · 남의 같은 이름 훅 남음 1 · 덧붙임 9) ‖ 실제 settings.json sha1 `8641eb22…10a7a` · mtime 1792131308 (변경 없음) · `hook_send` 0 회 · `~/.claude` 에 agentdash 백업 파일 0 |

| 10 | 2026-10-17 18:55 | 개발2 상태 수정(DEF-QA2-001~007) 보고 재검증 · 개발1+아키텍트 수정 계속 | `tests/test_state.py` + `test_linker.py` 79 passed ‖ `sqlite3 data/agentdash-dev2.db` 상태: DONE 301 · FAILED 12 · STALE 8 · RUNNING 2 · WAITING_INPUT 2 · SLEEPING 1 (= 이 오케스트레이터, D-18) ‖ 보고: judge.py 표본 30 오판 3 → 1 · 전수 325 불일치 14 → 1 (남은 1 = D-18 해석 차이) — QA 재검증 대상 ‖ 미처리 요청: R8 · R9 (개발1) · DEF-QA2-008 (gate.py) |

| 11 | 2026-10-17 19:10 | 개발1+아키텍트 수정(DEF-QA1-001 · 002 · 003 · 006 · 008) 재검증 → 웨이브 D 커밋 `7c45503` → 웨이브 D2(DEF-QA2-008 · R8 · R9 · D-03 D-17 표기) 기동 | `uv run pytest -q` 242 passed ‖ 기본 DB `make gate` PASS 21 · FAIL 1 (G-12 — 수정 전 QA2 리포트를 읽음, 재검증 필요) · G-07 PASS (에이전트별 소유 불일치 0) · G-14 PASS (DB 경로 21 회 거부 · 생긴 항목 0) · G-15 PASS ‖ 직접 재현: 가짜 루트 아래 `newdir/x.db` → RuntimeError · 폴더 미생성 ‖ settings.json sha1 `8641eb22e8f5…` 그대로 |

| 12 | 2026-10-17 19:30 | 웨이브 D2 재검증 → 커밋 `8606bc8` → 웨이브 C2 (QA1 · QA2 재검증) 병렬 기동 | `uv run pytest -q` 266 passed ‖ 기본 DB `make gate` PASS 18 · FAIL 0 · 미검증 4 (G-12 · G-18 · G-21 · G-22 — 리포트 표지 없음, QA 재검증 대기) ‖ `CLAUDE.md` 「QA 리포트 형식」 표지 `<!-- gate:G-nn -->` ‖ settings.json sha1 `8641eb22e8f5…` |

| 13 | 2026-10-17 19:45 | QA1 r2 확인 → DEF-QA1-101 직접 재현 → 웨이브 D3(101 · 102 · 103) 기동 · QA2 r2 계속 | `outputs/qa1-데이터안전-r2.md`: 이전 결함 7 해결 · DEF-002 차단(D-17) · G-14 FAIL · 새 결함 중대 1 · 경미 2 ‖ 직접 재현: 가짜 루트 `Home` + DB `home/x.db` → 거부 없이 테이블 11 생성 (macOS 대소문자 무시) ‖ settings.json sha1 `8641eb22e8f5…` |

| 14 | 2026-10-17 20:15 | QA2 r2 확인 → D3 에 DEF-QA2-101 · 102 · 103 추가 전달 | `outputs/qa2-상태대조-r2.md`: 이전 결함 8 해결 · G-09~G-12 · G-17 · G-18 · G-21 · G-22 PASS · G-12 표본 30 가설 기준 오판 0 · spec 글자 기준 1 (= 오케스트레이터, D-18) · 전수 328 같은 결과 · 새 결함 경미 3 · 치명 0 · 중대 0 ‖ 자기 관찰 r2: 기동 09:01:56Z → QA1 · QA2 RUNNING 09:02:00Z · 오케스트레이터 SLEEPING 09:06:05Z · QA1 DONE 09:12:09Z (반환 +0.2 s) · 기동 후 새 에이전트 생긴 그 초에 RUNNING |

| 15 | 2026-10-17 20:40 | 웨이브 D3 재검증 → 커밋 `4b42f08` → 웨이브 C3 (QA1 · QA2 3 회차) 병렬 기동 | `uv run pytest -q` 296 passed ‖ `make gate` PASS 21 · FAIL 1 (G-14 — QA1 r2 FAIL 이 남아 있음, 개발 판정 PASS) · G-12 · G-18 · G-21 · G-22 PASS (r2 리포트 반영) ‖ 직접 재현: 가짜 루트 `Home` + DB `home/x.db` → RuntimeError · 생긴 파일 0 ‖ settings.json sha1 `8641eb22e8f5…` |

| 16 | 2026-10-17 21:00 | QA1 r3 확인 · QA2 r3 계속 | `outputs/qa1-데이터안전-r3.md`: DEF-QA1-101 · 102 · 103 해결 (가짜 루트 생성 시도 16 거부 · 실제 경로 판정 30 기대대로 · `data/` · tmp 통과) · G-04~G-08 · G-13~G-16 · G-19 · G-20 PASS · 토큰 329/329 · 비용 합 $4,527.873066 전 집계 동일 · 새 결함 경미 1 (DEF-QA1-201 사람이 `data/` 에 원천 하드 링크를 미리 만들면 못 막음) · 치명 0 · 중대 0 ‖ `make gate` PASS 21 · 미검증 1 (G-15 — QA2 서버가 8095 점유 중 송신 시험 불가, QA1 8099 로 PASS) |

| 17 | 2026-10-17 21:15 | QA2 r3 확인 → 커밋 `e141412` → **EXIT 조건 1 · 2 충족**, 조건 3(연속 2 회전 새 실측 변화 없음) 확인 회전 시작 | `make gate` **PASS 22 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 0** ‖ `uv run pytest -q` 296 passed ‖ QA r3 2 종 치명 0 · 중대 0 (남은 경미: DEF-QA1-201 · DEF-QA2-201) ‖ G-12 r3 표본 30 가설 기준 오판 0 · 글자 기준 1 (D-18) · 전수 331 ‖ 자기 관찰 r3 09:30:09Z 기동 → 09:30:12Z RUNNING → 09:38:47Z DONE ‖ settings.json sha1 `8641eb22e8f5…` · 포트 8095~8099 LISTEN 0 |

| 18 | 2026-10-17 21:37 | EXIT 확인 회전 1/2 — 작업 없음 | `make gate` PASS 22 · FAIL 0 · 미검증 0 (회전 17 과 같음 — 게이트별 판정 22 개 동일) ‖ `uv run pytest -q` 296 passed (같음) ‖ 코드 변경 0 (`git status` progress.md 만) ‖ settings.json sha1 `8641eb22e8f5…` ‖ **새 실측 변화 없음 1/2** |

| 19 | 2026-10-17 21:58 | EXIT 확인 회전 2/2 → **최종 보고 · 루프 종료** | `make gate` PASS 22 · FAIL 0 · 미검증 0 (회전 18 과 같음) ‖ `uv run pytest -q` 296 passed (같음) ‖ 코드 변경 0 ‖ settings.json sha1 `8641eb22e8f5…` ‖ **새 실측 변화 없음 2/2 → EXIT** |

**사람 확인 대기 (추가):** D-18(busy + ScheduleWakeup 예약 → SLEEPING, DEF-QA2-004 — 이 루프 자신이 그 모양) · D-19(S1 있음 + pid 소멸 → S1 없음으로 판정, DEF-QA2-005).

**사람 확인 대기 (추가):** DEF-QA1-002 → D-17 서브에이전트 출력 토큰이 기록상 과소(스트리밍 시작값, 하한 ≈ 4.1M) — 원천으로 바로잡을 수 없어 표기 방식 결정 필요.

**사람 확인 대기 (추가):** D-13 세션 이름을 첫 사용자 메시지(본문) 대신 `agent-name` 줄로 — spec §3.1 과 다름.

## 지금 해야 할 것 (회전 3 시점 기록 — 최종 보고로 대체됨)

1. **웨이브 A 개발2 진행 중 · 웨이브 B 개발1 진행 중 (회전 3)** — 안전 게이트 G-13 · G-14 · G-16 PASS, G-15 는 설치 스크립트가 없어 `미검증`(정상). 가장 앞선 FAIL 은 웨이브 A 의 G-02~G-11 · G-15.
   - 개발1 (`goal.md` §5 개발1 프롬프트): `collect/tail.py` → `collect/parsers/*` → `core/model.py` → `core/usage.py` · 비용 → `make backfill` · `pricing-check` · `reprice`. G-02 · G-03 · G-04 · G-05 · G-07 · G-08. DB `data/agentdash-dev1.db`. 먼저 볼 결정: D-01 · D-02 · D-03 · D-06 · **D-11**(`api-request-blob` 이중 계산).
   - 개발2 (`goal.md` §5 개발2 프롬프트): `core/linker.py` → `core/state.py` → `collect/hooks_rx.py` → `scripts/{hook_send.sh,hooks_install.py}` → `app/sse.py`. G-06 · G-09 · G-10 · G-11 · G-15. DB `data/agentdash-dev2.db`. 먼저 볼 결정: D-04 · D-05 · **D-09**(S1 `status: shell`) · **D-10**(워크플로 · 손자 메타).
2. 훅 설치 계약은 `CLAUDE.md` 「코드 규약」 · `src/agentdash/tools/check_hooks.py` docstring 대로 (`--settings <경로> --yes` · `--uninstall --yes`). 실제 `~/.claude/settings.json` 에는 사람만.
3. 사람 확인 대기: D-07(.gitignore 범위) · D-08(Haiku 5.5 캐시 읽기 단가).

---

## Phase 0 — 아키텍트 (2026-10-17)

### 실측

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| spec 테이블 | 11 | `grep -cE '^CREATE TABLE' spec.md` |
| spec 상태 판정 규칙 | 13 (R-01 · R-02a · R-02b · R-03~R-12) | `grep -cE '^\| R-[0-9]+[ab]? \|' spec.md` |
| spec 연결 규칙 | 7 | `grep -cE '^\| L-0[1-7] \|' spec.md` |
| spec 진척 규칙 | 7 | `grep -cE '^\| P-0[1-7] \|' spec.md` |
| spec 검증 | 11 (V-01~V-11) | `` grep -cE '^\| V-[0-9]{2} `' spec.md `` |
| spec 화면 | 6 (D-01~D-06) | `grep -cE '^### D-0[1-6] ' spec.md` |
| spec API | 10 | `` grep -cE '^\| `(GET\|POST) /' spec.md `` |
| 원천 메인 세션 (16:12) | 77 | `find ~/.claude/projects -maxdepth 2 -name '*.jsonl' \| wc -l` |
| 원천 서브에이전트 (워크플로 제외) | 233 (spec · intro 의 232 보다 +1 — 계속 늘어난다) | `find ~/.claude/projects -path '*/subagents/agent-*.jsonl' -not -path '*/workflows/*' \| wc -l` |
| 원천 워크플로 에이전트 | 6 (Standard Data Hub 세션 1 건) | `find ~/.claude/projects -path '*/subagents/workflows/*/agent-*.jsonl' \| wc -l` |
| 원천 프로젝트 폴더 | 43 | `ls ~/.claude/projects \| wc -l` |
| schema.sql 테이블 | 11 = spec §3 (글자 단위로 같은 블록) | `uv run pytest tests/test_schema.py` |
| DB | `data/agentdash.db` · `data/agentdash-dev0.db` 테이블 11 · WAL | `make setup` · `AGENTDASH_DB=data/agentdash-dev0.db make setup` |
| config | settings(stale 300 · slow 90 · 8095 · 127.0.0.1) · pricing(모델 12 + alias 1, version 2026-10-06) · companies 11 · pipeline 단계 8 | `uv run pytest tests/test_config.py tests/test_settings.py` |
| 픽스처 | 23 파일 · 2 버전(`2.1.295` 워크플로 + 깊이 1·2, `2.1.301` 이 저장소 세션 + S1 + 깊이 1). 세션 jsonl 2 개는 앞 200 줄 + 연결 줄로 자름(468→204 · 8444→206, README 에 기록) | `make fixtures` · `tests/fixtures/*/README.md` |
| 픽스처 본문 검사 | PASS — 줄 1284 · 문자열 42330 중 `<redacted>` 17576 · 위반 0 | `uv run python scripts/check_fixtures_redacted.py` |
| 픽스처 검사기 참 양성 | 본문 키 · 120 자 초과 누출을 FAIL 로 잡음 | `tests/test_fixtures.py::test_checker_catches_leak` |
| check_readonly 참 양성 | 합성 파일의 원천 쓰기 6 곳 전부 잡음 · 저장소 쓰기는 통과 · 하드코딩 경로 잡음 | `tests/test_safety_tools.py` |
| check_bind 참 양성 | `import requests` · 외부 URL · `host="0.0.0.0"` 잡음 | `tests/test_safety_tools.py::test_bind_catches_external` |
| 서버 바인드 실측 | `AGENTDASH_PORT=8096 uv run python -m agentdash.app` → `TCP 127.0.0.1:8096 (LISTEN)` · `/` 200 (확인 후 정지) | `lsof -nP -iTCP:8096 -sTCP:LISTEN` |
| pytest | 30 passed | `uv run pytest -q` |
| Makefile 미구현 타깃 | backfill · hooks-install · hooks-uninstall · hooks-check · pricing-check · reprice · export → `미구현 — 담당 개발N` · 종료코드 2 | `make backfill; echo $?` |

### `make gate` 판정표 (2026-10-17, Phase 0 끝)

```
# make gate — 2026-10-17 16:14:04 (goal.md §2)
G-01  골격 — make setup · 테이블 11             PASS  tests/test_schema.py: 5 passed in 0.03s ‖ agentdash.db 테이블 11
G-02  파서 회귀 — 픽스처 S1~S6 · S9 (V-08)        FAIL  tests/test_parsers.py 없음 — 담당 개발1
G-03  증분 읽기 — 추가분 · 반쪽 줄 · inode           FAIL  tests/test_tail.py 없음 — 담당 개발1
G-04  전체 수집 — agent 행 = 원천 파일 수 (V-01)     FAIL  src/agentdash/tools/check_counts.py 없음 — 담당 개발1
G-05  파싱 오류율 ≤ 0.1% (V-07)                 FAIL  src/agentdash/tools/check_parse_errors.py 없음 — 담당 개발1
G-06  부모 연결 ≥ 95% (V-02)                   FAIL  src/agentdash/tools/check_link_rate.py 없음 — 담당 개발2
G-07  토큰 합 — 표본 10 세션 (V-03)               FAIL  src/agentdash/tools/check_usage_sum.py 없음 — 담당 개발1
G-08  비용 — 표본 20 건 손계산 (V-09)              FAIL  src/agentdash/tools/check_cost.py 없음 — 담당 개발1 ‖ tests/test_cost.py 없음 — 담당 개발1
G-09  판정 규칙 13 — 표 기반 테스트                  FAIL  tests/test_state.py 없음 — 담당 개발2
G-10  연결 규칙 L-01~L-07 테스트                  FAIL  tests/test_linker.py 없음 — 담당 개발2
G-11  실시간 — SSE 5 초 · 훅 1 초                FAIL  tests/test_realtime.py 없음 — 담당 개발2
G-12  상태 대조 — 표본 30 오판 ≤ 2                 미검증  outputs/qa2-상태대조.md 없음 — QA 리포트 대기 (웨이브 C)
G-13  본문 미저장 — DB TEXT ≤ 300 · 픽스처 (V-04)  PASS  agentdash.db 테이블 11 · 행 0 · TEXT 값 0 · 상한 300 자 · 위반 0 (빈 DB — 백필 뒤 다시 잰다) ‖ 파일 23 · 줄 1284 · 문자열 42330 (그중 <redacted> 17576) · 위반 0
G-14  원천 무접촉 — 정적 + 읽기 전용 pytest (V-05)    PASS  파일 29 · 쓰기 호출 22 곳 · 원천 경로 대상 0 ‖ 읽기 전용 가짜 루트(파일 23) · pytest 30 passed in 0.35s · 트리 변경 0 · 0.5s
G-15  훅 설치 안전 — 가짜 settings (V-10)         미검증  scripts/hooks_install.py · scripts/hook_send.sh 없음 — 설치 스크립트 미구현 (담당 개발2, 웨이브 A)
G-16  로컬 전용 — 127.0.0.1 · 외부 전송 0 (V-06)   PASS  host 127.0.0.1:8095 · 스캔 py 29 · 기타 4 · 외부 전송/바인드 위반 0
G-17  화면 6 · API 10 — HTTP 200             PASS  화면 6 + API 10 = 16 중 HTTP 200 16 (빈 DB) · placeholder 16
G-18  구성도 — 300 노드 ≤ 300 ms · 접기 · 보기 3    FAIL  tests/test_graph.py 없음 — 담당 개발2 ‖ outputs/qa2-상태대조.md 없음 — QA 리포트 대기 (웨이브 C)
G-19  진척 판정 — P-01~P-07 · 고려솔더 (V-11)      FAIL  src/agentdash/tools/check_pipeline.py 없음 — 담당 개발1 ‖ tests/test_pipeline.py 없음 — 담당 개발1
G-20  비용 화면 — [추정] 표기 · 단가 없음 · reprice    FAIL  tests/test_usage_page.py 없음 — 담당 개발1
G-21  브라우저 — 콘솔 오류 0 · 390px               미검증  outputs/qa2-상태대조.md 없음 — QA 리포트 대기 (웨이브 C)
G-22  자기 관찰 — 루프 서브에이전트 RUNNING → DONE     미검증  outputs/e2e/self-observe.md 없음 — QA 리포트 대기 (웨이브 C)
# 합계 PASS 5 · FAIL 13 · WARN 0 · BLOCKED 0 · 미검증 4
```

기대(`goal.md` §3.1) = G-01 · G-13 · G-14 · G-16 PASS, G-17 placeholder 로 PASS, 나머지 FAIL/미검증 — **기대와 같다.** G-13 의 DB 쪽은 빈 DB(행 0)라 백필 뒤 다시 잰다.
