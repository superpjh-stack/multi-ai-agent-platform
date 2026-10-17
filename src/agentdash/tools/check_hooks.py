#!/usr/bin/env python
"""V-10 check_hooks — 훅 설치 안전 (G-15). **실제 ~/.claude/settings.json 에는 절대 쓰지 않는다.**

    uv run python src/agentdash/tools/check_hooks.py

개발2 가 만들 것 (계약 — CLAUDE.md 「훅 계약」)
  · `scripts/hooks_install.py --settings <경로> [--yes]`            덧붙이기 (백업 · 식별 표시 · diff · 확인 · 문법 검사 · 되돌림)
  · `scripts/hooks_install.py --settings <경로> --uninstall [--yes]` 식별 표시 붙은 항목만 제거
  · `scripts/hook_send.sh`  표준입력 JSON → POST 127.0.0.1:8095/hooks/event, 항상 exit 0 · ≤ 1 초 · 표준출력 0 바이트

판정 (둘 다 있을 때만 — 없으면 `미검증`)
  1. 임시 폴더에 가짜 settings.json 을 만든다. 실제 파일이 있으면 그 `hooks` 의 **구조만**(이벤트 · matcher · 항목 수)
     본뜨고 명령은 `echo fixture-N` 으로 바꾼다(실제 명령 문자열은 옮기지 않는다). 없으면 PreToolUse · PostToolUse · Stop 3 개.
  2. 설치 → 기존 항목이 바이트 단위로 같다(이벤트별 기존 배열 앞부분 JSON 비교) · 덧붙인 항목이 9 개(spec.md §9.1 이벤트 9)이고
     전부 식별 표시(`hook_send.sh`)를 품는다.
  3. 제거 → 파일이 설치 전과 바이트 단위로 같다.
  4. 서버가 꺼진 상태(127.0.0.1:8095 듣는 프로세스 없음)에서 hook_send.sh: exit 0 · ≤ 1 초 · 표준출력 0 바이트.
     8095 에 누가 듣고 있으면 이 항목은 `미검증`(서버 꺼짐 조건을 만들 수 없다 — 다른 프로세스를 죽이지 않는다).
출력: `G-15  훅 설치 안전  PASS|FAIL|미검증  실측`
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from agentdash import settings as _settings  # noqa: E402

INSTALL = ROOT / "scripts" / "hooks_install.py"
SEND = ROOT / "scripts" / "hook_send.sh"
EVENTS = ["SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop", "Notification", "PreToolUse",
          "PostToolUse", "UserPromptSubmit"]
MARK = "hook_send.sh"


def fake_settings_from_real(s: _settings.Settings) -> dict:
    real = s.claude_home / "settings.json"
    hooks: dict = {}
    n = 0
    if real.exists():
        with real.open("r", encoding="utf-8") as fh:            # 읽기만
            data = json.load(fh)
        for ev, entries in (data.get("hooks") or {}).items():
            out = []
            for e in entries:
                item = {}
                if "matcher" in e:
                    item["matcher"] = e["matcher"]
                hs = []
                for _h in e.get("hooks", []):
                    n += 1
                    hs.append({"type": "command", "command": f"echo fixture-{n}"})
                item["hooks"] = hs
                out.append(item)
            hooks[ev] = out
    if not hooks:
        hooks = {ev: [{"hooks": [{"type": "command", "command": f"echo fixture-{i}"}]}]
                 for i, ev in enumerate(["PreToolUse", "PostToolUse", "Stop"], 1)}
    return {"theme": "fixture", "hooks": hooks}


def port_busy(port: int) -> bool:
    try:
        p = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    return bool(p.stdout.strip())


def check() -> tuple[str, str, list[str]]:
    missing = [p.relative_to(ROOT).as_posix() for p in (INSTALL, SEND) if not p.exists()]
    if missing:
        return "미검증", f"{' · '.join(missing)} 없음 — 설치 스크립트 미구현 (담당 개발2, 웨이브 A)", []
    s = _settings.get()
    bad: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="agentdash-hooks-"))
    try:
        target = tmp / "settings.json"
        if s.is_source_path(target):
            return "FAIL", f"가짜 settings 경로가 원천 아래: {target}", []
        model = fake_settings_from_real(s)
        original = (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target.write_bytes(original)
        before_hooks = model["hooks"]
        p = subprocess.run(["uv", "run", "python", str(INSTALL), "--settings", str(target), "--yes"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60, input="y\n")
        if p.returncode != 0:
            bad.append(f"설치 종료코드 {p.returncode}")
        after = json.loads(target.read_text(encoding="utf-8"))
        added = 0
        for ev, entries in before_hooks.items():
            cur = after.get("hooks", {}).get(ev, [])
            if json.dumps(cur[:len(entries)], sort_keys=False) != json.dumps(entries, sort_keys=False):
                bad.append(f"{ev}: 기존 항목이 바뀜")
        for ev in EVENTS:
            for e in after.get("hooks", {}).get(ev, []):
                if MARK in json.dumps(e):
                    added += 1
        if added != len(EVENTS):
            bad.append(f"덧붙인 항목 {added} ≠ {len(EVENTS)}")
        p = subprocess.run(["uv", "run", "python", str(INSTALL), "--settings", str(target), "--uninstall", "--yes"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60, input="y\n")
        if p.returncode != 0:
            bad.append(f"제거 종료코드 {p.returncode}")
        if target.read_bytes() != original:
            bad.append("제거 뒤 원본과 바이트 다름")
        send_note = ""
        if port_busy(s.port):
            send_note = f" · 송신 미검증 ({s.port} 사용 중)"
        else:
            t0 = time.time()
            q = subprocess.run(["bash", str(SEND)], input=b'{"hook_event_name":"Stop","session_id":"fixture"}',
                               capture_output=True, timeout=10)
            dt = time.time() - t0
            if q.returncode != 0:
                bad.append(f"송신 종료코드 {q.returncode}")
            if dt > 1.0:
                bad.append(f"송신 {dt:.2f}s > 1s")
            if q.stdout:
                bad.append(f"송신 표준출력 {len(q.stdout)} 바이트")
            send_note = f" · 송신 {dt:.2f}s exit {q.returncode} stdout {len(q.stdout)}B"
        detail = f"가짜 settings (기존 이벤트 {len(before_hooks)}) · 덧붙임 {added}{send_note} · 위반 {len(bad)}"
        if bad:
            return "FAIL", detail, bad
        return ("미검증" if "미검증" in send_note else "PASS"), detail, bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    st, detail, bad = check()
    for b in bad:
        print("  위반", b)
    print(f"G-15  훅 설치 안전  {st}  {detail}")
    return 1 if st == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
