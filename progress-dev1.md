# progress-dev1.md — 개발1 (수집 · 숫자)

> 실측값 + 검증 명령만. 본문은 붙여 넣지 않는다(숫자 · 경로만).

## 1. 공표 — 공용 시그니처 (개발2 는 이대로 쓴다. 바꿀 일이 있으면 progress-dev2.md §3 에 요청)

모든 쓰기 함수는 `con: sqlite3.Connection` 을 첫 인자로 받고 **커밋하지 않는다**(호출한 쪽이 `con.commit()`).
문자열은 전부 `model.clip()`(≤ 300 자, 설명류는 ≤ 120 자)을 거쳐 들어간다 — V-04.

### `agentdash.core.model`

```python
STATE_UNSET = "UNKNOWN"           # 판정 전 agent.state (NOT NULL 칸). state.evaluate 가 덮어쓴다. state_reason = "unevaluated"
KINDS = ("SESSION", "SUBAGENT", "WORKFLOW_AGENT", "WORKFLOW")

def key_session(session_id) -> "S:<sessionId>"; def key_agent(agent_id) -> "A:<agentId>"; def key_workflow(wf_id) -> "W:<wfId>"
def clip(s, n=300) -> str | None

@dataclass
class AgentExtra:                 # 메타의 연결 단서 — agent 테이블 열이 없어 DB 에 저장하지 않는다. load_extra() 로 다시 읽는다
    agent_id: str | None          # S3/S5 agentId
    tool_use_id: str | None       # S4 toolUseId (= agent.spawn_tool_use)
    parent_agent_id: str | None   # S4 parentAgentId (포크 · 손자, D-10)
    is_fork: bool                 # S4 isFork
    workflow_phase: str | None    # S5 workflowPhase (≤120)
    wf_id: str | None             # 경로 subagents/workflows/wf_<id>/ 의 "wf_<id>" (워크플로 에이전트), S6 runId (워크플로 노드)
    spawn_depth: int | None
    meta_model: str | None        # S4 model ("inherit" 등)
    jsonl_path: str | None        # 원천 경로 (읽기만)
    meta_path: str | None

@dataclass
class Agent:                      # agent 테이블 한 행. None 인 칸은 upsert 때 기존 값을 지우지 않는다
    agent_key: str; kind: str; project_key: str; session_id: str
    project_path=None; parent_key=None; spawn_tool_use=None; depth: int = 0; agent_type=None; name=None
    request_shape=None; model=None; cc_version=None; git_branch=None
    started_at=None; last_event_at=None; ended_at=None
    state=None; state_reason=None; state_since=None; pid=None
    extra: AgentExtra | None = None   # DB 저장 안 함

@dataclass
class UsageEvent:  agent_key, request_id, at, model, speed, input_tokens, cache_read, cache_write_5m, cache_write_1h,
                   output_tokens, thinking_tokens, web_search, web_fetch, cost_usd=None, pricing_ver=None
@dataclass
class ToolCall:    agent_key, tool_use_id, at, tool, target=None, ok=None, result_at=None
@dataclass
class FileTouch:   agent_key, path, op, at

def ensure_indexes(con) -> None                                  # 인덱스만 (테이블은 schema.sql 11 그대로)
def upsert_agent(con, a: Agent) -> bool                          # 새 행이면 True. started_at=MIN · last_event_at=MAX · 나머지 None 은 유지
                                                                 #   parent_key · state* · ended_at 은 None 이면 절대 덮지 않는다
def get_agent(con, agent_key) -> Agent | None
def list_agents(con, *, kind=None, session_id=None) -> list[Agent]
def set_parent(con, agent_key, parent_key: str | None, spawn_tool_use=None) -> bool      # linker 용. 바뀌면 True
def set_state(con, agent_key, state, reason, at) -> bool         # 바뀌면 agent.state/state_reason/state_since + state_log 1 행, True
def set_ended(con, agent_key, ended_at) -> None
def add_edge(con, src_key, dst_key, kind, at, label=None) -> bool   # 새 엣지면 True, 있으면 count += 1 · at=MAX
def add_usage(con, ev: UsageEvent) -> bool                       # PK(agent_key, request_id). 같은 requestId 가 다시 오면 output_tokens 큰 쪽(스트리밍 최종본)으로 교체 (D-01)
def add_tool_call(con, tc: ToolCall) -> bool                     # PK tool_use_id, 있으면 무시
def set_tool_result(con, tool_use_id, ok: bool | None, result_at, target=None) -> bool   # target: Workflow 결과 runId "wf_…"
def add_file_touch(con, ft: FileTouch) -> bool
def add_parse_error(con, path, line_no, reason) -> None
def add_hook_event(con, agent_key, at, event, detail) -> None    # detail clip 300 — hooks_rx 용
def load_extra(con, agent_key) -> AgentExtra | None              # src_file 에서 meta 경로를 찾아 원천을 다시 읽는다 (읽기만)
def on_change(fn: Callable[[str, dict], None]) -> None           # SSE 용 구독. 이벤트: "agent.new" {agent_key, kind}
                                                                 #   "agent.usage" {agent_key} · "edge.new" {src,dst,kind} · "agent.state" {agent_key,state,reason}
def off_change(fn) -> None
```

### `agentdash.collect`

```python
# tail.py — 증분 읽기 (spec §2.2, G-03)
@dataclass class Chunk: path, inode, size, mtime, start_offset, end_offset, start_line, lines: list[bytes], reset: bool
def read_new(con, path) -> Chunk          # src_file 의 offset 부터, 개행으로 끝난 줄만. inode 변경 · size<offset → 처음부터(reset=True)
def commit(con, chunk) -> None            # 처리 성공 뒤 src_file 갱신 (실패하면 부르지 않음 → 다음 회차 재시도)

# parsers/session_file.py (S1)   parse(path) -> SessionFile(pid, session_id, cwd, status, updated_at, status_updated_at,
#                                  started_at, name, kind, entrypoint, version)  · scan() -> dict[session_id, SessionFile]
# parsers/transcript.py (S2/S3/S5) parse_line(raw: bytes) -> Record | None   (None = 세지 않는 줄 종류, D-11)
#                                  필수 필드 없으면 LineError(reason) → parse_error
# parsers/meta.py (S4/S5 meta)    parse(path) -> Meta   · parsers/workflow.py (S6 + journal) parse(path) -> Workflow · parse_journal(path) -> {agentId: label}

# ingest.py
def classify(path) -> str | None          # "S1" | "S2" | "S3" | "S4" | "S5" | "S5meta" | "S5journal" | "S6" | None
def ingest_path(con, path) -> set[str]    # 그 파일을 읽어 DB 에 쓰고, 바뀐 agent_key 집합을 돌려준다
def ingest_all(con, *, since=None) -> Report   # 전체 스캔 (백필 · 60 초 재스캔)
def add_post_hook(fn: Callable[[sqlite3.Connection, set[str]], None])   # 수집 뒤 부를 함수 (linker · state 가 등록)
# 줄마다: agentdash.core.linker.on_line(con, author_key, line_dict) 가 있으면 assistant/user 줄(포크 사본 제외)마다 부른다 (dev2 R1)
# 순서: S4/S5meta → S6 → S2 → journal → S3/S5 → S1 (자식 행이 먼저 있어야 task-notification 이 바로 붙는다)
# Workflow tool_call.target = 결과 줄 toolUseResult.runId ("wf_…") — L-03 단서

# watcher.py — 감시 (spec §2.2)
def run(stop_event, db_path=None, on_batch=None) -> None   # watchfiles 1 초 묶음 + 60 초 재스캔, 묶음마다 ingest → post hook → commit → on_batch(keys)
def start(db_path=None, on_batch=None) -> (Thread, Event)

# backfill.py — `make backfill`
def run(db_path=None, since=None) -> Report   # init_db · ingest_all · usage.rebuild_daily · 커밋.
    # agentdash.core.linker 에 resolve_all(con) 이, agentdash.core.state 에 evaluate_all(con, now) 가 있으면 끝에 부른다
```

### `agentdash.core.usage`

```python
def load_pricing() -> Pricing                         # config/pricing.yaml
def cost(ev: UsageEvent, pricing) -> tuple[float | None, str]   # (cost_usd | None, pricing_ver). 모르는 모델 · 단가 없는 fast → None
def totals(con, agent_key, *, descendants=False) -> dict   # {input_tokens, cache_read, cache_write, output_tokens, thinking_tokens,
                                                           #  cost_usd, unpriced, requests} — <synthetic> 제외
def descendants(con, agent_key) -> list[str]          # spawn/workflow 엣지 → parent_key → 메타(parentAgentId · 같은 세션 폴더) 순
def rebuild_daily(con, agent_keys=None) -> int         # usage_daily (KST) 다시 만들기
def active_seconds(timestamps, gap_sec=300) -> int     # D-06
def reprice(con) -> dict                               # 전 기간 cost 재계산 + usage_daily 재생성
def unpriced_models(con) -> list[tuple[model, n]]
```

### 웨이브 B 공표 (2026-10-17)

```python
# agentdash.core.pipeline (spec §7.1)
evaluate(con=None, now=None, root=None) -> Result   # 원천 읽기만. Result.cells: [Cell(company, stage, status, base_status, rule, base_rule,
                                                    #   have, need, version, run_id, last_file_at, last_session, lag, lag_note, note, src,
                                                    #   files, progress, missing, wave)] · .unregistered · .next_stage() · .as_dict()
refresh(con, now=None) -> Result                    # evaluate + pipeline_cell 통째 교체 (커밋 안 함)
cached(con, max_age=None) -> Result                 # API 용 — 원천 signature 변경 또는 pipeline_tick_sec(300 s) 경과 때만 refresh + commit
load_dictionary().lookup(slot) / .find_in(text)     # 회사 이름 정규화(NFC · 공백 · 주식회사 · (주)) — 개발2 가 회사 이름을 찾을 때 그대로 쓴다
# agentdash.core.usage (D-04)
table(con, frm=None, to=None, group="agent"|"project"|"type"|"model"|"day") -> dict   # rows · total · trend · unpriced · estimate_label
to_csv(table) -> str ;  ESTIMATE_LABEL = "[추정] API 정가 환산"
# agentdash.collect.ingest — R3
ingest_all(con, *, since=None, run_hooks=True, link=True)   # link 이고 state.post_hook 미등록이면 끝에 state.post_hook(=linker.resolve_all + 바뀐 키 판정)
```

- **공용 템플릿 블록**: `app/templates/base.html` 에 `{% block head %}{% endblock %}` 하나만 더했다(`</head>` 바로 앞). 화면별 `<style>` · `<script>` 를 여기 넣는다 — 개발2 도 그대로 쓰면 된다(지금 개발2 는 body 안 include 를 쓴다, 바꿀 필요 없음). 그 밖의 base.html 은 그대로.
- 개발1 화면 전용: `templates/{usage,timeline,pipeline}.html` · `templates/_dev1_style.html`(상태 색 `--st-*` 는 `_dev2_style.html` 과 같은 값) · `app/routers/_svg.py`(서버 SVG 막대 · 면적).
- API: `GET /api/v1/usage?from=&to=&group=&format=csv` (format=csv 는 화면 「CSV 내보내기」) · `GET /api/v1/timeline?from=&to=` (lanes[segments] · concurrency) · `GET /api/v1/pipeline` (stages · companies · cells · next_stage · unregistered · counts).

## 2. 진행 — 웨이브 A 실측 (2026-10-17 16:38, DB `data/agentdash-dev1.db`)

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| G-02 파서 회귀 | PASS — 29 passed (S1 · S2/S3/S5 픽스처 12 파일 전 줄 · S4 깊이 1/2(포크) · S5 meta 6 · S6 · journal · 깨진 줄/필수 필드 없음 → parse_error · 본문 안 꺼냄) | `uv run pytest -q tests/test_parsers.py` |
| G-03 증분 읽기 | PASS — 9 passed (추가분만 · 반쪽 줄 다음 회차 · inode 변경 · 크기 감소 · commit 안 하면 재시도 · 재시작 뒤 줄 번호 · 읽기 전용 가짜 원천) | `uv run pytest -q tests/test_tail.py` |
| G-04 전체 수집 (V-01) | PASS — 세션 77/77 · 서브에이전트 235/235 · 워크플로 에이전트 6/6 (키 집합 동일, 빠짐 0 · 남음 0), 워크플로 노드 1/1 | `AGENTDASH_DB=data/agentdash-dev1.db uv run python src/agentdash/tools/check_counts.py` (증분 수집 직후 같은 시각에 셈) |
| G-05 파싱 오류율 (V-07) | PASS — 오류 0 / 줄 160,438 = 0.0000% · 파일 564 | `… check_parse_errors.py` |
| G-07 토큰 합 (V-03) | PASS — 표본 10 세션(에이전트 많은 5 + 시드 무작위 5, 워크플로 · 포크 세션 포함) 입력 · 캐시 읽기 · 캐시 쓰기 · 출력 4 칸 전부 원천 직접 합 = DB, 자기+자손 = 세션 합계, 세션 안 requestId 중복 0. 중복 제거로 뺀 출력 7,628,314 | `… check_usage_sum.py` |
| G-08 비용 (V-09) | PASS — 표본 20 건(1h 3 · 5m 3 · speed 없음 2 · 모델 5 종 각 1 · 무작위) 손계산 = DB 20/20 (차이 ≤ 1e-12), 단가 없는 모델 0 종 · 비용 NULL 0 행. 기록에 `speed=fast` 0 건 → fast · Haiku 구간 · NULL 경계는 `tests/test_cost.py` 13 passed | `… check_cost.py` · `uv run pytest -q tests/test_cost.py` |
| 백필 | 3.9 s (수집 3.5 s) · 원천 파일 564 (S1 3 · S2 77 · S3 235 · S4 235 · S5 6 · S5meta 6 · journal 1 · S6 1) · agent 319 (SESSION 77 · SUBAGENT 235 · WORKFLOW_AGENT 6 · WORKFLOW 1) · usage_event 26,997 · tool_call 30,547 · file_touch 2,442 · usage_daily 363 · parse_error 0 · edge spawn 236 · workflow 6 · handback 227 · message 55 (linker · state 는 개발2) | `rm data/agentdash-dev1.db*; AGENTDASH_DB=data/agentdash-dev1.db make backfill` |
| 백필이 원천을 바꾸지 않음 | `~/.claude/{projects,sessions}` 파일 1,157 개 (경로 · 크기 · mtime · inode) 백필 전후 변경 0 · 새 파일 0 · 사라진 파일 0 | 스크래치 `snap.py` 전후 비교 (읽기만) + `uv run python src/agentdash/tools/check_readonly.py` → G-14 정적 PASS · 읽기 전용 pytest 161 passed · 트리 변경 0 |
| pricing-check | 단가표 2026-10-06 · 기록 모델 5 · 단가 없는 모델 0 종 | `AGENTDASH_DB=data/agentdash-dev1.db make pricing-check` |
| reprice | 행 26,959 · 바뀐 행 0 · NULL 0 · 합계 usage_event $4,470.0794 = usage_daily $4,470.0794 (추정 API 정가 환산) | `AGENTDASH_DB=data/agentdash-dev1.db make reprice` · `tests/test_backfill.py::test_reprice_keeps_totals` |
| 감시기 | 가짜 루트에 새 세션 파일 → 5 초 안에 agent 행 (실측 < 1 초) | `tests/test_backfill.py::test_watcher_picks_up_new_session` |
| pytest 전체 | 161 passed | `uv run pytest -q` |
| make gate | PASS 16 · FAIL 3 (G-18 개발2 · G-19 · G-20 개발1 웨이브 B) · 미검증 3 (QA) — 웨이브 A G-02~G-08 전부 PASS | `AGENTDASH_DB=data/agentdash-dev1.db make gate` |

### 가설 확인 결과 (decisions.md)

| D | 결과 | 근거 (숫자만) |
|---|---|---|
| D-01 requestId 중복 | **확정** — (agent, requestId) 한 행 · output 최대(스트리밍 최종본) | 같은 파일 안 재등장 27,540 줄 · usage 다른 묶음 2,242 전부 output 단조 증가 |
| D-02 자식이 부모를 다시 적나 | **가설 반박** — 포크 26 개 전부 부모 줄 사본(1,142 줄) + 띄운 호출 재기록(새 uuid · 같은 requestId) → 사본 제외 규칙 | 파일 걸친 requestId 137 개 전부 포크 관련, 제외 후 두 에이전트 걸친 requestId 0 |
| D-03 thinking ⊂ output | **확정** | thinking 있는 22,888 줄 중 thinking > output 0 |
| D-06 active 5 분 | **확정**(분포 근거) | 간격 87,655 중 ≤ 5 분 99.16% · 4~7 분 0.29% |
| D-11 assistant 줄만 | **확정** | blob 안 tool_use 121 개 전부 assistant 에도 있음 · 깨진 줄 0 |
| D-13 (새) 세션 이름 | 가설 — 첫 사용자 메시지(본문) 대신 `agent-name` 줄 | `agent-name` 1,078 줄 |

### 참고
- `make gate` 기본 DB 는 `data/agentdash.db`(빈 DB) — 웨이브 A 수치 게이트는 `AGENTDASH_DB=data/agentdash-dev1.db make gate` 또는 기본 DB 에 `make backfill` 뒤 잰다.
- check_counts · check_usage_sum 은 같은 시각 비교를 위해 먼저 증분 수집(DB 에만 씀)을 한 번 돈다 (`--no-sync` 로 끔).

## 2B. 진행 — 웨이브 B 실측 (2026-10-17 16:59, DB `data/agentdash-dev1.db` · 원천 `~/Desktop/AI Coding` 읽기만)

| 항목 | 실측 | 검증 방법 |
|---|---|---|
| G-19 진척 판정 | **PASS** — 칸 88/88 · 근거(src) 없는 칸 0 · 표본 10 칸 have/need = `find` 독립 재계산 10/10 (시드 11 · 1 · 2 · 3 모두 일치) · 고려솔더 01 `DONE` v1.0 `20261016-151506-all` · 02 `DONE` v1.0 `20261016-154028-all` · 05 · 08 `UNKNOWN` · `tests/test_pipeline.py` 16 passed (P-01~P-07 각 ≥ 1 · 정규화 · NFD · 미등록 · 제외 폴더 · 최고 버전 · run.json 회사 · 뒤처짐 · 저장 ≤ 300 자 · 읽기 전용 원천) | `AGENTDASH_DB=data/agentdash-dev1.db uv run python src/agentdash/tools/check_pipeline.py [--seed N]` · `uv run pytest -q tests/test_pipeline.py` |
| G-20 비용 화면 | **PASS** — D-04 카드 · 추이 · 표 머리 · CSV 머리에 `[추정] API 정가 환산` · 「단가 없음 N 건」(모델별) · reprice 뒤 화면 합계 = usage_event 합 = usage_daily 합 (묶음 5 종 모두) · `make reprice` CLI 합계 = 화면 합계 · KST 일자 경계 · 빈 DB 200 — 7 passed | `uv run pytest -q tests/test_usage_page.py` |
| 실제 파이프라인 표 | 11 개사 × 8 단계 = 88 칸: DONE 53 · NEEDS_DECISION 2 (기저 DONE) · UNKNOWN 33 · PARTIAL 0 · NOT_STARTED 0 · IN_PROGRESS 0. 단계별 01 DONE 11 · 02 DONE 9 + 판단 필요 2(니즈푸드 progress.md:946 · 임진강김치 :913 · :921) · 03 DONE 11 (↻ 7) · 04 DONE 11 (↻ 2: 고려솔더 · 송월타월서울상사) · 00 DONE 11 · 05 · 06 · 08 UNKNOWN 각 11 (06 고려솔더 칸에 웨이브 Phase 0 ✅ · A ✅ · B 🔄 · C ✅ · D ✅). 미등록 회사 0 건(이름 없음). UNKNOWN 칸 33. 마지막 손댄 에이전트: 88 칸 모두 「대시보드 수집 이전」(산출물이 Write/Edit 가 아니라 스크립트로 만들어져 file_touch 에 없음) | `AGENTDASH_DB=data/agentdash-dev1.db uv run python -m agentdash.core.pipeline` |
| D-15 (새) 패턴 차이 | 가설 — 실제에 맞춰 config 로: `{사업}` = 제조AI · 스마트공장(니즈푸드 · 임진강김치), NFD 파일 이름 NFC 비교, run.json 회사 키 = facts, 산출물별 `match`, upstream, 미등록은 파일 · 폴더 · run.json 자리만, P-01 글자 그대로, 06 wave_company. NFC 없으면 경동 00 · 니즈푸드 04 PARTIAL 오판 + 미등록 1 이었음 | `decisions.md` D-15 |
| D-16 (새) 간트 | 가설 — state_log 첫 기록 앞 구간 = 「판정 기록 없음」, 막대 끝 4 px = 지금 상태 | `tests/test_usage_page.py::test_timeline_segments` |
| D-04 화면 | `/usage` 기간(KST) · 묶음 5 종 · 순위 표(요청 · 입력 · 캐시 읽기/쓰기 · 출력 · 적중률 · 도구 · 파일 · 실행 시간 · 추정 비용) · 일별 출력 · 비용 SVG 2 개(단일 축) · CSV. 실측 30 일: 출력 20.1M · 적중률 97.6% · $4,115.89 [추정] · 단가 없음 0 건 · 응답 0.05~0.15 s | 브라우저 스크린샷(스크래치, 커밋 안 함) · TestClient |
| D-05 화면 | `/timeline` 기본 지난 24 시간 · 부모 아래 자식 들여쓰기(최대 200 줄) · state_log 색 구간 · 동시 실행 면적(120 칸) | 같음 |
| D-06 화면 | `/pipeline` 단계 순서 01 → 02 → 03 → 04 → 00 → 05 · 06 · 08 · 칸 색 + have/need + 버전 + 날짜 · 판단 배지 · ↻ · ⚠ · 펼치면 규칙 · 근거 파일 · progress.md 줄 · 마지막 에이전트 · 다음 단계 열 | 같음 |
| CSV `make export` | `outputs/usage_<from>_<to>_<group>.csv` (UTF-8 BOM, 비용 열 이름에 `[추정] API 정가 환산 (단가표 …)`, 끝 줄 합계 · 단가 없음 N 건). 저장소 밖 경로 거부 | `AGENTDASH_DB=… make export [FROM= TO= GROUP=]` |
| R3 (개발2 요청) | `ingest_all` 끝에 `state.post_hook` (미등록일 때만) → 기본 DB `make gate` G-06 **PASS** (agentdash.db 부모 있음 243/243 = 100%, 이전 0/241). backfill 은 `link=False` 로 부르고 끝에서 resolve_all · evaluate_all | `make gate` (기본 `data/agentdash.db`) |
| G-17 | PASS — 화면 6 + API 10 = 16 HTTP 200 (빈 DB) · placeholder 0 | `uv run python src/agentdash/tools/check_routes.py` |
| G-13 · G-14 | PASS — dev1 DB 행 62,545 TEXT 위반 0 · 정적 쓰기 원천 대상 0 · 읽기 전용 pytest 198 passed 트리 변경 0 | `make gate` |
| pytest 전체 | 198 passed | `uv run pytest -q` |
| make gate | dev1 DB · 기본 DB 둘 다 PASS 18 · FAIL 0 · 미검증 4 (G-12 · G-18 · G-21 · G-22 QA) | `AGENTDASH_DB=data/agentdash-dev1.db make gate` · `make gate` |
| 원천 무변경 | `~/.claude/settings.json` 수정 시각 2026-10-16 15:15 그대로 · 파이프라인 판정은 이름 · mtime · run.json 회사 키 · progress.md 표제/표 행만 읽음 | `stat -f %Sm ~/.claude/settings.json` · `tests/test_pipeline.py::test_pipeline_never_writes_source` |

참고
- 390 px 확인은 못 했다 — 헤드리스 Chrome 창 최소 폭(약 500 px)이라 스크린샷이 잘린다. 표는 `.tablewrap`(가로 스크롤 안쪽), SVG 는 `width:100%` viewBox. G-21 은 QA2 몫.
- 파이프라인 갱신: `/pipeline` · `/api/v1/pipeline` 요청 때 원천 signature(단계 outputs/ · 그 아래 폴더 · progress.md mtime)가 바뀌었거나 300 s 가 지났으면 다시 판정해 pipeline_cell 에 저장. 감시기 스레드에는 붙이지 않았다.

## 3. 요청 (다른 사람에게)

- 개발2 → 반영함: R1 `linker.on_line` 을 ingest 가 줄마다 부른다 · Workflow `tool_call.target` = runId. (progress-dev2.md 가 아직 없어 linker.py 주석의 R1 · §3 요청을 보고 반영)
- 아키텍트: 없음. (gate.py 수정 요청 없음 — 도구 · 테스트 이름은 gate.py 그대로)
- 아키텍트 (웨이브 B — 이미 반영, 확인 요청): ① `config/pipeline.yaml` 에 `business_labels` · `run_json_company_keys` · `upstream` · 단계별 `match` · `stages.06.wave_company` 를 **덧붙였다**(spec 표 키 `patterns` · `need` 는 그대로 — `tests/test_config.py` 통과). 오케스트레이터 지시(「config/pipeline.yaml 로 표현」). ② `Makefile` `export` 타깃을 구현으로 바꿨다(NOTYET → `python -m agentdash.core.usage export`). ③ `base.html` 에 `{% block head %}` 한 줄.
- 개발2: R3 반영(위 표). R2 는 웨이브 A 에서 반영됨. R4(turn_ended)는 이번에 못 했다 — 필요하면 다음 회전.
