"""`uv run python -m agentdash.app` — settings 의 host(127.0.0.1 고정) · port 로 uvicorn 기동."""

from __future__ import annotations

import uvicorn

from agentdash import settings as _settings


def main() -> None:
    s = _settings.get()
    uvicorn.run("agentdash.app.main:app", host=s.host, port=s.port, log_level="info")


if __name__ == "__main__":
    main()
