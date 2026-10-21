"""QA2 독립 상태 판정기 r4 — spec v0.3 §4.2 글자 (세션 평가 순서 R-01→R-02a→(훅 도구 실행)→R-03→R-04→R-02b→R-05→R-06→R-07, 잠잠한 busy, pid 소멸 = S1 없음 D-19, 마지막 tool_use 기준 D-18, S1 shell = idle 계열 D-09) 를 v03_* 로, 옛 v0.2 글자를 spec_* 로 남긴다. r3 판정기에서 바뀐 것은 출력 이름뿐 (r3 의 가설 판정 = v0.3 글자). — 원천(~/.claude, 읽기만)을 직접 읽어 spec.md §4.2 규칙으로 상태를 정한다.

대시보드 코드(agentdash.*)를 import 하지 않는다. 출력은 키 · 시각 · 숫자 · 규칙 코드뿐(본문 없음).

    uv run python -I outputs/qa2/judge.py <키 목록 파일> <출력 json>

키: S:<sessionId> | A:<agentId>. 기준 시간: STALE 300 초 · SLOW 90 초 (spec §4.2, config/settings.yaml).
반환(L-07) 판정은 decisions.md D-04 확정 대안 규칙을 따른다:
  종료 신호 = 자식의 SubagentHandback ∪ 부모 쪽 <task-notification> status ∈ {completed, failed, killed} ∪ Agent tool_result is_error
  가장 늦은 종료 신호가 자식의 마지막 활동(tool_use 를 낸 assistant 줄 · 들어온 메시지 줄) 이후면 끝.
  failed · killed · is_error 는 오류 → FAILED (spec §4.1 FAILED "오류로 끝남 … 실패 보고").
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

HOME = os.path.expanduser("~/.claude")
STALE, SLOW = 300, 90
END = {"completed": False, "failed": True, "killed": True}
NOTIF = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
TAG = {k: re.compile(rf"<{k}>([^<]{{0,80}})</{k}>") for k in ("tool-use-id", "status", "task-id")}


def ts(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def lines(path):
    with open(path, "rb") as f:            # 읽기 전용
        for raw in f:
            try:
                yield json.loads(raw)
            except Exception:
                continue


def texts(content):
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text" and isinstance(c.get("text"), str):
                    yield c["text"]
                elif c.get("type") == "tool_result":
                    cc = c.get("content")
                    if isinstance(cc, str):
                        yield cc
                    elif isinstance(cc, list):
                        for x in cc:
                            if isinstance(x, dict) and isinstance(x.get("text"), str):
                                yield x["text"]


def scan_file(path):
    """파일 하나 요약: 마지막 기록 시각, 마지막 항목 종류, 미결 tool_use, 마지막 활동, handback, notification, 오류 결과, wakeup."""
    r = dict(last_at=None, last_kind=None, pending=[], last_activity=None, handbacks=[], notifs=[],
             tool_errors=set(), tool_results=set(), wakeup=None, last_assistant_tools=[], n=0, last_tool=None, last_wakeup_any=None)
    open_uses = {}
    for d in lines(path):
        t = d.get("timestamp")
        if t and (r["last_at"] is None or ts(t) > ts(r["last_at"])):
            r["last_at"] = t
        typ = d.get("type")
        if typ not in ("assistant", "user"):
            continue
        r["n"] += 1
        msg = d.get("message") or {}
        content = msg.get("content")
        if typ == "assistant":
            tools = [c for c in (content or []) if isinstance(c, dict) and c.get("type") == "tool_use"]
            r["last_kind"] = "assistant:tool_use" if tools else "assistant:text"
            r["last_assistant_tools"] = [c.get("name") for c in tools]
            for c in tools:
                open_uses[c.get("id")] = (c.get("name"), t)
                r["last_tool"] = c.get("name")
                if c.get("name") == "SubagentHandback":
                    r["handbacks"].append(t)
                if c.get("name") == "ScheduleWakeup":
                    inp = c.get("input") or {}
                    dl = inp.get("delaySeconds")
                    if isinstance(dl, (int, float)) and t:
                        r["wakeup"] = (ts(t).timestamp() + dl)
                        r["last_wakeup_any"] = r["wakeup"]
            if tools:
                r["last_activity"] = t
        else:
            is_result = isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "tool_result"
                                                         for c in content)
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        tid = c.get("tool_use_id")
                        open_uses.pop(tid, None)
                        r["tool_results"].add(tid)
                        if c.get("is_error") is True:
                            r["tool_errors"].add(tid)
            r["last_kind"] = "user:tool_result" if is_result else "user:message"
            for s in texts(content):
                for m in NOTIF.finditer(s):
                    body = m.group(1)
                    tid = TAG["tool-use-id"].search(body)
                    st = TAG["status"].search(body)
                    task = TAG["task-id"].search(body)
                    r["notifs"].append((tid.group(1).strip() if tid else None,
                                        task.group(1).strip() if task else None,
                                        st.group(1).strip() if st else None, t))
            if not is_result and not d.get("isMeta"):
                r["last_activity"] = t     # 들어온 메시지
    r["pending"] = [n for n, _ in open_uses.values()]
    return r


def s1_map():
    out = {}
    for p in glob.glob(os.path.join(HOME, "sessions", "*.json")):
        try:
            d = json.load(open(p, "rb"))
        except Exception:
            continue
        pid = d.get("pid")
        alive = subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0 if pid else False
        out[d.get("sessionId")] = dict(file=os.path.basename(p), status=d.get("status"), pid=pid, alive=alive,
                                       updatedAt=d.get("updatedAt"))
    return out


def find_session_dir(sid):
    hits = glob.glob(os.path.join(HOME, "projects", "*", f"{sid}.jsonl"))
    return hits[0] if hits else None


def find_agent(aid):
    hits = glob.glob(os.path.join(HOME, "projects", "*", "*", "subagents", f"agent-{aid}.jsonl")) + \
        glob.glob(os.path.join(HOME, "projects", "*", "*", "subagents", "workflows", "*", f"agent-{aid}.jsonl"))
    return hits[0] if hits else None


_cache = {}


def summary(path):
    if path not in _cache:
        _cache[path] = scan_file(path)
    return _cache[path]


def session_files(sess_jsonl):
    sid = os.path.basename(sess_jsonl)[:-6]
    folder = os.path.join(os.path.dirname(sess_jsonl), sid)
    files = [sess_jsonl] + glob.glob(os.path.join(folder, "subagents", "agent-*.jsonl")) + \
        glob.glob(os.path.join(folder, "subagents", "workflows", "*", "agent-*.jsonl"))
    return sid, folder, files


def judge_sub(aid, now, s1, depth=0):
    path = find_agent(aid)
    if not path:
        return dict(key=f"A:{aid}", error="원천 파일 없음")
    meta_p = path[:-6] + ".meta.json"
    meta = json.load(open(meta_p, "rb")) if os.path.exists(meta_p) else {}
    tuid = meta.get("toolUseId")
    is_wf = "/workflows/" in path
    sess_dir = path.split("/subagents/")[0]
    sid = os.path.basename(sess_dir)
    sess_jsonl = sess_dir + ".jsonl"
    me = summary(path)
    signals = [(t, "handback", False) for t in me["handbacks"] if t]
    children_open = 0
    child_ids = []
    for f in session_files(sess_jsonl)[2]:
        if f == path:
            continue
        s = summary(f)
        for tid, task, st, t in s["notifs"]:
            if (tuid and tid == tuid) or task == aid:
                if st in END and t:
                    signals.append((t, f"notification:{st}", END[st]))
        if tuid and tuid in s["tool_errors"]:
            signals.append((s["last_at"], "tool_error", True))
    # 자기 자식 (깊이 2): meta 의 parentAgentId 또는 toolUseId 가 내 기록의 Agent tool_use 인 것
    my_uses = set()
    for d in lines(path):
        if d.get("type") == "assistant":
            for c in (d.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Agent":
                    my_uses.add(c.get("id"))
    for mp in glob.glob(os.path.join(sess_dir, "subagents", "agent-*.meta.json")):
        if mp == meta_p:
            continue
        m = json.load(open(mp, "rb"))
        if m.get("parentAgentId") == aid or (m.get("toolUseId") in my_uses and m.get("spawnDepth", 1) >= 2):
            child_ids.append(os.path.basename(mp)[6:-10])
    last_act = me["last_activity"]
    ends = [s for s in signals if s[0]]
    ret = None
    if ends:
        last = max(ends, key=lambda x: ts(x[0]))
        if last_act is None or ts(last[0]) >= ts(last_act):
            ret = last
    sess = s1.get(sid)
    alive = bool(sess and sess["alive"])
    age = (now - ts(me["last_at"])).total_seconds() if me["last_at"] else None
    out = dict(key=f"A:{aid}", kind="WORKFLOW_AGENT" if is_wf else "SUBAGENT", session=sid,
               last_at=me["last_at"], age_s=int(age) if age is not None else None, last_kind=me["last_kind"],
               handbacks=len(me["handbacks"]), signals=[(s[0], s[1]) for s in ends],
               last_activity=last_act, session_s1=(sess["status"] if sess else None), session_alive=alive,
               toolUseId_present=bool(tuid), children=len(child_ids))
    if is_wf:
        # 워크플로 에이전트: 반환 신호 없음 — S6 workflows/wf_<id>.json 의 상태를 본다 (L-03)
        wfid = path.split("/workflows/")[1].split("/")[0]
        wfj = os.path.join(sess_dir, "workflows", f"{wfid}.json")
        st = None
        if os.path.exists(wfj):
            w = json.load(open(wfj, "rb"))
            st = w.get("status") or (w.get("meta") or {}).get("status")
            out["wf_status"] = st
            out["wf_keys"] = sorted(w.keys())[:12]
        if st in ("completed", "done", "finished", "success"):
            out.update(qa_state="DONE", qa_rule="R-08", why=f"워크플로 S6 status={st}",
                       spec_state="DONE", spec_rule="R-08", hyp_state="DONE", hyp_rule="R-08", v03_state="DONE", v03_rule="R-08")
            return out
    if ret:
        out.update(qa_state="FAILED" if ret[2] else "DONE", qa_rule="R-08", why=f"반환 {ret[1]} {ret[0]}")
    elif age is not None and age < SLOW:
        out.update(qa_state="RUNNING", qa_rule="R-09", why=f"{int(age)}초 전 기록")
    else:
        open_c = 0
        for c in child_ids:
            if depth < 2:
                cj = judge_sub(c, now, s1, depth + 1)
                if cj.get("qa_state") not in ("DONE", "FAILED", "STALE"):
                    open_c += 1
        out["open_children"] = open_c
        if open_c:
            out.update(qa_state="WAITING_CHILD", qa_rule="R-10", why=f"미종료 자식 {open_c}")
        elif not alive:
            out.update(qa_state="STALE", qa_rule="R-11", why="소속 세션 프로세스 없음 · 반환 없음")
        elif age is None or age >= STALE:
            out.update(qa_state="STALE", qa_rule="R-11", why=f"{int(age or 0)}초 무기록")
        else:
            out.update(qa_state="RUNNING", qa_rule="R-12", why="응답 느림")
    out.update(spec_state=out.get("qa_state"), spec_rule=out.get("qa_rule"), hyp_state=out.get("qa_state"), hyp_rule=out.get("qa_rule"), v03_state=out.get("qa_state"), v03_rule=out.get("qa_rule"))
    return out


def judge_session(sid, now, s1):
    path = find_session_dir(sid)
    if not path:
        return dict(key=f"S:{sid}", error="원천 파일 없음")
    me = summary(path)
    sess = s1.get(sid)
    age = (now - ts(me["last_at"])).total_seconds() if me["last_at"] else None
    out = dict(key=f"S:{sid}", kind="SESSION", last_at=me["last_at"], age_s=int(age) if age is not None else None,
               last_kind=me["last_kind"], last_tools=me["last_assistant_tools"], pending=me["pending"],
               s1=sess, wakeup=(datetime.fromtimestamp(me["wakeup"], timezone.utc).isoformat()[:19]
                                if me["wakeup"] else None))
    # 자식 (깊이 1) 미종료 수
    folder = path[:-6]
    kids = [os.path.basename(p)[6:-10] for p in glob.glob(os.path.join(folder, "subagents", "agent-*.meta.json"))]
    open_c = 0
    if sess and sess["alive"]:
        for k in kids:
            j = judge_sub(k, now, s1)
            if j.get("qa_state") not in ("DONE", "FAILED", "STALE"):
                open_c += 1
    out["children"] = len(kids)
    out["open_children"] = open_c
    if sess and sess["alive"]:
        st = sess["status"]
        if st == "busy":
            if age is not None and age < STALE:
                out.update(qa_state="RUNNING", qa_rule="R-02a", why="S1 busy · pid 살아 있음 · 5 분 안")
            else:
                out.update(qa_state="STALE", qa_rule="R-02b", why="S1 busy · 5 분 넘게 무기록 (D-14: 자식 있으면 WAITING_CHILD)")
                if open_c:
                    out["d14_alt"] = "WAITING_CHILD R-04"
        else:
            if me["wakeup"] and me["wakeup"] > now.timestamp() and me["last_assistant_tools"] and \
                    "ScheduleWakeup" in me["last_assistant_tools"]:
                out.update(qa_state="SLEEPING", qa_rule="R-03", why="ScheduleWakeup 미래")
            elif open_c:
                out.update(qa_state="WAITING_CHILD", qa_rule="R-04", why=f"미종료 자식 {open_c}")
            else:
                out.update(qa_state="WAITING_INPUT", qa_rule="R-05", why=f"S1 status={st}")
    else:
        last_pending = me["last_kind"] == "assistant:tool_use" and bool(me["pending"])
        out["last_item_pending_tool_use"] = last_pending
        if last_pending:
            out.update(qa_state="STALE", qa_rule="R-06", why="S1 없음/pid 소멸 · 마지막 항목 결과 없는 tool_use")
        else:
            out.update(qa_state="DONE", qa_rule="R-07", why="S1 없음/pid 소멸")
    # ---- r2: spec 글자(D-19 없이) 와 가설(D-14 · D-18 · D-19) 두 판정 ----
    last_pending = me["last_kind"] == "assistant:tool_use" and bool(me["pending"])
    wake_future = bool(me["wakeup"] and me["wakeup"] > now.timestamp())
    def none_rules():
        return ("STALE", "R-06") if last_pending else ("DONE", "R-07")
    # spec 글자: S1 이 있으면 status 로 (R-02a 만 pid 생존 요구). pid 소멸 · busy · 5 분 안 = 규칙 없음
    if sess:
        st = sess["status"]
        if st == "busy":
            if age is not None and age < STALE:
                spec = ("RUNNING", "R-02a") if sess["alive"] else ("규칙없음", "-")
            else:
                spec = ("STALE", "R-02b")
        else:
            if wake_future and "ScheduleWakeup" in (me["last_assistant_tools"] or []):
                spec = ("SLEEPING", "R-03")
            elif open_c:
                spec = ("WAITING_CHILD", "R-04")
            else:
                spec = ("WAITING_INPUT", "R-05")
    else:
        spec = none_rules()
    # 가설: D-19 pid 소멸 = S1 없음 · D-18 busy+예약 SLEEPING · D-14 busy+미종료 자식 WAITING_CHILD · idle R-03 은 마지막 tool_use 기준(D-18)
    d18 = wake_future and me["last_tool"] == "ScheduleWakeup"
    if sess and sess["alive"]:
        st = sess["status"]
        if st == "busy":
            if age is not None and age < STALE:
                hyp = ("RUNNING", "R-02a")
            elif d18:
                hyp = ("SLEEPING", "R-03 (D-18)")
            elif open_c:
                hyp = ("WAITING_CHILD", "R-04 (D-14)")
            else:
                hyp = ("STALE", "R-02b")
        else:
            if d18:
                hyp = ("SLEEPING", "R-03")
            elif open_c:
                hyp = ("WAITING_CHILD", "R-04")
            else:
                hyp = ("WAITING_INPUT", "R-05")
    else:
        hyp = none_rules()
    out.update(spec_state=spec[0], spec_rule=spec[1], hyp_state=hyp[0], hyp_rule=hyp[1], v03_state=hyp[0], v03_rule=hyp[1].split(" (")[0], last_tool=me["last_tool"],
               wake_future=wake_future)
    return out


def main():
    keys = [k.strip() for k in open(sys.argv[1]) if k.strip() and not k.startswith("#")]
    now = datetime.now(timezone.utc)
    s1 = s1_map()
    res = []
    for k in keys:
        if k.startswith("S:"):
            res.append(judge_session(k[2:], now, s1))
        else:
            res.append(judge_sub(k[2:], now, s1))
    json.dump(dict(now=now.isoformat()[:19] + "Z", s1=s1, results=res), open(sys.argv[2], "w"),
              ensure_ascii=False, indent=1, default=str)
    for r in res:
        print(r["key"], "v03", r.get("v03_state"), r.get("v03_rule"), "v02", r.get("spec_state"), r.get("spec_rule"), r.get("age_s"))


if __name__ == "__main__":
    main()
