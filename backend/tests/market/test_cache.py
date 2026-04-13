"""Tests for PriceCache."""

from datetime import datetime, timezone

from app.market.cache import PriceCache
from app.market.models import PriceTick


def _tick(ticker: str, price: float, prev_close: float = 100.0) -> PriceTick:
    return PriceTick(ticker=ticker, price=price, prev_close=prev_close, timestamp=datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_cache_is_empty():
    cache = PriceCache()
    assert cache.get_all() == {}


def test_initial_version_is_zero():
    cache = PriceCache()
    assert cache.version == 0


def test_get_unknown_ticker_returns_none():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_get_price_unknown_ticker_returns_none():
    cache = PriceCache()
    assert cache.get_price("AAPL") is None


# ---------------------------------------------------------------------------
# on_price stores and derives fields
# ---------------------------------------------------------------------------


async def test_on_price_stores_entry():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.42, prev_close=190.00))
    entry = cache.get("AAPL")
    assert entry is not None
    assert entry.ticker == "AAPL"
    assert entry.price == 191.42


async def test_on_price_increments_version():
    cache = PriceCache()
    assert cache.version == 0
    await cache.on_price(_tick("AAPL", 191.00))
    assert cache.version == 1
    await cache.on_price(_tick("AAPL", 192.00))
    assert cache.version == 2


async def test_on_price_computes_day_change():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.42, prev_close=190.00))
    entry = cache.get("AAPL")
    assert abs(entry.day_change - 1.42) < 0.001


async def test_on_price_computes_day_change_pct():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00, prev_close=190.00))
    entry = cache.get("AAPL")
    expected_pct = (191.00 - 190.00) / 190.00 * 100
    assert abs(entry.day_change_pct - expected_pct) < 0.001


async def test_direction_up():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    await cache.on_price(_tick("AAPL", 192.00))
    assert cache.get("AAPL").direction == "up"


async def test_direction_down():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 192.00))
    await cache.on_price(_tick("AAPL", 191.00))
    assert cache.get("AAPL").direction == "down"


async def test_direction_flat():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    await cache.on_price(_tick("AAPL", 191.00))
    assert cache.get("AAPL").direction == "flat"


async def test_first_tick_direction_is_flat():
    """On the very first tick, prev_price == price, so direction is flat."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    assert cache.get("AAPL").direction == "flat"


async def test_prev_price_tracks_previous_tick():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    await cache.on_price(_tick("AAPL", 192.00))
    entry = cache.get("AAPL")
    assert entry.prev_price == 191.00
    assert entry.price == 192.00


# ---------------------------------------------------------------------------
# get / get_price / get_all / remove
# ---------------------------------------------------------------------------


async def test_get_returns_cached_price():
    cache = PriceCache()
    await cache.on_price(_tick("MSFT", 420.00))
    entry = cache.get("MSFT")
    assert entry is not None
    assert entry.price == 420.00


async def test_get_price_returns_float():
    cache = PriceCache()
    await cache.on_price(_tick("MSFT", 420.00))
    assert cache.get_price("MSFT") == 420.00


async def test_get_all_returns_all_tickers():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    await cache.on_price(_tick("MSFT", 420.00))
    all_prices = cache.get_all()
    assert "AAPL" in all_prices
    assert "MSFT" in all_prices
    assert len(all_prices) == 2


async def test_get_all_returns_copy():
    """Mutating the returned dict does not affect the cache."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    all_prices = cache.get_all()
    all_prices["FAKE"] = None  # type: ignore
    assert "FAKE" not in cache.get_all()


async def test_remove_deletes_entry():
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    cache.remove("AAPL")
    assert cache.get("AAPL") is None


def test_remove_unknown_ticker_is_noop():
    cache = PriceCache()
    cache.remove("UNKNOWN")  # Should not raise


async def test_zero_prev_close_produces_zero_day_change():
    """Guard against division by zero when prev_close is 0."""
    cache = PriceCache()
    tick = PriceTick(ticker="TEST", price=50.0, prev_close=0.0, timestamp=datetime.now(timezone.utc))
    await cache.on_price(tick)
    entry = cache.get("TEST")
    assert entry.day_change == 0.0
    assert entry.day_change_pct == 0.0
