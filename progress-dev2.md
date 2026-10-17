# progress-dev2.md — 개발2 (관계 · 상태)

> 실측값 + 검증 명령만. 본문은 붙여 넣지 않는다(숫자 · 경로만).

## 1. 공표 — 공용 시그니처 (다른 사람은 이대로 쓴다. 바꿀 일이 있으면 §3 에 요청)

DB 쓰기 함수는 개발1 규약대로 **커밋하지 않는다**(호출한 쪽이 `con.commit()`), 쓰기는 `core.model` 함수(`set_parent` · `set_state` · `set_ended` · `add_edge`)를 거친다.

### `agentdash.core.linker` (L-01~L-07)

```python
# 순수 함수
@dataclass AgentRec(agent_key, kind, session_id, project_key="", depth=0, spawn_tool_use=None,
                    parent_agent_id=None, workflow_id=None, started_at=None, name=None)
@dataclass SpawnIndex(agent_calls: {tool_use_id: [author_key]}, workflow_calls: {wfId: [author_key]}, depth, started)
@dataclass(frozen) Link(parent_key: str | None, rule: "L-01".."L-05" | None, evidence: str)   # .resolved
def resolve(agent: AgentRec, index: SpawnIndex, *, sources_complete=True) -> Link
    # 못 찾으면 parent_key=None · sources_complete=False → L-04(재시도) / True → L-05 (구성도는 unresolved_key(project) 에 붙임)
def retry_pending(agents, links, index, *, sources_complete) -> {key: Link}      # L-04 바뀐 것만
def resolve_message(sender_key, to, *, agent_ids: set, names: {name: key}, at=None, keys: set | None = None) -> Edge   # L-06, 못 맞추면 X:<to>
def returned(signals: [ReturnSignal], last_activity_at) -> Return | None           # L-07 (D-04 대안 규칙)
def spawn_edge(child_key, link) / handback_edge(child_key, parent_key, ret) -> Edge | None
def facts(line: dict) -> [Fact]      # 줄 하나 → agent_call · workflow_call · send_message · handback_call · notification · agent_error · agent_message
def is_activity(line: dict) -> bool  # L-07 다시 깨어남 판정용
def session_key / agent_key / workflow_key / unresolved_key("U:<proj>") / external_key("X:<name>")
# DB
def on_line(con, author_key, line: dict) -> int    # ingest 가 assistant/user 줄마다 부른다 — task-notification · Workflow runId 를 남김
def note_notification(con, author_key, tool_use_id, status, at, task_id=None) -> bool   # 웨이브 D: task-id(=agentId) 로도 잇는다
def return_of(con, key) -> Return | None        # 웨이브 D: 한 에이전트의 L-07 반환 (is_error = failed/killed 알림 · Agent is_error)
def last_activity(con, key) -> str | None       # 웨이브 D: tool_call + 반환 뒤 기록 꼬리(읽기만)의 활동 줄
def signals_from_db(con, key=None) -> {key: [ReturnSignal]}
def note_workflow_call(con, author_key, wf_id, at) -> bool
def resolve_all(con, *, sources_complete=True) -> {key: Link}   # parent_key · spawn/workflow/handback/message 엣지 · ended_at
def scan_projects(projects_dir) -> Scan    # 원천 트리 직접 스캔(읽기만) — check_link_rate · 테스트용
```

### `agentdash.core.state` (R-01 · R-02a · R-02b · R-03~R-12)

```python
STATES (8) · RULES (13)
@dataclass HookInfo(event, at: datetime, notification_type=None, tool_running=False, tool_since=None, tool_name=None, tool_target=None)
@dataclass S1Info(status, pid_alive, updated_at=None)
@dataclass Ctx(last_record_at, s1, pending_tool_use, turn_ended, wakeup_at, open_children, returned, return_error,
               return_at, session_alive, hook)
@dataclass(frozen) Verdict(state, rule, evidence, slow=False, extra={})       # (state, rule, evidence) 로 풀린다
def evaluate(agent, ctx: Ctx, now: datetime, *, stale_after_sec=None, slow_after_sec=None) -> Verdict
    # agent 는 .kind 또는 {"kind": …}. 기준 시간 기본값은 settings(stale 300 · slow 90). evidence ≤ 300 자, 규칙 코드로 시작
def transition(prev_state, verdict) -> str | None    # state_log 사유. STALE → 다른 상태 = "<규칙> 회복"
def apply(con, agent_key, verdict, now) -> str | None   # model.set_state 로 상태 + state_log(사유 · 근거), state_reason = 규칙 코드
def evaluate_one(con, agent_key, now, *, s1map=None) -> (Verdict, 사유|None) | None
def evaluate_all(con, now=None) -> {key: Verdict}     # 깊은 것부터 (backfill 끝에서 부른다)
def post_hook(con, changed: set) -> None              # ingest.add_post_hook 용 — resolve_all + 바뀐 키와 조상 재판정
def register() -> None                                 # ingest.add_post_hook(post_hook)
def tick(db_path=None) -> int / start_ticker(interval_sec=None) -> (thread, stop)   # 10 초 주기 (collect.state_tick_sec)
```

### `agentdash.collect.hooks_rx` · `POST /hooks/event`

```python
filter_payload(raw) -> dict    # 화이트리스트: hook_event_name session_id transcript_path cwd agent_id agent_type
                               #   agent_transcript_path tool_name tool_use_id notification_type source reason · message/title 앞 120
                               #   tool_input 은 file_path notebook_path path url description(앞 120) subagent_type run_in_background 만
agent_key_for(p) -> "A:<agent_id>" | "A:<transcript 파일 agentId>" | "S:<session_id>"     (D-05)
store(con, p, now) -> agent_key      # hook_event(agent_key, at, event, detail JSON ≤ 300)
hook_info(con, agent_key) -> HookInfo | None   # PreToolUse 뒤 PostToolUse 없으면 tool_running
```
`POST /hooks/event`: 본문 > 1 MB → 413 · JSON 아님/이벤트 이름 없음 → 200 `{"accepted": false, "reason"}` · 정상 → hook_event 1 행 + 그 에이전트 즉시 판정 →
`{"accepted": true, "agent_key", "state", "rule", "changed"}`.

### SSE `GET /api/v1/stream` (`agentdash.app.sse`)

```
event: agent.new    data: {"agent_key", "kind"}
event: agent.state  data: {"agent_key", "state", "reason"}     # reason = state_log 사유 (규칙 코드 · 회복 · 근거)
event: agent.usage  data: {"agent_key"}
event: edge.new     data: {"src", "dst", "kind"}
id: 단조 증가 — 재접속 때 Last-Event-ID 로 링 버퍼(1000)에서 이어 받음. 첫 이벤트는 event: hello.
Accept: text/event-stream (또는 ?follow=1) 이면 붙잡고 실시간, 그 밖은 hello + 최근 묶음 한 번 보내고 닫는다 (G-17 check_routes 용).
```
원천은 개발1 `model.on_change` — `sse.broker.publish` 는 스레드 안전(감시기 스레드에서 불려도 된다). `sse.attach_model()` 이 on_change 구독 + `state.register()`.

### 훅 스크립트

- `scripts/hook_send.sh` — stdin → `curl -m 1 --connect-timeout 0.5 -s -o /dev/null POST 127.0.0.1:${AGENTDASH_PORT:-8095}/hooks/event`, 항상 exit 0, stdout · stderr 0 바이트.
- `scripts/hooks_install.py --settings <경로> [--uninstall | --check] [--yes]` — `--settings` 필수(기본값 없음). 실제 `claude_home/settings.json` 에는 `--yes` 거부(종료코드 2) · pytest 중 거부. 덧붙인 항목 = `{"hooks":[{"type":"command","command":"bash '<저장소>/scripts/hook_send.sh'","timeout":5}]}` (matcher 없음).
- `make hooks-install | hooks-uninstall | hooks-check` — 대상 = `SETTINGS=` 또는 `settings.claude_home/settings.json`. **사람만 실행.**

## 2. 진행 (웨이브 A, 2026-10-17)

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| G-06 부모 연결 (원천 직접) | PASS — 서브에이전트+워크플로 에이전트 241 중 241 = 100% (L-01 223 · L-02 12 · L-03 6) · 워크플로 노드 1/1 · 원천 줄 160204 · 1.9 s | `uv run python src/agentdash/tools/check_link_rate.py` |
| G-06 부모 연결 (개발2 백필 DB) | PASS — `agentdash-dev2.db` 서브에이전트 235 · 워크플로 에이전트 6 중 241 = 100% · 부모 미확인 0 · 워크플로 노드 1/1 | `rm data/agentdash-dev2.db*; AGENTDASH_DB=data/agentdash-dev2.db make backfill` (3.9 s) → `check_link_rate.py --db data/agentdash-dev2.db` |
| G-06 개발1 백필 DB | PASS — `agentdash-dev1.db` 241/241 | `check_link_rate.py --no-source --db data/agentdash-dev1.db` |
| G-06 `make gate` (기본 DB) | **FAIL** — `agentdash.db` 부모 있음 0/241. 기본 DB 는 개발1 `check_counts` 가 `ingest_all` 로 채우는데 linker 를 부르지 않는다 → §3 R3 | `make gate` |
| G-09 판정 규칙 13 | PASS — 39 passed (표 34 행: 규칙 13 전부 ≥ 1, 경계 89/91 · 299/301, 훅 도구 실행 중 R-01/R-02b/R-12, STALE → R-09 회복, D-09 shell, D-14, 픽스처 DB 전체 판정) | `uv run pytest -q tests/test_state.py` |
| G-10 연결 규칙 L-01~L-07 | PASS — 17 passed (픽스처 깊이 1·2 · 워크플로 6 · 포크 사본 · 늦은 부모 재시도 · 부모 미확인 · SendMessage 외부 노드 · handback/notification/재기상 · 개발1 ingest DB 위 resolve_all) | `uv run pytest -q tests/test_linker.py` |
| G-11 실시간 | PASS — 4 passed. 훅 POST → DB 상태 R-01 + SSE `agent.state` ≤ 1 s · 새 세션 + 서브에이전트 2 → 개발1 감시기 → SSE `agent.new` 3 건 0.19 s(≤ 5 s) · 1 MB 초과 413 · hook_send.sh 실제 송신 | `uv run pytest -q tests/test_realtime.py` (uvicorn 127.0.0.1 빈 포트 · 가짜 루트) |
| G-15 훅 설치 안전 | PASS — 가짜 settings(실제 hooks 구조: PostToolUse 3 · PreToolUse 1 · Stop 1) · 덧붙임 9 · 제거 후 바이트 동일 · 송신 0.01 s exit 0 stdout 0 B | `uv run python src/agentdash/tools/check_hooks.py` · `uv run pytest -q tests/test_hooks_install.py` (10 passed) |
| 실제 `~/.claude/settings.json` | 수정 시각 작업 전 `1792131308` (2026-10-16 15:15:08) = 작업 후 `1792131308` — 변경 없음. `make hooks-check`(읽기만) 출력 설치 0/9 · 다른 훅 5 | `stat -f '%m %Sm' ~/.claude/settings.json` |
| 실제 기록 판정 분포 (개발2 백필 DB, 16:45 무렵) | 세션 77: DONE R-07 73 · WAITING_INPUT R-05 2(그중 shell 1) · WAITING_CHILD R-04 1(오케스트레이터, D-14) · STALE R-06 1 / 서브에이전트 235: DONE R-08 226 · STALE R-11 7 · RUNNING R-09 2(개발1 · 개발2) / 워크플로 노드 1 · 에이전트 6 DONE R-08 · 엣지 spawn 236 · workflow 6 · handback 227 · message 55 | `AGENTDASH_DB=data/agentdash-dev2.db make backfill` 뒤 `SELECT kind,state,state_reason,COUNT(*) FROM agent GROUP BY 1,2,3` |
| G-13 개발2 DB 본문 | PASS — 행 62086 · TEXT 346296 · 300 자 초과 0 | `AGENTDASH_DB=data/agentdash-dev2.db uv run python src/agentdash/tools/check_no_payload.py` |
| G-17 | PASS — 16/16 HTTP 200 (stream · hooks 는 placeholder 아님, 남은 placeholder 14 = 화면 6 + agents/graph API 등 웨이브 B) | `uv run python src/agentdash/tools/check_routes.py` |
| pytest 전체 | 161 passed | `uv run pytest -q` |
| `make gate` | PASS 15 · FAIL 4 (G-06 기본 DB · G-18 웨이브 B · G-19 · G-20 개발1) · 미검증 3 (QA) | `make gate` |

### 확인한 가설

| D | 결과 | 근거 |
|---|---|---|
| D-04 handback ↔ 종료 1:1 | **가설 반박** — Agent tool_use 263 줄 = 고유 237(포크 사본 26) · 오류 2 → 자식 235. handback 221 건 = 자식 200(16 은 ≥ 2 회). handback 없는 35 = notification completed 16 · failed 12 · 신호 없음 7. 대안: handback ∪ notification ∪ is_error ∪ SubagentStop, 마지막 신호가 마지막 활동 이후일 때 종료 | `decisions.md` D-04 · `check_link_rate.py` 반환 분포 |
| D-05 훅 식별 필드 | 공식 문서 확인(`agent_id` · `agent_type` · `agent_transcript_path`) — 실제 페이로드는 `미검증`(설치 후) | `decisions.md` D-05 |
| D-09 `status: shell` | **확정(관찰 1)** — 턴 끝 시각에 찍힘 + 백그라운드 셸 자식 살아 있음 → idle 계열(R-03~R-05) + 근거 `(D-09)` | `decisions.md` D-09 |
| D-10 워크플로 · 손자 메타 · A2 | **확정** — toolUseId ↔ Agent tool_use.id 235/235 · parentAgentId 12/12 · runId 1/1 · 워크플로 에이전트 6/6 | `decisions.md` D-10 |
| D-14 (A1 S1 status 갱신) | **가설 반박(관찰 1)** — busy 가 턴 끝 뒤에도 백그라운드 자식 동안 남음 → 미종료 자식 있으면 WAITING_CHILD(R-04) | `decisions.md` D-14 |

## 3. 요청 (다른 사람에게)

- **R1 → 개발1 (완료 확인)**: transcript ingest 가 assistant/user 줄마다 `linker.on_line(con, author_key, line_dict)` 를 부른다 — 이미 `collect/ingest.py` `_on_line()` 으로 반영됨을 확인(16:45).
- **R2 → 개발1**: `Workflow` tool_call 의 `target` 에 tool_result `toolUseResult.runId`(`wf_…`)를 남겨 주면 좋다. 지금은 `on_line` 이 runId 를 spawn 엣지로 남기고, 없으면 같은 세션의 Workflow 호출자가 하나뿐일 때만 쓴다.
- **R3 → 개발1**: `ingest_all`(그리고 `check_counts` 가 기본 DB 를 채우는 경로)에서도 연결 · 판정이 돌게 — `ingest` 가 `_on_line` 처럼 `agentdash.core.state.post_hook` 을 지연 등록하거나 `ingest_all` 끝에 `linker.resolve_all` 을 부른다. 지금은 `backfill` 만 부르고 앱(`sse.attach_model` → `state.register`)만 등록해서, `make gate` 의 기본 `agentdash.db` 는 parent_key 0/241 → G-06 FAIL.
- **R4 → 개발1 (선택)**: R-06 · D-14 정확도용으로 세션 마지막 줄이 `system/turn_duration` 인지(턴 끝) 알 수 있으면 `Ctx.turn_ended` 에 쓴다. 테이블 열이 없으므로 방법은 개발1 판단(없어도 동작 — 근거 문구만 달라짐).
- **R5 → 아키텍트**: `app/main.py` 에 lifespan 추가 — 기동 때 `collect.watcher.start()` · `core.state.start_ticker()` · `app.sse.attach_model()`, 종료 때 stop 이벤트 set. 지금 `make run` 은 감시기 · 10 초 판정을 띄우지 않는다(라우터 import 때 attach_model 만 된다).
- **R6 → 아키텍트 (메모)**: CLAUDE.md 소유 표의 개발2 테스트 목록에 `tests/test_hooks_install.py` 가 빠져 있다(오케스트레이터 지시로 개발2 소유).

## 4. 웨이브 B (2026-10-17 17:05, DB `data/agentdash-dev2.db`)

새/바꾼 파일: `core/graph.py`(새) · `app/routers/{pages,agents,graph}.py` · `app/main.py`(R5 lifespan — 오케스트레이터 지시) · 템플릿 `dashboard.html` · `_d01_body.html` · `graph.html` · `agent.html` · `agent_raw.html` · `_dev2_style.html`(전부 새, 공용 `base.html` 은 손대지 않음 — `{% block body %}` 만 씀) · `tests/test_graph.py` · `tests/test_dashboard.py`(새, 개발2 소유로 둔다) · `tests/test_routes.py::test_placeholder_names_owner`(D-01 이 placeholder 라고 단정하던 줄을 "남은 placeholder 는 담당을 밝힌다" 로 고침 — 아키텍트 파일, §3 R7).

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| G-17 화면 6 + API 10 | PASS — 16/16 HTTP 200 (빈 DB) · placeholder 0 | `uv run python src/agentdash/tools/check_routes.py` |
| G-18 API 300 노드 | PASS — 합성 300 노드(프로젝트 4 · 세션 48 · 서브에이전트 240 · 워크플로 1+3 · 부모 미확인 · 외부) `/api/v1/graph` tree 7.3 · collab 7.4 · pipeline 7.2 ms (≤ 300) | `uv run pytest -q tests/test_graph.py -s` (6 passed) |
| G-18 접기 "+N" | PASS — 노드 402 → 접힘 390 · 세션마다 "+195" (DONE 자식 194 + DONE 손자 1, 살아 있는 손자를 품은 DONE 자식 · RUNNING 은 남김) · `expand=<키>` 로 펼침 | `test_graph.py::test_fold_over_300_and_expand` |
| G-18 보기 3 종 | PASS — tree=breadthfirst(프로젝트 묶음마다) · collab=cose(message 강조) · pipeline=`NN` 열 고정(`data.col`) · 잘못된 view/since → 422 | `test_300_nodes_under_300ms_each_view` · `test_filters` |
| G-18 브라우저 첫 그림 (300 노드 합성, Chrome) | tree 98 ms · collab 262 ms · pipeline 118 ms (≤ 2 초) · 앱 콘솔 오류 0 (확장 프로그램 경고만) | 8097 + 합성 DB(`AGENTDASH_NO_WATCH=1`) → `/graph?view=…` 의 `window.__graphFirstDrawMs` |
| 브라우저 실제 데이터 | D-01 · D-02(3 보기) · D-03 · 원본 보기 정상, SSE "연결됨", 노드 색이 SSE 로 바뀜(WAITING_CHILD→RUNNING) 확인, 앱 콘솔 오류 0 | `AGENTDASH_DB=data/agentdash-dev2.db AGENTDASH_PORT=8097 uv run python -m agentdash.app` (확인 뒤 정지) |
| 관제판 실제 숫자 (17:04) | 실행 2 · 입력 대기 2 · 권한 대기 0 · 잠듦 0 · 자식 대기 0 · 멈춤 의심 8 · 오늘 끝남 5 · 누적 끝남 308 · 에이전트 320 · 내 차례 2 · 파싱 오류 0 | `Q.summary_data` (dev2 DB) |
| 구성도 실제 숫자 | 기본(24 h + 살아 있음) 노드 33 · 엣지 28 · 에이전트 노드 24 ‖ 전체 노드 357 → 접힘 233 → 124 · 엣지 20 · 3.4 ms | `graph.build(con, since=…)` |
| D-01 · D-03 · 원본 보기 | 8 passed — 내 차례 순서(권한 먼저 · 오래 기다린 순) · cwd/이름 복사 · 지금 도구 · R-12 응답 느림 · 파싱 오류 · 피드 · 조상 빵부스러기 · 부모 미확인 표시 · `[추정] API 정가 환산` · 없는 키 200 found=false · 원본 보기: thinking · 도구 결과 · 명령 둘째 줄 · Write content 미노출, 요청 전후 DB 행 수 동일 · 본문 문자열 DB 0 · 원천 루트 밖 거부 · `Cache-Control: no-store` | `uv run pytest -q tests/test_dashboard.py` |
| R5 lifespan | 기동: init_db → attach_model → start_ticker → (빈 DB 면 backfill.run) → watcher.start / 종료: stop + join. `AGENTDASH_NO_WATCH=1` 이면 끔. 가짜 원천(읽기 전용)에서 빈 DB 백필 → 감시기 실행 → 종료 후 스레드 멈춤 확인 | `test_dashboard.py::test_lifespan_*` · 서버 로그 "Application shutdown complete" |
| pytest 전체 | 198 passed | `uv run pytest -q` |
| make gate (dev2 DB) | PASS 18 · FAIL 0 · 미검증 4 (G-12 · G-18 브라우저/QA 몫 · G-21 · G-22) | `AGENTDASH_DB=data/agentdash-dev2.db make gate` |
| 실제 `~/.claude/settings.json` | 수정 시각 작업 전 1792131308 = 작업 후 1792131308 | `stat -f '%m %Sm' ~/.claude/settings.json` |

비고
- Cytoscape.js `3.30.2` (cdn.jsdelivr.net/npm 고정). 못 불러오면 화면에 이유를 적는다. cose-bilkent 대신 내장 `cose`(추가 CDN 0).
- 원본 보기는 요청마다 원천 `.jsonl` 을 `rb` 로 읽어 응답만 — 도구 입력은 경로 + description(없으면 command/prompt) 첫 줄 120 자, thinking · 도구 결과는 크기만.
- 같은 Chrome 탭 묶음을 다른 에이전트(개발1 추정)와 같이 써서 탭이 서로 옮겨 다녔다 — 내 탭을 따로 만들어 쟀다.

### 3 추가 요청
- **R7 → 아키텍트 (메모)**: `tests/test_routes.py::test_placeholder_names_owner` 를 고쳤다(D-01 이 placeholder 라는 단정 → 남은 placeholder 는 담당을 밝힌다 + D-01~03 은 placeholder 아님). `app/main.py` 에 R5 lifespan 을 넣었다.

## 5. 웨이브 D — QA1 결함 수정 (2026-10-17 17:35, 커밋 10cbd18 기준 · 커밋 안 함)

바꾼 파일: `scripts/hooks_install.py`(`_protected_settings` · `is_real_target` · `marked` · `main` 가드 순서) · `scripts/hook_send.sh`(주석) · `collect/hooks_rx.py`(`_host` · `filter_payload` · `target_of`) · `tools/check_hooks.py`(5 · 6 항목 · 정확 일치 셈) · `tools/gate.py`(G-15 행만 — `test_hooks_install.py` 추가) · `tests/test_hooks_install.py`(+8) · `tests/test_hooks_rx.py`(새, 3). 실패 테스트 먼저(빨강 8) → 고침 → 초록.

| 결함 | 고친 것 | 실측 | 검증 방법 |
|---|---|---|---|
| DEF-QA1-004 (중대) | `is_real_target` = 설정과 무관한 `Path.home()/.claude/settings.json` + 설정된 claude_home 의 것 **둘 다**, resolve(심볼릭 링크) 후 비교 + samefile. 실제 파일이면 pytest 중 무조건 거부(프롬프트 없음) · `--yes` 거부 · 둘 다 exit 2 | 가짜 home 켠 채 실제 경로 · `~/` 형 · tmp 링크(파일 · 상위 폴더) · `--uninstall` → 전부 2 · 쓰기 함수 · `input()` 함정 호출 0 · 실제 파일 mtime · sha 전후 같음. 옛 코드에선 함정 5 회 불림(= 썼을 것) | `tests/test_hooks_install.py::test_real_home_*` · `test_configured_*` · QA1 `hooks_fake.sh` F: True/True/True |
| DEF-QA1-005 (중대) | 식별 = 명령 문자열이 `bash '<저장소 절대경로>/scripts/hook_send.sh'` 와 **정확 일치** | 남의 `bash /other/project/hook_send.sh` 있는 가짜 settings: 덧붙임 9 · 제거 후 남의 항목 1 남음 · 원본 바이트 동일 (백업 없이 제거해도 JSON 동일). 남의 것만 9 개면 `--check` 0/9 | `test_other_projects_hook_send_is_not_mine` · `test_only_others_*` · QA1 D: 9 · 1 |
| DEF-QA1-007 (경미) | `tool_input.url` → 호스트만 `host` 로(포트 · 경로 · 쿼리 · 조각 버림), `target_of` 는 `host` | `https://h.example:8443/a/SECRET?token=SECRET#SECRET` → `h.example` · 필터 결과 · detail 에 표지 0 | `tests/test_hooks_rx.py` · QA1 `hook_payload.py` WebFetch 표지 False |
| check_hooks 보강 | 5) 실제 파일 가드(in-process, 쓰기 함수 함정 · 실제 파일 읽기만) 5 경우 6) 남의 같은 이름 훅 · 덧붙임은 정확 일치로 셈 | `G-15 PASS — 덧붙임 9 · 실제 파일 가드 5/5 거부 · 함정 0 · 남의 같은 이름 훅 덧붙임 9 · 남음 1 · 송신 0.01s` · 옛 설치 스크립트(10cbd18) 로 돌리면 FAIL 위반 9 | `uv run python src/agentdash/tools/check_hooks.py` |
| G-15 (gate) | 수단 = check_hooks + `test_hooks_install.py` | PASS (check_hooks ‖ 18 passed) | `make gate` |
| pytest 전체 | — | 209 passed | `uv run pytest -q` |
| make gate (기본 DB) | — | PASS 21 · FAIL 1 (G-12 QA2 상태 대조 — DEF-QA2-001~003, 이 웨이브 범위 밖) | `make gate` 17:35 |
| G-14 정적 | 바꾼 3 파일 | PASS 쓰기 호출 12 · 원천 경로 대상 0 | `check_readonly.py --scan …` |
| 실제 `~/.claude/settings.json` | — | mtime 1792131308 → 1792131308 · sha1 8641eb22e8f5… 전 = 후 · `~/.claude` 의 `bak-agentdash*` 0 | `stat -f %m` · `shasum` |

## 5. 웨이브 D — 상태 · 연결 결함 수정 (2026-10-17, DB `data/agentdash-dev2.db`)

바꾼 파일: `core/state.py` · `core/linker.py` · `tests/test_state.py`(+16 표 행 · DB 경로 4) · `tests/test_linker.py`(+7) · `decisions.md`(D-18 · D-19 새로). 다른 사람 파일 0. 각 결함은 QA2 재현 → 실패 테스트 → 수정 → 재현 순서.

| 결함 | 원인 | 수정 | 테스트 | 재현 (judge.py) |
|---|---|---|---|---|
| DEF-QA2-001 failed/killed 알림 → DONE | `build_ctx.return_error` 가 Agent tool_result `ok=0` 만 봄 | `linker.return_of(con, key)` 의 is_error(가장 늦은 반환이 failed/killed 알림) 를 R-08 에 씀 | `test_db_failed_notification_is_FAILED` | 전수 DONE→FAILED 12 → 0 · DB FAILED R-08 12 (D-01 "실패" = state FAILED 수) |
| DEF-QA2-002 다시 깨운 뒤 알림 못 이음 | `note_notification` 이 spawn tool_use id 로만 자식 찾음 | `Fact.task_id` · `<task-id>`(= agentId) 로 이음. 엣지는 더 늦은 알림만 시각 · 상태 갱신 (늦게 읽힌 옛 알림이 덮지 않게). `scan_projects` 도 같게 | `test_L07_rewake_notification_matched_by_task_id` · `…older_notification_does_not_overwrite_newer` · `…scan_rewake_by_task_id` · `facts_carry_task_id` | `A:adc075af…` STALE → DONE R-08 |
| DEF-QA2-003 마지막 활동 = tool_call 만 | `resolve_all` 이 `MAX(tool_call.at)` | `linker._activity` = tool_call + 반환 뒤 기록 꼬리(`src_file` 경로, `rb` 로 뒤에서부터, `is_activity` 줄만 · isMeta 제외 · 크기/mtime 캐시). 반환 뒤 기록이 없으면 파일을 안 연다. `post_hook` 이 resolve_all 로 ended_at 이 바뀐 자식도 다시 판정 → 반환 뒤 새 활동이면 RUNNING | `test_L07_incoming_message_after_handback_wakes_child` · `test_db_rewake_after_return_runs_again` · `test_is_activity_skips_meta_and_results` | `A:a3b3e327…` DONE → STALE R-11 |
| DEF-QA2-004 busy + 예약 미래 → STALE | spec R-03 은 idle 만 | **D-18 가설**: busy · 5 분 무기록 · 가장 늦은 tool_use 가 ScheduleWakeup · 깰 시각 미래 → SLEEPING R-03 (R-02b · D-14 보다 먼저, 훅 도구 실행 중보다는 뒤). ScheduleWakeup 이 가장 늦은 tool_use 일 때만 예약으로 봄(006 f) | 표 5 행 · `test_db_wakeup_must_be_last_assistant` | 오케스트레이터 `S:2bee9170…` SLEEPING R-03 (judge 는 spec 글자 STALE — 남은 1 건) |
| DEF-QA2-005 S1 있음 · pid 소멸 | spec 빈칸 | **D-19 가설**: pid 소멸 = S1 없음 → R-06/R-07 (구현 유지) + R-01 훅도 SessionEnd 만 | 표 4 행 | 실제 영향 0 (S1 3 개 pid 살아 있음) |
| DEF-QA2-006 빈 경계 | — | 90 · 300 초 정각(서브에이전트 R-12 · R-11, 세션 busy 300 초 R-02b) · STALE 자식만 남은 부모(R-05 · R-11) · DB 경로 FAILED · 예약 "마지막 assistant" | `test_rule_table` 3 행 · `test_db_stale_children_do_not_hold_parent` 외 | — |
| DEF-QA2-007 L-06 `S:` 비교 | `raw[2:]` 를 `"S:<id>"` 꼴 값과 비교 | `resolve_message(…, keys=)` — 접두 붙은 to 는 알려진 키 전체와 비교 (resolve_all 이 agent 키 전부 넘김) | `test_L06_session_prefixed_target` | — |

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| G-12 표본 30 (QA2 `sample.txt`) | 전 **오판 3** (DONE→FAILED 2 · STALE→DONE 1) → 후 **불일치 1** (`S:2bee9170…` SLEEPING(D-18) vs judge spec 글자 STALE) | 백필 → `uv run python -I outputs/qa2/judge.py outputs/qa2/sample.txt <out.json>` → judge 결과와 DB `agent.state` 대조(스크래치 `cmp.py`, 키 · 상태만) |
| 전수 대조 (WORKFLOW 노드 제외 325) | 전 **14** (DONE→FAILED 12 · STALE→DONE 1 · DONE→STALE 1) → 후 **1** (위와 같은 D-18 건) | 같은 방법, 키 목록 = `SELECT agent_key FROM agent WHERE kind!='WORKFLOW'` |
| 판정 분포 (후) | 세션 77: DONE R-07 73 · WAITING_INPUT R-05 2 · SLEEPING R-03 1 · STALE R-06 1 / 서브에이전트 242: DONE R-08 221 · FAILED R-08 12 · STALE R-11 7 · RUNNING R-09 2 / 워크플로 1 · 워크플로 에이전트 6 DONE | `SELECT kind,state,state_reason,COUNT(*) FROM agent GROUP BY 1,2,3` |
| G-06 | PASS — 원천 248/248 · DB 248/248 · 반환 분포 반환 233 · 미반환 9 | `uv run python src/agentdash/tools/check_link_rate.py --db data/agentdash-dev2.db` |
| G-09 · G-10 | test_state 55 passed · test_linker 24 passed | `uv run pytest -q tests/test_state.py tests/test_linker.py` |
| G-13 · G-14 | PASS — dev2 DB TEXT 352912 · 300 자 초과 0 / 정적 위반 0 · 읽기 전용 pytest 242 passed · 트리 변경 0 | `check_no_payload.py` · `check_readonly.py` |
| pytest 전체 | 242 passed | `uv run pytest -q` |

### 3 추가 요청 (웨이브 D)
- **R8 → 개발1**: L-07 "마지막 활동"(tool_use 를 낸 assistant 줄 · 들어온 메시지 user 줄, `linker.is_activity`) 시각을 ingest 가 남겨 주면 linker 가 원천 기록 꼬리를 다시 읽지 않아도 된다. 지금은 `linker._activity` 가 반환 뒤 기록이 있는 자식만 `src_file` 경로를 `rb` 로 뒤에서부터 읽는다(캐시). 열이 없으므로(스키마 = 아키텍트 · spec) 방법은 개발1 · 아키텍트 판단 — 없어도 동작한다.
- **R9 → 개발1 (메모)**: `model.add_edge` 는 기존 엣지에 더 이른 `label` 이 와도 덮는다(`COALESCE(?, label)`). handback 알림은 linker 가 직접 "더 늦은 것만" 갱신하게 바꿨다 — 다른 엣지 종류에도 같은 문제가 없는지 확인 부탁.

## 6. 웨이브 D2 (정리 담당 겸, 2026-10-17 17:58 · 커밋 안 함)
- **R8 → 받음**: `linker._activity` 가 원천 기록 꼬리를 다시 읽지 않는다 — max(tool_call 마지막, 반환 뒤 `last_event_at`), ingest 가 handback 뒤 꼬리를 뺀 마지막 기록을 남긴다(D-20). `record_activity_since` · `_record_path` · `_ACT_CACHE` 삭제. `state.build_ctx` 는 그대로(`return_of` 경유, 파일 안 엶). 테스트 `test_L07_incoming_message_after_handback_wakes_child`(파일 없이) · `test_L07_ingest_to_linker_rewake_end_to_end` 새로.
- **D-17 D-03 표기**: `templates/agent.html` 작업량 표 — `usage.own` · `usage.with_descendants` 의 `undercount` 가 참인 칸의 출력 토큰 · 추정 비용 옆에 `undercount_note`(「기록상 과소 (D-17)」, title 에 그 몫 출력). 숫자 그대로. 테스트 `tests/test_dashboard.py::test_d03_undercount_note_d17`(빨강 → 초록).
- judge.py 전수(재백필 기본 DB, WORKFLOW 제외 326): **불일치 1** = `S:2bee9170…` SLEEPING R-03 (D-18) vs spec 글자 STALE — 이전과 같음. pytest 266 passed.
