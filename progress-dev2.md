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
def resolve_message(sender_key, to, *, agent_ids: set, names: {name: key}, at=None) -> Edge   # L-06, 못 맞추면 X:<to>
def returned(signals: [ReturnSignal], last_activity_at) -> Return | None           # L-07 (D-04 대안 규칙)
def spawn_edge(child_key, link) / handback_edge(child_key, parent_key, ret) -> Edge | None
def facts(line: dict) -> [Fact]      # 줄 하나 → agent_call · workflow_call · send_message · handback_call · notification · agent_error · agent_message
def is_activity(line: dict) -> bool  # L-07 다시 깨어남 판정용
def session_key / agent_key / workflow_key / unresolved_key("U:<proj>") / external_key("X:<name>")
# DB
def on_line(con, author_key, line: dict) -> int    # ingest 가 assistant/user 줄마다 부른다 — task-notification · Workflow runId 를 남김
def note_notification(con, author_key, tool_use_id, status, at) -> bool
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
