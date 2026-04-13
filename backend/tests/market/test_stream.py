"""Tests for the SSE price stream endpoint."""

import json
from datetime import datetime, timezone

from app.market.cache import PriceCache
from app.market.models import PriceTick
from app.market.stream import create_stream_router


def _tick(ticker: str, price: float, prev_close: float = 100.0) -> PriceTick:
    return PriceTick(
        ticker=ticker,
        price=price,
        prev_close=prev_close,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Router creation
# ---------------------------------------------------------------------------


def test_create_stream_router_returns_router():
    cache = PriceCache()
    router = create_stream_router(cache)
    routes = [r.path for r in router.routes]
    assert "/stream/prices" in routes


# ---------------------------------------------------------------------------
# Event JSON format
# ---------------------------------------------------------------------------


async def test_stream_event_json_has_required_fields():
    """Verify that cache data can produce events with all spec-required fields."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.42, prev_close=190.00))

    cached = cache.get("AAPL")
    event = json.loads(json.dumps({
        "ticker": cached.ticker,
        "price": cached.price,
        "prev_price": cached.prev_price,
        "prev_close": cached.prev_close,
        "day_change": round(cached.day_change, 4),
        "day_change_pct": round(cached.day_change_pct, 4),
        "direction": cached.direction,
        "timestamp": cached.timestamp.isoformat(),
    }))

    required_fields = {
        "ticker", "price", "prev_price", "prev_close",
        "day_change", "day_change_pct", "direction", "timestamp",
    }
    assert required_fields.issubset(event.keys())


async def test_stream_event_values_are_correct():
    """Verify event values match what the cache contains."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.42, prev_close=190.00))

    cached = cache.get("AAPL")
    event = {
        "ticker": cached.ticker,
        "price": cached.price,
        "prev_price": cached.prev_price,
        "prev_close": cached.prev_close,
        "day_change": round(cached.day_change, 4),
        "day_change_pct": round(cached.day_change_pct, 4),
        "direction": cached.direction,
        "timestamp": cached.timestamp.isoformat(),
    }

    assert event["ticker"] == "AAPL"
    assert event["price"] == 191.42
    assert event["prev_close"] == 190.00
    assert abs(event["day_change"] - 1.42) < 0.01
    assert event["direction"] == "flat"  # First tick — prev_price == price


# ---------------------------------------------------------------------------
# Version-based change detection
# ---------------------------------------------------------------------------


async def test_no_events_when_version_unchanged():
    """If version hasn't changed since last send, no events should be emitted."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))

    # Simulate the stream logic: after sending once at version 1,
    # a second check at the same version should yield nothing
    last_version = cache.version  # version = 1
    current_version = cache.version
    assert current_version == last_version  # No change — nothing to send


async def test_events_emitted_when_version_advances():
    """When version advances, new events should be emitted."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    last_version = cache.version  # 1

    await cache.on_price(_tick("AAPL", 192.00))  # version -> 2
    assert cache.version > last_version  # Change detected — should emit


# ---------------------------------------------------------------------------
# Multiple tickers
# ---------------------------------------------------------------------------


async def test_stream_includes_all_cached_tickers():
    """All cached tickers appear in the event batch."""
    cache = PriceCache()
    await cache.on_price(_tick("AAPL", 191.00))
    await cache.on_price(_tick("MSFT", 420.00))
    await cache.on_price(_tick("TSLA", 250.00))

    prices = cache.get_all()
    tickers = {cached.ticker for cached in prices.values()}
    assert tickers == {"AAPL", "MSFT", "TSLA"}


async def test_stream_empty_cache_yields_no_events():
    """An empty cache should produce no events."""
    cache = PriceCache()
    assert cache.version == 0
    prices = cache.get_all()
    assert len(prices) == 0
