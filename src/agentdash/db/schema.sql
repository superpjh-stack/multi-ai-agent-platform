-- spec.md v0.3 §3 정규화 모델 — 11 테이블을 글자 그대로 옮겼다 (사람만 고치는 정본에서 복사).
-- 아키텍트만 고친다. 바꿀 일이 생기면 decisions.md 에 먼저 올린다.

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
