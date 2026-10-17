"""Jinja2 렌더 — templates/ 하나. 화면은 서버 렌더 + static/*.js (spec.md §1.1)."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def render(request, name: str, ctx: dict | None = None, status_code: int = 200):
    return TEMPLATES.TemplateResponse(request, name, ctx or {}, status_code=status_code)
