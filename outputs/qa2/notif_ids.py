"""task-notification 의 id 칸만 뽑는다 (본문 없음). 인자: agentId toolUseId"""
import glob, json, os, re, sys
aid, tuid = sys.argv[1], sys.argv[2]
NOTIF = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
TAG = {k: re.compile(rf"<{k}>([^<]{{0,80}})</{k}>") for k in ("tool-use-id", "status", "task-id")}
for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")) + glob.glob(os.path.expanduser("~/.claude/projects/*/*/subagents/agent-*.jsonl")):
    with open(p, "rb") as f:
        raw = f.read()
    if aid.encode() not in raw:
        continue
    for ln in raw.splitlines():
        if b"task-notification" not in ln or aid.encode() not in ln:
            continue
        d = json.loads(ln)
        s = json.dumps(d.get("message", {}).get("content"), ensure_ascii=False)
        s = s.encode().decode("unicode_escape", errors="ignore") if "\\u003c" in s else s
        for m in NOTIF.finditer(json.loads(json.dumps(s))):
            b = m.group(1)
            g = {k: (t.search(b).group(1) if t.search(b) else None) for k, t in TAG.items()}
            print(os.path.basename(p)[:20], d.get("type"), d.get("timestamp"), "tool-use-id==spawn" if g["tool-use-id"] == tuid else f"tool-use-id={g['tool-use-id']}", "task-id==agent" if g["task-id"] == aid else f"task-id={g['task-id']}", g["status"])
