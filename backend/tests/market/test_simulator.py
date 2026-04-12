"""Tests for the GBM simulator internals (price stepping, events, correlation)."""

import math
import random

from app.market.seed_prices import (
    DEFAULT_SEED,
    SECTOR_CORRELATION,
    TICK_INTERVAL,
    TICKER_SEEDS,
)
from app.market.simulator import SimulatorMarketDataSource, _TickerState


def make_source(seed: int = 42) -> SimulatorMarketDataSource:
    """Create a simulator with a fixed-seed RNG for deterministic tests."""
    return SimulatorMarketDataSource(rng=random.Random(seed))


# ---------------------------------------------------------------------------
# Ticker initialisation
# ---------------------------------------------------------------------------


def test_init_known_ticker_uses_seed_price():
    src = make_source()
    src._init_ticker("AAPL")
    state = src._tickers["AAPL"]
    assert state.price == TICKER_SEEDS["AAPL"]["price"]
    assert state.volatility == TICKER_SEEDS["AAPL"]["volatility"]
    assert state.sector == TICKER_SEEDS["AAPL"]["sector"]


def test_init_unknown_ticker_uses_default():
    src = make_source()
    src._init_ticker("UNKNOWN")
    state = src._tickers["UNKNOWN"]
    assert state.price == DEFAULT_SEED["price"]
    assert state.volatility == DEFAULT_SEED["volatility"]
    assert state.sector == DEFAULT_SEED["sector"]


def test_prev_close_equals_seed_price():
    """prev_close is fixed at the seed price for the process lifetime."""
    src = make_source()
    src._init_ticker("TSLA")
    state = src._tickers["TSLA"]
    assert state.prev_close == state.price
    assert state.prev_close == TICKER_SEEDS["TSLA"]["price"]


def test_multiple_tickers_tracked_independently():
    src = make_source()
    src._init_ticker("AAPL")
    src._init_ticker("JPM")
    assert src._tickers["AAPL"].sector == "tech"
    assert src._tickers["JPM"].sector == "finance"
    assert src._tickers["AAPL"].price != src._tickers["JPM"].price


# ---------------------------------------------------------------------------
# GBM step
# ---------------------------------------------------------------------------


def test_gbm_step_produces_positive_price():
    src = make_source()
    state = _TickerState(price=190.0, prev_close=190.0, volatility=0.25, sector="tech")
    dt = TICK_INTERVAL / (252 * 6.5 * 3600)
    for _ in range(100):
        src._step_price(state, dt, src._rng.gauss(0, 1))
    assert state.price > 0


def test_gbm_step_rounds_to_two_decimal_places():
    src = make_source()
    state = _TickerState(price=190.0, prev_close=190.0, volatility=0.25, sector="tech")
    dt = TICK_INTERVAL / (252 * 6.5 * 3600)
    src._step_price(state, dt, 1.0)
    assert state.price == round(state.price, 2)


def test_price_clamped_above_minimum():
    """Price should never go below $0.01 even with extreme negative shocks."""
    src = make_source()
    state = _TickerState(price=0.01, prev_close=0.01, volatility=10.0, sector="other")
    dt = TICK_INTERVAL / (252 * 6.5 * 3600)
    for _ in range(50):
        src._step_price(state, dt, -10.0)  # Extreme negative z
    assert state.price >= 0.01


def test_gbm_step_deterministic_with_fixed_rng():
    """Same seed → same price sequence."""
    dt = TICK_INTERVAL / (252 * 6.5 * 3600)

    state1 = _TickerState(price=190.0, prev_close=190.0, volatility=0.25, sector="tech")
    src1 = make_source(seed=99)
    for _ in range(10):
        src1._step_price(state1, dt, src1._rng.gauss(0, 1))

    state2 = _TickerState(price=190.0, prev_close=190.0, volatility=0.25, sector="tech")
    src2 = make_source(seed=99)
    for _ in range(10):
        src2._step_price(state2, dt, src2._rng.gauss(0, 1))

    assert state1.price == state2.price


# ---------------------------------------------------------------------------
# Random event
# ---------------------------------------------------------------------------


def test_event_applies_large_move():
    src = make_source()
    state = _TickerState(price=190.0, prev_close=190.0, volatility=0.25, sector="tech")
    original = state.price
    src._apply_event(state)
    pct_change = abs(state.price - original) / original
    assert pct_change >= 0.02  # At least 2% move


def test_event_magnitude_within_bounds():
    src = make_source()
    state = _TickerState(price=100.0, prev_close=100.0, volatility=0.25, sector="tech")
    original = state.price
    for _ in range(100):
        state.price = original
        src._apply_event(state)
        pct_change = abs(state.price - original) / original
        assert 0.019 <= pct_change <= 0.051  # 2%–5% (with rounding tolerance)


def test_event_price_remains_positive():
    src = make_source()
    state = _TickerState(price=0.02, prev_close=0.02, volatility=0.25, sector="tech")
    src._apply_event(state)
    assert state.price >= 0.01


# ---------------------------------------------------------------------------
# Sector correlation
# ---------------------------------------------------------------------------


def test_sector_correlation_values_exist():
    for sector in ["tech", "finance", "auto", "other"]:
        assert sector in SECTOR_CORRELATION
        assert 0.0 <= SECTOR_CORRELATION[sector] <= 1.0


def test_zero_correlation_sector_uses_only_idiosyncratic():
    """With correlation=0, Z = 0 * Z_sector + 1 * Z_idio = Z_idio."""
    corr = SECTOR_CORRELATION["other"]
    assert corr == 0.0
    z_sector = 1.0
    z_idio = 0.5
    z = corr * z_sector + math.sqrt(1 - corr**2) * z_idio
    assert abs(z - z_idio) < 1e-10


def test_correlation_blends_sector_and_idio():
    corr = 0.6
    z_sector = 1.0
    z_idio = 0.0
    z = corr * z_sector + math.sqrt(1 - corr**2) * z_idio
    assert abs(z - 0.6) < 1e-10


# ---------------------------------------------------------------------------
# Tick interval and drift
# ---------------------------------------------------------------------------


def test_tick_interval_is_half_second():
    assert TICK_INTERVAL == 0.5


def test_drift_is_zero():
    from app.market.seed_prices import DRIFT
    assert DRIFT == 0.0
