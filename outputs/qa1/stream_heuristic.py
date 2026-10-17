#!/usr/bin/env python
"""QA1 — 기록 종류별로 '스트리밍 중간본만 남은' 요청 비율 (D-01 '최종본' 가정 점검). 숫자만 출력.

  요청 하나(같은 기록 · 같은 requestId)의 output_tokens 최대값 < 30 이면서 그 요청 content 블록 JSON 길이 합 > 400 자 → 의심.
  내용 길이만 재고 내용은 보지 않는다(본문 미출력).
"""
import json, os
from collections import defaultdict
from pathlib import Path
proj = Path(os.path.expanduser("~/.claude/projects"))
groups = {"main": sorted(proj.glob("*/*.jsonl")),
          "sub": sorted(proj.glob("*/*/subagents/agent-*.jsonl")),
          "wf": sorted(proj.glob("*/*/subagents/workflows/wf_*/agent-*.jsonl"))}
for g, fs in groups.items():
    n = sus = out_sum = 0
    for f in fs:
        req = defaultdict(lambda: [0, 0])
        for raw in open(f, "rb"):
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("type") != "assistant" or not d.get("requestId"):
                continue
            m = d.get("message") or {}
            if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
                continue
            r = req[d["requestId"]]
            r[0] = max(r[0], m["usage"].get("output_tokens") or 0)
            r[1] += sum(len(json.dumps(b)) for b in (m.get("content") or []))
        for o, c in req.values():
            n += 1
            out_sum += o
            sus += (o < 30 and c > 400)
    print(f"{g:5s} 기록 {len(fs):4d} · 요청 {n:6d} · 의심 {sus:6d} ({100*sus/max(n,1):.1f}%) · output 합 {out_sum}")

# 하한 추정 — 의심 요청의 text · tool_use 입력 JSON 길이(문자) ÷ 4 를 '적어도 이만큼 출력했다' 로 보고 기록값과의 차이 (thinking 제외)
est = rec = n = 0
for f in groups["sub"] + groups["wf"]:
    req = defaultdict(lambda: [0, 0])
    for raw in open(f, "rb"):
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if d.get("type") != "assistant" or not d.get("requestId"):
            continue
        m = d.get("message") or {}
        if m.get("model") == "<synthetic>" or not isinstance(m.get("usage"), dict):
            continue
        r = req[d["requestId"]]
        r[0] = max(r[0], m["usage"].get("output_tokens") or 0)
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text":
                r[1] += len(b.get("text") or "")
            elif isinstance(b, dict) and b.get("type") == "tool_use":
                r[1] += len(json.dumps(b.get("input"), ensure_ascii=False))
    for o, c in req.values():
        if o < 30 and c / 4 > o:
            n += 1; rec += o; est += c / 4
print(f"서브·워크플로 의심 요청 {n} · 기록 output 합 {rec} · text+tool 입력 길이/4 합 {int(est)} → 차이(하한 추정) {int(est - rec)} 토큰")
