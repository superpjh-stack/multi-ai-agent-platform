# 픽스처 — Claude Code 2.1.295

`scripts/make_fixture.py` 가 실제 기록(읽기만)에서 만든 사본이다. **손으로 고치지 않는다** — 다시 만들려면 `make fixtures`.

- 허용 키(구조 · id · 시각 · 모델 · 도구 이름 · 경로) 밖의 문자열 값은 전부 `"<redacted>"` 이다.
- 설명류(`description` · `workflowName` · `title` · `label` · `workflowPhase`)와 S1 `name` 은 앞 40 자만 남겼다.
- jsonl 은 앞 200 줄 + 부모 연결에 필요한 줄(고른 자식의 `toolUseId` · 워크플로 id 가 나오는 줄)만 남겼다. 아래 표의 `원래 줄` ≠ `남긴 줄` 이면 자른 것이다.
- 줄 사이 `parentUuid` 사슬은 잘린 곳에서 끊긴다 (앞 줄이 빠진 연결 줄). 파서 테스트는 이것을 허용해야 한다.
- 옮기지 않은 것: `tool-results/`(S7 본문) · `workflows/*/scripts/`(워크플로 스크립트 본문) · `custom-title.json` · `memory/`.
- 검사: `uv run python scripts/check_fixtures_redacted.py` (G-13).

| 파일 (원천 루트 기준) | 원천 | 원래 줄 | 남긴 줄 | 처리 |
|---|---|---|---|---|
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37.jsonl` | S2 세션 (워크플로) | 8444 | 206 | 자름 — 앞 200 줄 + 연결 줄 6 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/workflows/wf_fa635efe-270.json` | S6 워크플로 실행 기록 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a5de9442449dd9e3f.jsonl` | S5 워크플로 에이전트 | 75 | 75 | 전부 — 앞 75 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a5de9442449dd9e3f.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a7186b4827d0cb63f.jsonl` | S5 워크플로 에이전트 | 59 | 59 | 전부 — 앞 59 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a7186b4827d0cb63f.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a87cfd3e838743964.jsonl` | S5 워크플로 에이전트 | 127 | 127 | 전부 — 앞 127 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a87cfd3e838743964.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a97eb4e95ed253da0.jsonl` | S5 워크플로 에이전트 | 100 | 100 | 전부 — 앞 100 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-a97eb4e95ed253da0.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-aa0022308bc00552d.jsonl` | S5 워크플로 에이전트 | 75 | 75 | 전부 — 앞 75 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-aa0022308bc00552d.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-ab4335ccd7f8fed44.jsonl` | S5 워크플로 에이전트 | 63 | 63 | 전부 — 앞 63 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/agent-ab4335ccd7f8fed44.meta.json` | S5 워크플로 에이전트 | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/workflows/wf_fa635efe-270/journal.jsonl` | S5 워크플로 부속 | 13 | 13 | 전부 — 앞 13 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/agent-aca12685adbb11b9c.meta.json` | S4 meta (깊이 1, 손자의 부모) | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/agent-aca12685adbb11b9c.jsonl` | S3 서브에이전트 (깊이 1) | 74 | 74 | 전부 — 앞 74 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/agent-a76932516fc410131.meta.json` | S4 meta (깊이 2) | — | — | JSON 전체 (본문 지움) |
| `projects/-Users-gerardo92-Desktop-AI-Coding-Standard-Data-Hub/8f3a6abd-0740-4164-9188-e5ac6af4cd37/subagents/agent-a76932516fc410131.jsonl` | S3 서브에이전트 (깊이 2) | 149 | 149 | 전부 — 앞 149 줄 + 연결 줄 0 · 깨진 줄 제외 0 · 쓰는 중 마지막 줄 제외 0 |
