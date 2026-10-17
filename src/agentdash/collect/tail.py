"""증분 읽기 (spec.md §2.2, G-03). 담당 개발1.

파일마다 `src_file(path, inode, size, offset, mtime)` 를 둔다.
  · 다음 읽기는 offset 부터. 마지막 줄이 개행으로 끝나지 않으면 그 줄은 남겨 두고 다음 회차에 읽는다.
  · inode 가 바뀌었거나 size < offset 이면 처음부터 다시 읽는다 (Chunk.reset = True).
  · read_new() 는 DB 를 바꾸지 않는다. 처리에 성공한 뒤 commit() 이 offset 을 옮긴다 (실패하면 다음 회차 재시도).
원천은 읽기 모드('rb')로만 연다.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

_BLOCK = 1 << 20

# 줄 번호 캐시: path -> (offset, 그 offset 까지의 줄 수). 프로세스 안에서만 — 없으면 앞부분 개행을 다시 센다.
_line_cache: dict[str, tuple[int, int]] = {}


@dataclass
class Chunk:
    path: str
    inode: int
    size: int
    mtime: float
    start_offset: int
    end_offset: int
    start_line: int                      # lines[0] 의 줄 번호 (1 부터)
    lines: list[bytes] = field(default_factory=list)   # 개행 뺀 줄 (빈 줄 포함하지 않음 — 번호는 line_numbers)
    line_numbers: list[int] = field(default_factory=list)
    reset: bool = False
    newlines: int = 0                    # 읽은 구간의 개행 수 (빈 줄 포함)

    @property
    def unchanged(self) -> bool:
        return self.start_offset == self.end_offset and not self.reset


def state(con: sqlite3.Connection, path: str | Path) -> tuple[int, int, int, float] | None:
    r = con.execute("SELECT inode, size, offset, mtime FROM src_file WHERE path=?", (str(path),)).fetchone()
    return None if r is None else (r[0], r[1], r[2], r[3])


def _count_lines(path: str, upto: int) -> int:
    n, done = 0, 0
    with open(path, "rb") as fh:
        while done < upto:
            buf = fh.read(min(_BLOCK, upto - done))
            if not buf:
                break
            n += buf.count(b"\n")
            done += len(buf)
    return n


def read_new(con: sqlite3.Connection, path: str | Path) -> Chunk:
    p = str(path)
    st = os.stat(p)
    prev = state(con, p)
    offset, reset = 0, False
    if prev is not None:
        p_inode, _p_size, p_off, _p_mtime = prev
        if p_inode != st.st_ino or st.st_size < p_off:
            reset = True
        else:
            offset = p_off
    if offset == st.st_size:
        return Chunk(p, st.st_ino, st.st_size, st.st_mtime, offset, offset, 0, reset=reset)
    with open(p, "rb") as fh:
        fh.seek(offset)
        data = fh.read(st.st_size - offset)
    cut = data.rfind(b"\n")
    if cut < 0:                      # 개행 없는 반쪽 줄만 있음 → 다음 회차
        return Chunk(p, st.st_ino, st.st_size, st.st_mtime, offset, offset, 0, reset=reset)
    body = data[: cut + 1]
    end = offset + len(body)
    cached = _line_cache.get(p)
    if offset == 0:
        base = 0
    elif cached and cached[0] == offset and not reset:
        base = cached[1]
    else:
        base = _count_lines(p, offset)
    lines, nums = [], []
    for i, raw in enumerate(body.split(b"\n")[:-1]):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if raw.strip():
            lines.append(raw)
            nums.append(base + i + 1)
    return Chunk(p, st.st_ino, st.st_size, st.st_mtime, offset, end, base + 1, lines, nums, reset, body.count(b"\n"))


def commit(con: sqlite3.Connection, chunk: Chunk) -> None:
    con.execute(
        "INSERT INTO src_file (path, inode, size, offset, mtime) VALUES (?,?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET inode=excluded.inode, size=excluded.size, offset=excluded.offset, mtime=excluded.mtime",
        (chunk.path, chunk.inode, chunk.size, chunk.end_offset, chunk.mtime))
    if chunk.end_offset > chunk.start_offset:
        _line_cache[chunk.path] = (chunk.end_offset, chunk.start_line - 1 + chunk.newlines)


def mark_whole(con: sqlite3.Connection, path: str | Path) -> None:
    """JSON 한 덩어리 파일(S1 · S4 · S6)을 다 읽었다고 기록한다 — 다음에 size · mtime 이 같으면 건너뛴다."""
    st = os.stat(str(path))
    con.execute(
        "INSERT INTO src_file (path, inode, size, offset, mtime) VALUES (?,?,?,?,?) "
        "ON CONFLICT(path) DO UPDATE SET inode=excluded.inode, size=excluded.size, offset=excluded.offset, mtime=excluded.mtime",
        (str(path), st.st_ino, st.st_size, st.st_size, st.st_mtime))


def whole_changed(con: sqlite3.Connection, path: str | Path) -> bool:
    st = os.stat(str(path))
    prev = state(con, path)
    return prev is None or prev[0] != st.st_ino or prev[1] != st.st_size or prev[3] != st.st_mtime
