"""파일 감시 (spec.md §2.2). 담당 개발1.

    run(stop_event, db_path=None, on_batch=None)   # 막는 호출 — 스레드로 돌린다

  · settings.claude_home 의 sessions/ · projects/ 를 재귀 감시(watchfiles, macOS FSEvents). 변경을 1 초 묶음으로 처리한다.
  · 감시 누락에 대비해 rescan_sec(60 초)마다 ingest_all 을 한 번 더 돈다.
  · 묶음마다 ingest.ingest_path → commit → post hook(linker · state) → on_batch(changed_keys).
원천은 읽기만 한다 (watchfiles 는 알림만 받는다).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from agentdash import settings
from agentdash.collect import ingest
from agentdash.db import conn


def process(con, paths: list[Path]) -> set[str]:
    changed: set[str] = set()
    order = sorted(paths, key=lambda p: ingest._ORDER.get(ingest.classify(p) or "", 9))
    for p in order:
        changed |= ingest.ingest_path(con, p)
    if changed:                     # 추세 · 예산은 usage_daily 를 읽는다 — 바뀐 키만 다시 (V-14)
        from agentdash.core import usage as U

        U.rebuild_daily(con, changed)
    for fn in list(ingest._post_hooks):
        fn(con, changed)
    con.commit()
    return changed


def run(stop_event: threading.Event, db_path: str | Path | None = None,
        on_batch: Callable[[set[str]], None] | None = None) -> None:
    from watchfiles import watch

    s = settings.get()
    cfg = s.raw.get("collect") or {}
    batch_ms = int(float(cfg.get("batch_sec", 1)) * 1000)
    rescan = float(cfg.get("rescan_sec", 60))
    con = conn.connect(conn.init_db(db_path))
    roots = [str(p) for p in (s.claude_home / "sessions", s.claude_home / "projects") if p.is_dir()]
    try:
        rep = ingest.ingest_all(con)
        con.commit()
        if on_batch and rep.changed:
            on_batch(rep.changed)
        last_scan = time.time()
        if not roots:
            while not stop_event.wait(rescan):
                rep = ingest.ingest_all(con)
                con.commit()
                if on_batch and rep.changed:
                    on_batch(rep.changed)
            return
        for changes in watch(*roots, stop_event=stop_event, debounce=batch_ms, step=100,
                             rust_timeout=int(rescan * 1000), yield_on_timeout=True):
            paths = [Path(p) for _, p in changes if ingest.classify(p) is not None]
            changed = process(con, paths) if paths else set()
            if time.time() - last_scan >= rescan:
                changed |= ingest.ingest_all(con).changed
                con.commit()
                last_scan = time.time()
            if on_batch and changed:
                on_batch(changed)
    finally:
        con.close()


def start(db_path: str | Path | None = None, on_batch=None) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    t = threading.Thread(target=run, args=(stop, db_path, on_batch), name="agentdash-watcher", daemon=True)
    t.start()
    return t, stop
