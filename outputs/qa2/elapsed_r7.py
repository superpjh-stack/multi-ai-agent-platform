"""QA2 r7 DEF-QA2-502 D-33 — /api/v1/twin 설비 시간 키를 DB 값(mode=ro)으로 손계산 대조. 이름 · 키 · 시각 · 숫자만 찍는다."""
import json, sqlite3, sys, time, urllib.parse
from datetime import datetime, timezone
import http.client
db, port = sys.argv[1], int(sys.argv[2])
c = http.client.HTTPConnection("127.0.0.1", port); c.request("GET", "/api/v1/twin?width=1083"); d = json.loads(c.getresponse().read())
t_resp = datetime.now(timezone.utc)
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
def p(s):
    if not s: return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
rows = []
for ln in d["lines"]:
    for m in ln["machines"]:
        r = con.execute("select state,state_since,ended_at,last_event_at from agent where agent_key=?", (m["key"],)).fetchone()
        st, ss, ea, le = r
        f = lambda x: None if x is None else round((t_resp - x).total_seconds())
        rows.append((ln["name"], m["key"][:12], m["state"], st, m.get("elapsed_s"), f(p(ss)), m.get("ended_ago_s"), f(p(ea)), m.get("last_ago_s"), f(p(le)), ss, ea, le))
print("응답 시각", t_resp.isoformat(timespec="seconds"))
print("라인|키|화면상태|DB상태|elapsed_s|손(now-state_since)|ended_ago_s|손(now-ended_at)|last_ago_s|손(now-last_event_at)|state_since|ended_at|last_event_at")
for r in rows: print("|".join(str(x) for x in r))
