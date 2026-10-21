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

### 2차-A 공표 (2026-10-21 · Task 5~7 · 커밋 `f207e98` · `9e0922b` · `e2358c4`) — **개발2 Task 11 은 이것을 쓴다**

```python
# agentdash.core.budget (spec v0.3 §6.3) — 금액은 config/budget.yaml 에서만. KST = UTC+9
load() -> dict                     # {warn_ratio: float, total: {daily_usd, monthly_usd}, projects: {name: {daily_usd, monthly_usd}}}
                                   #   키 빠짐 · 금액이 null/양수 아님 · warn_ratio 0~1 밖 → settings.SettingsError
status(con, now: datetime | None = None, cfg: dict | None = None) -> list[dict]
                                   # cfg 없으면 budget.load() (모듈 속성으로 부른다 → monkeypatch.setattr(budget, "load", …) 가 먹는다)
    # 칸 순서: total day · total month · 그다음 cfg.projects 이름순 (day · month)
    # 칸 = {"scope": "total"|"project", "project": str|None, "period": "day"|"month",
    #       "limit": float|None, "est_usd": float (cost_est_usd 합, NULL 제외), "rec_usd": float (cost_usd 합),
    #       "ratio": float|None (est/limit), "level": "ok"|"warn"|"over"|"unset"|"no_records", "unpriced": int}
    # 일 = KST 오늘 00:00 ~ now, 월 = KST 1 일 00:00 ~ now. 한도 null → unset. 한도가 있는데 그 프로젝트 기록 0 → no_records
    # 프로젝트 = agent.project_path 마지막 이름 (없으면 project_key) — budget.project_name(path, key)
level(est, limit, warn_ratio) -> str   # ok < warn_ratio ≤ warn < 1.0 ≤ over, limit None → unset
worst(rows) -> dict | None         # over > warn 중 ratio 최대 칸 (D-01 띠). ok · unset · no_records 만이면 None
trend(con, grain: "day"|"week"|"month", frm: "YYYY-MM-DD", to: "YYYY-MM-DD", group: "total"|"project") -> list[dict]
    # 행 = {"bucket": "YYYY-MM-DD" (일 · 그 주 월요일 · 그 달 1 일, KST), "project": str|None (group=total 이면 None),
    #       "cost_usd": float|None, "cost_est_usd": float|None, "output_tokens": int, "output_est_total": int,
    #       "input_tokens", "cache_read", "cache_write": int, "hit": float|None}   — bucket · project 순. 원천 usage_daily
    # grain · group 이 틀리면 ValueError (API 는 422)
efficiency(con, group: "project"|"session"|"agent", frm, to) -> list[dict]
    # 행 = {"key", "label", "input_tokens", "cache_read", "cache_write", "hit": float|None, "cost_est_usd": float|None,
    #       "waste": float, "unpriced": int, "requests": int}  — waste = (1-hit)*cost_est_usd (hit None → 0) 내림차순
    # key: project = 이름 · session = "S:<sid>" (그 세션 폴더의 모든 에이전트 = 자기 + 자손) · agent = agent_key (자기만)
kst_bucket(ts_or_day, grain) -> "YYYY-MM-DD" ;  GRAINS · TREND_GROUPS · EFF_GROUPS
# agentdash.core.usage — D-17 (spec §6.2)
SUSPECT_MAX_OUTPUT = 30 ; SUSPECT_MIN_JSON = 400 ; UNDERCOUNT_NOTE = "추정 보정 (D-17)"
estimate(max_output, json_len, est_chars) -> int | None ;  cost_est(ev, pricing) -> float | None
totals(con, key, descendants=False)   # + "output_est_total" (의심 행 output_est · 나머지 output_tokens 합) · "cost_est_usd" · "est_note"
                                      #   1차 키 undercount* · LEGACY_UNDERCOUNT_NOTE 는 웨이브 B 에서 지움 (R-2A-1 개발2 완료 뒤)
table(...)                            # 행 · total · trend(일) 에 output_est_total · cost_est_usd, 결과에 "est_note" (undercount* 키 없음)
# agentdash.core.model.UsageEvent  + output_est: int|None · cost_est_usd: float|None
```

- 화면 문구 (spec 그대로): 금액 옆 `[추정] API 정가 환산` (`usage.ESTIMATE_LABEL`) · unset 칸 `한도 미설정` · 단가 없음 `단가 없음 N 건`. D-01 띠 예: 「오늘 전체 82 % · Standard MES 이번 달 104 %」 → `/insights` 링크. over = `st-FAILED` (계획 Task 11). D-07 게이지는 ok `st-DONE` · warn `st-WAITING_PERMISSION` (spec §6.3 · §4.1 주황, 웨이브 B 에서 바꿈 — R-2A-dev2-2) · over `st-FAILED` · unset/no_records `st-STALE` 를 쓴다 (`routers/insights.LEVEL_CLASS`) — D-01 띠도 같게 쓰면 맞는다.
- 수집기 누적기 키는 계획의 `(agent_key, request_id)` 에 **DB 파일을 더한** `(DB, agent_key) → {requestId: [max_output, json_len, est_chars]}` (테스트 · 도구가 한 프로세스에서 DB 를 여럿 연다). 다른 프로세스가 이어 읽으면 그 기록 앞부분 길이를 다시 잰다.
- 증분 수집(`ingest_all` · 감시기 묶음)이 바뀐 키의 `usage_daily` 를 다시 만든다 (`ingest_all(daily=True)` 기본, backfill 만 False 후 전체 재생성).

### 2차-T 공표 (2026-10-21 · Task 2 `usage.spark`) — **개발2 Task 3 (`core/twin.py`) 은 이것을 쓴다**

```python
# agentdash.core.usage (spec v0.4 §5.4 스파크)
SPARK_MINUTES = 30
spark(con, keys: list[str], now: datetime, minutes: int = SPARK_MINUTES) -> dict[str, list[int]]
    # 키마다 길이 minutes 의 int 리스트 (keys 순서대로 dict, 중복 키는 한 번). keys == [] → {}
    # 칸 i = [now_floor − (minutes−1−i) 분, +1 분) — i=0 가장 오래된 분, i=minutes−1 = 지금 분 (now 의 초는 버림)
    # 값 = SUM(COALESCE(output_est, output_tokens)) — 추정 보정 출력 [추정]. model '<synthetic>' 제외 (NULL 모델은 포함)
    # 기록 없는 키도 [0]*minutes. 자기 몫만 (자손 합 아님). 지금 분 다음(미래) 기록은 넣지 않는다
    # 분은 UTC — usage_event.at (UTC ISO "…Z") 앞 16 자. now 는 tz-aware 필수 (naive → ValueError), KST 로 줘도 같은 결과
    # 쿼리: keys 500 개씩 GROUP BY agent_key, 분 한 번 (설비마다 쿼리 아님)
```

- 테스트: `tests/test_usage.py::test_spark_*` 5 개 (칸 경계 10:01:00 첫 칸 · 10:00:59 제외 · 10:31:00 제외 · output_est 우선 · synthetic 제외 · 빈 키 0 · KST/UTC 같음 · 임의 50 행 합 = 직접 SQL 합).

## 2T. 2차-T 웨이브 A — Task 2 · Task 5 (2026-10-21)

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| Task 2 `usage.spark` | `tests/test_usage.py` spark 5 passed · 커밋 `5f916b1` | `uv run pytest -q tests/test_usage.py -k spark` |
| Task 5 G-32 (V-17) 가짜 DB | `tests/test_check_twin.py` 3 passed (PASS · 스파크 몽키패치 FAIL · 독립 스파크 = usage.spark) | `uv run pytest -q tests/test_check_twin.py` |
| G-32 `agentdash-v2a-verify.db` | PASS — 설비 11 · 라인 5 · 접힘 10+0 · 범위 21/21/21 · 누적 불일치 0 · 스파크 불일치 0 · 겹침 0 · TEXT>300 0 · 1.4 ms · 스파크 합 58202 | `AGENTDASH_DB=data/agentdash-v2a-verify.db uv run python src/agentdash/tools/check_twin.py` |
| G-32 같은 DB `--since all` | PASS — 설비 83 · 라인 32 · 접힘 239+0 · 범위 322 · 불일치 0 · 겹침 0 · 4.5 ms | `… check_twin.py --since all` |
| G-32 `agentdash-dev1.db` | PASS — 설비 10 · 라인 5 · 접힘 6+0 · 범위 16 · 10.0 ms | `AGENTDASH_DB=data/agentdash-dev1.db make check-twin` |
| pytest 전체 | 407 passed | `uv run pytest -q` |

- 300 설비 응답 시간은 실제 DB 에 설비가 300 개 없어 여기서 못 잰다 — 합성 300 은 개발2 `test_twin.py::test_build_300_under_300ms`.

## 2B2. 2차-A 웨이브 B — Task 12 (D-04~D-07 공통 틀) · R-2A-1 후속 (2026-10-21 10:30, DB `data/agentdash-dev1.db`)

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| `_dev1_style.html` 삭제 | 템플릿 include 0 (D-04~D-07). 색 #hex 0 · `--p-*` · `--st-RUNNING` 별칭 사용 0 — base 토큰 · `.card .grid .kpi .tbl .badge .st-* .chart` 만. 화면마다 `{% block head %}<style>` 은 배치(여백 · 폼 · 칩)만, 값은 토큰 | `grep -rn "_dev1_style\|#[0-9a-f]\{6\}" src/agentdash/app/templates/{usage,timeline,pipeline,insights}.html` |
| `_svg.py` · 간트 | SVG 마다 토큰만 쓰는 `<style>` (`_svg.STYLE`) · 간트 막대 `class="seg st-<STATE>"` (`--c`, `st-NONE` = `--line`, UNKNOWN = `--muted`) — 인라인 `var(--st-X)` 0 | `tests/test_usage_page.py` (`seg st-RUNNING`) |
| D-04 | 필터 카드 · KPI 카드 5 (`.grid.kpis` 160 px) · 설명 카드 · 일별 추이 2 차트 카드 (넓으면 2 열) · 순위 표 카드(`.tbl`, 칸 안 가로 밀기) · `[추정]` = `.badge` · 단가 없음 = `badge st-WAITING_PERMISSION` · y 눈금 잘림 수정(pad_l 60) | 브라우저 |
| D-05 | KPI 3 (기간 · 에이전트 · state_log) · 동시 실행 차트 카드 · 간트 카드(범례 = 상태 배지 10, 간트 `min-width 720px` 를 `.tbl` 안에서 가로 밀기) | 브라우저 |
| D-06 | 상태 수 KPI · 요약 카드 · 표 카드 — 칩 색 토큰 섞기(완료 accent · 일부 accent 옅게 · 진행 중 `--st-running` · 시작 전 선 · 규칙 없음 빗금) · 판단 필요 `badge st-WAITING_PERMISSION` | 브라우저 |
| D-07 | 예산 KPI 카드 · 추세 / 적중률 섹션 카드 · warn = `st-WAITING_PERMISSION` (`routers/insights.LEVEL_CLASS`, D-01 띠와 같음) · Chart.js 범례는 두 선만(프로젝트 막대 이름은 툴팁) · 테마 토글 · 시스템 테마 변경 시 토큰 다시 읽어 다시 그림(실측: 토글 뒤 선 색 = `--accent`) | 브라우저 |
| 390 px · 두 테마 | 4 화면 × 밝은 · 다크 = 8 : 문서 `scrollWidth` = `clientWidth` (373/373, iframe 390 px) · 콘솔 오류 0 | 스크린샷 `outputs/e2e/dev1-design/` 19 장 (커밋 안 함 — D-07) |
| R-2A-1 후속 | 개발2 완료(progress-dev2.md §8) 확인 뒤 `usage.totals()` 의 `undercount` · `undercount_note` · `undercount_output` · `_undercount_keys` · `UNDERCOUNT_KINDS` · `LEGACY_UNDERCOUNT_NOTE` 삭제 · 테스트 `test_undercount_flag_on_subagent_totals` → `test_totals_est_keys_without_legacy_undercount` (1차 키 0) · src 「기록상 과소」 0 | `uv run pytest -q tests/test_usage.py` · `grep -rn "기록상 과소\|undercount" src` |
| 전체 테스트 | **371 passed · 1 failed = `test_design.py::test_no_dev_style_includes` XPASS(strict)** — 개발1 · 개발2 둘 다 `_dev*_style` 을 걷어 내서 정상 (§3 R-2A-4) | `uv run pytest -q` |
| `make gate` | **PASS 27 · FAIL 2 · 미검증 1** — FAIL G-14 (읽기 전용 pytest `-x` 가 같은 XPASS 1 건에서 멈춤 · 정적 · DB 씨앗 PASS) · G-30 (같은 XPASS) → xfail 해제로 둘 다 풀린다. 미검증 G-29 (QA 표지) | `AGENTDASH_DB=data/agentdash-dev1.db make gate` |

## 2A. 2차-A 진행 — Task 5~8 · D-22 (2026-10-21 10:17, DB `data/agentdash-dev1.db` 새로 백필)

커밋: T5 `f207e98` · T6 `9e0922b` · T7 `e2358c4` · 공표 `eea9f69` · T8 `0ff1ffc` · D-22 `6b24506` (로컬만).

| 항목 | 실측 | 검증 명령 |
|---|---|---|
| 새 백필 | `rm -f data/agentdash-dev1.db*` → setup · backfill 4.3 s · 원천 파일 559 · agent 73 / 235 / 6 / 1 · usage_event 25,722 · usage_daily 352 · parse_error 0 | `AGENTDASH_DB=data/agentdash-dev1.db make setup backfill` |
| G-24 추정 열 (V-12) | **의심 DB 48.9 % (12,581/25,722) · 원천 48.9 % (12,581/25,722) · 차 0.00 %p · 위반 0** (참고 QA1 파일별 48.4 % — 포크 사본 중복 280 포함) · `tests/test_usage_est.py` 15 | `AGENTDASH_DB=data/agentdash-dev1.db uv run python src/agentdash/tools/check_usage_est.py` |
| G-26 예산 (V-13) | 칸 78 (설정 2 + 기록 프로젝트 38 × 2, 한도 없는 칸으로 대조) · 최대 차 $0.000000 · 단계 unset 2 (실제 budget.yaml = null) · `tests/test_budget.py` 16 | `… check_budget.py` |
| G-27 추세 (V-14) | 2026-08-01~10-21 · grain 3 × group 2 · 묶음 237 불일치 0 · usage_daily = usage_event (기록 $3,666.88 · 추정 보정 $3,795.53 · 출력 기록 17,422,091 · 추정 21,611,996) | `… check_trend.py` |
| G-28 캐시 적중률 (V-15) | 표본 10 (project 3 · session 3 · agent 4, 시드 20261021) · 최대 차 0 · 정렬 위반 0 | `… check_efficiency.py` |
| G-04 회귀 (D-22) | dev1 DB 73/73 · 235/235 · 6/6 · 보관 0 → PASS. **기본 DB** 세션 73 · DB 81 · 빠짐 0 · 남음 0 · **원천 삭제 보관 8**, 서브에이전트 235 · 254 · **보관 19** → PASS | `… check_counts.py` · `AGENTDASH_DB=data/agentdash.db …` |
| G-07 회귀 (D-22) | 후보 71 (dev1: 제외 0 · 기본 DB: 토큰 있는 세션 79 중 전부 지움 8 제외) · 표본 10/10 PASS (두 DB 같은 표본) · `# 표본 선정` 줄 | `… check_usage_sum.py` |
| G-17 | 화면 7 + API 13 = 20/20 HTTP 200 · **placeholder 0** | `uv run python src/agentdash/tools/check_routes.py` |
| 전체 테스트 | **370 passed · 1 xfailed** (개발2 진행분 포함) | `uv run pytest -q` |
| make gate (dev1 DB) | **PASS 28 · FAIL 0 · WARN 0 · BLOCKED 0 · 미검증 2** (G-29 · G-30 = QA 표지 대기) | `AGENTDASH_DB=data/agentdash-dev1.db make gate` |

- 계획과 다른 점 (근거): ① `_req_acc` 키에 DB 파일을 더했다 — 한 프로세스가 DB 를 여럿 열면(테스트 · 도구) 길이가 섞인다. ② 다른 프로세스가 기록을 이어 읽으면 누적기가 비어 있으므로 그 기록 앞부분(0 ~ offset)을 다시 재서 채운다 — 실측에서 백필 뒤 check 도구 동기화가 쓰고 있던 요청 1 건의 추정을 낮춘 것을 잡았다(`test_split_across_processes_same_as_single_pass`). ③ check_usage_est 모집단 = 세션 안 requestId 한 번(check_usage_sum 과 같은 독립 규칙) — QA1 파일별 정의는 포크 사본 280 요청을 두 번 세어 0.53 %p 벌어진다(참고로 같이 찍음). ④ 증분 수집 · 감시기가 바뀐 키의 usage_daily 를 다시 만든다 (전에는 백필 · reprice 때만 — 추세가 usage_daily 를 읽으므로).
- D-04 표기: 「기록상 과소 (D-17)」 → 「추정 보정 (D-17)」 · 표 · 카드 · CSV 에 기록 · 추정 두 열. D-03(개발2) 은 아직 1차 키를 읽어 `totals()` 의 `undercount*` 키를 남겼다 (§3 R-2A-1).
- 원천 무접촉: 원천은 'rb' 읽기 · `os.path.exists` 만. 가짜 루트 파일 삭제는 tmp 의 테스트 루트에서만. `check_readonly` PASS (정적 · 읽기 전용 pytest 370 · DB 씨앗 49/49). 실제 `~/.claude/settings.json` 손대지 않음 · 서버 띄우지 않음.

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

## 2D. 웨이브 D — QA1 결함 수정 (개발1 겸 아키텍트, 2026-10-17 17:30~17:50 · 코드 기준 `10cbd18` · DB `data/agentdash-dev1.db` 재백필)

| 결함 | 결과 | 고친 곳 | 먼저 실패한 테스트 → 통과 | 재현 스크립트 다시 돌림 |
|---|---|---|---|---|
| DEF-QA1-003 중대 | **고침** — 원천 거부 검사를 `mkdir` 앞으로. 원천 아래면 아무것도 만들지 않고 `RuntimeError` | `db/conn.py` `init_db` | `tests/test_settings.py::test_init_db_refuses_source_before_mkdir` (쓰기 가능한 가짜 home · agents 아래 DB 2 곳 × init_db/connect → 예외 · 트리 그대로) | QA1 §4(a) 그대로 스크래치 가짜 루트에서: `newdir` · `newdir2` · 읽기 전용 `Other Project/sub` 3 경우 모두 `RuntimeError` · **생긴 폴더 0** (이전: 폴더 생김 · PermissionError) |
| DEF-QA1-008 경미 | **고침** — `is_source_path` 가 설정 루트 + **항상** `Path.home()/.claude` · `config/settings.yaml` 기본 agents_root(저장소 자신 제외) 를 본다 (`Settings.guard_roots`). tmp 가짜 루트는 그대로 원천 | `settings.py` | `test_settings.py::test_is_source_path_always_guards_real_roots` | CLAUDE_HOME · AGENTS_ROOT 가짜로 둔 채 실제 `~/.claude/newdir/x.db` → True · 기본 agents_root 아래 → True · 저장소 `data/` → False (판정만, 열지 않음) |
| 도구 보강 (G-14) | **고침** — `check_readonly` 가 `AGENTDASH_DB` · `.db_path` 를 씨앗으로: 정적(쓰기 호출 앞줄에 원천 거부가 있어야) + 런타임(쓰기 가능한 가짜 루트 아래 DB 3 경로 × 진입점 7 = 21 회 — db.conn · backfill · pricing-check · reprice · export · pipeline · lifespan: 전부 「원천 루트 아래」 거부 · 생긴 항목 0) + 실제 루트 판정. G-14 가 세 번째 행 `G-14 원천 무접촉 (DB 경로 씨앗)` 을 함께 읽는다(항목 이름 `… + DB 경로`) | `tools/check_readonly.py` (`db_seed` · `--db-seed`) · `tools/gate.py` | `tests/test_safety_tools.py::test_readonly_db_seed_*` 3 (저장소 PASS · mkdir 먼저 하는 가짜 진입점 FAIL · 거부 안 하는 진입점 FAIL) | 옛 `conn.py`(10cbd18) 로 잠시 되돌려 돌리면 **FAIL** (정적 `conn.py:32 .mkdir()` · 런타임 `claude_home/newdir/` 생김) → 고친 뒤 PASS |
| DEF-QA1-001 중대 | **고침** — 사본 줄은 여전히 부모 몫이지만 사본 output 이 더 크면 소유 행(같은 세션에서 그 requestId 를 가진 행)을 그 값으로(`at` 은 소유 기록 그대로 · 비용 재계산). 부모 기록이 나중에 읽히면 미뤘다 반영 | `collect/ingest.py` (`_fork_pending` · `_apply_fork_pending`) · `core/model.py` `upgrade_owner_usage` | `tests/test_usage.py::test_fork_copy_final_value_goes_to_owner` · `…_when_fork_read_before_owner` (세션 사본 · 띄운 호출 재기록 · 손자 포크 → 부모 서브에이전트 · 순서 뒤바뀜) | 재백필 DB: dbd09a2a 출력 1,553,522 → **1,638,439 (+84,917)** · 8f3a6abd 1,352,668 → **1,358,335 (+5,667)** = **+90,584**. QA1 `recount.py`(소유 기록 안 최대 규칙) 대비 DB 출력 합 차이 = 21,187,750 − 21,097,166 = **90,584**, 다른 에이전트 = DEF-001 이 지목한 5 개뿐. `global_cost.py` 차이 $1.811680 (= DEF-001 금액). `fork_final.py` 는 원천만 재므로 128 · 90,584 그대로(정상) |
| `check_usage_sum` (G-07) | **고침** — 수집기 사본 제외 규칙(`skip_uuids` · `skip_rids`) 복제를 버리고 세션 단위 독립 규칙: requestId 세션에서 한 번 · 소유 = 처음 나온 기록(시각 → 깊이 → 키) · 값 = 사본 포함 output 최대 · DB `src_file.offset` 까지. 에이전트별 소유 불일치 수 추가 | `tools/check_usage_sum.py` | (도구) 옛 DB 에 돌리면 **FAIL 2** (dbd09a2a −84,917 · 8f3a6abd −5,667, 에이전트 불일치 4 · 1) | 재백필 DB · 기본 DB 표본 10 **PASS 10/10** · 불일치 0 |
| DEF-QA1-002 중대 | **차단 (D-17)** — 원천에 최종값이 없어 고칠 수 없다. 지어내지 않는다. 결정 전 임시 ①: 숫자 원천 그대로 + 표기 | `decisions.md` D-17 (+ D-01 · D-02 보완 줄) · `core/usage.py` (`totals` · `table` · CSV: `undercount` · `undercount_note` · `undercount_output`) · `templates/usage.html` | `test_usage.py::test_undercount_flag_on_subagent_totals` · `…_in_usage_table` | `stream_heuristic.py` 재실행: 메인 13/10,186 (0.1%) · **서브 11,999/17,492 (68.6%)** · 워크플로 60/85 (70.6%) · 하한 추정 4,138,268. D-04 `/usage` 전 기간: 출력 21,187,750 중 서브 · 워크플로 몫 7,943,038 에 「기록상 과소 (D-17)」 (화면 688 곳). D-03 API `usage.with_descendants` (dbd09a2a) undercount=true · 몫 1,296,881 / `usage.own` false |
| DEF-QA1-006 경미 | **고침** — 기간 · 묶음의 작성 파일 = 기간 안 고유 (agent, path) 수 (일자 묶음은 그날 고유). 일별 합을 더하지 않는다 | `core/usage.py` `_unique_files` | `test_usage.py::test_files_written_unique_over_period` (Write · Edit 가 다른 날 → 1) | 재백필 DB 전 기간: 묶음 agent · project · type · model 합계 = 행 합 = **2,269** = 고유 (agent, path) 2,269 (`usage_daily` 단순 합 2,284). QA1 시각 기대 2,262 — 그 뒤 원천이 7 늘었다 |

- 요청별 의심 플래그를 `usage_event` 에 두지 않았다: 스키마는 spec §3 과 글자 단위로 같아야 한다(G-01) — 열 추가는 정본 변경이라 D-17 대안 ② 에 묶인다. 대신 `check_usage_sum` 끝 줄이 표본 의심 비율을 매번 다시 잰다(길이만): 메인 4/4,178 (0.1%) · 서브 · 워크플로 10,376/14,055 (73.8%).
- 재백필: `rm data/agentdash-dev1.db*; AGENTDASH_DB=data/agentdash-dev1.db make backfill` 3.7 s · 원천 파일 578 · agent SESSION 77 · SUBAGENT 242 · WORKFLOW_AGENT 6 · WORKFLOW 1 · usage_event 27,490 · parse_error 0. 기본 DB 도 같은 방법으로 재백필(usage_event 27,498).
- QA1 나머지 스크립트(dev1 DB): `cost_check` 20/20 일치 · 단가표 불일치 0 · `cost_edge` 10/10 · `link_check` 248/248 · DB 일치 249/249 · `text_scan` 300 자 초과 0.
- `uv run pytest -q` **242 passed** (개발2 진행 중 테스트 포함).
- `make gate` (기본 DB, 17:44): **PASS 21 · FAIL 1 · WARN 0 · BLOCKED 0 · 미검증 0** — FAIL 은 G-12 (QA2 DEF-QA2-001~003, 개발2 몫). G-07 PASS 10/10 (새 독립 규칙) · G-14 PASS (정적 · 읽기 전용 pytest 242 · DB 경로 씨앗 21/21).
- 원천 무변경: `~/.claude/settings.json` mtime 1792131308 (2026-10-16 15:15) 그대로 · `~/.claude` · `~/Desktop/AI Coding` 의 이 폴더 밖에 `*agentdash*` · `newdir*` · `agentdash-probe` 0. 서버는 띄우지 않았다(8096 LISTEN 0). 커밋하지 않았다.

## 3. 요청 (다른 사람에게)

- **2차-A R-2A-4 (아키텍트) — xfail 해제**: Task 12 끝 — `_dev1_style.html` 삭제 · D-04~D-07 include 0. 개발2 도 `_dev2_style.html` 을 지워 `tests/test_design.py::test_no_dev_style_includes` 가 XPASS(strict) 로 깨진다 → xfail 을 떼 달라. 이 1 건이 `make gate` G-14 (check_readonly 의 `pytest -x`) · G-30 FAIL 의 원인이다.
- **2차-A R-2A-5 (아키텍트, 제안)**: 화면 4 가 같은 배치 규칙(`h1` · `h2` 크기 · `.stack` 세로 간격 · `.filters` 폼 컨트롤)을 각자 `<style>` 에 둔다(토큰만). base.html 공통 부품에 `.filters` (label · input · select · button) · `.stack` 을 올려 주면 화면별 `<style>` 을 더 줄인다.
- **R-2A-1 (개발2) — 완료 확인**: 개발2 §8 완료 → 개발1 이 `undercount*` 키 · `LEGACY_UNDERCOUNT_NOTE` 삭제 (§2B2).

- **2차-A R-2A-1 (개발2)**: D-03 (`agent.html` · `routers/agents.py`) 의 「기록상 과소 (D-17)」 를 D-17 확정 표기로 — `usage.totals()` 의 `output_est_total` · `cost_est_usd` · `est_note`(= 「추정 보정 (D-17)」) 를 기록 칸 옆에 `[추정]` 으로 (spec §6.2 「기록」 과 「추정 보정 (D-17)」 나란히). 바꾸면 `tests/test_dashboard.py::test_d03_undercount_note_d17` 도 갱신하고 알려 달라 — 그때 개발1 이 `totals()` 의 `undercount*` 키 · `LEGACY_UNDERCOUNT_NOTE` 를 지운다.
- **2차-A R-2A-2 (아키텍트) — T8 끝**: `routers/insights.py` 가 생겼다(`router = APIRouter()`, `/insights` · `/api/v1/{budget,trend,efficiency}`). `main.py` 의 `_insights_router` 분기 · `placeholders.INSIGHTS_STUB` 를 지우고 `insights` 를 `ROUTERS` 로 옮겨 달라. 지금도 check_routes placeholder 0.
- **2차-A R-2A-3 (아키텍트)**: CLAUDE.md 소유 표에 개발1 새 테스트 `tests/test_check_counts.py` (G-04 · G-07 D-22 시나리오) 를 더해 달라. `insights.html` 은 `_dev1_style` 을 include 하지 않는다(base 토큰 · 클래스만).

- 개발2 → 반영함: R1 `linker.on_line` 을 ingest 가 줄마다 부른다 · Workflow `tool_call.target` = runId. (progress-dev2.md 가 아직 없어 linker.py 주석의 R1 · §3 요청을 보고 반영)
- 아키텍트: 없음. (gate.py 수정 요청 없음 — 도구 · 테스트 이름은 gate.py 그대로)
- 아키텍트 (웨이브 B — 이미 반영, 확인 요청): ① `config/pipeline.yaml` 에 `business_labels` · `run_json_company_keys` · `upstream` · 단계별 `match` · `stages.06.wave_company` 를 **덧붙였다**(spec 표 키 `patterns` · `need` 는 그대로 — `tests/test_config.py` 통과). 오케스트레이터 지시(「config/pipeline.yaml 로 표현」). ② `Makefile` `export` 타깃을 구현으로 바꿨다(NOTYET → `python -m agentdash.core.usage export`). ③ `base.html` 에 `{% block head %}` 한 줄.
- 개발2: R3 반영(위 표). R2 는 웨이브 A 에서 반영됨. R4(turn_ended)는 이번에 못 했다 — 필요하면 다음 회전.
- **개발2 (웨이브 D, D-17 임시 표기 ① — 요청)**: D-03 상세(`/agents/{key}`)에서 서브에이전트 · 워크플로 에이전트의 출력 토큰 · 추정 비용 옆, 그리고 세션 합계(자기 + 자손)에 자손이 있으면 그 옆에 **「기록상 과소 (D-17)」** 를 붙여 달라. API 는 이미 준비됨 — `GET /api/v1/agents/{key}` 의 `usage.own` · `usage.with_descendants`(= `usage.totals`) 에 `undercount`(bool) · `undercount_note`(문구, 아니면 null) · `undercount_output`(그 몫의 출력 토큰). 숫자는 바꾸지 말 것. D-01 관제판 · D-02 구성도에 토큰을 보이면 같은 표기를 권한다. 사람이 D-17 을 정하면 바뀔 수 있다.


## 2D2. 웨이브 D2 (정리 담당 겸, 2026-10-17 17:58 · 커밋 안 함)
- **R8 반영** — `agent.last_event_at` = 모든 줄 종류의 마지막 기록(handback 뒤 활동 아닌 꼬리 제외, D-20). `parsers/transcript.parse_line(raw, *, others=False)` — `others=True` 면 세지 않는 줄 종류도 `Record(type, uuid, timestamp)` 만 (ingest 가 씀; 기본 동작 그대로). 새 열 없음. 테스트 `tests/test_model.py` 3 (빨강 → 초록).
- **R9 반영** — `model.add_edge`: label 은 더 늦은(같은) 시각 값만 바꾼다, 시각 없는 값 · 옛 값은 label 을 안 덮음(엣지 4 종 공통, `at` 도 시각 없는 값으로 안 바뀜). 테스트 `tests/test_model.py` 10 (빨강 8 → 초록).
- 재백필 기본 DB 4.0 s · 원천 파일 580 · agent 77 / 243 / 6 / 1 · usage_event 27,570 · parse_error 0. `uv run pytest -q` **266 passed**. `make gate` PASS 18 · 미검증 4 (G-12 · G-18 · G-21 · G-22 — QA 리포트 형식, DEF-QA2-008) · FAIL 0. 실제 settings.json sha1 8641eb22e8f5… 그대로.

## 2D3. 웨이브 D3 (수정 담당 — 아키텍트 · 개발1, 2026-10-17 18:30 · 커밋 안 함)
- **DEF-QA1-101** `settings.same_or_under` (resolve → 존재하는 가장 가까운 조상부터 (st_dev, st_ino) 비교 · 없는 꼬리 NFC+casefold) — `is_source_path` · `db/conn` 거부 · `scripts/hooks_install.is_real_target` 가 같은 함수. 저장소 예외는 정체성만(loose=False). 테스트 `test_settings.py` +7 · `test_hooks_install.py` +1 (빨강 → 초록). QA1 재현(`$S/CASEHOME/newdir/x.db` · `$S/CaseHome/projects/y.db`) → `RuntimeError`, 생긴 항목 0. 실제 `~/.CLAUDE/…` · `~/desktop/ai coding/…` 판정 True (판정만).
- **check_readonly --db-seed** 경로 3 → 7 (대문자 · 대소문자 · NFD · NFD+대문자) + 실제 루트 변형 3. 옛 settings.py(8606bc8) 사본에서 FAIL(거부 21/49 · 생긴 항목 4) · 새 코드 PASS 49/49.
- **DEF-QA1-103 · DEF-QA2-101** gate: 모든 게이트에 QA 묶음(`outputs/qa*-*.md` · `e2e/self-observe*.md`)별 최근 회차 표지 판정 · 개발 판정과 더 나쁜 쪽 · 실측 칸에 파일. CLAUDE.md 「QA 리포트 형식」 1 줄. `test_gate.py` +15.
- **DEF-QA1-102** D-21 (ingest + linker._activity). 사용량 뒤 last_event_at 60 → 0. judge.py 전수 328 불일치 1 → 0 (ingest 만이면 51).
- **DEF-QA2-102** D-01 카드 · D-03 판정(저장 · 지금)에 「가설 D-18」 (`agents.hypothesis_note`). **DEF-QA2-103** `/graph` 프로젝트 옵션 서버에서 미리 채움 + `selected` · JS 는 없는 것만 더함. 테스트 +4.
- 기본 DB 재백필 · `uv run pytest -q` **296 passed** · `make gate` PASS 21 · FAIL 1 (G-14 = QA1 r2 FAIL 반영, 개발 PASS — QA1 재검증 대기). settings.json sha1 8641eb22e8f5… 전 = 후.
