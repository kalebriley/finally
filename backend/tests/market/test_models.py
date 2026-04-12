"""Tests for market data models (PriceTick, CachedPrice)."""

import dataclasses
from datetime import datetime, timezone

from app.market.models import CachedPrice, PriceTick


# ---------------------------------------------------------------------------
# PriceTick
# ---------------------------------------------------------------------------


def test_price_tick_is_dataclass():
    assert dataclasses.is_dataclass(PriceTick)


def test_price_tick_creation():
    now = datetime.now(timezone.utc)
    tick = PriceTick(ticker="AAPL", price=191.42, prev_close=190.00, timestamp=now)
    assert tick.ticker == "AAPL"
    assert tick.price == 191.42
    assert tick.prev_close == 190.00
    assert tick.timestamp is now


def test_price_tick_stores_float_price():
    now = datetime.now(timezone.utc)
    tick = PriceTick(ticker="MSFT", price=420.50, prev_close=418.00, timestamp=now)
    assert isinstance(tick.price, float)
    assert isinstance(tick.prev_close, float)


def test_price_tick_timestamp_is_datetime():
    now = datetime.now(timezone.utc)
    tick = PriceTick(ticker="TSLA", price=250.00, prev_close=250.00, timestamp=now)
    assert isinstance(tick.timestamp, datetime)


def test_price_tick_equality():
    now = datetime.now(timezone.utc)
    t1 = PriceTick(ticker="AAPL", price=191.00, prev_close=190.00, timestamp=now)
    t2 = PriceTick(ticker="AAPL", price=191.00, prev_close=190.00, timestamp=now)
    assert t1 == t2


def test_price_tick_inequality():
    now = datetime.now(timezone.utc)
    t1 = PriceTick(ticker="AAPL", price=191.00, prev_close=190.00, timestamp=now)
    t2 = PriceTick(ticker="AAPL", price=192.00, prev_close=190.00, timestamp=now)
    assert t1 != t2


# ---------------------------------------------------------------------------
# CachedPrice
# ---------------------------------------------------------------------------


def test_cached_price_is_dataclass():
    assert dataclasses.is_dataclass(CachedPrice)


def test_cached_price_creation():
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="AAPL",
        price=191.42,
        prev_price=191.38,
        prev_close=190.00,
        day_change=1.42,
        day_change_pct=0.747,
        direction="up",
        timestamp=now,
    )
    assert cp.ticker == "AAPL"
    assert cp.price == 191.42
    assert cp.prev_price == 191.38
    assert cp.prev_close == 190.00
    assert cp.day_change == 1.42
    assert cp.day_change_pct == 0.747
    assert cp.direction == "up"
    assert cp.timestamp is now


def test_cached_price_direction_up():
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="AAPL", price=192.00, prev_price=191.00, prev_close=190.00,
        day_change=2.00, day_change_pct=1.05, direction="up", timestamp=now,
    )
    assert cp.direction == "up"


def test_cached_price_direction_down():
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="AAPL", price=189.00, prev_price=191.00, prev_close=190.00,
        day_change=-1.00, day_change_pct=-0.53, direction="down", timestamp=now,
    )
    assert cp.direction == "down"


def test_cached_price_direction_flat():
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="AAPL", price=191.00, prev_price=191.00, prev_close=190.00,
        day_change=1.00, day_change_pct=0.53, direction="flat", timestamp=now,
    )
    assert cp.direction == "flat"


def test_cached_price_timestamp_is_datetime():
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="AAPL", price=191.00, prev_price=191.00, prev_close=190.00,
        day_change=1.00, day_change_pct=0.53, direction="flat", timestamp=now,
    )
    assert isinstance(cp.timestamp, datetime)


def test_cached_price_negative_day_change():
    """Negative day_change when price is below prev_close."""
    now = datetime.now(timezone.utc)
    cp = CachedPrice(
        ticker="TSLA", price=245.00, prev_price=248.00, prev_close=250.00,
        day_change=-5.00, day_change_pct=-2.00, direction="down", timestamp=now,
    )
    assert cp.day_change < 0
    assert cp.day_change_pct < 0
