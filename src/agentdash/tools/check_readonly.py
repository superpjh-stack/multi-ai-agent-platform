#!/usr/bin/env python
"""V-05 check_readonly — 원천 무접촉 (G-14).

    uv run python src/agentdash/tools/check_readonly.py            # 정적 스캔 + 읽기 전용 가짜 루트 pytest
    uv run python src/agentdash/tools/check_readonly.py --static   # 정적 스캔만
    uv run python src/agentdash/tools/check_readonly.py --runtime  # 읽기 전용 가짜 루트 pytest 만
    uv run python src/agentdash/tools/check_readonly.py --db-seed  # AGENTDASH_DB 씨앗 (정적 + 진입점 런타임) 만
    uv run python src/agentdash/tools/check_readonly.py --scan 파일…  # 지정 파일만 정적 스캔 (테스트용)

정적 스캔 (src/agentdash/** · scripts/*.py)
  · 원천 경로 값(taint)을 추적한다. 씨앗 = `.claude_home` · `.agents_root` · `.source_roots` 속성,
    이름이 claude_home / agents_root / source_root(s) / src_root 인 변수 · 인자, `Path.home()`, `expanduser("~…")`,
    `os.environ[...]` 의 AGENTDASH_CLAUDE_HOME · AGENTDASH_AGENTS_ROOT.
    전파 = 대입 · for · with · 컴프리헨션 · `a / b`(왼쪽) · 경로 메서드(joinpath · glob · rglob · iterdir · resolve · parent …)
    · `Path(x)` · `os.path.join(x, …)` · f-string 첫 값 · sorted/list/max/min/next · 원천 경로를 돌려주는 함수.
  · 쓰기 = open(…, 'w'/'a'/'x'/'+') · `.open('w')` · write_text · write_bytes · unlink · rename · replace · rmdir · mkdir ·
    touch · chmod · symlink_to · hardlink_to · os.{remove,unlink,rename,replace,rmdir,removedirs,makedirs,mkdir,chmod,chown,
    utime,truncate,symlink,link,open} · shutil.{rmtree,move,copy*,copytree}(대상) · sqlite3.connect(원천, mode=ro 아님).
  · 원천 경로 하드코딩 = 코드 안 문자열 상수가 `~/` · `/Users/` · `/home/` 로 시작하거나 `/.claude` 를 품는다 (docstring 제외).
런타임
  · tests/fixtures 를 임시 폴더로 복사해 `chmod -R a-w` 한 가짜 루트를 AGENTDASH_CLAUDE_HOME · AGENTDASH_AGENTS_ROOT 로 주고
    AGENTDASH_TEST_READONLY=1 로 pytest 전체를 돌린다. 통과 + 실행 전후 트리(경로 · 크기 · mtime · sha256) 동일이어야 PASS.
AGENTDASH_DB 씨앗 (웨이브 D — DEF-QA1-003 · 008 을 이 도구가 못 보던 길)
  · DB 경로(`AGENTDASH_DB` · `.db_path`)도 원천이 될 수 있는 값으로 본다.
    정적: DB 경로 값에 쓰는 호출(mkdir · makedirs · touch · write_* · open(w) · sqlite3.connect(mode=ro 아님))은
    같은 함수 안에서 **그보다 앞줄에** 원천 거부(`_refuse_source` · `refuse_source` · `is_source_path`)가 있어야 한다.
    런타임: 쓰기 가능한 가짜 루트(home · agents)를 만들고, 그 아래 DB 경로를 AGENTDASH_DB 로 준 채 DB 를 여는 진입점
    (db.conn · backfill · pricing-check · reprice · export · pipeline · 서버 lifespan) 을 하나씩 돌린다.
    전부 「원천 루트 아래」 로 거부(종료코드 ≠ 0)해야 하고, 실행 전후 가짜 루트 트리가 같아야(폴더 · 파일 0 생성) PASS.
    + 가짜 루트를 설정한 채로도 실제 홈의 .claude 와 기본 agents_root 아래가 원천으로 판정되는지 (비교만, 열지 않음).
출력: `G-14  원천 무접촉 (정적)  PASS|FAIL  …` · `G-14  원천 무접촉 (읽기 전용 pytest)  PASS|FAIL  …`
      · `G-14  원천 무접촉 (DB 경로 씨앗)  PASS|FAIL  …`
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCAN_DIRS = [ROOT / "src" / "agentdash", ROOT / "scripts"]
FIXTURES = ROOT / "tests" / "fixtures"
READONLY_ENV = "AGENTDASH_TEST_READONLY"

SEED_NAME = re.compile(r"^(claude_home|agents_root|source_roots?|src_root|CLAUDE_HOME|AGENTS_ROOT)$")
SEED_ATTR = {"claude_home", "agents_root", "source_roots"}
SEED_ENV = {"AGENTDASH_CLAUDE_HOME", "AGENTDASH_AGENTS_ROOT"}
PATH_METHODS = {"joinpath", "glob", "rglob", "iterdir", "resolve", "absolute", "expanduser", "with_name", "with_suffix",
                "with_stem", "readlink", "walk"}
PATH_ATTRS = {"parent", "parents"}
PASS_FUNCS = {"Path", "PurePath", "PosixPath", "sorted", "list", "tuple", "max", "min", "next", "reversed", "iter",
              "set", "str", "fspath", "realpath", "abspath", "normpath", "expanduser", "join", "dirname"}
WRITE_METHODS = {"write_text", "write_bytes", "unlink", "rename", "replace", "rmdir", "mkdir", "touch", "chmod",
                 "lchmod", "symlink_to", "hardlink_to", "link_to"}
OS_WRITES = {"remove", "unlink", "rename", "replace", "rmdir", "removedirs", "makedirs", "mkdir", "chmod", "chown",
             "lchown", "utime", "truncate", "symlink", "link", "open", "mkfifo"}
SHUTIL_ANY = {"rmtree", "move"}                     # 원천이 어느 인자든 위반
SHUTIL_DST = {"copy", "copy2", "copyfile", "copytree", "copymode", "copystat"}   # 대상(두 번째) 인자
HARDCODE = re.compile(r"^(~/|/Users/|/home/)|/\.claude(/|$)")


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


class Taint:
    def __init__(self, tree: ast.Module, seed_name: re.Pattern = SEED_NAME, seed_attr: set[str] = SEED_ATTR,
                 seed_env: set[str] = SEED_ENV, home_seeds: bool = True):
        self.tree = tree
        self.names: set[str] = set()
        self.funcs: set[str] = set()      # 원천 경로를 돌려주는 함수
        self.seed_name, self.seed_attr, self.seed_env, self.home_seeds = seed_name, seed_attr, seed_env, home_seeds

    def tainted(self, e: ast.AST | None) -> bool:
        if e is None:
            return False
        if isinstance(e, ast.Name):
            return e.id in self.names or bool(self.seed_name.match(e.id))
        if isinstance(e, ast.Attribute):
            if e.attr in self.seed_attr:
                return True
            if e.attr in PATH_ATTRS:
                return self.tainted(e.value)
            return False
        if isinstance(e, ast.Subscript):
            sl = e.slice
            if isinstance(sl, ast.Constant) and sl.value in self.seed_env and _dotted(e.value).endswith("environ"):
                return True
            return self.tainted(e.value)
        if isinstance(e, ast.BinOp):
            return self.tainted(e.left)
        if isinstance(e, ast.JoinedStr):
            first = e.values[0] if e.values else None
            return isinstance(first, ast.FormattedValue) and self.tainted(first.value)
        if isinstance(e, (ast.IfExp,)):
            return self.tainted(e.body) or self.tainted(e.orelse)
        if isinstance(e, ast.BoolOp):
            return any(self.tainted(v) for v in e.values)
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            return any(self.tainted(v) for v in e.elts)
        if isinstance(e, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            return self.tainted(e.elt) or any(self.tainted(g.iter) for g in e.generators)
        if isinstance(e, ast.Starred):
            return self.tainted(e.value)
        if isinstance(e, ast.Await):
            return self.tainted(e.value)
        if isinstance(e, ast.Call):
            f = e.func
            d = _dotted(f)
            if self.home_seeds and d.endswith("home") and d.split(".")[-1] == "home" and "Path" in d:     # Path.home()
                return True
            if self.home_seeds and d.endswith("expanduser") and e.args and isinstance(e.args[0], ast.Constant) \
                    and str(e.args[0].value).startswith("~"):
                return True
            if d.endswith("environ.get") or d.endswith("getenv"):
                return bool(e.args) and isinstance(e.args[0], ast.Constant) and e.args[0].value in self.seed_env
            if isinstance(f, ast.Attribute) and f.attr in PATH_METHODS:
                return self.tainted(f.value) or (f.attr in {"join"} and bool(e.args) and self.tainted(e.args[0]))
            last = d.split(".")[-1] if d else ""
            if last in PASS_FUNCS:
                return bool(e.args) and self.tainted(e.args[0])
            if isinstance(f, ast.Name) and f.id in self.funcs:
                return True
            if isinstance(f, ast.Attribute) and f.attr in self.funcs:
                return True
            return False
        return False

    def _mark(self, target: ast.AST) -> bool:
        changed = False
        if isinstance(target, ast.Name):
            if target.id not in self.names:
                self.names.add(target.id)
                changed = True
        elif isinstance(target, (ast.Tuple, ast.List)):
            for t in target.elts:
                changed |= self._mark(t)
        elif isinstance(target, ast.Starred):
            changed |= self._mark(target.value)
        return changed

    def solve(self) -> None:
        for _ in range(20):
            changed = False
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Assign) and self.tainted(node.value):
                    for t in node.targets:
                        changed |= self._mark(t)
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None \
                        and self.tainted(node.value):
                    changed |= self._mark(node.target)
                elif isinstance(node, (ast.For, ast.AsyncFor)) and self.tainted(node.iter):
                    changed |= self._mark(node.target)
                elif isinstance(node, ast.comprehension) and self.tainted(node.iter):
                    changed |= self._mark(node.target)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for it in node.items:
                        if it.optional_vars is not None and self.tainted(it.context_expr):
                            changed |= self._mark(it.optional_vars)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for a in node.args.args + node.args.kwonlyargs:
                        if self.seed_name.match(a.arg) and a.arg not in self.names:
                            self.names.add(a.arg)
                            changed = True
                    if node.name not in self.funcs:
                        for r in ast.walk(node):
                            if isinstance(r, ast.Return) and self.tainted(r.value):
                                self.funcs.add(node.name)
                                changed = True
                                break
            if not changed:
                return


def _mode_of(call: ast.Call, pos: int) -> str | None:
    if len(call.args) > pos:
        m = call.args[pos]
        return m.value if isinstance(m, ast.Constant) and isinstance(m.value, str) else "?"
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) else "?"
    return None


def _writes(mode: str | None) -> bool:
    if mode is None:
        return False
    return mode == "?" or any(c in mode for c in "wax+")


def scan_file(path: Path) -> tuple[list[str], int]:
    """→ (위반 목록, 쓰기 호출 총수)."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    tn = Taint(tree)
    tn.solve()
    bad: list[str] = []
    writes = 0
    rel = path.relative_to(ROOT) if ROOT in path.parents else path
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            if HARDCODE.search(node.value):
                bad.append(f"{rel}:{node.lineno}: 원천 경로 하드코딩 {node.value[:60]!r}")
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        d = _dotted(f)
        last = d.split(".")[-1] if d else ""
        hit = None
        if isinstance(f, ast.Name) and f.id == "open":
            if _writes(_mode_of(node, 1)):
                writes += 1
                if node.args and tn.tainted(node.args[0]):
                    hit = f"open(…, {_mode_of(node, 1)!r})"
        elif isinstance(f, ast.Attribute) and f.attr == "open" and not d.startswith("os."):
            if _writes(_mode_of(node, 0)):
                writes += 1
                if tn.tainted(f.value):
                    hit = f".open({_mode_of(node, 0)!r})"
        elif isinstance(f, ast.Attribute) and f.attr in WRITE_METHODS and not d.startswith(("os.", "shutil.")):
            writes += 1
            if tn.tainted(f.value):
                hit = f".{f.attr}()"
        elif d.startswith("os.") and last in OS_WRITES and d.count(".") == 1:
            writes += 1
            if last == "open":
                flags = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
                if node.args and tn.tainted(node.args[0]) and flags.strip() not in ("os.O_RDONLY", "O_RDONLY"):
                    hit = f"os.open(…, {flags})"
            elif any(tn.tainted(a) for a in node.args[:2]):
                hit = f"{d}()"
        elif d.startswith("shutil.") and (last in SHUTIL_ANY or last in SHUTIL_DST):
            writes += 1
            if last in SHUTIL_ANY and any(tn.tainted(a) for a in node.args[:2]):
                hit = f"{d}()"
            elif last in SHUTIL_DST and len(node.args) > 1 and tn.tainted(node.args[1]):
                hit = f"{d}(대상=원천)"
        elif d.endswith("sqlite3.connect"):
            writes += 1
            if node.args and tn.tainted(node.args[0]):
                arg = ast.unparse(node.args[0])
                if "mode=ro" not in arg:
                    hit = "sqlite3.connect(원천)"
        if hit:
            bad.append(f"{rel}:{node.lineno}: 원천 경로에 쓰기 {hit}")
    return bad, writes


def static(files: list[Path] | None = None) -> tuple[bool, str, list[str]]:
    if files is None:
        files = sorted(p for d in SCAN_DIRS if d.exists() for p in d.rglob("*.py"))
    bad: list[str] = []
    writes = 0
    for f in files:
        b, w = scan_file(f)
        bad += b
        writes += w
    detail = f"파일 {len(files)} · 쓰기 호출 {writes} 곳 · 원천 경로 대상 {len(bad)}"
    return not bad, detail, bad


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        elif p.is_dir():
            out[str(p.relative_to(root)) + "/"] = (0, 0, "dir")
    return out


def _chmod_tree(root: Path, writable: bool) -> None:
    paths = [root, *root.rglob("*")]       # 열 때는 위에서 아래로(안을 고칠 수 있게)
    if not writable:
        paths = list(reversed(paths))      # 닫을 때는 안부터
    for p in paths:
        mode = p.stat().st_mode
        if writable:
            os.chmod(p, mode | stat.S_IWUSR)
        else:
            os.chmod(p, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def runtime(pytest_args: list[str] | None = None) -> tuple[bool, str, list[str]]:
    if not any(FIXTURES.glob("*/")):
        return False, "tests/fixtures 없음 — make fixtures", []
    tmp = Path(tempfile.mkdtemp(prefix="agentdash-ro-"))
    fake_home, fake_agents, dbdir = tmp / "claude_home", tmp / "agents_root", tmp / "db"
    fake_home.mkdir()
    fake_agents.mkdir()
    dbdir.mkdir()
    for ver in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        shutil.copytree(ver, fake_home, dirs_exist_ok=True, ignore=shutil.ignore_patterns("README.md"))
    before = {**{f"H/{k}": v for k, v in _snapshot(fake_home).items()},
              **{f"A/{k}": v for k, v in _snapshot(fake_agents).items()}}
    _chmod_tree(fake_home, writable=False)
    _chmod_tree(fake_agents, writable=False)
    env = dict(os.environ)
    env.update({"AGENTDASH_CLAUDE_HOME": str(fake_home), "AGENTDASH_AGENTS_ROOT": str(fake_agents),
                "AGENTDASH_DB": str(dbdir / "ro.db"), "AGENTDASH_TEST_READONLY": "1"})
    t0 = time.time()
    try:
        p = subprocess.run(["uv", "run", "pytest", "-q", "-x", *(pytest_args or [])], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=900)
        out = (p.stdout or "") + (p.stderr or "")
        code = p.returncode
    finally:
        _chmod_tree(fake_home, writable=True)
        _chmod_tree(fake_agents, writable=True)
    after = {**{f"H/{k}": v for k, v in _snapshot(fake_home).items()},
             **{f"A/{k}": v for k, v in _snapshot(fake_agents).items()}}
    shutil.rmtree(tmp, ignore_errors=True)
    changed = sorted(set(before) ^ set(after) | {k for k in before if k in after and before[k] != after[k]})
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    tail = lines[-1][:120] if lines else ""
    bad = [f"가짜 루트 변경: {c}" for c in changed[:20]]
    if code != 0:
        bad.append(f"pytest 종료코드 {code}: {tail}")
        for ln in lines:
            if "Permission" in ln or "Read-only" in ln:
                bad.append(ln[:200])
                break
    detail = (f"읽기 전용 가짜 루트(파일 {sum(1 for k in before if not k.endswith('/'))}) · pytest {tail} · "
              f"트리 변경 {len(changed)} · {time.time() - t0:.1f}s")
    return code == 0 and not changed, detail, bad


# ── AGENTDASH_DB 씨앗 (DEF-QA1-003 · 008) ──────────────────────────────
DB_SEED_NAME = re.compile(r"^db_path$")
DB_SEED_ATTR = {"db_path"}
DB_SEED_ENV = {"AGENTDASH_DB"}
GUARD_CALLS = {"_refuse_source", "refuse_source", "is_source_path"}
REFUSE_MARK = "원천 루트 아래"          # db/conn.py _refuse_source 의 거부 문구


def scan_db_seed(path: Path) -> list[str]:
    """DB 경로 값에 쓰는 호출이 같은 함수 안 앞줄의 원천 거부 없이 나오면 위반."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tn = Taint(tree, DB_SEED_NAME, DB_SEED_ATTR, DB_SEED_ENV, home_seeds=False)
    tn.solve()
    rel = path.relative_to(ROOT) if ROOT in path.parents else path
    bad: list[str] = []
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in funcs:
        guards = [c.lineno for c in ast.walk(fn) if isinstance(c, ast.Call)
                  and _dotted(c.func).split(".")[-1] in GUARD_CALLS]
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f, d = node.func, _dotted(node.func)
            last = d.split(".")[-1] if d else ""
            hit = None
            if isinstance(f, ast.Attribute) and f.attr in {"mkdir", "touch", "write_text", "write_bytes"} \
                    and not d.startswith(("os.", "shutil.")) and tn.tainted(f.value):
                hit = f".{f.attr}()"
            elif isinstance(f, ast.Name) and f.id == "open" and _writes(_mode_of(node, 1)) and node.args \
                    and tn.tainted(node.args[0]):
                hit = "open(w)"
            elif d.startswith("os.") and last in {"makedirs", "mkdir"} and node.args and tn.tainted(node.args[0]):
                hit = f"{d}()"
            elif d.endswith("sqlite3.connect") and node.args and tn.tainted(node.args[0]) \
                    and "mode=ro" not in ast.unparse(node.args[0]):
                hit = "sqlite3.connect()"
            if hit and not any(g < node.lineno for g in guards):
                bad.append(f"{rel}:{node.lineno}: DB 경로에 원천 거부 없이 쓰기 {hit} (함수 {fn.name})")
    return bad


#: (이름, 명령) — "python" 은 지금 인터프리터로 바꾼다. 전부 DB 를 conn.init_db / connect 로 연다.
DB_ENTRIES: list[tuple[str, list[str]]] = [
    ("db.conn", ["python", "-m", "agentdash.db.conn"]),
    ("backfill", ["python", "-m", "agentdash.collect.backfill"]),
    ("pricing-check", ["python", "-m", "agentdash.core.usage", "pricing-check"]),
    ("reprice", ["python", "-m", "agentdash.core.usage", "reprice"]),
    ("export", ["python", "-m", "agentdash.core.usage", "export"]),
    ("pipeline", ["python", "-m", "agentdash.core.pipeline"]),
    ("lifespan", ["python", "-c", "import asyncio\nfrom agentdash.app.main import app, lifespan\n"
                  "async def m():\n    async with lifespan(app):\n        pass\nasyncio.run(m())"]),
]


def _real_guard_probe(fake_home: Path, fake_agents: Path) -> list[str]:
    """가짜 루트를 설정한 채 실제 기본 루트 아래가 원천으로 판정되는지 (DEF-QA1-008). 비교만 — 경로를 열지 않는다."""
    sys.path.insert(0, str(ROOT / "src"))
    from agentdash import settings as _s

    keep = {k: os.environ.get(k) for k in ("AGENTDASH_CLAUDE_HOME", "AGENTDASH_AGENTS_ROOT")}
    os.environ["AGENTDASH_CLAUDE_HOME"], os.environ["AGENTDASH_AGENTS_ROOT"] = str(fake_home), str(fake_agents)
    try:
        st = _s.get()
        default_agents = Path(str(_s.load_yaml("settings.yaml")["sources"]["agents_root"])).expanduser()
        probes = {"실제 홈 .claude": Path.home() / ".claude" / "agentdash-probe" / "x.db",
                  "기본 agents_root": default_agents / "agentdash-probe" / "x.db",
                  # 대소문자 · NFD 변형 (DEF-QA1-101) — 판정만, 열지 않는다
                  "실제 홈 .CLAUDE": Path.home() / ".CLAUDE" / "agentdash-probe" / "x.db",
                  "기본 agents_root 소문자": Path(str(default_agents).lower()) / "agentdash-probe" / "x.db",
                  "기본 agents_root NFD": Path(unicodedata.normalize("NFD", str(default_agents))) / "agentdash-probe"}
        bad = [f"원천 판정 빠짐: {k} (설정 루트가 가짜일 때)" for k, v in probes.items() if not st.is_source_path(v)]
        if st.is_source_path(ROOT / "data" / "x.db"):
            bad.append("저장소 data/ 가 원천으로 판정됨")
        return bad
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def db_seed_runtime(entries: list[tuple[str, list[str]]] | None = None) -> tuple[bool, str, list[str]]:
    entries = DB_ENTRIES if entries is None else entries
    tmp = Path(tempfile.mkdtemp(prefix="agentdash-dbseed-"))
    # agents 루트 이름에 한글(NFC 로 만든다) — NFD 변형 경로가 문자열로는 달라지게 (DEF-QA1-101)
    fake_home, fake_agents = tmp / "claude_home", tmp / unicodedata.normalize("NFC", "agents_root_에이전트")
    (fake_home / "projects").mkdir(parents=True)
    (fake_agents / "Other Project").mkdir(parents=True)
    nfd_agents = Path(unicodedata.normalize("NFD", str(fake_agents)))
    targets = {"home/newdir": fake_home / "newdir" / "deep" / "x.db",
               "home": fake_home / "x.db",
               "agents/Other Project": fake_agents / "Other Project" / "sub" / "x.db",
               # 대소문자 · 유니코드 정규화 변형 (APFS 는 같은 폴더로 연다 — 문자열 비교면 통과해 버린다)
               "HOME 대문자/newdir": tmp / "CLAUDE_HOME" / "newdir" / "x.db",
               "Home 대소문자/projects": tmp / "Claude_Home" / "projects" / "y.db",
               "agents NFD/Other Project": nfd_agents / "Other Project" / "sub" / "x.db",
               "agents NFD+대문자/other project": tmp / unicodedata.normalize("NFD", "AGENTS_ROOT_에이전트") / "other project" / "x.db"}
    before = _snapshot(tmp)
    bad: list[str] = []
    t0 = time.time()
    runs = 0
    try:
        for name, cmd in entries:
            cmd = [sys.executable if c == "python" else c for c in cmd]
            for tname, target in targets.items():
                env = dict(os.environ)
                env.update({"AGENTDASH_CLAUDE_HOME": str(fake_home), "AGENTDASH_AGENTS_ROOT": str(fake_agents),
                            "AGENTDASH_DB": str(target), "AGENTDASH_NO_WATCH": "1",
                            "PYTHONPATH": str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")})
                env.pop(READONLY_ENV, None)
                try:
                    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                    code, out = p.returncode, (p.stdout or "") + (p.stderr or "")
                except subprocess.TimeoutExpired:
                    code, out = 124, "timeout"
                runs += 1
                if code == 0 or REFUSE_MARK not in out:
                    bad.append(f"{name} → {tname}: 거부 안 함 (종료코드 {code})")
                after = _snapshot(tmp)
                new = sorted(set(after) - set(before))
                if new:
                    bad.append(f"{name} → {tname}: 거부 전 생김 {', '.join(new[:3])}")
                    before = after
        bad += _real_guard_probe(fake_home, fake_agents)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    detail = (f"진입점 {len(entries)} × 원천 아래 DB 경로 {len(targets)} = {runs} 회 · 거부 "
              f"{runs - sum(1 for b in bad if '거부 안 함' in b)} · 생긴 항목 {sum(1 for b in bad if '생김' in b)} · "
              f"실제 루트 판정 {'OK' if not any('원천 판정' in b or 'data/' in b for b in bad) else 'FAIL'} · "
              f"{time.time() - t0:.1f}s")
    return not bad, detail, bad


def db_seed(entries=None) -> tuple[bool, str, list[str]]:
    files = sorted(p for d in SCAN_DIRS if d.exists() for p in d.rglob("*.py"))
    sbad = [b for f in files for b in scan_db_seed(f)]
    ok, detail, rbad = db_seed_runtime(entries)
    return ok and not sbad, f"정적 위반 {len(sbad)} · {detail}", sbad + rbad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--runtime", action="store_true")
    ap.add_argument("--db-seed", action="store_true")
    ap.add_argument("--scan", nargs="+")
    a = ap.parse_args()
    rc = 0
    if a.scan:
        ok, detail, bad = static([Path(x).resolve() for x in a.scan])
        for b in bad:
            print("  위반", b)
        print(f"G-14  원천 무접촉 (정적)  {'PASS' if ok else 'FAIL'}  {detail}")
        return 0 if ok else 1
    only = a.static or a.runtime or a.db_seed
    do_static = a.static or not only
    do_runtime = a.runtime or not only
    do_db = a.db_seed or not only
    if do_static:
        ok, detail, bad = static()
        for b in bad[:30]:
            print("  위반", b)
        print(f"G-14  원천 무접촉 (정적)  {'PASS' if ok else 'FAIL'}  {detail}")
        rc |= 0 if ok else 1
    if do_runtime:
        ok, detail, bad = runtime()
        for b in bad[:30]:
            print("  위반", b)
        print(f"G-14  원천 무접촉 (읽기 전용 pytest)  {'PASS' if ok else 'FAIL'}  {detail}")
        rc |= 0 if ok else 1
    if do_db:
        ok, detail, bad = db_seed()
        for b in bad[:30]:
            print("  위반", b)
        print(f"G-14  원천 무접촉 (DB 경로 씨앗)  {'PASS' if ok else 'FAIL'}  {detail}")
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
