# 결정 대장 (decisions.md)

상태: `확정` (근거 파일 · 줄과 함께) / `가설` (확인 전 기본값) / `가설 반박` (대안 규칙으로 진행) / `차단` (사람 확인 필요 — 화면에 `미확정 (D-nn)`).
`gate.py` 는 `상태: 차단` 인 D-번호 본문이 언급한 G-nn 을 BLOCKED 로 표시한다. 본문을 붙여 넣지 않는다 — 숫자 · 경로만.

## D-01 `requestId` 같은 줄의 중복 여부 (A3)
- 상태: 가설
- 기본값: 같은 `requestId` 는 usage 한 번만 센다.
- 확인 방법: 표본 세션에서 중복 제거 전후 토큰 합 비교 (G-07 · V-03). 담당 개발1.

## D-02 자식 기록의 부모 재기록 여부 (A4)
- 상태: 가설
- 기본값: 없음 → 이중 계산 없음 (세션 합계 = 자기 + 자손).
- 확인 방법: 부모 · 자식 토큰 합 비교. 담당 개발1.

## D-03 `thinking_tokens ⊂ output_tokens`
- 상태: 가설
- 기본값: 포함 (비용 공식에서 따로 더하지 않는다, `spec.md` §6.1).
- 확인 방법: 표본 메시지 대조. 담당 개발1.

## D-04 `SubagentHandback` ↔ 자식 종료 1:1 (L-07)
- 상태: 가설
- 기본값: 1:1.
- 확인 방법: 260 회 띄움 · 220 회 반환의 차이 40 건 원인 조사 (G-10 · R-08). 담당 개발2.

## D-05 훅 페이로드의 서브에이전트 식별 필드
- 상태: 가설
- 기본값: `transcript_path` 로 붙인다 (`spec.md` §9.2).
- 확인 방법: 공식 문서 → 사람이 훅을 설치한 뒤 실측 (설치 전 `미검증`, goal.md §2.6). 담당 개발2.

## D-06 `active_seconds` 간격 기준
- 상태: 가설
- 기본값: 5 분 (연속 기록 간격 ≤ 5 분 구간의 합).
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
- 상태: 가설
- 관찰: `~/.claude/sessions/*.json` 3 개 중 1 개가 `status: "shell"` (version 2.1.302). `spec.md` §2.1 · §4.2 R-02a~R-05 는 `busy`/`idle` 만 다룬다.
- 기본값(제안): `shell` 은 R-02 ~ R-05 어디에도 걸리지 않으므로 판정을 지어내지 말고 상태 근거에 원래 값을 남긴 채 `WAITING_INPUT`(R-05 와 같은 대기)으로 볼지, 별도 규칙이 필요한지 개발2 가 실측(무엇을 할 때 `shell` 이 되는지)으로 정한다. 정하기 전에는 상태 근거에 `S1 status=shell (D-09)` 를 표시.
- 담당: 개발2 (G-09).

## D-10 워크플로 · 손자 메타 형식
- 상태: 가설
- 관찰: 워크플로 에이전트 `.meta.json` 에는 `toolUseId` 가 없고 `agentType: workflow-subagent` · `workflowPhase` 가 있다. 깊이 2 포크 메타에는 `parentAgentId` · `isFork` · `model` 이 있다. 워크플로 폴더에 `journal.jsonl` · `scripts/` 가 함께 있다. 세션 폴더에 `custom-title.json` 이 있는 경우가 있다.
- 기본값(제안): L-03 은 폴더(`subagents/workflows/wf_<id>/`)로 워크플로 노드에 붙이고, L-02 는 `parentAgentId` 가 있으면 그것을 1순위로 쓴 뒤 `toolUseId` 대조로 확인. `scripts/` 는 본문이므로 읽지 않는다.
- 담당: 개발2 (G-10). 픽스처: `tests/fixtures/2.1.295/`.

## D-11 transcript 줄 종류 — `assistant` · `user` 밖의 줄
- 상태: 가설
- 관찰: 이 저장소 세션 468 줄 중 `assistant` 86 · `user` 62 외에 `api-request-blob` 64 · `attachment` 53 · `api-request` 33 · `last-prompt` 30 · `mode` 30 · `permission-mode` 30 · `atis-latch` 30 · `ai-title` 29 · `system` 11 · `file-history-*` 9 · `api-request-shape` 1. **`api-request-blob` 줄의 `message.content` 에도 `tool_use` 블록이 있다**(43 건).
- 기본값(제안): 도구 호출 · 토큰은 `type == "assistant"` 줄에서만 센다(요청 사본인 `api-request-blob` 을 세면 이중 계산). 모르는 종류는 무시하되 `parse_error` 로 올리지 않는다(필수 필드가 없는 assistant/user 줄만 `parse_error`).
- 담당: 개발1 (G-02 · G-07).

## D-12 원천 규모 기준값 (계속 늘어난다)
- 상태: 확정 (2026-10-17 16:12 실측, `goal.md` §9 명령)
- 메인 세션 77 · 서브에이전트(워크플로 제외) 233 · 워크플로 에이전트 6 · 프로젝트 폴더 43. `spec.md` · `intro.md` 의 232 · 41 보다 늘었다 — 백필 대조(V-01)는 같은 시각에 다시 센다.
