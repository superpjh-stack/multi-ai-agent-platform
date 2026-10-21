# /goal — 멀티 에이전트 대시보드 2차-T 디지털 트윈 (D-01 공장 평면도 · API 14 · 검증 17 · 게이트 G-01~G-35)

> **이 문서가 메타프롬프트다.** `/loop` 가 매 회전 이 문서를 판정 기준으로 읽는다. 투입되는 에이전트도 작업 전에 이 문서와 `CLAUDE.md` · `decisions.md` · `progress.md` 를 먼저 읽는다.
> 1차는 `goal-v1.md`, 2차-A 는 `goal-v2a.md` 에 보존한다. 프로토콜 · 금지 사항은 그 둘과 같고(`goal-v1.md` §4.3 · §8, `goal-v2a.md` §0.2 · §4), 다른 것만 여기 적는다.
> 수치는 `spec.md` v0.4 에서 센 값이다(§9).

| 항목 | 값 | 출처 |
|---|---|---|
| 시스템 | 2차-A 대시보드 + **D-01 을 디지털 트윈 공장 평면도로** (라인 = 프로젝트 · 설비 = 에이전트 · 배관 = spawn/handback · 컨베이어 = message · 표시등 · 스파크 · 흐름) | `problem.md` §4.2b G17 |
| 정본 | `intro.md` · `problem.md`(2차-T) · `spec.md` **v0.4** — 사람만 고친다 | — |
| 설계 · 계획 | `docs/superpowers/specs/2026-10-21-agentdash-twin-design.md` · **`docs/superpowers/plans/2026-10-21-agentdash-twin.md` (Task 1~8)** | — |
| 규모 | 화면 7 · API **14** · 테이블 11 · 판정 규칙 13 · 연결 규칙 7 · **배치 규칙 7 (T-01~T-07)** · 진척 규칙 7 · 검증 **17** · 훅 이벤트 9 | `spec.md` |
| 출발점 | `1c33a63` 2차-A 완료 (G-01~G-30 PASS · pytest 375) → `27102d3` 정본 v0.4 | `git log` |
| 범위 밖 | 3D · 평면도에서 에이전트 제어(2차-B) · 사용자 배치 저장 · 라인 KPI | `problem.md` §5 |
| 완료 기준 | **G-01~G-35 전부 PASS · QA 치명 0 · 중대 0 · 연속 2 회전 변화 없음** | §4.4 |

---

## 0. 이 문서를 어떻게 쓰는가

### 0.1 루프 기동

```
/loop goal.md 를 판정 기준으로 멀티 에이전트 대시보드 2차-T(디지털 트윈)를 만든다. §4.2 한 회전 절차를 따른다 —
progress.md·decisions.md 를 읽고(2차-T 섹션이 없으면 Phase 0 부터), `make gate` 로 G-01~G-35 를 실측하고,
FAIL 중 가장 앞선 웨이브의 항목을 골라 계획(docs/superpowers/plans/2026-10-21-agentdash-twin.md)의 해당 태스크를
§5 프롬프트로 담당 에이전트에게 맡기고(병렬 가능한 것은 한 번에), 게이트 명령을 직접 다시 돌려 확인한 뒤
실측값과 검증 명령을 progress.md 에 적고 로컬 커밋한다. ~/.claude 와 이 폴더 밖에는 쓰지 않는다.
막히면 decisions.md 에 `차단` 을 올리고 다음 항목으로. 게이트를 낮추지 않는다. §4.4 를 만족하면 최종 보고 후 정지.
```

### 0.2 2차-A 와 다른 점

- **D-01 이 바뀐다.** 기존 관제판 항목은 하나도 빼지 않고 패널로 옮긴다 — `tests/test_dashboard.py` 가 회귀 기준(G-34). 테스트를 지워서 통과시키는 것은 게이트 낮추기다.
- **배치는 서버가 결정적으로.** 좌표를 브라우저에서 다시 계산하지 않는다(T-07). 그래야 테스트 · QA 가 같은 그림을 본다.
- **새 라이브러리 0.** SVG · CSS · 순수 JS 만. CDN 추가는 G-16 결함.
- **사람이 띄운 개발 서버.** 사람이 8095 에 개발 서버를 띄워 두었을 수 있다 — 끄지 않는다. 에이전트는 8096 · 8097 만 쓰고, 자기가 띄운 PID 만 kill 한다(`pkill` 금지). G-15 송신 항목이 8095 사용 중으로 미검증이면 사람에게 물어 잠깐 끄고 잰다.
- **실측 게이트는 새로 백필한 DB** (`data/agentdash-v2a-verify.db` 또는 새 파일)로 잰다 (`goal-v2a.md` §0.2).

---

## 1. 목표

**D-01 을 열면 프로젝트별 생산 라인 위에 에이전트 설비가 배관으로 이어져 보이고, 가동 · 대기 · 멈춤이 표시등으로, 일을 넘기는 순간이 배관 흐름으로 실시간 보인다. 숫자는 2차-A 와 같다.**

1. G-01~G-30 회귀 PASS (G-17 은 API 14).
2. 배치 규칙 T-01~T-07 이 표 기반 테스트로 고정되고 합성 300 설비 겹침 0 · ≤ 300 ms (G-31 · G-32).
3. 실제 DB 에서 설비 누적 · 스파크가 `usage` 직접 합과 같다 (V-17).
4. 새 에이전트 ≤ 5 초 · 훅 상태 ≤ 1 초 · handback 역흐름 → DONE 이 브라우저에서 보인다 (G-33).
5. v0.3 관제판 항목 전부가 패널에 있고, 두 테마 · 390/1400 px · reduced-motion · 키보드가 된다 (G-34 · G-35).

---

## 2. 수용 게이트

### 2.1 회귀
`goal-v2a.md` §2 의 G-01~G-30 그대로. 바뀌는 것: G-17 화면 7 + API **14** · G-21 은 D-01 평면도 포함 · G-22 자기 관찰은 평면도에서도(이 루프가 띄운 서브에이전트가 이 저장소 라인에 보조 설비로 나타나 DONE 으로 흐려진다).

### 2.2 2차-T 게이트

| # | 게이트 | 통과 기준 | 판정 수단 · 태스크 |
|---|---|---|---|
| G-31 | 배치 규칙 | T-01~T-07 각 표 기반 테스트 ≥ 1 + Review Focus 5 (라인 간 부모 · 순환 · 뿌리 안 접힘 · 24 자 · 경과 클램프) | `test_twin.py` · T3 |
| G-32 | 트윈 API | 실제 DB: 누적 · 스파크 불일치 0 · 겹침 0 · 칸 + 접힘 = 범위 안 에이전트 · TEXT ≤ 300 · 합성 300 설비 ≤ 300 ms | `check_twin` · T3 · T5 |
| G-33 | 실시간 | 가짜 루트 새 세션 + 서브 2 → 평면도 ≤ 5 초 · 훅 상태 → 표시등 ≤ 1 초 · handback → 역흐름 + DONE (브라우저 E2E) | `test_realtime.py` + QA2 `outputs/e2e/twin.md` · T6 · T8 |
| G-34 | 관제판 흡수 | v0.3 관제판 항목 전부 · 기존 `test_dashboard.py` 무삭제 PASS · 알림 · 예산 띠 회귀 | `test_dashboard.py` + QA2 · T6 · T8 |
| G-35 | 시각 | 정적 계약(reduced-motion · 접근성 · 외부 스크립트 0 · EventSource 1) + 두 테마 · 390/1400 · reduced-motion 움직임 0 · 키보드 순회 · 콘솔 0 | `test_twin_page.py` + QA2 · T6 · T8 |

### 2.3 범위 밖
3D · 제어 · 배치 저장 · 라인 KPI · 실제 OS 알림 · 훅 실설치 측정.

---

## 3. 팀 · 웨이브

```
Phase 0  아키텍트   T1 gate G-31~G-35 · routers/twin.py 자리(→ 개발2 소유) · API 14 · CLAUDE.md
   ↓
웨이브 A  개발1 T2 usage.spark (공표) → T5 check_twin (T4 공표 뒤)  /  개발2 T3 core/twin 배치 → T4 /api/v1/twin (공표)
   ↓
웨이브 B  개발2 T6 D-01 공장 평면도 화면
   ↓
웨이브 C  QA1 T7 (qa1-데이터안전-r5) / QA2 T8 (qa2-상태대조-r5 · e2e/twin · self-observe-r6)
   ↓
웨이브 D  결함 수정 — C→D 반복
```

새 소유: 개발2 `core/twin.py` · `routers/twin.py` · `templates/_twin.html` · `tests/test_{twin,twin_page}.py` / 개발1 `tools/check_twin.py` · `tests/test_check_twin.py` (+ `core/usage.py` 의 `spark`).

---

## 4. 루프 프로토콜

`goal-v1.md` §4 · `goal-v2a.md` §4 그대로. EXIT (§4.4): ① G-01~G-35 전건 PASS ② QA r5 2 종 + e2e twin · self-observe r6 치명 0 · 중대 0 ③ 연속 2 회전 변화 없음. 최종 보고에 사람이 할 일(평면도 실제 화면 확인 · D-23 · D-24 등 남은 결정)을 적는다.

## 5. 기동 프롬프트

`goal-v1.md` §5 공통 서두 + 이 두 줄:

> 이번은 **2차-T (디지털 트윈)** 다. 정본은 `spec.md` **v0.4** (§5.4 배치 · §7 D-01 · §7.4 애니메이션), 할 일은 `docs/superpowers/plans/2026-10-21-agentdash-twin.md` 의 **Task [번호]** — Files · Interfaces · Step 을 그대로 따르고 테스트를 먼저 쓴다(TDD). G-01~G-30 회귀를 깨면 끝난 것이 아니다 — `uv run pytest -q` 전체와 `make gate` 로 확인한다.
> 사람이 8095 에 띄운 개발 서버는 끄지 않는다. 너는 8096 · 8097 만 쓰고 네가 띄운 PID 만 kill 한다(`pkill` 금지). `git add` 는 네 파일만 경로로.

## 9. 실측 방법

```bash
grep -cE '^CREATE TABLE' spec.md            # 11
grep -cE '^\| R-[0-9]+[ab]? \|' spec.md      # 13
grep -cE '^\| L-0[1-7] \|' spec.md           # 7
grep -cE '^\| T-0[1-7] \|' spec.md           # 7
grep -cE '^\| P-0[1-7] \|' spec.md           # 7
grep -cE '^\| V-[0-9]{2} `' spec.md          # 17
grep -cE '^### D-0[1-7] ' spec.md            # 7
grep -cE '^\| `(GET|POST) /' spec.md         # 14
AGENTDASH_DB=data/agentdash-v2a-verify.db make gate   # 35 행
```
