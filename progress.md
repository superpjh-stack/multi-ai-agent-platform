# progress.md — 검증된 현황의 유일한 진실

> 실측값 + 검증 명령만 적는다. 본문은 붙여 넣지 않는다(숫자 · 경로만). 상태 파일 형식은 `goal.md` §4.1.

## 회전 기록 (오케스트레이터)

| 회전 | 시각 | 한 일 | 직접 재검증 |
|---|---|---|---|
| 1 | 2026-10-17 15:59 | Phase 0 아키텍트 기동 | — |
| 2 | 2026-10-17 16:15 | Phase 0 보고 재검증 → 웨이브 A 개발1 · 개발2 병렬 기동 | `make gate` PASS 5 · FAIL 13 · 미검증 4 (G-01 · G-13 · G-14 · G-16 · G-17 PASS — 보고와 일치) · `uv run pytest -q` 30 passed · `git log` `faac37c` · `stat ~/.claude/settings.json` 수정 시각 2026-10-16 15:15 (변경 없음) |

| 3 | 2026-10-17 16:40 | 개발1 웨이브 A 보고 재검증 → 개발1 웨이브 B 기동 (개발2 웨이브 A 계속) | `AGENTDASH_DB=data/agentdash-dev1.db make gate`: G-02~G-08 PASS · G-06 PASS (연결 241/241 = 100%) · G-13 PASS (행 62,100 · 위반 0) · G-14 PASS (pytest 161 · 트리 변경 0) · 합계 PASS 16 · FAIL 3 · 미검증 3 ‖ `sqlite3 … agent` SESSION 77 · SUBAGENT 235 · WORKFLOW_AGENT 6 · WORKFLOW 1 · usage_event 27,010 ‖ `stat ~/.claude/settings.json` 2026-10-16 15:15 (변경 없음) ‖ 커밋은 개발2 웨이브 A 종료 후 |

| 4 | 2026-10-17 17:05 | 개발2 웨이브 A 보고 재검증 → 웨이브 A 커밋 `de84747` → 개발1 에 R3 전달 · 개발2 웨이브 B 기동(R5 포함) | dev2 테스트 4 파일 70 passed ‖ `AGENTDASH_DB=data/agentdash-dev1.db make gate`: G-06 PASS (원천 242/242 · DB 241/242 = 99.6%, 부모 미확인 1 — 방금 생긴 서브에이전트) · G-09 39 · G-10 17 · G-11 4 passed · G-15 PASS (덧붙임 9 · 송신 0.01s · stdout 0B) · 합계 PASS 16 · FAIL 3 · 미검증 3 ‖ 기본 DB `make gate` G-06 FAIL (부모 0/241, R3) · 합계 PASS 15 · FAIL 4 ‖ `stat ~/.claude/settings.json` mtime 1792131308 (변경 없음) ‖ 커밋에 DB 파일 0 |

| 5 | 2026-10-17 17:25 | 개발1 웨이브 B (+R3) 보고 재검증 · 개발2 웨이브 B 계속 | 기본 DB `make gate`: PASS 18 · FAIL 0 · 미검증 4 (G-12 · G-18 · G-21 · G-22) · G-06 243/243 (R3 해결) · G-17 placeholder 0 · G-19 칸 88/88 근거 · 표본 10/10 · G-20 7 passed ‖ `sqlite3 data/agentdash.db pipeline_cell`: DONE 53 · NEEDS_DECISION 2 · UNKNOWN 33 · 고려솔더 01 DONE v1.0 `20261016-151506-all` · 02 DONE v1.0 `20261016-154028-all` · 05 · 08 UNKNOWN ‖ settings.json mtime 1792131308 (변경 없음) ‖ 미처리: R4(선택, 개발1 미처리) · D-15 · D-16 가설 |

**사람 확인 대기 (추가):** D-13 세션 이름을 첫 사용자 메시지(본문) 대신 `agent-name` 줄로 — spec §3.1 과 다름.

## 지금 해야 할 것

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
