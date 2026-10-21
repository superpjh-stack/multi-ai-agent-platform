"""G-24 추정 열 (spec.md v0.3 §6.2 · V-12) — 요청별 길이 → `usage_event.output_est` · `cost_est_usd`.

  · 의심 = 요청(같은 기록 · 같은 requestId) 기록 output 최대 < 30 이고 content 블록 json.dumps 길이 합 > 400.
  · output_est = ceil((text 글자 수 + tool_use 입력 json.dumps(ensure_ascii=False) 글자 수) / 4), thinking 제외, 하한 = 기록.
  · 길이는 재고 버린다 — DB 열은 spec §3 블록 그대로, 본문 · 길이 숫자를 저장하지 않는다.
원천 흉내는 tmp 의 가짜 루트로만 (Claude Code 역할).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from agentdash.collect import ingest
from agentdash.collect.parsers import transcript as tr_p
from agentdash.core import usage as U
from agentdash.db import conn

PK = "-tmp-est"
SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
USAGE_COLS = ["agent_key", "request_id", "at", "model", "speed", "input_tokens", "cache_read", "cache_write_5m",
              "cache_write_1h", "output_tokens", "thinking_tokens", "web_search", "web_fetch", "cost_usd", "pricing_ver",
              "output_est", "cost_est_usd"]


def _line(uuid, rid, ts, out, blocks, *, model="claude-opus-5-5", agent=None):
    d = {"type": "assistant", "uuid": uuid, "timestamp": ts, "sessionId": SID, "requestId": rid, "cwd": "/tmp/est",
         "message": {"model": model, "content": blocks,
                     "usage": {"input_tokens": 10, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0,
                               "output_tokens": out}}}
    if agent:
        d.update(agentId=agent, isSidechain=True)
    return json.dumps(d, ensure_ascii=False)


def _text(n, ch="a"):
    return {"type": "text", "text": ch * n}


def _write(p: Path, lines, mode="w"):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, mode, encoding="utf-8") as fh:
        fh.write("".join(x + "\n" for x in lines))


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "projects" / PK).mkdir(parents=True)
    monkeypatch.setenv("AGENTDASH_CLAUDE_HOME", str(h))
    return h


def _db(tmp_path, name):
    return conn.connect(conn.init_db(tmp_path / f"{name}.db"))


def _sub(home, aid="x1"):
    sub = home / "projects" / PK / SID / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": "general-purpose", "toolUseId": "t1",
                                                            "spawnDepth": 1, "description": "est"}))
    return sub / f"agent-{aid}.jsonl"


STREAM3 = [  # 같은 requestId 3 줄 — 기록 output 1,1,1 · text 합 2,000 자 (스트리밍 시작값만 남은 서브에이전트 기록)
    ("u1", "RQ", "2026-10-20T01:00:00Z", 1, [_text(700)]),
    ("u2", "RQ", "2026-10-20T01:00:01Z", 1, [_text(700)]),
    ("u3", "RQ", "2026-10-20T01:00:02Z", 1, [_text(600)]),
]


def _lines(rows, agent="x1"):
    return [_line(u, r, t, o, b, agent=agent) for u, r, t, o, b in rows]


# ── 순수 함수 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("max_out,json_len,est_chars,want", [
    (29, 401, 2000, 500),
    (30, 401, 2000, None),      # output 30 은 의심 아님 (< 30)
    (29, 400, 2000, None),      # 길이 400 은 의심 아님 (> 400)
    (0, 401, 10, 3),            # ceil(10/4)
    (20, 401, 40, 20),          # 하한 = 기록 output
])
def test_estimate_table(max_out, json_len, est_chars, want):
    assert U.SUSPECT_MAX_OUTPUT == 30 and U.SUSPECT_MIN_JSON == 400
    assert U.estimate(max_out, json_len, est_chars) == want


def test_parser_lengths():
    blocks = [_text(100, "가"), {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"a": "b"}},
              {"type": "thinking", "thinking": "z" * 500, "signature": "s"}]
    rec = tr_p.parse_line(_line("p1", "R1", "2026-10-20T00:00:00Z", 5, blocks))
    assert rec.est_chars == 100 + len('{"a": "b"}')                      # thinking 은 0
    assert rec.content_json_len == sum(len(json.dumps(b)) for b in blocks)
    user = json.dumps({"type": "user", "uuid": "u", "timestamp": "2026-10-20T00:00:00Z", "sessionId": SID,
                       "message": {"role": "user", "content": [_text(900)]}})
    r2 = tr_p.parse_line(user)
    assert r2.est_chars == 0 and r2.content_json_len == 0                 # 사용자 줄은 재지 않는다


def test_cost_est_uses_output_est():
    p = U.load_pricing()
    from agentdash.core import model as M
    ev = M.UsageEvent(agent_key="A:x", request_id="r", at="2026-10-20T00:00:00Z", model="claude-opus-5-5",
                      input_tokens=10, cache_read=100, output_tokens=1)
    ev.cost_usd, _ = U.cost(ev, p)
    assert U.cost_est(ev, p) == ev.cost_usd                               # output_est 없음 → cost_usd
    ev.output_est = 500
    want = (10 * 4.0 + 100 * 0.2 + 500 * 20.0) / 1e6
    assert U.cost_est(ev, p) == pytest.approx(want, abs=1e-12)
    ev2 = M.UsageEvent(agent_key="A:x", request_id="r", at=None, model="claude-mystery-9", output_tokens=1, output_est=99)
    assert U.cost_est(ev2, p) is None                                     # 단가 없는 모델 → 둘 다 NULL


# ── 수집 ─────────────────────────────────────────────────────────────
def test_ingest_sets_output_est(home, tmp_path):
    _write(_sub(home), _lines(STREAM3))
    con = _db(tmp_path, "a")
    ingest.ingest_all(con, run_hooks=False)
    row = con.execute("SELECT output_tokens, output_est, cost_usd, cost_est_usd FROM usage_event "
                      "WHERE agent_key='A:x1' AND request_id='RQ'").fetchone()
    assert row[0] == 1 and row[1] == math.ceil(2000 / 4) == 500
    assert row[3] > row[2] > 0


def test_not_suspect_is_null(home, tmp_path):
    _write(_sub(home), _lines([("u1", "RN", "2026-10-20T01:00:00Z", 500, [_text(3000)])]))
    con = _db(tmp_path, "a")
    ingest.ingest_all(con, run_hooks=False)
    o, est, c, ce = con.execute("SELECT output_tokens, output_est, cost_usd, cost_est_usd FROM usage_event").fetchone()
    assert o == 500 and est is None and ce == c


def test_synthetic_excluded(home, tmp_path):
    _write(_sub(home), [_line("s1", "RS", "2026-10-20T01:00:00Z", 0, [_text(3000)], model="<synthetic>", agent="x1")])
    con = _db(tmp_path, "a")
    ingest.ingest_all(con, run_hooks=False)
    assert con.execute("SELECT COUNT(*) FROM usage_event").fetchone()[0] == 0


def test_main_session_same_rule(home, tmp_path):
    """종류로 거르지 않는다 (spec §6.2 범위) — 메인 세션 기록도 같은 규칙."""
    _write(home / "projects" / PK / f"{SID}.jsonl", _lines(STREAM3, agent=None))
    con = _db(tmp_path, "a")
    ingest.ingest_all(con, run_hooks=False)
    assert con.execute(f"SELECT output_est FROM usage_event WHERE agent_key='S:{SID}'").fetchone()[0] == 500


def test_split_request_same_as_single_pass(home, tmp_path):
    """한 요청이 두 번의 증분 읽기(2 줄 · 1 줄)에 걸쳐 들어와도 한 번에 읽은 것과 같다 (Review Focus 1)."""
    f = _sub(home)
    lines = _lines(STREAM3)
    _write(f, lines[:2])
    split = _db(tmp_path, "split")
    ingest.ingest_all(split, run_hooks=False)
    split.commit()
    first = split.execute("SELECT output_est FROM usage_event").fetchone()[0]
    assert first == math.ceil(1400 / 4)
    _write(f, lines[2:], mode="a")
    ingest.ingest_all(split, run_hooks=False)
    split.commit()
    single = _db(tmp_path, "single")
    ingest.ingest_all(single, run_hooks=False)
    q = "SELECT agent_key, request_id, output_tokens, output_est, cost_usd, cost_est_usd FROM usage_event ORDER BY 1, 2"
    assert split.execute(q).fetchall() == single.execute(q).fetchall()
    assert single.execute("SELECT output_est FROM usage_event").fetchone()[0] == 500


def test_reread_from_start_not_doubled(home, tmp_path):
    """같은 프로세스에서 같은 DB 경로를 새로 만들어 처음부터 다시 읽어도 길이를 두 번 더하지 않는다."""
    _write(_sub(home), _lines(STREAM3))
    path = tmp_path / "again.db"
    for _ in range(2):
        if path.exists():
            path.unlink()
        con = conn.connect(conn.init_db(path))
        ingest.ingest_all(con, run_hooks=False)
        con.commit()
        assert con.execute("SELECT output_est FROM usage_event").fetchone()[0] == 500
        con.close()


def test_no_length_stored(home, tmp_path):
    blocks = [_text(900, "본")]
    _write(_sub(home), _lines([("u1", "RL", "2026-10-20T01:00:00Z", 1, blocks)]))
    con = _db(tmp_path, "a")
    ingest.ingest_all(con, run_hooks=False)
    cols = [r[1] for r in con.execute("PRAGMA table_info(usage_event)")]
    assert cols == USAGE_COLS                                               # 길이 열 없음 (spec §3 블록 그대로)
    for (v,) in con.execute("SELECT agent_key || request_id || at || model || COALESCE(speed,'') || "
                            "COALESCE(pricing_ver,'') FROM usage_event"):
        assert "본" not in v and len(v) <= 300
    daily = [r[1] for r in con.execute("PRAGMA table_info(usage_daily)")]
    assert "output_est" in daily and "cost_est_usd" in daily and not any("len" in c or "chars" in c for c in daily)
