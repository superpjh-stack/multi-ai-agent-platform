"""QA2 자기 관찰 폴러 — /api/v1/agents?project=… 를 2 초마다 (r3) 읽어 키 · 상태 · 규칙만 남긴다 (본문 없음)."""
import json, sys, time, urllib.request as _u  # noqa: 로컬 127.0.0.1 만
from datetime import datetime
URL = "http://127.0.0.1:8095/api/v1/agents?project=-Users-gerardo92-Desktop-AI-Coding-Multi-agent-Dashboard"
OUT = sys.argv[1]
prev = {}
while True:
    try:
        d = json.load(_u.urlopen(URL, timeout=5))
        now = datetime.now().strftime("%H:%M:%S")
        cur = {a["agent_key"]: (a["state"], a.get("state_reason")) for a in d["agents"]}
        with open(OUT, "a") as f:
            for k, v in cur.items():
                if prev.get(k) != v:
                    f.write(f"{now}  {k}  {prev.get(k, ('-', '-'))[0]} -> {v[0]} ({v[1]})\n")
            f.write(f"{now}  tick n={len(cur)}\n")
        prev = cur
    except Exception as e:  # 서버 꺼짐
        with open(OUT, "a") as f:
            f.write(f"{datetime.now():%H:%M:%S}  error {type(e).__name__}\n")
    time.sleep(2)
