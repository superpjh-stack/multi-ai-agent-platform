"""collect/hooks_rx — 화이트리스트 · detail (spec.md §9.2 · §3 tool_call.target). DEF-QA1-007."""

from __future__ import annotations

import json

from agentdash.collect import hooks_rx as H

SECRET = "SECRET-BODY-abc"


def _pre(tool: str, ti: dict) -> dict:
    return {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": tool, "tool_input": ti}


def test_url_target_is_host_only():
    p = H.filter_payload(_pre("WebFetch", {"url": f"https://h.example:8443/a/b/{SECRET}?token={SECRET}#f{SECRET}",
                                          "prompt": SECRET}))
    assert H.target_of(p) == "h.example"
    assert SECRET not in json.dumps(p) and SECRET not in H.detail_of(p)
    assert json.loads(H.detail_of(p))["target"] == "h.example"


def test_url_without_host_kept_none():
    p = H.filter_payload(_pre("WebFetch", {"url": f"not a url {SECRET}"}))
    assert H.target_of(p) is None
    assert SECRET not in json.dumps(p)


def test_file_path_target_kept():
    p = H.filter_payload(_pre("Write", {"file_path": "/a/b.txt", "content": SECRET}))
    assert H.target_of(p) == "/a/b.txt" and SECRET not in json.dumps(p)
