#!/bin/bash
# QA1 — hooks_install.py 를 가짜 settings 로만 설치/제거 → 바이트 비교 (G-15 · V-10). 실제 ~/.claude 는 건드리지 않는다.
#   bash outputs/qa1/hooks_fake.sh <빈 스크래치 폴더>
set -u
W="$1"; mkdir -p "$W/home"
export AGENTDASH_CLAUDE_HOME="$W/home"          # 가짜 claude_home (is_real_target 은 이것과 비교)
export AGENTDASH_AGENTS_ROOT="$W/agents"; mkdir -p "$AGENTDASH_AGENTS_ROOT"
REAL_MTIME_BEFORE=$(stat -f %m ~/.claude/settings.json); REAL_SHA_BEFORE=$(shasum ~/.claude/settings.json | cut -c1-40)
PY=".venv/bin/python"
mk() {  # $1 경로 $2 indent
"$PY" -I - "$1" "$2" <<'PYX'
import json, sys
ind = sys.argv[2]; ind = int(ind) if ind.isdigit() else ind
d = {"env": {"X": "1"}, "permissions": {"allow": ["Bash(ls:*)"], "deny": []}, "model": "m",
     "hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "echo a", "timeout": 10}]},
                                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo b"}]},
                                {"hooks": [{"type": "command", "command": "echo c 한글"}]}],
               "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo d"}]}],
               "Stop": [{"hooks": [{"type": "command", "command": "echo e"}]}]},
     "statusLine": {"type": "command", "command": "echo s"}, "k6": 1, "k7": True, "k8": None, "k9": [1, 2]}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=ind) + "\n")
PYX
}
run() { "$PY" scripts/hooks_install.py "$@"; echo "  → exit $?"; }
echo "## A. 실제와 같은 형식(indent 2 · 한글 그대로) 가짜 settings"
mkdir -p "$W/A"; mk "$W/A/settings.json" 2; cp "$W/A/settings.json" "$W/orig_A.json"
run --settings "$W/A/settings.json" --yes > "$W/A_install.log"; tail -1 "$W/A_install.log"
"$PY" -I - "$W/orig_A.json" "$W/A/settings.json" <<'PYX'
import json, sys
o, n = (json.load(open(p)) for p in sys.argv[1:])
same = all(json.dumps(n["hooks"][e][:len(v)]) == json.dumps(v) for e, v in o["hooks"].items())
added = sum(1 for e in n["hooks"].values() for x in e if "hook_send.sh" in json.dumps(x))
others = all(o[k] == n[k] for k in o if k != "hooks")
print(f"  기존 hooks 항목 동일 {same} · 덧붙인 항목 {added} · hooks 밖 키 동일 {others}")
# 기존 줄 바이트: 원본 각 줄이 설치본에 순서대로 들어 있나
ol = open(sys.argv[1], encoding="utf-8").read().splitlines(); nl = open(sys.argv[2], encoding="utf-8").read().splitlines()
it = iter(nl); print("  원본 줄이 설치본에 순서대로 모두 있음:", all(any(l == m for m in it) for l in ol))
PYX
ls "$W/A" | sed 's/^/  파일 /'
run --settings "$W/A/settings.json" --yes > /dev/null   # 두 번째 설치 — 중복 없어야
echo "  두 번 설치 후 식별 항목 수: $(grep -c hook_send.sh "$W/A/settings.json")"
run --settings "$W/A/settings.json" --uninstall --yes | tail -1
cmp "$W/orig_A.json" "$W/A/settings.json" && echo "  제거 후 원본과 바이트 동일: 예" || echo "  제거 후 원본과 바이트 동일: 아니오"

echo "## B. 다른 형식(indent 4) — 설치 중 바꾼 줄 수"
mkdir -p "$W/B"; mk "$W/B/settings.json" 4; cp "$W/B/settings.json" "$W/orig_B.json"
run --settings "$W/B/settings.json" --yes > /dev/null
run --settings "$W/B/settings.json" --uninstall --yes | tail -1
cmp -s "$W/orig_B.json" "$W/B/settings.json" && echo "  B 제거 후 바이트 동일: 예" || echo "  B 제거 후 바이트 동일: 아니오"

echo "## C. 설치 뒤 사람이 다른 훅을 하나 더한 경우 → 제거"
mkdir -p "$W/C"; mk "$W/C/settings.json" 2
run --settings "$W/C/settings.json" --yes > /dev/null
"$PY" -I -c "import json,sys;p=sys.argv[1];d=json.load(open(p));d['hooks']['Stop'].append({'hooks':[{'type':'command','command':'echo user-added'}]});open(p,'w').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')" "$W/C/settings.json"
run --settings "$W/C/settings.json" --uninstall --yes | tail -1
echo "  사용자 추가 훅 남음: $(grep -c user-added "$W/C/settings.json") · 식별 항목 남음: $(grep -c hook_send.sh "$W/C/settings.json")"

echo "## D. 남의 hook_send.sh (다른 프로젝트 같은 이름 스크립트) 가 이미 있는 경우"
mkdir -p "$W/D"; mk "$W/D/settings.json" 2
"$PY" -I -c "import json,sys;p=sys.argv[1];d=json.load(open(p));d['hooks']['Stop'].append({'hooks':[{'type':'command','command':'bash /other/project/hook_send.sh'}]});open(p,'w').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n')" "$W/D/settings.json"
run --settings "$W/D/settings.json" --yes | tail -1
echo "  Stop 에 agentdash 항목 덧붙음: $(grep -c 'Multi-agent Dashboard/scripts/hook_send.sh' "$W/D/settings.json") (9 이어야)"
run --settings "$W/D/settings.json" --uninstall --yes | tail -1
echo "  남의 /other/project/hook_send.sh 남음: $(grep -c '/other/project/hook_send.sh' "$W/D/settings.json") (1 이어야)"

echo "## E. --yes 없이 (stdin 닫힘) — 실제 경로 실수 실행 흉내 (가짜 파일)"
mkdir -p "$W/E"; mk "$W/E/settings.json" 2; cp "$W/E/settings.json" "$W/orig_E.json"
run --settings "$W/E/settings.json" < /dev/null | tail -2
cmp -s "$W/orig_E.json" "$W/E/settings.json" && echo "  파일 그대로 · 백업 $(ls "$W/E" | grep -c bak) 개"
echo "## F. --yes 가드: claude_home 이 가짜일 때 '다른' settings.json (실제 파일 대역)"
mkdir -p "$W/F/.claude"; mk "$W/F/.claude/settings.json" 2
run --settings "$W/F/.claude/settings.json" --yes | tail -1
"$PY" -I - <<'PYX'
import os, sys
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
import hooks_install as H
from pathlib import Path
print("  is_real_target(~/.claude/settings.json) (AGENTDASH_CLAUDE_HOME=가짜):", H.is_real_target(Path(os.path.expanduser("~/.claude/settings.json"))))
os.environ.pop("AGENTDASH_CLAUDE_HOME")
print("  is_real_target(~/.claude/settings.json) (환경변수 없음):", H.is_real_target(Path(os.path.expanduser("~/.claude/settings.json"))))
os.environ["PYTEST_CURRENT_TEST"] = "x"; os.environ["AGENTDASH_CLAUDE_HOME"] = "/nonexistent-fake"
print("  pytest 중 · 가짜 home 일 때 is_real_target(실제):", H.is_real_target(Path(os.path.expanduser("~/.claude/settings.json"))))
PYX
echo "## G. 송신 스크립트 — 서버 꺼짐 (포트 8099)"
S=$(date +%s.%N 2>/dev/null || python3 -c 'import time;print(time.time())')
OUT=$(echo '{"hook_event_name":"Stop","session_id":"x"}' | AGENTDASH_PORT=8099 bash scripts/hook_send.sh; echo "rc=$?")
E=$(python3 -c 'import time;print(time.time())')
echo "  $OUT · stdout 바이트 $(( ${#OUT} - 4 )) · 시간 $(python3 -c "print(round($E-$S,3))") s"
REAL_MTIME_AFTER=$(stat -f %m ~/.claude/settings.json); REAL_SHA_AFTER=$(shasum ~/.claude/settings.json | cut -c1-40)
echo "## 실제 ~/.claude/settings.json mtime $REAL_MTIME_BEFORE → $REAL_MTIME_AFTER · sha1 같음: $([ "$REAL_SHA_BEFORE" = "$REAL_SHA_AFTER" ] && echo 예 || echo 아니오)"
