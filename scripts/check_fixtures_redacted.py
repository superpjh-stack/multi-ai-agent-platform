#!/usr/bin/env python
"""픽스처 본문 누출 검사 — G-13 (goal.md §2.3) · V-04 의 픽스처 쪽.

    uv run python scripts/check_fixtures_redacted.py [경로 …]     # 기본 tests/fixtures

`make_fixture.py` 와 **따로** 규칙을 갖는다(생성기를 믿지 않는다). 위반 하나라도 있으면 FAIL · 종료코드 1.
  1. 본문 키(text · thinking · content · command · prompt · new_string · old_string · lastPrompt · aiTitle · script …)의
     문자열 값이 "<redacted>" 가 아니다.
  2. 허용 키(ALLOW — 구조 · id · 시각 · 모델 · 도구 이름 · 경로) 밖의 문자열 값이 120 자를 넘는다.
  3. 허용 키의 값이라도 300 자를 넘는다 (DB TEXT 상한과 같은 기준).
  4. 설명 키(description · workflowName · title · label · workflowPhase)가 40 자를 넘는다.
  5. dict 키 자체가 120 자를 넘는다 (키로 숨은 본문).
  6. jsonl 의 줄이 JSON 이 아니다 (원문 줄이 그대로 들어온 것).
  7. README.md 외의 파일 형식(.jsonl · .json 외)이 있다.
출력 마지막 줄: `G-13  픽스처 본문  PASS|FAIL  <실측>` (gate.py 가 읽는다).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "tests" / "fixtures"
REDACTED = "<redacted>"

BODY = {
    "text", "thinking", "content", "command", "prompt", "new_string", "old_string", "lastPrompt", "aiTitle",
    "script", "stdout", "stderr", "result", "summary", "message", "input", "output", "query", "pattern",
    "signature", "data", "notes", "args", "reason", "base", "tail", "params", "snapshot", "backup", "logs",
}
ALLOW = {
    "type", "subtype", "level", "role", "uuid", "parentUuid", "leafUuid", "logicalParentUuid", "timestamp",
    "sessionId", "session_id", "requestId", "id", "tool_use_id", "model", "requestedModel", "advisorModel",
    "defaultModel", "stop_reason", "service_tier", "speed", "inference_geo", "version", "entrypoint", "userType",
    "cwd", "gitBranch", "permissionMode", "mode", "kind", "status", "promptId", "messageId", "snapshotMessageId",
    "sourceToolUseID", "sourceToolAssistantUUID", "toolUseID", "effort", "requestRef",
    "name", "file_path", "notebook_path", "filePath", "subagent_type", "skill", "to",
    "agentType", "toolUseId", "requestShape", "agentId", "parentAgentId", "runId", "taskId", "scriptPath",
    "trackingPath", "hash", "shapeHash", "requestDigest", "querySource",
}
DESC = {"description", "workflowName", "title", "label", "workflowPhase"}


def walk(obj, key, where: str, bad: list[str], stats: dict) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if len(k) > 120:
                bad.append(f"{where}: dict 키 {len(k)} 자")
            walk(v, k, where, bad, stats)
        return
    if isinstance(obj, list):
        for x in obj:
            walk(x, key, where, bad, stats)
        return
    if not isinstance(obj, str):
        return
    stats["strings"] += 1
    if obj == REDACTED:
        stats["redacted"] += 1
        return
    if key in BODY:
        bad.append(f"{where}: 본문 키 {key!r} 가 지워지지 않음 ({len(obj)} 자)")
    elif key in DESC:
        if len(obj) > 40:
            bad.append(f"{where}: 설명 키 {key!r} {len(obj)} 자 > 40")
    elif key in ALLOW:
        if len(obj) > 300:
            bad.append(f"{where}: 허용 키 {key!r} {len(obj)} 자 > 300")
    elif len(obj) > 120:
        bad.append(f"{where}: 허용 밖 키 {key!r} {len(obj)} 자 > 120")


def check(paths: list[Path]) -> tuple[list[str], dict]:
    bad: list[str] = []
    stats = {"files": 0, "lines": 0, "strings": 0, "redacted": 0}
    for base in paths:
        if not base.exists():
            bad.append(f"{base}: 없음")
            continue
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for f in files:
            rel = f.relative_to(ROOT) if ROOT in f.parents else f
            if f.name == "README.md":
                continue
            stats["files"] += 1
            if f.suffix == ".jsonl":
                for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if not ln.strip():
                        continue
                    stats["lines"] += 1
                    try:
                        d = json.loads(ln)
                    except json.JSONDecodeError:
                        bad.append(f"{rel}:{i}: JSON 아님")
                        continue
                    walk(d, None, f"{rel}:{i}", bad, stats)
            elif f.suffix == ".json":
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    bad.append(f"{rel}: JSON 아님")
                    continue
                walk(d, None, str(rel), bad, stats)
            else:
                bad.append(f"{rel}: 픽스처에 허용되지 않는 파일 형식")
    return bad, stats


def main(argv: list[str]) -> int:
    paths = [Path(a).resolve() for a in argv] or [DEFAULT]
    bad, st = check(paths)
    for b in bad[:30]:
        print("  위반", b)
    if len(bad) > 30:
        print(f"  … 외 {len(bad) - 30} 건")
    detail = (f"파일 {st['files']} · 줄 {st['lines']} · 문자열 {st['strings']} (그중 <redacted> {st['redacted']}) · "
              f"위반 {len(bad)}")
    if st["files"] == 0:
        print(f"G-13  픽스처 본문  FAIL  픽스처 파일 0 — make fixtures")
        return 1
    print(f"G-13  픽스처 본문  {'PASS' if not bad else 'FAIL'}  {detail}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
