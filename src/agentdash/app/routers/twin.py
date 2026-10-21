"""D-01 공장 평면도 API — `GET /api/v1/twin?since=&project=` (spec.md v0.4 §5.4 · §8). 담당 개발2.

    /api/v1/twin?since=24h|7d|30m|all|<ISO>&project=<project_key 또는 라인 이름 일부>

데이터 · 좌표는 `core/twin.build` 가 결정적으로 계산한다(T-07). 잘못된 since 는 422 + 이유 (조용히 기본값으로 바꾸지 않는다).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agentdash.core import twin as T
from agentdash.db import conn

router = APIRouter()


@router.get("/api/v1/twin")
def twin_api(since: str | None = None, project: str | None = None):
    con = conn.connect()
    try:
        return T.build(con, since=since, project=project)
    except T.TwinError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    finally:
        con.close()
