# 멀티 에이전트 대시보드 — 명령 (CLAUDE.md 「명령」 · spec.md §1.3). 전부 `uv run …` (시스템 python 을 쓰지 않는다).
# 원천(~/.claude · 다른 에이전트 폴더)은 읽기만 한다. DB 는 AGENTDASH_DB (기본 config/settings.yaml 의 data/agentdash.db,
# 개발마다 AGENTDASH_DB=data/agentdash-dev{N}.db). 포트 8095 (개발 중 AGENTDASH_PORT=8096 · 8097). 127.0.0.1 만.
.PHONY: setup backfill run gate test hooks-install hooks-uninstall hooks-check pricing-check reprice export \
        fixtures check-fixtures check-routes check-readonly check-bind check-no-payload check-hooks

TOOLS := src/agentdash/tools
# 미구현 타깃 — 종료코드 2 로 분명히 실패한다 (조용한 성공 금지)
NOTYET = @echo "미구현 — 담당 $(1) (make $@) — goal.md §3.2"; exit 2

setup:            ## uv sync · DB 생성 · schema.sql 적용 (G-01)
	uv python pin 3.12
	uv sync
	uv run python -m agentdash.db.conn

backfill:         ## 과거 기록 전체 읽기 [SINCE=2026-08-01] — 개발1 (collect/)
	$(call NOTYET,개발1)

run:              ## 감시기 + 웹 (127.0.0.1:8095). 지금은 화면 placeholder 만 — 감시기는 개발1
	uv run python -m agentdash.app

gate:             ## 판정표 G-01~G-22 (goal.md §2)
	uv run python $(TOOLS)/gate.py

test:
	uv run pytest -q

hooks-install:    ## ~/.claude/settings.json 에 덧붙임 — 사람이 직접 실행한다 (goal.md §0.2). 개발2
	$(call NOTYET,개발2)

hooks-uninstall:  ## 식별 표시 붙은 훅 항목만 제거 — 사람이 직접. 개발2
	$(call NOTYET,개발2)

hooks-check:      ## 설치 여부 · 최근 수신 시각 · 이벤트별 건수 — 개발2
	$(call NOTYET,개발2)

pricing-check:    ## 기록의 모델 중 단가표에 없는 것 — 개발1
	$(call NOTYET,개발1)

reprice:          ## 단가표 바뀐 뒤 전 기간 비용 재계산 — 개발1
	$(call NOTYET,개발1)

export:           ## 작업량 CSV → outputs/ [FROM=… TO=…] — 개발1
	$(call NOTYET,개발1)

# ── 검사 도구 (gate 가 부르는 것과 같다) ─────────────────────────────
fixtures:         ## 실제 기록(읽기만)에서 본문 지운 픽스처 다시 만들기 → tests/fixtures/<ver>/
	uv run python scripts/make_fixture.py
	uv run python scripts/check_fixtures_redacted.py

check-fixtures:   ## G-13 픽스처 쪽
	uv run python scripts/check_fixtures_redacted.py

check-no-payload: ## G-13 DB 쪽 (V-04)
	uv run python $(TOOLS)/check_no_payload.py

check-readonly:   ## G-14 (V-05) 정적 스캔 + 읽기 전용 가짜 루트 pytest
	uv run python $(TOOLS)/check_readonly.py

check-hooks:      ## G-15 (V-10) 가짜 settings 로만
	uv run python $(TOOLS)/check_hooks.py

check-bind:       ## G-16 (V-06)
	uv run python $(TOOLS)/check_bind.py

check-routes:     ## G-17 화면 6 + API 10
	uv run python $(TOOLS)/check_routes.py
