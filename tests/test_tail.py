"""G-03 증분 읽기 — 추가분만 · 개행 없는 마지막 줄은 다음 회차 · inode 변경 / 크기 감소 시 처음부터 (spec.md §2.2).

파일은 tmp_path 에 테스트가 직접 쓴다 (Claude Code 역할). tail 은 읽기만 한다.
"""

import os

import pytest

from agentdash.collect import tail
from agentdash.db import conn


@pytest.fixture
def con(tmp_path):
    c = conn.connect(conn.init_db(tmp_path / "t.db"))
    yield c
    c.close()


def _append(p, data: bytes):
    with open(p, "ab") as fh:
        fh.write(data)


def _read(con, p):
    ch = tail.read_new(con, p)
    tail.commit(con, ch)
    return ch


def test_first_read_then_only_appended(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2}\n')
    ch = _read(con, p)
    assert ch.lines == [b'{"a":1}', b'{"a":2}'] and ch.line_numbers == [1, 2] and not ch.reset
    _append(p, b'{"a":3}\n')
    ch = _read(con, p)
    assert ch.lines == [b'{"a":3}'] and ch.line_numbers == [3]
    ch = _read(con, p)
    assert ch.lines == [] and ch.unchanged
    row = con.execute("SELECT inode, size, offset FROM src_file WHERE path=?", (str(p),)).fetchone()
    assert row[0] == os.stat(p).st_ino and row[1] == row[2] == p.stat().st_size


def test_half_line_waits_for_newline(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":')
    ch = _read(con, p)
    assert ch.lines == [b'{"a":1}']
    assert ch.end_offset == len(b'{"a":1}\n')
    _append(p, b'2}')
    assert _read(con, p).lines == []           # 아직 개행 없음
    _append(p, b"\n")
    ch = _read(con, p)
    assert ch.lines == [b'{"a":2}'] and ch.line_numbers == [2]


def test_only_half_line_reads_nothing(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1')
    ch = _read(con, p)
    assert ch.lines == [] and ch.end_offset == 0


def test_inode_change_rereads_from_start(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2}\n')
    _read(con, p)
    new = tmp_path / "s.new"
    new.write_bytes(b'{"b":1}\n{"b":2}\n{"b":3}\n')
    os.replace(new, p)                        # 같은 이름 · 다른 inode
    ch = _read(con, p)
    assert ch.reset and ch.start_offset == 0
    assert ch.lines == [b'{"b":1}', b'{"b":2}', b'{"b":3}'] and ch.line_numbers == [1, 2, 3]


def test_truncated_file_rereads_from_start(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2}\n{"a":3}\n')
    _read(con, p)
    with open(p, "r+b") as fh:                # 같은 inode, 크기 감소
        fh.truncate(0)
        fh.write(b'{"c":1}\n')
    ch = _read(con, p)
    assert ch.reset and ch.lines == [b'{"c":1}']


def test_no_commit_means_retry(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n')
    ch1 = tail.read_new(con, p)               # 처리 실패를 흉내 — commit 안 함
    ch2 = tail.read_new(con, p)
    assert ch1.lines == ch2.lines == [b'{"a":1}']


def test_line_numbers_survive_restart(con, tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_bytes(b'{"a":1}\n\n{"a":2}\n')      # 빈 줄도 번호를 먹는다
    _read(con, p)
    tail._line_cache.clear()                  # 프로세스 재시작 흉내
    _append(p, b'{"a":3}\n')
    ch = _read(con, p)
    assert ch.line_numbers == [4]


def test_whole_file_change_detection(con, tmp_path):
    p = tmp_path / "m.json"
    p.write_bytes(b'{"x":1}')
    assert tail.whole_changed(con, p)
    tail.mark_whole(con, p)
    assert not tail.whole_changed(con, p)
    p.write_bytes(b'{"x":22}')
    assert tail.whole_changed(con, p)


@pytest.mark.readonly_source
def test_tail_reads_readonly_source(fake_claude_home, con):
    """읽기 전용 가짜 원천에서도 읽힌다 (원천에 쓰지 않는다)."""
    files = sorted(fake_claude_home.rglob("*.jsonl"))
    assert files
    total = 0
    for f in files:
        ch = _read(con, f)
        total += len(ch.lines)
    assert total > 0
