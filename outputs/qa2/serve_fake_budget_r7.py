"""QA2 r7 — 가짜 루트 서버 (8097) + 프로세스 안에서만 바꾼 예산 한도.
실제 config/budget.yaml 은 읽지도 쓰지도 않는다 — settings.load_yaml("budget.yaml") 만 이 프로세스 안에서 바꿔 끼운다.
한도는 outputs/qa2/fake-budget-r7.json 에서 매 요청 읽는다 (없으면 전부 null = 한도 미설정).

    AGENTDASH_CLAUDE_HOME=… AGENTDASH_AGENTS_ROOT=… AGENTDASH_DB=… AGENTDASH_PORT=8097 \
      uv run python outputs/qa2/serve_fake_budget_r7.py
"""
import json
import os

import uvicorn

from agentdash import settings

HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, "fake-budget-r7.json")
_orig = settings.load_yaml


def _patched(name: str) -> dict:
    if name == "budget.yaml":
        if os.path.exists(FAKE):
            with open(FAKE) as f:
                return json.load(f)
        return {"warn_ratio": 0.8, "total": {"daily_usd": None, "monthly_usd": None}, "projects": {}}
    return _orig(name)


settings.load_yaml = _patched

if __name__ == "__main__":
    s = settings.get()
    assert s.port == 8097 and s.host == "127.0.0.1"
    uvicorn.run("agentdash.app.main:app", host=s.host, port=s.port, log_level="info")
