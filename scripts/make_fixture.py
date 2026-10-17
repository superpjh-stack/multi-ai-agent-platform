#!/usr/bin/env python
"""실제 기록(읽기만)에서 본문을 지운 픽스처를 만든다 — goal.md §3.1-5 · G-02 · G-13.

    uv run python scripts/make_fixture.py            # tests/fixtures/<cc_version>/ 를 다시 만든다
    uv run python scripts/make_fixture.py --dry-run  # 무엇을 고를지만 찍는다

원천 루트는 `AGENTDASH_CLAUDE_HOME`(기본 ~/.claude — config/settings.yaml) 에서 받는다. 원천은 **읽기만** 한다.

고르는 것
  A. 이 저장소 프로젝트(`-Users-...-Multi-agent-Dashboard`, 저장소 경로에서 계산) 의 세션 1 + `sessions/*.json` 1
     + 깊이 1 서브에이전트 1 (가능하면).
  B. 워크플로가 있는 세션(`projects/*/*/workflows/wf_*.json` 의 첫째) 의 워크플로 1 (실행 기록 + 워크플로 에이전트 전부)
     + 그 세션의 깊이 2 서브에이전트 1 과 그 부모(깊이 1) — 손자 연결(L-02) 회귀용.

지우는 것 — 허용 키(KEEP)가 아닌 **모든 문자열 값**을 "<redacted>" 로 바꾼다 (화이트리스트 방식).
  message.content 의 text/thinking/tool_result, tool_use input 의 command/prompt/content/new_string/old_string,
  user 메시지 문자열, lastPrompt · aiTitle · api-request 본문 · toolUseResult · 워크플로 script/result 등이 모두 여기에 걸린다.
  설명류(description · workflowName · title · label · workflowPhase)는 앞 40 자만, 세션 이름(S1 name)도 앞 40 자만.
남기는 것 — 구조 키 · 숫자 · bool · id · timestamp · model · 도구 이름 · file_path · cwd.

자르는 것 — jsonl 은 앞 HEAD_LINES(200) 줄 + 부모 연결에 필요한 줄(고른 자식의 toolUseId · 워크플로 id 가 나오는 줄).
  자른 사실과 원래 줄 수는 tests/fixtures/<ver>/README.md 에 적는다. tool-results/ · workflows/*/scripts/ · custom-title.json 은
  본문이므로 옮기지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentdash import settings as _settings  # noqa: E402

OUT = ROOT / "tests" / "fixtures"
HEAD_LINES = 200
REDACTED = "<redacted>"

#: 값을 그대로 남기는 문자열 키 (구조 · id · 시각 · 모델 · 도구 이름 · 경로). 300 자를 넘으면 그래도 지운다.
KEEP = {
    # 줄 · 메시지 구조
    "type", "subtype", "level", "role", "uuid", "parentUuid", "leafUuid", "logicalParentUuid", "timestamp",
    "sessionId", "session_id", "requestId", "id", "tool_use_id", "model", "requestedModel", "advisorModel",
    "defaultModel", "stop_reason", "service_tier", "speed", "inference_geo", "version", "entrypoint", "userType",
    "cwd", "gitBranch", "permissionMode", "mode", "kind", "status", "promptId", "messageId", "snapshotMessageId",
    "sourceToolUseID", "sourceToolAssistantUUID", "toolUseID", "effort", "requestRef",
    # 도구
    "name", "file_path", "notebook_path", "filePath", "subagent_type", "skill", "to",
    # 서브에이전트 · 워크플로 메타
    "agentType", "toolUseId", "requestShape", "agentId", "parentAgentId", "runId", "taskId", "scriptPath",
    "trackingPath", "hash", "shapeHash", "requestDigest", "querySource",
}
#: 앞 40 자만 남기는 설명류
TRUNC40 = {"description", "workflowName", "title", "label", "workflowPhase"}


def redact(obj, key: str | None = None):
    if isinstance(obj, dict):
        return {k: redact(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x, key) for x in obj]
    if isinstance(obj, str):
        if key in KEEP and len(obj) <= 300:
            return obj
        if key in TRUNC40:
            return obj[:40]
        return REDACTED
    return obj  # 숫자 · bool · None


def read_jsonl(path: Path, link_ids: set[str]) -> tuple[list[str], dict]:
    """원천 jsonl 을 읽기만 한다 → (본문 지운 줄들, 통계)."""
    out: list[str] = []
    total = kept_link = bad = partial = 0
    with path.open("r", encoding="utf-8") as fh:
        raw = fh.read()
    lines = raw.split("\n")
    if lines and lines[-1] != "":
        partial = 1          # 개행 없는 마지막 줄(쓰는 중) — 옮기지 않는다
    lines = lines[:-1]
    for i, ln in enumerate(lines):
        total += 1
        head = i < HEAD_LINES
        link = (not head) and any(t in ln for t in link_ids)
        if not (head or link):
            continue
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            bad += 1
            continue
        out.append(json.dumps(redact(d), ensure_ascii=False, separators=(",", ":")))
        kept_link += int(link)
    return out, {"total": total, "kept": len(out), "head": min(total, HEAD_LINES), "link": kept_link,
                 "bad_skipped": bad, "partial_skipped": partial}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def first_version(path: Path) -> str:
    with path.open("r", encoding="utf-8") as fh:
        for ln in fh:
            try:
                v = json.loads(ln).get("version")
            except json.JSONDecodeError:
                continue
            if isinstance(v, str) and re.fullmatch(r"[0-9][0-9A-Za-z.\-]*", v):
                return v
    raise SystemExit(f"버전 필드를 못 찾음: {path}")


class Plan:
    def __init__(self, home: Path):
        self.home = home
        self.items: list[tuple[str, Path, str, set[str]]] = []  # (ver, src, kind, link_ids)

    def add(self, ver: str, src: Path, kind: str, link_ids: set[str] | None = None) -> None:
        self.items.append((ver, src, kind, link_ids or set()))


def project_key_of(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def metas_of(session_dir: Path) -> list[tuple[Path, dict]]:
    sub = session_dir / "subagents"
    if not sub.is_dir():
        return []
    return [(m, read_json(m)) for m in sorted(sub.glob("agent-*.meta.json"))]


def plan_a(home: Path, plan: Plan) -> None:
    proj = home / "projects" / project_key_of(ROOT)
    if not proj.is_dir():
        raise SystemExit(f"이 저장소 프로젝트 기록이 없음: {proj}")
    sess_files = {}
    for sj in sorted((home / "sessions").glob("*.json")):
        try:
            sess_files[read_json(sj).get("sessionId")] = sj
        except (json.JSONDecodeError, OSError):
            continue
    candidates = sorted(proj.glob("*.jsonl"))
    # sessions/*.json 이 있는 세션 → 깊이 1 서브에이전트가 있는 세션 순으로 고른다
    def score(p: Path) -> tuple[int, int]:
        sid = p.stem
        has_s1 = sid in sess_files
        has_d1 = any(m.get("spawnDepth") == 1 for _, m in metas_of(proj / sid))
        return (int(has_s1), int(has_d1))
    sess = max(candidates, key=score)
    sid = sess.stem
    ver = first_version(sess)
    child = next(((mp, m) for mp, m in metas_of(proj / sid) if m.get("spawnDepth") == 1), None)
    links = {child[1]["toolUseId"]} if child and child[1].get("toolUseId") else set()
    plan.add(ver, sess, "S2 세션", links)
    if sid in sess_files:
        plan.add(ver, sess_files[sid], "S1 sessions/*.json")
    if child:
        mp, _ = child
        plan.add(ver, mp, "S4 meta (깊이 1)")
        plan.add(ver, mp.with_name(mp.name.replace(".meta.json", ".jsonl")), "S3 서브에이전트 (깊이 1)")


def plan_b(home: Path, plan: Plan) -> None:
    wfs = sorted((home / "projects").glob("*/*/workflows/wf_*.json"))
    if not wfs:
        print("워크플로 기록 없음 — B 건너뜀 (README 에 적는다)")
        return
    wf = wfs[0]
    sdir = wf.parent.parent
    sess = sdir.with_suffix(".jsonl")
    ver = first_version(sess)
    wf_id = wf.stem                       # wf_xxx
    wfd = read_json(wf)
    links = {wf_id}
    if isinstance(wfd.get("runId"), str):
        links.add(wfd["runId"])
    if isinstance(wfd.get("taskId"), str):
        links.add(wfd["taskId"])
    # 깊이 2 서브에이전트 + 부모
    metas = metas_of(sdir)
    by_id = {mp.name[len("agent-"):-len(".meta.json")]: (mp, m) for mp, m in metas}
    d2 = next(((mp, m) for mp, m in metas if (m.get("spawnDepth") or 0) >= 2 and m.get("parentAgentId") in by_id), None)
    parent_links: set[str] = set()
    if d2:
        mp2, m2 = d2
        pmp, pm = by_id[m2["parentAgentId"]]
        if pm.get("toolUseId"):
            links.add(pm["toolUseId"])
        if m2.get("toolUseId"):
            parent_links.add(m2["toolUseId"])
    plan.add(ver, sess, "S2 세션 (워크플로)", links)
    plan.add(ver, wf, "S6 워크플로 실행 기록")
    for p in sorted((sdir / "subagents" / "workflows" / wf_id).glob("*")):
        if p.is_file() and (p.suffix in (".jsonl", ".json")):
            plan.add(ver, p, "S5 워크플로 에이전트" if p.name.startswith("agent-") else "S5 워크플로 부속")
    if d2:
        plan.add(ver, pmp, "S4 meta (깊이 1, 손자의 부모)")
        plan.add(ver, pmp.with_name(pmp.name.replace(".meta.json", ".jsonl")), "S3 서브에이전트 (깊이 1)", parent_links)
        plan.add(ver, mp2, "S4 meta (깊이 2)")
        plan.add(ver, mp2.with_name(mp2.name.replace(".meta.json", ".jsonl")), "S3 서브에이전트 (깊이 2)")


def write(plan: Plan, dry: bool) -> list[Path]:
    home = plan.home
    st = _settings.get()
    versions = sorted({v for v, *_ in plan.items})
    readme_rows: dict[str, list[str]] = {v: [] for v in versions}
    if dry:
        for ver, src, kind, links in plan.items:
            print(f"{ver}  {kind:28s}  {src.relative_to(home)}  링크 {len(links)}")
        return []
    for ver in versions:
        d = OUT / ver
        if st.is_source_path(d):
            raise SystemExit(f"출력이 원천 아래: {d}")
        if d.exists():
            shutil.rmtree(d)          # 저장소 안 tests/fixtures/<ver> 만 (원천 아님 — 위에서 확인)
    written: list[Path] = []
    for ver, src, kind, links in plan.items:
        rel = src.relative_to(home)
        dst = OUT / ver / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".jsonl":
            lines, stat = read_jsonl(src, links)
            dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            cut = "자름" if stat["kept"] < stat["total"] else "전부"
            readme_rows[ver].append(
                f"| `{rel}` | {kind} | {stat['total']} | {stat['kept']} | {cut} — 앞 {stat['head']} 줄 + 연결 줄 {stat['link']}"
                f" · 깨진 줄 제외 {stat['bad_skipped']} · 쓰는 중 마지막 줄 제외 {stat['partial_skipped']} |")
        else:
            data = read_json(src)
            red = redact(data)
            if kind.startswith("S1") and isinstance(data.get("name"), str):
                red["name"] = data["name"][:40]
            dst.write_text(json.dumps(red, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            readme_rows[ver].append(f"| `{rel}` | {kind} | — | — | JSON 전체 (본문 지움) |")
        written.append(dst)
    for ver in versions:
        body = [
            f"# 픽스처 — Claude Code {ver}",
            "",
            "`scripts/make_fixture.py` 가 실제 기록(읽기만)에서 만든 사본이다. **손으로 고치지 않는다** — 다시 만들려면 `make fixtures`.",
            "",
            "- 허용 키(구조 · id · 시각 · 모델 · 도구 이름 · 경로) 밖의 문자열 값은 전부 `\"<redacted>\"` 이다.",
            "- 설명류(`description` · `workflowName` · `title` · `label` · `workflowPhase`)와 S1 `name` 은 앞 40 자만 남겼다.",
            f"- jsonl 은 앞 {HEAD_LINES} 줄 + 부모 연결에 필요한 줄(고른 자식의 `toolUseId` · 워크플로 id 가 나오는 줄)만 남겼다. 아래 표의 `원래 줄` ≠ `남긴 줄` 이면 자른 것이다.",
            "- 줄 사이 `parentUuid` 사슬은 잘린 곳에서 끊긴다 (앞 줄이 빠진 연결 줄). 파서 테스트는 이것을 허용해야 한다.",
            "- 옮기지 않은 것: `tool-results/`(S7 본문) · `workflows/*/scripts/`(워크플로 스크립트 본문) · `custom-title.json` · `memory/`.",
            "- 검사: `uv run python scripts/check_fixtures_redacted.py` (G-13).",
            "",
            "| 파일 (원천 루트 기준) | 원천 | 원래 줄 | 남긴 줄 | 처리 |",
            "|---|---|---|---|---|",
            *readme_rows[ver],
            "",
        ]
        (OUT / ver / "README.md").write_text("\n".join(body), encoding="utf-8")
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    home = _settings.get().claude_home
    plan = Plan(home)
    plan_a(home, plan)
    plan_b(home, plan)
    written = write(plan, args.dry_run)
    if not args.dry_run:
        vers = sorted({p.relative_to(OUT).parts[0] for p in written})
        print(f"픽스처 {len(written)} 파일 → tests/fixtures/{{{','.join(vers)}}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
