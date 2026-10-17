# 결정 대장 (decisions.md)

상태: `확정` (근거 파일 · 줄과 함께) / `가설` (확인 전 기본값) / `가설 반박` (대안 규칙으로 진행) / `차단` (사람 확인 필요 — 화면에 `미확정 (D-nn)`).
`gate.py` 는 `상태: 차단` 인 D-번호 본문이 언급한 G-nn 을 BLOCKED 로 표시한다. 본문을 붙여 넣지 않는다 — 숫자 · 경로만.

## D-01 `requestId` 같은 줄의 중복 여부 (A3)
- 상태: 확정 (개발1, 2026-10-17 실측 — 원천 jsonl 318 개 읽기만)
- 기본값: 같은 `requestId` 는 usage 한 번만 센다.
- 근거: requestId 있는 assistant 줄 54,708 중 같은 파일 안 같은 requestId 재등장 27,540 줄(내용 블록마다 한 줄). 그중 usage 가 다른 묶음 2,242 — 다른 칸은 `output_tokens` · `output_tokens_details` · `server_tool_use` · `iterations` · `speed` 뿐(입력 · 캐시는 같음)이고 2,242/2,242 에서 output 이 단조 증가 → 스트리밍 중간본. 규칙: (agent_key, requestId) 한 행, output_tokens 가 가장 큰 줄(최종본)을 남긴다 (`model.add_usage`). 표본 10 세션에서 중복 제거로 빠진 출력 토큰 7,628,314 (`check_usage_sum` 끝 줄). requestId 없는 assistant 줄 66 은 전부 `<synthetic>`.
- 확인 방법: 표본 세션에서 중복 제거 전후 토큰 합 비교 (G-07 · V-03). 담당 개발1.

## D-02 자식 기록의 부모 재기록 여부 (A4)
- 상태: 가설 반박 (개발1, 2026-10-17 실측) → 대안 규칙으로 진행
- 기본값: 없음 → 이중 계산 없음 (세션 합계 = 자기 + 자손).
- 근거: 부모가 자식 usage 를 다시 적는 경우는 없다(일반 서브에이전트 · 워크플로 에이전트와 부모 사이 공유 requestId 0). 그러나 **포크(`isFork`) 26 개는 전부 부모 기록 줄을 uuid · requestId · 시각 그대로(agentId 만 바꿔) 맨 앞에 다시 적는다** — 사본 1,142 줄(assistant 455), 여러 파일에 걸친 requestId 137 개가 전부 포크 관련. 또 포크 26 개 모두 띄운 호출(부모 assistant 의 tool_use 줄)을 **새 uuid · 같은 requestId** 로 한 줄 더 적는다(16 개는 첫 assistant, 10 개는 사본 끝).
- 대안 규칙: 포크 기록에서 부모 파일(`parentAgentId` 있으면 그 에이전트, 없으면 세션 메인)에 같은 uuid 가 있는 줄과 부모 assistant 와 requestId 가 같은 assistant 줄은 부모 몫 → 토큰 · 도구 호출로 세지 않는다 (`collect/ingest.py`). 결과: 백필 DB 에서 두 에이전트에 걸친 requestId 0 (`check_usage_sum` 「세션 안 requestId 중복 0」), 세션 합계 = 자기 + 자손.
- 확인 방법: 부모 · 자식 토큰 합 비교. 담당 개발1.

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
- 상태: 가설
- 기본값: `data/` 제외, 스크린샷(`outputs/e2e/*.png`)은 커밋하지 않음. Phase 0 의 `.gitignore` 가 이대로다(`data/` · `.env` · `.venv/` · `__pycache__/` · `outputs/e2e/*.png`).
- 확인 방법: 사람 확인.

## D-08 Haiku 5.5 캐시 읽기 단가 (`[추정: 0.1 배]`)
- 상태: 가설
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
- 상태: 가설 (개발1 제안, 사람 확인 대기 — 차단 아님)
- 관찰: `spec.md` §3.1 은 세션 이름을 "S1 `name` → 첫 사용자 메시지 앞 40 자 → 프로젝트 폴더 마지막 이름" 으로 정하지만, 첫 사용자 메시지는 프롬프트 본문이다(CLAUDE.md 「본문을 저장 · 복사하지 않는다」 와 충돌). 기록에는 `agent-name` 줄(1,078 줄, `agentName` = S1 `name` 과 같은 꼴의 이름)이 있다.
- 기본값: S1 `name` → 그 세션 기록의 마지막 `agent-name` → `cwd` 마지막 이름(없으면 프로젝트 폴더명). 첫 사용자 메시지는 읽지 않는다 (`collect/ingest.py`).
- 담당: 개발1. 사람이 spec 쪽을 정하면 따른다.

## D-14 S1 `busy` 가 턴이 끝난 뒤에도 남는다 (A1 `sessions/*.json` status 갱신)
- 상태: 가설 반박 (개발2, 2026-10-17 관찰 1 건) → 대안 규칙으로 진행
- 관찰: 오케스트레이터 세션(이 루프)의 S1 은 `status: busy` · `updatedAt` 15:58 그대로인데, 기록 마지막 줄은 16:16 의 `system/turn_duration`(턴 끝)이고 그 뒤 새 줄이 없었다. 그동안 그 세션이 띄운 백그라운드 서브에이전트 2(개발1 · 개발2)가 실행 중이었다. 즉 S1 `busy` 는 "모델이 지금 생각 중" 이 아니라 백그라운드 자식 작업까지 포함해 남는다 — spec §4.2 R-02b 를 그대로 쓰면 자식을 기다리는 세션이 5 분 뒤 `STALE` 로 오판된다.
- 대안 규칙 (`core/state.py` `_session`): S1 `busy` · 5 분 넘게 기록 없음 · 훅 도구 실행 중 아님이어도 **미종료 백그라운드 자식(RUNNING · WAITING_* — STALE 자식은 빼고) ≥ 1** 이면 `WAITING_CHILD`(규칙 코드 R-04, 근거에 `S1 status=busy · 미종료 백그라운드 자식 N · D-14`). 자식이 없으면 spec 대로 R-02b `STALE`.
- 테스트: `tests/test_state.py::test_rule_table[R-04 busy · 턴 끝 · 자식 (D-14)]` 외 1. 실측: 개발2 백필 DB 에서 그 세션 = WAITING_CHILD R-04. 사람이 spec R-02b 를 고칠지 정한다. 담당 개발2.
