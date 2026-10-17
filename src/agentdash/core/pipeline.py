"""파이프라인 진척 판정 (spec.md §7.1 P-01~P-07) — 담당 개발1.

원천(settings.agents_root 아래 `<NN> * Agent/{outputs,progress.md}`)은 **읽기만** 한다: 폴더 · 파일 이름과 mtime,
run.json 의 회사 키(config `run_json_company_keys` — 본문 키 notes 등은 읽지 않는다), progress.md 의 `## ` · `### ` 표제와
표 행(`|`)에서 회사 이름 · 상태 키워드가 있는지만 본다. 본문은 저장하지 않는다 — 근거는 `파일:줄` 로만 남긴다.

회사 · 단계 · 패턴 · 키워드는 전부 config/{companies,pipeline}.yaml 에서 읽는다 (코드에 박지 않는다).
  · 이름 정규화: normalize_strip(공백 · 주식회사 · (주)) 를 지우고 표준 이름 · 별칭과 비교. 사전에 없는 이름은 칸을 만들지 않고
    「미등록 회사 N 건」(파일명 · 폴더명의 {회사} 자리 · run.json 회사 키에서 나온 것).
  · 제외: exclude(_구판_* · _preview* · scratch/ · tour/) 가 경로 성분 하나라도 맞으면 세지 않는다.
  · 같은 산출물 여러 벌 → 가장 높은 v · 가장 최근 실행(실행 폴더 이름) · 최근 mtime 순.
  · 실행 폴더의 회사 = run.json 회사 키 → 폴더 안 산출물 파일명의 {회사} 자리 순.
판정 (위에서부터): P-01 NEEDS_DECISION(배지, 기저 상태는 base_status) · P-02 IN_PROGRESS · P-03 DONE · P-04 PARTIAL ·
P-05 DONE+파일 없음 · P-06 NOT_STARTED · P-07 UNKNOWN(단계 규칙 없음).
추가: 뒤처짐 ↻(upstream 단계의 최신 실행 시각 > 이 칸 산출물 최신 mtime) · 마지막 손댄 에이전트(file_touch).
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path

from agentdash import settings
from agentdash.core import model as M

KST = timezone(timedelta(hours=9))
STATUSES = ("DONE", "PARTIAL", "IN_PROGRESS", "NEEDS_DECISION", "NOT_STARTED", "UNKNOWN")
_VER = re.compile(r"_v(\d+(?:\.\d+)*)\.[^./]+$")
_RUN_TS = re.compile(r"^(\d{8}-\d{6})")


def nfc(s: str) -> str:
    """macOS 파일 이름은 한글이 NFD(자모 분리)로 올 수 있다 — 비교 전에 NFC 로 모은다 (D-15)."""
    return unicodedata.normalize("NFC", s)


# ── 설정 ──────────────────────────────────────────────────────────────
@dataclass
class Dictionary:
    strip: list[str]
    names: list[str]                       # 표준 이름 (companies.yaml 순)
    norm: dict[str, str]                   # 정규화 이름(표준 · 별칭) → 표준 이름
    variants: dict[str, list[str]]         # 표준 이름 → 원래 표기(표준 + 별칭)

    def normalize(self, s: str) -> str:
        s = nfc(s)
        for t in self.strip:
            s = "".join(s.split(t))   # 문자열 지우기 (파일 이름 바꾸기 아님)
        return s

    def lookup(self, slot: str | None) -> str | None:
        """파일명 · 폴더명의 {회사} 자리 값 → 표준 이름 (정확히 같을 때만)."""
        if not slot:
            return None
        return self.norm.get(self.normalize(slot))

    def find_in(self, text: str) -> set[str]:
        """문자열 안에 든 회사(표준 이름) — 표제 · 표 행 · 도구 대상용."""
        t = self.normalize(text)
        return {std for n, std in self.norm.items() if n and n in t}


def load_dictionary() -> Dictionary:
    raw = settings.load_yaml("companies.yaml")
    strip = list(raw.get("normalize_strip") or [])
    d = Dictionary(strip=strip, names=[], norm={}, variants={})
    for c in raw["companies"]:
        std = c["name"]
        d.names.append(std)
        d.variants[std] = [std, *(c.get("aliases") or [])]
        for v in d.variants[std]:
            d.norm[d.normalize(v)] = std
    return d


def load_pipeline() -> dict:
    p = settings.load_yaml("pipeline.yaml")
    for k in ("display_order", "exclude", "stages", "progress_rules"):
        if k not in p:
            raise settings.SettingsError(f"config/pipeline.yaml 에 {k} 없음")
    return p


# ── 파일 패턴 ─────────────────────────────────────────────────────────
def glob_regex(glob: str, labels: list[str]) -> re.Pattern:
    """경로 성분 하나의 glob → 정규식. {회사} = 이름 자리(밑줄 · / 없음), {사업} = business_labels 중 하나."""
    glob = nfc(glob)
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("{회사}", i):
            out.append(r"(?P<co>[^_/]+)")
            i += 4
        elif glob.startswith("{사업}", i):
            out.append("(?:" + "|".join(re.escape(x) for x in labels) + ")" if labels else r"[^_/]+")
            i += 4
        elif glob[i] == "*":
            out.append(r"[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def excluded(rel_parts: tuple[str, ...], patterns: list[str]) -> bool:
    for part in rel_parts:
        for p in patterns:
            if fnmatch(nfc(part), nfc(p.rstrip("/"))):
                return True
    return False


def version_of(name: str) -> tuple[int, ...] | None:
    m = _VER.search(name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def vstr(v: tuple[int, ...] | None) -> str | None:
    return ("v" + ".".join(str(x) for x in v)) if v else None


@dataclass
class Candidate:
    path: Path
    rel: str                     # agents_root 기준
    version: tuple[int, ...] | None
    run: str | None
    mtime: float

    def key(self):
        return (self.version or (), self.run or "", self.mtime)


@dataclass
class StageScan:
    found: dict[str, dict[str, list[Candidate]]] = field(default_factory=dict)   # 회사 → 산출물 id → 후보
    runs: dict[str, list[tuple[str, float, str]]] = field(default_factory=dict)  # 회사 → [(run_id, 시각 epoch, 근거)]
    unregistered: dict[str, str] = field(default_factory=dict)                   # 이름 → 근거 경로
    mismatch: list[str] = field(default_factory=list)                            # 실행 회사 ≠ 파일 회사 (세지 않음)
    folder_missing: bool = False


def _list_dirs(base: Path, pattern: str, labels: list[str]) -> list[tuple[Path, str | None]]:
    """base 아래 pattern(성분별 glob, {회사} 가능) 에 맞는 폴더 [(경로, 폴더명의 {회사} 자리)]."""
    cur: list[tuple[Path, str | None]] = [(base, None)]
    for comp in [c for c in pattern.split("/") if c]:
        rx = glob_regex(comp, labels)
        nxt = []
        for d, co in cur:
            if not d.is_dir():
                continue
            for child in sorted(d.iterdir()):
                if not child.is_dir():
                    continue
                m = rx.match(nfc(child.name))
                if m:
                    nxt.append((child, m.groupdict().get("co") or co))
        cur = nxt
    return cur


def _run_json_company(run_dir: Path, keys: list[str], dic: Dictionary) -> tuple[str | None, str | None]:
    """run.json 의 회사 키 → (표준 이름, 미등록 이름). 본문 키는 읽지 않는다(값을 저장하지도 않는다)."""
    p = run_dir / "run.json"
    if not p.is_file():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    for k in keys:
        v = data.get(k)
        if not isinstance(v, str) or not v:
            continue
        hit = dic.find_in(v)
        if len(hit) == 1:
            return next(iter(hit)), None
        if not hit and k in ("company", "company_name"):
            return None, v[:60]
    return None, None


def _run_time(run_dir: Path) -> float | None:
    """실행 시각 — run.json started(KST) → 폴더 이름 YYYYMMDD-HHMMSS(KST)."""
    p = run_dir / "run.json"
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            s = d.get("started") if isinstance(d, dict) else None
            if isinstance(s, str):
                return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).timestamp()
        except (OSError, ValueError):
            pass
    m = _RUN_TS.match(run_dir.name)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=KST).timestamp()
    return None


def scan_stage(root: Path, st: dict, cfg: dict, dic: Dictionary) -> StageScan:
    out = StageScan()
    folder = root / st["folder"]
    if not folder.is_dir():
        out.folder_missing = True
        return out
    labels = list(cfg.get("business_labels") or [])
    keys = list(cfg.get("run_json_company_keys") or [])
    excl = list(cfg.get("exclude") or [])
    items = st.get("match") or []
    run_company: dict[Path, str | None] = {}
    for it in items:
        frx = glob_regex(it["file"], labels)
        for d, dir_co in _list_dirs(folder, it["dir"], labels):
            rel_parts = tuple(nfc(x) for x in d.relative_to(folder).parts)
            if excluded(rel_parts, excl):
                continue
            if dir_co is not None and dic.lookup(dir_co) is None:
                out.unregistered.setdefault(dir_co, str(d.relative_to(root)))
                continue
            files = []
            for f in sorted(d.iterdir()):
                if not f.is_file() or excluded((nfc(f.name),), excl):
                    continue
                m = frx.match(nfc(f.name))
                if not m:
                    continue
                slot = m.groupdict().get("co")
                std = dic.lookup(slot)
                if std is None:
                    out.unregistered.setdefault(slot or "?", str(f.relative_to(root)))
                    continue
                files.append((f, std))
            company_of_dir = dic.lookup(dir_co) if dir_co else None
            run_id = None
            if it.get("run"):
                run_id = d.name
                if d not in run_company:
                    rc, unreg = _run_json_company(d, keys, dic)
                    if unreg:
                        out.unregistered.setdefault(unreg, str((d / "run.json").relative_to(root)))
                    if rc is None:          # run.json 에 회사 없음 → 폴더 안 산출물 파일명 (모든 항목 패턴)
                        seen: dict[str, int] = {}
                        for it2 in items:
                            rx2 = glob_regex(it2["file"], labels)
                            for f2 in d.iterdir():
                                m2 = rx2.match(nfc(f2.name)) if f2.is_file() else None
                                s2 = dic.lookup(m2.groupdict().get("co")) if m2 else None
                                if s2:
                                    seen[s2] = seen.get(s2, 0) + 1
                        rc = max(seen, key=lambda k: seen[k]) if seen else None
                    run_company[d] = rc
                    if rc:
                        t = _run_time(d)
                        if t is not None:
                            src = "run.json" if (d / "run.json").is_file() else "폴더 이름"
                            out.runs.setdefault(rc, []).append((d.name, t, f"{d.relative_to(root)}/{src}"))
                company_of_dir = run_company[d]
            for f, std in files:
                if company_of_dir and std != company_of_dir:
                    out.mismatch.append(str(f.relative_to(root)))
                    continue
                c = Candidate(path=f, rel=nfc(str(f.relative_to(root))), version=version_of(f.name), run=run_id,
                              mtime=f.stat().st_mtime)
                out.found.setdefault(std, {}).setdefault(it["id"], []).append(c)
    return out


# ── progress.md ───────────────────────────────────────────────────────
@dataclass
class ProgressRefs:
    rel: str | None = None
    decision: dict[str, list[int]] = field(default_factory=dict)   # 회사 → 줄 (P-01)
    done: dict[str, list[int]] = field(default_factory=dict)       # 회사 → 줄 (P-05)
    waves: list[tuple[int, str, str]] = field(default_factory=list)  # (줄, 이름, 표시)


def read_progress(root: Path, st: dict, rules: dict, dic: Dictionary) -> ProgressRefs:
    """표제(`## ` · `### `)와 표 행만 본다. 돌려주는 것은 회사 이름 · 줄 번호 · 웨이브 표시뿐."""
    p = root / st["folder"] / "progress.md"
    out = ProgressRefs()
    if not p.is_file():
        return out
    out.rel = str(p.relative_to(root))
    section = rules.get("decision_section", "## 지금 해야 할 것").strip()
    dkeys = list(rules.get("decision_keywords") or [])
    done_kw = rules.get("done_keyword", "완료")
    marks = list(st.get("wave_marks") or [])
    in_decision = False
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        for no, line in enumerate(fh, 1):
            s = line.rstrip("\n")
            is_h2 = s.startswith("## ")
            is_head = is_h2 or s.startswith("### ")
            is_row = s.lstrip().startswith("|")
            if is_h2:
                in_decision = s.strip() == section
            if not (is_head or is_row):
                continue
            cos = dic.find_in(s)
            if in_decision and cos and any(k in s for k in dkeys):
                for c in cos:
                    out.decision.setdefault(c, []).append(no)
            if is_head and cos and done_kw in s:
                for c in cos:
                    out.done.setdefault(c, []).append(no)
            if is_h2 and marks:
                found = [mk for mk in marks if mk in s]
                if found:
                    name = s[3:].split("—")[0].strip()
                    for mk in marks:
                        name = "".join(name.split(mk)).strip()
                    out.waves.append((no, name[:30], found[0]))
    return out


# ── 판정 ──────────────────────────────────────────────────────────────
@dataclass
class Cell:
    company: str
    stage: str
    status: str
    base_status: str
    rule: str
    base_rule: str
    have: int | None
    need: int | None
    version: str | None = None
    run_id: str | None = None
    last_file_at: str | None = None
    last_session: str | None = None
    lag: bool = False
    lag_note: str | None = None
    note: str | None = None
    src: str = ""
    files: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    wave: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Result:
    stages: list[dict]
    companies: list[str]
    cells: list[Cell]
    unregistered: dict[str, str]
    mismatch: int
    evaluated_at: str
    root: str

    def cell(self, company: str, stage: str) -> Cell | None:
        for c in self.cells:
            if c.company == company and c.stage == stage:
                return c
        return None

    def next_stage(self) -> dict[str, str | None]:
        out = {}
        for co in self.companies:
            out[co] = None
            for st in self.stages:
                c = self.cell(co, st["code"])
                if c and c.base_status not in ("DONE", "UNKNOWN"):
                    out[co] = st["code"]
                    break
        return out

    def counts(self) -> dict[str, int]:
        n: dict[str, int] = {s: 0 for s in STATUSES}
        for c in self.cells:
            n[c.status] = n.get(c.status, 0) + 1
        return n

    def as_dict(self) -> dict:
        return {
            "evaluated_at": self.evaluated_at, "stages": self.stages, "companies": self.companies,
            "cells": [c.as_dict() for c in self.cells], "next_stage": self.next_stage(),
            "unregistered": len(self.unregistered), "unregistered_names": sorted(self.unregistered),
            "unknown_cells": sum(1 for c in self.cells if c.status == "UNKNOWN"),
            "counts": self.counts(), "mismatch_files": self.mismatch,
        }


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def _kst(ts: float) -> str:
    return datetime.fromtimestamp(ts, KST).strftime("%Y-%m-%d %H:%M")


def _active_companies(con: sqlite3.Connection | None, stage_dir: Path, window_min: int, now: datetime,
                      dic: Dictionary) -> dict[str, list[str]]:
    """P-02 — 단계 폴더에서 RUNNING / WAITING_* 인 에이전트가 최근 window 분 안에 회사 이름이 든 대상을 다뤘거나 이름에 회사가 있다."""
    if con is None:
        return {}
    cutoff = (now - timedelta(minutes=window_min)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    base = str(stage_dir)
    out: dict[str, list[str]] = {}
    rows = con.execute("SELECT agent_key, name, state, project_path FROM agent "
                       "WHERE (state = 'RUNNING' OR state LIKE 'WAITING_%') AND project_path IS NOT NULL").fetchall()
    for key, name, state, pp in rows:
        if not (pp == base or pp.startswith(base + "/")):
            continue
        texts = [name or ""]
        texts += [r[0] for r in con.execute("SELECT target FROM tool_call WHERE agent_key=? AND at >= ? AND target IS NOT NULL",
                                            (key, cutoff))]
        texts += [r[0] for r in con.execute("SELECT path FROM file_touch WHERE agent_key=? AND at >= ?", (key, cutoff))]
        for t in texts:
            for c in dic.find_in(t):
                ev = f"{key} {state}"
                if ev not in out.setdefault(c, []):
                    out[c].append(ev)
    return out


def _last_session(con: sqlite3.Connection | None, paths: list[Path]) -> str | None:
    if con is None or not paths:
        return None
    best = None
    for i in range(0, len(paths), 400):
        part = sorted({v for p in paths[i:i + 400] for v in (str(p), nfc(str(p)))})
        r = con.execute(f"SELECT agent_key, at FROM file_touch WHERE path IN ({','.join('?' * len(part))}) "
                        "ORDER BY at DESC LIMIT 1", part).fetchone()
        if r and (best is None or (r[1] or "") > (best[1] or "")):
            best = r
    return best[0] if best else None


def _src(parts: list[str]) -> str:
    s = " · ".join(p for p in parts if p)
    return M.clip(s, 300) or ""


def evaluate(con: sqlite3.Connection | None = None, now: datetime | None = None, root: Path | None = None) -> Result:
    now = now or datetime.now(timezone.utc)
    root = root or settings.get().agents_root
    dic = load_dictionary()
    cfg = load_pipeline()
    rules = cfg["progress_rules"]
    window = int(rules.get("in_progress_window_min", 30))
    order = [str(x) for x in cfg["display_order"]]
    stages_cfg = {str(k): v for k, v in cfg["stages"].items()}
    scans = {code: scan_stage(root, stages_cfg[code], cfg, dic) for code in order}
    progs = {code: read_progress(root, stages_cfg[code], rules, dic) for code in order}
    upstream = {str(k): [str(x) for x in v] for k, v in (cfg.get("upstream") or {}).items()}
    unregistered: dict[str, str] = {}
    mismatch = 0
    for sc in scans.values():
        for k, v in sc.unregistered.items():
            unregistered.setdefault(k, v)
        mismatch += len(sc.mismatch)

    chosen: dict[tuple[str, str], list[Candidate]] = {}
    cells: list[Cell] = []
    for code in order:
        st = stages_cfg[code]
        sc, pr = scans[code], progs[code]
        items = st.get("match") or []
        has_rule = bool(items) and st.get("need") is not None
        active = _active_companies(con, root / st["folder"], window, now, dic)
        prog_ref = (lambda lines: [f"{pr.rel}:{n}" for n in lines]) if pr.rel else (lambda lines: [])
        for co in dic.names:
            files: list[Candidate] = []
            missing: list[str] = []
            for it in items:
                cands = sc.found.get(co, {}).get(it["id"], [])
                if cands:
                    files.append(max(cands, key=Candidate.key))
                else:
                    missing.append(it["id"])
            chosen[(co, code)] = files
            have = len(files) if has_rule else None
            need = len(items) if has_rule else None
            src: list[str] = []
            notes: list[str] = []
            if has_rule and need != st.get("need"):
                notes.append(f"need 설정 {st.get('need')} ≠ 패턴 {need}")
            if sc.folder_missing:
                notes.append(f"폴더 없음 {st['folder']}")
            # 기저 상태
            if co in active:
                base, brule = "IN_PROGRESS", "P-02"
                src.append("실행 중 " + ", ".join(active[co][:3]))
            elif not has_rule:
                base, brule = "UNKNOWN", "P-07"
                src.append(f"config/pipeline.yaml stages.{code}: 규칙 없음 (P-07)")
            elif have == need:
                base, brule = "DONE", "P-03"
            elif have and have > 0:
                base, brule = "PARTIAL", "P-04"
                notes.append("없음: " + ", ".join(missing))
            elif co in pr.done:
                base, brule = "DONE", "P-05"
                notes.append("⚠ 파일 없음 — progress.md 표제는 완료")
                src += prog_ref(pr.done[co][:3])
            else:
                base, brule = "NOT_STARTED", "P-06"
                src.append(f"{st['folder']}/outputs 패턴 0 건 (config/pipeline.yaml stages.{code}.match)")
            if files:
                files_sorted = sorted(files, key=lambda c: c.rel)
                src.insert(0, files_sorted[0].rel + (f" 외 {len(files) - 1}" if len(files) > 1 else ""))
            status, rule = base, brule
            progress_lines: list[str] = []
            if co in pr.decision:
                status, rule = "NEEDS_DECISION", "P-01"
                progress_lines = prog_ref(pr.decision[co])
                src.insert(0, ", ".join(progress_lines[:3]))
                notes.insert(0, f"판단 필요 — 기저 {base} ({brule})")
            if co in pr.done and brule != "P-05":
                progress_lines += prog_ref(pr.done[co][:5])
            wave = None
            if st.get("wave_company") == co and pr.waves:
                wave = " · ".join(f"{n} {mk}" for _, n, mk in pr.waves)
                notes.append("웨이브 " + wave)
                src.append(", ".join(f"{pr.rel}:{ln}" for ln, _, _ in pr.waves[:5]))
            last_ts = max((c.mtime for c in files), default=None)
            runs = [c.run for c in files if c.run]
            vers = [c.version for c in files if c.version]
            cell = Cell(company=co, stage=code, status=status, base_status=base, rule=rule, base_rule=brule,
                        have=have, need=need, version=vstr(max(vers)) if vers else None,
                        run_id=max(runs) if runs else None, last_file_at=_iso(last_ts),
                        last_session=_last_session(con, [c.path for c in files]),
                        files=[c.rel for c in sorted(files, key=lambda c: c.rel)], progress=progress_lines,
                        missing=missing, wave=wave)
            cell.note = M.clip(" · ".join(notes), 300) if notes else None
            cell.src = _src(src)
            cells.append(cell)

    # 뒤처짐 ↻ — 앞 단계 최신 실행(run.json 시각, 실행 폴더가 없는 단계는 산출물 최신 mtime) > 이 칸 산출물 최신 mtime
    for c in cells:
        ups = upstream.get(c.stage) or []
        files = chosen.get((c.company, c.stage)) or []
        if not ups or not files:
            continue
        down = max(f.mtime for f in files)
        for u in ups:
            runs = scans[u].runs.get(c.company) or []
            if stages_cfg[u].get("match") and any(i.get("run") for i in stages_cfg[u]["match"]) and runs:
                rid, t, ev = max(runs, key=lambda r: r[1])
            else:
                ufiles = chosen.get((c.company, u)) or []
                if not ufiles:
                    continue
                f = max(ufiles, key=lambda x: x.mtime)
                rid, t, ev = None, f.mtime, f.rel
            if t > down:
                c.lag = True
                c.lag_note = M.clip(f"↻ 앞 단계 갱신됨 — {u} {rid or ''} {_kst(t)} > 이 칸 {_kst(down)}", 300)
                c.note = M.clip(" · ".join(x for x in (c.note, c.lag_note) if x), 300)
                c.src = _src([c.src, ev])
                break
    stages = [{"code": code, "label": stages_cfg[code].get("label"), "folder": stages_cfg[code]["folder"],
               "need": stages_cfg[code].get("need") if stages_cfg[code].get("match") else None} for code in order]
    return Result(stages=stages, companies=list(dic.names), cells=cells, unregistered=unregistered, mismatch=mismatch,
                  evaluated_at=now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), root=str(root))


# ── 저장 · 캐시 ───────────────────────────────────────────────────────
def store(con: sqlite3.Connection, res: Result) -> int:
    """pipeline_cell 을 통째로 바꾼다 (커밋하지 않는다). TEXT 는 전부 ≤ 300 자."""
    con.execute("DELETE FROM pipeline_cell")
    for c in res.cells:
        con.execute(
            "INSERT INTO pipeline_cell (company, stage, status, rule, have, need, version, run_id, last_file_at, "
            "last_session, note, src, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c.company, c.stage, c.status, c.rule, c.have, c.need, c.version, c.run_id, c.last_file_at,
             c.last_session, M.clip(c.note, 300), M.clip(c.src, 300), res.evaluated_at))
    return len(res.cells)


def refresh(con: sqlite3.Connection, now: datetime | None = None) -> Result:
    res = evaluate(con, now)
    store(con, res)
    return res


def signature(root: Path | None = None) -> tuple:
    """변경 감지 — 단계 폴더 outputs/ 와 그 바로 아래 폴더 · progress.md 의 mtime."""
    root = root or settings.get().agents_root
    cfg = load_pipeline()
    sig = [str(root)]
    for st in cfg["stages"].values():
        f = root / st["folder"]
        for p in (f / "outputs", f / "progress.md"):
            try:
                sig.append((str(p), p.stat().st_mtime))
            except OSError:
                sig.append((str(p), None))
        out = f / "outputs"
        if out.is_dir():
            for d in out.iterdir():
                if d.is_dir():
                    sig.append((d.name, d.stat().st_mtime))
    return tuple(sig)


_lock = threading.Lock()
_cache: dict = {}


def cached(con: sqlite3.Connection, max_age: float | None = None) -> Result:
    """API 용 — 원천 변경(signature) 또는 pipeline_tick_sec(300 초) 경과 때만 다시 판정하고 pipeline_cell 에 저장한다."""
    if max_age is None:
        max_age = float(settings.get().raw.get("collect", {}).get("pipeline_tick_sec", 300))
    sig = signature()
    with _lock:
        hit = _cache.get("res")
        if hit is not None and _cache.get("sig") == sig and _cache.get("dbpath") == _dbpath(con) \
                and time.time() - _cache.get("t", 0) < max_age:
            return hit
        res = refresh(con)
        con.commit()
        _cache.update(res=res, sig=sig, t=time.time(), dbpath=_dbpath(con))
        return res


def _dbpath(con: sqlite3.Connection) -> str:
    r = con.execute("PRAGMA database_list").fetchone()
    return r[2] if r else ""


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def main(argv: list[str] | None = None) -> int:
    """`uv run python -m agentdash.core.pipeline [--db …]` — 판정 + pipeline_cell 저장 + 요약 (원천은 읽기만)."""
    import argparse

    from agentdash.db import conn

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    con = conn.connect(conn.init_db(a.db))
    try:
        res = refresh(con)
        con.commit()
        d = res.as_dict()
        print(f"pipeline — 칸 {len(res.cells)} · " + " · ".join(f"{k} {v}" for k, v in d["counts"].items() if v)
              + f" · 미등록 회사 {d['unregistered']} {d['unregistered_names']} · UNKNOWN {d['unknown_cells']}")
        for st in res.stages:
            row = [c for c in res.cells if c.stage == st["code"]]
            cnt: dict[str, int] = {}
            for c in row:
                cnt[c.status] = cnt.get(c.status, 0) + 1
            print(f"  {st['code']} {st['label']}: " + " · ".join(f"{k} {v}" for k, v in sorted(cnt.items()))
                  + f" · ↻ {sum(1 for c in row if c.lag)}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
