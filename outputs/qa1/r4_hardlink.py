#!/usr/bin/env python
"""QA1 r4 — G-25 · G-14 하드 링크 · 심볼릭 링크 재현 (가짜 루트만). 실제 ~/.claude 파일로는 링크를 만들지 않는다.

    uv run python outputs/qa1/r4_hardlink.py <빈 스크래치 폴더>

가짜 원천 = <스크래치>/casehome (AGENTDASH_CLAUDE_HOME) · <스크래치>/caseagents (AGENTDASH_AGENTS_ROOT).
링크는 저장소 data/qa1r4-* 에 만들고 끝에 전부 지운다. 출력은 경우 · 결과 · 원천 파일 변화(크기 · 해시 같음 여부)뿐.
"""
import hashlib, os, sqlite3, subprocess, sys
from pathlib import Path

S = Path(sys.argv[1]).resolve()
assert not S.exists() or not any(S.iterdir()), "빈 폴더여야 한다"
home, agents = S / "casehome", S / "caseagents"
(home / "projects" / "p").mkdir(parents=True)
agents.mkdir()
os.environ["AGENTDASH_CLAUDE_HOME"] = str(home)
os.environ["AGENTDASH_AGENTS_ROOT"] = str(agents)
REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
sys.path.insert(0, str(REPO / "src"))
from agentdash import settings  # noqa: E402
from agentdash.db import conn  # noqa: E402

assert settings.get().claude_home == home
made: list[Path] = []


def src_file(name: str, body: bytes = b'{"type":"user"}\n') -> Path:
    p = home / "projects" / "p" / name
    p.write_bytes(body)
    return p


def fp(p: Path):
    b = p.read_bytes()
    st = p.stat()
    return (len(b), hashlib.sha256(b).hexdigest(), st.st_mtime_ns)


def link(src: Path, name: str, sym=False) -> Path:
    d = DATA / name
    for x in (d, Path(str(d) + "-wal"), Path(str(d) + "-shm")):
        made.append(x)
    if sym:
        os.symlink(src, d)
    else:
        os.link(src, d)
    return d


def attempt(label, fn, src: Path | None):
    before = fp(src) if src else None
    try:
        fn()
        res = "허용(열림)"
    except RuntimeError as e:
        res = "거부 RuntimeError"
    except Exception as e:  # noqa: BLE001 — 결과 분류만
        res = f"예외 {type(e).__name__}"
    after = fp(src) if src else None
    ch = "" if src is None else (" · 원천 변화 없음" if before == after else f" · 원천 바뀜 (크기 {before[0]}→{after[0]})")
    nl = f" · nlink {src.stat().st_nlink}" if src else ""
    print(f"  {label:58s} {res}{ch}{nl}")
    return res


def write_some(p):
    c = conn.connect(p)
    c.execute("CREATE TABLE IF NOT EXISTS qa(x)")
    c.execute("INSERT INTO qa VALUES (1)")
    c.commit()
    c.close()


try:
    print("## DB 파일 자체가 원천 파일의 하드 링크")
    s1 = src_file("h1.jsonl")
    d1 = link(s1, "qa1r4-hl1.db")
    attempt("init_db(data/qa1r4-hl1.db)", lambda: conn.init_db(d1), s1)
    attempt("connect(data/qa1r4-hl1.db)", lambda: conn.connect(d1).close(), s1)
    env = dict(os.environ, AGENTDASH_DB=str(d1))
    before = fp(s1)
    r = subprocess.run(["uv", "run", "python", "-m", "agentdash.db.conn"], cwd=REPO, env=env, capture_output=True, text=True)
    print(f"  {'CLI make setup 경로 (-m agentdash.db.conn, AGENTDASH_DB)':58s} exit {r.returncode} · "
          f"{'RuntimeError' if 'RuntimeError' in r.stderr else '거부 문구 없음'} · 원천 {'변화 없음' if fp(s1) == before else '바뀜'}")
    r = subprocess.run(["uv", "run", "python", "-m", "agentdash.collect.backfill"], cwd=REPO, env=env, capture_output=True, text=True)
    print(f"  {'CLI 백필 경로 (-m agentdash.collect.backfill)':58s} exit {r.returncode} · "
          f"{'RuntimeError' if 'RuntimeError' in r.stderr else '거부 문구 없음'} · 원천 {'변화 없음' if fp(s1) == before else '바뀜'}")

    print("## 원천 sqlite 파일(유효한 DB)의 하드 링크")
    s2 = home / "projects" / "p" / "real.sqlite"
    c = sqlite3.connect(s2); c.execute("CREATE TABLE t(x)"); c.commit(); c.close()
    d2 = link(s2, "qa1r4-hl2.db")
    attempt("init_db(data/qa1r4-hl2.db) — 유효 sqlite", lambda: conn.init_db(d2), s2)

    print("## 저장소 안 두 파일끼리 하드 링크 (원천 아님, spec 글자 st_nlink > 1)")
    n1 = DATA / "qa1r4-plain.db"; made.append(n1); n1.write_bytes(b"")
    d3 = link(n1, "qa1r4-hl3.db")
    attempt("init_db(data/qa1r4-hl3.db)", lambda: conn.init_db(d3), None)

    print("## 심볼릭 링크 파일 → 원천 파일")
    s4 = src_file("s4.jsonl")
    d4 = link(s4, "qa1r4-sym.db", sym=True)
    attempt("init_db(data/qa1r4-sym.db → casehome/…/s4.jsonl)", lambda: conn.init_db(d4), s4)
    attempt("connect(data/qa1r4-sym.db)", lambda: conn.connect(d4).close(), s4)

    print("## 곁 파일(-wal · -shm)이 원천 파일의 하드 링크 — DB 본 파일은 정상")
    for suf in ("-wal", "-shm"):
        base = DATA / f"qa1r4-side{suf.strip('-')}.db"
        made += [base, Path(str(base) + "-wal"), Path(str(base) + "-shm")]
        conn.init_db(base)           # 정상 생성 (닫히면 -wal 은 지워진다)
        for x in (Path(str(base) + "-wal"), Path(str(base) + "-shm")):
            if x.exists():
                x.unlink()
        s5 = src_file(f"side{suf}.jsonl", b'{"type":"user","x":"' + b"a" * 200 + b'"}\n')
        os.link(s5, str(base) + suf)
        attempt(f"connect+쓰기(data/{base.name}) · {suf} = 원천 하드 링크", lambda: write_some(base), s5)

    print("## 정상 (거부되면 안 됨)")
    ok = DATA / "qa1r4-ok.db"; made += [ok, Path(str(ok) + "-wal"), Path(str(ok) + "-shm")]
    attempt("init_db(data/qa1r4-ok.db) 새 파일", lambda: conn.init_db(ok), None)
    attempt("connect(data/qa1r4-ok.db) 다시", lambda: conn.connect(ok).close(), None)
finally:
    for x in made:
        if x.is_symlink() or x.exists():
            x.unlink()
    left = sorted(p.name for p in DATA.glob("qa1r4-*"))
    print(f"정리: data/qa1r4-* 남은 것 {len(left)}")
