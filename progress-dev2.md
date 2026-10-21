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

### 2차-T 공표 (2026-10-21 · Task 3 · 4) — `agentdash.core.twin` · `GET /api/v1/twin` — **개발1 check_twin 은 이대로 쓴다**

```python
from agentdash.core import twin
twin.BOX_W = 208 · BOX_H = 92 · GAP_X = 56 · GAP_Y = 16 · LINE_HEAD = 36 · LINE_PAD = 16 · LINE_GAP = 24
twin.FOLD_AFTER_SEC = 1800 (T-05) · MACHINE_LIMIT = 300 (T-06) · NAME_MAX = 24 · INLET_NAME = "부모 미확인"
twin.TwinError = graph.GraphError                        # 잘못된 since → API 422 {"error"}
twin.build(con, *, since: str | None = None, project: str | None = None, now: datetime | None = None,
           limit: int = MACHINE_LIMIT) -> dict           # now 없으면 twin._now() (UTC). 설비마다 쿼리 안 함
twin.overlaps(resp) -> int      # 설비 상자(반입구 포함) 쌍 겹침 + 라인 상자 쌍 겹침. 닿기만 하면 0
twin.scope_count(resp) -> int   # Σ 칸 + Σ machine.folded + Σ inlet.folded + Σ line.hidden  (V-17: == resp["agents_in_scope"])
```

응답 (spec §8 키 그대로 + 덧붙인 키 ★):
```
{ generated_at: "YYYY-MM-DDTHH:MM:SS" (UTC),
  lines: [{ key: project_key, name: 라인 이름(project_label ≤ 60), live: 살아 있는 수(범위 안, 접힌 것 포함),
            counts: {STATE: n} (범위 안 전부), box: {x,y,w,h} 정수,
            machines: [{ key, kind, name(≤ 24), parent: agent.parent_key 그대로(다른 라인 · 범위 밖일 수 있음),
                         state, rule: state_reason, since: state_since | null, elapsed_s: max(0, now − since) | null,
                         tool, target: ok IS NULL 인 마지막 tool_call (at, tool_use_id 최대) | null,
                         out_total = totals.output_tokens, out_est_total = totals.output_est_total,
                         cost_est_usd = totals.cost_est_usd (자기 몫, 단가 없으면 null),
                         spark: usage.spark 30 칸, folded: 이 설비 안에 접힌 수(자손 포함), box: {x,y,w=BOX_W,h=BOX_H},
                         ★wake_at: SLEEPING 이면 마지막 state_log 근거의 ScheduleWakeup 시각 | null (웨이브 B, spec §7.4 「깰 시각」) }],
            pipes: [{ src, dst, kind: spawn|workflow|handback, at }]   # 같은 라인 안. src "U:<project_key>" = 반입구 → 자식
            ★inlet: { key: "U:<project_key>", name, folded, box } | null,
            ★folded_line: bool, ★hidden: n (접힌 라인이면 그 라인 범위 안 수, machines=[] · box.h = LINE_HEAD) }],
  links: [{ src, dst, ★kind: message|spawn|workflow|handback, count }]  # message 전부(같은 라인 · 다른 라인 · X:외부) + 라인 간 spawn/workflow/handback
  folded_lines: n, ★agents_in_scope: n, ★filters: {since, since_arg, project}, ★elapsed_ms: 계산 시간 }
```
- 좌표: 설비 x = LINE_PAD + 열 × (BOX_W + GAP_X), y = 라인 y + LINE_HEAD + 행 × (BOX_H + GAP_Y). 라인 h = LINE_HEAD + 행 수 × (BOX_H + GAP_Y) − GAP_Y + LINE_PAD, 다음 라인 y += h + LINE_GAP. 열 = `(box.x − LINE_PAD) // (BOX_W + GAP_X)`.
- 범위: 살아 있는 것 + `max(last_event_at, started_at) ≥ since`(기본 24h) · 프로젝트 = project_key 같음 또는 라인 이름에 포함 (D-02 와 같음). **조상은 끌어오지 않는다** — 부모가 범위 밖 · 다른 라인 · 순환이면 반입구 행(0 열) 옆 1 열에 뿌리로. 다른 라인 부모(범위 안)는 links `spawn` 만(반입구 배관 없음).
- T-05: DONE/FAILED · ended_at < now − 30 분 · **자손 전부 DONE/FAILED** 일 때만 접는다(살아 있는 자손을 숨기지 않는다 — 해석). 뿌리(세션)는 접지 않는다. 반입구 아래 뿌리는 반입구 `folded` 로.

### 2차-T 웨이브 D 공표 변경 (2026-10-21, spec v0.4.1) — **개발1 check_twin 은 아래를 따른다**
```python
twin.build(con, *, since=None, project=None, now=None, limit=MACHINE_LIMIT, width: int = 1400) -> dict
twin.GRID_WIDTH = 1400 · GRID_WIDTH_MAX = 100_000
twin.check_width(w) -> int          # 1~100000 정수(문자열 숫자 허용) 아니면 TwinError → API 422 {"error": "width …"}
twin.grid(sizes: list[(w, h)], width) -> (cols, [(x, y, 행 높이)])   # T-08
graph.project_names(rows: (project_key, project_path)…) -> {project_key: 라인 이름}   # D-28 — 트윈 · D-02 · D-01 프로젝트 목록 공용
graph.project_match(필터, project_key, 라인 이름) -> bool                              # 필터 = 라인 단위 (DEF-QA1-401)
```
- `GET /api/v1/twin?…&width=<px>` — 없으면 1400. 응답 ★`grid: {width, cols, rows}`.
- 좌표 (T-08): 라인마다 자기 원점에서 짠 뒤 격자로 옮긴다. 설비 x = **라인 box.x** + LINE_PAD + 열 × (BOX_W + GAP_X), y = 라인 box.y + LINE_HEAD + 행 × (BOX_H + GAP_Y). 열 = `(box.x − 라인 box.x − LINE_PAD) // (BOX_W + GAP_X)`. 라인 box.h = 그 격자 행의 최대 높이(접힌 라인도). 다음 열 x = 앞 열들 최대 너비 합 + 열 수 × LINE_GAP.
- 라인 이름 (D-28): 그 project_key 의 **DB 전체** 에이전트 project_path 중 가장 짧은 것(같으면 사전순)의 마지막 이름, 없으면 project_key — 범위 · 행 순서와 무관.
- 프로젝트 필터: project_key 같음 또는 **라인 이름**에 포함 → 그 라인 에이전트 전부(하위 폴더 cwd 포함). (전에는 에이전트마다 자기 폴더 이름으로 걸렀다.)
- 설비 ★`ended_ago_s` = now − ended_at (DONE · FAILED 만, 아니면 null) · ★`last_ago_s` = now − last_event_at · `elapsed_s` = now − state_since (지금 상태가 이어진 시간 — 백필 직후엔 백필 시각부터). 모두 미래면 0, 시각 없으면 null.
- 끝난 설비(DONE · FAILED) `tool` · `target` = null.

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

## 7. 2차-A 웨이브 A (2026-10-21, spec v0.3 · 계획 `docs/superpowers/plans/2026-10-20-agentdash-v2a.md` Task 9 · 10 · 11)

### Task 9 — D-13 · D-14 · D-18 · D-19 확정 반영 (커밋 `512b463`)
바꾼 파일: `core/state.py`(머리 주석 `[가설 …]` → `확정 spec v0.3 §4.2` + 세션 평가 순서, 규칙 코드 · 근거 문자열 그대로 — 근거에 `가설` 0) · `app/routers/agents.py`(`D18_NOTE` · `hypothesis_note` · `_last_evidence` · `hypothesis` 필드 3 곳 제거) · `templates/_d01_body.html` · `templates/agent.html`(`data-hypothesis` span 3 곳 제거) · `tests/test_dashboard.py`(옛 D-18 표시 테스트 3 → `test_no_hypothesis_label`) · `tests/test_state.py`(v0.3 순서 3 행).

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| 라벨 테스트 빨강 → 초록 | 구현 전 FAIL(`가설 D-18` 이 D-01 카드에) → 후 PASS. D-01 · `?part=body` · D-02 · D-03 HTML · `/api/v1/agents/{key}` · `/api/v1/agents` · `/api/v1/graph` 에 `가설 D-18` · `data-hypothesis` · `"hypothesis"` 0 | `uv run pytest -q tests/test_dashboard.py -k no_hypothesis` |
| v0.3 순서 표 | busy·5 분+·미래 Wakeup·자식 1 → SLEEPING R-03 · busy·5 분+·자식 STALE 만 → STALE R-02b · S1 있음·pid 소멸·5 분 안 → DONE R-07 (구현 변경 없이 통과 — 1차 웨이브 D 구현이 이미 v0.3 순서) | `uv run pytest -q tests/test_state.py` |
| G-23 | `G-23  결정 반영  PASS  확정 7/7 · D-08 출처 있음 · src/ 「가설 D-18」·D18_NOTE 0 곳` | `uv run python src/agentdash/tools/check_decisions.py` |

### Task 10 — WAITING 알림 (커밋 `67373bf`)
새 파일: `templates/_alerts.html` · `tests/test_alerts.py`(12). 서버 · base.html 변경 0 (Phase 0 `{% include "_alerts.html" ignore missing %}` 로 실림).
- 공표: `window.agentdashAlerts = {waiting: Set, seen: Set, states, leader, mode, ready, notified, skipped, events, perm(), enabled(), stream}` · localStorage `agentdash.alerts`(on|off) · `agentdash.seen`(최근 200 `key|since`) · BroadcastChannel `agentdash-alerts`(생존 신호 · `seen` 공유) · Notification `tag = key|since`.
- 리더 탭 = 먼저 잡은 탭. **Web Locks(`navigator.locks`, 잠금 이름 `agentdash-alerts`)가 있으면 그것**(탭이 닫히면 자동으로 다음 탭 — 숨은 탭 타이머 지연에 안 흔들림), 없으면 BroadcastChannel 생존 신호로 가장 먼저 열린 탭, 둘 다 없으면 그 탭. 계획의 「BroadcastChannel 로 먼저 잡은 탭」과 뜻은 같고 수단만 하나 더 — QA2 가 보는 값 `agentdashAlerts.mode` (`locks`|`channel`|`single`).
- `agent.state` 는 개발1 `model.set_state` 가 **DB 커밋 전에** 내보낸다 → 상세 저장값이 이벤트 상태와 다르면 250 ms 간격 4 번까지 다시 읽는다.
- 첫 로드 · SSE 재연결: `/api/v1/agents?state=WAITING_INPUT,WAITING_PERMISSION&limit=5000` 으로 배지만 채움(알림 0). `state.since` 가 화면을 연 시각보다 이르면 알리지 않고 seen 만.
- 각 화면이 SSE 연결을 하나 더 연다(D-01 · D-02 · D-03 은 자기 `openStream` 과 합쳐 탭당 2). 탭 3 개 넘게 열면 HTTP/1.1 호스트당 6 연결에 닿을 수 있다 — 웨이브 B(Task 13)에서 `openStream` 이 `agentdashAlerts.stream` 을 같이 쓰게 합칠 예정.

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| 정적 계약 | 12 passed — 화면 7 (D-01~D-07) 에 스크립트 1 회 · `</main>` 뒤 · `?part=body` 0 · 계약 문자열 · `fetch(` 대상 `/api/v1/` 만 · EventSource 1 (`/api/v1/stream?follow=1`) · 외부 URL 0 · alert/confirm/prompt 0 | `uv run pytest -q tests/test_alerts.py` |
| JS 문법 | OK | `node --check` (스크립트 부분만 스크래치로 빼서) |
| 수동 확인 (Chrome, 2026-10-21 10:00 KST) | 가짜 루트 서버 8097 (`data/fake-alerts/` · `data/agentdash-dev2-alerts.db`, 세션 2 · S1 busy · pid 살아 있는 `sleep`), 훅은 `curl POST /hooks/event`. Notification 은 실제 권한 창을 띄우지 않으려고 로드 뒤 `window.Notification` 을 기록용 가짜(permission granted)로 바꿔 셈 (아래 숫자) | 탭 A `/` · 탭 B `/graph` · `javascript_tool` 로 `agentdashAlerts` · `document.title` 읽음 |
| · 첫 로드 | 세션 1 이 이미 WAITING_INPUT 인 채 두 탭 열기 → 제목 `(1) …` 두 탭 · 알림 0 · 이벤트 0 | |
| · 전이 | 세션 2 `Notification permission_prompt` → 알림 **1** (리더 탭 A, 제목 「권한 대기」 · 본문 `alert-proj · alert-2` · tag `S:…0002|2026-10-21T01:00:19Z`) · 탭 B 0 · 두 탭 제목 `(2)` · 탭 B seen 에 같은 키(채널 공유) | |
| · 재전송 | 같은 훅 다시 POST → 서버 `changed:false` · SSE 이벤트 0 · 알림 추가 0 | |
| · 새로고침 | 탭 A 새로고침 → 알림 0 · 이벤트 0 · 배지 `(2)` · 리더가 탭 B 로 넘어감(`leader` A false · B true) | |
| · 두 탭 (리더 넘어간 뒤) | 세션 1 UserPromptSubmit → RUNNING → idle_prompt → 알림 **1** (탭 B 「입력 대기」 `alert-proj · alert-1`) · 탭 A 0 → 두 탭 합 1 | |
| · 권한 거부 | 리더 탭 B 에서 permission `denied` (가짜 `requestPermission` → denied) 후 버튼 → 「알림 불가 — 배지만」 · disabled. 세션 2 RUNNING → WAITING_PERMISSION → 알림 0 · 배지 `(1)`→`(2)` · 파비콘 점 있음 | |
| · 배지 꺼짐 | 둘 다 UserPromptSubmit → 제목 접두 없음 · waiting 0 | |
| · 콘솔 오류 | 두 탭 0 | `read_console_messages onlyErrors` |
| 정리 | 서버 · `sleep` 정지 (8097 LISTEN 0) · 탭 닫음 · `~/.claude/settings.json` mtime 1792131308 그대로 | `lsof -iTCP:8097` · `stat -f %m` |
| pytest 전체 | 340 passed · 1 xfailed (개발1 작업 중 파일 포함) | `uv run pytest -q` |

실제 브라우저 권한 창 · OS 알림 표시는 확인하지 않았다(대화상자 금지) — QA2 G-29 E2E 몫.

### Task 11 — D-01 예산 경고 띠 (커밋 `b3badcb`, 개발1 공표 `eea9f69` 뒤 시작)
바꾼 파일: `app/routers/pages.py`(`budget_band` — `budget.status` 의 warn · over 칸 전부를 「오늘 전체 85 %」 · 「alpha 이번 달 102 %」 꼴로, 색 = `budget.worst`) · `templates/_d01_body.html`(맨 위 `#budget-band`, `/?part=body` 에도 실림) · `tests/test_dashboard.py`(+2).
- 색: over `st-FAILED`(빨강) · warn **`st-WAITING_PERMISSION`(주황)** — spec §6.3 「0.8 부터 주황」 · §4.1 주황 = WAITING_PERMISSION. 개발1 공표의 「warn = st-WAITING_INPUT(주황) 계열」 은 노랑이라 spec 색을 따랐다.
- % 는 내림(99.9 % 를 100 % 로 보이지 않게). 칸 title 에 `$추정 / 한도 $` · 단가 없음 N 건. 문구 옆 `[추정] API 정가 환산`.
- `budget.load()` 가 `SettingsError` 면 띠에 「예산 설정 오류 — …」 (관제판은 200, 조용히 숨기지 않음).

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| 띠 테스트 빨강 → 초록 | 전부 unset → 띠 없음 · 일 한도 100 · 오늘 85 → 띠 · `/insights` · `85 %` · 주황 · 102 → `st-FAILED` `102 %` · 여러 칸(월 92 % warn + alpha 월 102 % over) → 빨강 · ok 만 → 없음 · 설정 오류 표시 | `uv run pytest -q tests/test_dashboard.py -k budget` (2 passed) |
| pytest 전체 | 362 passed · 1 failed (`tests/test_insights.py::test_trend_and_efficiency_api` — 개발1 Task 8 작업 중, 미커밋 파일) · 1 xfailed | `uv run pytest -q` |
| make gate (기본 DB) | PASS 24 · FAIL 4 · 미검증 2. FAIL = G-04 · G-07 (Phase 0 부터, D-22 개발1) · G-24 · G-27 (개발1). G-23 · G-26 · G-28 PASS · G-29 · G-30 미검증 (QA 표지) — G-01~G-22 판정은 Phase 0 와 같음(회귀 0) | `make gate` |

### 3 요청 (2차-A)
- **R-2A-dev2-1 → 개발1 (메모)**: `model.set_state` 가 `agent.state` 를 **커밋 전에** 내보낸다 — `_alerts.html` 이 상세를 250 ms × 4 회 다시 읽어 버틴다. 커밋 뒤로 미룰 수 있으면 좋다(필수 아님).
- **R-2A-dev2-2 → 개발1 (메모)**: 공표의 띠 warn 색 「st-WAITING_INPUT(주황)」 은 노랑 — D-01 은 spec 주황(`st-WAITING_PERMISSION`)을 썼다. D-07 게이지도 같은 색으로 맞추면 좋다.
- **R-2A-dev2-3 → 아키텍트 · QA2 (메모)**: 알림은 탭마다 SSE 를 하나 더 연다(D-01 · D-02 · D-03 은 탭당 2). HTTP/1.1 호스트당 6 연결 — 같은 화면 탭 3 개 넘게면 막힐 수 있음. 웨이브 B Task 13 에서 `openStream` 이 `agentdashAlerts.stream` 을 같이 쓰게 합친다.
- **R-2A-dev2-4 → QA2 (G-29)**: 리더 수단은 Web Locks(`agentdashAlerts.mode == "locks"`) 우선, 없으면 BroadcastChannel. E2E 는 `window.agentdashAlerts.{waiting, seen, leader, notified}` 를 읽으면 된다.

## 8. 2차-A 웨이브 B (2026-10-21, 계획 Task 13 · R-2A-1 · R-2A-dev2-3)

### R-2A-1 완료 (개발1 요청) — D-03 「추정 보정 (D-17)」
- `templates/agent.html`: 「기록상 과소 (D-17)」 매크로(`under` · `data-undercount`)를 지우고, 작업량 표 출력 · 비용 칸마다 기록 숫자 옆에 `[추정] 추정 보정 (D-17) <값>` (`usage.totals()` 의 `output_est_total` · `cost_est_usd` · `est_note`, 비용 NULL 이면 「단가 없음」). 자기 · 자손 포함 두 칸 모두, 늘 나란히 (spec §6.2 표기).
- D-03 은 이제 `undercount` · `undercount_note` · `undercount_output` 을 읽지 않는다 → **개발1 이 `totals()` 의 `undercount*` 키 · `LEGACY_UNDERCOUNT_NOTE` 를 지워도 된다** (`tests/test_usage.py:230~237` 은 개발1 소유 — 같이 정리).
- 테스트: `tests/test_dashboard.py::test_d03_undercount_note_d17` → `test_d03_estimate_note_d17` (A:kid output_est 4,321 · cost_est $0.25 → 칸별 표기 2 · 자손 포함 5,555 · $0.3750 · 「기록상 과소」 0). `uv run pytest -q tests/test_dashboard.py` 12 passed · 전체 370 passed · 1 xfailed.

### Task 13 — D-01 · D-02 · D-03 공통 틀 (spec v0.3 §7.3)
바꾼 파일: `templates/{dashboard,_d01_body,graph,agent,agent_raw,_alerts}.html` · 새 `templates/_live.html` (스크립트만 — 상태 이름 `state_ko|tojson` · `stColor`(토큰 `--st-<state>` 를 getComputedStyle) · `stateBadge` · `onThemeChange` · `copyText` · `openStream`) · **`templates/_dev2_style.html` 삭제** · `tests/test_alerts.py` (+1 · 화면별 EventSource 1 검사).
- 세 화면 모두 base 토큰 · 공통 클래스(`.card .grid .kpi .tbl .badge .st-<STATE> .chart`)로. 화면별 `<style>` 은 `{% block head %}` 의 배치만(개발1 insights 와 같은 방식) — hex 색 0, 색 · 간격 · 글꼴은 전부 `var(--…)`. 옛 `.pill` + 인라인 `--c:var(--st-X)` → `badge st-X`.
- D-01: 상태 KPI 카드(위 테두리 = 상태 색) · **살아 있는 상태 분포 막대(차트)** · 내 차례 표 · 살아 있는 에이전트 카드 · 오늘 KPI 2×2 · 상위 5 가로 막대 · 파싱 오류 · 최근 상태 변화. 데스크톱 2 열(2:1), 1000 px 아래 1 열.
- D-02: 필터 카드(보기 세그먼트 버튼 · 범례 = 상태 배지) · 구성도 카드 + 요약 패널 카드. **Cytoscape 스타일 = `buildStyle()` 가 토큰을 읽어 만든다**, 머리글 토글(data-theme MutationObserver) · 시스템 설정 변경 시 `cy.style(buildStyle())` 로 다시 칠함(`window.__graphThemeRedraws`).
- D-03: KPI 5 (출력 · 비용 = 기록 큰 숫자 + `[추정] 추정 보정 (D-17)` 작은 줄) · 정보 · 판정 · 작업량 표 · 시간대 막대 차트 · 자식 · 상태 이력 · 작성 파일 · 도구 타임라인 · 원본 보기. 좁은 폭에서 큰 표는 `.tbl.wide`(표 min-width 600) — 칸을 짓누르지 않고 표 안에서만 가로로 민다.

### R-2A-dev2-3 — SSE 탭당 1 연결
- `_alerts.html` 의 EventSource 하나에 `agentdashAlerts.subscribe(handlers, statusEl)` 를 더했다 (agent.state · agent.new · agent.usage · edge.new 를 구독자에게 나눠 줌, 상태 칸 「실시간: 연결됨 / 끊김 — 다시 연결 중」). 화면 스크립트는 `_live.html` 의 `openStream` 으로 붙는다 — `_alerts` 가 `</body>` 앞이라 먼저 부른 구독은 `window.agentdashStreamQueue` 에 있다가 붙는다. 처리기 오류는 상태 칸 · console.error 로 드러낸다(삼키지 않음). base.html 수정 불필요.

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| 화면 HTML 의 `new EventSource(` | 화면 7 모두 1 | `uv run pytest -q tests/test_alerts.py` (13 passed) |
| 실제 연결 수 | 탭 2 개(D-01 · D-02) 열린 상태 서버 ESTABLISHED 브라우저 연결 **2 = 탭당 1** (전: 탭당 2) · 각 탭 `subscribers()` 1 · D-03 탭도 1 | `lsof -nP -iTCP:8097 -sTCP:ESTABLISHED` · `agentdashAlerts.subscribers()` |
| 390 px 가로 스크롤 | D-01 · D-02 · D-03 × 밝은 · 다크 = 6/6 `scrollWidth == clientWidth` (375 = 390 − 세로 막대), 표 밖으로 넘친 요소 0 · 1400 px 도 6/6 | 같은 출처 iframe(폭 390 · 1400) 안 `documentElement.scrollWidth` — 창 크기 바꾸기가 듣지 않아 iframe 으로 잼 |
| 테마 전환 다시 그림 | D-02 밝은 → 토글 → `data-theme=dark` · `__graphThemeRedraws` +1 · `--st-running` `#34c06f` 로 다시 칠함 | Chrome `javascript_tool` |
| 대비 | 48 쌍 · 글자 최소 5.6:1 · 도형 3.3:1 | `uv run python src/agentdash/tools/check_contrast.py` |
| 스크린샷 (커밋 안 함, D-07) | `outputs/e2e/dev2-design/` 16 장 (d01 · d02 · d03 × light/dark × 390/1400) — 디자인 DB 는 `data/agentdash-v2a-verify.db` 복사본 + `AGENTDASH_NO_WATCH=1` (원천 안 읽음) | |

### 알림 회귀 (가짜 루트 `data/fake-alerts/` · DB `data/agentdash-dev2-alerts.db` 새로 · 8097 · 살아 있는 `sleep` pid · 훅 = `curl POST /hooks/event`, Notification 은 로드 뒤 기록용 가짜)
| 단계 | 결과 |
|---|---|
| 첫 로드 (세션 1 이미 WAITING_INPUT) | 탭 A `/` · 탭 B `/graph` 제목 `(1)` · 알림 0 · 이벤트 0 |
| 전이 (세션 2 permission_prompt) | 알림 **1** (리더 A 「권한 대기」 `alert-proj · alert-2`) · B 0 · 두 탭 `(2)` · D-01 피드에 같은 이벤트(공유 연결) |
| 재전송 | `changed:false` · 이벤트 0 · 알림 추가 0 |
| 새로고침 | A 새로고침 → 알림 0 · 이벤트 0 · 리더 B 로 넘어감 |
| 두 탭 | 세션 1 UserPromptSubmit → idle_prompt → B 알림 1 · A 0 (합 1) · A 피드 새 줄 2 |
| 콘솔 오류 | 두 탭 0 (D-03 탭 포함) |
| 정리 | 서버 · sleep 은 띄운 PID 만 kill · 8097 LISTEN 0 · 탭 닫음 · `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22e8f5` 그대로 |

| 회귀 | 실측 | 명령 |
|---|---|---|
| pytest 전체 | **371 passed · 1 failed** = `tests/test_design.py::test_no_dev_style_includes` **XPASS(strict) — 정상** (개발1 7639db1 · 개발2 모두 `_dev*_style` 0). 그것만 빼면 371 passed · 1 deselected | `uv run pytest -q` · `… --deselect tests/test_design.py::test_no_dev_style_includes` |
| make gate (기본 DB) | PASS 25 · FAIL 4 · 미검증 1 — FAIL = G-14 · G-30 (둘 다 위 XPASS: check_readonly 의 `pytest -x` · test_design) · G-24 · G-27 (기본 DB `output_est` 미채움 = D-24, 화면 무관) | `make gate` |
| make gate (새 DB) | **PASS 27 · FAIL 2 · 미검증 1** — FAIL = G-14 · G-30 (XPASS 만) · G-29 미검증(QA 표지) | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |

### 3 요청 (웨이브 B)
- **R-2B-dev2-1 → 아키텍트**: `tests/test_design.py::test_no_dev_style_includes` 의 **xfail 해제** (개발1 · 개발2 둘 다 `_dev*_style` include 0 — 지금 XPASS(strict) 로 G-14 · G-30 이 FAIL). 해제하면 base 의 1차 별칭(`--warn --card --soft --st-RUNNING …`)도 개발2 화면은 더 쓰지 않는다(D-01~D-03 은 새 토큰만).
- **R-2B-dev2-2 → 아키텍트 (선택)**: base.html 다크 블록에 `color-scheme: dark` (밝은 쪽 `light`) — 다크에서 표 · 피드 안 스크롤 막대와 select 가 밝게 그려진다(스크린샷 `d01-dark-390-table.jpg`). 화면에서 고칠 수 없는 브라우저 기본 부품이라 토큰 쪽 일.
- **R-2B-dev2-3 → QA2 (G-29 · G-30)**: 화면 스크립트는 `agentdashAlerts.subscribe` 로 SSE 를 같이 쓴다 — 탭당 연결 1 은 `agentdashAlerts.subscribers()` · 서버 ESTABLISHED 로 잴 수 있다. D-02 테마 전환 다시 그림 = `window.__graphThemeRedraws`.

## 9. 2차-T 웨이브 A (2026-10-21, spec v0.4 §5.4 · §8 · 계획 Task 3 · 4)

| 항목 | 실측 | 명령 |
|---|---|---|
| Task 3 `core/twin.py` (G-31) | `tests/test_twin.py` 20 passed — T-01~T-07 각 ≥ 1 (T-05 3 · T-04 2) · Review Focus 5 (`test_cross_line_parent` · `test_parent_cycle_terminates` · `test_root_never_folded` · `test_name_clip_24` · `test_elapsed_clamped`) · 설비 값 = `usage.totals` · `usage.spark`(개발1 실제, 5f916b1) · 합성 300 설비(라인 7 · 0~4 열) 겹침 0 · ≤ 300 ms | `uv run pytest -q tests/test_twin.py` |
| Task 4 `/api/v1/twin` | 4 passed — 빈 DB 200 (`_placeholder` 없음 · lines [] ) · build 와 같음 · 잘못된 since 422 · 모든 문자열 ≤ 300 | 같은 파일 |
| G-17 | PASS — 화면 7 + API 14 = 21 HTTP 200 · placeholder 0 | `uv run python src/agentdash/tools/check_routes.py` |
| pytest 전체 | **404 passed** | `uv run pytest -q` |
| 실제 DB (`data/agentdash-v2a-verify.db`, 읽기만, now = 실행 시각) | 24h: 라인 5 · 설비 11 · 접힘 10 · 접힌 라인 0 · 반입구 3 · 배관 10 · links 0 · 겹침 0 · 범위 21 = 칸+접힘 21 · **0.9 ms** / 7d: 라인 10 · 설비 23 · 접힘 32 · 겹침 0 · 55 = 55 · 1.0 ms / all: 라인 32 · 설비 83 · 접힘 239 · 접힌 라인 0 · links 4 · 겹침 0 · 322 = 322 · **3.4 ms** (3 회 중 최소) | scratchpad `twin_measure.py` — `twin.build` · `twin.overlaps` · `twin.scope_count` |
| 24h 반입구 3 의 원인 | 5 설비 전부 STALE 서브에이전트, 부모가 DONE 이고 24h 밖(10-12 · 10-09 · 09-29) — 부모 미확인(NULL) 0. `parent` 키에는 실제 부모가 남는다 | 같은 DB `SELECT kind,state,last_event_at FROM agent WHERE agent_key=<parent>` |

### 해석 (spec 에 없는 부분 — 바꾸려면 §3 로)
- **T-tw-1** 범위 밖 부모 → 반입구 아래 (조상 끌어오지 않음). V-17 「칸 + 접힘 = 범위 안 에이전트」 를 그대로 맞추려고. D-02 는 조상을 `ctx` 로 끌어온다 — 화면에서 반입구 이름이 「부모 미확인」 이라 범위 밖 부모와 구별이 안 됨 → Task 6 에서 `parent` 가 있으면 「부모 범위 밖」 으로 표기할 예정.
- **T-tw-2** T-05 는 자손 전부 끝났을 때만 접는다 (spec 「자손도 함께 접힌다」 를 살아 있는 자손까지 숨기지 않는 쪽으로).
- **T-tw-3** WORKFLOW 노드도 설비 한 칸 (묶음 틀은 Task 6 그리기 몫) · 미확인 반입구는 0 열 첫 반입구 행 (spec 표 「맨 오른쪽」 과 T-02 「반입구 아래 1 열」 중 T-02 를 따름).

### 3 요청 (2차-T)
- **R-2T-dev2-1 → 개발1 (check_twin)**: 위 §1 2차-T 공표를 쓴다 — 칸 + 접힘 = `twin.scope_count(resp)` 대 `resp["agents_in_scope"]` (독립으로 다시 세려면 범위 = 위 「범위」 정의) · 겹침 = `twin.overlaps` · 스파크 대조는 `machines[].spark`.
- **R-2T-dev2-2 → 아키텍트 / 사람 (확인)**: 해석 T-tw-1 · T-tw-3 (spec §5.4 표 「미확인 반입구 — 맨 오른쪽」 vs T-02) — 맞지 않으면 decisions.md 에 결정을 달아 주면 바꾼다.


## 10. 2차-T 웨이브 B — Task 6 D-01 공장 평면도 (2026-10-21, spec v0.4 §7 D-01 · §7.3 · §7.4)

바꾼 파일: `templates/{dashboard,_d01_body}.html` · 새 `templates/_twin.html` · `routers/pages.py` (title 「공장 평면도」 · 기간 · 프로젝트 옵션) · `core/twin.py` (★`wake_at`) · `tests/test_twin.py` (+1 `test_sleeping_wake_at`, 키 집합에 `wake_at`) · 새 `tests/test_twin_page.py` (11). **`tests/test_dashboard.py` 수정 없음** (12 passed 그대로).

화면: 공통 틀 안 2 열 격자 — 평면도 카드 7fr(≈ 70 %, 넓은 화면 sticky) · 패널 3fr, 1000 px 미만이면 평면도 → 패널 → 피드 1 열. 예산 띠는 맨 위 한 줄(없으면 행 자체 없음, `:has`).
- 평면도: 라인 = 둥근 구역 카드(머리 = 이름 · 「가동 n · 대기 n」, 접힌 라인은 점선 「접힘 (T-06) · 설비 n」) · 설비 = 머리띠 있는 상자(왼쪽 위 표시등 · 이름 24 자 clipPath · 오른쪽 위 「!」/경보 삼각형/z · 상태줄(상태 · 경과 또는 깰 시각) · 종류 · 지금 도구 · 30 분 스파크 + 지금 분당 `[추정]` · 누적(기록 · 추정 · 비용) · 아래 꼬리표 「+N 완료」 · 바닥 볼트) · 반입구 = 점선 상자(부모 범위 밖 n · 미확인 n) · 배관 = 굵은 관(외피 + 속관, 둥근 꺾임) 위 입자(자식 RUNNING) · 컨베이어(message) = 점선, 굵기 = 횟수 · 워크플로 묶음 틀 = 점선 테두리 · 바닥 점 격자. 색은 토큰만(`.st-<STATE>` 의 --c/--c-fg), hex · rgb 0.
- 좌표 = 응답 `box` 그대로 (T-07). 스크립트에 배치 상수 0 — 라인 머리 높이도 응답(첫 설비 y − 라인 y)에서 읽음.
- 상호작용: 누르기 = 패널 「선택한 설비」(빠른 요약 즉시 + `/api/v1/agents/{key}` 근거 · 부모 · 자식 · 자손 포함 작업량, 선택 중엔 살아 있는 에이전트 목록 숨김, 패널 15 초 갱신 뒤 다시 넣음) · 두 번 누르기 / Enter = D-03 · Space 선택 · Esc 해제 · Tab 순회(포커스 설비가 화면 밖이면 그쪽으로 이동, 250 ms 뒤 선택) · 버튼 − + 맞춤 · Ctrl(⌘)+휠 포인터 기준 확대 · 휠 = 평면도 안 위아래 이동(끝이면 페이지 스크롤) · 끌기 이동. 맞춤 = 다 넣었을 때 배율 < 0.55 면 폭 맞춤(≤ 1) 위에서부터.
- 숨김 표 `#twin-table` (`.sr-only` 감싼 div — 표를 직접 sr-only 로 하면 390 px 에서 가로 넘침 1067 px 였음, 고침).
- 실시간: `openStream` 공유(탭당 EventSource 1) — `agent.state` 즉시 다시 칠함(클래스 · 상태줄 · aria · 자식 배관 입자) · 평면도에 없는 키 → `soon()` 1 초 묶음 · `agent.new`/`edge.new` 1 초 묶음 + 흐름 1 회(관이 있으면 바로, 없으면 다시 받은 뒤) · `agent.usage` 5 초 묶음 · 경과 글자 5 초 · 60 초 다시 받기 · 숨은 탭 = `.paused`(입자 정지) · 테마 바뀜 = 다시 그림(`redraws` +1).
- E2E 전역: `window.agentdashTwin = {render, machineEl, redraws, flows, flowsReduced, flowMiss, appeared, renders, loads, lastPaintMs, stateLog, vb, scale, select, fit, reload}`.

| 항목 | 실측 | 방법 |
|---|---|---|
| 정적 계약 (G-35) | `tests/test_twin_page.py` 11 passed — 평면도 + 패널 항목 전부 · 예산 띠 맨 위 · 빈 DB · reduced-motion 블록(.lamp .beacon .alarm .flow .burst .appear animation:none + transition:none) · §7.4 움직임 문자열 · 토큰만 · 외부 스크립트 0 · EventSource 1 · 접근성(role · tabindex · aria-label · Enter · dblclick · sr-only) · 전역 API · 모르는 키 → soon() · 1 초 · 5 초 묶음 · 배치 상수 0 | `uv run pytest -q tests/test_twin_page.py` |
| G-34 회귀 | `tests/test_dashboard.py` 12 passed (수정 0) | `uv run pytest -q tests/test_dashboard.py` |
| pytest 전체 | **419 passed** | `uv run pytest -q` |
| 대비 | G-30 PASS 48 쌍 · 글자 최소 5.6:1 · 도형 3.3:1 | `uv run python src/agentdash/tools/check_contrast.py` |
| make gate | **PASS 31 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 4** — G-15 송신 미검증(8095 사용 중, 정상) · G-33 · G-34 · G-35 개발 테스트 PASS · QA 표지 대기 | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |

브라우저 (Chrome, 창 1400×653 고정 — 창 크기 조절 대신 같은 출처 iframe 390 / 1400):

| 측정 | 결과 |
|---|---|
| 실제 기록 복사 DB (`data/agentdash-dev2-twin.db` = verify DB `sqlite3 backup` 사본 · `AGENTDASH_NO_WATCH=1` · 8097) | 라인 5 · 설비 12 · 반입구 3 · 배관 12 (spawn 9 · handback 3) · 접힌 완료 10 · 계산 1.6 ms · 평면도 카드 936 px / main 1385 px (≈ 68 %) |
| 가로 스크롤 | 390 밝은 · 390 다크 · 1400 밝은 · 1400 다크 = 4/4 `scrollWidth == clientWidth` (375/375 · 1385/1385), 넘친 요소 0 (svg · 표 안 제외) |
| 테마 전환 | 토글 → `data-theme=dark` · `redraws` +1 · 상자 면 `--surface` 다크 값 · 표시등 `--st-running` 다크 값 |
| 가짜 루트 (`data/dev2-twin-fake/` · DB `data/agentdash-dev2-twin-fake.db` 새로 · 감시기 켬 · 살아 있는 `sleep` pid S1) | |
| spawn → 보이기 | 세션 기록 + 서브에이전트 2 파일 쓰기 → 두 설비 DOM 등장 **1.22 초** (세션 RUNNING 은 0.22 초) · 새 설비 나타남 2 · spawn 흐름 2 · 흐름 놓침 0 |
| 훅 → 표시등 | `POST /hooks/event` permission_prompt → `data-state=WAITING_PERMISSION` **23 ms** · 다시 칠하기 프레임 5.6 ms · 경광등 · 「!」 표시 |
| handback | task-notification completed 덧붙임 → 역흐름 1 회(250 ms 시점 burst 1 · flows 2→3) · worker 1 DONE **154 ms** · 흐림 opacity 0.5 · handback 배관 1 |
| 키보드 | 맞춤 버튼 → Tab → 세션 → 서브 1 → 서브 2 순 · 포커스 테두리 3.4 px · 포커스 250 ms 뒤 패널 요약 · Enter → `/agents/A%3Aa0000000000000001` (D-03) |
| reduced-motion (에뮬레이션 대신: 그 @media 블록 규칙을 조건 없이 주입 + `matchMedia` reduce 참) | 움직임 twin 애니메이션 5 → **0** · 전이 0 · 그 뒤 WAITING 경광등 · handback 도 0 (burst 요소 0 · flowsReduced 1) |
| 콘솔 오류 | 0 (새로고침 뒤 · 클릭 · 이벤트) |
| 숨은 탭 입자 멈춤 | 정적 계약만 (`visibilitychange` → `.paused` → `animation-play-state: paused`) — 확장 도구로 탭을 숨기지 못해 실측 못 함 |
| 정리 | 띄운 PID 만 kill (서버 2 · sleep 1) · 8097 LISTEN 0 · 탭 닫음 · `~/.claude/settings.json` mtime 1792131308 · sha1 `8641eb22e8f5` 그대로 |

스크린샷 (커밋 안 함): `outputs/e2e/dev2-twin/` 6 장 — real-light-1400 · real-dark-1400-selected · real-dark-1400-stale-inlet · real-dark-390-iframe · fake-dark-spawn-flow · fake-dark-waiting-handback-done-selected.

### 해석 · 남은 것
- 가짜 루트에서 세션 행은 S1(`sessions/<pid>.json`)만으로 먼저 생긴다(STALE) — 「새 세션 + 서브 2 → ≤ 5 초」 중 세션은 기록 쓰기 전부터 평면도에 있었다. 서브 2 는 1.22 초.
- 실제 24h 평면도는 라인이 세로로 쌓여(서버 배치) 넓은 화면에서 오른쪽이 빈다 — 배치는 T-04 대로 두고 브라우저에서 바꾸지 않았다(T-07).
- SLEEPING 깰 시각은 `wake_at`(state_log 근거) — 근거에 시각이 없으면 경과를 보인다.

### 3 요청 (웨이브 B)
- **R-2T-dev2-3 → 아키텍트**: `base.html` 머리글 링크 「D-01 관제판」 → 「D-01 공장 평면도」 (spec v0.4 D-01 이름, 화면 제목 · h1 은 바꿨음).
- **R-2T-dev2-4 → QA2 (G-33 · G-35)**: 측정 손잡이 = `window.agentdashTwin` (`machineEl` · `flows` · `flowsReduced` · `redraws` · `lastPaintMs` · `stateLog[{key,state,at}]`). 가짜 루트 도우미 꼴은 위 표(세션 jsonl + `subagents/agent-*.{meta.json,jsonl}` · 훅 curl · task-notification 덧붙임).
- **R-2T-dev2-5 → 개발1 (참고)**: twin 응답에 ★`wake_at` 이 늘었다 — check_twin 의 키 비교가 있으면 맞춰 달라 (지금 G-32 PASS).


## 11. 2차-T 웨이브 D — 결함 수정 (2026-10-21, spec v0.4.1 · D-28 · D-30)

| 결함 | 커밋 | 테스트 |
|---|---|---|
| DEF-QA1-402 · D-28 라인 이름 · T-07 행 순서 | `feea67e` | `test_twin.py::test_line_name_shortest_path` · `test_T07_row_order_independent` (agent · usage_event · tool_call · edge · state_log 를 rowid 역순으로 넣은 사본 — 기본 · all · project) · `test_graph.py::test_project_label_shortest_path_d28` |
| DEF-QA1-401 필터 = 라인 단위 | `fa337d3` | `test_project_filter_whole_line` (D-02 와 같은 집합) |
| DEF-QA1-403 빠진 테스트 | `c3043d9` | `test_T05_exactly_30m_stays` · `test_T05_failed_after_30m_folds` · `test_D25_parent_outside_24h` · `test_T06_after_T05` (+ T-07 은 feea67e) — 코드 변경 없이 통과(동작은 이미 맞음) |
| D-30 / DEF-QA2-402 T-08 격자 | `cae284e` · `734cf60` | `test_T08_grid_1400_two_or_more_cols` · `test_T08_narrow_one_col` · `test_T08_same_row_height` · `test_T08_column_width_is_widest_in_column` · `test_T08_300_no_overlap_fast[1·360·1400·4000]` · `test_T08_bad_width` · `test_twin_api_width` · `test_twin_page.py::test_grid_width_sent_and_resize_refetch` |
| DEF-QA2-401 경과 | `1caf4e1` | `test_elapsed_meaning_after_backfill` · `test_elapsed_text_by_state` |
| DEF-QA2-404 지금 도구 | `960f76b` · `734cf60` | `test_final_machine_has_no_current_tool` · `test_tool_line_ellipsis_and_final_empty` |
| DEF-QA2-403 두 번째 반환 역흐름 | `bc82a4e` | `test_done_transition_reverse_flow_once` (정적 계약 — 실제 흐름은 QA2 가짜 루트 재측정 필요) |

| 항목 | 실측 | 명령 |
|---|---|---|
| pytest 전체 | **443 passed** | `uv run pytest -q` |
| check_twin (24h · all) | PASS 설비 11 · 라인 6 · 범위 26=26=26 · 겹침 0 · 1.7 ms / all 설비 83 · 라인 32 · 327=327=327 · 4.6 ms | `AGENTDASH_DB=data/agentdash-v2a-verify.db uv run python src/agentdash/tools/check_twin.py [--since all]` |
| 대비 | G-30 PASS 48 쌍 · 글자 5.6:1 · 도형 3.3:1 | `check_contrast.py` |
| make gate | **PASS 34 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 1** (G-15 송신 — 8095 사람 서버) | `AGENTDASH_DB=data/agentdash-v2a-verify.db make gate` |
| 브라우저 (8097, verify DB 백업 사본 `data/agentdash-dev2-twin-d.db` · 감시기 끔) | 창 안쪽 1352 px · 카드 866 px → width 1083 · **cols 2 · rows 3** · 맞춤 배율 0.73 · 첫 화면 라인 4 (온전히 2) · 가로 스크롤 0 · 두 테마 / 390 px iframe: wrap 307 → width 384 · cols 1 · 375/375 · 두 테마 / iframe 390→1100 px: 1 초 뒤 다시 받기 1 회 · 콘솔 오류 0 | 스크린샷 `outputs/e2e/dev2-twin-d/` 5 장 (커밋 안 함) |
| 실제 라인 이름 (24h) | Multi-agent Dashboard · lcomFine MES · Standard ML Platform · Standard MES Platform · **SongWol QR Platform** (전 「contracts」) · 00 PM Agent | `/api/v1/twin` |
| 경과 (백필 사본) | 끝남 「28분 전」 · 멈춤 의심 「기록 6일 11시간 전」 · 「기록 8일 12시간 전」 … 서로 다름 · ended_at 없는 DONE 세션 1 은 상태 지속 「15분」 | 같은 화면 |
| 정리 | 띄운 PID 만 kill (uv 30275 · python 30277) · 8097 LISTEN 0 · 8095 (사람) 그대로 · 탭 닫음 | `lsof -iTCP:8097` |

### 해석 (사람 확인 — decisions.md D-31)
- 화면이 보내는 width = 평면도 카드 실제 너비 ÷ 0.8. 카드 실제 px 그대로면 1400 px 창(카드 ≈ 866 px)에서 504 px 라인 2 개(1032)가 안 들어가 1 열 → QA2-402 가 그대로. 0.8 = 맞춤이 폭 맞춤으로 떨어질 때의 배율 하한(글자 12 px → 9.6 px).
- 멈춤 의심(STALE)은 「기록 n 전」(last_ago_s) — 상태 지속(state_since)은 백필 직후 전부 같은 값이라. 그 밖 살아 있는 설비는 state_since.
- ended_at 이 없는 DONE 은 「끝남 · 상태 지속」 (지어내지 않음).

### 3 요청 (웨이브 D)
- **R-2T-dev2-6 → 개발1 (check_twin)**: `direct_scope` 의 프로젝트 필터가 에이전트마다 `project_label(pk, pp)` 로 거른다 — 트윈은 이제 라인 단위(`graph.project_names` + `graph.project_match`). `--project` 를 줄 때만 범위 수가 어긋난다(기본 · `--since all` 은 PASS). 바꾸지 않았다.
- **R-2T-dev2-7 → QA1 · QA2 재검증**: DEF-QA1-401~403 · DEF-QA2-401~404. QA2 는 가짜 루트에서 「다시 깨운 서브에이전트의 두 번째 반환」 역흐름 1 회(+ 첫 반환 중복 0)를 실측해 달라 — 이번엔 정적 계약만.
