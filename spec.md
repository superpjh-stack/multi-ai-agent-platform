# 기능 명세 — 멀티 에이전트 대시보드

> 관련 문서: `intro.md`(소개 · 근거 숫자 · 경계), `problem.md`(문제 · 목표 G1~G10 · 확정 필요 사항 Q1~Q10)
> 근거: 이 컴퓨터의 `~/.claude/` 기록 (2026-08-01 ~ 2026-10-17, Claude Code 2.1.x)
> 버전: **v0.4** (2026-10-21 사람 승인, 2차-T — 디지털 트윈: D-01 을 공장 평면도로 · 트윈 배치 규칙 T-01~T-07 · 애니메이션 규칙 · API 14 · V-17)
> 이전: v0.3 (2026-10-20 사람 승인, 2차-A — 결정 D-07 · D-08 · D-13 · D-14 · D-17 · D-18 · D-19 확정 반영 · 추정 출력 열 · 예산 · 추세 · 캐시 적중률 · WAITING 알림 · 디자인 · 화면 D-07 · API 13)
> 이전: v0.2 (2026-10-17, Q1 훅 연동 · Q2 멈춤 5 분 · Q4 비용 단가표 · Q5 진척 규칙 확정 반영)
> 설계: `docs/superpowers/specs/2026-10-21-agentdash-twin-design.md` (v0.4) · `docs/superpowers/specs/2026-10-20-agentdash-v2a-design.md` (v0.3)

**v0.4 에서 바뀐 곳** — §1.1 · §5.4(신설) · §7 D-01 · §7.3 · §7.4(신설) · §8 · §10(V-17) · §11 · §12(M8) · §13(2 · 15~17). 그 밖은 v0.3 과 글자까지 같다.

**v0.3 에서 바뀐 곳** — §1.1 · §1.2 · §2.3 · §3(`usage_event` · `usage_daily` 열) · §3.1 · §4.2(R-02b · R-03 · R-04 · R-06 · R-07 · 평가 순서) · §6 · §6.1(D-08) · §6.2 · §6.3 · §7(D-01 · D-04 · D-07 · §7.2 · §7.3 — §7.1 번호 유지) · §8 · §10(V-05 · V-12~V-16) · §11 · §12(M7) · §13(10~14). 그 밖은 v0.2 와 글자까지 같다.

**표기 규칙**
- `[실측]`: 2026-10-17 에 이 컴퓨터 기록에서 직접 확인한 형식 · 값. 그대로 따른다.
- `[가설]`: 구현하며 확인할 규칙. 확인되면 `decisions.md` 에 남기고 `[실측]` 으로 바꾼다.
- **대시보드는 `~/.claude/` 에 쓰지 않는다.** 저장하는 것은 메타데이터와 숫자뿐이고 대화 본문은 저장하지 않는다(G10).

---

## 1. 시스템 구성

### 1.1 계층

```
┌──────────────────────────── 화면 7 · 읽기 API · SSE ─────────────────────────────┐
│ D-01 공장 평면도 · D-02 네트워크 구성도 · D-03 에이전트 상세 · D-04 작업량 · D-05 타임라인 │
│ D-06 파이프라인 · D-07 비용 · 효율                                                │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ Jinja2 서버 렌더 + static/*.js · /api/v1/* · /api/v1/stream
┌──────────────────────────────────────▼─────────────────────────────────────────┐
│ src/agentdash/app/      main · settings · routers/* · sse                         │
│ src/agentdash/collect/  watcher(파일 감시) · tail(증분 읽기) · parsers/* · hooks_rx  │
│ src/agentdash/core/     model · linker(부모 연결) · state(상태 판정) · usage(집계)   │
│                         graph(구성도 데이터) · pipeline(progress.md 읽기)            │
│                         budget(예산 · 추세 · 캐시 적중률) · twin(평면도 배치)          │
│ src/agentdash/db/       conn · schema.sql                                         │
└──────────────────────────────────────┬─────────────────────────────────────────┘
                                       │ sqlite3 (WAL)
                     ┌─────────────────▼─────────────────┐
                     │ data/agentdash.db  (SQLite)         │
                     └───────────────────────────────────┘
 원천(읽기만): ~/.claude/sessions · ~/.claude/projects · 에이전트 프로젝트 폴더 outputs/ · progress.md
 훅 원천:     Claude Code 훅 → scripts/hook_send.sh → POST http://127.0.0.1:8095/hooks/event
```

### 1.2 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 언어 · 도구 | Python 3.12 · `uv` · Makefile | 다른 저장소(Standard Data Hub · Standard MES Platform)와 같게 |
| 웹 | FastAPI · Jinja2 · SSE(`sse-starlette`) | 서버 하나로 화면 · API · 실시간 스트림 |
| 그래프 | Cytoscape.js 3.x (CDN 고정 버전) + `cose-bilkent` 배치 | 노드 수백 개 · 접기 · 계층 배치 |
| 차트 | 서버 SVG(막대 · 추이, D-03~D-05) · Chart.js 4.x (CDN 고정 버전, D-07) | D-07 의 전환 · 쌓은 막대 · 두 선 비교는 JS 차트가 낫다. CDN 은 Cytoscape 와 같은 jsdelivr |
| 화면 틀 | `base.html` 의 색 · 간격 · 글꼴 토큰 (CSS 변수), 밝은 기본 + 다크 (§7.3) | 화면 7 을 한 틀로 |
| DB | SQLite (WAL) | 단일 사용자 · 로컬. 별도 서버 불필요 |
| 파일 감시 | `watchfiles` | macOS FSEvents |
| 테스트 | pytest · `tests/fixtures/`(실제 기록에서 본문을 지운 사본) | 형식 변화 회귀 |

### 1.3 실행 모드

| 명령 | 하는 일 |
|---|---|
| `make setup` | `uv sync` · DB 생성 · `schema.sql` 적용 |
| `make backfill [SINCE=2026-08-01]` | 과거 기록 전체 읽기 (증분 오프셋 기록) |
| `make run` | 감시기 + 웹 기동 (`127.0.0.1:8095`) |
| `make hooks-install` / `make hooks-uninstall` / `make hooks-check` | 훅 이벤트 송신을 `~/.claude/settings.json` 에 **덧붙임 / 제거 / 점검** (기존 훅 유지, 백업 생성, 사용자 확인 후, §9) — 대시보드가 원천에 쓰는 유일한 예외이며 사용자가 직접 실행한다 |
| `make pricing-check` | 기록에 나온 모델 중 단가표에 없는 것을 찾아 출력 (§6.1) |
| `make gate` | 검증 도구(§10) 실행 |
| `make export [FROM=…] [TO=…]` | 작업량 표 CSV → `outputs/` |

---

## 2. 원천

### 2.1 원천 목록 `[실측]`

| 코드 | 경로 | 내용 | 쓰는 곳 |
|---|---|---|---|
| S1 | `~/.claude/sessions/<pid>.json` | `pid` · `sessionId` · `cwd` · `startedAt` · `kind`(interactive …) · `entrypoint` · `name` · `status`(`busy`/`idle`) · `updatedAt` · `statusUpdatedAt` · `version` | 살아 있는 세션 · 현재 상태 |
| S2 | `~/.claude/projects/<proj>/<sessionId>.jsonl` | 줄마다 `type`(user/assistant/…) · `uuid` · `parentUuid` · `timestamp` · `sessionId` · `cwd` · `gitBranch` · `version` · `requestId` · `message`(`model` · `content[]` · `usage`) | 메인 세션 이력 · 도구 호출 · 토큰 |
| S3 | `<proj>/<sessionId>/subagents/agent-<agentId>.jsonl` | S2 와 같은 형식, `isSidechain: true` · `agentId` | 서브에이전트 이력 |
| S4 | `<proj>/<sessionId>/subagents/agent-<agentId>.meta.json` | `agentType` · `description` · `toolUseId` · `spawnDepth` · `requestShape`(background …) · `requestNonInteractive` · `launchedWithDefaults` | 유형 · 이름 · 부모 연결 · 깊이 |
| S5 | `<proj>/<sessionId>/subagents/workflows/wf_<id>/agent-*.jsonl` · `.meta.json` | 워크플로가 띄운 에이전트 | 워크플로 에이전트 |
| S6 | `<proj>/<sessionId>/workflows/wf_<id>.json` | 워크플로 실행 기록 | 워크플로 노드 · 단계 |
| S7 | `<proj>/<sessionId>/tool-results/*.txt` | 큰 도구 결과 본문 | 읽지 않는다 (크기만) |
| S8 | `~/Desktop/AI Coding/<NN> * Agent/progress.md` | 파이프라인 진척 (사람이 쓴 기록) | D-06 |
| S9 | `~/Desktop/AI Coding/<NN> * Agent/outputs/**` | 단계 산출물 파일 · 실행 폴더(`YYYYMMDD-HHMMSS-<scope>/run.json`) | D-06 (1순위 판정) |
| H | 훅 이벤트 | `hook_event_name` · `session_id` · `transcript_path` · `cwd` + 이벤트별 필드 `[가설: 설치 후 실제 페이로드로 확정]` | 상태 확정 · 지연 단축 (§9) |

프로젝트 폴더명은 경로의 `/` · 공백 · 비ASCII 를 `-` 로 바꾼 것이다(`-Users-gerardo92-Desktop-AI-Coding-00-PM-Agent`). 원래 경로는 줄의 `cwd` 로 복원한다.

### 2.2 증분 읽기

- 파일마다 `(path, inode, size, offset, mtime)` 를 `src_file` 에 저장한다. 다음 읽기는 `offset` 부터, 마지막 줄이 개행으로 끝나지 않으면 그 줄은 다음 번에 읽는다.
- `inode` 가 바뀌거나 `size < offset` 이면 처음부터 다시 읽는다.
- 줄 파싱 실패는 `parse_error(path, line_no, reason)` 에 쌓고 넘어간다. D-01 하단에 건수를 띄운다.
- 감시기는 `~/.claude/sessions` · `~/.claude/projects` 를 재귀 감시하고, 변경 이벤트를 1 초 묶음으로 처리한다. 감시 누락에 대비해 60 초마다 mtime 스캔을 한 번 더 돈다.

### 2.3 저장하지 않는 것

- `message.content` 의 텍스트 · thinking · 도구 결과 본문.
- 도구 입력 중 `command` · `prompt` · `content` 본문. 남기는 것은 도구 이름 · `file_path` · `description` 첫 120 자뿐이다.
- 추정 출력(§6.2)을 위해 수집기는 text · 도구 입력의 **길이(글자 수)만** 재고 버린다. 길이 숫자도 DB 에 남기지 않고 `output_est` 계산에만 쓴다.
- 상세 화면의 "원본 보기"는 요청 시점에 원천 파일을 읽어 보여 주고 저장하지 않는다.

---

## 3. 정규화 모델

```sql
-- 에이전트: 세션 · 서브에이전트 · 워크플로 에이전트를 하나로
CREATE TABLE agent (
  agent_key      TEXT PRIMARY KEY,   -- 'S:<sessionId>' | 'A:<agentId>' | 'W:<wfId>'
  kind           TEXT NOT NULL,      -- SESSION | SUBAGENT | WORKFLOW_AGENT | WORKFLOW
  project_key    TEXT NOT NULL,      -- projects/ 아래 폴더명
  project_path   TEXT,               -- cwd 로 복원한 실제 경로
  session_id     TEXT NOT NULL,      -- 소속 세션 (세션 자신이면 같은 값)
  parent_key     TEXT,               -- 띄운 쪽. 못 찾으면 NULL → '부모 미확인'
  spawn_tool_use TEXT,               -- 부모의 tool_use.id (S4.toolUseId)
  depth          INTEGER NOT NULL,   -- 세션 0, 서브에이전트 S4.spawnDepth
  agent_type     TEXT,               -- general-purpose | Explore | fork | 사용자 정의 …
  name           TEXT,               -- §3.1
  request_shape  TEXT,               -- background | foreground …
  model          TEXT,               -- 가장 많이 쓴 모델
  cc_version     TEXT,
  git_branch     TEXT,
  started_at     TEXT, last_event_at TEXT, ended_at TEXT,
  state          TEXT NOT NULL,      -- §4
  state_reason   TEXT,               -- 판정 규칙 코드 (R-01 …)
  state_since    TEXT,
  pid            INTEGER             -- 살아 있는 세션만
);

CREATE TABLE edge (                  -- 에이전트 사이 관계
  src_key TEXT, dst_key TEXT,
  kind    TEXT,                      -- spawn | message | handback | workflow
  at      TEXT, count INTEGER DEFAULT 1, label TEXT,
  PRIMARY KEY (src_key, dst_key, kind)
);

CREATE TABLE usage_event (           -- assistant 메시지 한 건의 토큰 (requestId 로 중복 제거)
  agent_key TEXT, request_id TEXT, at TEXT, model TEXT,
  speed TEXT,                        -- usage.speed: standard | fast | NULL(옛 기록)
  input_tokens INTEGER, cache_read INTEGER,
  cache_write_5m INTEGER,            -- usage.cache_creation.ephemeral_5m_input_tokens
  cache_write_1h INTEGER,            -- usage.cache_creation.ephemeral_1h_input_tokens
  output_tokens INTEGER, thinking_tokens INTEGER, web_search INTEGER, web_fetch INTEGER,
  cost_usd REAL,                     -- §6.1 로 계산. 단가표에 없는 모델이면 NULL
  pricing_ver TEXT,                  -- 계산에 쓴 단가표 버전
  output_est INTEGER,                -- §6.2 하한 추정 출력 토큰. 의심 요청만, 아니면 NULL
  cost_est_usd REAL,                 -- output_est 를 출력에 쓴 §6.1 비용. 의심 아니면 cost_usd 와 같다
  PRIMARY KEY (agent_key, request_id)
);

CREATE TABLE tool_call (
  agent_key TEXT, tool_use_id TEXT PRIMARY KEY, at TEXT, tool TEXT,
  target TEXT,                       -- file_path · URL 호스트 · 하위 에이전트 description 앞 120 자
  ok INTEGER,                        -- tool_result is_error 반대. 결과 없으면 NULL
  result_at TEXT
);

CREATE TABLE file_touch (            -- Write · Edit · NotebookEdit 대상
  agent_key TEXT, path TEXT, op TEXT, at TEXT, PRIMARY KEY (agent_key, path, op)
);

CREATE TABLE usage_daily (           -- 집계 (KST 일자)
  day TEXT, agent_key TEXT, model TEXT,
  input_tokens INTEGER, cache_read INTEGER, cache_write INTEGER, output_tokens INTEGER,
  tool_calls INTEGER, files_written INTEGER, active_seconds INTEGER, cost_usd REAL,
  output_est INTEGER,                -- 그날 의심 요청의 output_est 합 (없으면 0)
  cost_est_usd REAL,                 -- cost_est_usd 합
  PRIMARY KEY (day, agent_key, model)
);

CREATE TABLE state_log (agent_key TEXT, at TEXT, state TEXT, reason TEXT);
CREATE TABLE src_file  (path TEXT PRIMARY KEY, inode INTEGER, size INTEGER, offset INTEGER, mtime REAL);
CREATE TABLE parse_error (path TEXT, line_no INTEGER, reason TEXT, at TEXT);
CREATE TABLE pipeline_cell (           -- §7.1
  company TEXT, stage TEXT,
  status  TEXT,                        -- DONE | PARTIAL | IN_PROGRESS | NEEDS_DECISION | NOT_STARTED | UNKNOWN
  rule    TEXT,                        -- 판정 규칙 코드 P-01 …
  have INTEGER, need INTEGER,          -- 갖춘 산출물 수 / 필요한 산출물 수
  version TEXT, run_id TEXT,           -- 가장 최근 산출물의 v1.x · 실행 폴더
  last_file_at TEXT, last_session TEXT,-- 마지막 산출물 시각 · 마지막으로 손댄 에이전트
  note TEXT, src TEXT, updated_at TEXT,-- src = 근거 파일 경로(:줄)
  PRIMARY KEY (company, stage)
);
CREATE TABLE hook_event (agent_key TEXT, at TEXT, event TEXT, detail TEXT);  -- detail ≤ 300 자
```

### 3.1 이름 정하기

| 종류 | 이름 (앞에서부터 있는 것) |
|---|---|
| 세션 | S1 `name` → 그 세션 기록의 마지막 `agent-name` 줄의 `agentName` → `cwd` 마지막 이름 → 프로젝트 폴더 마지막 이름. 첫 사용자 메시지는 본문이므로 읽지 않는다 (D-13) |
| 서브에이전트 | S4 `description` → `agentType` + `agentId` 앞 6 자 |
| 워크플로 | S6 의 `meta.name` → `wf_<id>` |
| 워크플로 에이전트 | 워크플로 `label` → `description` |

### 3.2 부모 연결 (linker)

| 규칙 | 내용 |
|---|---|
| L-01 | 서브에이전트의 `spawn_tool_use`(S4 `toolUseId`)와 같은 `tool_use.id` 를 가진 `Agent` 호출을 소속 세션(같은 `<sessionId>` 폴더) 기록에서 찾는다 → 그 줄을 쓴 에이전트가 부모 |
| L-02 | 소속 세션에 없으면 같은 세션 폴더의 다른 서브에이전트 기록에서 찾는다 (손자 이상, `depth ≥ 2`) |
| L-03 | 워크플로 에이전트의 부모는 워크플로 노드(`W:<wfId>`), 워크플로 노드의 부모는 `Workflow` 도구를 부른 에이전트 |
| L-04 | 부모 기록이 아직 안 읽혔으면 `parent_key = NULL` 로 두고 다음 증분 때 다시 시도한다 |
| L-05 | 끝까지 못 찾으면 프로젝트 아래 "부모 미확인" 가상 노드에 붙인다. 비율이 G5 지표 |
| L-06 | `SendMessage` 호출의 `to` 를 S1 `name` 또는 에이전트 이름과 맞춰 `message` 엣지를 만든다. 못 맞추면 `label` 에 원래 이름을 두고 "외부" 노드로 |
| L-07 | `SubagentHandback` · 자식 `tool_result` 가 부모 기록에 돌아오면 `handback` 엣지와 자식 `ended_at` 을 기록한다 `[가설: handback 이 자식 종료와 1:1 인지 확인]` |

---

## 4. 상태 판정

### 4.1 상태 코드

| 상태 | 뜻 | 색 | 사람 행동 필요 |
|---|---|---|---|
| `RUNNING` | 모델이 생각 중이거나 도구가 실행 중 | 초록 | — |
| `WAITING_INPUT` | 내 다음 입력을 기다림 (대화형 세션 idle) | 노랑 | ✔ |
| `WAITING_PERMISSION` | 도구 권한 승인을 기다림 | 주황 | ✔ |
| `SLEEPING` | `ScheduleWakeup` · 루프로 예약된 시각까지 잠듦 | 파랑 | — |
| `WAITING_CHILD` | 백그라운드 자식 · 워크플로 결과를 기다림 | 하늘 | — |
| `DONE` | 정상 종료 (결과 반환 · 세션 종료) | 회색 | — |
| `FAILED` | 오류로 끝남 (마지막 도구 결과 오류 후 종료, 훅 실패 보고) | 빨강 | 확인 |
| `STALE` | 끝 표시 없이 기록이 끊김 (멈춤 의심) | 보라 | 확인 |

### 4.2 판정 규칙 (위에서부터 먼저 걸리는 것)

기준 시간 `STALE_AFTER = 5 분` (Q2 확정, `config/settings.yaml` 의 `stale_after_sec: 300`). 응답 느림 경계 `SLOW_AFTER = 90 초`.

**세션 평가 순서** (v0.3): R-01 → R-02a → (훅 도구 실행 중이면 `RUNNING`) → R-03 → R-04 → R-02b → R-05 → R-06 → R-07. S1 `busy` 는 턴이 끝난 뒤에도 남으므로(D-14) R-03 · R-04 를 R-02b 보다 먼저 본다. 아래 표는 코드 번호 순이다.

- **S1 살아 있음** = S1 파일 있음 · pid 살아 있음. **S1 없음** = S1 파일 없음 **또는 pid 소멸** (D-19).
- **잠잠한 busy** = S1 살아 있음 · `status = busy` · 5 분 넘게 기록 없음 · 훅으로 도구 실행 중이 아님.
- "마지막 assistant" 는 마지막 `tool_use` 로 본다 — 예약 뒤 인사 텍스트 줄은 활동이 아니다 (D-18).

| 코드 | 대상 | 조건 | 상태 |
|---|---|---|---|
| R-01 | 모두 | 훅 이벤트가 최근 상태를 알려 줌 (§9.2 표) — 단, 그 뒤에 더 새로운 기록이 있으면 기록이 이긴다 | 이벤트대로 |
| R-02a | 세션 | S1 살아 있음 · `status = busy` · 마지막 기록 < 5 분 | `RUNNING` |
| R-02b | 세션 | 잠잠한 busy 이고 R-03 · R-04 에 안 걸림 | `STALE` (훅으로 도구 실행 중 — PreToolUse 후 PostToolUse 없음 — 이면 `RUNNING` 유지, 상세에 "도구 실행 N 분째") |
| R-03 | 세션 | S1 살아 있음 · (`status = idle` 또는 잠잠한 busy) · 마지막 assistant 가 `ScheduleWakeup` 을 호출하고 예약 시각이 미래 (D-18) | `SLEEPING` (깰 시각 표시) |
| R-04 | 세션 | S1 살아 있음 · (`status = idle` 또는 잠잠한 busy) · 아직 안 끝난 백그라운드 자식(`RUNNING` · `WAITING_*`, `STALE` 제외) ≥ 1 (D-14) | `WAITING_CHILD` |
| R-05 | 세션 | S1 살아 있음 · `status = idle` | `WAITING_INPUT` |
| R-06 | 세션 | S1 없음(파일 없음 또는 pid 소멸, D-19) · 마지막 항목이 결과 없는 `tool_use` | `STALE` |
| R-07 | 세션 | S1 없음(파일 없음 또는 pid 소멸, D-19) | `DONE` |
| R-08 | 서브에이전트 | 부모 기록에 결과 반환 있음 (L-07) | `DONE` (결과 `is_error` 면 `FAILED`) |
| R-09 | 서브에이전트 | 최근 기록 < 90 초 | `RUNNING` |
| R-10 | 서브에이전트 | 자기 자식 중 미종료 있음 | `WAITING_CHILD` |
| R-11 | 서브에이전트 | 소속 세션 프로세스가 사라졌거나, 무기록 ≥ 5 분 (훅으로 도구 실행 중인 경우 제외) | `STALE` |
| R-12 | 서브에이전트 | 그 밖 (90 초 ~ 5 분 무기록) | `RUNNING` (회색 테두리 "응답 느림") |

- `STALE` 은 끝난 상태가 아니다. 그 뒤 새 기록이 들어오면 즉시 `RUNNING` 으로 돌아가고 `state_log` 에 "회복" 으로 남는다.

- 판정은 이벤트가 올 때마다, 그리고 10 초마다 살아 있는 에이전트 전부에 대해 돈다.
- 상태가 바뀌면 `state_log` 에 남기고 SSE 로 `agent.state` 이벤트를 보낸다.
- 상세 화면은 걸린 규칙 코드와 근거 값(마지막 기록 시각 · S1 status · 예약 시각)을 함께 보여 준다.

---

## 5. 네트워크 구성도

### 5.1 노드

| 노드 | 모양 | 크기 | 라벨 |
|---|---|---|---|
| 프로젝트 | 둥근 사각형 (묶음 · 접기 가능) | 고정 | 폴더 마지막 이름 |
| 세션 | 원 · 굵은 테두리 | 출력 토큰 √ 비례 | 이름 · 상태 |
| 서브에이전트 | 원 | 출력 토큰 √ 비례 | `agentType` 아이콘 + description 앞 24 자 |
| 워크플로 | 육각형 (묶음) | 고정 | 워크플로 이름 · 에이전트 수 |
| 부모 미확인 · 외부 | 점선 원 | 고정 | — |

색은 §4.1 상태 색. `RUNNING` 은 테두리가 맥박처럼 깜박인다. 사람 행동이 필요한 노드는 배지(!)를 단다.

### 5.2 엣지

| 엣지 | 선 | 방향 |
|---|---|---|
| `spawn` | 실선 | 부모 → 자식 |
| `message` | 점선 · 굵기 = 횟수 | 보낸 쪽 → 받은 쪽 |
| `handback` | 가는 실선 (기본 숨김) | 자식 → 부모 |
| `workflow` | 실선 | 워크플로 → 에이전트 |

### 5.3 보기

| 보기 | 배치 | 용도 |
|---|---|---|
| 계층 보기 (기본) | 위 → 아래 트리 (`breadthfirst`), 프로젝트 묶음 | 누가 누구를 띄웠나 |
| 협업 보기 | 힘 배치 (`cose-bilkent`), `message` 엣지 강조 | 세션 간 일 넘기기 |
| 파이프라인 보기 | 에이전트 프로젝트 `00` → `08` 을 왼 → 오른 열로 고정 | 단계 흐름 |

필터: 기간(기본 최근 24 시간 + 살아 있는 것) · 프로젝트 · 상태 · 유형 · 최소 토큰. 노드가 300 개를 넘으면 `DONE` 서브에이전트를 부모 안으로 접고 "+N" 으로 표시한다(G6).

### 5.4 디지털 트윈 — 공장 평면도 배치 (v0.4)

D-01 은 에이전트를 공장 설비처럼 보여 준다. 같은 데이터(§3 · §4 · §6)를 쓰고, 배치는 서버가 계산한다.

| 공장 | 대시보드 |
|---|---|
| 생산 라인 | 프로젝트 (`agent.project_path` 마지막 이름, 없으면 `project_key`) |
| 주 설비 | 세션 |
| 보조 설비 | 서브에이전트 · 워크플로 에이전트 (워크플로는 그 에이전트들을 감싸는 묶음 틀) |
| 배관 | `spawn` (부모 → 자식) · `handback` (자식 → 부모) |
| 라인 간 컨베이어 | `message` 엣지 (라인이 다르면 라인 사이, 같으면 라인 안) |
| 미확인 반입구 | "부모 미확인" · "외부" 노드 — 그 라인의 맨 오른쪽 |

**배치 규칙** (위에서부터 적용, 같은 입력이면 같은 출력)

| 코드 | 규칙 |
|---|---|
| T-01 | 라인 순서: 살아 있는 설비(`DONE` · `FAILED` 아님)가 있는 라인 먼저 → 라인의 가장 늦은 `last_event_at` 최근 순 → 라인 이름 순 |
| T-02 | 열 = 깊이: 세션 0 열, 그 자식 1 열 … (`agent.depth` 가 아니라 이 라인 안 부모 사슬 길이). 부모 없는 서브에이전트는 미확인 반입구 아래 1 열 |
| T-03 | 행 = 깊이 우선 순서: 라인 안 뿌리(세션)를 `started_at` 순으로, 각 부모 아래 자식을 `started_at` 순(같으면 `agent_key`)으로 깊이 우선 탐색한 순서. 한 설비는 한 행 |
| T-04 | 칸 크기 고정 (설비 상자 너비 · 높이 · 가로 · 세로 간격은 상수) — 설비 상자끼리 · 라인 상자끼리 겹침 0 |
| T-05 | `DONE` · `FAILED` 이고 `ended_at` 이 지금보다 30 분 넘게 이전인 설비는 칸을 만들지 않고 부모 설비의 `folded` 수에 더한다 ("+N 완료"). 자손도 함께 접힌다. 접힌 설비의 숫자는 부모 누적에 더하지 않는다(누적은 §6 그대로) |
| T-06 | T-05 뒤에도 설비 > 300 이면 T-01 순서의 뒤 라인부터 라인 머리 한 줄로 접는다(`folded_lines`), 300 이하가 될 때까지 |
| T-07 | 결정적: 같은 DB 상태 · 같은 `now` · 같은 필터면 좌표까지 같은 응답 |

- 범위: 기본 「지금 살아 있는 것 + 최근 24 시간 안에 기록이 있는 것」, 필터 기간 · 프로젝트 (D-02 와 같음).
- 설비 값: 상태 · 규칙 · `state_since` · 경과 · 지금 도구(그 에이전트의 결과 없는 마지막 `tool_call` 의 `tool` · `target`) · 누적 출력(기록 · 추정 보정) · 추정 보정 비용(= §6 `totals` 의 자기 몫) · **스파크** = 최근 30 분 분당 추정 보정 출력(`output_est` 가 있으면 그 값, 없으면 `output_tokens`, `<synthetic>` 제외) `[추정]` 30 칸 (가장 오래된 것부터, 지금 분이 마지막).

---

## 6. 작업량 지표

| 지표 | 정의 | 원천 |
|---|---|---|
| 입력 토큰 | `usage.input_tokens` 합 | S2 · S3 |
| 캐시 읽기 · 쓰기 | `cache_read_input_tokens` · `cache_creation_input_tokens` 합 | S2 · S3 |
| 출력 토큰 | `output_tokens` 합 (그중 `thinking_tokens` 따로) | S2 · S3 |
| 추정 출력 토큰 | 의심 요청은 `output_est`, 나머지는 `output_tokens` 를 쓴 합 (§6.2) `[추정]` | 계산 |
| 캐시 적중률 | 캐시 읽기 ÷ (입력 + 캐시 읽기 + 캐시 쓰기) | 계산 |
| 도구 호출 | `tool_use` 수, 도구별 · 성공/오류별 | S2 · S3 |
| 작성 파일 | `Write` · `Edit` · `NotebookEdit` 의 서로 다른 `file_path` 수 | S2 · S3 |
| 실행 시간 | 연속 기록 간격이 5 분 이하인 구간의 합 (`active_seconds`) `[가설]` | 타임스탬프 |
| 벽시계 시간 | `ended_at`(또는 지금) − `started_at` | 타임스탬프 |
| 하위 에이전트 | 직계 · 전체 자손 수 | `edge` |
| 추정 비용 | §6.1 공식 (API 단가 환산) | 계산 `[추정]` |
| 추정 보정 비용 | `cost_est_usd` 합 — 예산 · 추세의 기준 (§6.3) | 계산 `[추정]` |

규칙
- `requestId` 가 같은 줄은 한 번만 센다(A3).
- **자기 작업량**과 **자손 포함 작업량**을 따로 보여 준다. 세션 합계 = 자기 + 자손 합(G7). 서브에이전트 기록을 부모 합계에 다시 더하지 않는다(A4).
- 일자는 KST 기준으로 자른다.
- `model = "<synthetic>"` 줄(109 건 `[실측]`)은 Claude Code 가 만든 가짜 응답이므로 토큰 · 비용에서 뺀다.
- 캐시 적중률의 분모가 0 이면 `NULL`("—") 이다. 0 % 로 쓰지 않는다.

### 6.1 비용 단가표 (Q4 확정)

**공식** (메시지 한 건, 단위 US$ · 단가는 1M 토큰당)

```
cost = ( input_tokens   × in
       + cache_read      × cr
       + cache_write_5m  × in × 1.25
       + cache_write_1h  × in × 2.0
       + output_tokens   × out ) / 1e6
       × (speed == "fast" ? fast_mult : 1)
```

- `thinking_tokens` 는 `output_tokens` 안에 들어 있으므로 따로 더하지 않는다 `[가설: 표본 대조로 확인]`.
- 캐시 쓰기 배수: 5 분 TTL 1.25 배, 1 시간 TTL 2 배 (전 모델 공통). 기록에 TTL 별 분리 값(`cache_creation.ephemeral_5m/1h_input_tokens`)이 있다 `[실측]`. 분리 값이 없는 옛 기록은 전부 5 분으로 본다.
- 웹 검색 · 웹 가져오기 요청 요금은 v1 에서 건수만 보여 주고 비용에 넣지 않는다.

**기본 단가표** — `config/pricing.yaml` `version: 2026-10-06` (Anthropic 1st-party API 정가, Claude API 스킬 단가표 캐시 2026-10-06 기준)

| 모델 ID | 입력 `in` | 출력 `out` | 캐시 읽기 `cr` | 빠른 모드 | 이 컴퓨터 기록 (assistant 메시지 수) `[실측]` |
|---|---|---|---|---|---|
| `claude-fable-5-1` | 10.00 | 50.00 | 0.25 | — | 15,348 |
| `claude-fable-5` | 10.00 | 50.00 | 1.00 | — | — |
| `claude-opus-5-5` | 4.00 | 20.00 | 0.20 | ×2 (8 / 40) | 22,024 |
| `claude-opus-5` | 5.00 | 25.00 | 0.50 | ×2 (10 / 50) | 7,872 |
| `claude-opus-4-8` | 5.00 | 25.00 | 0.50 | — | 233 |
| `claude-opus-4-7` · `claude-opus-4-6` | 5.00 | 25.00 | 0.50 | — | — |
| `claude-sonnet-5-5` | 2.00 | 10.00 | 0.20 | — | — |
| `claude-sonnet-5` | 2.00 | 10.00 | 0.20 | — | 8,862 |
| `claude-sonnet-4-6` | 3.00 | 15.00 | 0.30 | — | — |
| `claude-haiku-5-5` | 0.10 (≤100K) · 0.50 (>100K) | 0.50 · 2.50 | 0.01 · 0.05 `[추정: 입력의 0.1 배 — 공식 단가 페이지 대조 후 확정 (D-08)]` | — | — |
| `claude-haiku-4-5` | 1.00 | 5.00 | 0.10 | — | — |

```yaml
# config/pricing.yaml (발췌)
version: "2026-10-06"
source: "Anthropic 1st-party API list price"
cache_write_mult: { "5m": 1.25, "1h": 2.0 }
models:
  claude-opus-5-5:  { in: 4.00,  out: 20.00, cache_read: 0.20, fast_mult: 2.0 }
  claude-fable-5-1: { in: 10.00, out: 50.00, cache_read: 0.25 }
  claude-haiku-5-5:
    tiers:                       # 프롬프트(입력+캐시 읽기+캐시 쓰기) 크기 기준
      - { max_prompt: 100000, in: 0.10, out: 0.50, cache_read: 0.01 }
      - { max_prompt: null,   in: 0.50, out: 2.50, cache_read: 0.05 }
aliases:                         # 날짜 · 접미사가 붙은 ID 를 위 키로 모은다
  "claude-opus-5-5[1m]": claude-opus-5-5
```

운용 규칙
- 단가표에 없는 모델은 비용을 `NULL` 로 두고 D-04 에 "단가 없음 N 건" 을 띄운다. `make pricing-check` 가 그 목록을 찍는다.
- 단가는 바뀔 수 있으므로 단가표 `version` 을 행마다 남긴다(`pricing_ver`). 단가표를 고치면 `make reprice` 가 전 기간을 다시 계산한다.
- 화면의 비용은 항상 `[추정] API 정가 환산` 표시를 붙인다. Claude Code 구독 요금제로 쓴 경우 실제 청구와 다르다.
- 단가 원본: https://platform.claude.com/docs/en/about-claude/pricing — 분기마다 대조해 `version` 을 올린다.

### 6.2 추정 출력 (D-17 확정, v0.3)

`[실측]` 서브에이전트 · 워크플로 에이전트 기록의 `output_tokens` 는 스트리밍 시작값만 남은 경우가 많다 — 2026-10-17 서브에이전트 요청 17,492 중 11,999 (68.6 %), 워크플로 에이전트 85 중 60, 메인 세션 10,186 중 13. 원천에 최종값이 없으므로 기록값은 그대로 두고 하한 추정을 따로 둔다.

| 항목 | 규칙 |
|---|---|
| 요청 | 같은 기록 · 같은 `requestId` 의 assistant 줄 묶음 (A3 중복 제거와 같은 단위) |
| 의심 | 묶음의 기록 `output_tokens` 최대 **< 30** 이고, 묶음 `content` 블록을 JSON 으로 쓴 길이 합 **> 400** 자 |
| 추정 | `output_est = ceil((text 블록 글자 수 + tool_use 입력 JSON 글자 수) / 4)`. thinking 블록은 세지 않는다. `output_est < output_tokens` 이면 `output_tokens` 를 쓴다 (하한) |
| 비용 | `cost_est_usd` = §6.1 공식에서 `output_tokens` 자리에 `output_est` 를 넣은 값. 의심 아니면 `cost_usd` 와 같다. 단가 없는 모델이면 둘 다 `NULL` |
| 범위 | 모든 종류(세션 · 서브에이전트 · 워크플로 에이전트)에 같은 규칙. 종류로 거르지 않는다 |
| 표기 | 화면 · API · CSV 에 「기록」 과 「추정 보정 (D-17)」 을 나란히. 추정 쪽은 늘 `[추정]` |

- 길이는 수집 때 재고 버린다(§2.3). 본문을 다시 읽어 재계산하지 않으며, 규칙을 바꾸면 백필을 다시 돈다.
- 검사 V-12 는 QA1 `outputs/qa1/stream_heuristic.py` 와 같은 정의로 원천을 다시 재서 의심 비율을 대조한다.

### 6.3 예산 · 추세 (v0.3)

**예산** — `config/budget.yaml`

```yaml
warn_ratio: 0.8                  # 이 비율부터 주황, 1.0 부터 빨강
total:    { daily_usd: null, monthly_usd: null }
projects: {}                     # "<project_path 마지막 이름>": { daily_usd: …, monthly_usd: … }
```

- 금액은 사람이 넣는다. `null` 이면 그 칸은 「한도 미설정」 이고 경고를 내지 않는다. 코드에 금액을 쓰지 않는다.
- 기준 금액 = 기간 안 `cost_est_usd` 합 (추정 보정 포함). 기록 기준 `cost_usd` 합을 함께 보여 준다. 단가 없음 `NULL` 은 0 으로 더하지 않고 「단가 없음 N 건」 을 붙인다.
- 기간: 일 = KST 오늘 00:00 ~ 지금, 월 = KST 이번 달 1 일 00:00 ~ 지금.
- 프로젝트 = `agent.project_path` 의 마지막 이름 (없으면 `project_key`). 자손의 비용은 그 자손의 `project_path` 로 센다.
- 단계: `ok` (< warn_ratio) · `warn` (≥ warn_ratio) · `over` (≥ 1.0) · `unset`.
- 경고는 화면 표시만 한다(D-01 띠 · D-07 게이지). 알림(§7.2)은 보내지 않는다.

**추세**
- 단위: 일 (KST) · 주 (KST 월요일 00:00 시작) · 월 (KST 1 일).
- 값: `cost_usd` 합 · `cost_est_usd` 합 · 출력 토큰 · 추정 출력 토큰, 묶음 `total` 또는 `project`.
- 원천: `usage_daily`. 합은 같은 기간 `usage_event` 직접 합과 같아야 한다 (V-14).

**캐시 적중률 순위**
- 묶음: 프로젝트 · 세션(자손 포함) · 에이전트(자기만). 정렬 기본값 = `(1 − 적중률) × cost_est_usd` 큰 순 — 절감 여지가 큰 곳이 위.

---

## 7. 화면

### D-01 공장 평면도 `/`
v0.4 — 관제판을 디지털 트윈 평면도로 바꾼다. **v0.3 관제판의 항목은 하나도 빼지 않고** 오른쪽 패널로 옮긴다.
- 맨 위: 예산 단계가 `warn` · `over` 인 칸이 하나라도 있으면 경고 띠 (「오늘 전체 82 % · Standard MES 이번 달 104 %」 꼴) → D-07 링크.
- **평면도** (넓은 화면 ≈ 70 %): §5.4 배치의 라인 · 설비 · 배관 · 컨베이어를 SVG 로. 라인 머리 = 라인 이름 · 가동 수(살아 있는 설비) · 대기 수(`WAITING_*`). 필터 기간 · 프로젝트, 확대 · 축소 · 이동(버튼 · Ctrl+휠 · 끌기) · 「맞춤」.
- **설비 상자**: 상태 표시등 · 이름 앞 24 자 · 상태 · 경과 · 지금 도구 · 30 분 스파크와 지금 분당 `[추정]` · 누적 출력 · 추정 보정 비용 · 접힌 수 "+N 완료". 누르면 패널에 요약(상태 · 판정 규칙과 근거 · 부모 · 자식 · 작업량), 두 번 누르거나 Enter 면 D-03.
- **패널** (넓은 화면 ≈ 30 %, 1000 px 미만이면 평면도 아래):
  - 상태별 카드 숫자 (실행 · 입력 대기 · 권한 대기 · 잠듦 · 자식 대기 · 멈춤 의심 · 오늘 끝남).
  - **"내 차례" 목록**: `WAITING_INPUT` · `WAITING_PERMISSION` 을 기다린 시간 긴 순. 프로젝트 · 이름 · 마지막 도구 · 기다린 시간. 터미널 이동은 못 하므로 `cwd` 와 세션 이름을 복사 버튼으로.
  - 선택한 설비 요약 (선택이 없으면 살아 있는 에이전트 목록: 상태 · 이름 · 프로젝트 · 지금 쓰는 도구와 대상 · 경과 시간 · 출력 토큰 · 자식 수).
  - 오늘 출력 토큰 · 도구 호출 · 작성 파일 · 상위 5 에이전트.
  - 최근 상태 변화 피드 (SSE), 파싱 오류 건수.
- 실시간: `agent.state` → 그 설비 표시등을 바로 다시 칠한다 · `agent.new` · `edge.new` → 배관 흐름(§7.4) 뒤 `/api/v1/twin` 다시 받기(1 초 묶음) · `agent.usage` → 5 초 묶음으로 다시 받기. SSE 연결은 탭당 1 개(§7.2 알림과 공유).
- 접근성: 설비마다 `role="button"` · `tabindex="0"` · `aria-label`(이름 · 상태 · 경과). 같은 내용의 화면 낭독기용 표를 숨겨 둔다.

### D-02 네트워크 구성도 `/graph`
§5 그대로. 노드를 누르면 오른쪽 패널에 요약(상태 · 근거 규칙 · 작업량 · 부모 · 자식), 두 번 누르면 D-03.

### D-03 에이전트 상세 `/agents/{agent_key}`
- 머리: 이름 · 종류 · 유형 · 프로젝트 · 모델 · 버전 · 상태와 판정 근거 · 시작/끝/경과.
- 계보: 조상 경로(빵부스러기) · 직계 자식 표.
- 작업량: §6 지표 표 + 시간대별 출력 토큰 막대.
- 도구 타임라인: 도구 호출 순서 (도구 · 대상 · 성공/오류 · 걸린 시간).
- 작성 파일 목록.
- "원본 보기": 원천 `.jsonl` 을 그때 읽어 사용자 · assistant 메시지를 접힌 상태로 보여 준다(저장 안 함).

### D-04 작업량 `/usage`
기간 선택 · 묶음 기준(에이전트 / 프로젝트 / 유형 / 모델 / 일자) · 순위 표 · 일별 추이 · 캐시 적중률 · 추정 비용 열(단가표 있을 때) · 추정 출력 · 추정 보정 비용 열 (§6.2). CSV 내보내기 (같은 열).

### D-05 타임라인 `/timeline`
가로축 시간, 세로축 에이전트(부모 아래 자식 들여쓰기)의 간트 막대. 막대 색 = 그 시점 상태(`state_log`). 동시에 몇 개가 돌았는지 위쪽 면적 그래프.

### D-06 파이프라인 `/pipeline`
행 = 회사, 열 = 단계(`01 Analyze` → `02 Design` → `03 UI` → `04 QA` → `00 PM` 순으로 보여 준다. 00 PM 이 01 · 02 결과를 읽어 관리산출물을 만들기 때문이다. 그 뒤에 `05 Open` · `06 Coding` · `08 AI Agent Making`). 칸 = §7.1 상태 색 + `have/need` + 버전(v1.x) + 마지막 산출물 날짜. 칸을 누르면 판정 규칙 코드 · 근거 파일 목록 · `progress.md` 해당 줄 · 마지막으로 손댄 에이전트(D-03 링크)가 펼쳐진다. 오른쪽 끝 열은 회사별 "다음 단계" (첫 번째 미완료 단계).

### D-07 비용 · 효율 `/insights` (v0.3)
- 위: 예산 게이지 — 전체 오늘 · 이번 달, 그 아래 한도가 있는 프로젝트마다 오늘 · 이번 달. 게이지 = `cost_est_usd` / 한도, 옆에 기록 기준 금액. `unset` 은 「한도 미설정 — config/budget.yaml」.
- 가운데: 비용 추세 — 일 · 주 · 월 전환, 기간 선택. 선 2 (기록 · 추정 보정) + 프로젝트별 쌓은 막대 (추정 보정 기준). 모든 금액에 `[추정] API 정가 환산`.
- 아래: 캐시 적중률 — 묶음(프로젝트 · 세션 · 에이전트) 전환 순위 표 (적중률 · 캐시 읽기 · 입력 · 캐시 쓰기 · 추정 보정 비용, §6.3 정렬) + 전체 일별 적중률 선. 행을 누르면 D-03 (세션 · 에이전트) 또는 D-04 프로젝트 필터.

### 7.1 파이프라인 진척 규칙 (Q5 확정)

`[실측: 2026-10-17 각 에이전트 폴더 확인]` 근거
- 01 · 02 · 00 은 실행마다 `outputs/YYYYMMDD-HHMMSS-<scope>/` 폴더와 `run.json` 을 남기고, 산출물 이름이 `NN.SF-<코드>_<문서명>_<회사>_v<버전>.docx` 이다 (예: `01.SF-AD1_현행업무분석서_고려솔더_v1.0.docx`).
- 03 · 04 는 `outputs/` 바로 아래 `<회사>_제조AI_<문서명>_v<버전>.<확장자>` 로 쌓는다. 구판은 `_구판_<날짜>/` 로 옮긴다.
- `progress.md` 는 자유 서술이다. 회사별 결과는 `## ` · `### ` 표제에 `<회사> … — 완료` · `재실행 완료` · `(날짜)` 꼴로 적히고, 사람 판단이 필요한 일은 `## 지금 해야 할 것` 아래 `### (X) <회사> … — 사용자 판단 필요` 로 적힌다.
- `05 Open Agent` · `08 AI Agent Making Agent` 는 `progress.md` 가 없다. `06 Coding Agent` 는 회사 하나(고려솔더)의 웨이브 상태를 `✅ 🔄 ⏸` 로 적는다.

**회사 사전** — `config/companies.yaml`

| 표준 이름 | 별칭 (파일 · 표제에서 같은 회사로 본다) |
|---|---|
| 경동글로벌텍 | 경동 |
| 고려솔더 | 주식회사 고려솔더 |
| 광성정밀 | 광성 |
| 니즈푸드 | 니즈 |
| 브랜뉴머시너리 | 브랜뉴 |
| 송월타월서울상사 | 송월타월 서울상사 · 송월타월 · 송월 |
| 엘컴화인 | lcomFine |
| 와이엔프린팅 | — |
| 원터치 | OneTouch |
| 임진강김치 | 임진강 |
| 평창꽃순이김치 | 평창 |

- 이름을 맞출 때 공백 · `주식회사` · `(주)` 를 지우고 비교한다 (법인격이 이름 가운데 있는 회사 대응).
- 사전에 없는 이름은 칸을 만들지 않고 "미등록 회사 N 건" 으로 보여 준다 (두손푸드처럼 참조로만 나오는 이름 걸러내기).

**단계 사전** — `config/pipeline.yaml`

| 단계 | 폴더 | 필요한 산출물 (`need`) | 찾는 위치 · 패턴 |
|---|---|---|---|
| `01` 분석 | `01 Analyze Agent` | SF-AD1 · AD2 · AD3 (3) | `outputs/*-all/*SF-AD{1,2,3}_*_{회사}_v*.docx` |
| `02` 설계 | `02 Design Agent` | SF-TD1 ~ TD5 (5) | `outputs/*-all/*SF-TD{1..5}_*_{회사}_v*.docx` |
| `03` 화면 | `03 UI Agent` | 화면설명서 html · 화면정의서 pptx · 영상 mp4 (3, 영상은 4 벌 중 1 개 이상) | `outputs/{회사}_제조AI_화면{설명서,정의서}*_v*.*` |
| `04` 시험 · 인수 | `04 QA Agent` | 단위테스트결과서 · 통합테스트결과서 · 시스템전환결과서 · 메뉴얼 · 사용자테스트결과서 · 운영지원계획서 · 운영현황보고서 (7) | `outputs/{회사}_제조AI_{문서명}_v*.docx` |
| `00` 관리 | `00 PM Agent` | 중간보고서 · SF-PM1 ~ PM4 (5) | `outputs/*-midterm/` 의 `run.json` 회사 · `outputs/pm-{회사}/*SF-PM{1..4}*` |
| `05` · `06` · `08` | 각 폴더 | 규칙 미정 | — → `UNKNOWN` (06 은 대상 회사 칸에 웨이브 표시만) |

`_구판_*` · `_preview*` · `scratch/` · `tour/` 아래 파일은 세지 않는다. 같은 산출물이 여러 버전이면 가장 높은 `v` · 가장 최근 실행을 쓴다. 실행 폴더의 회사는 `run.json` → 폴더 안 산출물 파일명 순으로 정한다.

**칸 상태 판정** (위에서부터 먼저 걸리는 것)

| 코드 | 조건 | 상태 | 색 |
|---|---|---|---|
| P-01 | `progress.md` 의 `## 지금 해야 할 것` 절 안 표제 · 표 행에 그 회사 + (`판단 필요` · `사용자 판단` · `확인 필요`) | `NEEDS_DECISION` (다른 상태 위에 배지로 겹친다) | 주황 배지 |
| P-02 | 그 단계 폴더의 세션 · 서브에이전트가 `RUNNING` / `WAITING_*` 이고, 최근 30 분 안에 그 회사 이름이 든 파일을 읽거나 썼다(`tool_call.target` · `file_touch.path`) 또는 에이전트 이름에 회사 이름이 있다 | `IN_PROGRESS` | 초록 |
| P-03 | `have = need` | `DONE` | 회색 진함 |
| P-04 | `0 < have < need` | `PARTIAL` (`have/need` 표시) | 회색 연함 |
| P-05 | `have = 0` 이지만 `progress.md` 표제에 그 회사 + `완료` | `DONE` + "파일 없음" 경고 (문서와 파일이 어긋남) | 회색 + ⚠ |
| P-06 | `have = 0` · 표제 언급 없음 | `NOT_STARTED` | 흰색 |
| P-07 | 단계 규칙 없음 (`05` · `08`) | `UNKNOWN` | 빗금 |

추가 표시
- **뒤처짐**: 앞 단계의 최신 실행이 뒤 단계 산출물보다 새로우면 (예: 02 설계를 10-16 에 다시 돌렸는데 03 화면은 10-04 판) 칸에 ↻ "앞 단계 갱신됨" 을 단다. 근거는 앞 단계 `run.json` 시각과 뒤 단계 파일 mtime 비교.
- **마지막 손댄 에이전트**: 그 칸의 산출물 경로를 `file_touch` 에서 찾아 가장 최근 에이전트를 링크한다. 못 찾으면 "대시보드 수집 이전".
- 갱신: `outputs/` · `progress.md` 변경 감시 + 5 분마다 재판정.

### 7.2 WAITING 알림 (v0.3)
- 서버 변경 없음. 모든 화면의 공통 스크립트(`base.html`)가 SSE `agent.state` 를 받는다.
- 알리는 때: 상태가 `WAITING_INPUT` 또는 `WAITING_PERMISSION` 으로 **바뀌는 순간**만. 그 밖의 상태 · 예산은 알리지 않는다.
- 내용: 제목 「권한 대기」 / 「입력 대기」, 본문 = 프로젝트 · 이름. 누르면 그 에이전트의 D-03.
- 한 번만: 같은 `(agent_key, state_since)` 는 한 번. 화면을 처음 열 때 이미 대기 중이던 것은 알리지 않는다. 탭이 여럿이면 BroadcastChannel 로 한 탭만 알린다.
- 배지: 탭 제목 앞 `(N) ` 과 파비콘 점 — N = 지금 `WAITING_*` 수.
- 권한: 머리글 「알림 켜기」 버튼(사용자 동작)으로 `Notification.requestPermission()`. 켜짐/꺼짐은 브라우저 localStorage 에만 둔다. 거부 · 미지원이면 버튼에 그 사실을 적고 배지만 쓴다.
- 훅 미설치면 권한 대기를 구분하지 못하므로(§9.3) 「입력 대기」 로 알린다.

### 7.3 화면 틀 (v0.3)
- 깔끔한 대시보드형: 넓은 여백 · 카드 · 차트 중심. 밝은 테마 기본, `prefers-color-scheme: dark` 를 따르고 머리글 토글로 바꾼다(선택은 localStorage).
- 색 · 간격 · 글꼴은 `base.html` 의 CSS 변수 토큰만 쓴다. 화면별 스타일 조각을 따로 두지 않는다.
- §4.1 상태 색 8 은 이름(초록 · 노랑 …)을 그대로 두고, 두 테마 각각 배경 대비 ≥ 3:1 (도형) · 상태 글자 ≥ 4.5:1 이 되게 값을 정한다.
- 화면 7 모두 390 px 폭에서 가로 스크롤 0, 표는 칸 안에서만 가로로 민다. D-01 평면도도 자기 카드 안에서만 이동한다 (v0.4).

### 7.4 평면도 애니메이션 (v0.4)
- 색은 §4.1 상태 색 토큰(`--st-*`)만 쓴다. 새 색을 만들지 않는다.

| 대상 | 움직임 |
|---|---|
| `RUNNING` 표시등 | 2 초 주기 맥박 |
| `WAITING_INPUT` · `WAITING_PERMISSION` | 경광등(돌아가는 빛) + 「!」 배지 |
| `STALE` | 알람 삼각형 1 초 깜빡임 |
| `SLEEPING` | 멈춤 · 깰 시각 표시 |
| `DONE` · `FAILED` | 흐림 (FAILED 는 빨강 테두리 유지) |
| spawn 배관 | 자식이 `RUNNING` 인 동안 느린 입자 흐름 · 새 spawn 순간 굵은 입자 1 회 + 새 설비 0.4 초 나타남 |
| handback | 자식 → 부모 거꾸로 입자 1 회 → 설비 흐림 |
| message 컨베이어 | 점선, 굵기 = 횟수, 새 메시지 순간 점선이 1 회 흐름 |

- `prefers-reduced-motion: reduce` 면 깜빡임 · 맥박 · 입자를 모두 끄고 색 · 배지만 남긴다.
- 애니메이션은 CSS · SVG 로만 (새 라이브러리 없음). 화면에 보이지 않는 탭에서는 입자를 멈춘다.

---

## 8. API

모두 읽기 전용 · JSON · `127.0.0.1` 만.

| 메서드 · 경로 | 내용 |
|---|---|
| `GET /api/v1/summary` | 상태별 수 · 오늘 작업량 · 파싱 오류 수 |
| `GET /api/v1/agents?state=&project=&kind=&since=` | 에이전트 목록 |
| `GET /api/v1/agents/{key}` | 상세 (작업량 · 부모 · 자식 · 판정 근거) |
| `GET /api/v1/agents/{key}/tools` | 도구 호출 목록 |
| `GET /api/v1/graph?since=&project=&view=` | Cytoscape 형식 `{nodes, edges}` |
| `GET /api/v1/usage?from=&to=&group=` | 집계 표 |
| `GET /api/v1/timeline?from=&to=` | 간트 데이터 |
| `GET /api/v1/pipeline` | 회사 × 단계 표 |
| `GET /api/v1/budget` | 예산 칸별 기준 금액 · 기록 금액 · 한도 · 비율 · 단계 (§6.3) |
| `GET /api/v1/trend?grain=day\|week\|month&from=&to=&group=total\|project` | 비용 · 출력 추세 (기록 · 추정 보정) |
| `GET /api/v1/efficiency?group=project\|session\|agent&from=&to=` | 캐시 적중률 순위 |
| `GET /api/v1/twin?since=&project=` | 평면도 (§5.4) `{generated_at, lines[{key, name, live, counts, box, machines[{key, kind, name, parent, state, rule, since, elapsed_s, tool, target, out_total, out_est_total, cost_est_usd, spark[30], folded, box}], pipes[{src, dst, kind, at}]}], links[{src, dst, count}], folded_lines}` |
| `GET /api/v1/stream` | SSE: `agent.new` · `agent.state` · `agent.usage` · `edge.new` |
| `POST /hooks/event` | 훅 이벤트 수신 (로컬 · 본문 1 MB 제한 · 필요한 필드만 남기고 버림) |

---

## 9. 훅 연동 (Q1 확정 — v1 포함)

파일 감시와 훅을 **함께** 쓴다. 파일 감시는 과거 기록 · 작업량 · 관계의 원천이고, 훅은 상태를 **추정이 아니라 사건으로** 확정해 권한 대기 · 도구 실행 중 · 종료를 구분한다. 대시보드가 꺼져 있던 동안의 훅 이벤트는 잃지만, 파일 감시가 다시 따라잡는다.

### 9.1 설치

`[실측]` 지금 `~/.claude/settings.json` 에는 `PreToolUse` · `PostToolUse` · `Stop` 훅이 있다(이슈 자동 등록 등). 이것을 건드리지 않는다.

`make hooks-install` 이 하는 일:
1. `~/.claude/settings.json` 을 `settings.json.bak-agentdash-<시각>` 으로 백업한다.
2. 아래 이벤트마다 `matcher` 없는(전체) 항목을 하나씩 **덧붙인다**. 기존 항목의 순서 · 내용은 바꾸지 않는다. 덧붙인 항목에는 명령 경로로 식별 표시(`…/agentdash/scripts/hook_send.sh`)를 둔다.
   `SessionStart` · `SessionEnd` · `SubagentStart` · `SubagentStop` · `Stop` · `Notification` · `PreToolUse` · `PostToolUse` · `UserPromptSubmit`
3. 바꾼 내용의 diff 를 보여 주고 사용자가 `y` 를 입력해야 저장한다.
4. 저장 뒤 JSON 문법 검사, 실패하면 백업으로 되돌린다.

`make hooks-uninstall` 은 식별 표시가 붙은 항목만 지운다. `make hooks-check` 는 설치 여부 · 최근 수신 시각 · 이벤트별 수신 건수를 찍는다.

### 9.2 송신 · 수신

- `scripts/hook_send.sh`: 표준입력 JSON 을 `curl -m 1 -s -X POST http://127.0.0.1:8095/hooks/event --data-binary @-` 로 보내고 **항상 exit 0**, 표준출력에 아무것도 쓰지 않는다(Claude Code 동작에 영향 0). 1 초 안에 못 보내면 버린다.
- 수신기: 필요한 필드만 남기고 버린다 — `hook_event_name` · `session_id` · `transcript_path` · `cwd` · `tool_name` · 도구 입력의 `file_path` · `notification_type`/메시지 앞 120 자 · 서브에이전트 식별자. 도구 입력 본문 · 프롬프트 본문은 저장하지 않는다(G10).
- 서브에이전트 이벤트를 에이전트에 붙이는 키는 페이로드의 에이전트 식별자 또는 `transcript_path` 다 `[가설: 설치 후 실제 페이로드로 확정해 decisions.md 에 기록]`.

| 이벤트 | 상태 반영 |
|---|---|
| `SessionStart` | 새 세션 `RUNNING`(또는 `WAITING_INPUT`), `agent.new` 즉시 발송 |
| `UserPromptSubmit` | `WAITING_*` → `RUNNING` |
| `PreToolUse` | `RUNNING` + "도구 실행 중: <tool> <대상>" (R-02b · R-11 의 5 분 기준을 멈춤) |
| `PostToolUse` | 도구 실행 끝, `tool_call.ok` 갱신 |
| `Notification` (권한 요청) | `WAITING_PERMISSION` — "내 차례" 맨 위 |
| `Notification` (입력 대기) | `WAITING_INPUT` |
| `Stop` | 세션 응답 끝 → `WAITING_INPUT` (예약된 `ScheduleWakeup` 있으면 `SLEEPING`, 미종료 자식 있으면 `WAITING_CHILD`) |
| `SubagentStart` | 서브에이전트 `RUNNING`, 부모 연결 즉시 |
| `SubagentStop` | 서브에이전트 `DONE` |
| `SessionEnd` | 세션 `DONE`, 미종료 자식은 5 분 뒤 R-11 로 판정 |

### 9.3 훅 없이 / 훅 있이

| 항목 | 파일 감시만 | 훅 함께 |
|---|---|---|
| 새 에이전트 반영 | ≤ 5 초 (1 초 묶음 + 파싱) | ≤ 1 초 |
| 권한 대기 구분 | 불가 (`WAITING_INPUT` 으로 합침) | 가능 |
| 긴 도구 실행 vs 멈춤 | 5 분 뒤 `STALE` 오판 가능 | 구분 |
| 서브에이전트 종료 | 부모 기록의 결과 반환으로 판정 | `SubagentStop` 으로 확정 |

---

## 10. 검증 도구 (`make gate`)

| 코드 | 검사 | 통과 기준 | 목표 |
|---|---|---|---|
| V-01 `check_counts` | 원천 파일 수(세션 · 서브에이전트 · 워크플로 에이전트) ↔ `agent` 행 수 | 일치 | G1 |
| V-02 `check_link_rate` | 서브에이전트 중 `parent_key` 있는 비율 | ≥ 95% | G5 |
| V-03 `check_usage_sum` | 표본 세션 10 개의 토큰을 원천에서 직접 합산 ↔ DB | 일치 (requestId 중복 제거 후) | G7 |
| V-04 `check_no_payload` | DB 의 모든 TEXT 열 길이 ≤ 300, 본문 저장 열 없음 | 0 건 위반 | G10 |
| V-05 `check_readonly` | 실행 중 `~/.claude/` 쓰기 시도 0 (파일 열기 모드 감사 · 테스트에서 읽기 전용 마운트) · DB 경로가 원천 파일의 하드 링크(이미 있는 파일 `st_nlink > 1`)면 거부 | 0 건 | G10 |
| V-06 `check_bind` | 서버 바인드 주소 `127.0.0.1` | 통과 | G10 |
| V-07 `check_parse_errors` | 파싱 오류율 | ≤ 0.1% 줄 | P1 |
| V-08 `check_fixtures` | 버전별 픽스처 파싱 회귀 테스트 | pytest 통과 | R1 |
| V-09 `check_cost` | 표본 메시지 20 건의 비용을 §6.1 공식으로 손계산 ↔ DB, 단가 없는 모델 목록 | 차이 0, 목록 출력 | G8 |
| V-10 `check_hooks` | 설치 후 기존 훅 항목이 설치 전과 같은지(바이트 비교), 송신 스크립트가 서버 꺼짐에서도 exit 0 · 1 초 안에 끝나는지 | 통과 | G10 · P5 |
| V-11 `check_pipeline` | 회사 × 단계 칸마다 근거(`src`)가 있고, 표본 10 칸을 손으로 센 `have/need` 와 대조 | 근거 없는 칸 0, 대조 일치 | G9 |
| V-12 `check_usage_est` | 원천을 §6.2 정의로 다시 재서 의심 요청 비율 ↔ DB `output_est` 있는 행 비율 · 의심 행 `output_est ≥ output_tokens` · 비의심 행 `NULL` | 비율 차 ≤ 0.5 %p · 위반 0 | G8 |
| V-13 `check_budget` | 칸마다 `/api/v1/budget` 기준 금액 ↔ `usage_event` 직접 합 (KST 일 · 월) | 차이 ≤ $0.01 | G8 |
| V-14 `check_trend` | 일 · 주 · 월 추세 합 ↔ `usage_daily` 합 ↔ `usage_event` 합 (기록 · 추정 각각) | 일치 | G7 · G8 |
| V-15 `check_efficiency` | 표본 10 행의 캐시 적중률을 §6 공식으로 손계산 ↔ API | 차이 ≤ 0.001 | G7 |
| V-16 `check_contrast` | 두 테마 토큰의 상태 색 글자 대비 · 도형 대비 | 글자 ≥ 4.5:1 · 도형 ≥ 3:1 | — |
| V-17 `check_twin` | 실제 DB `/api/v1/twin`: 설비 누적 = `usage.totals` · 스파크 합 = `usage_event` 분당 직접 합 · 설비 상자 겹침 0 · 접힌 수 + 칸 수 = 범위 안 에이전트 수 · TEXT ≤ 300 · 응답 시간 | 불일치 0 · 겹침 0 · ≤ 300 ms (300 설비) | G2 · G6 |

---

## 11. 디렉터리

```
Multi-agent Dashboard/
├─ intro.md · problem.md · spec.md
├─ CLAUDE.md · decisions.md · progress.md        (구현 단계)
├─ Makefile · pyproject.toml · uv.lock
├─ config/
│  ├─ settings.yaml        원천 경로 · 포트 · stale_after_sec: 300 (Q2) · 백필 범위(Q6)
│  ├─ pricing.yaml         모델별 단가 · 캐시 쓰기 배수 · 빠른 모드 배수 (Q4, §6.1)
│  ├─ pipeline.yaml        단계 폴더 · 필요한 산출물 · 파일 패턴 (Q5, §7.1)
│  ├─ companies.yaml       회사 표준 이름 · 별칭 (§7.1)
│  └─ budget.yaml          예산 한도 · 경고 비율 (§6.3, v0.3)
├─ src/agentdash/
│  ├─ app/        main.py · settings.py · sse.py · routers/{pages,api,hooks}.py · templates/ · static/
│  ├─ collect/    watcher.py · tail.py · hooks_rx.py · parsers/{session_file,transcript,meta,workflow,progress}.py
│  ├─ core/       model.py · linker.py · state.py · usage.py · graph.py · pipeline.py · budget.py · twin.py
│  └─ db/         conn.py · schema.sql
├─ scripts/       hook_send.sh · hooks_install.py · gate/*.py
├─ tests/         fixtures/<cc_version>/ · test_*.py
├─ data/          agentdash.db (git 제외)
└─ outputs/       CSV 내보내기
```

---

## 12. 구현 순서

| 단계 | 내용 | 끝 기준 |
|---|---|---|
| M1 | 파서 · 증분 읽기 · 스키마 · 백필 · 단가표 · 비용 계산 | V-01 · V-03 · V-07 · V-09 통과 |
| M2 | 부모 연결 · 상태 판정 · 훅 수신기 · 설치 스크립트 · SSE | V-02 · V-10 통과, 표본 30 건 상태 수동 대조 오판 ≤ 2 (G4) |
| M3 | D-01 관제판 · D-02 구성도 · D-03 상세 | G2 · G3 · G6 수용 기준 |
| M4 | D-04 작업량 · 비용 · D-05 타임라인 · CSV | G7 · G8 |
| M5 | D-06 파이프라인 (회사 · 단계 사전, 진척 판정) | V-11 통과 (G9) |
| M6 | `make gate` 전체 · LaunchAgent(선택) | V-01 ~ V-11 전부 통과 |
| M7 (v0.3) | 결정 반영 · 추정 출력 · 예산 · 추세 · 캐시 적중률 · D-07 · 알림 · 화면 틀 | V-01 ~ V-16 전부 통과 |
| M8 (v0.4) | 트윈 배치 · `/api/v1/twin` · D-01 공장 평면도 · 애니메이션 | V-01 ~ V-17 전부 통과 |

---

## 13. 수용 기준

1. `make backfill` 후 D-01 의 누적 에이전트 수가 원천 파일 수와 같다. (G1)
2. 다른 터미널에서 새 세션을 띄우고 서브에이전트 2 개를 백그라운드로 실행하면, 5 초 안에 D-01 평면도의 설비 3 개와 D-02 노드 3 개(세션 1 + 자식 2)가 `RUNNING` 으로 나타나고 `spawn` 배관 · 엣지로 이어진다. (G2 · G5 · G6)
3. 훅을 설치한 상태에서 그 세션이 권한 승인을 요청하면 1 초 안에 `WAITING_PERMISSION` 으로 "내 차례" 목록 맨 위에 뜬다. (G3)
4. 서브에이전트가 결과를 넘기면 `DONE` 으로, 세션 프로세스를 강제 종료하면 진행 중이던 자식이 **5 분** 안에 `STALE` 로 바뀐다. 10 분 걸리는 `sleep 600` Bash 를 돌리는 세션은 훅이 있을 때 `STALE` 로 바뀌지 않는다. (G4)
5. `/loop` 세션이 `ScheduleWakeup` 으로 잠들면 `SLEEPING` 과 깰 시각이 보인다. (G3)
6. D-04 에서 임의 세션의 출력 토큰 합이 원천 직접 합산과 같고, 세션 합계 = 자기 + 자손 합이다. 같은 세션의 추정 비용이 §6.1 손계산과 같다. (G7 · G8)
7. D-06 에 11 개사 × 단계 표가 뜨고, 고려솔더의 `01` · `02` 칸이 `DONE` v1.0 (실행 `20261016-151506-all` · `20261016-154028-all`) 으로, `05` · `08` 열이 `UNKNOWN` 으로 나온다. (G9)
8. `make hooks-install` → `make hooks-uninstall` 뒤 `~/.claude/settings.json` 이 설치 전과 바이트 단위로 같다. (G10)
9. `make gate` 가 V-01 ~ V-16 을 모두 통과한다. (G10)
10. 서브에이전트 기록이 있는 세션의 D-04 · D-07 에 「기록」 과 「추정 보정 (D-17)」 이 나란히 나오고, 추정 보정 ≥ 기록이다. (G8)
11. `config/budget.yaml` 에 전체 일 한도를 오늘 쓴 금액의 0.9 배로 넣으면 D-01 에 경고 띠가 뜨고 D-07 게이지가 주황(또는 빨강)이다. `null` 로 되돌리면 「한도 미설정」. (G8)
12. D-07 의 일 · 주 · 월 추세 합이 D-04 같은 기간 합과 같다. (G7 · G8)
13. 알림을 켠 상태에서 다른 터미널의 세션이 입력 대기가 되면 브라우저 알림이 한 번 뜨고, 탭 제목에 `(N)` 이 붙는다. 새로 고침해도 다시 뜨지 않는다. (G3)
14. D-01 ~ D-07 이 밝은 · 다크 두 테마에서 390 px 가로 스크롤 0 · 콘솔 오류 0 이다.
15. D-01 평면도에서 이 저장소 라인 아래 루프 세션(주 설비)과 그가 띄운 서브에이전트(보조 설비)가 배관으로 이어져 보이고, 서브에이전트가 결과를 넘기면 거꾸로 흐름 뒤 흐려진다(`DONE`). 훅 상태 변화는 1 초 안에 표시등에 반영된다. (G2 · G3 · G6)
16. v0.3 관제판의 항목(상태 카드 · 내 차례와 복사 버튼 · 오늘 작업량 · 상위 5 · 피드 · 파싱 오류 · 예산 띠)이 D-01 패널에 모두 있다. (G3)
17. `prefers-reduced-motion` 을 켜면 평면도 움직임이 0 이고, 키보드(Tab · Enter)만으로 설비를 돌아다니며 D-03 으로 갈 수 있다.
