"""G-11 — 실시간: 훅 POST → 1 초 안에 상태 반영 + SSE agent.state · 새 세션 + 서브에이전트 2 → 5 초 안에 SSE agent.new 3.

서버는 실제 uvicorn 을 127.0.0.1 의 빈 포트에 띄우고(스레드), SSE 는 httpx 스트림(Accept: text/event-stream)으로 읽는다.
가짜 루트만 쓴다 — `fake_claude_home_rw` 는 Claude Code 역할(새 세션 파일 쓰기)만 한다.
감시기(collect/watcher.py)는 개발1 몫이다. 없으면 `agent.new` 테스트는 FAIL(개발1 대기) 로 실패한다
(단 check_readonly 의 읽기 전용 실행에서는 건너뛴다 — 원천 무접촉 판정을 남의 미구현으로 깨지 않게).
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from agentdash.db import conn


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def server(monkeypatch):
    conn.init_db()
    port = _free_port()
    from agentdash.app.main import app
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    srv = uvicorn.Server(cfg)
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    t0 = time.time()
    while not srv.started and time.time() - t0 < 10:
        time.sleep(0.02)
    assert srv.started
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(5)


class SSEReader:
    """백그라운드 스레드로 SSE 를 읽어 (event, data, 받은 시각) 를 모은다."""

    def __init__(self, base: str):
        self.events: list[tuple[str, dict, float]] = []
        self.ready = threading.Event()
        self._stop = False
        self._th = threading.Thread(target=self._run, args=(base,), daemon=True)
        self._th.start()
        assert self.ready.wait(5), "SSE hello 못 받음"

    def _run(self, base):
        with httpx.Client(timeout=None) as c:
            with c.stream("GET", f"{base}/api/v1/stream", headers={"accept": "text/event-stream"}) as r:
                ev, data = None, None
                for line in r.iter_lines():
                    if self._stop:
                        break
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                    elif line == "" and ev:
                        if ev == "hello":
                            self.ready.set()
                        else:
                            self.events.append((ev, json.loads(data or "{}"), time.time()))
                        ev, data = None, None

    def wait(self, pred, timeout: float):
        t0 = time.time()
        while time.time() - t0 < timeout:
            hit = [e for e in self.events if pred(e)]
            if hit:
                return hit
            time.sleep(0.01)
        return [e for e in self.events if pred(e)]

    def close(self):
        self._stop = True


def _write_s1(home: Path, sid: str, status: str) -> None:
    (home / "sessions").mkdir(exist_ok=True)
    (home / "sessions" / f"{os.getpid()}.json").write_text(json.dumps({
        "pid": os.getpid(), "sessionId": sid, "cwd": "/tmp/fake-proj", "startedAt": int(time.time() * 1000),
        "version": "2.1.301", "kind": "interactive", "entrypoint": "cli", "name": "fake", "status": status,
        "updatedAt": int(time.time() * 1000), "statusUpdatedAt": int(time.time() * 1000)}), encoding="utf-8")


def test_hook_post_reflects_state_within_1s(server, fake_claude_home_rw):
    from agentdash.core import model as M
    sid = "11111111-2222-3333-4444-555555555555"
    _write_s1(fake_claude_home_rw, sid, "idle")
    con = conn.connect()
    M.upsert_agent(con, M.Agent(agent_key=f"S:{sid}", kind="SESSION", project_key="-tmp-fake-proj", session_id=sid,
                                last_event_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30))))
    con.commit()
    con.close()
    sse = SSEReader(server)
    try:
        payload = {"hook_event_name": "Notification", "session_id": sid, "notification_type": "permission_prompt",
                   "message": "Claude needs your permission", "prompt": "SECRET-BODY " * 1000,
                   "tool_input": {"command": "SECRET-CMD", "file_path": "/tmp/x.txt"}}
        t0 = time.time()
        r = httpx.post(f"{server}/hooks/event", json=payload, timeout=5)
        dt_post = time.time() - t0
        assert r.status_code == 200 and r.json()["state"] == "WAITING_PERMISSION", r.text
        hit = sse.wait(lambda e: e[0] == "agent.state" and e[1]["agent_key"] == f"S:{sid}", 1.0)
        assert hit and hit[0][1]["state"] == "WAITING_PERMISSION"
        assert hit[0][2] - t0 <= 1.0 and dt_post <= 1.0
        con = conn.connect()
        assert con.execute("SELECT state, state_reason FROM agent WHERE agent_key=?", (f"S:{sid}",)).fetchone()[:] == \
            ("WAITING_PERMISSION", "R-01")
        rows = con.execute("SELECT event, detail FROM hook_event").fetchall()
        con.close()
        assert len(rows) == 1 and rows[0][0] == "Notification"
        assert "SECRET" not in rows[0][1] and len(rows[0][1]) <= 300 and "/tmp/x.txt" in rows[0][1]
        # 프롬프트 제출 → RUNNING
        r = httpx.post(f"{server}/hooks/event", json={"hook_event_name": "UserPromptSubmit", "session_id": sid,
                                                      "prompt": "SECRET"}, timeout=5)
        assert r.json()["state"] == "RUNNING"
        assert sse.wait(lambda e: e[0] == "agent.state" and e[1]["state"] == "RUNNING", 1.0)
    finally:
        sse.close()


def test_hook_body_limit_and_garbage(server):
    big = b'{"hook_event_name":"Stop","x":"' + b"a" * (1024 * 1024) + b'"}'
    r = httpx.post(f"{server}/hooks/event", content=big, headers={"content-type": "application/json"}, timeout=10)
    assert r.status_code == 413
    r = httpx.post(f"{server}/hooks/event", content=b"not json", timeout=5)
    assert r.status_code == 200 and r.json()["accepted"] is False
    con = conn.connect()
    assert con.execute("SELECT COUNT(*) FROM hook_event").fetchone()[0] == 0
    con.close()


def test_hook_send_script_delivers(server, monkeypatch):
    """hook_send.sh → 서버 → hook_event 1 행 (실제 송신 경로)."""
    import subprocess
    port = server.rsplit(":", 1)[1]
    send = Path(__file__).resolve().parents[1] / "scripts" / "hook_send.sh"
    q = subprocess.run(["bash", str(send)], input=json.dumps({"hook_event_name": "SessionStart",
                                                               "session_id": "abc", "source": "startup"}).encode(),
                       capture_output=True, timeout=5, env={**os.environ, "AGENTDASH_PORT": port})
    assert q.returncode == 0 and q.stdout == b""
    con = conn.connect()
    assert con.execute("SELECT agent_key, event FROM hook_event").fetchall()[0][:] == ("S:abc", "SessionStart")
    con.close()


def _watcher_module():
    return importlib.util.find_spec("agentdash.collect.watcher")


def test_new_session_and_two_subagents_agent_new_within_5s(server, fake_claude_home_rw):
    if _watcher_module() is None:
        if os.environ.get("AGENTDASH_TEST_READONLY") == "1":
            pytest.skip("collect/watcher.py 없음 — 개발1 대기 (읽기 전용 실행에서는 건너뜀)")
        pytest.fail("FAIL(개발1 대기) — src/agentdash/collect/watcher.py 없음 (G-11 agent.new 5 초)")
    from agentdash.collect import watcher
    th, stop = watcher.start()          # 개발1 공표: start(db_path=None, on_batch=None) -> (thread, stop_event)
    sse = SSEReader(server)
    time.sleep(1.0)                     # 감시기 첫 ingest_all · watch 등록 대기 (측정은 파일을 쓴 순간부터)
    try:
        proj = fake_claude_home_rw / "projects" / "-tmp-rt-proj"
        sid = "99999999-8888-7777-6666-555555555555"
        sdir = proj / sid / "subagents"
        sdir.mkdir(parents=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        t0 = time.time()
        (proj / f"{sid}.jsonl").write_text(json.dumps({
            "type": "assistant", "uuid": "u1", "parentUuid": None, "timestamp": now, "sessionId": sid,
            "cwd": "/tmp/rt-proj", "message": {"model": "claude-opus-5", "content": [
                {"type": "tool_use", "id": "toolu_rt1", "name": "Agent", "input": {}},
                {"type": "tool_use", "id": "toolu_rt2", "name": "Agent", "input": {}}],
                "usage": {"input_tokens": 1, "output_tokens": 1}}, "requestId": "req_rt"}) + "\n", encoding="utf-8")
        for i in (1, 2):
            aid = f"a{i:016x}"
            (sdir / f"agent-{aid}.meta.json").write_text(json.dumps({
                "agentType": "general-purpose", "description": f"rt {i}", "toolUseId": f"toolu_rt{i}",
                "spawnDepth": 1, "requestShape": "background"}), encoding="utf-8")
            (sdir / f"agent-{aid}.jsonl").write_text(json.dumps({
                "type": "assistant", "uuid": f"s{i}", "parentUuid": None, "timestamp": now, "sessionId": sid,
                "isSidechain": True, "agentId": aid, "message": {"model": "claude-opus-5", "content": []}}) + "\n",
                encoding="utf-8")
        keys = {f"S:{sid}", "A:a0000000000000001", "A:a0000000000000002"}
        hit = sse.wait(lambda e: e[0] == "agent.new" and e[1]["agent_key"] in keys and len(
            {x[1]["agent_key"] for x in sse.events if x[0] == "agent.new"} & keys) == 3, 5.0)
        got = {e[1]["agent_key"] for e in sse.events if e[0] == "agent.new"} & keys
        assert got == keys, f"5 초 안 agent.new {len(got)}/3"
        assert max(e[2] for e in sse.events if e[0] == "agent.new" and e[1]["agent_key"] in keys) - t0 <= 5.0
        assert hit
    finally:
        sse.close()
        stop.set()
        th.join(5)
