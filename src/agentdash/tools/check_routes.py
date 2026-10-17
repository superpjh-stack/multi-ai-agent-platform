#!/usr/bin/env python
"""G-17 check_routes — 화면 6 + API 10 (spec.md §7 · §8) 전부 HTTP 200, 빈 DB 에서도.

    uv run python src/agentdash/tools/check_routes.py

  · 목록은 spec.md 에서 읽는다: `### D-0n 이름 `/경로`` 6 개 · `| `GET|POST /경로` |` 10 개. 개수가 6 · 10 이 아니면 FAIL.
  · 앱에 그 메서드 · 경로가 등록돼 있어야 한다(경로 변수는 `{key}` → 표본 `S:fixture`).
  · 임시 빈 DB(schema 11 테이블, 행 0)를 AGENTDASH_DB 로 주고 TestClient 로 부른다 — 서버를 띄우지 않는다.
  · placeholder 수(HTML `data-placeholder` · JSON `_placeholder` · SSE 본문)를 실측에 적는다. placeholder 도 200 이면 PASS
    (Phase 0 기대) — 남은 placeholder 수는 웨이브 B 의 진척 지표다.
출력: `G-17  화면 · API  PASS|FAIL  실측`
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

SPEC = ROOT / "spec.md"
SAMPLE = {"key": "S:fixture"}


def spec_routes() -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    text = SPEC.read_text(encoding="utf-8")
    pages = [(m.group(1), m.group(2), m.group(3)) for m in re.finditer(r"^### (D-0[1-6]) (.+?) `(/[^`]*)`", text, re.M)]
    apis = [(m.group(1), m.group(2).split("?")[0]) for m in re.finditer(r"^\| `(GET|POST) (/[^`]*)`", text, re.M)]
    return pages, apis


def fill(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: SAMPLE.get(m.group(1), "x"), path).replace("{agent_key}", SAMPLE["key"])


def iter_routes(routes, prefix: str = ""):
    """(경로, 메서드) — FastAPI 0.14x 의 include 래퍼(_IncludedRouter.original_router)도 펼친다."""
    for r in routes:
        inner = getattr(r, "original_router", None)
        if inner is not None:
            yield from iter_routes(inner.routes, prefix + (getattr(inner, "prefix", "") or ""))
        elif getattr(r, "path", None) is not None:
            yield prefix + r.path, set(getattr(r, "methods", None) or ())


def main() -> int:
    pages, apis = spec_routes()
    tmp = Path(tempfile.mkdtemp(prefix="agentdash-routes-"))
    os.environ["AGENTDASH_DB"] = str(tmp / "empty.db")
    from agentdash.db import conn

    conn.init_db(os.environ["AGENTDASH_DB"])
    from fastapi.testclient import TestClient

    from agentdash.app.main import app

    registered = {(m, path) for path, methods in iter_routes(app.routes) for m in methods}
    bad: list[str] = []
    ok = placeholders = 0
    client = TestClient(app)
    targets = [("GET", re.sub(r"\{agent_key\}", "{key}", p), f"{code} {name}") for code, name, p in pages]
    targets += [(m, p, f"{m} {p}") for m, p in apis]
    for method, path, label in targets:
        if (method, path) not in registered:
            bad.append(f"{label}: 앱에 없음 ({method} {path})")
            continue
        url = fill(path)
        r = client.request(method, url, json={} if method == "POST" else None,
                           headers={"accept": "text/html"} if not path.startswith(("/api", "/hooks")) else {})
        body = r.text
        if r.status_code != 200:
            bad.append(f"{label}: HTTP {r.status_code}")
            continue
        ok += 1
        if "data-placeholder" in body or "_placeholder" in body:
            placeholders += 1
    count_bad = []
    if len(pages) != 6:
        count_bad.append(f"spec 화면 {len(pages)} ≠ 6")
    if len(apis) != 10:
        count_bad.append(f"spec API {len(apis)} ≠ 10")
    bad = count_bad + bad
    for b in bad:
        print("  위반", b)
    total = len(targets)
    detail = f"화면 {len(pages)} + API {len(apis)} = {total} 중 HTTP 200 {ok} (빈 DB) · placeholder {placeholders}"
    print(f"G-17  화면 · API  {'PASS' if not bad else 'FAIL'}  {detail}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
