"""QA2 r4 알림 E2E 용 가짜 루트 (저장소 안 data/qa2-fake/). 세션 2 개, S1 = 살아 있는 sleep pid, status idle/busy.
본문 없음 — 빈 tool_use 하나짜리 assistant 줄만.
    uv run python -I outputs/qa2/make_fake_r4.py <repo> <sleep_pid>
"""
import json, os, sys, time
repo, pid = sys.argv[1], int(sys.argv[2])
root = os.path.join(repo, "data", "qa2-fake")
home = os.path.join(root, "claude_home"); agents = os.path.join(root, "agents_root")
assert os.path.realpath(root).startswith(os.path.realpath(repo) + "/data/")
for d in ("00 PM Agent", "01 Analyze Agent", "02 Design Agent", "03 UI Agent", "04 QA Agent", "05 Open Agent", "06 Coding Agent", "08 AI Agent Making Agent"):
    os.makedirs(os.path.join(agents, d, "outputs"), exist_ok=True)
proj = os.path.join(home, "projects", "-tmp-qa2-alert-proj"); os.makedirs(proj, exist_ok=True)
os.makedirs(os.path.join(home, "sessions"), exist_ok=True)
now_ms = int(time.time() * 1000)
iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - 20))
for i, status in ((1, "idle"), (2, "busy")):
    sid = f"bbbbbbbb-0000-0000-0000-00000000000{i}"
    with open(os.path.join(proj, f"{sid}.jsonl"), "w") as f:
        f.write(json.dumps({"type": "assistant", "uuid": f"q{i}", "parentUuid": None, "timestamp": iso, "sessionId": sid,
                            "cwd": "/tmp/qa2-alert-proj", "message": {"model": "claude-opus-5", "content": [
                                {"type": "tool_use", "id": f"toolu_q{i}", "name": "Read", "input": {}}],
                                "usage": {"input_tokens": 1, "output_tokens": 1}}, "requestId": f"req_q{i}"}) + "\n")
        f.write(json.dumps({"type": "user", "uuid": f"r{i}", "parentUuid": f"q{i}", "timestamp": iso, "sessionId": sid,
                            "message": {"content": [{"type": "tool_result", "tool_use_id": f"toolu_q{i}", "content": "ok"}]}}) + "\n")
    with open(os.path.join(home, "sessions", f"{pid}{i}.json"), "w") as f:
        json.dump({"pid": pid, "sessionId": sid, "cwd": "/tmp/qa2-alert-proj", "startedAt": now_ms, "version": "2.1.301",
                   "kind": "interactive", "entrypoint": "cli", "name": f"qa2-alert-{i}", "status": status,
                   "updatedAt": now_ms, "statusUpdatedAt": now_ms}, f)
print(root)
