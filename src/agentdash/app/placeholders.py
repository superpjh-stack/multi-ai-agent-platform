"""placeholder 표지 — 아직 구현하지 않은 화면 · API 를 명확히 드러낸다 (조용한 빈 화면 금지).

화면 GET 을 실제로 구현하면 그 라우터의 placeholder 호출을 지운다. `tools/check_routes.py` 가 남은 placeholder 수를 센다.
"""

from __future__ import annotations

MARK = "미구현"


def label(owner: str) -> str:
    return f"{MARK} — 담당 {owner}"


def api(owner: str, **empty) -> dict:
    """빈 응답 + 표지. 키 `_placeholder` 가 있으면 미구현이다."""
    return {"_placeholder": label(owner), **empty}
