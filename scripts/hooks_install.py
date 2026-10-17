#!/usr/bin/env python
"""agentdash 훅 설치 · 제거 · 점검 (spec.md §9.1) — 담당 개발2. **실제 ~/.claude/settings.json 에는 사람이 직접 돌린다.**

    uv run python scripts/hooks_install.py --settings <경로>              # 덧붙이기 (diff 보여 주고 y 확인)
    uv run python scripts/hooks_install.py --settings <경로> --uninstall  # 식별 표시 붙은 항목만 제거
    uv run python scripts/hooks_install.py --settings <경로> --check      # 설치 여부 · 최근 수신 · 이벤트별 건수
    --yes  확인 없이 진행 (가짜 설정 파일 검증용 — 실제 claude_home 의 settings.json 에는 거부한다)

하는 일 (설치)
  1. `<settings>.bak-agentdash-<YYYYmmdd-HHMMSS>` 로 백업 (바이트 그대로).
  2. 이벤트 9 종마다 matcher 없는 항목 하나를 배열 **끝에 덧붙인다**. 기존 항목의 순서 · 내용은 건드리지 않는다.
     이미 식별 표시(`hook_send.sh`)가 있는 이벤트는 건너뛴다(두 번 돌려도 하나).
  3. 바뀐 내용의 diff 를 표준출력에 보여 주고 `y` 를 받아야 저장한다.
  4. 저장 뒤 다시 읽어 JSON 문법 · 기존 항목 동일 · 덧붙인 수를 검사하고, 하나라도 틀리면 백업으로 되돌린다.
제거
  · 식별 표시가 붙은 항목만 지운다. 결과가 가장 최근 백업과 JSON 으로 같으면 백업 바이트를 그대로 되돌려 놓는다
    (설치 → 제거 뒤 원본과 바이트 동일, G-15). 덧붙이며 새로 만든 빈 이벤트 배열은 지운다.
필수 인자 `--settings`: 기본값을 두지 않는다 — `make hooks-install` 이 settings.claude_home 으로 경로를 계산해 넘긴다.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EVENTS = ["SessionStart", "SessionEnd", "SubagentStart", "SubagentStop", "Stop", "Notification", "PreToolUse",
          "PostToolUse", "UserPromptSubmit"]
MARK = "hook_send.sh"
SEND = ROOT / "scripts" / MARK
BAK = ".bak-agentdash-"


def command() -> str:
    # 경로에 공백이 있다 ("AI Coding/Multi-agent Dashboard") — 셸 인용
    return f"bash {shlex.quote(str(SEND))}"


def entry() -> dict:
    return {"hooks": [{"type": "command", "command": command(), "timeout": 5}]}


def marked(e) -> bool:
    return MARK in json.dumps(e, ensure_ascii=False)


def detect_indent(text: str):
    for ln in text.splitlines()[1:]:
        if ln.strip():
            lead = ln[: len(ln) - len(ln.lstrip())]
            if lead.startswith("\t"):
                return "\t"
            return len(lead) or 2
    return 2


def dump(data: dict, indent) -> str:
    return json.dumps(data, ensure_ascii=False, indent=indent) + "\n"


def is_real_target(target: Path) -> bool:
    """실제 claude_home 의 settings.json 인가 (--yes 금지 판정용 — 비교만)."""
    from agentdash import settings as _s
    try:
        real = _s.get().claude_home / "settings.json"
    except Exception:                  # noqa: BLE001 — 설정을 못 읽으면 실제 파일일 수 있다고 보고 막는다
        return True
    return target.resolve() == real.resolve()


def confirm(yes: bool, prompt: str) -> bool:
    if yes:
        return True
    try:
        ans = input(prompt)
    except EOFError:
        return False
    return ans.strip().lower() in ("y", "yes")


def atomic_write(target: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".agentdash-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def restore(target: Path, bak: Path) -> None:
    atomic_write(target, bak.read_text(encoding="utf-8"))


def backups(target: Path) -> list[Path]:
    return sorted(target.parent.glob(target.name + BAK + "*"))


def load(target: Path) -> tuple[str, dict]:
    text = target.read_text(encoding="utf-8") if target.exists() else "{}\n"
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict):
        raise SystemExit(f"settings 형식 오류 (객체 아님): {target}")
    hooks = data.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise SystemExit(f"settings.hooks 형식 오류 (객체 아님): {target}")
    return text, data


def show_diff(before: str, after: str, name: str) -> int:
    lines = list(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f"{name} (전)", f"{name} (후)"))
    sys.stdout.write("".join(lines) or "(변경 없음)\n")
    return len(lines)


def install(target: Path, yes: bool) -> int:
    if not target.exists():
        print(f"settings 파일 없음: {target} — 만들지 않는다 (사람이 확인)")
        return 1
    before_text, data = load(target)
    old_hooks = json.loads(json.dumps(data.get("hooks") or {}))
    hooks = data.setdefault("hooks", {})
    added = []
    for ev in EVENTS:
        lst = hooks.setdefault(ev, [])
        if not isinstance(lst, list):
            print(f"hooks.{ev} 형식 오류 (배열 아님) — 중단, 아무것도 바꾸지 않았다")
            return 1
        if any(marked(e) for e in lst):
            continue
        lst.append(entry())
        added.append(ev)
    if not added:
        print("이미 설치됨 — 바꿀 것 없음 (이벤트 9 종 모두 식별 표시 있음)")
        return 0
    after_text = dump(data, detect_indent(before_text))
    show_diff(before_text, after_text, target.name)
    if not confirm(yes, f"이벤트 {len(added)} 종에 agentdash 훅을 덧붙입니다. 저장할까요? [y/N] "):
        print("취소 — 아무것도 바꾸지 않았다")
        return 1
    bak = target.with_name(target.name + BAK + datetime.now().strftime("%Y%m%d-%H%M%S"))
    n = 0
    while bak.exists():
        n += 1
        bak = bak.with_name(bak.name.split("~")[0] + f"~{n}")
    bak.write_bytes(target.read_bytes())
    print(f"백업: {bak}")
    try:
        atomic_write(target, after_text)
        _, check = load(target)                        # 문법 검사
        bad = verify(old_hooks, check.get("hooks") or {})
        if bad:
            raise ValueError("; ".join(bad))
    except (ValueError, OSError, SystemExit) as e:
        restore(target, bak)
        print(f"검사 실패 → 백업으로 되돌림: {e}")
        return 1
    print(f"설치 완료 — 덧붙인 이벤트 {len(added)}: {' '.join(added)}")
    return 0


def verify(old_hooks: dict, new_hooks: dict) -> list[str]:
    bad = []
    for ev, entries in old_hooks.items():
        cur = new_hooks.get(ev, [])
        if json.dumps(cur[: len(entries)], ensure_ascii=False) != json.dumps(entries, ensure_ascii=False):
            bad.append(f"{ev}: 기존 항목이 바뀜")
    n = sum(1 for ev in EVENTS for e in new_hooks.get(ev, []) if marked(e))
    if n != len(EVENTS):
        bad.append(f"식별 항목 {n} ≠ {len(EVENTS)}")
    return bad


def uninstall(target: Path, yes: bool) -> int:
    if not target.exists():
        print(f"settings 파일 없음: {target}")
        return 1
    before_text, data = load(target)
    hooks = data.get("hooks") or {}
    removed = 0
    for ev in list(hooks):
        lst = hooks[ev]
        if not isinstance(lst, list):
            continue
        keep = [e for e in lst if not marked(e)]
        removed += len(lst) - len(keep)
        hooks[ev] = keep
    if removed == 0:
        print("식별 표시 붙은 항목 없음 — 바꿀 것 없음")
        return 0
    # 가장 최근 백업과 같으면 백업 바이트를 그대로 (원본 바이트 동일)
    restored_from = None
    for bak in reversed(backups(target)):
        try:
            b = json.loads(bak.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        cand = json.loads(json.dumps(data))
        for ev in EVENTS:              # 설치가 새로 만든 빈 배열은 백업에 없으면 지운다
            if ev in cand.get("hooks", {}) and not cand["hooks"][ev] and ev not in (b.get("hooks") or {}):
                del cand["hooks"][ev]
        if "hooks" in cand and not cand["hooks"] and "hooks" not in b:
            del cand["hooks"]
        if cand == b:
            restored_from = bak
            after_text = bak.read_text(encoding="utf-8")
            break
    if restored_from is None:
        for ev in EVENTS:
            if ev in hooks and not hooks[ev]:
                del hooks[ev]
        after_text = dump(data, detect_indent(before_text))
    show_diff(before_text, after_text, target.name)
    if not confirm(yes, f"agentdash 훅 {removed} 개를 지웁니다. 저장할까요? [y/N] "):
        print("취소 — 아무것도 바꾸지 않았다")
        return 1
    snap = target.read_bytes()
    try:
        atomic_write(target, after_text)
        _, chk = load(target)
        if any(marked(e) for lst in (chk.get("hooks") or {}).values() if isinstance(lst, list) for e in lst):
            raise ValueError("식별 항목이 남음")
    except (ValueError, OSError, SystemExit) as e:
        target.write_bytes(snap)
        print(f"검사 실패 → 되돌림: {e}")
        return 1
    how = f"백업 {restored_from.name} 바이트 그대로" if restored_from else "식별 항목만 지우고 다시 씀"
    print(f"제거 완료 — {removed} 개 ({how})")
    return 0


def check(target: Path) -> int:
    if not target.exists():
        print(f"settings 파일 없음: {target}")
        return 1
    _, data = load(target)
    hooks = data.get("hooks") or {}
    have = [ev for ev in EVENTS if any(marked(e) for e in hooks.get(ev, []) if isinstance(hooks.get(ev), list))]
    print(f"설치: {len(have)}/{len(EVENTS)} 이벤트 — {' '.join(have) or '없음'}")
    missing = [ev for ev in EVENTS if ev not in have]
    if missing:
        print(f"빠진 이벤트: {' '.join(missing)}")
    others = sum(len(v) for v in hooks.values() if isinstance(v, list)) - len(have)
    print(f"다른 훅 항목: {others} (건드리지 않음)")
    print(f"송신 스크립트: {SEND} ({'있음' if SEND.exists() else '없음'})")
    try:
        from agentdash import settings as _s
        from agentdash.db import conn
        db = _s.get().db_path
        if not db.exists():
            print(f"DB 없음 {db} — 수신 기록 없음")
            return 0
        con = conn.connect(db)
        rows = con.execute("SELECT event, COUNT(*), MAX(at) FROM hook_event GROUP BY event ORDER BY event").fetchall()
        last = con.execute("SELECT MAX(at) FROM hook_event").fetchone()[0]
        con.close()
        print(f"최근 수신: {last or '없음'} · DB {db.name}")
        for ev, n, at in rows:
            print(f"  {ev:18s} {n:6d}  마지막 {at}")
    except Exception as e:             # noqa: BLE001 — 점검 출력이 실패해도 설치 상태 출력은 남긴다
        print(f"수신 기록 읽기 실패: {type(e).__name__}: {e}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", required=True, type=Path, help="settings.json 경로 (필수 — 기본값 없음)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--uninstall", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--yes", action="store_true", help="확인 없이 (가짜 설정 파일 검증용)")
    a = ap.parse_args(argv)
    target = a.settings.expanduser()
    if a.check:
        return check(target)
    if a.yes and is_real_target(target):
        print("실제 claude_home 의 settings.json 에는 --yes 를 쓸 수 없다 — diff 를 보고 y 를 직접 입력한다")
        return 2
    if os.environ.get("PYTEST_CURRENT_TEST") and is_real_target(target):
        print("테스트 중 실제 settings.json 거부")
        return 2
    return uninstall(target, a.yes) if a.uninstall else install(target, a.yes)


if __name__ == "__main__":
    raise SystemExit(main())
