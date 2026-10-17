"""G-08 비용 공식 (spec.md §6.1) — 5m/1h 캐시 쓰기 · fast · Haiku 구간 · 모르는 모델 NULL 경계.

기대값은 config/pricing.yaml 의 단가로 손계산한 숫자다 (코드의 공식을 다시 부르지 않는다).
"""

import pytest

from agentdash.core import model as M
from agentdash.core import usage as U


@pytest.fixture(scope="module")
def pricing():
    return U.load_pricing()


def ev(model, **kw):
    base = dict(agent_key="A:x", request_id="r", at="2026-10-17T00:00:00Z", model=model)
    base.update(kw)
    return M.UsageEvent(**base)


def test_pricing_version(pricing):
    assert pricing.version == "2026-10-06"
    c, ver = U.cost(ev("claude-opus-5-5", input_tokens=1), pricing)
    assert ver == "2026-10-06"


def test_basic_opus55(pricing):
    # opus-5-5: in 4 · out 20 · cr 0.20
    e = ev("claude-opus-5-5", input_tokens=1000, cache_read=10_000, output_tokens=2000)
    c, _ = U.cost(e, pricing)
    assert c == pytest.approx((1000 * 4 + 10_000 * 0.20 + 2000 * 20) / 1e6)   # 0.046


def test_cache_write_5m_and_1h(pricing):
    # sonnet-5: in 2 → 5m 2.5 / 1h 4.0 per 1M
    e = ev("claude-sonnet-5", cache_write_5m=1_000_000, cache_write_1h=1_000_000)
    c, _ = U.cost(e, pricing)
    assert c == pytest.approx(2.5 + 4.0)
    only5 = U.cost(ev("claude-sonnet-5", cache_write_5m=400_000), pricing)[0]
    assert only5 == pytest.approx(400_000 * 2 * 1.25 / 1e6)   # 1.0


def test_legacy_no_ttl_split_is_5m():
    """분리 값이 없는 옛 기록 → 파서가 전부 cache_write_5m 에 넣는다 (spec §6.1)."""
    import json

    from agentdash.collect.parsers import transcript as tr_p

    line = json.dumps({"type": "assistant", "uuid": "u", "timestamp": "2026-10-17T00:00:00Z", "sessionId": "s",
                       "requestId": "r", "message": {"model": "claude-opus-4-8", "content": [],
                                                     "usage": {"cache_creation_input_tokens": 800_000}}})
    u = tr_p.parse_line(line).usage
    assert (u.cache_write_5m, u.cache_write_1h) == (800_000, 0)
    c, _ = U.cost(ev("claude-opus-4-8", cache_write_5m=u.cache_write_5m), U.load_pricing())
    assert c == pytest.approx(800_000 * 5 * 1.25 / 1e6)     # 5.0


def test_fast_multiplier(pricing):
    std = U.cost(ev("claude-opus-5-5", input_tokens=1_000_000, output_tokens=1_000_000, speed="standard"), pricing)[0]
    fast = U.cost(ev("claude-opus-5-5", input_tokens=1_000_000, output_tokens=1_000_000, speed="fast"), pricing)[0]
    assert std == pytest.approx(24.0) and fast == pytest.approx(48.0)          # 8 / 40
    assert U.cost(ev("claude-opus-5", output_tokens=1_000_000, speed="fast"), pricing)[0] == pytest.approx(50.0)


def test_fast_without_fast_price_is_null(pricing):
    """빠른 모드 단가가 없는 모델(spec 표 '—')에 fast 가 오면 지어내지 않고 NULL."""
    assert U.cost(ev("claude-sonnet-5", output_tokens=10, speed="fast"), pricing)[0] is None
    assert U.cost(ev("claude-sonnet-5", output_tokens=10, speed=None), pricing)[0] == pytest.approx(10 * 10 / 1e6)


@pytest.mark.parametrize("prompt_in,expect_in,expect_out", [(100_000, 0.10, 0.50), (100_001, 0.50, 2.50)])
def test_haiku55_tier_boundary(pricing, prompt_in, expect_in, expect_out):
    e = ev("claude-haiku-5-5", input_tokens=prompt_in, output_tokens=1000)
    c, _ = U.cost(e, pricing)
    assert c == pytest.approx((prompt_in * expect_in + 1000 * expect_out) / 1e6)


def test_haiku55_prompt_includes_cache(pricing):
    # 입력 50K + 캐시 읽기 40K + 캐시 쓰기 20K = 110K > 100K → 위 구간
    e = ev("claude-haiku-5-5", input_tokens=50_000, cache_read=40_000, cache_write_5m=20_000)
    c, _ = U.cost(e, pricing)
    assert c == pytest.approx((50_000 * 0.50 + 40_000 * 0.05 + 20_000 * 0.50 * 1.25) / 1e6)


def test_unknown_model_null(pricing):
    assert U.cost(ev("claude-unknown-9", input_tokens=5), pricing)[0] is None
    assert U.cost(ev(None, input_tokens=5), pricing)[0] is None


def test_alias(pricing):
    a = U.cost(ev("claude-opus-5-5[1m]", output_tokens=1000), pricing)[0]
    assert a == pytest.approx(1000 * 20 / 1e6)


def test_thinking_not_added(pricing):
    """D-03: thinking_tokens 는 output_tokens 안 — 따로 더하지 않는다."""
    a = U.cost(ev("claude-fable-5-1", output_tokens=1000, thinking_tokens=900), pricing)[0]
    assert a == pytest.approx(1000 * 50 / 1e6)


def test_zero_tokens_zero_cost(pricing):
    assert U.cost(ev("claude-fable-5-1"), pricing)[0] == 0.0
