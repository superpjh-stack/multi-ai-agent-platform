"""r5 (복사본, 경로만 r5): judge-out-r5.json + db-sample-r5.txt(key|state|rule|since|last) → 마크다운 표. 기대 = spec v0.3 §4.2 글자 (v03_*), 참고 = 옛 v0.2 글자 (spec_*)."""
import json, sys
d = json.load(open("outputs/qa2/judge-out-r5.json"))
snap = {}
for l in open("outputs/qa2/db-sample-r5.txt"):
    p = l.rstrip("\n").split("|"); snap[p[0]] = (p[1], p[2])
print("| # | 키 | 종류 | 원천 근거 (spec v0.3 §4.2 입력값) | 기대 v0.3 글자 | (참고) v0.2 글자 | 대시보드 | 일치 |")
print("|---|---|---|---|---|---|---|---|")
bad = 0
for i, r in enumerate(d["results"], 1):
    k = r["key"]; st, rule = snap[k]
    if r["kind"] == "SESSION":
        s1 = r.get("s1")
        s1s = f"S1 status={s1['status']} · pid {'살아 있음' if s1['alive'] else '소멸'}" if s1 else "S1 없음"
        ev = f"{s1s} · 마지막 기록 {r['last_at'][:19]}Z ({r['age_s']}초 전) · 마지막 줄 {r['last_kind']} · 마지막 tool_use {r.get('last_tool') or '-'}" + \
             (f" · 결과 없는 tool_use {r['pending']}" if r.get('last_item_pending_tool_use') else "") + \
             (f" · ScheduleWakeup {r['wakeup']}Z{'(미래)' if r.get('wake_future') else '(지남)'}" if r.get("wakeup") else "") + f" · 자식 {r['children']} (미종료 {r['open_children']})"
    else:
        sig = ", ".join(f"{s[1]}@{s[0][5:19]}" for s in sorted(r["signals"])) or "없음"
        ev = f"세션 {r['session'][:8]} S1 {r['session_s1'] or '없음'}{'' if r['session_alive'] else ' (프로세스 없음)'} · " \
             f"마지막 기록 {r['last_at'][5:19]} ({r['age_s']}초 전) · 마지막 활동 {(r['last_activity'] or '-')[5:19]} · 반환 {sig}"
        if r.get("wf_status"):
            ev += f" · S6 status={r['wf_status']}"
    ok = st == r["v03_state"] and rule == r["v03_rule"]
    bad += not ok
    print(f"| {i} | `{k}` | {r['kind']} | {ev} | {r['v03_state']} {r['v03_rule']} | {r['spec_state']} {r['spec_rule']} | {st} {rule} | {'O' if ok else '**X**'} |")
print(f"\n오판 (v0.3 글자, 상태+규칙) {bad} / {len(d['results'])}", file=sys.stderr)
