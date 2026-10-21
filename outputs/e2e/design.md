# G-30 디자인 — 화면 7 × 두 테마 (QA2 r4, 2026-10-21, 커밋 8c75bd1)

> 정본: `spec.md` v0.3 §7.3 (토큰만 · 두 테마 · 머리글 토글 + `prefers-color-scheme` · 상태 색 대비 · 390 px 가로 스크롤 0). **고치지 않았다.**
> 데이터: 실제 기록을 새로 백필한 `data/agentdash-qa2.db` (agent 319), 서버 8097 (감시기 켬). 브라우저 Claude in Chrome 창 1400 × 829.
> **시스템 설정 다크 재현 방법**: 이 Mac 의 시스템 설정은 밝음(`matchMedia('(prefers-color-scheme: dark)')` false)이고 OS 설정은 바꾸지 않았다. 대신 같은 출처 iframe 에 CSS `color-scheme: dark` 를 주면 Chrome 이 그 문서의 `prefers-color-scheme` 를 dark 로 계산한다(측정: iframe 안 matchMedia true · `data-theme` 없음 · body 배경 `rgb(18,19,22)`). 시스템 다크 스크린샷은 창 전체를 덮는 그 iframe 을 찍은 것이다. 머리글 토글 모드는 실제 「테마 바꾸기」 버튼 클릭.

<!-- gate:G-30 -->
G-30  디자인 — 두 테마 스크린샷 · 390px · 콘솔 0 · 대비  PASS  r4 D-01~D-07 × (밝은 · 다크 토글 · 다크 시스템) 1400px 21 장 + 390px 밝은/다크 7 장 · iframe 56 측정 가로 스크롤 0 · 앱 콘솔 오류 0 · check_contrast 48 쌍 글자 최소 5.6 · 도형 3.3 · 상태 색 8 쌍별 최소 ΔE 27.9(밝은)/29.7(다크) · test_design 통과

## 1. 대비 · 정적 검사 (재실행)

| 항목 | 실측 | 명령 |
|---|---|---|
| 토큰 대비 | `G-30  디자인 대비  PASS  글자 최소 5.6:1 (light --st-waiting-permission-fg/--bg) · 도형 최소 3.3:1 (light --st-waiting-permission) · 쌍 48` | `uv run python src/agentdash/tools/check_contrast.py` |
| `_dev*_style` include 0 · 토큰 블록 | `tests/test_alerts.py tests/test_design.py` 18 passed (xfail 0) | `uv run pytest -q tests/test_alerts.py tests/test_design.py` |
| 상태 색 구분 (눈 + 숫자) | 8 상태 색을 실제 페이지 계산값으로 읽어 CIE Lab ΔE76 쌍별 최소: 밝은 **27.9** (권한 대기 `#d9650a` / 실패 `#d93025`) · 다크 **29.7** (입력 대기 `#e6b422` / 권한 대기 `#f08a2c`). 스크린샷에서도 D-01 상태 카드 위 테두리 · 분포 막대 · D-02 노드 · D-05 범례 8 색이 두 테마 모두 서로 구분된다 | `javascript_tool` (getComputedStyle `--st-*`) |

두 테마 상태 색 (페이지 계산값):

| 상태 | 밝은 | 다크 |
|---|---|---|
| RUNNING 초록 | `#1e8e4e` | `#34c06f` |
| WAITING_INPUT 노랑 | `#a67c00` | `#e6b422` |
| WAITING_PERMISSION 주황 | `#d9650a` | `#f08a2c` |
| SLEEPING 파랑 | `#2f6fdb` | `#4d8ef7` |
| WAITING_CHILD 하늘 | `#1a8fb8` | `#3bb6e0` |
| DONE 회색 | `#80868f` | `#8e939b` |
| FAILED 빨강 | `#d93025` | `#f2564b` |
| STALE 보라 | `#8e44ad` | `#b06ad6` |

## 2. 가로 스크롤 — 같은 출처 iframe 56 측정 (창 크기 조절 대신)

iframe 폭 390 / 1400 px (테두리 0), 모드 4 (밝은 토글 = localStorage `light` · 다크 토글 = `dark` · 시스템 밝은 = 키 없음 + `color-scheme: light` · 시스템 다크 = 키 없음 + `color-scheme: dark`), 화면 7 (`/` · `/graph` · `/agents/S:fa752590…` · `/usage` · `/timeline` · `/pipeline` · `/insights`). 각 iframe 에서 `documentElement.scrollWidth` vs `clientWidth` · `body.scrollWidth` · 「가로 스크롤 상자(overflow-x auto/scroll/hidden) 밖에서 오른쪽 끝을 넘는 요소 수」.

| 모드 | 390 px (clientWidth 375 = 390 − 세로 막대) | 1400 px (1385) | 배경 | `data-theme` / 매체 |
|---|---|---|---|---|
| 밝은 (토글) | 7/7 scrollWidth 375 · 넘는 요소 0 | 7/7 1385 · 0 | `rgb(245,246,248)` | light / L |
| 다크 (토글) | 7/7 375 · 0 | 7/7 1385 · 0 | `rgb(18,19,22)` | dark / L |
| 밝은 (시스템) | 7/7 375 · 0 | 7/7 1385 · 0 | `rgb(245,246,248)` | 없음 / L |
| 다크 (시스템) | 7/7 375 · 0 | 7/7 1385 · 0 | `rgb(18,19,22)` | 없음 / D |

**56/56 가로 스크롤 0.** 넓은 표(D-03 작업량 · D-06 회사 × 단계)는 표 상자 안에서만 가로로 민다(390 스크린샷의 D-06 표 오른쪽 잘림 = 상자 안 스크롤).

## 3. 머리글 토글 · 시스템 설정

- 토글(실제 클릭, 화면 7 각각): 밝은(시스템) → 클릭 → `data-theme=dark` · localStorage `agentdash-theme=dark` · body `rgb(18,19,22)` → 다시 클릭 → `light` · `rgb(245,246,248)`. 버튼 글자 「어둡게」 ↔ 「밝게」.
- D-02 Cytoscape: 토글마다 `__graphThemeRedraws` 0 → 1 → 2 (토큰으로 다시 칠함, 스크린샷 노드 색이 테마별 토큰).
- 시스템 다크(키 없음): 화면 7 모두 다크 토큰 · 버튼 「밝게」. 다크 블록의 `color-scheme` 덕에 D-04 · D-07 날짜 입력 · select 도 어둡게 그려짐.

## 4. 콘솔

D-01~D-07 를 차례로 열고(밝은 · 다크 토글 · 시스템 다크 iframe 포함) `read_console_messages onlyErrors` → **0**. 전체 메시지 1 건 = cytoscape 3.30.2 의 「custom wheel sensitivity」 경고(라이브러리 안내, 앱 오류 아님).

## 5. 스크린샷 (`outputs/e2e/qa2-r4/`, 커밋 안 됨 — .gitignore D-07)

| 화면 | 밝은 (시스템) 1400 | 다크 (머리글 토글) 1400 | 다크 (시스템) 1400 | 390 밝은 · 다크 (시스템, 나란히) |
|---|---|---|---|---|
| D-01 관제판 | `d01-light-system-1400.jpg` | `d01-dark-toggle-1400.jpg` | `d01-dark-system-1400.jpg` | `d01-390-light-dark-system.jpg` |
| D-02 구성도 | `d02-light-system-1400.jpg` | `d02-dark-toggle-1400.jpg` | `d02-dark-system-1400.jpg` | `d02-390-light-dark-system.jpg` |
| D-03 상세 (오케스트레이터) | `d03-light-system-1400.jpg` | `d03-dark-toggle-1400.jpg` | `d03-dark-system-1400.jpg` | `d03-390-light-dark-system.jpg` |
| D-04 작업량 | `d04-light-system-1400.jpg` | `d04-dark-toggle-1400.jpg` | `d04-dark-system-1400.jpg` | `d04-390-light-dark-system.jpg` |
| D-05 타임라인 | `d05-light-system-1400.jpg` | `d05-dark-toggle-1400.jpg` | `d05-dark-system-1400.jpg` | `d05-390-light-dark-system.jpg` |
| D-06 파이프라인 | `d06-light-system-1400.jpg` | `d06-dark-toggle-1400.jpg` | `d06-dark-system-1400.jpg` | `d06-390-light-dark-system.jpg` |
| D-07 비용 · 효율 | `d07-light-system-1400.jpg` | `d07-dark-toggle-1400.jpg` | `d07-dark-system-1400.jpg` | `d07-390-light-dark-system.jpg` |

밝은(토글) 은 시스템 밝은과 같은 토큰이라 iframe 측정(§2)만 했다. 스크린샷에는 숫자 · 이름 · 경로만 보인다(본문 없음).

## 6. 관찰 (결함 아님 · 게이트 무관)

- D-02 390 px: 필터 카드가 길어 구성도 상자가 첫 화면 아래(top 595 px)에서 시작 — 노드는 상자 안(렌더 경계 y 238~357)에 다 그려짐. 의도대로.
- D-07 프로젝트별 쌓은 막대가 초록 · 빨강 · 주황 · 보라 등 상태 색과 비슷한 계열을 쓴다 — 상태 색으로 오해할 여지(범례 있음). 원하면 프로젝트 팔레트를 상태 색과 다른 계열로.
- D-01 「내 차례」 표 머리 「기다린 시간」 이 1400 px 에서도 두 줄로 접힌다(가독성 영향 작음).
- D-02 계층 보기 형제 노드 이름표 겹침 → **DEF-QA2-301 (경미)**, `outputs/qa2-상태대조-r4.md` §4.
