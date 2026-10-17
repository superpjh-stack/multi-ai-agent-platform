#!/usr/bin/env bash
# agentdash 훅 송신 (spec.md §9.2) — Claude Code 훅이 부른다. 담당 개발2.
#   표준입력 JSON → POST http://127.0.0.1:${AGENTDASH_PORT:-8095}/hooks/event
#   · 항상 exit 0 · 표준출력 0 바이트 · 표준에러도 버린다 (Claude Code 동작에 영향 0)
#   · curl -m 1 — 1 초 안에 못 보내면 버린다. 서버가 꺼져 있으면 연결 거부로 바로 끝난다.
#   · 127.0.0.1 만. 본문 걸러내기는 수신기(hooks_rx)가 한다 — 여기서는 저장하지 않는다.
# 식별 표시: 이 파일 이름(hook_send.sh)이 settings.json 명령 문자열에 들어 있어야 hooks_install.py 가 알아본다.
port="${AGENTDASH_PORT:-8095}"
case "$port" in (*[!0-9]*|'') port=8095 ;; esac
if command -v curl >/dev/null 2>&1; then
  curl -m 1 --connect-timeout 0.5 -s -o /dev/null -X POST -H 'Content-Type: application/json' \
       "http://127.0.0.1:${port}/hooks/event" --data-binary @- >/dev/null 2>&1 || true
else
  cat >/dev/null 2>&1 || true
fi
exit 0
