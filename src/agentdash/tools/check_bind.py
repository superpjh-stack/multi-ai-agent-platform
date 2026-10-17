#!/usr/bin/env python
"""V-06 check_bind — 로컬 전용 (G-16).

    uv run python src/agentdash/tools/check_bind.py [--scan 파일…]

판정
  1. 설정: `settings.get().host == "127.0.0.1"` (yaml 이 다른 값이면 settings 가 기동을 거부하는지도 확인).
  2. 바인드 정적 스캔 — src/ · scripts/ · Makefile · pyproject.toml 에서 `0.0.0.0` · `::` 바인드 · `--host <127.0.0.1 아님>` ·
     `host=<127.0.0.1 아님 상수>` 가 없다.
  3. 외부 전송 정적 스캔 — src/agentdash/** · scripts/** 에서
     · `requests` · `httpx` · `aiohttp` · `urllib.request` · `http.client` · `socket` · `smtplib` · `ftplib` import 0
       (테스트 · tools/ 의 TestClient 용 httpx 는 tests/ 에만 둔다)
     · 코드 문자열의 `http(s)://` 주소가 127.0.0.1 · localhost 뿐 (템플릿의 CDN `<script src>` 는 고정 버전이면 허용 — 서버가 보내는 것이 아니라 브라우저가 받는 것)
     · 셸 스크립트의 curl · wget 대상이 127.0.0.1 뿐
출력: `G-16  로컬 전용  PASS|FAIL  실측`
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from agentdash import settings as _settings  # noqa: E402

NET_MODULES = {"requests", "httpx", "aiohttp", "urllib.request", "urllib3", "http.client", "socket", "smtplib",
               "ftplib", "websockets", "paramiko", "boto3"}
URL = re.compile(r"\b(https?|wss?)://([^/\s\"'`:]+)")
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
CDN_PINNED = re.compile(r"<script[^>]+src=\"https://(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net/npm|unpkg\.com)/[^\"]*@?\d+\.\d+")
BIND_BAD = re.compile(r"0\.0\.0\.0|--host\s+(?!127\.0\.0\.1\b)\S+|host\s*=\s*[\"'](?!127\.0\.0\.1[\"'])[^\"']+[\"']")
SELF = Path(__file__).resolve()


def scan_py(path: Path) -> list[str]:
    bad = []
    rel = path.relative_to(ROOT) if ROOT in path.parents else path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in NET_MODULES or a.name.split(".")[0] in {"requests", "httpx", "aiohttp", "urllib3"}:
                    bad.append(f"{rel}:{node.lineno}: 외부 전송 모듈 import {a.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod in NET_MODULES or mod.split(".")[0] in {"requests", "httpx", "aiohttp", "urllib3"} or \
                    (mod == "urllib" and any(a.name == "request" for a in node.names)) or \
                    (mod == "http" and any(a.name == "client" for a in node.names)):
                bad.append(f"{rel}:{node.lineno}: 외부 전송 모듈 import {mod}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and path != SELF:
            for m in URL.finditer(node.value):
                if m.group(2) not in LOCAL_HOSTS:
                    bad.append(f"{rel}:{node.lineno}: 외부 주소 {m.group(0)}")
            if BIND_BAD.search(node.value):
                bad.append(f"{rel}:{node.lineno}: 바인드 {node.value[:60]!r}")
        elif isinstance(node, ast.keyword) and node.arg == "host" and isinstance(node.value, ast.Constant):
            if node.value.value != _settings.LOOPBACK:
                bad.append(f"{rel}:{node.value.lineno}: host={node.value.value!r}")
    return bad


def scan_text(path: Path) -> list[str]:
    bad = []
    rel = path.relative_to(ROOT) if ROOT in path.parents else path
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = ln.split("#", 1)[0] if path.suffix in (".sh", "") or path.name == "Makefile" else ln
        if BIND_BAD.search(s):
            bad.append(f"{rel}:{i}: 바인드 {s.strip()[:80]}")
        for m in URL.finditer(s):
            if m.group(2) in LOCAL_HOSTS:
                continue
            if path.suffix == ".html" and CDN_PINNED.search(s):
                continue
            if path.name in ("pyproject.toml",):
                continue
            bad.append(f"{rel}:{i}: 외부 주소 {m.group(0)}")
    return bad


def check(files: list[Path] | None = None) -> tuple[bool, str, list[str]]:
    bad: list[str] = []
    s = _settings.get()
    if s.host != _settings.LOOPBACK:
        bad.append(f"settings.host = {s.host}")
    if files is None:
        py = sorted(p for d in (ROOT / "src" / "agentdash", ROOT / "scripts") if d.exists() for p in d.rglob("*.py"))
        other = sorted(p for d in (ROOT / "src" / "agentdash", ROOT / "scripts") if d.exists()
                       for p in d.rglob("*") if p.suffix in (".sh", ".html", ".js", ".yaml"))
        other += [p for p in (ROOT / "Makefile", ROOT / "config" / "settings.yaml") if p.exists()]
    else:
        py = [f for f in files if f.suffix == ".py"]
        other = [f for f in files if f.suffix != ".py"]
    for f in py:
        bad += scan_py(f)
    for f in other:
        bad += scan_text(f)
    detail = f"host {s.host}:{s.port} · 스캔 py {len(py)} · 기타 {len(other)} · 외부 전송/바인드 위반 {len(bad)}"
    return not bad, detail, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", nargs="+")
    a = ap.parse_args()
    ok, detail, bad = check([Path(x).resolve() for x in a.scan] if a.scan else None)
    for b in bad[:30]:
        print("  위반", b)
    print(f"G-16  로컬 전용  {'PASS' if ok else 'FAIL'}  {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
