# Repository Guidelines

## Project Structure & Module Organization

`agentdash` is a local dashboard for Claude Code activity, built with Python 3.12, FastAPI, SQLite, Jinja2, and SSE. Source lives in `src/agentdash/`: `collect/` ingests records, `core/` handles relationships, state, and usage, `db/` owns persistence, and `app/` contains routers and templates. Validation tools live in `src/agentdash/tools/`; helper scripts in `scripts/`. YAML configuration belongs in `config/`. Tests and versioned, redacted fixtures live in `tests/`. Runtime databases use `data/`; reports and exports use `outputs/`.

## Build, Test, and Development Commands

Use `uv` for the pinned Python environment:

- `make setup`: install dependencies and initialize the SQLite schema.
- `AGENTDASH_DB=data/agentdash-dev1.db AGENTDASH_PORT=8096 make run`: start an isolated development server and watcher.
- `make backfill`: import historical records; optionally pass `SINCE=2026-08-01`.
- `make test`: run `uv run pytest -q`.
- `uv run pytest tests/test_state.py -q`: run focused tests.
- `make gate`: evaluate acceptance gates G-01 through G-35.
- `make check-readonly` / `make check-fixtures`: verify source protection and fixture redaction.

## Coding Style & Naming Conventions

Follow existing four-space Python indentation, `snake_case` functions/modules, `PascalCase` classes, and type annotations. No formatter or linter is configured in `pyproject.toml`. Define routers in `app/routers/<domain>.py`, register them in `app/main.py`, and render through `templating.render`. Reuse `base.html` CSS tokens. Access configuration through `settings.get()` and databases through `db.conn`; keep pricing and budgets in YAML.

## Testing Guidelines

Use pytest with `test_*.py` files and `test_*` functions. Preserve `tests/conftest.py` source isolation and use fake-root fixtures rather than live records. Generate fixtures only through `make fixtures`. Add regression tests for changed behavior; run relevant checks and the acceptance gates. No numeric coverage threshold is configured; never weaken gates or remove regression assertions to obtain a pass.

## Commit & Pull Request Guidelines

History uses descriptive Korean subjects identifying the phase, component, or defect, often including `DEF-QA…` and `D-nn` references. Follow that pattern. In pull requests, explain behavior changes, link relevant decisions or defects, report validation commands/results, and include screenshots for UI changes.

## Safety & Project Instructions

Read `CLAUDE.md` and its referenced specifications and ownership rules before implementation. Treat source records as read-only; never persist conversation payloads. Bind only to `127.0.0.1`. Leave the human server on port 8095 running. Real hook installation is human-only. Preserve protected specifications and record unresolved decisions in `decisions.md`.
