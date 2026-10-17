"""r3: judge-out-r3.json + db-sample-r3.txt → 마크다운 표 (키 · 시각 · 숫자 · 규칙 코드만). spec 글자 / 가설 두 칸."""
import json, sys
d = json.load(open("outputs/qa2/judge-out-r3.json"))
snap = {}
for l in open("outputs/qa2/db-sample-r3.txt"):
    k, st, r = l.split()
    snap[k] = (st, r)
print("| # | 키 | 종류 | 원천 근거 | spec 글자 | 가설 (D-14·18·19) | 대시보드 | 일치 (글자 / 가설) |")
print("|---|---|---|---|---|---|---|---|")
bs = bh = 0
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
    os_ = st == r["spec_state"]; oh = st == r["hyp_state"]
    bs += not os_; bh += not oh
    kind = r["kind"] + (" (깊이 2)" if False else "")
    print(f"| {i} | `{k}` | {kind} | {ev} | {r['spec_state']} {r['spec_rule']} | {r['hyp_state']} {r['hyp_rule']} | {st} {rule} | {'O' if os_ else '**X**'} / {'O' if oh else '**X**'} |")
print(f"\n오판 spec 글자 {bs} · 가설 {bh} / {len(d['results'])}", file=sys.stderr)
