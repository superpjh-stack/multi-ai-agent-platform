"""config/*.yaml = spec.md §6.1 · §7.1 표 (지어내지 않는다)."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def test_pricing_matches_spec_table():
    p = load("pricing.yaml")
    assert p["version"] == "2026-10-06"
    assert p["cache_write_mult"] == {"5m": 1.25, "1h": 2.0}
    m = p["models"]
    expected = {
        "claude-fable-5-1": (10.0, 50.0, 0.25), "claude-fable-5": (10.0, 50.0, 1.0),
        "claude-opus-5-5": (4.0, 20.0, 0.20), "claude-opus-5": (5.0, 25.0, 0.50),
        "claude-opus-4-8": (5.0, 25.0, 0.50), "claude-opus-4-7": (5.0, 25.0, 0.50),
        "claude-opus-4-6": (5.0, 25.0, 0.50), "claude-sonnet-5-5": (2.0, 10.0, 0.20),
        "claude-sonnet-5": (2.0, 10.0, 0.20), "claude-sonnet-4-6": (3.0, 15.0, 0.30),
        "claude-haiku-4-5": (1.0, 5.0, 0.10),
    }
    for k, (i, o, cr) in expected.items():
        assert (m[k]["in"], m[k]["out"], m[k]["cache_read"]) == (i, o, cr), k
    assert set(m) == set(expected) | {"claude-haiku-5-5"}
    assert m["claude-opus-5-5"]["fast_mult"] == 2.0 and m["claude-opus-5"]["fast_mult"] == 2.0
    tiers = m["claude-haiku-5-5"]["tiers"]
    assert [(t["max_prompt"], t["in"], t["out"], t["cache_read"]) for t in tiers] == [
        (100000, 0.10, 0.50, 0.01), (None, 0.50, 2.50, 0.05)]
    assert p["aliases"] == {"claude-opus-5-5[1m]": "claude-opus-5-5"}


def test_companies_11():
    c = load("companies.yaml")
    names = [x["name"] for x in c["companies"]]
    assert len(names) == 11 and "고려솔더" in names and "송월타월서울상사" in names
    assert c["normalize_strip"] == [" ", "주식회사", "(주)"]


def test_pipeline_stages():
    p = load("pipeline.yaml")
    assert p["display_order"] == ["01", "02", "03", "04", "00", "05", "06", "08"]
    need = {k: v["need"] for k, v in p["stages"].items()}
    assert need == {"01": 3, "02": 5, "03": 3, "04": 7, "00": 5, "05": None, "06": None, "08": None}


def test_budget_yaml_defaults():
    """spec.md v0.3 §6.3 — 금액은 사람이 넣는다. 기본은 null (한도 미설정) · 프로젝트 없음."""
    b = load("budget.yaml")
    assert b["warn_ratio"] == 0.8
    assert b["total"] == {"daily_usd": None, "monthly_usd": None}
    assert b["projects"] == {}


def test_haiku_5_5_cache_read_confirmed():
    """D-08 확정 (2026-10-21 공식 단가 페이지 대조) — `[추정]` 표시 제거, 값은 spec §6.1 그대로."""
    h = load("pricing.yaml")["models"]["claude-haiku-5-5"]
    assert "cache_read_estimated" not in h


def test_check_decisions_evaluate():
    """G-23 판정 함수 — 7 D 확정 · D-08 출처 · src/ 남은 「가설 D-18」 을 본다."""
    import sys

    sys.path.insert(0, str(ROOT / "src" / "agentdash" / "tools"))
    import check_decisions as cd

    url = "u://pricing"
    ok_text = "".join(f"## {d} x\n- 상태: 확정 (2026-10-20)\n" + (f"- 출처 {url}\n" if d == "D-08" else "")
                      for d in cd.REQUIRED)
    assert cd.evaluate(ok_text, {"a.py": "x = 1"}, url)[0]
    assert not cd.evaluate(ok_text, {"a.py": 'N = "가설 D-18"'}, url)[0]
    assert not cd.evaluate(ok_text.replace("## D-19 x\n- 상태: 확정", "## D-19 x\n- 상태: 가설"), {}, url)[0]
    assert not cd.evaluate(ok_text.replace(url, "-"), {}, url)[0]
    blocked = ok_text.replace("## D-08 x\n- 상태: 확정", "## D-08 x\n- 상태: 차단")
    assert cd.evaluate(blocked, {}, url)[0]                      # 날짜 있는 D-08 차단은 허용
