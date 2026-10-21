# 결정 대장 (decisions.md)

상태: `확정` (근거 파일 · 줄과 함께) / `가설` (확인 전 기본값) / `가설 반박` (대안 규칙으로 진행) / `차단` (사람 확인 필요 — 화면에 `미확정 (D-nn)`).
`gate.py` 는 `상태: 차단` 인 D-번호 본문이 언급한 G-nn 을 BLOCKED 로 표시한다. 본문을 붙여 넣지 않는다 — 숫자 · 경로만.

## D-01 `requestId` 같은 줄의 중복 여부 (A3)
- 상태: 확정 (개발1, 2026-10-17 실측 — 원천 jsonl 318 개 읽기만)
- 기본값: 같은 `requestId` 는 usage 한 번만 센다.
- 근거: requestId 있는 assistant 줄 54,708 중 같은 파일 안 같은 requestId 재등장 27,540 줄(내용 블록마다 한 줄). 그중 usage 가 다른 묶음 2,242 — 다른 칸은 `output_tokens` · `output_tokens_details` · `server_tool_use` · `iterations` · `speed` 뿐(입력 · 캐시는 같음)이고 2,242/2,242 에서 output 이 단조 증가 → 스트리밍 중간본. 규칙: (agent_key, requestId) 한 행, output_tokens 가 가장 큰 줄(최종본)을 남긴다 (`model.add_usage`). 표본 10 세션에서 중복 제거로 빠진 출력 토큰 7,628,314 (`check_usage_sum` 끝 줄). requestId 없는 assistant 줄 66 은 전부 `<synthetic>`.
- 확인 방법: 표본 세션에서 중복 제거 전후 토큰 합 비교 (G-07 · V-03). 담당 개발1.
- **웨이브 D 보완 (2026-10-17)**: 「마지막 줄 = 최종본」 근거는 **메인 세션 기록에만** 성립한다 — 서브에이전트 · 워크플로 기록은 → **D-17 (차단)**. 또 requestId 하나는 세션 안에서 한 번, 값은 소유 기록 + 포크 사본을 통틀어 output 최대 줄 (DEF-QA1-001, D-02 보완 참고).

## D-02 자식 기록의 부모 재기록 여부 (A4)
- 상태: 가설 반박 (개발1, 2026-10-17 실측) → 대안 규칙으로 진행
- 기본값: 없음 → 이중 계산 없음 (세션 합계 = 자기 + 자손).
- 근거: 부모가 자식 usage 를 다시 적는 경우는 없다(일반 서브에이전트 · 워크플로 에이전트와 부모 사이 공유 requestId 0). 그러나 **포크(`isFork`) 26 개는 전부 부모 기록 줄을 uuid · requestId · 시각 그대로(agentId 만 바꿔) 맨 앞에 다시 적는다** — 사본 1,142 줄(assistant 455), 여러 파일에 걸친 requestId 137 개가 전부 포크 관련. 또 포크 26 개 모두 띄운 호출(부모 assistant 의 tool_use 줄)을 **새 uuid · 같은 requestId** 로 한 줄 더 적는다(16 개는 첫 assistant, 10 개는 사본 끝).
- 대안 규칙: 포크 기록에서 부모 파일(`parentAgentId` 있으면 그 에이전트, 없으면 세션 메인)에 같은 uuid 가 있는 줄과 부모 assistant 와 requestId 가 같은 assistant 줄은 부모 몫 → 토큰 · 도구 호출로 세지 않는다 (`collect/ingest.py`). 결과: 백필 DB 에서 두 에이전트에 걸친 requestId 0 (`check_usage_sum` 「세션 안 requestId 중복 0」), 세션 합계 = 자기 + 자손.
- 확인 방법: 부모 · 자식 토큰 합 비교. 담당 개발1.
- **웨이브 D 보완 (DEF-QA1-001, 2026-10-17)**: 사본 줄은 여전히 부모 몫(포크 에이전트 토큰으로 세지 않음)이지만, 사본의 output 이 소유 행보다 크면 **그 값을 소유 행에 반영**한다(시각 `at` 은 소유 기록 그대로, `model.upgrade_owner_usage`). 소유 행 = 같은 세션에서 그 requestId 를 가진 행 — 손자 포크의 사본이 이미 사본인 줄이어도 진짜 소유자(세션 · 조부모)에 붙는다. 부모 기록이 나중에 읽히면 미뤄 두었다가 반영(`ingest._fork_pending`). 실측: QA1 128 requestId · 출력 +90,584 (8f3a6abd +5,667 · dbd09a2a +84,917). `check_usage_sum` 은 이 규칙을 복제하지 않고 세션 단위 독립 규칙(소유 = 처음 나온 기록, 값 = 사본 포함 최대)으로 다시 센다.

## D-03 `thinking_tokens ⊂ output_tokens`
- 상태: 확정 (개발1, 2026-10-17 실측)
- 기본값: 포함 (비용 공식에서 따로 더하지 않는다, `spec.md` §6.1).
- 근거: `output_tokens_details.thinking_tokens` 가 있는 assistant 줄 22,888 중 thinking > output 인 줄 0. 포함 관계와 모순 없음 → 비용은 output 만 곱한다 (`tests/test_cost.py::test_thinking_not_added`).
- 확인 방법: 표본 메시지 대조. 담당 개발1.

## D-04 `SubagentHandback` ↔ 자식 종료 1:1 (L-07)
- 상태: 가설 반박 (개발2, 2026-10-17 실측 — `~/.claude/projects/**` 읽기만) → 대안 규칙으로 진행
- 실측 (원천 전체, 서브에이전트 meta 235):
  - "260 회 띄움" = assistant 줄의 `Agent` tool_use **263 줄** 이지만 고유 tool_use.id 는 **237**. 26 건은 포크 기록(`isFork`, 26 개)이 부모 대화를 사본으로 품어 같은 id 가 두 파일에 나온 것.
  - 고유 237 중 2 건은 tool_result `is_error: true`(에이전트 안 생김) → meta 235 와 일치. 235 전부 `async_launched`(background) — 부모에게 바로 돌아오는 결과는 "띄움 확인"이지 종료가 아니다.
  - "220 회 반환" = `SubagentHandback` tool_use **221 건**(전부 자식 자기 기록 안, tool_result `success`). 이를 부른 자식은 **200**; 16 자식은 2 회 이상(SendMessage 로 다시 깨운 뒤 다시 반환 — `resumedAgentId` 관찰).
  - handback 을 한 번도 안 부른 자식 35: 부모 기록의 `<task-notification>` status `completed` 16 · `failed` 12, 신호 없음 7 (그중 2 는 측정 시각에 실행 중인 개발1 · 개발2, 5 는 신호 없이 끊김 → R-11 STALE).
  - 부모 쪽에는 handback 이 `<agent-message from="<agentId>">` user 줄로 돌아온다(195 건, from 은 전부 agentId).
  - handback 직후 자식 기록은 그 tool_result(136) 또는 tool_result + 마지막 text(58) 뿐 — 새 tool_use · 들어온 메시지가 있으면 다시 깨어난 것.
- 대안 규칙 (`core/linker.py` `returned()`): 종료 신호 = `SubagentHandback`(자식) ∪ `<task-notification>` status ∈ {completed, failed, killed}(부모, failed · killed 는 오류) ∪ Agent tool_result is_error ∪ 훅 `SubagentStop`. **가장 늦은 종료 신호가 자식의 마지막 활동(tool_use 를 낸 assistant 줄 · 들어온 메시지 줄) 이후**면 끝(R-08), 아니면 아직 실행 중. 실측 결과: 반환 223 · 미반환 12 (`uv run python src/agentdash/tools/check_link_rate.py` 의 「반환 분포」).
- 근거 재현: `check_link_rate.py` (원천 직접 스캔 · 숫자만 출력). 담당 개발2.

## D-05 훅 페이로드의 서브에이전트 식별 필드
- 상태: 가설 (공식 문서로 확인 · 실제 페이로드는 `미검증` — 사람이 훅을 설치한 뒤 실측, goal.md §2.6)
- 공식 문서 (code.claude.com/docs/en/hooks, 2026-10-17 읽음): 공통 `session_id` · `transcript_path` · `cwd` · `hook_event_name` (+ `prompt_id` · `permission_mode` 등). **서브에이전트 안에서 난 이벤트에는 `agent_id` · `agent_type`** 이 붙고 PreToolUse/PostToolUse 도 서브에이전트 도구 호출에 대해 난다. `SubagentStart`: `agent_id` · `agent_type`. `SubagentStop`: `agent_id` · `agent_type` · `agent_transcript_path` · `last_assistant_message` · `stop_hook_active`. `Notification`: `message` · `title` · `notification_type`(matcher 값 `permission_prompt` · `idle_prompt` …). PreToolUse/PostToolUse: `tool_name` · `tool_input` · `tool_use_id`.
- 채택 (`collect/hooks_rx.py` `agent_key_for`): `agent_id` → `A:<agent_id>`; 없으면 `agent_transcript_path`/`transcript_path` 파일명이 `agent-<id>.jsonl` 이면 `A:<id>`; 그 밖 `S:<session_id>`. 저장 필드는 화이트리스트(프롬프트 · `last_assistant_message` · `tool_input` 본문은 버림, `tool_input` 은 file_path · path · url · description 앞 120 자만).
- 남은 확인: 설치 후 `make hooks-check` 로 이벤트별 수신 · `agent_id` 실제 존재 여부. 담당 개발2.

## D-06 `active_seconds` 간격 기준
- 상태: 확정 (개발1, 2026-10-17 실측 — 분포 근거. 사람 체감 대조는 웨이브 B D-04 화면에서)
- 기본값: 5 분 (연속 기록 간격 ≤ 5 분 구간의 합).
- 근거: 백필 DB 의 기록 시각(usage_event.at · tool_call.at · result_at) 에이전트별 연속 간격 87,655 개 중 ≤ 1 분 97.14% · ≤ 5 분 99.16% · 4~7 분 구간 258 개(0.29%) — 경계 근처가 비어 있어 4 분 · 7 분으로 바꿔도 합이 거의 같다. 일자는 뒤 기록의 KST 날짜 (`core/usage.py::active_by_day`).
- 확인 방법: 표본 세션 체감 대조. 담당 개발1.

## D-07 `.gitignore` 범위 (`data/` · `outputs/e2e/` 스크린샷에 경로 노출)
- 상태: 확정 (2026-10-20 사람 승인 — `spec.md` v0.3 머리 버전 줄 「결정 D-07 … 확정 반영」 · `docs/superpowers/specs/2026-10-20-agentdash-v2a-design.md` 결정 표 「현재 `.gitignore` 확정」)
- 확정: 지금 `.gitignore` 그대로 (`data/` · `.env` · `.venv/` · `__pycache__/` · `outputs/e2e/*.png`). 아키텍트 반영 2026-10-21.
- 기본값: `data/` 제외, 스크린샷(`outputs/e2e/*.png`)은 커밋하지 않음. Phase 0 의 `.gitignore` 가 이대로다(`data/` · `.env` · `.venv/` · `__pycache__/` · `outputs/e2e/*.png`).
- 확인 방법: 사람 확인.

## D-08 Haiku 5.5 캐시 읽기 단가 (`[추정: 0.1 배]`)
- 상태: 확정 (아키텍트, 2026-10-21 — 공식 단가 페이지 대조, 읽기만 · 코드에 외부 전송 없음)
- 확정: 출처 https://platform.claude.com/docs/en/about-claude/pricing (2026-10-21 읽음) 「Model pricing」 표 — Claude Haiku 5.5 (prompts up to 100,000 tokens) Cache hits and refreshes **$0.01 / MTok** · (over 100,000 tokens) **$0.05 / MTok**. 기존 값 0.01 · 0.05 와 같다 → 값 변경 없음 · `make reprice` 불필요 · `config/pricing.yaml` 의 `cache_read_estimated` 표시 제거. 같은 표의 입력 0.10 · 0.50 · 출력 0.50 · 2.50 도 `spec.md` §6.1 과 같다. 근거 절 = `spec.md` v0.3 §6.1 (D-08) · 2026-10-20 사람 승인.
- 기본값: 0.01 (≤100K) · 0.05 (>100K) — `config/pricing.yaml` 에 `cache_read_estimated: true` 로 표시.
- 확인 방법: 공식 단가 페이지 대조 (외부 전송 아님 — 읽기). 지금 기록에 Haiku 5.5 메시지는 없다(`spec.md` §6.1 표).

---

아래는 Phase 0 에서 원천을 읽으며(쓰기 없음) 본 것 — 개발자가 가설을 정할 때 출발점. 2026-10-17 실측.

## D-09 S1 `status` 에 `busy` · `idle` 밖의 값 `shell`
- 상태: 확정 (개발2, 2026-10-17 관찰 1 건 — 다시 보이면 재확인) → idle 계열로 처리
- 관찰: `~/.claude/sessions/*.json` 3 개 중 1 개가 `status: "shell"` (version 2.1.302). 그 세션의 `statusUpdatedAt` 은 기록 마지막 줄 `system/turn_duration` 과 같은 밀리초(턴이 끝난 순간)였고, 그 뒤 새 기록 없음. 그 claude 프로세스 밑에 `zsh → npm run dev` 자식이 살아 있었다(같은 세션의 `Bash run_in_background: true` 호출 3 건 중 마지막이 그 직전). 나머지 2 세션은 `busy`.
- 해석: 턴을 끝내고 입력을 기다리는데 백그라운드 셸 작업이 남아 있는 상태 — busy 아님.
- 처리 (`core/state.py`): `shell` 은 R-03 · R-04 · R-05(idle 계열)로 판정하고 근거에 `S1 status=shell (D-09)` 를 남긴다. `busy` · `idle` · `shell` 밖의 값도 idle 계열로 보되 근거에 `미지 값` 을 남긴다(조용히 삼키지 않는다). 새 상태 · 새 규칙은 만들지 않았다.
- 테스트: `tests/test_state.py::test_rule_table[R-05 shell (D-09)]` · `test_evidence_carries_values`. 담당 개발2.

## D-10 워크플로 · 손자 메타 형식
- 상태: 확정 (개발2, 2026-10-17 실측 — 원천 meta 241 읽기만)
- 관찰: 워크플로 에이전트 `.meta.json` 에는 `toolUseId` 가 없고 `agentType: workflow-subagent` · `workflowPhase` 가 있다. 깊이 2 포크 메타에는 `parentAgentId` · `isFork` · `model` 이 있다. 워크플로 폴더에 `journal.jsonl` · `scripts/` 가 함께 있다. 세션 폴더에 `custom-title.json` 이 있는 경우가 있다.
- 확인 (A2 `toolUseId` ↔ `tool_use.id` 포함): 서브에이전트 meta 235 전부가 자기 `toolUseId` 와 같은 `Agent` tool_use.id 를 같은 세션 폴더 안에서 찾았다 — 세션 기록 223(L-01) · 다른 서브에이전트 기록 12(L-02, 전부 깊이 2 · `parentAgentId` 있음, 12/12 일치). 같은 id 가 세션과 포크 사본 두 곳에 나오는 26 건은 세션 > 깊이 낮은 기록 순으로 고르면 parentAgentId 와 어긋남 0. 워크플로 노드의 부모는 `Workflow` tool_result 의 `toolUseResult.runId`(= 폴더 `wf_<id>`)를 품은 줄의 에이전트 — 1/1. 워크플로 에이전트 6 은 폴더로 `W:<wfId>` 에 (L-03).
- 규칙: L-03 폴더(`subagents/workflows/wf_<id>/`) → 워크플로 노드, 워크플로 노드 → runId 를 받은 에이전트. L-02 는 `parentAgentId` 1 순위 + `toolUseId` 대조(근거에 일치/불일치). `scripts/` 는 본문이므로 읽지 않는다.
- 결과: 원천 직접 연결 241/241 = 100% · 개발2 백필 DB(`data/agentdash-dev2.db`) 241/241 (`check_link_rate.py --db data/agentdash-dev2.db`). 담당 개발2 (G-06 · G-10).

## D-11 transcript 줄 종류 — `assistant` · `user` 밖의 줄
- 상태: 확정 (개발1, 2026-10-17 — 아래 「확정」 줄)
- 관찰: 이 저장소 세션 468 줄 중 `assistant` 86 · `user` 62 외에 `api-request-blob` 64 · `attachment` 53 · `api-request` 33 · `last-prompt` 30 · `mode` 30 · `permission-mode` 30 · `atis-latch` 30 · `ai-title` 29 · `system` 11 · `file-history-*` 9 · `api-request-shape` 1. **`api-request-blob` 줄의 `message.content` 에도 `tool_use` 블록이 있다**(43 건).
- 기본값(제안): 도구 호출 · 토큰은 `type == "assistant"` 줄에서만 센다(요청 사본인 `api-request-blob` 을 세면 이중 계산). 모르는 종류는 무시하되 `parse_error` 로 올리지 않는다(필수 필드가 없는 assistant/user 줄만 `parse_error`).
- 담당: 개발1 (G-02 · G-07).
- **확정 (개발1, 2026-10-17 실측)**: 전체 원천 159,139 줄 · 줄 종류 23 가지. `api-request-blob` 488 줄 안 `tool_use` id 121 개가 **전부** assistant 줄에도 있다(없는 것 0) → 사본. assistant 줄 tool_use 30,698. 깨진 JSON 0 · 필수 필드 없는 assistant 0. 기본값대로 구현 (`collect/parsers/transcript.py`, `tests/test_parsers.py::test_d11_blob_tool_use_not_counted`). `agent-name` 줄은 이름만 꺼낸다(D-13).

## D-12 원천 규모 기준값 (계속 늘어난다)
- 상태: 확정 (2026-10-17 16:12 실측, `goal.md` §9 명령)
- 메인 세션 77 · 서브에이전트(워크플로 제외) 233 · 워크플로 에이전트 6 · 프로젝트 폴더 43. `spec.md` · `intro.md` 의 232 · 41 보다 늘었다 — 백필 대조(V-01)는 같은 시각에 다시 센다.

## D-13 세션 이름 2 순위 — 첫 사용자 메시지 앞 40 자 대신 `agent-name` 줄
- 상태: 확정 (2026-10-20 사람 승인 — `spec.md` v0.3 §3.1 세션 이름 행 「… 마지막 `agent-name` 줄 … 첫 사용자 메시지는 본문이므로 읽지 않는다 (D-13)」 · `problem.md` Q9)
- 확정: 아래 기본값이 spec 글자가 되었다. 구현 변경 없음.
- 관찰: `spec.md` §3.1 은 세션 이름을 "S1 `name` → 첫 사용자 메시지 앞 40 자 → 프로젝트 폴더 마지막 이름" 으로 정하지만, 첫 사용자 메시지는 프롬프트 본문이다(CLAUDE.md 「본문을 저장 · 복사하지 않는다」 와 충돌). 기록에는 `agent-name` 줄(1,078 줄, `agentName` = S1 `name` 과 같은 꼴의 이름)이 있다.
- 기본값: S1 `name` → 그 세션 기록의 마지막 `agent-name` → `cwd` 마지막 이름(없으면 프로젝트 폴더명). 첫 사용자 메시지는 읽지 않는다 (`collect/ingest.py`).
- 담당: 개발1. 사람이 spec 쪽을 정하면 따른다.

## D-14 S1 `busy` 가 턴이 끝난 뒤에도 남는다 (A1 `sessions/*.json` status 갱신)
- 상태: 확정 (2026-10-20 사람 승인 — `spec.md` v0.3 §4.2 세션 평가 순서 「R-03 · R-04 를 R-02b 보다 먼저 (D-14)」 · R-03 · R-04 행 「잠잠한 busy」 · `problem.md` Q12). 1차 기록: 가설 반박 (개발2, 2026-10-17 관찰 1 건) → 대안 규칙으로 진행
- 확정: 아래 대안 규칙이 spec R-04 글자가 되었다.
- 관찰: 오케스트레이터 세션(이 루프)의 S1 은 `status: busy` · `updatedAt` 15:58 그대로인데, 기록 마지막 줄은 16:16 의 `system/turn_duration`(턴 끝)이고 그 뒤 새 줄이 없었다. 그동안 그 세션이 띄운 백그라운드 서브에이전트 2(개발1 · 개발2)가 실행 중이었다. 즉 S1 `busy` 는 "모델이 지금 생각 중" 이 아니라 백그라운드 자식 작업까지 포함해 남는다 — spec §4.2 R-02b 를 그대로 쓰면 자식을 기다리는 세션이 5 분 뒤 `STALE` 로 오판된다.
- 대안 규칙 (`core/state.py` `_session`): S1 `busy` · 5 분 넘게 기록 없음 · 훅 도구 실행 중 아님이어도 **미종료 백그라운드 자식(RUNNING · WAITING_* — STALE 자식은 빼고) ≥ 1** 이면 `WAITING_CHILD`(규칙 코드 R-04, 근거에 `S1 status=busy · 미종료 백그라운드 자식 N · D-14`). 자식이 없으면 spec 대로 R-02b `STALE`.
- 테스트: `tests/test_state.py::test_rule_table[R-04 busy · 턴 끝 · 자식 (D-14)]` 외 1. 실측: 개발2 백필 DB 에서 그 세션 = WAITING_CHILD R-04. 사람이 spec R-02b 를 고칠지 정한다. 담당 개발2.

## D-15 파이프라인 파일 패턴 — spec §7.1 과 실제 폴더의 차이 (G-19)
- 상태: 가설 (개발1, 2026-10-17 실측 — `~/Desktop/AI Coding/0{0,1,2,3,4,5,6,8} *Agent/outputs` 이름 · mtime 만 읽음) → 실제에 맞춰 `config/pipeline.yaml` 로 표현 (코드에 박지 않음)
- 관찰 1 — `{사업}` 칸: 03 · 04 파일명 둘째 칸이 `제조AI` 만이 아니다. 니즈푸드 · 임진강김치는 `스마트공장` (03 각 6 파일 · 04 각 7 파일). spec 패턴 `{회사}_제조AI_…` 그대로면 두 회사 03 · 04 가 have 0 → NOT_STARTED 오판. 채택: `business_labels: [제조AI, 스마트공장]`, 패턴 `{회사}_{사업}_…`.
- 관찰 2 — macOS 파일 이름 NFD: 일부 파일(예: 00 `pm-경동글로벌텍/12.SF-PM3_…` · 04 니즈푸드 단위테스트결과서)이 한글 자모 분리(NFD)로 저장돼 NFC 사전 이름과 바이트가 다르다. 정규화 없이 세면 경동 00 PARTIAL 4/5 · 니즈푸드 04 PARTIAL 6/7 + 「미등록 회사 1 (경동글로벌텍)」 오판. 채택: 이름 비교 전에 NFC (`core/pipeline.py nfc`). `check_pipeline` 의 find 는 NFC · NFD 두 벌 패턴.
- 관찰 3 — run.json 에 `company` 키가 없다. 01 · 02 run.json 은 run_id · scope · notes(본문) · started(+02 analysis 경로), 00 midterm 은 `facts: notes/<회사>_확정값.yaml`. 채택: `run_json_company_keys: [company, company_name, facts]` (값에 사전 이름이 든 것) → 없으면 폴더 안 산출물 파일명 {회사} 칸(최빈). notes 는 읽지 않는다.
- 관찰 4 — spec 패턴을 산출물 단위로 펼쳤다(`stages.NN.match`: id · dir · run · file). 03 은 화면설명서 html · 화면정의서 pptx · 영상 mp4(`화면설명서_영상*` 4 벌 중 하나) 3 칸, 00 은 `*-midterm` 실행의 `*중간보고서_{회사}_v*.docx` 1 + `pm-{회사}/` 의 SF-PM1~4. `11-1.중간보고서_검수의견_*` 은 세지 않는다. `pm-고려솔더_20261016` · `pm-임진강김치_20261004` · `납품_*` 은 spec 패턴(`pm-{회사}/`) 밖이라 세지 않는다 — 그래서 고려솔더 00 의 SF-PM 근거는 `pm-고려솔더/`(09-13 mtime).
- 관찰 5 — 뒤처짐 비교 대상(`upstream`): 02←01 · 03←02 · 04←03 · 00←01·02 (spec §7 D-06 「00 PM 이 01 · 02 결과를 읽는다」). 앞 단계가 실행 폴더면 그 회사 최신 run.json `started`(KST), 아니면 산출물 최신 mtime.
- 관찰 6 — 미등록 회사는 구조화된 자리(파일명 · 폴더명의 {회사} 칸, run.json 회사 키)에서만 센다. progress.md 표제에서 사전 밖 이름을 골라내는 규칙은 spec 에 없어(자유 서술) 표제는 사전 이름만 찾는다. 실측: 미등록 0 건(두손푸드는 00 progress.md 표제에만 나오고 파일 · 폴더 이름에는 없다).
- 관찰 7 — P-01 키워드는 글자 그대로(`판단 필요` · `사용자 판단` · `확인 필요`). 02 progress.md 의 「고객 확인이 필요한 항목」 표제 3 개는 `확인 필요` 와 글자가 달라 걸리지 않는다. 실측 P-01: 02 니즈푸드(progress.md:946) · 임진강김치(:913 · :921).
- 관찰 8 — 06 Coding Agent 대상 회사: 표제 · 표 행에 회사 이름이 없다(줄 3 의 인용 줄에만). spec §7.1 문장(「회사 하나(고려솔더)」)대로 `stages.06.wave_company: 고려솔더` 로 두고 웨이브 표시는 `## ` 표제의 ✅ 🔄 ⏸ 만 읽는다 → 「Phase 0 ✅ · 웨이브 A ✅ · 웨이브 B 🔄 · 웨이브 C ✅ · 웨이브 D ✅」.
- 확인 방법: `uv run python src/agentdash/tools/check_pipeline.py` (V-11 — find 독립 재계산 표본 10 칸 일치) · `tests/test_pipeline.py`. 사람이 spec §7.1 패턴을 고칠지 정한다. 담당 개발1.

## D-16 D-05 간트의 `state_log` 이전 구간
- 상태: 가설 (개발1, 2026-10-17)
- 관찰: `state_log` 은 대시보드가 판정한 순간에만 쌓인다. 백필 DB 의 state_log 319 행은 전부 백필 시각(2026-10-17 07:38Z) — 과거 에이전트 막대의 끝보다 뒤다. 그 시점 상태를 지어낼 근거가 없다.
- 채택: 막대 = started_at → ended_at(없으면 last_event_at, 살아 있으면 지금). state_log 첫 기록 앞 구간은 「판정 기록 없음」(NONE, 연회색), 그 뒤는 기록된 상태 색. 막대 끝 4 px 에 지금 상태 색. 대시보드를 켜 둔 동안의 새 에이전트부터 상태 색이 채워진다.
- 확인 방법: `tests/test_usage_page.py::test_timeline_segments`. 담당 개발1.

## D-17 서브에이전트 · 워크플로 기록의 `output_tokens` 는 스트리밍 시작값인 경우가 많다 — D-01 반박 (서브에이전트 한정)
- 상태: 확정 (2026-10-20 사람 승인 — 대안 ② 「길이 기반 하한 추정을 별도 열로 `[추정]`」 · `spec.md` v0.3 §6.2 · §3 `usage_event` · `usage_daily` 의 `output_est` · `cost_est_usd` · §2.3 · `problem.md` Q11). 1차 기록: 차단 (아키텍트, 2026-10-17 — DEF-QA1-002)
- 확정: 기록값은 그대로, 의심 요청(output 최대 < 30 · content JSON 길이 합 > 400)에 `output_est` · `cost_est_usd` (spec §6.2). 표기 「추정 보정 (D-17)」. 구현 = 개발1 Task 5 · 6 (계획 `docs/superpowers/plans/2026-10-20-agentdash-v2a.md`). 스키마 열은 Phase 0 Task 1 에서 반영.
- 관찰 (QA1 `outputs/qa1/stream_heuristic.py` — 요청 = 같은 기록 · 같은 requestId, 의심 = output 최대 < 30 이면서 content 블록 JSON 길이 > 400 자, 길이만 잼):
  - QA1 실측 (17:2x): 메인 세션 요청 10,175 중 13 (0.1%) · **서브에이전트 17,299 중 11,840 (68.4%)** · 워크플로 에이전트 85 중 60 (70.6%). 의심 요청의 기록 output 합 121,024 vs text + 도구 입력 길이 ÷ 4 합 4,226,667 → **하한 추정 ≈ 4.1M 출력 토큰 과소** (DB 서브에이전트 출력 합 8.18M 의 절반 규모).
  - 아키텍트 재실행 (웨이브 D, 같은 스크립트): 메인 10,186 중 13 (0.1%) · 서브 17,492 중 11,999 (68.6%) · 워크플로 85 중 60 (70.6%) · 하한 추정 4,138,268.
  - 직접 증거: DEF-QA1-001 의 사본 비교 — 같은 uuid · 같은 내용 길이인데 부모 기록 output 10 vs 포크 사본 178. 서브에이전트 기록에는 최종 usage 줄이 안 남는 경우가 대부분이다.
  - 대체 원천 없음: 부모 기록의 `<task-notification>` `subagent_tokens` 는 마지막 요청의 문맥 크기와 48/58 일치 — 누적 출력이 아니다 (`outputs/qa1/notif_usage.py`).
- 영향: 서브에이전트 · 워크플로 에이전트의 출력 토큰 · 비용(출력 단가 몫)과 그들을 품은 세션 합계(자기 + 자손)가 실제보다 적다. G-07 의 글자 기준(DB = 원천 직접 합)은 깨지지 않는다 — 숫자가 「원천과 같이」 틀린다.
- 사람이 고를 대안:
  1. **「기록상 과소」 표기만** — 숫자는 원천 그대로, 서브 · 워크플로 몫이 든 출력 · 비용 옆에 표기. (지금 임시로 이것)
  2. **길이 기반 추정치를 별도 열로 `[추정]`** — 의심 요청에 text + 도구 입력 길이 ÷ 4 를 하한 추정으로 따로 보여 준다(기록 열은 그대로). 요청별 길이를 수집 때 재야 하므로 `usage_event` 에 열 추가 = spec §3 스키마 변경(정본 수정 필요).
  3. **다른 원천** — 예: 훅(`SubagentStop` · `PostToolUse`) 이나 Claude Code 가 따로 남기는 사용량 기록이 생기면 그것을 쓴다. 지금 기록에서는 찾지 못했다.
- 임시 적용 (① — 결정 전): `core/usage.py` `UNDERCOUNT_KINDS` · `UNDERCOUNT_NOTE = "기록상 과소 (D-17)"`.
  - D-04 (`/usage`, `GET /api/v1/usage`): 서브에이전트 · 워크플로 몫이 섞인 행 · 합계에 `undercount=true` · `undercount_output`(그 몫의 출력), 화면 출력 · 비용 칸 옆 「과소 (D-17)」 · 카드 「기록상 과소 (D-17)」 · CSV 열 `output 기록상 과소 (D-17)`.
  - D-03 (`GET /api/v1/agents/{key}` 의 `workload.own` · `with_descendants` = `usage.totals`): 같은 세 키. 화면 표기는 개발2 소유 — `progress-dev1.md` §3 요청.
  - 숫자는 바꾸지 않는다.
- 요청별 의심 플래그를 `usage_event` 에 두지 않은 이유: 스키마는 spec §3 과 글자 단위로 같아야 한다(G-01 `tests/test_schema.py`) — 열 추가는 정본 변경이라 사람 결정(대안 ②)에 묶인다. 대신 `check_usage_sum` 끝 줄이 표본 세션의 의심 요청 비율을 매번 다시 잰다(길이만).
- 확인 방법: `.venv/bin/python -I outputs/qa1/stream_heuristic.py` · `uv run python src/agentdash/tools/check_usage_sum.py` 끝 줄. 담당 아키텍트(결정) · 개발1(표기) · 개발2(D-03 표기).

## D-18 S1 `busy` 인데 미래 시각 `ScheduleWakeup` 을 걸고 잠든 세션 (QA2 DEF-QA2-004)
- 상태: 확정 (2026-10-20 사람 승인 — `spec.md` v0.3 §4.2 R-03 행 「(`status = idle` 또는 잠잠한 busy) · … `ScheduleWakeup` … 미래 (D-18)」 · 「마지막 assistant 는 마지막 `tool_use` (D-18)」 · `problem.md` Q12). 1차 기록: 가설 (개발2, 2026-10-17 웨이브 D)
- 확정: 아래 채택 규칙이 spec 글자가 되었다. 화면 · API 의 「가설 D-18」 표시 · `D18_NOTE` 는 개발2 Task 9 에서 지운다 (G-23).
- 관찰: 오케스트레이터 세션 `S:2bee9170…` 은 S1 `busy` · pid 살아 있음 · 마지막 기록 뒤 5 분 넘게 새 줄 없음 · 가장 늦은 tool_use 가 `ScheduleWakeup`(깰 시각 미래). spec 글자(R-02b)대로면 STALE 이지만 실제로는 루프가 잠든 것 — D-14 대로 턴 뒤에도 busy 가 남는다.
- 근거: spec §4.1 SLEEPING 정의(「ScheduleWakeup · 루프로 예약된 시각까지 잠듦」) · §13-5 수용 기준(「/loop 세션이 ScheduleWakeup 으로 잠들면 SLEEPING 과 깰 시각」) · §9.2 Stop 행(예약 있으면 SLEEPING 이 미종료 자식 WAITING_CHILD 보다 먼저) · D-14.
- 채택 (`core/state.py` `_session`): S1 busy · 5 분 넘게 기록 없음 · 훅 도구 실행 중 아님 · **가장 늦은 tool_use 가 ScheduleWakeup 이고 깰 시각 > 지금** → `SLEEPING`(규칙 코드 R-03, 근거에 `D-18` · 깰 시각). 순서: R-02a(5 분 안 RUNNING) > 훅 도구 실행 중 RUNNING > **D-18 SLEEPING** > D-14 WAITING_CHILD > R-02b STALE. "마지막 assistant" 는 마지막 tool_use 로 본다(예약 뒤 마지막 인사 텍스트 줄은 DB 에 없고 활동이 아니다 — D-04 와 같은 해석). idle 계열 R-03 도 같은 조건으로 좁혔다.
- 실측: 개발2 백필 DB 에서 그 세션 = SLEEPING R-03 (D-18). QA2 `judge.py`(spec 글자) 는 STALE R-02b(D-14 대안 WAITING_CHILD) — 전수 대조의 남은 불일치 1 건이 이것.
- 테스트: `tests/test_state.py::test_rule_table[D-18 …]` 5 행 · `test_db_wakeup_must_be_last_assistant`. 사람이 spec R-03 을 busy 까지 넓힐지 정한다. 담당 개발2.

## D-19 S1 파일은 있는데 pid 가 죽은 세션 (QA2 DEF-QA2-005)
- 상태: 확정 (2026-10-20 사람 승인 — `spec.md` v0.3 §4.2 「S1 없음 = S1 파일 없음 또는 pid 소멸 (D-19)」 · R-06 · R-07 행 · `problem.md` Q12). 1차 기록: 가설 (개발2, 2026-10-17 웨이브 D)
- 확정: 아래 채택 규칙이 spec 글자가 되었다.
- 관찰: spec R-02a 는 pid 생존을 요구하고 R-02b 는 pid 를 말하지 않으며, R-06/R-07 은 「S1 없음(프로세스 소멸)」. S1 있음 · pid 소멸 · 5 분 안은 어느 규칙에도 안 걸리고, 5 분 뒤는 R-02b 글자로 STALE 이 된다. 지금 실제 S1 3 개는 모두 pid 살아 있어 영향 0.
- 채택 (현재 구현 유지): pid 소멸 = 「S1 없음(프로세스 소멸)」 — R-06(마지막 항목 결과 없는 tool_use → STALE) / R-07(DONE). S1 status · 예약 시각은 보지 않는다. R-01 훅도 SessionEnd 밖에는 쓰지 않는다(Stop 등은 프로세스가 사라진 뒤 의미 없음). 근거 문구 `S1 있음 · pid 소멸 (D-19)`.
- 테스트: `tests/test_state.py::test_rule_table[D-19 …]` 4 행 + 기존 `R-06 pid 소멸`. 사람이 spec R-02b/R-06 문구를 정한다. 담당 개발2.

## D-20 `agent.last_event_at` = 마지막 기록 (모든 줄 종류) · handback 뒤 꼬리 제외 — L-07 마지막 활동을 기록 꼬리 대신 (R8)
- 상태: 확정 (웨이브 D2 정리 담당 — 아키텍트 · 개발1 · 개발2 겸, 2026-10-17). 스키마 변경 없음 (spec §3 11 테이블 그대로).
- 규칙 (`collect/ingest.py` `_ingest_transcript`): timestamp 있는 **모든 줄 종류**(assistant · user · system · attachment …, 포크 사본 제외)의 마지막 시각. 단 `SubagentHandback` tool_use 뒤의 **활동 아닌 줄**(`linker.is_activity` 거짓 — 그 결과 · 첨부 · 마지막 인사 텍스트 · isMeta)은 넣지 않는다; 활동 줄(들어온 메시지 · 새 tool_use)이 오면 다시 모든 줄. 증분 시작 때는 DB 의 가장 늦은 tool_call 이 handback 이고 last_event_at ≤ 그 시각이면 「handback 뒤」로 이어 간다. `started_at` 은 그대로(assistant · user 줄).
- 그래서 `linker._activity` = max(tool_call 마지막 시각, 반환 뒤 last_event_at) — 원천 기록 파일 꼬리 다시 읽기(`record_activity_since`) 삭제. `state.build_ctx` → `linker.return_of` 도 파일을 열지 않는다.
- 근거: spec R-02a · R-09 · R-11 「마지막 · 최근 기록」, QA2 `judge.py` `last_at`(모든 줄). 실측: 재백필 기본 DB 전수 326 대조 불일치 1 (D-18 `S:2bee9170…` 그대로).
- 테스트: `tests/test_model.py` (모든 줄 · handback 뒤 꼬리 · 증분) · `tests/test_linker.py::test_L07_incoming_message_after_handback_wakes_child` · `…ingest_to_linker_rewake_end_to_end`.

## D-21 `last_event_at` ≥ 마지막 usage · tool_call — handback 뒤 사용량 줄은 기록이지만 활동은 아니다 (DEF-QA1-102, D-20 보완)
- 상태: 확정 (웨이브 D3 — 아키텍트 · 개발1, 2026-10-17). 스키마 변경 없음.
- 규칙: `collect/ingest.py` — handback 뒤에도 **사용량 · tool_use 가 있는 assistant 줄**은 `last_event_at` 에 넣는다(활동 아닌 첨부 · 결과 · isMeta 꼬리는 D-20 대로 제외, after_hb 유지). 증분 이어 가기: 마지막 기록이 handback 이하 **또는 handback 뒤 사용량 줄 시각**이면 「handback 뒤」. `core/linker._activity` — `last_event_at` 이 그 에이전트의 사용량 줄 시각과 같으면 다시 깨어난 증거로 보지 않는다(tool_use 가 있었다면 tool_call 이 이미 그 시각).
- 한계: 반환 뒤 들어온 메시지에 tool_use 없이 답만 하고 그 뒤 줄이 없으면 「반환 그대로」 로 본다(QA2 judge 는 다시 깨어남) — 실측 0 건.
- 실측: 개발1 DB 재백필 — `usage_event.at > last_event_at` 에이전트 60 → 0 · 61 행/출력 34,334/$11.5749 → 0 · tool_call 뒤 0. QA2 `judge.py` 전수 328 불일치 전 1 (D-18) → 후 0 (그 순간 오케스트레이터 RUNNING — 유휴면 D-18 1 건). ingest 만 바꾸고 linker 를 그대로 두면 51 (반환 뒤 응답을 깨어남으로 오판) — 그래서 linker 도 함께.
- 테스트: `tests/test_model.py::test_post_handback_billed_reply_*` 2 · `tests/test_linker.py::test_L07_billed_reply_after_handback_is_not_a_rewake`.

## D-22 원천에서 지워진 기록의 에이전트 — DB 는 남기고(Q10), V-01 · V-03 비교에서는 빼고 따로 센다 (G-04 · G-07)
- 상태: 확정 (개발1, 2026-10-21 — 근거 `problem.md:156` Q10 「대시보드 DB 는 원천이 지워져도 집계 숫자를 남긴다」 + 아래 실측. 검사를 느슨하게 하지 않고 분류를 엄밀하게 했다). 1차 기록: 가설 (아키텍트, 2026-10-21 관찰)
- 확정 규칙 (구현 `src/agentdash/tools/check_counts.py` `recorded_paths` · `split_extra`, `src/agentdash/tools/check_usage_sum.py` 표본 선정):
  1. **원천 삭제 보관** = DB 에만 있는 키 중 그 키의 기록(jsonl) 경로가 `src_file` 에 있고 그 경로가 **전부 지금 디스크에 없음**을 확인한 것만. 경로가 기록돼 있지 않거나 하나라도 남아 있으면 「남음」 → G-04 FAIL. 원천에 있는 파일이 DB 에 없으면(빠짐) 그대로 FAIL.
  2. check_counts 출력 행마다 `원천 삭제 보관 N` 을 따로 찍는다 (숨기지 않음).
  3. check_usage_sum 표본은 **원천 파일이 지금 다 있는 세션**(메인 기록 + src_file 에 기록된 그 세션 에이전트 기록 전부 있음)에서만 뽑는다. 선정 규칙 · 후보 수 · 제외 수(전부 지움 · 일부 지움)를 `# 표본 선정` 줄에 찍는다.
  4. 보관 행은 화면(D-04 · D-07)에 계속 나온다 (Q10). check_usage_est (G-24) 의 비율 비교에서는 보관 행을 빼고 `원천 삭제 보관 행 N 비교 제외` 로 찍는다.
- 확정 실측 (2026-10-21 10:15, 원천 읽기만 · `os.path.exists` 만):
  - 기본 DB `data/agentdash.db`: `src_file` 609 행 중 지금 없는 경로 50 (jsonl 27 · meta 19 · 기타 4, 기록 mtime 2026-09-17 ~ 2026-10-18). check_counts 세션 원천 73 · DB 81 · 빠짐 0 · 남음 0 · **원천 삭제 보관 8** · 서브에이전트 235 · 254 · 0 · 0 · **보관 19** · 워크플로 에이전트 6 · 6 · 보관 0 → G-04 PASS (보관 27 = 사라진 jsonl 27). check_usage_sum 후보 71 (토큰 있는 세션 79 중 제외 8 = 전부 지움 8 · 일부 0) · 표본 10/10 PASS.
  - 새로 백필한 dev1 DB `data/agentdash-dev1.db`: 보관 0 · 0 · 0, 후보 71/71 · 표본 10/10 PASS — 같은 표본.
  - 테스트 `tests/test_check_counts.py` 7 (가짜 루트에서 세션 기록을 지우는 시나리오 · 경로 기록 없는 DB 전용 키 FAIL · 경로가 아직 있는 키 FAIL · 빠짐 FAIL · 일부 지운 세션 표본 제외 · 후보 부족 FAIL). 처음 4 FAIL → 구현 뒤 7 PASS.
- 관찰 (`make gate` 2026-10-21 09:46, 기본 DB `data/agentdash.db`):
  - G-04 FAIL — 세션 원천 74 · DB 81 (DB 만 7), 서브에이전트 원천 233 · DB 252 (DB 만 19, 세션 2 곳), 워크플로 에이전트 6 = 6 · 워크플로 1 = 1. **DB 만 있는 26 키 전부 `src_file` 의 그 경로가 디스크에 없다** (26/26). `src_file` 605 행 중 사라진 경로 49 (mtime 2026-09-17 ~ 2026-10-18). 예: `S:cd6db165…` (2026-09-17 기록) · `S:09cc91b1…` 의 서브에이전트 13 (2026-09-18).
  - G-07 FAIL — 표본 10 세션 중 2 개(`09cc91b1` · `cd6db165`)가 바로 그 지워진 세션: 원천 합 0 · DB 합 그대로 (예: 출력 0 vs 1,480,417). 나머지 8 세션은 4 칸 전부 일치 · 소유 불일치 0. 즉 수집 · 중복 제거가 틀린 것이 아니라 표본에 「원천이 이제 없는 세션」 이 들어갔다.
  - 원인 [가설]: Claude Code 가 오래된 기록을 지운다 (`~/.claude/settings.json` 에 `cleanupPeriodDays` 없음 → 기본값). 2026-10-17 1차 EXIT 때는 지워진 기록이 없어 G-04 · G-07 이 PASS 였다.
- 충돌: `problem.md` Q10 「원천이 지워져도 DB 는 숫자를 남긴다」 와 `spec.md` §10 V-01 「원천 파일 수 ↔ agent 행 수 일치」 · V-03 「표본 세션 원천 직접 합 ↔ DB」. 지금 검사기는 DB 의 보관 행을 원천과 그대로 견준다.
- 제안 (개발1 · 사람 확인 — 기준을 낮추지 않는 방향):
  1. `check_counts` (V-01): 「DB 만」 키 중 `src_file` 경로가 전부 사라진 것은 **「원천 삭제 보관 N」** 으로 따로 찍고 비교에서 뺀다. 그 밖의 「DB 만」 · 「빠짐」 은 지금처럼 FAIL. 실측 칸에 보관 수를 늘 보인다(조용히 숨기지 않음).
  2. `check_usage_sum` (V-03): 표본은 **원천 세션 파일이 지금 있는 세션**에서만 뽑는다 (시드 고정 그대로). 원천이 지워진 세션 수를 끝 줄에 따로 적는다.
  3. 보관 행은 화면(D-04 · D-07)에 계속 나온다 — Q10 그대로.
- 확인 방법: 위 두 검사기 수정 뒤 기본 DB `make gate` G-04 · G-07 PASS + 실측 칸 「원천 삭제 보관 26」 · 새로 백필한 DB(보관 0) 에서도 PASS. 담당 개발1 (검사기) · 사람 (Q10 해석 승인).

## D-23 V-12 의심 비율의 모집단 — 「세션 안 requestId 한 번」 (포크 사본 중복 제외)
- 상태: 가설 (개발1, 2026-10-21 웨이브 A — QA1 r4 가 판정)
- 관찰: spec §6.2 V-12 는 QA1 `stream_heuristic.py` 와 「같은 정의」 로 대조한다고 적었다. 그 스크립트는 **기록 파일마다** 요청을 세므로 포크 사본 줄 280 요청이 두 번 들어간다(48.4 %, 12,581/26,002). DB 는 D-02 · DEF-QA1-001 대로 세션 안 requestId 를 한 번만 센다(48.9 %, 12,581/25,722). 파일별 정의로 대조하면 차 0.53 %p 로 FAIL.
- 채택: `check_usage_est` 는 모집단을 check_usage_sum 과 같은 독립 규칙(세션 안 requestId 한 번)으로 세고, 파일별 비율을 같은 줄에 참고로 찍는다. 의심 판정 · 추정 공식(spec §6.2 표)은 그대로 — 바뀐 것은 비율의 분모 · 분자를 세는 단위뿐이다. 허용 차 0.5 %p 도 그대로.
- 실측 (오케스트레이터 재실행, 새 DB `data/agentdash-v2a-verify.db`): DB 48.9 % (12,583/25,730) · 원천 48.9 % · 차 0.00 %p.
- 사람이 정할 것: spec §10 V-12 문구를 「세션 안 requestId 단위」 로 고칠지. 담당 개발1 · 판정 QA1.

## D-24 기본 DB 의 `output_est` 채우기 — 다시 백필하면 원천 삭제 보관 27 키를 잃는다
- 상태: 차단 (오케스트레이터, 2026-10-21 — 사람 결정)
- 관찰: 기본 DB `data/agentdash.db` 는 `init_db` 로 v0.3 열이 붙었지만 기존 행의 `output_est` · `cost_est_usd` 는 NULL 이다(증분 오프셋 뒤만 새로 계산). 값을 채우려면 원천을 처음부터 다시 읽어야 하는데, 새 DB 로 백필하면 원천에서 지워진 기록의 에이전트 27 키(세션 8 · 서브에이전트 19, D-22)의 숫자가 사라진다(Q10 「원천이 지워져도 DB 는 숫자를 남긴다」 와 충돌).
- 대안: ① 새 DB 로 다시 백필 (보관 27 키 손실, 옛 DB 는 `data/` 에 파일로 남김) ② 기본 DB 를 그대로 두고 남아 있는 원천만 오프셋 0 부터 다시 읽어 `output_est` 를 채우는 `make reestimate` 를 만든다(개발1 · 새 명령 = 계획 밖) ③ 그대로 둠 (2026-10-21 이전 요청은 추정 보정 없음, 화면에 표시).
- 게이트 영향 없음 — 실측 게이트는 새로 백필한 DB 로 잰다(goal.md §0.2). 사람이 고를 때까지 기본 DB 는 손대지 않는다.

## D-25 트윈 — 부모가 범위 밖 · 다른 라인 · 순환이면 조상을 끌어오지 않고 반입구 아래에 둔다 (T-tw-1)
- 상태: 가설 (개발2, 2026-10-21 2차-T 웨이브 A — 사람 확인)
- 관찰: spec §5.4 T-02 는 「부모 없는 서브에이전트는 미확인 반입구 아래 1 열」 만 말한다. 실제 24 h 범위에서 STALE 서브에이전트 5 개는 부모(DONE)가 24 h 밖이라 범위에 없다.
- 채택: 범위 밖 부모 · 순환은 그 설비를 반입구 아래 1 열에, 다른 라인의 부모는 `links`(kind=spawn 등)로만 잇는다. 조상을 범위 안으로 끌어오지 않는다 — V-17 「칸 + 접힘 = 범위 안 에이전트 수」 를 지키려고.
- 테스트: `tests/test_twin.py::test_cross_line_parent` · `test_parent_cycle_terminates`. 담당 개발2.

## D-26 트윈 — T-05 는 자손이 전부 끝났을 때만 접는다 (T-tw-2)
- 상태: 가설 (개발2, 2026-10-21)
- 관찰: T-05 는 「자손도 함께 접힌다」 고만 한다. DONE 부모 아래 살아 있는 자손이 있으면 접으면 살아 있는 설비가 숨는다.
- 채택: 끝난 지 30 분 넘었어도 살아 있는 자손이 하나라도 있으면 접지 않는다. 담당 개발2.

## D-27 트윈 — 워크플로는 설비 한 칸, 반입구는 0 열 첫 행 (T-tw-3)
- 상태: 가설 (개발2, 2026-10-21 — spec 내부 어긋남, 사람 확인)
- 관찰: spec §5.4 대응표는 미확인 반입구를 「그 라인의 맨 오른쪽」 이라 하고, T-02 는 부모 없는 서브에이전트를 「반입구 아래 1 열」 이라 한다 — 반입구가 맨 오른쪽이면 그 자식의 1 열과 모순. 워크플로 「묶음 틀」 도 칸 규칙(T-04)과 따로 정의가 없다.
- 채택: T-02 를 따라 반입구 = 0 열(세션과 같은 열) · 그 라인의 첫 반입구 행, 워크플로 = 설비 한 칸(그 에이전트들이 1 열 아래 자식). 사람이 spec §5.4 대응표 문구를 정한다. 담당 개발2.

## D-28 트윈 라인 이름 = 그 프로젝트의 가장 짧은 `project_path` 의 마지막 이름 (DEF-QA1-402)
- 상태: 확정 (2026-10-21 사람 결정 · spec v0.4.1 §5.4 대응표)
- 관찰 (QA1 r5): 라인 이름이 순서 없는 SELECT 의 첫 경로로 정해져 DB 행 순서에 따라 바뀌었다 — T-07 위반. 실제 화면에 「dev」 · 「contracts」(= SongWol QR Platform) 같은 하위 폴더 이름.
- 확정: 경로 중 가장 짧은 것(길이 같으면 사전순), 없으면 `project_key`. T-07 문구에 「DB 행 물리 순서와 무관」 추가. D-02 구성도 프로젝트 라벨도 같은 규칙을 권한다(개발2). 담당 개발2.

## D-29 `~/.claude/settings.json` 변경 (2026-10-21 13:27 KST) — 사람이 Claude Code 설정을 바꿈
- 상태: 확정 (사람 확인 2026-10-21)
- 관찰 (QA2 r5): sha1 `8641eb22e8f5…` → `8a539108c7d4…`, 키 `autoMode` · `theme` · `tui` 등. 훅 항목 PostToolUse 3 · PreToolUse 1 · Stop 1 그대로 · `hook_send.sh` · `agentdash` 0. 이 저장소 코드의 원천 쓰기 경로 0 (QA1 r5 정적 검사).
- 확정: 사람이 직접 바꾼 것 — G-14 위반 아님. 이후 원천 무접촉 기준 sha1 = `8a539108c7d4a2263c92732dbb3b022d99673e04`.

## D-30 트윈 라인 격자 T-08 (DEF-QA2-402)
- 상태: 확정 (2026-10-21 사람 결정 · spec v0.4.1 §5.4 T-08)
- 관찰 (QA2 r5): 넓은 화면에서 라인이 세로로만 쌓여 평면도 오른쪽 ≈ 40 % 가 비고 첫 화면에 라인 1 개.
- 확정: 라인을 평면도 너비에 맞춘 격자로(T-01 순서 왼 → 오른 · 위 → 아래), API 에 `width` 매개변수. 담당 개발2.

## D-31 트윈 화면이 보내는 `width` = 평면도 카드 너비 ÷ 0.8 (T-08 해석, DEF-QA2-402)
- 상태: 가설 (개발2, 2026-10-21 웨이브 D — 사람 확인)
- 관찰: spec T-08 「width = 평면도 너비 px」 를 카드 실제 px 로 보내면 1400 px 창(카드 ≈ 866 px)에서 실제 라인(폭 504) 2 개 + 간격 = 1032 가 안 들어가 1 열 — 오른쪽이 비는 QA2-402 가 그대로.
- 채택: 화면은 카드 너비 ÷ 0.8(맞춤 배율 하한)을 보낸다 → 1083 · 2 열 · 맞춤 0.73. 서버 규칙(T-08)은 그대로, API 기본 1400. 멈춤 의심 설비의 경과는 「마지막 기록부터」 (DEF-QA2-401). 담당 개발2.

## D-32 트윈 — 끝난 설비(DONE · FAILED)는 「지금 도구」 를 비운다 (DEF-QA2-404 · DEF-QA1-501)
- 상태: 가설 (오케스트레이터, 2026-10-21 — 사람 확인)
- 관찰: spec §5.4 는 「지금 도구 = 결과 없는 마지막 tool_call」 이라고만 하고 끝난 설비를 빼지 않는다. 끝난 설비에 결과 없는 마지막 도구가 남아 있으면 지금 쓰는 것처럼 보인다(QA2 r5). 개발2 가 `960f76b` 에서 DONE · FAILED 는 `tool` · `target` = null 로 비웠다. 실제 DB 영향: since=all 1 설비 · 24 h 0 (QA1 r6).
- 채택: 끝난 설비는 「지금」 이 없으므로 비운다. 마지막 도구는 D-03 도구 타임라인에서 본다. 사람이 spec §5.4 문구에 반영할지 정한다. 담당 개발2.

## D-33 트윈 — `ended_at` 없는 DONE 설비의 경과 표기 (DEF-QA2-502)
- 상태: 가설 (오케스트레이터, 2026-10-21 — 사람 확인)
- 관찰 (QA2 r6): `S:fc3908a3`(00 PM Agent) DONE · ended_at 없음 → 새 백필 직후 「끝남 · 1분 8초」 (state_since 기준) 로 방금 끝난 것처럼 보인다. last_event_at 은 1 시간 56 분 전.
- 채택: DONE · FAILED 이고 ended_at 이 없으면 `last_ago_s` 로 「끝남 · 기록 n 전」. 담당 개발2.

## D-34 트윈 — 좁은 화면 맞춤 배율 하한 (DEF-QA2-503)
- 상태: 가설 (오케스트레이터, 2026-10-21 — 사람 확인)
- 관찰 (QA2 r6): 390 px 에서 「맞춤」 배율 0.57 → 글자 5.7 ~ 7.5 px, 확대 없이는 읽을 수 없다.
- 채택: 첫 표시 · 「맞춤」 배율 하한을 글자 ≥ 10 px 가 되는 값(배율 ≈ 0.85)으로 두고, 넘치는 부분은 평면도 카드 안에서 세로로 이동한다(spec §7.3 「자기 카드 안에서만 이동」 그대로). 페이지 가로 스크롤 0 유지. 담당 개발2.
