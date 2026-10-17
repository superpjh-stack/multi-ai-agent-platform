"""judge-out.json + DB 상태 → 마크다운 표 (숫자 · 키 · 시각만)."""
import json, sqlite3, sys
d = json.load(open("outputs/qa2/judge-out.json"))
con = sqlite3.connect("file:data/agentdash-qa2.db?mode=ro", uri=True)
snap = {}  # 표본 시각(08:08Z) 대시보드 값 — 그 뒤 바뀐 것은 아래에서 덮어쓰지 않도록 db-sample.txt 가 있으면 그것
try:
    for l in open("outputs/qa2/db-sample.txt"):
        k, st, r = l.split()
        snap[k] = (st, r)
except FileNotFoundError:
    pass
print("| # | 키 | 종류 | 원천 근거 (S1 · pid · 마지막 기록 · 마지막 줄 · 반환 신호) | QA 판정 | 대시보드 | 일치 |")
print("|---|---|---|---|---|---|---|")
bad = 0
for i, r in enumerate(d["results"], 1):
    k = r["key"]
    st, rule = snap.get(k) or con.execute("SELECT state, state_reason FROM agent WHERE agent_key=?", (k,)).fetchone()
    if r["kind"] == "SESSION":
        s1 = r.get("s1")
        s1s = f"S1 {s1['file']} status={s1['status']} · `ps -p {s1['pid']}` {'살아 있음' if s1['alive'] else '없음'}" if s1 else "S1 없음"
        ev = f"{s1s} · 마지막 기록 {r['last_at'][:19]}Z ({r['age_s']}초 전) · 마지막 줄 {r['last_kind']}" + \
             (f" · 결과 없는 tool_use {r['pending']}" if r.get('last_item_pending_tool_use') else "") + \
             (f" · ScheduleWakeup {r['wakeup']}Z" if r.get("wakeup") else "") + f" · 자식 {r['children']} (미종료 {r['open_children']})"
    else:
        sig = ", ".join(f"{s[1]}@{s[0][5:19]}" for s in sorted(r["signals"])) or "없음"
        ev = f"세션 {r['session'][:8]} S1 {r['session_s1'] or '없음'} ({'살아 있음' if r['session_alive'] else '프로세스 없음'}) · " \
             f"마지막 기록 {r['last_at'][:19]}Z ({r['age_s']}초 전) · 마지막 줄 {r['last_kind']} · 마지막 활동 {(r['last_activity'] or '-')[5:19]} · 반환 신호 {sig}"
        if r.get("wf_status"):
            ev += f" · S6 status={r['wf_status']}"
    ok = st == r["qa_state"]
    bad += not ok
    print(f"| {i} | `{k}` | {r['kind']} | {ev} | **{r['qa_state']}** {r['qa_rule']} | {st} {rule} | {'O' if ok else '**X 오판**'} |")
print(f"\n오판 {bad} / {len(d['results'])}", file=sys.stderr)
