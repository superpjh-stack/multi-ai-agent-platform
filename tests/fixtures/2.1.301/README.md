# 픽스처 — Claude Code 2.1.301

`scripts/make_fixture.py` 가 실제 기록(읽기만)에서 만든 사본이다. **손으로 고치지 않는다** — 다시 만들려면 `make fixtures`.

- 허용 키(구조 · id · 시각 · 모델 · 도구 이름 · 경로) 밖의 문자열 값은 전부 `"<redacted>"` 이다.
- 설명류(`description` · `workflowName` · `title` · `label` · `workflowPhase`)와 S1 `name` 은 앞 40 자만 남겼다.
- jsonl 은 앞 200 줄 + 부모 연결에 필요한 줄(고른 자식의 `toolUseId` · 워크플로 id 가 나오는 줄)만 남겼다. 아래 표의 `원래 줄` ≠ `남긴 줄` 이면 자른 것이다.
- 줄 사이 `parentUuid` 사슬은 잘린 곳에서 끊긴다 (앞 줄이 빠진 연결 줄). 파서 테스트는 이것을 허용해야 한다.
- 옮기지 않은 것: `tool-results/`(S7 본문) · `workflows/*/scripts/`(워크플로 스크립트 본문) · `custom-title.json` · `memory/`.
- 검사: `uv run python scripts/check_fixtures_redacted.py` (G-13).

| 파일 (원천 루트 기준) | 원천 | 원래 줄 | 남긴 줄 | 처리 |
|---|---|---|---|---|
| `projects/-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard/2bee9170-9e95-4e4e-873d-8490f228ad20.jsonl` | S2 세션 | 468 | 204 | 자름 — 앞 200 줄 + 연결 줄 4 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `sessions/85955.json` | S1 sessions/*.json | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard/2bee9170-9e95-4e4e-873d-8490f228ad20/subagents/agent-ae52277140e6732bc.meta.json` | S4 meta (깊이 1) | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard/2bee9170-9e95-4e4e-873d-8490f228ad20/subagents/agent-ae52277140e6732bc.jsonl` | S3 서브에이전트 (깊이 1) | 139 | 139 | 전부 — 앞 139 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
