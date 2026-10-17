#!/usr/bin/env python
"""QA1 — 훅 수신 화이트리스트에 본문 표지(SECRET-BODY)를 넣은 합성 페이로드를 먹여 detail 에 남는지 본다. DB 안 씀.
    uv run python outputs/qa1/hook_payload.py"""
import json
from agentdash.collect import hooks_rx as H
B = "SECRET-BODY-" + "x" * 500
cases = {
  "UserPromptSubmit": {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": B},
  "PreToolUse Bash": {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Bash", "tool_use_id": "t",
                      "tool_input": {"command": B, "description": "짧은 설명"}},
  "PreToolUse Write": {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Write",
                       "tool_input": {"file_path": "/a/b.txt", "content": B}},
  "PostToolUse": {"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Read", "tool_response": {"output": B},
                  "tool_input": {"file_path": "/a"}},
  "SubagentStop": {"hook_event_name": "SubagentStop", "session_id": "s", "agent_id": "a1", "last_assistant_message": B},
  "Notification": {"hook_event_name": "Notification", "session_id": "s", "message": "SECRET-BODY-msg " + "y" * 300,
                   "notification_type": "permission_prompt"},
  "WebFetch url": {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "WebFetch",
                   "tool_input": {"url": "https://h.example/p?token=SECRET-BODY-abc", "prompt": B}},
  "reason 긴 값": {"hook_event_name": "SessionEnd", "session_id": "s", "reason": B},
  "nested 키": {"hook_event_name": "Stop", "session_id": "s", "transcript_path": "/x/agent-abc.jsonl", "cwd": B},
}
for name, raw in cases.items():
    p = H.filter_payload(raw)
    d = H.detail_of(p)
    leak_detail = "SECRET-BODY" in d
    kept_body_len = max((len(v) for v in p.values() if isinstance(v, str)), default=0)
    print(f"{name:18s} detail {len(d):3d} 자 · detail 에 본문 표지 {leak_detail} · 필터 뒤 최장 문자열 {kept_body_len} · 키 {sorted(p)}")
