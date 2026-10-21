"""QA2 r5 G-33 가짜 루트 도우미 — Claude Code 가 쓰는 순서를 흉내 낸다 (저장소 안 data/qa2-fake-twin/ 에만 씀).
본문 없음 — 사용자 줄은 자리표 "x", 도구 입력은 빈 dict, 이름 · id · 시각 · 숫자만.

    uv run python -I outputs/qa2/twin_driver_r5.py <repo> init
    uv run python -I outputs/qa2/twin_driver_r5.py <repo> s1 <pid> idle|busy   # S1 (프로세스 시작 = idle, 프롬프트 = busy)
    uv run python -I outputs/qa2/twin_driver_r5.py <repo> prompt              # 세션 transcript 첫 줄 (user 프롬프트 + assistant Read)
    uv run python -I outputs/qa2/twin_driver_r5.py <repo> spawn               # 부모 assistant Agent×2 → 자식 meta + 첫 줄
    uv run python -I outputs/qa2/twin_driver_r5.py <repo> tick <n>            # 자식 n 에 활동 줄 1
    uv run python -I outputs/qa2/twin_driver_r5.py <repo> handback <n>        # 자식 n SubagentHandback → 부모 task-notification completed

실제 Claude Code 순서: 프로세스 시작 시 sessions/<pid>.json(idle) → 첫 프롬프트에 transcript 생김 + S1 busy →
Agent tool_use 줄 → subagents/agent-<id>.meta.json → agent-<id>.jsonl. 반환: 자식 SubagentHandback → 부모 <task-notification>.
"""
import json, os, sys, time

repo, cmd = sys.argv[1], sys.argv[2]
root = os.path.join(repo, "data", "qa2-fake-twin")
assert os.path.realpath(root).startswith(os.path.realpath(repo) + "/data/")
home = os.path.join(root, "claude_home"); agents = os.path.join(root, "agents_root")
SID = "99999999-aaaa-bbbb-cccc-000000000001"
CWD = "/tmp/qa2-twin-r5"
proj = os.path.join(home, "projects", "-tmp-qa2-twin-r5")
sess_file = os.path.join(proj, SID + ".jsonl")
subdir = os.path.join(proj, SID, "subagents")
AIDS = {1: "a9900000000000001", 2: "a9900000000000002"}


def now_iso():
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def app(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


def asst(uuid, tools, sid=SID, agent=None, out=50):
    d = {"type": "assistant", "uuid": uuid, "parentUuid": None, "timestamp": now_iso(), "sessionId": sid, "cwd": CWD,
         "message": {"model": "claude-opus-5", "content": [{"type": "tool_use", "id": i, "name": n, "input": {}} for i, n in tools],
                     "usage": {"input_tokens": 1, "output_tokens": out}}, "requestId": "req_" + uuid}
    if agent:
        d.update(isSidechain=True, agentId=agent)
    return d


if cmd == "init":
    for d in ("00 PM Agent", "01 Analyze Agent", "02 Design Agent", "03 UI Agent", "04 QA Agent", "05 Open Agent",
              "06 Coding Agent", "08 AI Agent Making Agent"):
        os.makedirs(os.path.join(agents, d, "outputs"), exist_ok=True)
    os.makedirs(os.path.join(home, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(home, "projects"), exist_ok=True)
elif cmd == "s1":
    pid, status = int(sys.argv[3]), sys.argv[4]
    p = os.path.join(home, "sessions", f"{pid}.json")
    ms = int(time.time() * 1000)
    started = json.load(open(p))["startedAt"] if os.path.exists(p) else ms
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"pid": pid, "sessionId": SID, "cwd": CWD, "startedAt": started, "version": "2.1.301", "kind": "interactive",
                   "entrypoint": "cli", "name": "qa2-twin-r5", "status": status, "updatedAt": ms, "statusUpdatedAt": ms}, f)
    os.replace(tmp, p)
elif cmd == "prompt":
    os.makedirs(proj, exist_ok=True)
    app(sess_file, {"type": "user", "uuid": "p0", "parentUuid": None, "timestamp": now_iso(), "sessionId": SID, "cwd": CWD,
                    "message": {"role": "user", "content": "x"}})
    app(sess_file, asst("p1", [("toolu_qr1", "Read")]))
elif cmd == "spawn":
    app(sess_file, asst("p2", [("toolu_qs1", "Agent"), ("toolu_qs2", "Agent")]))
    os.makedirs(subdir, exist_ok=True)
    for n, aid in AIDS.items():
        with open(os.path.join(subdir, f"agent-{aid}.meta.json"), "w") as f:
            json.dump({"agentType": "general-purpose", "description": f"qa2 r5 worker {n}", "toolUseId": f"toolu_qs{n}",
                       "spawnDepth": 1, "requestShape": "background"}, f)
    for n, aid in AIDS.items():
        app(os.path.join(subdir, f"agent-{aid}.jsonl"), asst(f"w{n}a", [(f"toolu_w{n}a", "Read")], agent=aid, out=200))
elif cmd == "tick":
    n = int(sys.argv[3]); aid = AIDS[n]
    app(os.path.join(subdir, f"agent-{aid}.jsonl"), asst(f"w{n}{int(time.time()*1000)}", [(f"toolu_w{n}{int(time.time())}", "Grep")], agent=aid, out=120))
elif cmd == "handback":
    n = int(sys.argv[3]); aid = AIDS[n]
    app(os.path.join(subdir, f"agent-{aid}.jsonl"), asst(f"w{n}h", [(f"toolu_w{n}h", "SubagentHandback")], agent=aid, out=30))
    app(sess_file, {"type": "user", "uuid": f"n{n}", "parentUuid": None, "timestamp": now_iso(), "sessionId": SID,
                    "message": {"role": "user", "content": f"<task-notification><task-id>{aid}</task-id><tool-use-id>toolu_qs{n}</tool-use-id><status>completed</status></task-notification>"}})
else:
    sys.exit("unknown cmd")
print(cmd, now_iso())
