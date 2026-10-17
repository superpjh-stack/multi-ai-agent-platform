"""GET /api/v1/graph — Cytoscape 형식 {nodes, edges} (spec.md §5 · §8). 담당 개발2.

    /api/v1/graph?since=24h|7d|all|<ISO>&project=&view=tree|collab|pipeline&state=A,B&kind=SESSION,SUBAGENT&min_tokens=0&expand=<key>,…

잘못된 필터 값은 422 + 이유 (조용히 기본값으로 바꾸지 않는다). 데이터는 core/graph.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from agentdash.core import graph as G
from agentdash.db import conn

router = APIRouter()


@router.get("/api/v1/graph")
def graph(since: str | None = None, project: str | None = None, view: str | None = None,
          state: str | None = None, kind: str | None = None, min_tokens: int = Query(0, ge=0),
          expand: str | None = None, handback: int = 1):
    con = conn.connect()
    try:
        return G.build(con, since=since, project=project, view=view, states=state, kinds=kind,
                       min_tokens=min_tokens, expand=expand, show_handback=bool(handback))
    except G.GraphError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    finally:
        con.close()
